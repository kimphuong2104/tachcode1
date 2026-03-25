# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Module util

This module contains utility functions.These functions are not part
ot the external api!
"""

import datetime
import isodate

from collections import defaultdict
from urllib.parse import unquote

from cdb import sig, i18n
from cdb import sqlapi
from cdb import typeconversion
from cdb.objects import ByID
from cdb.objects.cdb_file import CDB_File
from cs.platform.web.rest.app import get_collection_app
from cs.platform.web.rest.generic import convert
from cdb.typeconversion import to_user_repr_date_format

from cs.classification.catalog import Property
from cs.classification.classes import ClassProperty
from cs.classification.units import UnitCache


def _emit_signal(obj, *names):
    sig.emit(obj.__class__, *names)(obj)


def is_property_value_found(property_type, property_value, search_entries, compare_normalized_values=True):
    for entry in search_entries:
        if are_property_values_equal(
            property_type, property_value, entry["value"], compare_normalized_values=compare_normalized_values
        ):
            return True
    return False


def are_property_values_equal(property_type, value_1, value_2, compare_normalized_values=True):
    retVal = False
    if value_1 is None and value_2 is None:
        retVal = True
    elif (value_1 is None and value_2 is not None) or (value_2 is None and value_1 is not None):
        retVal = False
    elif property_type == "float":
        value_1_normalized = value_1.get("float_value_normalized", None)
        value_2_normalized = value_2.get("float_value_normalized", None)

        if not compare_normalized_values or value_1_normalized is None or value_2_normalized is None:
            if not isclose(value_1["float_value"], value_2["float_value"]) \
                    or value_1["unit_object_id"] != value_2["unit_object_id"]:
                retVal = False
            else:
                retVal = True
        else:
            retVal = isclose(value_1_normalized, value_2_normalized)
    elif property_type == "float_range":
        if len(value_1) != len(value_2):
            return False
        for range_identifier, value in value_1.items():
            compare_val = value_2.get(range_identifier, None)
            value_1_normalized = value.get("float_value_normalized", None)
            value_2_normalized = compare_val.get("float_value_normalized", None)
            if not compare_normalized_values or value_1_normalized is None or value_2_normalized is None:
                if not isclose(value["float_value"], compare_val["float_value"]) \
                    or value["unit_object_id"] != compare_val["unit_object_id"]:
                    return False
            else:
                if not isclose(value_1_normalized, value_2_normalized):
                    return False
        retVal = True
    elif property_type == "multilang":
        if len(value_1) != len(value_2):
            return False
        # compare only text ignore ids
        for lang_key, value in value_1.items():
            compare_val = value_2.get(lang_key, None)
            if value.get("text_value", None) != compare_val.get("text_value", None):
                return False
        retVal = True
    else:
        retVal = value_1 == value_2
    return retVal


def is_property_value_set(prop_values):
    if prop_values and 'delete_all' == prop_values[0].get('operation'):
        return True
    for prop_value in prop_values:
        prop_type = prop_value["property_type"]
        if "block" == prop_type:
            if prop_value["value"]:
                for child_prop_values in prop_value["value"]["child_props"].values():
                    if is_property_value_set(child_prop_values):
                        return True
        elif "boolean" == prop_type or "integer" == prop_type:
            return prop_value["value"] is not None
        elif "float" == prop_type:
            if prop_value["value"] and "float_value" in prop_value["value"]:
                return prop_value["value"]["float_value"] is not None
        elif "float_range" == prop_type:
            if prop_value["value"]:
                for val in prop_value["value"].values():
                    if val["float_value"] is not None:
                        return True
        elif "multilang" == prop_type:
            if prop_value["value"]:
                for multilang_val in prop_value["value"].values():
                    if multilang_val["text_value"]:
                        return True
        elif prop_value["value"]:
            return True
    return False


def merge_simple_values(exisiting_values, new_values, eav_ids_to_delete):
    def collect_eav_id_to_delete(existing_value, eav_ids_to_delete):
        if "float_range" == existing_value["property_type"] and existing_value["value"]:
            for _, val in existing_value["value"].items():
                eav_id = val.get('id')
                if eav_id:
                    eav_ids_to_delete[eav_id] = existing_value['value_path']
        elif "multilang" == existing_value["property_type"] and existing_value["value"]:
            for _, lang_value in existing_value["value"].items():
                eav_id = lang_value.get('id')
                if eav_id:
                    eav_ids_to_delete[eav_id] = existing_value['value_path']
        else:
            eav_id = existing_value.get('id')
            if eav_id:
                eav_ids_to_delete[eav_id] = existing_value['value_path']

    if new_values and 'delete_all' == new_values[0].get('operation'):
        # remove all multivalues
        for existing_value in exisiting_values:
            collect_eav_id_to_delete(existing_value, eav_ids_to_delete)
        del exisiting_values[:]
        return
    for new_value in new_values:
        property_type = new_value["property_type"]
        if "block" == property_type:
            return

        already_exists = False
        empty_value = None
        indexes_to_delete = []

        for idx, existing_value in enumerate(exisiting_values):
            if are_property_values_equal(
                    property_type, new_value["value"], existing_value["value"],
                    compare_normalized_values=False
            ):
                already_exists = True
                if 'delete' == new_value.get('operation'):
                    indexes_to_delete.append(idx)
                    collect_eav_id_to_delete(existing_value, eav_ids_to_delete)
                else:
                    break
            if not empty_value and not is_property_value_set([existing_value]):
                empty_value = existing_value

        if 'delete' == new_value.get('operation'):
            for idx in sorted(indexes_to_delete, reverse=True):
                del exisiting_values[idx]
        else:
            if already_exists:
                continue
            elif empty_value:
                replace_simple_prop_value(empty_value, new_value, eav_ids_to_delete)
            else:
                exisiting_values.append(new_value)


def replace_simple_prop_value(prop_value, new_prop_value, eav_ids_to_delete):
    prop_type = prop_value["property_type"]
    if "block" == prop_type:
        return
    elif "multilang" == prop_type and prop_value["value"]:
        if 'delete_all' == new_prop_value.get('operation'):
            for _, old_value in prop_value["value"].items():
                eav_id = old_value.get('id')
                if eav_id:
                    eav_ids_to_delete[eav_id] = prop_value['value_path']
            prop_value["value"] = {}
        elif new_prop_value["value"]:
            old_value = prop_value["value"]
            for lang, new_value in new_prop_value["value"].items():
                if new_value["text_value"]:
                    if lang in old_value:
                        old_value[lang]["text_value"] = new_value["text_value"]
                    else:
                        old_value[lang] = new_value
        else:
            # no modifications necessary
            pass
    elif "float_range" == prop_type and prop_value["value"]:
        if 'delete_all' == new_prop_value.get('operation'):
            for _, old_value in prop_value["value"].items():
                eav_id = old_value.get('id')
                if eav_id:
                    eav_ids_to_delete[eav_id] = prop_value['value_path']
            prop_value["value"] = {}
        elif new_prop_value["value"]:
            old_value = prop_value["value"]
            for range_identifier, new_value in new_prop_value["value"].items():
                if new_value["float_value"] is not None:
                    if range_identifier in old_value:
                        old_value[range_identifier]["float_value"] = new_value["float_value"]
                        old_value[range_identifier]["unit_object_id"] = new_value["unit_object_id"]
                    else:
                        old_value[range_identifier] = new_value
        else:
            # no modifications necessary
            pass
    else:
        prop_value["value"] = new_prop_value["value"]
        if 'delete_all' == new_prop_value.get('operation'):
            eav_id = prop_value.get('id')
            if eav_id:
                eav_ids_to_delete[eav_id] = prop_value['value_path']


def check_classification_object(obj):
    if not hasattr(obj, "cdb_object_id"):
        raise ValueError("Object has no cdb_object_id")
    if not isinstance(obj.cdb_object_id, str):
        raise ValueError("The cdb_object_id of the given object has to be a string")


def convert_datestr_to_datetime(value):
    if isinstance(value, datetime.datetime):
        # already datetime no need to convert
        return value
    # convert iso time strings to datetime for rest api compatibility
    if value and isinstance(value, str):
        value = value.strip()
    try:
        return isodate.parse_datetime(value)
    except (isodate.ISO8601Error, ValueError):
        # if it is not a iso time string assume it
        # is a legacy time string handled by ce orm.
        try:
            return typeconversion.from_legacy_date_format(value)
        except ValueError:
            # support american time format as well
            # MM/DD/YYYY hh:mm:ss
            for date_format in ("%m/%d/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S"):
                try:
                    return datetime.datetime.strptime(value, date_format)
                except ValueError:
                    pass
            raise


def get_epsilon(a, b=0.0, rel_tol=1e-09, abs_tol=0.0):
    return max(rel_tol * max(abs(a), abs(b)), abs_tol)


# http://stackoverflow.com/a/33024979
# https://www.python.org/dev/peps/pep-0485/#proposed-implementation
def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    if not a and not b:
        return True
    if (not a and b) or (a and not b):
        return False
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def _load_base_units(prop_codes, from_catalog):
    result = {}
    if prop_codes:
        if from_catalog:
            table = "cs_property"
            cls = Property
            rset = sqlapi.RecordSet2(
                sql="select code, unit_object_id, unit_object_id as default_unit_object_id from cs_property where %s" % Property.code.one_of(*prop_codes)
            )
        else:
            table = "cs_class_property"
            cls = ClassProperty
            rset = sqlapi.RecordSet2(
                sql="select code, unit_object_id, default_unit_object_id from cs_class_property where %s" % Property.code.one_of(*prop_codes)
            )
        result = {
            r.code: {
                "unit_object_id" : r.unit_object_id,
                "default_unit_object_id": r.default_unit_object_id,
            } for r in rset
        }
    return result


def load_base_units(prop_tuples):
    normal_props = set()
    block_detail_props = set()
    for prop_code, is_inside_block in prop_tuples:
        if is_inside_block:
            block_detail_props.add(prop_code)
        else:
            normal_props.add(prop_code)
    # Lookup class props
    base_units = _load_base_units(normal_props, False)
    # Lookup props in catalog that were not found as class prop. These are the standalone props.
    standalone_props = normal_props - set(base_units.keys())
    base_units.update(_load_base_units(standalone_props, True))
    # Lookup props in catalog that belong to block properties
    base_units.update(_load_base_units(block_detail_props, True))
    return base_units
    ret_val = {}
    for prop_code, base_unit_ids in base_units.items():
        ret_val[prop_code] = base_unit_ids["unit_object_id"]
    return ret_val


def load_base_unit_oids(prop_codes, from_catalog):
    base_units = {}
    for prop_code, base_unit_ids in _load_base_units(prop_codes, from_catalog).items():
        base_units[prop_code] = base_unit_ids["unit_object_id"]
    return base_units


def load_base_unit_symbols(prop_codes, from_catalog):
    base_units = {}
    for prop_code, base_unit_ids in _load_base_units(prop_codes, from_catalog).items():
        base_units[prop_code] = UnitCache.get_unit_label(base_unit_ids["unit_object_id"])
    return base_units


def add_file_data(request, class_infos, class_code=None):
    from cs.classification.classes import ClassificationClass

    class_id = ''
    class_codes = []
    class_ids = []

    for class_info in class_infos:
        class_codes.append(class_info["code"])
        class_ids.append(class_info["cdb_object_id"])
    if class_code:
        class_id = ClassificationClass.code_to_oid(class_code)

    file_data_by_oid = get_primary_file_data(request, class_ids)

    for class_info in class_infos:
        class_info["file"] = file_data_by_oid.get(class_info["cdb_object_id"], None)

    if class_id:
        return file_data_by_oid.get(class_id, None)
    else:
        return None


def get_primary_file_data(request, for_this_oids):

    file_objs = CDB_File.Query(
        ((CDB_File.cdbf_object_id.one_of(*for_this_oids)) & (CDB_File.cdbf_primary == 1)),
        order_by=["cdbf_object_id", "cdbf_name"]
    )
    collection_app = get_collection_app(request)
    files_by_oid = {}
    for file_obj in file_objs:
        file_data = {
            "url": unquote(request.link(file_obj, app=collection_app)),
            "alt": file_obj.cdbf_name,
            "content_type": file_obj.content_type
        }
        files_by_oid[file_obj.cdbf_object_id] = file_data
    return files_by_oid


def check_arg(ctx, key, value):
    if ctx and key in ctx.ue_args.get_attribute_names() and value == ctx.ue_args[key]:
        return True
    if ctx and key in ctx.sys_args.get_attribute_names() and value == ctx.sys_args[key]:
        return True
    return False


def check_code(code):
    import re
    result = re.match(r"^[^\d\W]\w*$", code)
    return result is not None


def create_code(name):
    import re
    code = re.sub(r"\W|^(?=\d)", "_", name)
    return code


def make_code_unique(stmt, code):
    rset = sqlapi.RecordSet2(sql=stmt)
    codes = set([r.code for r in rset])
    unique_code = code
    code_counter = 1
    while unique_code in codes:
        unique_code = code + "_" + str(code_counter)
        code_counter += 1
    return unique_code


def date_to_iso_str(value):
    if isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
        return value.isoformat()


def format_number_string(float_string, language=None, decimal_seperator=None, group_seperator=None):
    import re
    decimal_sep = decimal_seperator if decimal_seperator else i18n.get_decimal_separator(language)
    group_sep = group_seperator if group_seperator is not None else i18n.get_group_separator(language)
    if "." in float_string:
        integer, decimal = float_string.split(".")
    else:
        integer = float_string
        decimal = None
    if group_sep:
        integer = re.sub(r"\B(?=(?:\d{3})+$)", group_sep, integer)
    return integer + decimal_sep + decimal if decimal is not None else integer


def get_text_prop_codes(values):
    prop_codes = set()
    for code, property_value in values.items():
        prop_type = property_value[0]["property_type"]
        if prop_type == "block":
            prop_codes = prop_codes.union(get_text_prop_codes(property_value[0]["value"]["child_props"]))
        elif prop_type == "text":
            prop_codes.add(code)
        else:
            # nothing to do for other prop types
            pass
    return prop_codes


def add_enum_labels(values, enum_values_by_prop_code):
    from cs.classification import tools
    if not enum_values_by_prop_code:
        return
    for code, property_values in values.items():
        for property_value in property_values:
            prop_type = property_value["property_type"]
            if prop_type == "block":
                add_enum_labels(property_value["value"]["child_props"], enum_values_by_prop_code)
            elif prop_type == "text":
                for enum_value in enum_values_by_prop_code.get(code, []):
                    if property_value["value"] == enum_value.text_value:
                        property_value["addtl_value"] = {"label": tools.get_label("label", enum_value)}
                        break
            else:
                # nothing to do for other prop types
                pass


def get_enum_values_with_labels(prop_codes):
    from cs.classification import tools

    def get_columns(table):
        columns = ""
        for lang in langs:
            columns = columns + \
                ", {table}.label_{lang}".format(table=table, lang=lang)
        return columns

    def get_where_condition(table):
        op = ""
        where_condition = "("
        for lang in langs:
            where_condition = where_condition + \
                "{op} ({table}.label_{lang} IS NOT NULL AND {table}.label_{lang} != '')".format(
                    op=op, table=table, lang=lang
                )
            op = " OR "
        where_condition = where_condition + ")"
        return where_condition

    enum_values_by_prop_code = defaultdict(list)
    if not prop_codes:
        return enum_values_by_prop_code

    langs = ['cs', 'de', 'en', 'es', 'fr', 'it', 'ja', 'ko', 'pl', 'pt', 'tr', 'zh']

    # cdb_object ids of class properties with enum values are needed for an efficient query of
    # cs_class_property_values_v. selecting via code or with subselect takes ages!
    stmt = """
        SELECT min(cdb_object_id) as cdb_object_id FROM cs_class_property 
        WHERE {in_condition}
        GROUP BY code
    """.format(
        in_condition=tools.format_in_condition('code', prop_codes)
    )
    class_prop_oids = []
    for class_prop in sqlapi.RecordSet2(sql=stmt):
        class_prop_oids.append(class_prop['cdb_object_id'])

    stmt = ""
    if class_prop_oids:
        # query only if there are class properties with enum values
        stmt = """
            SELECT
                    cs_class_property_values_v.property_code,
                    cs_class_property_values_v.text_value
                    {columns_class}
                FROM cs_class_property_values_v
                WHERE {where_condition_class} AND {in_condition_class}
                UNION ALL
        """.format(
            columns_class=get_columns("cs_class_property_values_v"),
            in_condition_class=tools.format_in_condition(
                'cs_class_property_values_v.property_id', class_prop_oids
            ),
            where_condition_class=get_where_condition("cs_class_property_values_v")
        )

    # selecting values even if there is no catalog property code in prop_codes is faster as checking the
    # prop_codes against cs_property table before
    stmt = stmt + """
        SELECT
            cs_property.code as property_code,
            cs_property_value.text_value
            {columns}
        FROM cs_property_value
        JOIN cs_property ON cs_property_value.property_object_id = cs_property.cdb_object_id
        WHERE {where_condition} AND {in_condition}
    """.format(
        columns=get_columns("cs_property_value"),
        in_condition=tools.format_in_condition('cs_property.code', prop_codes),
        where_condition=get_where_condition("cs_property_value")
    )

    for enum_value in sqlapi.RecordSet2(sql=stmt):
        enum_values_by_prop_code[enum_value.property_code].append(enum_value)
    return enum_values_by_prop_code


def get_value_list(properties, path_elements):
    path_element = path_elements[0]
    if ":" in path_element:
        property_code, pos_str = path_element.split(":")
        pos = int(pos_str) - 1
    else:
        property_code = path_element
        pos = 0

    property_values = properties[property_code]
    if 1 == len(path_elements):
        return property_values
    else:
        return get_value_list(property_values[pos]["value"]["child_props"], path_elements[1:])

def create_class_description(
    class_description_pattern, object_property_values,
    languages=None, decimal_seperator=None, group_seperator=None, dateformat=None
):
    create_all_block_descriptions(object_property_values)
    description = replace_pattern(
        class_description_pattern, object_property_values,
        languages, decimal_seperator, group_seperator, dateformat
    )
    return description


def create_all_block_descriptions(object_property_values, with_object_descriptions=True):
    for property_code, property_values in object_property_values.items():
        for property_value in property_values:
            if "block" == property_value["property_type"]:
                create_block_descriptions(
                    property_code, property_value,
                    decimal_seperator=None, group_seperator=None, dateformat=None,
                    with_object_descriptions=with_object_descriptions
                )


def create_block_descriptions(
    block_property_code, block_property, decimal_seperator=None, group_seperator=None, dateformat=None,
    with_object_descriptions=True
):
    from cs.classification import get_block_prop_description_pattern

    child_properties = block_property["value"]["child_props"]
    pattern = get_block_prop_description_pattern(block_property_code)

    for property_code, property_values in child_properties.items():
        for property_value in property_values:
            if "block" == property_value["property_type"]:
                create_block_descriptions(
                    property_code, property_value, decimal_seperator, group_seperator, dateformat,
                    with_object_descriptions
                )
    if pattern:
        block_property["value"]["description"] = replace_pattern(
            pattern, child_properties, None, decimal_seperator, group_seperator, dateformat,
            with_object_descriptions
        )
    else:
        block_property["value"]["description"] = ""


def replace_pattern(
    pattern, properties, languages=None, decimal_seperator=None, group_seperator=None, dateformat=None,
    with_object_descriptions=True
):
    from cs.classification import tools

    if not pattern:
        return pattern
    if not languages:
        languages = tools.get_languages()

    value_formats = tools.parse_formats(pattern)

    prop_descriptions = defaultdict(str)
    for prop_code, prop_values in properties.items():
        seperator = ""
        substitute = ""
        for prop_value in prop_values:
            value_value = prop_value.get('value')
            if prop_value.get('property_type') == 'block':
                value_value = value_value.get('description')
            elif prop_value.get('property_type') == 'objectref' and value_value is not None and with_object_descriptions:
                addtl_value = prop_value.get("addtl_value", None)
                if addtl_value:
                    value_value = addtl_value.get("ui_text", value_value)
                else:
                    obj = ByID(value_value)
                    if obj:
                        value_value = obj.GetDescription()
            elif prop_value.get('property_type') == 'multilang' and value_value is not None:
                text_value = ""
                for lang in languages:
                    data = value_value.get(lang)
                    if data is not None:
                        text_value = data.get("text_value")
                        if text_value:
                            break
                value_value = text_value if text_value else ""
            elif prop_value.get('property_type') == 'float' and value_value is not None:
                value_format = value_formats.get(prop_code, {})
                unit = UnitCache.get_unit_label(value_value.get("unit_object_id")) if value_format.get("with_unit", False) else ""
                float_format = value_format.get("format_string", "")
                float_value = value_value.get('float_value')
                if float_value is not None:
                    if float_format:
                        try:
                            value_value = float_format % float_value
                        except:
                            value_value = str(float_value)
                    else:
                        value_value = str(float_value)
                    value_value = format_number_string(
                        value_value, languages[0], decimal_seperator, group_seperator
                    )
                    value_value += unit
                else:
                    value_value = ""
            elif prop_value.get('property_type') == 'float_range' and value_value is not None:
                value_format = value_formats.get(prop_code, {})
                if value_format.get("with_unit", False):
                    unit_labels = {
                        "min": UnitCache.get_unit_label(value_value["min"].get("unit_object_id")),
                        "max": UnitCache.get_unit_label(value_value["max"].get("unit_object_id"))
                    }
                else:
                    unit_labels = {
                        "min": "",
                        "max": ""
                    }
                float_format = value_format.get("format_string", "")
                formatted_value = ""
                value_sep = ""
                for identifier in ["min", "max"]:
                    float_value = value_value[identifier].get('float_value')
                    if float_value is not None:
                        if float_format:
                            try:
                                formatted_float_value = float_format % float_value
                            except:
                                formatted_float_value = str(float_value)
                        else:
                            formatted_float_value = str(float_value)
                        formatted_float_value = format_number_string(
                            formatted_float_value, languages[0], decimal_seperator, group_seperator
                        )
                        formatted_float_value += unit_labels[identifier]
                        formatted_value = formatted_value + value_sep + formatted_float_value
                        value_sep = " .. "
                value_value = formatted_value
            elif prop_value.get("property_type") == "integer" and value_value is not None:
                int_format = value_formats.get(prop_code, {}).get("format_string", "")
                if int_format:
                    try:
                        value_value = int_format % value_value
                    except:
                        value_value = str(value_value)
                else:
                    value_value = str(value_value)
                value_value = format_number_string(
                    value_value, languages[0], decimal_seperator, group_seperator
                )
            elif prop_value.get('property_type') == 'datetime' and value_value is not None:
                value_value = to_user_repr_date_format(value_value, format=dateformat)
            elif prop_value.get('property_type') == 'text':
                text_value = prop_value.get('value')
                if not text_value:
                    text_value = ""
                addtl_value = prop_value.get("addtl_value")
                prop_label = ""
                if addtl_value:
                    prop_label = addtl_value.get("label")

                if prop_label:
                    value_value = prop_label + " (" + text_value + ")"
                else:
                    value_value = text_value

            if value_value:
                substitute = "{}{}{}".format(substitute, seperator, value_value)
                seperator = ", "  # separate multi values by comma
        prop_descriptions[prop_code] = "{}".format(substitute)
    # Note: new properties may be missing in child_descriptions for older classification data.
    # For this reason child_descriptions is a defaultdict, which returns an empty string
    # as replacement in this case.
    return tools.parse_raw(pattern) % prop_descriptions

