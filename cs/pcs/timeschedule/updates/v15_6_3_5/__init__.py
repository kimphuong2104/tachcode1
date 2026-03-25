#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import json

from cdb import sqlapi, transactions, util
from cdb.comparch import protocol


class MigrateStartDates:
    SECONDS_PER_DAY = 60 * 60 * 24
    TEXT_KEYS = ["setting_id", "setting_id2", "personalnummer"]

    def _migrate(self, settings_json):
        settings_dict = json.loads(settings_json)
        gantt = settings_dict.get("gantt", {})
        startDate = gantt.get("startDate", None)
        if startDate:
            settings_dict["gantt"]["startDate"] = startDate / self.SECONDS_PER_DAY
        return json.dumps(settings_dict)

    def migrate_settings(self):
        settings = sqlapi.RecordSet2(
            "cdb_usr_setting",
            "setting_id = 'cs-pcs-timeschedule-web'",
        )
        for setting in settings:
            if setting.cdb_classname == "cdb_usr_setting":
                setting.update(value=self._migrate(setting.value))
            elif setting.cdb_classname == "cdb_usr_setting_long":
                # update long text
                key_values = [setting[k] for k in self.TEXT_KEYS]
                value = util.text_read(
                    "cdb_usr_setting_long_txt",
                    self.TEXT_KEYS,
                    key_values,
                )
                util.text_write(
                    "cdb_usr_setting_long_txt",
                    self.TEXT_KEYS,
                    key_values,
                    self._migrate(value),
                )
            else:
                protocol.logError(f"unknown settings class: {setting.cdb_classname}")

        protocol.logMessage("converted timeschedule start dates from seconds to days")

    def run(self):
        with transactions.Transaction():
            self.migrate_settings()


post = [MigrateStartDates]
