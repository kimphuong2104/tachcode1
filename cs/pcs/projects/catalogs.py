#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Powerscript catalog "cdbpcs_resp_brows"
"""

import itertools

from cdb import sqlapi
from cdb.objects import Object
from cdb.objects.org import CommonRole, Person
from cdb.platform.gui import CDBCatalog, CDBCatalogContent
from cdb.platform.mom import CDBObjectHandle, SimpleArgument, SimpleArgumentList
from cdb.typeconversion import to_untyped_c_api

from cs.pcs.projects import Role
from cs.pcs.projects.common import format_in_condition
from cs.pcs.helpers import get_dbms_split_count


class CatalogProjectRoles(Object):
    __maps_to__ = "cdbpcs_role_def"
    __classname__ = "cdbpcs_role_def"


RESP_TYPES = [
    (Person.__subject_type__, Person, "personalnummer"),
    (CommonRole.__subject_type__, CommonRole, "role_id"),
    (Role.__subject_type__, Role, "role_id"),
]
RESP_TYPES_NO_PID = [
    RESP_TYPES[0],
    RESP_TYPES[1],
    # searching without a project ID means
    # we have to check access on project role definitions instead
    (Role.__subject_type__, CatalogProjectRoles, "name"),
]


class CatalogResponsibleData(CDBCatalogContent):
    def __init__(self, cdb_project_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()

        if self.cdef:
            tabdef = self.cdef.getProjection(tabdefname, True)
        else:
            tabdef = tabdefname

        CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.data = None

    def getSQLCondition(self):
        condition = super().getSQLCondition() or "1=1"
        if self.cdb_project_id:
            return condition
        return f"{condition} AND cdb_project_id = ''"

    def _initData(self, refresh=False):
        if not self.data or refresh:
            condition = self.getSQLCondition()
            data = sqlapi.RecordSet2(
                "cdbpcs_resp_brows",
                condition,
                addtl="ORDER BY subject_type DESC, subject_id",
            )
            all_entries = list(data)
            grouped_entries = {}

            for subject_type, group in itertools.groupby(
                all_entries, lambda x: x.subject_type
            ):
                grouped_entries[subject_type] = list(group)

            readable_entries = self.getReadableEntries(grouped_entries)
            result = []
            already_seen = set()
            for entry in all_entries:
                subject = (entry["subject_id"], entry["subject_type"])
                if (
                    subject in readable_entries
                    and entry["subject_id"]  # E036872
                    and subject not in already_seen
                ):
                    result.append(entry)
                    already_seen.add(subject)
            self.data = result

    def getReadableEntries(self, entries):
        result = set()
        resp_types = RESP_TYPES if self.cdb_project_id else RESP_TYPES_NO_PID
        for subject_type, subject_cls, id_attr in resp_types:
            if subject_type in entries:
                ids = {str(obj.subject_id) for obj in entries[subject_type]}
                condition = format_in_condition(
                    id_attr, list(ids), get_dbms_split_count()
                )
                if subject_cls == Role:
                    condition += f" AND cdb_project_id = '{self.cdb_project_id}'"

                readable_entries = sqlapi.RecordSet2(
                    subject_cls.__maps_to__,
                    condition,
                    access="read",
                )
                result.update([(o[id_attr], subject_type) for o in readable_entries])
        return result

    def onSearchChanged(self):
        self._initData(True)

    def refresh(self):
        self._initData(True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def getRowObject(self, row):
        if not self.cdef:
            return CDBCatalogContent.getRowObject(self, row)

        else:
            self._initData()
            keys = SimpleArgumentList()

            for keyname in self.cdef.getKeyNames():
                keys.append(SimpleArgument(keyname, self.data[row][keyname]))

            return CDBObjectHandle(self.cdef, keys, False, True)

    def _get_value(self, rec, attr):
        "Retrieves the value of `attr` from the record `rec`"
        if self.cdef:
            adef = self.cdef.getAttributeDefinition(attr)

            for db_name in adef.getSQLSelectNames():
                result = rec[db_name]
                if result:
                    return to_untyped_c_api(result)

        return to_untyped_c_api(rec[attr])

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()

        for col in tdef.getColumns():
            attr = col.getAttribute()

            try:
                obj = self.data[row]
                result.append(self._get_value(obj, attr) or "")
            except Exception:
                result.append("")

        return result


class CatalogResponsible(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        cdb_project_id = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
        except KeyError:
            pass

        self.setResultData(CatalogResponsibleData(cdb_project_id, self))


class CatalogProjectProposals(Object):
    __maps_to__ = "pcs_project_proposals"
    __classname__ = "pcs_project_proposals"


class CatalogProjectTaskProposals(Object):
    __maps_to__ = "pcs_task_proposals"
    __classname__ = "pcs_task_proposals"


class CatalogProjectTemplateProposals(Object):
    __maps_to__ = "pcs_project_template_proposals"
    __classname__ = "pcs_project_template_proposals"
