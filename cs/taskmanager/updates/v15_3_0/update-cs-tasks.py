# coding: utf-8
"""
Optional update script for cs.taskmanager 15.3.0
================================================================================

Only runnable if the legacy configuration tables (cdbtodo...) exist in your
database. Make sure to fully read and understand this documentation before
running the script.

The script is only runnable from a command line:
``powerscript update-cs-tasks.py``

It will only run if

- all legacy tables (cdbtodo...) exist in the database and
- the user confirms a warning

After running the script, check the comparch logs (
:menuselection:`Administration/Configuration --> Administration --> `
:menuselection:`Packages & Modules --> Protocols`.) for potential errors and
warnings. See below for common mitigation strategies.


Migration
--------------------------------------------------------------------------------

Objects will be migrated in this order:

#. Task classes
#. Attribute mappings
#. Column definitions

All changes are applied inside a single transaction, and will be rolled back if
an exception is raised.

Cleanup after migration:

#. Drop legacy tables, so cdb_object_ids are unique again
#. Delete legacy settings (elink.apps.taskmanager*)
#. Repair cdb_object_ids
#. Rebuild cs_tasks_headers_v


Warnings
--------------------------------------------------------------------------------

Ignoring warnings is not recommended, though should result in a usable
application.


expected propname: ...
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Issued when an attribute mapping for a well-known column has an unexpected
propname. The propname may very well be correct, even if this warning is
issued.

**Mitigation**: Verify the mapping is correct.


label ... does not exist
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Issued when a column's name value does not correspond to a label ID (
ausgaben.ausgabe_label), which is used for translating the column's name.

**Mitigation**: Create a new label or change the name to an existing label's
ID.


column ...: name is empty
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Issued when a column's name is NULL or an empty string. While the application
will just render these columns without a title, it is strongly recommended you
provide this valuable feedback to your users.

**Mitigation**: Enter an existing label's ID as the column's name.


... task classes defined for classname ...; make sure objects do not overlap.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Issued when multiple task classes exist for the same classname. This may be a
correct configuration. However, you should double-check the task classes'
object rules and make sure no object can be part of more than one rule at any
given time.

**Mitigation**: Either delete superfluous task classes or design object rules
to represent mutually exclusive object sets.


task class for new classname ... found; make sure to set up the class [...]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Issued for task classes referencing classnames not set up for being used in the
application out of the box.

**Mitigation**: Set up classes as described in cs.taskmanager's administrator's
manual.


Errors
--------------------------------------------------------------------------------

As errors can potentially break the application, mitigating these is mandatory.


failed to compile cs_tasks_headers_v
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The view cs_tasks_headers_v is central to cs.taskmanager as it identifies each
user's currently active tasks. Each time a task class's rule changes, the view
is recompiled. Thus, only "queryable" rules may be used. See
:ref:`object_rules` (section on "querying") for further information.

**Mitigation**: Fix your task classes's rules and call
``cs.taskmanager.TaskClass.compileToView()``.


... task classes defined for rule_id '...'
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Issued when a single object rule is used for more than one task class. There is
one case where this constellation is okay to use: If all task classes target
different classnames that are not part of the same class hierarchy. Basically,
the same restrictions as with other task classes concerning overlap apply.

**Mitigation**: Either delete all but one of the task classes or use a
different, non-overlapping rule for all but the first of theses task classes.


"""

import sys

from cdb import ddl, sqlapi, transactions
from cdb.comparch import protocol
from cdb.comparch.modules import get_default_module
from cdb.platform.gui import Label
from cdb.platform.tools import CDBObjectIDFixer
from cs.taskmanager import TaskHeaders

from .common import Migrater, formatDict


class TaskClassMigrater(Migrater):
    """
    - **name**: see transform_name
    - **fqpyname**: just gets removed
    - **activities_context**: keep existing value, default to empty string
    """

    __table_old__ = "cdbtodo_task_cls"
    __table_new__ = "cs_tasks_class"

    __defaults__ = {
        "activities_context": "",
    }
    __keep__ = ["activities_context", "cdb_module_id"]
    __transformations__ = {
        "name": "transform_name",
    }

    def transform_name(self, record):
        """
        New attribute 'name'. Migration strategy:

        #. Keep default name if entry with same cdb_object_id already exists
        #. If not, use classname if it is unique
        #. If not, use rule_id if it is unique
        #. Use cdb_object_id
        """
        # 1. keep existing name
        existing = self._get_existing_by_oid(record)
        if existing:
            return existing.name

        # 2. use classname if unique
        existing = sqlapi.RecordSet2(
            self.__table_new__, "name='{}'".format(sqlapi.quote(record["classname"]))
        )
        if not existing:
            return record["classname"]

        # 3. use rule_id if unique
        existing = sqlapi.RecordSet2(
            self.__table_new__, "name='{}'".format(sqlapi.quote(record["rule_id"]))
        )
        if not existing:
            return record["rule_id"]

        # 4. use cdb_object_id
        return record["cdb_object_id"]


