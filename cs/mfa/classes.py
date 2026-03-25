#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Data dictionary classes for MFA
"""

from __future__ import unicode_literals

from cdb import util
from cdb.objects.core import Object
from cdb.objects.org import User

from cs.mfa import exc


class MFAPluginSettings(Object):
    """
    MFA auth chain configuration
    """
    __classname__ = "cs_mfa_auth_plugin_settings"
    __maps_to__ = "cs_mfa_auth_plugin_settings"


class CounterUsageCache(Object):
    """
        Has one or no entry per cdb_person, purpose with the last successfully
        used counter value for a given purpose e.g. totp
    """
    __classname__ = "cs_mfa_counter_usage_cache"
    __maps_to__ = "cs_mfa_counter_usage_cache"

    @classmethod
    def insert_or_update_counter_value(cls, external_username, purpose, counter_value):
        """
        Update the last used counter for given user

        The cache stores the last used counter value to prevent
        replay attacks, where old codes are used again.

        :param external_username: Username matching a login in elements.
        :param purpose: Purpose of this counter, which plugin used this
        :param counter_value: Value of the counter
        """
        user = User.ByKeys(login=external_username)
        cuc = CounterUsageCache.ByKeys(login=external_username, purpose=purpose)

        if cuc:
            if cuc.CheckAccess('save'):
                cuc.value = counter_value
            else:
                raise exc.CounterAccessError()
        else:
            if util.check_access(cls.__maps_to__, the_keys={}, access="create"):
                new_obj = cls.Create(**dict(
                    person_object_id=user.cdb_object_id,
                    personalnummer=user.personalnummer,
                    login=user.login,
                    purpose=purpose,
                    value=counter_value
                ))
                if new_obj is None:
                    raise exc.CounterAccessError()
            else:
                raise exc.CounterAccessError()


class UserCredentials(Object):
    """
        Entity to store generic encrypted credentials for a given purpose
        (e.g. totp) assigned 1:n to system users. The encryption of the values
        is *NOT* part of this entity and can be different for different purposes.
        Due to some special cases it stores/updates/uses optionally
        a second index (external_username).
    """
    __classname__ = "cs_user_credentials"
    __maps_to__ = "cs_user_credentials"

    @classmethod
    def _get_credential(cls, user, purpose, external_username=None):
        """
        Gets the encrypted credential from the database

        Either indexed by user or external username

        :param user: `User` object
        :param purpose: The purpose to use
        :param external_username: The external name to look for
        """
        if isinstance(user, User):
            args = dict(person_object_id=user.cdb_object_id, purpose=purpose)
        else:
            args = dict(external_username=external_username, purpose=purpose)
        db_cred = cls.ByKeys(**args)
        if db_cred:
            if db_cred.CheckAccess('read'):
                return db_cred
            else:
                raise exc.CredentialAccessError()

    @classmethod
    def _get_or_create_credential(cls, user, purpose, create_if_missing=False, external_username=None):
        """
        Gets or inserts a credential for a given purpose and user

        :param user: `User` object
        :param purpose: The purpose to use
        :param create_if_missing: Should a set of credentials be generated.
        :param external_username: The external name to look for

        :returns: The credentials
        """
        db_cred = cls._get_credential(user, purpose, external_username)
        if db_cred:
            # update second key when changed
            if db_cred.external_username != external_username:
                db_cred.external_username = external_username
            return db_cred
        if create_if_missing:
            if util.check_access(cls.__maps_to__, the_keys={}, access="create"):
                db_cred = cls.Create(**dict(
                    person_object_id=user.cdb_object_id,
                    personalnummer=user.personalnummer,
                    external_username=external_username,
                    purpose=purpose
                ))
            else:
                db_cred = None
            if not db_cred:
                raise exc.FailedCredentialsCreationError(
                    'for external_username {} and purpose {}'.format(
                        external_username, purpose))
        else:
            # FIXME: use a label here
            raise exc.MissingCredentialsError(
                'for external_username {} and purpose {}'.format(
                    external_username, purpose))
        return db_cred

    @classmethod
    def get_encrypted_credential(cls, user, purpose, external_username=None):
        """ Returns ***encrypted*** credentials """
        db_cred = cls._get_or_create_credential(
            user=user, purpose=purpose, external_username=external_username)
        return db_cred.GetText('cs_user_credentials_txt')

    @classmethod
    def set_encrypted_credential(cls, user, purpose, credential, external_username=None):
        """ Should be used to store already ***encrypted*** credentials

        :param user: `User` object
        :param purpose: The purpose to use
        :param credential: The credential to store, should be encrypted.
        :param external_username: The external name to look for
        """
        db_cred = cls._get_or_create_credential(
            user=user, purpose=purpose, create_if_missing=True,
            external_username=external_username)

        if db_cred.CheckAccess("write"):
            db_cred.SetText('cs_user_credentials_txt', credential)
        else:
            raise exc.CredentialAccessError()

    @classmethod
    def delete_encrypted_credential(cls, user, purpose, external_username=None):
        """ Allow deletion of the stored credentials

            Useful for admin reset of credentials.

            :param user: `User` object
            :param purpose: The purpose to use
            :param external_username: The external name to look for
        """
        if user is not None:
            db_cred = cls.ByKeys(personalnummer=user.personalnummer,
                                 purpose=purpose)
        else:
            db_cred = cls.ByKeys(external_username=external_username,
                                 purpose=purpose)
        if db_cred:
            if db_cred.CheckAccess('delete'):
                db_cred.Delete()
            else:
                raise exc.FailedCredentialsDeletionError()

    @classmethod
    def has_credentials_for_purpose(cls, purpose):
        """
        Checks whether a credential for a given purpose exists.

        Useful to check whether a new application secret should exist already.

        :param purpose: The purpose to check
        :returns: True or False.
        """
        return bool(cls.KeywordQuery(purpose=purpose))
