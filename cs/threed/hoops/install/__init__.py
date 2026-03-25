# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class RegisterHoopsPlugin(object):

    def run(self):
        from cdb.acs.acstools import cli_register
        cli_register("hoops")


pre = []
post = [RegisterHoopsPlugin]
