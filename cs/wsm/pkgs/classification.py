# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module classfication

Support functions for classification
"""

from __future__ import absolute_import

import collections
import copy
import logging

from cdb import util
from cs.vp.items import Item
from cs.documents import Document

import six


_available = True
try:
    from cs.classification.classes import ModelAssignment
    from cs.classification import api as cl_api
    from cs.classification.rest.utils import convert_from_json
    from cs.classification.util import are_property_values_equal
    from cs.classification.units import Unit
except ImportError:
    _available = False

__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []


def ucAvailable():
    return _available


def getUnitMapping():
    if _available:
        return {unit.symbol: unit.cdb_object_id for unit in Unit.Query()}
    else:
        return {}


def add_additonal_property_infos(uc_class, class_data):
    """
    adds adtional property information to class_data
    """
    additonal_infos = {}
    for prop in uc_class.OwnProperties:
        prop_dict = {}
        for name_prop in list(prop):
            if name_prop.startswith("name_"):
                prop_dict[name_prop] = prop[name_prop]
        additonal_infos[prop.code] = prop_dict
    class_data["_prop_names_"] = additonal_infos


def _handle_float_units(value_list):
    """
    Replaces unit_symbols by unit_object_id
    """
    for float_value in value_list:
        float_data = float_value["value"]
        unit_name = float_data.get("unit_symbol")
        unit_id = float_data.get("unit_object_id")
        if unit_id is None and unit_name is not None:
            unit = Unit.ByKeys(symbol=unit_name)
            if unit is not None:
                float_data["unit_object_id"] = unit.cdb_object_id
            else:
                logging.error("Unit :%s not found", unit_name)


def _handle_text_records(new_record, cad_record):
    """
    merge text into existing record
    new_record is copy of existing record
    cad_record are values from designpush
    """
    if not new_record["value"]:
        new_record["value"] = dict()
    for iso_lang_key, text in six.iteritems(cad_record["value"]):
        language_record = new_record["value"].get(iso_lang_key)
        if language_record is None:
            language_record = dict()
            new_record["value"][iso_lang_key] = language_record
        l_code = text["iso_language_code"]
        language_record["iso_language_code"] = l_code
        t_val = text["text_value"]
        language_record["text_value"] = t_val


def _merge_property(property_name, existing_prop_records, cad_values):
    """
    :returns: Bool, list of values
    """
    ret_values = []  # list of new records (merged)
    changed = False
    existing_len = 0
    # p_record = prototype record
    if existing_prop_records is not None:
        existing_len = len(existing_prop_records)
        p_record = copy.deepcopy(existing_prop_records[0])
        del p_record["id"]
    else:
        # if we have a new item in additional properties, ask api
        a_prop = cl_api.create_additional_props([property_name])
        p_record = a_prop["properties"][property_name][0]

    new_property_type = p_record["property_type"]
    is_float = p_record["property_type"] == u"float"
    # if a list len differs we are unequal
    new_len = len(cad_values)
    changed |= existing_len != new_len
    # perhaps we must change the unit to the object_id
    if is_float:
        _handle_float_units(cad_values)
    # iterate over list of values
    for i in six.moves.range(new_len):
        lv = cad_values[i]
        if i < existing_len:
            new_record = copy.deepcopy(existing_prop_records[i])
            if "property_type" not in lv:
                lv["property_type"] = new_record["property_type"]
                convert_from_json(lv)
            new_val = new_record["value"]
            changed |= not are_property_values_equal(
                new_property_type, lv["value"], new_val
            )
        else:
            changed = True
            new_record = copy.deepcopy(p_record)
        if new_property_type == "multilang":
            _handle_text_records(new_record, lv)
        elif new_property_type == "block":
            raise ValueError(
                "Classification: Block Properties"
                "are not supported (%s)" % property_name
            )
        else:
            new_record["value"] = lv["value"]
        logging.debug("classication: CAD value: %s", new_record)
        if "id" not in new_record:
            new_record["id"] = None
        ret_values.append(new_record)
    return changed, ret_values


def merge_classication(class_to_merge, classification_data, item, update_index=True):
    """
    :param class_to_merge: str: Classcode
    :param classification_data: Classfication_data structure
    :param item: cs.vp.Item with classification info
    :param update_index: forwarded to update_classification

    Merges class class_to_merge from given classification_data for item
    with existing classification of item.
    Stores the classification data into item
    """
    class_info = None
    changed = False
    cad_properties = classification_data.get("properties")
    existing_data = cl_api.get_classification(item, with_metadata=True)
    if class_to_merge not in existing_data["assigned_classes"]:
        c_data = cl_api.rebuild_classification(existing_data, [class_to_merge])
        class_info = c_data["new_classes_metadata"].get(class_to_merge)
        current_props = c_data.get("properties")
        existing_data = c_data
        changed = True
    else:
        current_props = existing_data.get("properties")
        class_info = existing_data["metadata"]["classes"].get(class_to_merge)

    if current_props is not None and cad_properties is not None and class_info:
        # merge properties
        changed_props = collections.defaultdict(list)
        for prop_key in list(class_info["properties"]):
            prop_value = current_props.get(prop_key)
            new_value = cad_properties.get(prop_key)
            if new_value is not None:
                prop_changed, merged_values = _merge_property(
                    prop_key, prop_value, new_value
                )
                if prop_changed:
                    changed_props[prop_key].extend(merged_values)
                    changed = True
        current_props.update(changed_props)
    if changed:
        cl_api.update_classification(item, existing_data, update_index=update_index)
    return changed


def class_for_generic(doc, cad_view=None):
    """
    find unique class for given generic

    :returns classname for given document
    """
    query = {"z_nummer": doc.z_nummer, "z_index": doc.z_index}
    if cad_view:
        query["cad_view"] = cad_view
    views = ModelAssignment.KeywordQuery(**query)
    uc_class = None
    if len(views) == 1:
        uc_class = views[0].Class
    else:
        logging.info(
            "class_for_genric: no unique class found for: %s, cnt: %s",
            query,
            len(views),
        )
    return uc_class


def create_empty_classification_from_generic(generic_doc, view_name, item):
    """
    :param generic_doc: Document
    :param view_name: restrict search to view_name
    :param item: None or cs.vp.Item. If given check for valid uc class for item
    :returns UCClass, empty-classification structure for UC_Class
    """
    empty_classification = None
    uc_class = class_for_generic(generic_doc, view_name)
    if uc_class is not None:
        empty_classification = create_empty_classification(uc_class.code, item)
        add_additonal_property_infos(uc_class, empty_classification)
    return uc_class, empty_classification


def create_empty_classification(cls_code, item):
    """
    creates an empty classification if cls_code is valid for item
    by calling get_new_classification.
    if item is None. no check for valid_classes will be done.
    """
    cl_object = None
    if item is not None:
        valid_classes = cl_api.get_applicable_classes(item)
    else:
        valid_classes = {cls_code}
    if cls_code in valid_classes:
        cl_object = cl_api.get_new_classification([cls_code], narrowed=False)
        # this a complete object with "metadata" : {<classcade>: "properties": ...
    else:
        logging.error(
            "Invalid classcode %s. No classfification data created.", cls_code
        )
    return cl_object


def get_classification_for_item(uc_class, item):
    """
    :param uc_class: classification class
    :param item: cs.vp.Item
    :returns: classification data with additional property name information
    """
    existing_data = cl_api.get_classification(item, with_metadata=True)
    add_additonal_property_infos(uc_class, existing_data)
    return existing_data


def get_familytable_for_class(uc_classcode, dstClass):
    """
    :param uc_classcode: str classcode
    :param dstClass: cdb.objects.Object class
    :returns iterator with tuples of (ddobjects from dstClass, classfification data)
    """
    cond = {
        "assigned_classes": [uc_classcode],
        "class_independent_property_codes": [],
        "properties": {},
    }
    # filter for max_index items
    if dstClass == Item:
        ixsp = util.get_prop("ixsp")
        order_by = "teilenummer, %s desc" % ixsp
        last_teilenummer = ""
        max_index_objs = []
        for obj in dstClass.KeywordQuery(
            order_by=order_by, cdb_object_id=cl_api.search(cond)
        ):
            if last_teilenummer != obj.teilenummer:
                max_index_objs.append(obj)
    elif dstClass == Document:
        ixsm = util.get_prop("ixsm")
        order_by = "z_nummer, %s desc" % ixsm
        last_znummer = ""
        max_index_objs = []
        for obj in dstClass.KeywordQuery(
            order_by=order_by, cdb_object_id=cl_api.search(cond)
        ):
            if last_znummer != obj.z_nummer:
                max_index_objs.append(obj)
    else:
        max_index_objs = dstClass.KeywordQuery(cdb_object_id=cl_api.search(cond))
    for obj in max_index_objs:
        cl_data = cl_api.get_classification(obj, with_metadata=True)
        yield (obj, cl_data)


def get_drawing_for_generic(generic_doc, viewname):
    """
    retrives the drawingmodel for the the cadsystem of
    the generic_doc
    """
    drawing_model = None
    uc_class = class_for_generic(generic_doc)
    if uc_class:
        cad_system = generic_doc.erzeug_system.split(":")[0]
        query = {
            "classification_class_id": uc_class.cdb_object_id,
            "cad_view": viewname,
        }
        model_assignments = ModelAssignment.KeywordQuery(**query)
        valid_models = [
            m.Model
            for m in model_assignments
            if m.Model.erzeug_system.split(":")[0] == cad_system
        ]
        logging.debug("get_draw_for_models: no of valids: %s", len(valid_models))
    else:
        logging.error(
            "get_drawing_for_generic: generic_doc not valid. Not assigned to a class."
        )
    if valid_models:
        drawing_model = valid_models[0]
    return drawing_model


def get_classification(obj):
    if _available:
        return cl_api.get_classification(obj, with_metadata=True)