class AttributeMigrater(Migrater):
    """
    Schema did not change. Simply copy entries, translating well-known column
    propnames along the way (e.g. "getCsTasks..." methods).

    Warn for another set of well-known columns if their propnames do not end
    with an expected suffix (for ex. the Project column should map to propnames
    like "Project", "Task.Project"...).
    """

    __table_old__ = "cdbtodo_task_attribute"
    __table_new__ = "cs_tasks_attribute"

    __keep__ = ["cdb_module_id"]
    __transformations__ = {
        "propname": "transform_propname",
    }

    __propmap__ = {
        "5e3e7821-3deb-11e6-a189-00aa004d0001": "getCsTasksType",
        "b3d94b70-3deb-11e6-ba66-00aa004d0001": "getCsTasksProceedData",
        "8c3b142e-3df6-11e6-8707-00aa004d0001": "getCsTasksResponsible",
        "01e638a1-3dec-11e6-b6df-00aa004d0001": "getCsTasksTags",
        "5204d021-3dde-11e6-b91d-00aa004d0001": "getCsTasksReadStatus",
        "8d2b0fe1-76d5-11e6-8171-68f7284ff046": "getCsTasksBasePriority",
    }
    __prop_warnings__ = {
        "32f4ec1e-3df6-11e6-acaa-00aa004d0001": "Project",
        "70971ede-3df6-11e6-a4b4-00aa004d0001": "Process",
    }

    def transform_propname(self, record):
        expected_prop = self.__propmap__.get(record["column_object_id"], None)
        return expected_prop if expected_prop else record["propname"]

    def _validate(self, old_record, new_record):
        expected_prop = self.__prop_warnings__.get(new_record["column_object_id"], None)
        if expected_prop and not new_record["propname"].endswith(expected_prop):
            protocol.logWarning(
                "expected propname: '{}'".format(expected_prop),
                details_longtext=formatDict(new_record),
            )


class ColumnMigrater(Migrater):
    """
    - **cdb_icon_id**: just gets removed
    - **name**: keep existing name or keep as-is. Warn if no label exists.
    - **format_object_id**: just gets removed
    - **plugin_component**: keep existing value or guess based on attr mapping
    - **tooltip**: empty string
    - **cdb_module_id**: keep new value, or default
    """

    __table_old__ = "cdbtodo_column"
    __table_new__ = "cs_tasks_column"

    __defaults__ = {
        "tooltip": "",
        "cdb_module_id": get_default_module(),
    }
    __keep__ = ["name", "cdb_module_id"]
    __transformations__ = {
        "plugin_component": "get_component",
    }

    def _validate(self, old_record, new_record):
        if new_record["name"]:
            if not Label.ByKeys(new_record["name"]):
                protocol.logWarning(
                    "label '{}' does not exist".format(new_record["name"])
                )
        else:
            protocol.logWarning(
                "column '{}': name is empty".format(new_record["cdb_object_id"])
            )


