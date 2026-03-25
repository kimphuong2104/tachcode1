#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

import sys

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import misc

# find and import available converters
_O2K7_CONVERTERS = {}
_APPLICATION_NAMES = {}


def _register(mod):
    for item in [(myname, value, "%s.%s" % (__name__, myname))
                 for myname, value in mod.__dict__.items()
                 if hasattr(value, "__module__")]:
        if hasattr(item[1], "__conversions__"):
            # currently one converter type is supported:
            # based on pdfconverter.O2K7PDFConverter.
            if pdfconverter.O2K7PDFConverter in item[1].__mro__:
                for c in getattr(item[1], "__conversions__"):
                    _O2K7_CONVERTERS[c] = item[1]
                    _APPLICATION_NAMES[c] = getattr(item[1], "__application_name__")


for fname in os.listdir(os.path.dirname(__file__)):
    name, ext = os.path.splitext(fname)
    try:
        if ext == ".py" and not name.find("__init__") == 0:
            if sys.platform == "win32":
                _register(__import__("%s.%s" % (__name__, name), globals(), locals(), ['*']))
    except ImportError:
        # import errors can occur becuase of win32 imports...
        misc.log_traceback("Failed to import module %s:" % name)


def GetConverter(suffix):
    return _O2K7_CONVERTERS.get(suffix, None)


def RegisterCustomConverter(fqpyname):
    try:
        _register(__import__(fqpyname, globals(), locals(), ['*']))
    except ImportError:
        # import errors can occur becuase of win32 imports...
        misc.log_traceback("Failed to import module %s" % fqpyname)
