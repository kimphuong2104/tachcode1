# coding: utf-8

from cdb import sqlapi, transaction
from cdb.comparch import protocol


class RemoveObsoleteTableSettings(object):
    """
    Delete obsolete entries from cdb_setting (replaced by cdb_usr_setting).
    """

    __table__ = "cdb_setting"
    __stmt__ = "setting_id='{}' AND setting_id2='{}'"
    __old_settings__ = [
        ("cs.taskmanager", "settings"),
        ("cs.webcomponents.table", "cs-taskmanager-web-tasks-table"),
    ]

    def run(self):
        for sid, sid2 in self.__old_settings__:
            for old in sqlapi.RecordSet2(
                self.__table__, self.__stmt__.format(sid, sid2)
            ):
                protocol.logWarning(
                    "deleted obsolete cdb_setting entry",
                    details_longtext=old.default_val,
                )

        with transaction.Transaction():
            for sid, sid2 in self.__old_settings__:
                sqlapi.SQLdelete(
                    "FROM {} WHERE {}".format(
                        self.__table__, self.__stmt__.format(sid, sid2)
                    )
                )


pre = []
post = [RemoveObsoleteTableSettings]
