#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import logging

from cs.activitystream.install import CreateDailyMailConfTask


class UpdateDailyMailConf(object):
    """
    Run install task even for updates
    """

    def run(self):
        log = logging.getLogger(__name__)
        log.info("Creating activitystream_daily_mail.conf if it does not exist yet...")
        CreateDailyMailConfTask().run()


pre = []
post = [UpdateDailyMailConf]

if __name__ == "__main__":
    UpdateDailyMailConf().run()
