#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Powerscript catalog "cdbwf_action_resp_brows"
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import itertools
from collections import abc

from cdb import sqlapi
from cdb.objects import Object
from cdb.objects.org import CommonRole, Person
from cdb.platform.gui import CDBCatalog, CDBCatalogContent
from cdb.platform.mom import CDBObjectHandle, SimpleArgument, SimpleArgumentList
from cdb.typeconversion import to_untyped_c_api

from cs.actions import misc

RESPONSIBLE_TYPES = [
    ("Person", Person, "personalnummer"),
    ("Common Role", CommonRole, "role_id"),
]


def partition(values, chunksize):
    values = list(values) if isinstance(values, abc.KeysView) else values
    if not (isinstance(chunksize, int) and chunksize > 1):
        raise ValueError("chunksize must be a positive integer")

    for index in range(0, len(values), chunksize):
        yield values[index : index + chunksize]


def format_in_condition(col_name, values, max_inlist_value=1000):
    """
    Copied from cs.pcs.projects.common module.

    :param col_name: Name of the column to generate an "in" clause for
    :type col_name: string

    :param values: Values to use in "in" clause
    :type values: list - will break if a set is used

    :returns: "or"-joined SQL "in" clauses including ``values`` in batches of
        up to 1000 each to respect DBMS-specific limits (ORA: 1K, MS SQL 10K).
        NOTE: If values is empty "1=0" is returned, so no value should be
              returned for the SQL statement.
    :rtype: string
    """

    def _convert(values):
        return f"{col_name} IN ({','.join([sqlapi.make_literals(v) for v in values])})"

    if len(values) == 0:
        return "1=0"

    conditions = [_convert(chunk) for chunk in partition(values, max_inlist_value)]
    return " OR ".join(conditions)


class CatalogActionResponsibleData(CDBCatalogContent):
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

    def _initData(self, refresh=False):
        if not self.data or refresh:
            condition = self.getSQLCondition()
            if not self.cdb_project_id and "cdb_project_id" not in condition:
                if condition:
                    condition += " AND {} ".format("cdb_project_id = ''")
                else:
                    condition = "cdb_project_id = ''"

            self.data = sqlapi.RecordSet2(
                "cdb_action_resp_brows",
                "{}".format(condition),
                addtl=" ORDER BY order_by",
            )
            # WARNING: if order_by values do not map 1:1 to subject_type values
            #  itertools.groupby might produce wrong results
            all_entries = list(self.data)
            grouped_entries = {}
            for key, group in itertools.groupby(all_entries, lambda x: x.subject_type):
                grouped_entries[key] = list(group)
            readable_entries = self.getReadableEntries(grouped_entries)
            result = []
            for e in all_entries:
                if (e.subject_id, e.subject_type) in readable_entries and e[
                    "subject_id"
                ]:  # E036872
                    result.append(e)
            self.data = result

    def getReadableEntries(self, entries):
        responsible_types = list(RESPONSIBLE_TYPES)
        if misc.is_installed("cs.pcs.projects"):
            from cs.pcs.projects import Role

            responsible_types.append(("PCS Role", Role, "role_id"))
        result = []
        for subject_type, subject_cls, id_attr in responsible_types:
            if subject_type in entries:
                ids_list = []
                for obj in entries[subject_type]:
                    ids_list.append(str(obj.subject_id))
                readable_entries = subject_cls.Query(
                    format_in_condition(id_attr, ids_list), access="read"
                )
                result += [(o[id_attr], subject_type) for o in readable_entries]
        return result

    def onSearchChanged(self):
        args = self.getSearchArgs()
        self.cdb_project_id = None
        for arg in args:
            if arg.name == "cdb_project_id":
                self.cdb_project_id = arg.value
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
        result = ""

        if self.cdef:
            adef = self.cdef.getAttributeDefinition(attr)

            for db_name in adef.getSQLSelectNames():
                result = rec[db_name]

                if result:
                    break
        else:
            result = rec[attr]

        return to_untyped_c_api(result)

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

            except Exception:  # pylint: disable=broad-except; usage like recommend by platform
                value = ""

            result.append(value)

        return result


class CatalogActionResponsible(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
        except Exception:  # pylint: disable=broad-except; usage like recommend by platform
            cdb_project_id = ""

        self.setResultData(CatalogActionResponsibleData(cdb_project_id, self))


class ResponsibleCatalog(Object):
    __maps_to__ = "cdb_action_resp_brows"
    __classname__ = "cdb_action_resp_brows"

    def on_query_catalog_pre_mask(cls, ctx):
        if ctx.catalog_name == "cdb_action_resp_brows":
            ctx.set_fields_writeable(["cdb_project_id"])
