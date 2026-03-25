# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Module reports

This is the documentation for the reports module.
"""

from __future__ import unicode_literals
from cs.requirements import rqm_utils


class XHTML(object):
    def convert(self, content):
        plaintext = rqm_utils.strip_tags(content)
        return plaintext
