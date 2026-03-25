# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Create activitystream_daily_mail.conf
"""
import io
import os

from cdb import CADDOK
from cdb.comparch import protocol


class CreateDailyMailConfTask(object):
    def run(self):
        conf_path = os.path.join(CADDOK.BASE, "etc", "activitystream_daily_mail.conf")
        if os.path.exists(conf_path):
            protocol.logMessage("{} already exists".format(conf_path))
            return
        protocol.logMessage("Creating default {}".format(conf_path))
        with io.open(conf_path.encode("utf-8"), "w", encoding="utf_8_sig") as f:
            f.write(u'CADDOK_DEBUG="FALSE"\n')


pre = []
post = [CreateDailyMailConfTask]

if __name__ == "__main__":
    CreateDailyMailConfTask().run()
