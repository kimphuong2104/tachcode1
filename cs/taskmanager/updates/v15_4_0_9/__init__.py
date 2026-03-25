#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.comparch import protocol


class UpdateAppSettings(object):
    def run(self):
        protocol.logMessage(
            "skipping obsolete update script 'UpdateAppSettings'",
        )


pre = []
post = [UpdateAppSettings]
