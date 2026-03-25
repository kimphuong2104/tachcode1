#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Auth Plugin that implements the TOTP method


"""

from __future__ import unicode_literals, print_function

import base64
import datetime
import logging
import os

from passlib import totp
from passlib.exc import TokenError

import cdbwrapc

from cdb import CADDOK
from cdb import fls
from cdb import i18n
from cdb import rte
from cdb import sig
from cdb import ue
from cdb import util

from cdb.authentication.iauthenticator import AuthResult
from cdb.objects.org import User

from cs.mfa import MFAAuthenticator
from cs.mfa import exc
from cs.mfa.classes import CounterUsageCache, UserCredentials


LOG = logging.getLogger(__name__)


class TOTP_2FA_Authenticator(MFAAuthenticator):
    """
    TOTP Plugin

    This plugin implements the TOTP method,
    as specified in :rfc:`6238`.
    """

    PLUGIN_NAME = 'totp'
    SECRETS_PATH = 'cs.platform/auth/totp/appkey'

    MFA_CONFIG = {
        'mfa_label': 'cs_mfa_login_totp_label',
        'mfa_icon': '/static/images/Password-White.png',
        'mfa_placeholder': 'cs_mfa_login_totp_label',
    }

    def __init__(self, totp_wallet_path=None, *args, **kwargs):
        """
        :param totp_wallet_path: Path to the secret key file used
        """
        super(TOTP_2FA_Authenticator, self).__init__(self.PLUGIN_NAME)
        self._handle_lic()
        self.otp_purpose = self.PLUGIN_NAME
        self.stored_cred_path = totp_wallet_path or self.SECRETS_PATH
        self._token_factory = None

    def token_factory(self):
        """
        Init the wallet for the secret keys
        """
        if self._token_factory is None:
            try:
                self._token_factory = TOTPSupport.init_wallet(self.stored_cred_path)
            except exc.NoApplicationKeyError:
                if UserCredentials.has_credentials_for_purpose(self.otp_purpose):
                    LOG.warning("TOTP store credentials %s does not exists, but there "
                                "are already user credentials for TOTP. "
                                "Existing user credentials will not be useable.",
                                self.stored_cred_path)
                raise
        return self._token_factory

    def _handle_lic(self):
        """
        Allocate the proper license
        """
        try:
            fls.allocate_server_license('MFA_002')
            self._lic = self._lic and True
        except fls.LicenseError as e:
            LOG.exception(e)
            self._lic = False
            self._lic_errors.append(e)

    def auth_otp(self, username, cred, timestamp=None):
        """ Run a TOTP check for the given username

            :param username: The login to use
            :param cred: The totp credentials offered by the user
            :returns: Success code
        """
        try:
            db_totp = TOTPSupport.get_totp(
                self.token_factory(),
                user=User.ByKeys(login=username),
                purpose=self.otp_purpose,
                external_username=username)

            last_counter_obj = CounterUsageCache.ByKeys(
                login=username, purpose=self.otp_purpose)
            last_counter = last_counter_obj.value if last_counter_obj else None
            match = db_totp.match(
                cred, last_counter=last_counter, time=timestamp)
            if match:
                CounterUsageCache.insert_or_update_counter_value(
                    username, self.otp_purpose, match.counter)
                return True
        except exc.MissingCredentialsError:
            raise
        except TokenError as e:
            LOG.info('Token error on auth for %s: %s (%s)',
                     username, type(e), e)
        return False

    def _generate_otp_psk(self, user, external_username=None):
        """ Create the pre-shared Key for TOTP

            :param user: The login name of the user
            :param external_username: external name for the user
        """
        user_obj = User.ByKeys(login=user)
        if user_obj is None:
            raise exc.MFAException("User not found", user)
        return TOTPSupport.generate_totp_code(
            self.token_factory(), user_obj, self.otp_purpose, external_username)

    def authenticate(self, **kwargs):
        """
        Authenticate a user

        Checks the mfa code and delegates to the subsequent plugin.

        Expects the following parameters in the arguments.
        Other args are just passed through to the subsequent plugin.

        :param username: external name of the user
        :param iso_lang: (optional) language to use for messages
        :param mfacode: The mfa code to check

        :returns: `AuthResult` object
        """
        username = kwargs.get('username', '')
        iso_lang = kwargs.get('iso_lang', i18n.default())

        # Handle and remove mfacode from kwargs
        try:
            otp_credential = kwargs.pop('mfacode')
        except KeyError:
            otp_credential = ''

        default_login_fail = util.CDBMsg(
            util.CDBMsg.kFatal,
            "branding_login_failure").getText(iso_lang, True)

        response = {
            'msg': default_login_fail,
            'force_pwd_change': False,
            'authenticated_login': None
        }

        if not self._lic:
            LOG.error('Authentication failed due to missing licenses %s',
                      ",".join([x.alic for x in self._lic_errors]))
            response['msg'] = "\n".join([x.message for x in self._lic_errors])
            return AuthResult(False, response)

        # Try to do this in constant time
        # So we always call the backend & totp code.

        # Figure out the correct username by calling the successor first
        try:
            result = self.auth_plugin_successor.authenticate(**kwargs)
        except Exception:
            LOG.traceback("Successor plugin failed")
            result = AuthResult(False, response)

        # If it succeeded, we have the correct login now, if not we don't care
        authenticated_user = result.data.get('authenticated_user', username)

        totp_success = False
        try:
            totp_success = self.auth_otp(authenticated_user, otp_credential)
        except exc.MissingCredentialsError:
            if self.should_auto_enroll(authenticated_user, result.success):
                result = self.auto_enrollment(
                    authenticated_user, username, response, iso_lang)

        LOG.info("TOTP code check for %s: %s", username, totp_success)

        # Final result
        auth_success = result.success and totp_success
        data = response if not result.success else result.data

        return AuthResult(auth_success, data)

    def should_auto_enroll(self, authenticated_user, auth_code):
        """
        Default trigger for auto enrollment
        """
        LOG.debug("Checking auto enrollment for %s", authenticated_user)
        return auth_code

    def auto_enrollment(self, authenticated_user, username, res, iso_lang):
        """
        Add the auto enrollment info to an auth response

        :param authenticated_user: The login of the user.
        :param username: The external username before transformations.
        :param res: The response dict to update.
        :param iso_lang: The language to use for messages.
        :returns: AuthResult object
        """
        try:
            img, code = self._generate_otp_psk(authenticated_user, username)
        except exc.MFAException:
            LOG.exception("Failed to generate new TOTP PSK for user '%s'",
                          authenticated_user)
            extra_msg = util.get_label_with_fallback(
                'qs_mfa_qr_code_enroll_failed', iso_lang)
        else:
            res['mfa_qr_code'] = img
            res['mfa_base32_code'] = code
            res['msg_title'] = util.get_label_with_fallback(
                'cs_mfa_qr_code_was_generated_title', iso_lang)

            extra_msg = util.get_label_with_fallback(
                'cs_mfa_qr_code_was_generated_msg', iso_lang)

        msg = res.get('msg')
        if msg:
            msg += '\n'
            msg += extra_msg
        else:
            msg = extra_msg

        res['msg'] = msg

        return AuthResult(False, res)


class TOTPSupport(object):
    @classmethod
    def init_wallet(cls, wallet_path):
        """
        Initialize the secrets wallet at the given path

        :param wallet_path: Path to the wallet secrets file.
        :param purpose: Purpose to check for.

        :returns: TOTP factory
        """
        LOG.info("Using wallet at %s", wallet_path)
        return cls.get_totp_factory(wallet_path)

    @classmethod
    def init_application_secrets(cls, secrets_path, store=None):
        """
        Write a new TOTP Secret into the secrets store
        """
        store = store if store else rte.get_runtime().secrets
        secret = totp.generate_secret()
        LOG.info("Creating new TOTP application secret at %s", secrets_path)
        store.store_secret(secrets_path, secret.encode('utf-8'))

    @classmethod
    def load_application_secrets(cls, secrets_path, store=None):
        """
        Fetch the application secrets from the secrets store
        """
        store = store if store else rte.get_runtime().secrets
        app_secrets = {}
        for version in range(0, 10):
            skey = store.resolve(secrets_path, version=version)
            if skey is None:
                break
            app_secrets["%d" % version] = skey.decode('utf-8')
        if not app_secrets:
            raise exc.NoApplicationKeyError()

        return app_secrets

    @classmethod
    def get_totp_factory(cls, path_to_secret):
        """
        Initialize the token factory
        """
        appsecret = cls.load_application_secrets(path_to_secret)
        try:
            return totp.TOTP.using(secrets=appsecret)
        except ValueError:
            # Format broken
            raise exc.MalformedEncryptionKeyFileError(path_to_secret)

    @classmethod
    def get_totp(cls, totp_factory, user, purpose, external_username=None):
        encrypted_user_totp = UserCredentials.get_encrypted_credential(
            user, purpose, external_username)
        return totp_factory.from_source(encrypted_user_totp)

    @classmethod
    def generate_totp(cls, totp_factory, user, purpose, external_username=None):
        user_totp = totp_factory.new()
        UserCredentials.set_encrypted_credential(
            user, purpose, user_totp.to_json(encrypt=True), external_username)
        return user_totp

    @classmethod
    def generate_totp_code(cls, totp_factory, user, purpose, external_username=None):
        user_totp = cls.generate_totp(
            totp_factory, user, purpose, external_username)
        label = util.get_label('cs_mfa_qr_code_label').format(
            username=external_username,
            branding_name_with_user=cdbwrapc.getBrandedShortVersion())
        issuer = util.get_label('cs_mfa_qr_code_issuer').format(
            username=external_username,
            branding_name=cdbwrapc.getApplicationWndName(external_username))

        uri = user_totp.to_uri(label=label, issuer=issuer)
        base32 = user_totp.base32_key
        return gen_base64_svg_qr_code(external_username, uri), base32

    @staticmethod
    @sig.connect(User, 'cs_mfa_delete_totp_credential', 'now')
    def reset_totp_from_ctx(user, ctx, *args, **kwargs):
        cdbwrapc.allocate_server_license("MFA_002")
        LOG.info("TOTP reset by admin for '%s'", user)
        try:
            TOTPSupport.reset_totp(user)
        except exc.FailedCredentialsDeletionError as e:
            raise ue.Exception("just_a_replacement", e.args)

    @classmethod
    def reset_totp(cls, user):
        UserCredentials.delete_encrypted_credential(user, TOTP_2FA_Authenticator.PLUGIN_NAME)


def gen_svg_qr_code(username, content):
    """
    Create a QR code for the given content

    :param content: The content to encode
    :returns: The encoded content
    """
    cdbwrapc.allocate_server_license("MFA_002")

    from qrcode.image import svg
    from qrcode import make as qrmake
    from io import BytesIO

    factory = svg.SvgImage
    img = qrmake(content, image_factory=factory)
    output = BytesIO()
    img.save(output)
    return output.getvalue()


def gen_base64_svg_qr_code(username, content):
    """Encode content as QR Code inside a data URL value

       :param content: The content to encode
       :returns: A data URL value to be embedded in web pages.
    """
    b64content = base64.b64encode(gen_svg_qr_code(username, content))
    return "data:image/svg+xml;base64,{}".format(b64content.decode('utf-8'))


if __name__ == "__main__":
    print("Writing TOTP MFA Configuration")
    plugin = TOTP_2FA_Authenticator()
    plugin.write_mfa_conf()
    TOTPSupport().init_application_secrets(plugin.SECRETS_PATH)
