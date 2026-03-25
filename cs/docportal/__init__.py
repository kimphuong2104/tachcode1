# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
cs.docportal

The CONTACT Documentation Portal

A Documentation Portal hosting some CONTACT application documentation.
Usually hosting the entirety of a single umbrella release (e.g. 15.4)
or multiple separate umbrella releases side-by-side (e.g. 15.0-15.4).
"""
from os import environ

isCDBEnvironment = bool(environ.get('CADDOK_BASE'))


class DocPortalError(Exception):
    pass


class EmptyDocPortalError(DocPortalError):
    pass


class DocPortalConfigurationError(DocPortalError):
    pass