class ScriptMain(object):
    """WARNING: This script should never run in a production environment!

    Even if you receive no warnings, running this script may result in a
    broken, inconsistent, or otherwise unusable configuration and results
    MUST be thoroughly reviewed.
    """

    def __init__(self):
        self.table_names = [
            TaskClassMigrater.__table_old__,
            AttributeMigrater.__table_old__,
            ColumnMigrater.__table_old__,
        ]
        self._check()
        self._disclaimer()

    def _abort(self, msg):
        sys.stderr.write("\n{}\n".format(msg))
        sys.exit(1)

    def _check(self):
        missing = [t for t in self.table_names if not ddl.Table(t).exists()]
        if missing:
            err_msg = "missing tables {}"
            self._abort(err_msg.format(missing))

    def _disclaimer(self):
        print((self.__doc__))
        prompt = "Continue (y/n)?\n"
        answer = None

        while not answer:
            answer = input(prompt)

        if answer not in "yY":
            self._abort("user canceled")

    def _migrate(self):
        prot = protocol.ModuleProtocol.createProtocol("migration", "")
        with protocol.ProtocolContext(prot):
            with transactions.Transaction():
                for migrater in [
                    TaskClassMigrater,
                    AttributeMigrater,
                    ColumnMigrater,
                ]:
                    try:
                        migrater().migrate()
                    except Exception as e:
                        protocol.logError(
                            "{} failed".format(migrater),
                            details_longtext="{}".format(e),
                        )
                        raise

    def _cleanup(self):
        prot = protocol.ModuleProtocol.createProtocol("cleanup", "")
        with protocol.ProtocolContext(prot):
            # remove legacy tables so object IDs are unique again
            with transactions.Transaction():
                for tbl_name in self.table_names:
                    table = ddl.Table(tbl_name)
                    try:
                        table.drop()
                    except Exception as e:
                        protocol.logError(
                            "failed to drop table '{}'".format(tbl_name),
                            details_longtext="{}".format(e),
                        )
                        raise

            protocol.logMessage(
                "dropped legacy tables",
                details_longtext="dropped tables: {}\n\nmake sure to remove "
                "classes and configuration based on these "
                "tables".format(self.table_names),
            )

            for tbl in ["cdb_setting", "cdb_usr_setting", "cdb_usr_setting_long_txt"]:
                stmt = (
                    "FROM {} WHERE setting_id LIKE "
                    "'elink.apps.taskmanager%%'".format(tbl)
                )
                try:
                    sqlapi.SQLdelete(stmt)
                except:  # noqa: E722 pylint: disable=bare-except
                    protocol.logError(
                        "could not delete legacy setting",
                        details_longtext="DELETE {}".format(stmt),
                    )
            protocol.logMessage("deleted legacy settings")

            CDBObjectIDFixer(None).run()
            protocol.logMessage("repaired cdb_object_ids")

            try:
                TaskHeaders.compileToView(fail=True)
                protocol.logMessage("compiled cs_tasks_headers_v")
            except Exception as e:  # pylint: disable=broad-except
                protocol.logError(
                    "failed to compile cs_tasks_headers_v",
                    details_longtext="migration finished\n\nfix object rules "
                    "and recompile cs_tasks_headers_v\n\n"
                    "{}".format(e),
                )

    def _final_report(self):
        prot = protocol.ModuleProtocol.createProtocol("migration finished", "")
        with protocol.ProtocolContext(prot):
            multi_stmt = (
                "SELECT {col} value, COUNT(*) amount FROM {tbl} "
                "GROUP BY {col} HAVING COUNT(*) > 1"
            )
            for multiclass in sqlapi.RecordSet2(
                sql=multi_stmt.format(col="classname", tbl="cs_tasks_class")
            ):
                protocol.logWarning(
                    "{} task classes defined for classname '{}'; make sure "
                    "objects do not overlap.".format(
                        multiclass.amount, multiclass.value
                    )
                )

            for multirule in sqlapi.RecordSet2(
                sql=multi_stmt.format(col="rule_id", tbl="cs_tasks_class")
            ):
                protocol.logError(
                    "{} task classes defined for rule_id '{}'".format(
                        multirule.amount, multirule.value
                    )
                )

            known_classes = [
                "cdbwf_task_examination",
                "cdbwf_task_approval",
                "cdbwf_task_execution",
                "cdbwf_info_message",
                "cdb_action",
                "cdbpcs_checklist",
                "cdbpcs_cl_item",
                "cdbpcs_issue",
                "cdbpcs_task",
                "cdbinno_evaluation_task",
                "cdbinno_analysis",
            ]
            for newclass in sqlapi.RecordSet2(
                sql="SELECT DISTINCT classname FROM cs_tasks_class WHERE "
                "classname NOT IN ('{}')".format("', '".join(known_classes))
            ):
                protocol.logWarning(
                    "task class for new classname '{}' found; make sure to "
                    "set up the class according to the administrator's "
                    "manual".format(newclass.classname)
                )

    def run(self):
        with protocol.CDBPKG_ActionContext("update-cs-tasks.py"):
            self._migrate()
            self._cleanup()
            self._final_report()


if __name__ == "__main__":
    ScriptMain().run()
