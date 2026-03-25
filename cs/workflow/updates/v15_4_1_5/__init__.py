#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb import transaction
from cdb.comparch import protocol


class MigrateEMailSettingsInfoMessage(object):
    def run(self):
        with transaction.Transaction():
            sqlapi.SQLinsert(
                "INTO cdb_usr_setting (setting_id, setting_id2, personalnummer, value, cdb_classname) "
                "SELECT 'user.email_wf_info', setting_id2, personalnummer, value, cdb_classname "
                "FROM cdb_usr_setting WHERE setting_id='user.email_with_task'"
            )

            sqlapi.SQLinsert(
                "INTO cdb_usr_setting_long_txt (setting_id, setting_id2, personalnummer, zeile, text) "
                "SELECT 'user.email_wf_info', setting_id2, personalnummer, zeile, text "
                "FROM cdb_usr_setting_long_txt WHERE setting_id='user.email_with_task'"
            )

            protocol.logMessage(
                "cdb_usr_setting and cdb_usr_setting_long_txt table update successful after"
                "adding a new variable in the user settings."
            )

pre = []
post = [MigrateEMailSettingsInfoMessage]
