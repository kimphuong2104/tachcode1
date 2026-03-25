#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module misc

This is the documentation for the misc module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def is_installed(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False
