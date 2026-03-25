#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import os
import logging

from passlib.totp import TOTP
from webtest import TestApp as Client

from cdb import CADDOK
from cdb.authentication.iauthenticator import AuthError, AuthResult
from cdb.testcase import RollbackTestCase
from cs.platform.web.root import Root

from cs.mfa.classes import UserCredentials
from cs.mfa import exc
from cs.mfa.tests.test_utils import with_faked_caddok_pw
from cs.mfa.totp import TOTPSupport, TOTP_2FA_Authenticator


LOG = logging.getLogger(__name__)


class TestTOTP_2FA(RollbackTestCase):
    def setUp(self):
        app = Root()
        self.client = Client(app)
        self.stored_cred_path = TOTP_2FA_Authenticator.SECRETS_PATH
        try:
            TOTPSupport.load_application_secrets(self.stored_cred_path)
        except exc.NoApplicationKeyError:
            TOTPSupport.init_application_secrets(self.stored_cred_path)
        self.factory = TOTPSupport.init_wallet(self.stored_cred_path)

        RollbackTestCase.setUp(self)
        with_faked_caddok_pw(self)
        UserCredentials.Query().Delete()

    def tearDown(self):
        RollbackTestCase.tearDown(self)
        if os.path.isfile(self.stored_cred_path):
            os.unlink(self.stored_cred_path)

    def _enroll_user(self, user):
        """ enrolls a given user by generating and storing a totp secret for that user """
        return TOTPSupport.generate_totp(self.factory, self.user, 'totp')

    def test_authenticate_successfully_with_totp_and_pw(self):
        """ authenticate with totp enrolled for user, correct totp value and correct pw """
        self._enroll_user(self.user)
        user_totp = TOTPSupport.get_totp(self.factory, self.user, 'totp')
        token = user_totp.generate().token
        totp_auth = TOTP_2FA_Authenticator(totp_wallet_path=self.stored_cred_path)
        errors = []
        try:
            res = totp_auth.authenticate(username=self.username, mfacode=token,
                                         password=self.user_pw, iso_lang='de')
        except AuthError as e:
            errors.append(unicode(e))
        self.assertTrue(isinstance(res, AuthResult) and res.success and len(errors) == 0)

    def test_authenticate_with_incorrect_totp_and_pw(self):
        """ authenticate with totp enrolled for user, incorrect totp value and correct pw """
        self._enroll_user(self.user)
        totp_auth = TOTP_2FA_Authenticator(totp_wallet_path=self.stored_cred_path)
        errors = []
        try:
            res = totp_auth.authenticate(username=self.username,
                                         mfacode='incorrect',
                                         password=self.user_pw, iso_lang='de')
        except AuthError as e:
            errors.append(unicode(e))
        self.assertTrue(isinstance(res, AuthResult) and not res.success and len(errors) == 0)

    def test_authenticate_with_correct_totp_and_incorrect_pw(self):
        """ authenticate with totp enrolled for user, correct totp value and incorrect pw """
        self._enroll_user(self.user)
        user_totp = TOTPSupport.get_totp(self.factory, self.user, 'totp')
        token = user_totp.generate().token
        totp_auth = TOTP_2FA_Authenticator(totp_wallet_path=self.stored_cred_path)
        errors = []
        try:
            res = totp_auth.authenticate(username=self.username, mfacode=token,
                                         password='incorrect', iso_lang='de')
        except AuthError as e:
            errors.append(unicode(e))
        self.assertTrue(isinstance(res, AuthResult) and not res.success and len(errors) == 0)

    def test_authenticate_without_totp(self):
        """ authenticate with totp *not* enrolled for user, empty totp value and correct pw and get the correct auto enrollment response """
        totp_auth = TOTP_2FA_Authenticator(totp_wallet_path=self.stored_cred_path)
        auth_result = totp_auth.authenticate(username=self.username,
                                             password=self.user_pw, iso_lang='de')
        self.assertEqual(auth_result.success, False)
        self.assertIn('mfa_qr_code', auth_result.data)
        self.assertIn('mfa_base32_code', auth_result.data)
        # qr code check of information needs qrcode recognition which is actually not installed
        self.assertNotEqual(auth_result.data['mfa_qr_code'], '')

        # load user totp credential to ensure the enrollment response does contain the right/needed information to login afterwards
        user_totp = TOTPSupport.get_totp(self.factory, self.user, 'totp')
        self.assertEqual(auth_result.data.get('mfa_base32_code'), user_totp.base32_key)
        LOG.info(auth_result.data)

    def test_authenticate_with_basic_auth_and_totp(self):
        """ authenticate with totp enrolled for user, correct totp value and correct basic auth """
        enrolled_totp = self._enroll_user(self.user)
        self.client.set_authorization(('Basic', (self.username, self.user_pw)))
        headers = {
            "HTTP_X_CON_MFACODE": "{}".format(enrolled_totp.generate().token).encode('utf-8')
        }
        response = self.client.get('/', headers=headers, status=302)
        LOG.info(response)

    def test_auto_enrollment_login(self):
        """ authenticate with totp *not* enrolled for user, empty totp value and correct pw, receive the auto enrollment response and login with correct totp value """
        totp_auth = TOTP_2FA_Authenticator(totp_wallet_path=self.stored_cred_path)
        LOG.info('auth without totp enrolled - should fail')
        auth_result = totp_auth.authenticate(username=self.username,
                                             password=self.user_pw, iso_lang='de')
        self.assertEqual(auth_result.success, False)
        LOG.info('get psk from auto enrollment response')
        user_totp = TOTP(auth_result.data.get('mfa_base32_code'))
        token = user_totp.generate().token
        LOG.info('auth with totp enrolled after enrollment')
        auth_result_two = totp_auth.authenticate(username=self.username,
                                                 mfacode=token,
                                                 password=self.user_pw,
                                                 iso_lang='de')
        self.assertEqual(auth_result_two.success, True)
