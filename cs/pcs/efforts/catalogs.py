#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from enum import Enum

from cdb import auth, typeconversion
from cdb.classbody import classbody
from cdb.objects import Rule
from cdb.platform import gui, mom

from cs.pcs.checklists import Checklist, ChecklistItem
from cs.pcs.efforts import TimeSheet
from cs.pcs.issues import Issue
from cs.pcs.projects.tasks import Task  # pylint: disable=unused-import


class ObjectRules(Enum):
    ACTIVE_ISSUES = "cdbpcs: TimeSheet: Active Issues"
    ACTIVE_CHECKLISTS = "cdbpcs: TimeSheet: Active Checklists"
    ACTIVE_CHECKPOINTS = "cdbpcs: TimeSheet: Active Checkpoints"


class CatalogDescriptionData(gui.CDBCatalogContent):
    def __init__(self, catalog, cdb_project_id, task_id):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        if self.cdef:
            tabdef = self.cdef.getProjection(tabdefname, True)
        else:
            tabdef = tabdefname

        gui.CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.task_id = task_id
        self.data = None

    def _initData(self, refresh=False):
        """
        This method fills the description catalog values.
        """
        if not self.data or refresh:
            # use set to avoid duplicates
            result = set()

            qstr = (
                f"cdb_project_id='{self.cdb_project_id}' and task_id='{self.task_id}' "
            )
            timesheets = TimeSheet.KeywordQuery(
                person_id=auth.persno,
                cdb_project_id=self.cdb_project_id,
                task_id=self.task_id,
            )

            # include already existing effort descriptions for the same user
            # task and project
            for ts in timesheets:
                result.add(ts.description)

            # method to update results based on rule name and object type
            def updateResults(rule_name, obj_type, obj_id=None, qexpr=qstr):
                rule = Rule.ByKeys(name=rule_name)
                objects = rule.getObjects(obj_type, add_expr=qexpr)
                ids = []
                for obj in objects:
                    result.add(obj.GetDescription())
                    if obj_id:
                        ids.append(getattr(obj, obj_id))
                return ids

            # include active issues
            updateResults(ObjectRules.ACTIVE_ISSUES.value, Issue)

            # include active checklists
            ids = updateResults(
                ObjectRules.ACTIVE_CHECKLISTS.value, Checklist, "checklist_id"
            )

            # include active checkpoints
            if ids:
                in_stmt = ",".join(
                    [
                        f"'{obj_id}'" if isinstance(obj_id, str) else str(obj_id)
                        for obj_id in ids
                    ]
                )
                qstr = f"cdb_project_id='{self.cdb_project_id}' and checklist_id in ({in_stmt}) "
                updateResults(
                    ObjectRules.ACTIVE_CHECKPOINTS.value, ChecklistItem, qexpr=qstr
                )

            result = list(result)
            result.sort(key=lambda s: s.lower())

            self.data = [{"description": r} for r in result]

    def onSearchChanged(self):
        self._initData(True)

    def refresh(self):
        self._initData(True)

    def getRowObject(self, row):
        if not self.cdef:
            return gui.CDBCatalogContent.getRowObject(self, row)
        else:
            self._initData()
            keys = mom.SimpleArgumentList()
            for keyname in ["description"]:
                keys.append(mom.SimpleArgument(keyname, self.data[row][keyname]))
            return mom.CDBObjectHandle(self.cdef, keys, False, True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def _get_value(self, rec, attr):
        """
        Retrieves the value of `attr` from the record `rec`-
        """
        result = ""
        result = rec[attr]
        return typeconversion.to_untyped_c_api(result)

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()
        for col in tdef.getColumns():
            attr = col.getAttribute()
            value = ""
            try:
                obj = self.data[row]
                value = self._get_value(obj, attr)
                if not value:
                    value = ""
            except KeyError:
                value = ""
            result.append(value)
        return result


class CatalogDescription(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        cdb_project_id = ""
        task_id = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
            task_id = self.getInvokingDlgValue("task_id")
        except KeyError:
            pass
        self.setResultData(CatalogDescriptionData(self, cdb_project_id, task_id))


@classbody
class Task:
    def on_query_catalog_pre_mask(cls, ctx):
        if ctx.catalog_name == "cdbpcs_tasks_for_efforts":
            ctx.set_fields_readonly(["cdb_project_id", "project_name"])
