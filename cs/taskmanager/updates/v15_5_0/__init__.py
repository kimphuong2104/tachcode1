#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json

from cdb import ddl, kernel, sqlapi, transactions
from cdb.comparch import content, modules, protocol
from cs.taskmanager.conf import Attribute, TaskClass


class UpdateTaskSettings(object):
    TXT = "cdb_usr_setting_long_txt"
    CLASS = "cdb_usr_setting"
    RENAMED = (
        ("notificationInterval", "refreshInterval"),
        ("currentUserView", "selectedView"),
        ("recentUserViews", "recentViews"),
    )

    def new_entry(self, persno, key, value):
        sqlapi.Record(
            self.CLASS,
            setting_id="cs.taskmanager",
            setting_id2=key,
            personalnummer=persno,
            value=json.dumps(value),
            cdb_classname=self.CLASS,
        ).insert()

    def migrate(self, record):
        old_setting = json.loads(record.text)

        for old_key, new_key in self.RENAMED:
            old_value = old_setting.get(old_key)
            if old_value:
                self.new_entry(record.personalnummer, new_key, old_value)

        record.delete()

    def run(self):
        records = sqlapi.RecordSet2(
            self.TXT,
            "setting_id = 'cs.taskmanager' AND setting_id2 = 'settings'",
        )
        for record in records:
            with transactions.Transaction():
                self.migrate(record)


class FilterConditionStructure(object):
    TABLE = "cs_tasks_user_view_condition"
    RENAMED = {
        "consider_absence": "absence",
    }
    DEADLINE = "deadline"
    NOT_RESPONSIBLE = {"types", "contexts"}
    RESPONSIBLE = {
        "my_personal",
        "my_roles",
        "substitutes",
        "absence",
        "users",
        "user_personal",
        "user_roles",
    }
    DEFAULT = {
        "types": [],
        "contexts": [],
        "deadline": {
            "active": None,
            "days": 5,
            "range": {
                "start": None,
                "end": None,
            },
        },
        "responsible": {
            "my_personal": True,
            "my_roles": False,
            "substitutes": True,
            "absence": True,
            "users": [],
            "user_personal": True,
            "user_roles": False,
        },
    }

    def migrate(self, old_text):
        text = old_text.replace("\\n", "")

        try:
            old_condition = json.loads(text)
        except ValueError:
            protocol.logError("cannot parse json: '{}'".format(text))
            return None

        new_condition = dict(self.DEFAULT)
        needs_attention = False

        for key, value in old_condition.items():
            new_key = key

            if key in self.RENAMED:
                new_key = self.RENAMED[key]
                new_condition[new_key] = value

            if new_key == self.DEADLINE:
                new_condition[new_key].update(value)
            if new_key in self.NOT_RESPONSIBLE:
                new_condition[new_key] = value
            elif new_key in self.RESPONSIBLE:
                new_condition["responsible"][new_key] = value
            elif new_key not in self.DEFAULT:
                needs_attention = True
                protocol.logWarning(
                    "unknown filter condition '{}' = {}".format(
                        new_key,
                        value,
                    ),
                )

        result = json.dumps(new_condition)

        if result == text:
            if needs_attention:
                protocol.logMessage(
                    "will ignore filter condition:\n'{}'".format(text),
                )
            return None

        protocol.logMessage(
            "will migrate filter condition:\n'{}'\n'{}'".format(
                text,
                result,
            ),
        )
        return result

    def run(self):
        rows = sqlapi.RecordSet2(
            sql="SELECT DISTINCT text FROM {}".format(self.TABLE),
        )
        updates = {}

        for row in rows:
            new_text = self.migrate(row.text)
            if new_text:
                updates[row.text] = new_text

        with transactions.Transaction():
            for old_text, new_text in updates.items():
                update_stmt = "{} SET text = '{}' WHERE text = '{}'".format(
                    self.TABLE,
                    new_text,
                    old_text,
                )
                sqlapi.SQLupdate(update_stmt)


class MigrateAttributes(object):
    def is_native_field(self, classname, field_name):
        table_name = kernel.getPrimaryTableForClass(classname)
        table = ddl.Table(table_name)
        return bool(table.hasColumn(field_name))

    def run(self):
        with transactions.Transaction():
            to_be_deleted = Attribute.KeywordQuery(
                column_object_id=[
                    "96e333a1-3deb-11e6-bec7-00aa004d0001",  # cs_tasks_col_deadline
                    "01e638a1-3dec-11e6-b6df-00aa004d0001",  # cs_tasks_col_tags
                    "5204d021-3dde-11e6-b91d-00aa004d0001",  # cs_tasks_col_read_status
                    "4d6d0160-6747-11e9-9ad7-6057182154bd",  # cs_tasks_col_classname
                    "5e3e7821-3deb-11e6-a189-00aa004d0001",  # cs_tasks_col_type
                ]
            )
            to_be_deleted.Delete()

            for task_class in TaskClass.Query():
                for attr in task_class.Attributes:
                    if not self.is_native_field(task_class.classname, attr.propname):
                        attr.Update(is_async=1)

                    if attr.propname == "getCsTasksProceedData":
                        attr.Update(propname="getCsTasksStatusData")

        protocol.logMessage("migrated cs_tasks_attribute entries")


class EnsureDefaultUserView(object):
    """Always roll back default user view"""

    __tables__ = [
        "cs_tasks_user_view",
    ]

    def run(self):
        protocol.logMessage("reverting patches in {}".format(self.__tables__))

        module = modules.Module.ByKeys("cs.taskmanager")
        for table_name in self.__tables__:
            content_filter = content.ModuleContentFilter([table_name])
            mc = modules.ModuleContent(
                module.module_id,
                module.std_conf_exp_dir,
                content_filter,
            )
            reverted = 0

            for mod_content in mc.getItems(table_name).values():
                mod_content.deleteFromDB()
                mod_content.insertIntoDB()
                reverted += 1

            if reverted:
                protocol.logMessage(
                    "  {}: reverted {} patches".format(module.module_id, reverted)
                )


pre = []
post = [
    UpdateTaskSettings,
    FilterConditionStructure,
    MigrateAttributes,
    EnsureDefaultUserView,
]
