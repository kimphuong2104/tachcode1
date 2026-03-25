# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Module reports

This is the documentation for the reports module.
"""

from __future__ import unicode_literals


class ReqIFInterfaceError(BaseException):
    pass


class InvalidEnumValueError(ReqIFInterfaceError):
    pass


class ReqIFValidationError(BaseException):
    pass
