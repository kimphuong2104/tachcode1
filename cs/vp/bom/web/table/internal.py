# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Internal app for the table
"""
from cdbwrapc import CDBClassDef, RestTabularData

from cdb import fls
from cdb import sqlapi
from cs.platform.web import JsonAPI
from cs.platform.web import root
from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.classdef.main import get_classdef
from cs.platform.web.rest.support import get_restlink_by_keys
from cs.platform.web.uisupport.resttable import RestTableWrapper
from morepath import Request

from cs.vp import bom
from cs.vp.bom.web.bommanager import XBOM_FEATURE
from cs.vp.bom.web.table import OPERATION_MANAGER
from cs.vp.bom.enhancement.register import BomTableScope
from cs.vp.bom.enhancement import FlatBomRestEnhancement


class TableInternal(JsonAPI):
    pass


@root.Internal.mount(app=TableInternal, path="bomtable")
def _mount_internal():
    return TableInternal()


@TableInternal.path(path="setupdata")
class SetupData(object):
    @staticmethod
    def get_classnames(classname):
        classdef = CDBClassDef(classname)
        result = [classname]
        result.extend(classdef.getSubClassNames(True))
        return result

    @staticmethod
    def get_graphview_operations():
        stmt = """select distinct cdb_op_names.name, cdb_op_names.kind from cdb_operations
                        join cdb_op_names on cdb_operations.name = cdb_op_names.name
                        where classname in ('%s')""" % (
            "','".join(SetupData.get_classnames("part"))
        )

        ops = sqlapi.RecordSet2(sql=stmt)

        operations = []
        for operation in ops:
            if operation.kind == "GraphView":
                operations.append(operation.name)

        return operations

    @staticmethod
    def get_bom_types():
        kwargs = dict(is_enabled=1)
        if not fls.is_available(XBOM_FEATURE):
            # when the XBOM feature is not available, only return the eBOM and mBOM BOM Type
            kwargs["code"] = ["mBOM", "eBOM"]
        return bom.BomType.KeywordQuery(**kwargs)

    @staticmethod
    def get_bom_item_type_url(request):
        cdef = CDBClassDef(bom.AssemblyComponent.__classname__)
        return request.link(cdef, app=get_classdef(request))

    @staticmethod
    def get_classnames(classname):
        classdef = CDBClassDef(classname)
        result = [classname]
        result.extend(classdef.getSubClassNames(True))
        return result

    @classmethod
    def get_all_class_type_urls(cls, base_classes, request):
        all_class_names = []
        for base_class in base_classes:
            all_class_names.extend(cls.get_classnames(base_class))

        result = []
        for name in all_class_names:
            classdef = CDBClassDef(name)
            result.append(request.link(classdef, app=get_classdef(request)))
        return result


@TableInternal.json(model=SetupData)
def setup_data(model, request):
    return {
        "class_type_urls": model.get_all_class_type_urls(["part", "bom_item"], request),
        "sub_classes": {
            "part": model.get_classnames("part"),
            "bom_item": model.get_classnames("bom_item"),
        },
        "bomtypes": [
            request.view(t, app=get_collection_app(request))
            for t in model.get_bom_types()
        ],
        "bomitemtypeurl": model.get_bom_item_type_url(request),
        "graphview_operations": model.get_graphview_operations(),
    }


@TableInternal.path(path="bom_enhancement_default_data")
class BomEnhancementDefaultDataModel(object):
    @staticmethod
    def get_bom_enhancement_default_data(request: Request):
        bom_table_url = request.json.get("bomTableUrl", None)
        instance_name = request.json.get("instanceName", None)
        root_item_cdb_object_id = request.json.get("rootItemCdbObjectId", None)
        bom_enhancement_options = request.json.get("bomEnhancementOptions", {})
        bom_enhancement = FlatBomRestEnhancement(BomTableScope.INIT)
        bom_enhancement.initialize_for_default_data(
            bom_table_url=bom_table_url,
            instance_name=instance_name,
            root_item_cdb_object_id=root_item_cdb_object_id,
            additional_data=bom_enhancement_options.get("ADDITIONAL_DATA_FOR_FETCH_DEFAULT_DATA", {}),
            request=request
        )

        return bom_enhancement.get_plugins_default_data()


@TableInternal.json(model=BomEnhancementDefaultDataModel, request_method="POST")
def bom_enhancement_default_data(model: BomEnhancementDefaultDataModel, request: Request):
    return model.get_bom_enhancement_default_data(request)


@TableInternal.path(path="last_completed_operation")
class OperationWait(object):
    pass


@TableInternal.json(model=OperationWait)
def wait_for_operation_competion(model, request):
    frontend_identifier = request.GET.get("frontendIdentifier")
    return OPERATION_MANAGER.get_last_completed_operation(frontend_identifier)


@TableInternal.path(path="bom_item_occurrences")
class TableInternalBomItemOccurrences(object):
    def get_additional_select_statement(self):
        """
        Can be used to provide additional select statements for query
        (e.g. used by cs.variants for selection conditions)

        :return: Additional select statement
        """
        return ""

    def additional_values(self, bom_item_occurrence):
        """
        Can be used to provide additional values
        (e.g. used by cs.variants for selection conditions)

        :param bom_item_occurrence: RecordSet2 of an bom item occurrence
        :return: Dict with additional values
        """
        return {}

    def filter_query_results(self, bom_item_occurrences):
        """
        Can be filter queried occurrences
        (e.g. used by cs.variants for selection conditions filter)

        :param bom_item_occurrences: List of RecordSet2 of bom item occurrences
        :return: Filtered list
        """
        return bom_item_occurrences

    def get_table_data(self, request):
        bom_item_keys = request.json.get("bom_item_keys")
        quoted_bom_item_id = sqlapi.quote(bom_item_keys.get('cdb_object_id'))

        sql_statement = """
        SELECT o.*{additional_select_statement} 
        FROM bom_item_occurrence o
        WHERE {where_condition}
        """.format(
            additional_select_statement=self.get_additional_select_statement(),
            where_condition=f"bompos_object_id='{quoted_bom_item_id}'",
        )
        bom_item_occurrences = sqlapi.RecordSet2(
            table="bom_item_occurrence", sql=sql_statement
        )

        bom_item_occurrences = self.filter_query_results(bom_item_occurrences)

        values = []
        rest_links = []
        for each in bom_item_occurrences:
            obj_dict = dict(each)
            obj_dict.update(self.additional_values(each))
            values.append(obj_dict)

            rest_links.append(
                get_restlink_by_keys(
                    "bom_item_occurrence", objargs=each, request=request
                )
            )

        table_def = CDBClassDef("bom_item_occurrence").getTabDefinition(
            "bomtable_details_bom_item_oc", False
        )
        data = RestTabularData(values, table_def)
        rest_data = RestTableWrapper(data).get_rest_data(request)

        rest_data_rows = rest_data["rows"]
        for each_index, each_row in enumerate(rest_data_rows):
            rest_link = rest_links[each_index]
            each_row["@id"] = rest_link
            each_row["persistent_id"] = rest_link

        return rest_data


@TableInternal.json(model=TableInternalBomItemOccurrences, request_method="POST")
def json_post_bom_item_occurrences(model, request):
    return model.get_table_data(request)
