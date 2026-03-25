#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals, print_function
from cdb.testcase import RollbackTestCase

from cs.mfa.classes import UserCredentials
from cs.mfa.exc import MissingCredentialsError
from cs.mfa.tests.test_utils import with_faked_caddok_pw


class TestUserCredentials(RollbackTestCase):
    def setUp(self):
        RollbackTestCase.setUp(self)
        with_faked_caddok_pw(self)
        UserCredentials.Query().Delete()

    def test_missing_encrypted_credential(self):
        with self.assertRaises(MissingCredentialsError):
            cred = UserCredentials.get_encrypted_credential(self.user, 'no_credential_for_this_purpose_is_saved')
            self.assertIsInstance(cred, basestring)

    def test_set_and_get_encrypted_credential(self):
        purpose = 'testing_purpose'
        # as we do not test the encryption here but only the storage apis it is not encrypted
        encrypted_secret = 'highly_encrypted_secret'
        UserCredentials.set_encrypted_credential(self.user, purpose, encrypted_secret)
        self.assertEqual(UserCredentials.get_encrypted_credential(self.user, purpose), encrypted_secret)

    def test_has_credentials_for_purpose(self):
        purpose = 'testing'
        self.assertEqual(UserCredentials.has_credentials_for_purpose(purpose), False)
        UserCredentials.set_encrypted_credential(self.user, purpose, 'secret')
        self.assertEqual(UserCredentials.has_credentials_for_purpose(purpose), True)

    def tearDown(self):
        RollbackTestCase.tearDown(self)


if __name__ == "__main__":
    import nose
    nose.runmodule()
