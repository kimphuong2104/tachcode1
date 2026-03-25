# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.threed.hoops.install import RegisterHoopsPlugin


class RegisterHoopsPluginForVersion1550(RegisterHoopsPlugin):
    pass


pre = []
post = [RegisterHoopsPluginForVersion1550]
