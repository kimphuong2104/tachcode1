#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This update task disables daily mails for existing installations where
the update provides a new setting. The convoluted nature of this update
is required due to the update architecture and the specific requirements
for the behavior of this update.

For new installations, this update script does not run which ensures, that
all users get daily mails by default. For existing installations, if the
setting exists (was created by the user) we respect that. If it doesn't, we
update the default value of the new setting to 0, as we do not want
to introduce behavioral changes with SL-updates.

Updating the setting in the Pre-Task directly isn't possible, as cdbpkg sync
will complain about a conflicting update. Detecting whether the setting
was there before can not be done in the Post-task, as it is run after the
configuration has been written to the database. This update task therefore
splits the task into two separate actions.
"""

from __future__ import absolute_import

FLAG_SETTING_ID = "cs.activitystream.updates.v15_3_1_7.DailyMailPropertyUpdater"


class DailyMailPropertyUpdater(object):
    def set_flag(self):
        from cdb import util

        ins = util.DBInserter("cdb_usr_setting")
        ins.add("setting_id", FLAG_SETTING_ID)
        ins.add("setting_id2", "")
        ins.add("personalnummer", "aspostingqueue")
        ins.add("cdb_classname", "cdb_usr_setting")
        ins.add("value", "1")
        ins.insert()

    def is_flag_set(self):
        from cdb import sqlapi

        setting = sqlapi.RecordSet2(
            "cdb_usr_setting", "setting_id='{}'".format(FLAG_SETTING_ID)
        )
        return bool(setting)

    def delete_flag(self):
        from cdb import sqlapi

        sqlapi.SQLdelete(
            "FROM cdb_usr_setting WHERE setting_id = '{}'".format(FLAG_SETTING_ID)
        )


class DailyMailPropertyUpdaterPre(DailyMailPropertyUpdater):
    """
    Set a flag if the record did not exist pre-update
    """

    def run(self):
        from cdb import sqlapi
        from cdb.comparch import protocol

        protocol.logMessage("Checking whether email_daily_as setting existed")
        setting = sqlapi.RecordSet2("cdb_setting", "setting_id='user.email_daily_as'")
        if not setting:
            protocol.logMessage(
                "Setting did not exist, will set it to '0' in post update script"
            )
            self.set_flag()
        else:
            protocol.logMessage("Setting existed, will respect the customized value")


class DailyMailPropertyUpdaterPost(DailyMailPropertyUpdater):
    """
    Set user.email_daily_as setting default value to 0 if flag is set
    """

    def run(self):
        from cdb import sqlapi
        from cdb.comparch import protocol

        if self.is_flag_set():
            protocol.logMessage(
                "Patching cdb_setting to disable email_daily_as by default"
            )
            setting = sqlapi.RecordSet2(
                "cdb_setting", "setting_id='user.email_daily_as'", updatable=1
            )
            setting[0].update(default_val="0")
            self.delete_flag()


pre = [DailyMailPropertyUpdaterPre]
post = [DailyMailPropertyUpdaterPost]

if __name__ == "__main__":
    DailyMailPropertyUpdaterPre().run()
    DailyMailPropertyUpdaterPost().run()
