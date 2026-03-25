#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Module cs.workflow.designer.catalogs
"""

import json
import logging
import re
from functools import reduce
from cdb import CADDOK
from cdb import i18n
from cdb import sig
from cdb import sqlapi
from cdb.objects.org import CommonRole
from cs.shared.elink_plugins import catalog
from cs.workflow.processes import Process
from cs.workflow.designer import wfinterface
from cs.workflow.misc import ResponsibleBrowserEntry
from cs.workflow.pyrules import RuleWrapper

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

CATALOG_CONDITION = sig.signal()
SQL_AND_PATTERN = "({}) AND ({})"


def get_roles(**varkw):
    cdb_process_id = varkw.get("cdb_process_id", "")
    roles = []
    process = Process.ByKeys(cdb_process_id)

    if process:
        roles = process.GetRoleCandidates()

    return [
        [
            role["subject_name"],
            {
                "subject_id": role["subject_id"],
                "subject_type": role["subject_type"],
            }
        ]
        for role in roles
    ]


def get_label(getter):
    """
    Because legacy eLink catalogs break when their title is empty,
    make sure we always get _any_ value.

    :param getter: Function to be called with an ISO language code.
        Must interpret an empty string as the current user's language.
        Supposed to return a non-empty string.

    :returns: The first non-empty `getter` result for languages
        `[""] + fallback languages`.
        "?" if no language yields a non-empty result.
    """
    for isolang in [""] + i18n.FallbackLanguages():
        label = getter(isolang)
        if label:
            return label
    return "?"


class CatalogWithCustomizableCondition(object):
    """
    Catalogs of this class allow for customizing the default search conditions
    which are not accessible to the user.

    Provide custom conditions by connecting to the ``cdb.sig.signal``
    ``cs.workflow.designer.catalogs.CATALOG_CONDITION``. Your functions will
    receive a single parameter containing the fully-qualified Python name of
    the calling catalog instance and is expected to return a list or set.
    Conditions are joined using OR.

    If you provide any custom conditions for a catalog, the default conditions
    will be ignored. Include the default conditions in your custom conditions
    if you want to keep them.

    Usage examples:

    .. code-block:: python

        from cdb import sig
        from cs.workflow.designer.catalogs import CATALOG_CONDITION
        from cs.workflow.designer.catalogs import FormTemplateCatalog
        from cs.workflow.designer.catalogs import OperationCatalog

        # join multiple conditions of this catalog with "AND"
        FormTemplateCatalog.__join_conditions__ = "AND"

        OPERATION_WHITELIST = ["CDB_Create", "CDB_Modify"]

        @sig.connect(CATALOG_CONDITION)
        def custom_catalog_condition(fqpyname):
            if fqpyname == "cs.workflow.designer.catalogs.RuleWrapperCatalog":
                return [
                    "cdb_module_id='my.constrs'",
                    "category='Task constraints'"
                ]

            if fqpyname == "cs.workflow.designer.catalogs.FormTemplateCatalog":
                return ["status = 20"]

            if fqpyname == "cs.workflow.designer.catalogs.OperationCatalog":
                return [
                    "name='{}'".format(opname)
                    for opname in OPERATION_WHITELIST
                ]

        @sig.connect(CATALOG_CONDITION)
        def another_condition(fqpyname):
            if fqpyname == "cs.workflow.designer.catalogs.FormTemplateCatalog":
                return ["mask_name != 'forbidden'"]

    """
    __default_conditions__ = []
    __join_conditions__ = "OR"

    def _get_catalog_rules_conditions(self):
        fqpyname = "{}.{}".format(
            self.__module__,
            self.__class__.__name__
        )
        custom_conditions = set()

        for result in sig.emit(CATALOG_CONDITION)(fqpyname):
            if isinstance(result, (list, set)):
                custom_conditions.update(result)
            else:
                logging.info(
                    "ignoring non-list/non-set "
                    "catalog search condition '%s'",
                    result
                )

        return custom_conditions or self.__default_conditions__

    def get_filter_condition(self):
        conditions = self._get_catalog_rules_conditions()

        if conditions:
            return reduce(
                lambda x, y: "({}) {} ({})".format(
                    x,
                    self.__join_conditions__,
                    y,
                ),
                conditions
            )

        return "1=1"


class ResponsiblePerson(object):
    """
    Person data for responsible catalog
    """
    def __getitem__(self, name):
        try:
            return self.__dict__.__getitem__(name)
        except KeyError:
            return ""

    def match(self, condition):
        for key, value in condition.items():
            if self[key].lower().find(value.lower()) < 0:
                return False
        return True


class ResponsibleCatalog(catalog.ElinkResponsibleCatalog):
    __catalog_name__ = "cdbwf_resp_browser"

    def get_table_def(self, **varkw):
        from cdb.platform.gui import Table
        table = Table.KeywordQuery(name=self.__catalog_name__).pop()
        table_def = {
            "searchable": True,
            "columns": [],
        }

        for col in table.Attributes.KeywordQuery(itemtype="Value"):
            visible = col.visible_len > 0 and col.anzeigen == 1
            table_def["columns"].append({
                "label": col.Label[""],
                "attribute": col.attribut,
                "type": catalog.CatalogTools.get_field_type(sqlapi.SQL_CHAR),
                "visible": visible,
                "searchable": visible,
            })

        # Fix filter problem with invisible columns(show them at the end)
        table_def["columns"].sort(key=lambda x: not x["visible"])
        return table_def

    def get_catalog_title(self, **varkw):
        from cdb.platform.gui import Browser
        browser_label = Browser.ByKeys(self.__catalog_name__).Label
        return get_label(lambda isolang: browser_label[isolang])

    def _wrap_person(self, person):
        result = ResponsiblePerson()
        result.__dict__.update({
            "subject_id": person["personalnummer"],
            "description": person["name"],
            "subject_type": "Person",
            "subject_name": person["name"],
            "order_by": "1",
        })
        return result

    def _extract_person_from_role(self, role, search_condition):
        result = []

        for person in role.Owners:
            if person.CheckAccess("read"):
                wrapped = self._wrap_person(person)

                if wrapped.match(search_condition):
                    result.append(wrapped)

                result.sort(key=lambda x: x["description"])

        return result

    def get_data(self, **varkw):
        cdb_process_id = varkw.get("cdb_process_id", "")
        subject_id = ""
        subject_type = ""
        plugin_condition = varkw.get(
            "catalog_plugin_conditions",
            None
        )

        if plugin_condition:
            parsed = {}
            try:
                parsed = json.loads(plugin_condition)
                subject_id = parsed.get("subject_id", "")
                subject_type = parsed.get("subject_type", "")
            except Exception:
                pass

        search_cond = {}

        if "catalog_search_conditions" in varkw:
            try:
                search_cond = json.loads(
                    varkw["catalog_search_conditions"]
                )
            except ValueError as e:
                logging.error(
                    "Error by parsing catalog search conditions: %s",
                    e
                )

        result = []
        process = Process.ByKeys(cdb_process_id)

        if process:
            if subject_type == 'Common Role':
                role = CommonRole.ByKeys(role_id=subject_id)

                if role:
                    result = self._extract_person_from_role(
                        role,
                        search_cond
                    )

            elif subject_type == 'PCS Role':
                if hasattr(process, 'Project') and process.Project:
                    role = process.Project.RolesByID[subject_id]
                    if role:
                        result = self._extract_person_from_role(
                            role,
                            search_cond
                        )
            # Person or nothing (field empty)
            else:
                # search multilanguage fields not existing in the db...
                for attr, attr_name_getter in [
                        (
                            "subject_name",
                            ResponsibleBrowserEntry.SubjectNameAttr
                        ), (
                            "description",
                            ResponsibleBrowserEntry.DescriptionAttr
                        ),
                ]:
                    if attr in search_cond:
                        search_cond[attr_name_getter()] = search_cond[attr]
                        del search_cond[attr]

                varkw["catalog_search_conditions"] = json.dumps(search_cond)
                result = process.GetSubjectCandidates(
                    catalog.CatalogTools.get_search_conditions(**varkw)
                )

        return result

    def render(self, context, **varkw):
        # TODO: check access(only access for workflow designer/responsible)
        result = super(ResponsibleCatalog, self).render(context, **varkw)
        if result["datalist"] and isinstance(
                result["datalist"][0],
                ResponsiblePerson
        ):
            result["datalist"] = self._data_wrapper(
                self.__table_def__,
                result["datalist"]
            )

        return result

    def make_responsible_id(self, data):
        return re.sub(
            "[^0-9a-zA-Z]+",
            "_",
            "{}_{}".format(
                data["subject_type"],
                data["subject_id"],
            )
        )

    def _data_wrapper(self, table_def, datalist):
        new_datalist = []

        if table_def and "columns" in table_def:
            for data in datalist:
                new_data = [
                    {
                        "name": "_id",
                        "text": self.make_responsible_id(data),
                    }, {
                        "name": "_description",
                        "text": "",
                    },
                ]

                for column_def in table_def["columns"]:
                    new_data.append({
                        "name": column_def["attribute"],
                        "text": data[column_def["attribute"]],
                    })

                new_datalist.append(new_data)

        return new_datalist


class RuleWrapperCatalog(catalog.ElinkCatalogStandard,
                         CatalogWithCustomizableCondition):
    __catalog_table_name__ = "cdbwf_pyrule_browser"
    __catalog_table_class__ = "cdbwf_pyrule"
    __catalog_table_searchable__ = ["name", "description"]

    def get_data(self, **varkw):
        # TODO: check access(only access for workflow designer/responsible)
        cond = catalog.CatalogTools.get_search_conditions(**varkw)

        if "all_rules" in varkw:
            return RuleWrapper.Query(cond, access="read")

        fcondition = self.get_filter_condition()
        return RuleWrapper.Query(
            SQL_AND_PATTERN.format(cond, fcondition)
        )

    def get_table_def(self, **varkw):
        result = super(RuleWrapperCatalog, self).get_table_def(**varkw)
        result["columns"] = [
            col
            for col in result["columns"]
            if col["attribute"] != "cdb_module_id"
        ]
        return result

    def _data_wrapper(self, table_def, datalist):
        new_datalist = []

        if table_def and "columns" in table_def:
            for data in datalist:
                new_data = [
                    {
                        "name": "_id",
                        "text": data.ID(),
                    }, {
                        "name": "_description",
                        "text": "",
                    }
                ]

                for column_def in table_def["columns"]:
                    new_data.append({
                        "name": column_def["attribute"],
                        "text": data[column_def["attribute"]],
                    })

                new_datalist.append(new_data)

        return new_datalist


class ConstraintCatalog(RuleWrapperCatalog):
    __default_conditions__ = ["category = 'Task constraint'"]

    def get_data(self, **varkw):
        cond = catalog.CatalogTools.get_search_conditions(**varkw)
        cond = cond.replace(
            "name",
            "name_" + CADDOK.ISOLANG
        ).replace("description", "description_" + CADDOK.ISOLANG)
        fcondition = self.get_filter_condition()
        return RuleWrapper.Query(
            SQL_AND_PATTERN.format(cond, fcondition),
            access="read",
        )


class FilterCatalog(RuleWrapperCatalog):
    __default_conditions__ = ["category = 'Briefcase filter'"]


class ConditionCatalog(RuleWrapperCatalog):
    __default_conditions__ = ["category = 'Subworkflow condition'"]


class FormTemplateCatalog(catalog.ElinkCatalogStandard,
                          CatalogWithCustomizableCondition):
    __catalog_table_name__ = "cdbwf_form_template"
    __catalog_table_class__ = "cdbwf_form_template"
    __catalog_table_searchable__ = ["mask_name"]
    __default_conditions__ = ["status = 20"]

    def get_data(self, **varkw):
        cond = catalog.CatalogTools.get_search_conditions(**varkw)
        from cs.workflow.forms import FormTemplate
        fcondition = self.get_filter_condition()
        return FormTemplate.Query(
            SQL_AND_PATTERN.format(cond, fcondition),
            access="read",
        )

    def get_table_def(self, **varkw):
        result = super(FormTemplateCatalog, self).get_table_def(**varkw)
        result["columns"] = [
            col
            for col in result["columns"]
            if col["attribute"] != "cdb_module_id"
        ]
        return result

    def _data_wrapper(self, table_def, datalist):
        new_datalist = []
        if table_def and "columns" in table_def:
            for data in datalist:
                new_data = [
                    {
                        "name": "_id",
                        "text": data.ID(),
                    }, {
                        "name": "_description",
                        "text": "",
                    },
                ]

                for column_def in table_def["columns"]:
                    new_data.append({
                        "name": column_def["attribute"],
                        "text": data[column_def["attribute"]],
                    })

                new_datalist.append(new_data)

        return new_datalist


class OperationCatalog(catalog.ElinkCatalogStandard,
                       CatalogWithCustomizableCondition):
    __catalog_table_name__ = "cdb_op_names_tab"
    __catalog_table_class__ = "cdb_op_names"
    __catalog_table_searchable__ = ["name"]
    __default_conditions__ = [
        "cdb_module_id NOT LIKE 'cs.%%'",
        "name IN ('CDB_Create', 'CDB_Modify')",
    ]

    def get_data(self, **varkw):
        cond = catalog.CatalogTools.get_search_conditions(**varkw)
        from cdb.platform.mom.operations import Operation
        fcondition = self.get_filter_condition()
        return Operation.Query(
            SQL_AND_PATTERN.format(cond, fcondition),
            access="read",
        )

    def get_table_def(self, **varkw):
        result = super(OperationCatalog, self).get_table_def(**varkw)
        result["columns"] = [
            col
            for col in result["columns"]
            if col["attribute"] != "cdb_module_id"
        ]
        return result

    def _data_wrapper(self, table_def, datalist):
        new_datalist = []

        if table_def and "columns" in table_def:
            for data in datalist:
                new_data = [
                    {
                        "name": "_id",
                        "text": data.ID()
                    }, {
                        "name": "_description",
                        "text": "",
                    },
                ]

                for column_def in table_def["columns"]:
                    new_data.append({
                        "name": column_def["attribute"],
                        "text": data[column_def["attribute"]],
                    })

                new_datalist.append(new_data)

        return new_datalist


class ProjectCatalog(catalog.ElinkCatalogBase):
    def import_pcs(self):
        from cs.pcs import projects  # @UnresolvedImport
        return projects

    def get_table_def(self, **varkw):
        table_def = {
            "searchable": True,
            "columns": [],
        }
        if not wfinterface._is_pcs_enabled():
            return table_def

        projects = self.import_pcs()
        clsdef = projects.Project._getClassDef()

        for col in ["cdb_project_id", "project_name"]:
            table_def["columns"].append({
                "label": str(
                    clsdef.getAttributeDefinition(col).getLabel()
                ),
                "attribute": col,
                "type": catalog.CatalogTools.get_field_type(
                    sqlapi.SQL_CHAR
                ),
                "visible": True,
                "searchable": True,
            })

        return table_def

    def get_catalog_title(self, **varkw):
        if not wfinterface._is_pcs_enabled():
            return ""

        projects = self.import_pcs()
        clsdef = projects.Project._getClassDef()
        return get_label(
            lambda isolang: str(clsdef.getDesignation(isolang))
        )

    def get_data(self, **varkw):
        cdb_process_id = varkw.get("cdb_process_id", "")
        result = []

        if not wfinterface._is_pcs_enabled():
            return result

        process = Process.ByKeys(cdb_process_id)

        if not process:
            return result

        cond = catalog.CatalogTools.get_search_conditions(**varkw)
        projects = self.import_pcs()
        if cond and hasattr(projects.Project, "ce_baseline_id"):
            cond += " and ce_baseline_id = ''"
        return projects.Project.Query(cond, access="read")


class WorkflowTemplateCatalog(catalog.ElinkCatalogStandard,
                              CatalogWithCustomizableCondition):
    __catalog_table_name__ = "cdbwf_process"
    __catalog_table_class__ = "cdbwf_process"
    __catalog_table_searchable__ = ["cdb_process_id", "title"]
    __default_conditions__ = [
        "is_template IN ('1', 1) AND status = {}".format(
            Process.COMPLETED.status
        )
    ]

    def get_data(self, **varkw):
        cond = catalog.CatalogTools.get_search_conditions(**varkw)
        fcondition = self.get_filter_condition()
        return Process.Query(
            SQL_AND_PATTERN.format(cond, fcondition)
        )

    def get_table_def(self, **varkw):
        result = super(WorkflowTemplateCatalog, self).get_table_def(**varkw)
        result["columns"] = [
            col
            for col in result["columns"]
            if col["attribute"] != "cdb_module_id"
        ]
        return result

    def _data_wrapper(self, table_def, datalist):
        new_datalist = []

        if table_def and "columns" in table_def:
            for data in datalist:
                new_data = [
                    {
                        "name": "_id",
                        "text": data.ID(),
                    }, {
                        "name": "_description",
                        "text": "",
                    },
                ]

                for column_def in table_def["columns"]:
                    new_data.append({
                        "name": column_def["attribute"],
                        "text": data[column_def["attribute"]],
                    })

                new_datalist.append(new_data)

        return new_datalist
