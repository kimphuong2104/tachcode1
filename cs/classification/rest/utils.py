#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import datetime
import webob

from cdbwrapc import StatusInfo
from cdb import util
from cdb.objects.core import ByID
from cs.platform.web.rest import get_collection_app
from cs.web.components.ui_support import forms

from cs.classification.util import convert_datestr_to_datetime

OBJ_PROPERTY_VAL_CDEF = None


def convert_from_json(json_prop_value_dict):
    if json_prop_value_dict["property_type"] == 'datetime' and json_prop_value_dict["value"]:
        json_prop_value_dict["value"] = convert_datestr_to_datetime(json_prop_value_dict["value"]).replace(tzinfo=None)


def ensure_json_serialiability(value):
    retVal = value
    if isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
        retVal = value.isoformat()
    elif isinstance(value, dict):
        retVal = {child_key: ensure_json_serialiability(child_val) for (child_key, child_val) in value.items()}
    elif isinstance(value, list) or isinstance(value, set):
        retVal = [ensure_json_serialiability(v) for v in value]
    return retVal


def get_rest_obj_by_id(object_id):
    obj = ByID(object_id)
    if not obj or not obj.CheckAccess("read"):
        msg = util.CDBMsg(util.CDBMsg.kFatal, "cs_classification_object_acces_denied")
        raise webob.exc.HTTPForbidden(str(msg))
    return obj


def get_rest_obj_by_handle_id(object_handle_id):
    from cdb.platform import mom
    from cdb.objects.core import object_from_handle

    obj_handle = mom.CDBObjectHandle(object_handle_id)
    obj = object_from_handle(obj_handle)
    if not obj or not obj.CheckAccess("read"):
        msg = util.CDBMsg(util.CDBMsg.kFatal, "cs_classification_object_acces_denied")
        raise webob.exc.HTTPForbidden(unicode(msg))
    return obj


def render_object_classification_to_json(request, object_classification):
    json_data = request.view(object_classification, app=get_collection_app(request))
    try:
        info = StatusInfo(object_classification.cdb_objektart, object_classification.status)
        json_data['cdb_status_txt_localized'] = info.getLabel()
    except AttributeError:
        # not localized status text will be used
        pass
    return json_data


def get_property_catalog_configs(request, metadata):

    def get_catalog_identifier(properties):
        for property_code, property_data in properties.items():
            catalog_identifier = property_data['catalog']
            if catalog_identifier:
                catalog_identifiers.add(catalog_identifier)
            if 'block' == property_data['type']:
                get_catalog_identifier(property_data['child_props_data'])

    catalog_identifiers = set()
    for class_code, class_data in metadata.get('classes', {}).items():
        get_catalog_identifier(class_data['properties'])
    get_catalog_identifier(metadata.get('addtl_properties', {}))

    return get_catalog_configs(request, catalog_identifiers)


def get_catalog_configs(request, catalog_identifiers):
    catalog_configs = {}
    for catalogIdentifier in catalog_identifiers:
        catalog_configs[catalogIdentifier] = forms.FormInfoBase.get_catalog_config(
            request, catalogIdentifier, is_combobox=False, as_objs=False
        )
    return catalog_configs


