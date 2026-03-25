#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from cdb import sqlapi, transactions
from cdb.comparch import protocol
from cdb.misc import ask_user

settings_sql = """
    INSERT INTO csweb_ui_settings
        (component, property, json_value, persno)
    SELECT COALESCE(setting_id, '') {concat_op} '-' {concat_op} COALESCE(setting_id2, ''),
    'app-settings' {collation}, value, personalnummer
    FROM cdb_usr_setting
    WHERE setting_id = 'cs-pcs-timeschedule-web'
"""

long_settings_sql = """
    INSERT INTO csweb_ui_settings_txt
        (component, property, text, persno, zeile)
    SELECT COALESCE(setting_id, '') {concat_op} '-' {concat_op} COALESCE(setting_id2, ''),
    'app-settings' {collation}, text, personalnummer, zeile
    FROM cdb_usr_setting_long_txt
    WHERE setting_id = 'cs-pcs-timeschedule-web'
"""

delete_stmt = "DELETE from {table} WHERE setting_id = 'cs-pcs-timeschedule-web'"


class MigrateOwnSettingsToWebUI:
    """
    Migrates timeschedule frontend app settings from PersonalSettings api to
    web ui settings api.
    """

    def format_collation(self, query):
        dbms = sqlapi.SQLdbms()
        collation = ""
        if dbms == sqlapi.DBMS_MSSQL:
            from cdb.mssql import CollationDefault

            collation = CollationDefault.get_default_collation()
        return query.format(concat_op=sqlapi.SQLstrcat(), collation=collation)

    def copy_settings(self):
        for query in [settings_sql, long_settings_sql]:
            sqlapi.SQL(self.format_collation(query))

    def delete_stale_settings(self):
        with transactions.Transaction():
            for table in ["cdb_usr_setting", "cdb_usr_setting_long_txt"]:
                sqlapi.SQL(delete_stmt.format(table=table))

    def run(self):
        with transactions.Transaction():
            self.copy_settings()
        protocol.logMessage(
            "settings have been migrated, to delete obsolete settings, run this update script directly"
        )


post = [MigrateOwnSettingsToWebUI]

if __name__ == "__main__":
    yes = ask_user("Are you sure you want to delete timeschedule settings?")
    if yes:
        MigrateOwnSettingsToWebUI().delete_stale_settings()
