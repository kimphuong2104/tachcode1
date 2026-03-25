# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module implements a PythonColumnProvider to display the classification properties
in standard result lists of a classified search.
"""

import json

from cdb import sqlapi, typeconversion

from cs.classification import classes, FloatRangeObjectPropertyValue, tools, units, util
from cs.classification.classification_data import ClassificationData

from cdb.platform.gui import PythonColumnProvider


class ClassificationPropertiesProvider(PythonColumnProvider):
    """
    Universal column provider to display classification properties in standard result lists of a classified search.
    To use this provider simply add a new column to the desired table configuration and
    use the full qualified python name of this class (cs.classification.table_columns.ClassificationPropertiesProvider)
    as attribute name. As data source select `PythonCode` for this column.
    Note that the result table must contain the attribute `cdb_object_id`, which is required to load the
    classification data for each row of the result table.
    """

    @staticmethod
    def getRequiredColumns(classname, available_columns):
        return ['cdb_object_id']

    @staticmethod
    def getColumnData(classname, table_data):
        # returns an ordered list of dicts with prop_code and value
        object_ids = []
        for row_data in table_data:
            object_ids.append(row_data["cdb_object_id"])

        languages = tools.get_languages()

        # load property data for the given object ids
        result = []
        values, _ = ClassificationData._load_data(
            object_ids, [classname],
            narrowed=True,
            request=None,
            calc_checksums=False
        )
        text_prop_codes = set()
        for props in values:
            text_prop_codes = text_prop_codes.union(util.get_text_prop_codes(props))
        enum_values = util.get_enum_values_with_labels(text_prop_codes)

        for props in values:
            new_dict = {}
            util.add_enum_labels(props, enum_values)
            util.create_all_block_descriptions(props, with_object_descriptions=True)

            for k, v in props.items():
                untyped_c_api_values = []
                for val_dict in v:
                    val = ""
                    if val_dict["value"] is not None:
                        if val_dict["property_type"] == "block":
                            val = typeconversion.to_untyped_c_api(val_dict["value"]["description"])
                        elif val_dict["property_type"] == "float":
                            float_value = val_dict["value"]["float_value_normalized"]
                            if float_value is None:
                                float_value = val_dict["value"]["float_value"]
                            val = typeconversion.to_untyped_c_api(float_value)
                        elif val_dict["property_type"] == "float_range":
                            sep = ""
                            val = ""
                            for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                                float_value = val_dict["value"][range_identifier]["float_value_normalized"]
                                if float_value is None:
                                    float_value = val_dict["value"][range_identifier]["float_value"]
                                val = "{}{}{}".format(val, sep, float_value)
                                sep = " .. "
                            val = typeconversion.to_untyped_c_api(val)
                        elif val_dict["property_type"] == "multilang":
                            for lang in languages:
                                if lang in val_dict["value"]:
                                    val = typeconversion.to_untyped_c_api(val_dict["value"][lang]["text_value"])
                                    break
                        elif val_dict["property_type"] == "text":
                            prop_label = val_dict["addtl_value"].get("label", "") if "addtl_value" in val_dict else ""
                            if prop_label:
                                val = typeconversion.to_untyped_c_api(prop_label + " (" + val_dict["value"] + ")")
                            else:
                                val = typeconversion.to_untyped_c_api(val_dict["value"])
                        else:
                            val = typeconversion.to_untyped_c_api(val_dict["value"])
                    untyped_c_api_values.append(val)

                new_dict[k] = "\n".join(untyped_c_api_values)
            result.append(new_dict)
        return result

    @staticmethod
    def getColumnDefinitions(classname, query_args):
        # Returns an ordered list of dicts with the column definitions

        def add_prop(code, prop):
            prop_type = prop["type"]
            if prop_type == "objectref":
                # currently not supported for performance reasons
                return

            flags = prop["flags"]
            if flags[2] == 0:
                # is_visible flag is 0
                return

            label = prop["name"]
            if prop_type in ["float", "float_range"]:
                unit_label = prop.get("base_unit_symbol")
                if unit_label:
                    label += " (%s)" % unit_label

            is_multivalued = flags[3]
            if is_multivalued or prop_type in ["float_range", "multilang"]:
                prop_type = "text"

            if prop_type == "datetime" and prop["with_timestamp"] != 1:
                prop_type = "date"

            result.append({"column_id": code,
                           "label": label,
                           "data_type": prop_type})

        def add_prop_for_table(row):
            prop_type = classes.classname_type_map[row.cdb_classname]
            if prop_type == "objectref":
                # currently not supported for performance reasons
                return
            if row.is_visible == 0:
                return

            label = tools.get_label("name", row)
            if prop_type in ["float", "float_range"]:
                unit_label = units.UnitCache.get_unit_label(row.unit_object_id)  # the default unit
                if unit_label:
                    label += " (%s)" % unit_label

            if row.is_multivalued or prop_type == "multilang":
                prop_type = "text"

            if prop_type == "datetime" and row["with_timestamp"] != 1:
                prop_type = "date"

            result.append({"column_id": row.code,
                           "label": label,
                           "data_type": prop_type})
        result = []
        classification_web_ctrl_arg = query_args.get("cdb::argument.classification_web_ctrl")
        if classification_web_ctrl_arg:
            web_ctrl_data = json.loads(classification_web_ctrl_arg)
            assigned_classes = set(tools.get_assigned_class_codes(web_ctrl_data))
            sql_stmt = """
                select 
                    cs_classification_class.code as class_code,
                    cs_class_property.*,
                    cs_class_table_columns.pos
                from cs_class_table_columns
                join cs_classification_class
                on cs_class_table_columns.classification_class_id = cs_classification_class.cdb_object_id
                join cs_class_property
                on cs_class_table_columns.class_property_id = cs_class_property.cdb_object_id
                where {}
                order by cs_classification_class.code, cs_class_table_columns.pos
            """.format(tools.format_in_condition("cs_classification_class.code", assigned_classes))

            class_codes_with_columns = set()
            if assigned_classes:
                for row in sqlapi.RecordSet2(sql=sql_stmt):
                    class_codes_with_columns.add(row.class_code)
                    add_prop_for_table(row)

            diff_assigned_codes = assigned_classes - class_codes_with_columns
            if diff_assigned_codes:
                metadata = None
                if not class_codes_with_columns:
                    classification_web_ctrl_arg = query_args.get("cdb::argument.classification_web_ctrl")
                    if classification_web_ctrl_arg:
                        web_ctrl_data = json.loads(classification_web_ctrl_arg)
                        if "metadata" in web_ctrl_data:
                            metadata = web_ctrl_data["metadata"]
                if not metadata:
                    classification_data = ClassificationData(
                        None, class_codes=list(diff_assigned_codes), narrowed=False, request=None
                    )
                    metadata = classification_data.get_classification_metadata()
                for cls in metadata["classes_view"]:
                    cls_data = metadata["classes"][cls]
                    for pgroup in cls_data["property_groups"]:
                        for prop_data in pgroup["properties"]:
                            prop_code = prop_data["prop_code"]
                            prop_cls_code = prop_data["class_code"]
                            # prop may belong to a base class
                            prop_cls_data = cls_data if prop_cls_code == cls else metadata["classes"][prop_cls_code]
                            add_prop(prop_code, prop_cls_data["properties"][prop_code])

        return result
