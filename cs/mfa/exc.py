#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals
"""

FIXME: Document it

"""


class MFAException(Exception):
    pass


class MissingCredentialsError(MFAException):
    pass


class FailedCredentialsCreationError(MFAException):
    pass


class FailedCredentialsDeletionError(MFAException):
    pass


class NoApplicationKeyError(MFAException):
    pass


class MalformedEncryptionKeyFileError(MFAException):
    pass


class UserNotEnrolledError(MFAException):
    pass


class CredentialAccessError(MFAException):
    pass


class CounterAccessError(MFAException):
    pass


class ConfigAccessError(MFAException):
    pass
