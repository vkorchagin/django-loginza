# -*- coding: utf-8 -*-
try:
    from django.contrib.auth import get_user_model
except ImportError: # django < 1.5
    from django.contrib.auth.models import User
else:
    User = get_user_model()
from django.db import models
from django.utils import simplejson as json
from django.utils.translation import ugettext_lazy as _

from loginza import signals
from loginza.conf import settings

class IdentityManager(models.Manager):
    def from_loginza_data(self, loginza_data):
        try:
            identity = self.get(identity=loginza_data['identity'])
            # update data as some apps can use it, e.g. avatars
            identity.data = json.dumps(loginza_data)
            identity.save()
        except self.model.DoesNotExist:
            identity = self.create(
                identity=loginza_data['identity'],
                provider=loginza_data['provider'],
                data=json.dumps(loginza_data)
            )
        return identity


class UserMapManager(models.Manager):
    def for_identity(self, identity, request):
        try:
            user_map = self.get(identity=identity)
        except self.model.DoesNotExist:
            # if there is authenticated user - map identity to that user
            # if not - create new user and mapping for him
            if request.user.is_authenticated():
                user = request.user
            else:
                loginza_data = json.loads(identity.data)

                loginza_email = loginza_data.get('email', '')
                email = loginza_email if '@' in loginza_email else settings.DEFAULT_EMAIL

                loginza_nickname = loginza_data.get('nickname', None)

                # If nickname is not set - try to get it from first name
                if loginza_nickname is None or loginza_nickname == "":
                    # Try to obtain name from first name
                    try:
                        loginza_nickname = loginza_data['name']['first_name']
                    except KeyError:
                        loginza_nickname = None

                # if nickname is not set - try to get it from email
                # e.g. vgarvardt@gmail.com -> vgarvardt
                if loginza_nickname is None or loginza_nickname == "":
                    username = email.split('@')[0]
                else:
                    username = loginza_nickname

                # check duplicate user name
                username_counter = 1
                while True:
                    try:
                        existing_user = User.objects.get(username=username)
                        username = '%s%d' % (username, username_counter)
                        username_counter += 1
                    except User.DoesNotExist:
                        break

                user = User.objects.create_user(
                    username,
                    email
                )
            user_map = UserMap.objects.create(identity=identity, user=user)
            signals.created.send(request, user_map=user_map)
        return user_map


class Identity(models.Model):
    identity = models.CharField(_('identity'), max_length=255, unique=True)
    provider = models.CharField(_('provider'), max_length=255)
    data = models.TextField(_('data'))

    objects = IdentityManager()

    def __unicode__(self):
        return self.identity

    class Meta:
        ordering = ['id']
        verbose_name = _('identity')
        verbose_name_plural = _('identities')


class UserMap(models.Model):
    identity = models.OneToOneField(Identity, verbose_name=_('identity'))
    user = models.ForeignKey(User, verbose_name=_('user'))
    verified = models.BooleanField(_('active'), default=False, db_index=True)

    objects = UserMapManager()

    def __unicode__(self):
        return '%s [%s]' % (unicode(self.user), self.identity.provider)

    class Meta:
        ordering = ['user']
        verbose_name = _('user map')
        verbose_name_plural = _('user maps')
