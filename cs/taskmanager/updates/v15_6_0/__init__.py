#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pathlib
from tempfile import gettempdir

from cdb import ddl, i18n, imex, sqlapi, transactions
from cdb.comparch import protocol
from cdb.platform.gui import Label
from cdb.platform.mom.entities import Class
from cdb.platform.mom.fields import DDMultiLangField
from cs.taskmanager.updates.v15_4_1_1 import revert_deleted_patch
from cs.taskmanager.user_views import (
    CATEG_EDITED,
    CATEG_PRECONFIGURED,
    CATEG_USER,
    UserView,
)

# modify this before running to prioritize languages
SORTED_ISOCODES = ["en", "de"]


class EnsureTasksAdmin(object):
    def run(self):
        for subject_id in ["Administrator", "Administrator: Master Data"]:
            revert_deleted_patch(
                "cs.taskmanager",
                "cdb_global_subj",
                role_id="Administrator: My Tasks",
                subject_id=subject_id,
                subject_type="Common Role",
                exception_id="",
            )


class FlagDefaultUserViews(object):
    def run(self):
        sqlapi.SQLupdate(
            "cs_tasks_user_view "
            "SET category = 'preconfigured', is_default = 1 "
            "WHERE category = 'default'"
        )


class InitUserViewNamesAndPosition(object):
    def run(self):
        if not self._has_label_field():
            protocol.logWarning("Update not relevant.")
            return

        lang_fields = self._get_lang_fields()

        with transactions.Transaction():
            self.migrate_preconfigured(lang_fields)
            self.migrate_personal(lang_fields)
            self.initialize_position(lang_fields)

    def _has_label_field(self):
        table = ddl.Table("cs_tasks_user_view")
        field_names = [getattr(x, "colname", "?") for x in table.reflect()]
        return "label" in field_names

    def _get_lang_fields(self):
        name_field = DDMultiLangField.ByKeys("cs_tasks_user_view", "name")
        return {x.cdb_iso_language_code: x.field_name for x in name_field.LangFields}

    def migrate_preconfigured(self, lang_fields):
        # pylint: disable=protected-access
        lang_codes = {
            iso: cdb_lang for cdb_lang, iso in i18n._CDBLang2ISOLangDict.items()
        }
        language_mapping = {
            # iso: (user view field name, label field name)
            iso: (lang_fields[iso], lang_codes[iso])
            for iso in lang_fields
        }

        categ_condition = "category IN ('{}')".format(
            "', '".join(["default", CATEG_PRECONFIGURED])
        )
        views = sqlapi.RecordSet2(
            "cs_tasks_user_view",
            "label > '' AND (name_en IS NULL OR name_en = '') AND {}".format(
                categ_condition
            ),
        )
        labels = {
            label.ausgabe_label: label
            for label in Label.Query(
                "ausgabe_label IN (SELECT label FROM cs_tasks_user_view)"
            )
        }

        for view in views:
            label = labels.get(view.label, None)
            if label:
                updates = {
                    view_field: label[label_field]
                    for (view_field, label_field) in language_mapping.values()
                }
                view.update(**updates)
            else:
                protocol.logWarning(
                    "missing label '{0.label}' "
                    "referenced by user view '{0.cdb_object_id}'".format(view)
                )

    def migrate_personal(self, lang_fields):
        categ_condition = "category IN ('{}')".format(
            "', '".join([CATEG_USER, CATEG_EDITED])
        )
        views = sqlapi.RecordSet2("cs_tasks_user_view", categ_condition)

        for view in views:
            updates = {
                lang_fields[iso]: view.name
                for iso in lang_fields
                if not view[lang_fields[iso]]
            }
            if updates:
                view.update(**updates)

    def initialize_position(self, lang_fields):
        sorted_views = UserView.Query(
            addtl="ORDER BY {}".format(
                ", ".join(lang_fields[iso] for iso in SORTED_ISOCODES)
            )
        )

        with transactions.Transaction():
            for index, view in enumerate(sorted_views):
                view.Update(view_position=10 * (index + 1))


class RemoveOldFields(object):
    __expfile__ = "upd-v15.6.0-user_view.exp"
    __fields__ = (("cs_tasks_user_view", ("label", "name")),)

    def run(self):
        tables = [field[0] for field in self.__fields__]
        exportFile = str(pathlib.Path(gettempdir(), self.__expfile__))
        exported = False

        try:
            imex.export(
                ignore_errors=False,
                control_file=None,
                control_lines=["* FROM {}".format(table) for table in tables],
                output_file=exportFile,
            )
            protocol.logWarning(
                "Exported tables {} into file '{}'".format(tables, exportFile)
            )
            exported = True
        except Exception as e:
            protocol.logError("Error occured during export:\n{}".format(e.message))
            raise

        if exported:
            for table_name, fields in self.__fields__:
                table = ddl.Table(table_name)
                for field in fields:
                    if table.hasColumn(field):
                        table.dropAttributes(field)
                        protocol.logMessage(
                            "column '{}' dropped from table '{}'".format(
                                field, table_name
                            )
                        )

        dd_classes = Class.KeywordQuery(relation=tables)
        missing_classes = set(tables).difference(dd_classes.relation)

        if missing_classes:
            protocol.logError(
                "cannot find DD classes for tables '{}'".format(missing_classes)
            )

        for dd_class in dd_classes:
            dd_class.compile(force=True)


pre = []
post = [
    EnsureTasksAdmin,
    FlagDefaultUserViews,
    InitUserViewNamesAndPosition,
    RemoveOldFields,
]


if __name__ == "__main__":
    for updater in post:
        updater().run()
