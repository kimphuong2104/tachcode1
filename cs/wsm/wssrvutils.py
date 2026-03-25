# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module wssrvutils

This is the documentation for the wssrvutils module.
"""

from __future__ import absolute_import

import six
import base64
import json


__docformat__ = "restructuredtext en"
__revision__ = "$Id: python_template 4042 2019-08-27 07:30:13Z js $"
# Exported objects
__all__ = []


def json_to_b64_str(jsondata):
    if six.PY2:
        jdump = json.dumps(jsondata, encoding="utf-8")
        encodedDump = base64.standard_b64encode(jdump)
    else:
        jdump = json.dumps(jsondata).encode("utf-8")
        encodedDump = base64.standard_b64encode(jdump).decode("utf-8")
    return encodedDump
