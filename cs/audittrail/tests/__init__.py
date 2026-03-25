# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def setup():
    from cdb import testcase
    testcase.run_level_setup()
