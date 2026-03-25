#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import logging
import os
import shutil
import sys

from cdb import CADDOK, sqlapi, transaction
from cdb.comparch import protocol

log = logging.getLogger(__name__)


class InitNotificationSettings(object):
    __tables__ = ["cdb_setting", "cdb_usr_setting"]

    def run(self):
        """
        copy defaults and user settings from user.email_with_task (cs.shared)
        """
        with transaction.Transaction():
            for table in self.__tables__:
                columns = sqlapi.RecordSet2("cdb_columns", "table_name='%s'" % table)
                col_str = ", ".join(
                    c.column_name for c in columns if c.column_name != "setting_id"
                )
                sqlapi.SQLinsert_if_no_conflict(
                    "INTO %s (setting_id, %s) "
                    "SELECT 'user.email_with_sharing', %s FROM %s "
                    "WHERE setting_id='user.email_with_task'"
                    % (table, col_str, col_str, table)
                )


class CreateShareObjectsQueueConfTask(object):
    def run(self):
        conf = "share_objects_queue.conf"
        try:
            conf_path = os.path.join(CADDOK.BASE, "etc", conf)
            if os.path.exists(conf_path):
                protocol.logMessage("{} already exists".format(conf_path))
                return
            protocol.logMessage("Creating default {}".format(conf_path))
            source = os.path.abspath(
                os.path.join(__file__, "..", "..", "templates", "etc", conf)
            )
            shutil.copyfile(source, conf_path)
        except Exception as exc:  # pylint: disable=W0703
            protocol.logError(
                "Failed to copy %s to %s" % (source, conf_path), "%s" % exc
            )


post = [InitNotificationSettings, CreateShareObjectsQueueConfTask]

if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)-8s] [%(name)s] %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    InitNotificationSettings().run()
    CreateShareObjectsQueueConfTask().run()
