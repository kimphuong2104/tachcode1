# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This module contains functions that implements the catalog REST-API.
This API is instable at this time.

Note that POST request are used because the form informations might be too
large to be transferred using the request parameters. They do not alter the
database state as it might be expected during a POST request.
"""

from __future__ import absolute_import
import json
import six

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ["CatalogConfig",
           "CatalogItemsModel",
           "CatalogSelectedValuesModel",
           "CatalogTypeAheadModel",
           "CatalogTableDefWithValuesModel",
           "CatalogValueCheckModel",
           "CatalogQueryFormModel"
           ]

from collections import defaultdict, deque

from cdb import cdbuuid
from cdb import constants
from cdb import misc
from cdb import ElementsError
from cdb import sqlapi
from cdb import typeconversion
from cdb.platform import mom
from cdbwrapc import Operation
from cdbwrapc import RestCatalog
from cdb.platform import gui
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web.rest.generic import convert
from cs.platform.web.rest import get_collection_app, support
from cs.platform.web.rest.support import rest_objecthandle
from cs.platform.web.uisupport.resttable import RestTableWrapper, TableRowObject
from webob.exc import HTTPForbidden, HTTPGone, HTTPNotFound
from cdb.objects.core import class_from_handle
from cdb.objects.iconcache import IconCache, _LabelValueAccessor
from . import App, get_uisupport_app
from .user_settings import SettingsModel
from .utils import SimpleWebUIArguments
from cs.platform.web.root import get_internal
from cs.platform.web.uisupport.tabledef import TableDefBaseModel, TableDefApp
from cs.platform.web.uisupport import get_uisupport
from .dnd_operations import get_dnd_operations

import logging

LOGGER = logging.getLogger(__name__)


class CatalogWithUUID(object):
    """
    Class to provide cached catalogs.
    """

    def __init__(self, catalog):
        self.catalog = catalog
        self.id = cdbuuid.create_uuid()


@six.add_metaclass(misc.Singleton)
class CatalogCache(object):
    """
    A cache for catalogs.
    """

    def __init__(self):
        self.catalogs = deque()
        self.cache_limit = 5  # the number of catalogs to be cached

    def __contains__(self, catalog_id):
        return any(c.id == catalog_id
                   for c in self.catalogs)

    def clear(self):
        """
        Clears the cached structure objects. At this time this is a
        feature for tests that checks if a node can be expanded when
        the structure ist not there.
        """
        self.catalogs = deque()

    def get_catalog(self, catalog_id):
        """
        Returns the catalog stored with the given `catalog_id`.
        """
        result = None
        first = True
        for catalog in self.catalogs:
            if catalog_id == catalog.id:
                result = catalog
                break
            first = False

        if not first and result:
            # Sort to access the recently used elements at the beginning
            self.catalogs.remove(result)
            self.catalogs.appendleft(result)

        if result:
            return result.catalog
        return None

    def add_catalog(self, catalog):
        """
        Adds a catalog to the cache and returns the id that
        has to be used to get the catalog from the cache calling
        `get_catalog`.
        """
        c = CatalogWithUUID(catalog)
        self.catalogs.appendleft(c)
        if len(self.catalogs) > self.cache_limit:
            self.catalogs.pop()
        return c.id

    def remove_catalog(self, catalog_id):
        """
        Remove the catalog with the given `catalog_id`
        from the cache.
        """
        result = None
        for catalog in self.catalogs:
            if catalog_id == catalog.id:
                result = catalog
                break
        if result:
            self.catalogs.remove(result)


class CatalogConfig(object):
    """
    Class to retrieve the catalog configuration.
    Actually the class is used to provide link generation.
    """

    def __init__(self, catalog_name):
        self.catalog_name = catalog_name


@App.path(path="catalog/{catalog_name}", model=CatalogConfig)
def _path_catalog_config(catalog_name):
    """
    """
    return CatalogConfig(catalog_name)


@App.json(model=CatalogConfig, request_method='GET')
def _view_catalog_config(self, request):
    """
    At this time only to provide link generation. In the future we might
    use the call to access the catalog configuration.
    """
    raise HTTPForbidden("Not yet implemented")


class CatalogBaseModel(object):
    """
    Base class for all CatalogModels.
    """

    def __init__(self, catalog_name, extra_parameters):
        """
        Initializes the catalog. `request_para`
        are used to paremtrize the kernel catalog.
        You can retrieve them by calling `get_request_parameter`.
        """
        self.catalog_name = catalog_name
        if extra_parameters:
            self.extra_parameters = extra_parameters
        else:
            self.extra_parameters = {}

    def get_request_parameters(self):
        """
        Return the parameter of the request that
        had consructed the model.
        """
        return self.extra_parameters

    def get_catalog(self, request):
        """
        Returns the catalog object. The request must contain json data.
        This data is a dictionary. The dictionary key for the field the catalog belongs
        to is ``catalog_field``. The form data is stored with the key ``form_data``. The
        form data value is a dictionary that maps attribute names to their values.
        """
        catalog_cache_id = self.extra_parameters.get("catalog_id", None)
        if catalog_cache_id:
            catalog = CatalogCache().get_catalog(catalog_cache_id)
            if catalog:
                return catalog
            else:
                # The id is only provided if we cant run without a cached
                # catalog so raise an error
                msg = gui.Message.GetMessage("web_err_outdated")
                raise HTTPGone(msg)
        input_field = request.json.get("catalog_field", "")
        operation_state = request.json.get("operation_state", None)
        form_data = request.json.get("form_data", {})
        if operation_state:
            json_field_types = operation_state.get("json_field_types", {})
            for attr, typeinfo in json_field_types.items():
                value = form_data.get(attr)
                if typeinfo == sqlapi.SQL_DATE and value:
                    date = convert.load_datetime(value)
                    form_data[attr] = typeconversion.to_legacy_date_format_auto(date)
            op = Operation(operation_state)
        else:
            op = None

        try:
            allow_multi_select = json.loads(self.extra_parameters.get('allow_multi_select', 'false'))
        except ValueError:
            allow_multi_select = False

        if allow_multi_select:
            return RestCatalog(self.catalog_name,
                               input_field,
                               mom.SimpleArguments(**form_data),
                               op,
                               allow_multi_select)
        else:
            # Keep compatibility with older SLs
            return RestCatalog(self.catalog_name,
                               input_field,
                               mom.SimpleArguments(**form_data),
                               op)


class CatalogItemWithValuesModel(CatalogBaseModel):
    pass


@App.path(path="catalog/{catalog_name}/items_with_values", model=CatalogItemWithValuesModel)
def _path_catalog_items_with_values(catalog_name, extra_parameters):
    return CatalogItemWithValuesModel(catalog_name, extra_parameters)


@App.json(model=CatalogItemWithValuesModel, request_method='POST')
def _view_catalog_items_with_values(self, request):
    """
    """
    try:
        c = self.get_catalog(request)
        result = {}
        result["items_with_values"] = c.do_onecolumn_simple_browse_select()
        return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


class CatalogItemsModel(CatalogBaseModel):
    """
    Specialization to retrieve only the string values of a combobox
    """
    pass


@App.path(path="catalog/{catalog_name}/items", model=CatalogItemsModel)
def _path_catalog_items(catalog_name, extra_parameters):
    return CatalogItemsModel(catalog_name, extra_parameters)


@App.json(model=CatalogItemsModel, request_method='POST')
def _view_catalog_items(self, request):
    """
    Get the items of a catalog. If the request parameters contain ``as_objects``
    the call returns a list of object information. A list of strings is returned otherwise.
    The request has to contain the data `get_catalog` needs.
    """

    def _obj_info(obj):
        return {"oid": obj.get_object_id(),
                "icon": IconCache.getIcon(obj.getClassDef().getObjectIconId(),
                                          accessor=_LabelValueAccessor(obj)),
                "label": obj.getDesignation()}

    try:
        c = self.get_catalog(request)
        result = {}
        if "as_objects" in self.get_request_parameters():
            objs = c.do_object_browse()
            result["items"] = [_obj_info(o) for o in objs]
        elif "as_strings" in self.get_request_parameters():
            result["items"] = c.do_onecolumn_simple_browse()
        else:
            raise HTTPForbidden("No valid representation when retrieving catalog items")
        return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


class CatalogSelectedValuesModel(CatalogBaseModel):
    """
    Specialization to retrieve the values to be filled.

    When used in a SelectAndAssign Context self should contain the
    following query parameters in self.extra_parameters
    - relship: role name of the relship
    - parent_classname: classname of the start object of the relship
    - parent_keys: rest keys for the start object of the relship
    """

    @classmethod
    def template_link(cls, request):
        return request.class_link(CatalogSelectedValuesModel,
                                  {"catalog_name": "${catalog_name}",
                                   "extra_parameters": {"as_objects": "${as_objects}"}},
                                  app=get_uisupport(request))

    def get_object_result(self, objs, request):
        result = []
        app = get_collection_app(request)
        for obj in objs:
            cls = class_from_handle(obj)
            result_object = cls._FromObjectHandle(obj)
            result.append(request.view(result_object,
                                       app=app))
        return result


@App.path(path="catalog/{catalog_name}/selected_values",
          model=CatalogSelectedValuesModel)
def _path_catalog_selected_values(catalog_name, extra_parameters):
    return CatalogSelectedValuesModel(catalog_name, extra_parameters)


@App.json(model=CatalogSelectedValuesModel, request_method='POST')
def _view_catalog_selected_values_post(self, request):
    """
    Returns the fields to be filled or if the request parameters contain
    ``as_objects`` the selected objects.
    """
    try:
        result = {}
        c = None
        selection_id = self.extra_parameters.get("selection_id")
        as_objects = "as_objects" in self.get_request_parameters()
        as_operations = \
            self.get_request_parameters().get('parent_keys', None) and \
            self.get_request_parameters().get('relship', None) and \
            self.get_request_parameters().get('parent_classname', None)
        catalog_id = request.json.get("catalog_id", None)
        parent_classname = self.extra_parameters.get('parent_classname', None)
        parent_keys = self.extra_parameters.get('parent_keys', None)
        relship = self.extra_parameters.get('relship', None)
        if catalog_id:
            c = CatalogCache().get_catalog(catalog_id)
        if not c:
            c = self.get_catalog(request)
        if "selected_objects" in request.json:
            objects = request.json.get("selected_objects", [])
            ohs = [mom.CDBObjectHandle(oid) for oid in objects]
            if as_objects:
                result["selected_objects"] = self.get_object_result(ohs, request)
            elif as_operations:
                result["selected_operations"] = get_dnd_operations(request, ohs, parent_classname, parent_keys, relship)
            else:
                result["selected_values"] = c.do_objects_select(ohs)
        elif "selected_rest_ids" in request.json:
            selected_rest_ids = request.json.get("selected_rest_ids", [])
            rest_ids_by_class = defaultdict(list)
            for classname, rest_id in selected_rest_ids:
                rest_ids_by_class[classname].append(rest_id)
            ohs = []
            for classname, rest_ids in rest_ids_by_class.items():
                cdef = CDBClassDef(classname)
                try:
                    handles_by_rest_id = mom.getObjectHandlesFromRESTIDs(cdef, rest_ids, True)
                    handles = [handles_by_rest_id.get(rest_id) for rest_id in rest_ids]
                    ohs += [h for h in handles if h is not None]
                except ValueError:
                    pass
            try:
                if as_objects:
                    result["selected_objects"] = self.get_object_result(ohs, request)
                elif as_operations:
                    result["selected_operations"] = get_dnd_operations(request, ohs, parent_classname, parent_keys, relship)
                else:
                    result["selected_values"] = c.do_objects_select(ohs)
            except ElementsError as e:
                # do not log when selection fails
                raise HTTPForbidden(six.text_type(e))
        elif "selected_string" in request.json:
            # Handle ComboBoxCatalog
            selected_string = request.json.get("selected_string", "")
            selected_values = c.do_onecolumn_simple_select(selected_string)
            if selected_values is None:
                if c.is_value_check_catalog():
                    result["message"] = gui.Message.GetMessage("cdb_checkcatalog_noval")
                selected_values = {}
            result["selected_values"] = selected_values
        elif "selected_ids" in request.json or selection_id:
            selection_ids = request.json.get("selected_ids", [selection_id])
            if as_objects:
                ohs = c.get_selection_as_objects(selection_ids)
                result["selected_objects"] = self.get_object_result(ohs, request)
            elif as_operations:
                ohs = c.get_selection_as_objects(selection_ids)
                result["selected_operations"] = get_dnd_operations(request, ohs, parent_classname, parent_keys, relship)
            else:
                result["selected_values"] = c.do_select(selection_ids)
        # The kernel catalogs provide date field values in the legacy string format,
        # or possibly a search string. For the Web UI, we need to convert this to
        # ISO 8601 format if possible.
        type_info = request.json.get('operation_state', {}).get('json_field_types')
        if type_info:
            for attr, typeinfo in six.iteritems(type_info):
                if typeinfo == sqlapi.SQL_DATE:
                    date_str = result["selected_values"].get(attr)
                    if date_str:
                        try:
                            date_value = typeconversion.from_legacy_date_format(date_str)
                            result["selected_values"][attr] = convert.dump_datetime(date_value)
                        except ValueError:
                            # Might be an expression like ">21.12.2020", so just let it pass
                            pass
        # After the selection we can remove the catalog from the cache
        if catalog_id:
            CatalogCache().remove_catalog(catalog_id)
        return result
    except ElementsError as e:
        LOGGER.exception(e)
        raise HTTPForbidden(six.text_type(e))


class CatalogQueryFormModel(CatalogBaseModel):
    """
    Specialization to retrieve the catalogs query form
    """

    @classmethod
    def template_link(cls, request):
        return request.class_link(CatalogQueryFormModel,
                                  {"catalog_name": "${catalog_name}"},
                                  app=get_uisupport(request))


@App.path(path="catalog/{catalog_name}/query_form", model=CatalogQueryFormModel)
def _path_catalog_queryform(catalog_name, extra_parameters):
    return CatalogQueryFormModel(catalog_name, extra_parameters)


@App.json(model=CatalogQueryFormModel, request_method='POST')
def _get_catalog_form(self, request):
    """
    """
    from cs.web.components.ui_support.forms import FormInfoBase
    c = self.get_catalog(request)
    sargs = SimpleWebUIArguments()
    sargs.append(mom.SimpleArgument(constants.kArgumentDialogUseWebUICfg, "1"))

    dav = c.get_dialog_and_values(False, sargs)
    search_classdef = c.getSearchClassDef()
    fib = FormInfoBase(search_classdef)
    fib.set_search_form_flag()
    result = fib.get_forminfo_dict(request,
                                   dav["dialog"],
                                   dav["values"],
                                   {})
    result["display_mapping_url"] = request.link(CatalogDisplayMappingModel(self.catalog_name, {}))
    # At this time we do not support a real operation state
    # so remove them from the generic result
    op_state = result.pop("operation_state", {})
    ft = op_state.get("json_field_types", None)
    if ft:
        result["json_field_types"] = ft
    # Give a hint if "no search" is set in the catalogs configuration
    af = typeconversion.to_bool(c.get_definition_value("no_search"))
    result["activate_search_form"] = af
    # To allow searching for classification properties, the catalog search needs
    # to know the class it has to search.
    if search_classdef:
        result["search_classname"] = search_classdef.getClassname()
        # For presetting the classified search.
        # This attribute disappears in c.get_dialog_and_values call above. Therefore, we insert it here again.
        # The content of the variable 'cdb::argument.classification_web_ctrl'
        # must be a valid classification json string like:
        # '{"assigned_classes": ["CAR_SEAT"]}'.
        if request.json.get("form_data", {}).get("cdb::argument.classification_web_ctrl") is not None:
            result["values"]["cdb::argument.classification_web_ctrl"] = request.json.get("form_data").get(
                "cdb::argument.classification_web_ctrl")
    return result


class CatalogTableDefWithValuesModel(CatalogBaseModel):
    """
    Specialization to retrieve table definition with values

    When used in a SelectAndAssign context this should contain
    allow_multi_select in its extra_parameters. This will force
    the catalog into multiselect mode.
    """

    @classmethod
    def template_link(cls, request):
        return request.class_link(CatalogTableDefWithValuesModel,
                                  {"catalog_name": "${catalog_name}",
                                   "extra_parameters": {"allow_multi_select": "${allow_multi_select}"}},
                                  app=get_uisupport(request))


@App.path(path="catalog/{catalog_name}/tabular_with_values",
          model=CatalogTableDefWithValuesModel)
def _path_catalog_tabdef(catalog_name, extra_parameters):
    return CatalogTableDefWithValuesModel(catalog_name, extra_parameters)


@App.json(model=CatalogTableDefWithValuesModel, request_method='POST')
def _get_catalog_tabdef(self, request):
    """
    """
    try:
        result = {}
        c = self.get_catalog(request)
        if c:
            query_data = request.json.get("query_data", {})
            values = query_data.get("values", {})
            type_info = query_data.get("json_field_types")
            if type_info:
                for attr, typeinfo in six.iteritems(type_info):
                    if typeinfo == sqlapi.SQL_DATE and attr in values:
                        json_value = values[attr]
                        if json_value:
                            values[attr] = convert.load_datetime(json_value)
            tab_browse = c.do_table_browse(SimpleWebUIArguments(**values))
            if tab_browse:
                result = RestTableWrapper(tab_browse).get_rest_data(request)
                result['multiselect'] = c.is_multiselect()
                result['preview'] = c.is_preview()
                catalog_id = self.extra_parameters.get("catalog_id")
                # We only add it if it is not in the cache
                result['catalog_id'] = \
                    CatalogCache().add_catalog(c) \
                        if catalog_id not in CatalogCache() \
                        else catalog_id
        return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


class CatalogTableDefWithProposalsModel(CatalogBaseModel):
    """
    Specialization to retrieve table definition with proposals

    When used in a SelectAndAssign context this should contain
    allow_multi_select in its extra_parameters. This will force
    the catalog into multiselect mode.
    """
    pass


@App.path(path="catalog/{catalog_name}/tabular_with_proposals",
          model=CatalogTableDefWithProposalsModel)
def _path_catalog_proposal_tabdef(catalog_name, extra_parameters):
    return CatalogTableDefWithProposalsModel(catalog_name, extra_parameters)


@App.json(model=CatalogTableDefWithProposalsModel, request_method='POST')
def _get_catalog_proposal_tabdef(self, request):
    """
    """
    try:
        result = {}
        c = self.get_catalog(request)
        if c:
            tab_browse = c.get_proposal_table()
            if tab_browse:
                result = RestTableWrapper(tab_browse).get_rest_data(request)
                result['multiselect'] = c.is_multiselect()
        return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


class CatalogTypeAheadModel(CatalogBaseModel):
    """
    Specialization to retrieve type ahead proposals
    """

    @classmethod
    def template_link(cls, request):
        return request.class_link(CatalogTypeAheadModel,
                                  {"catalog_name": "${catalog_name}"},
                                  app=get_uisupport(request))


@App.path(path="catalog/{catalog_name}/typeAhead", model=CatalogTypeAheadModel)
def _path_catalog_type_ahead(catalog_name):
    """
    """
    return CatalogTypeAheadModel(catalog_name, {})


@App.json(model=CatalogTypeAheadModel, request_method='POST')
def _get_type_ahead_entries(self, request):
    """
    """
    try:
        result = {}
        c = self.get_catalog(request)
        user_input = request.json.get("user_input", "")
        max_count = request.json.get("max_count", 25)
        result["proposals"] = c.get_type_ahead_proposals(user_input, max_count)
        return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


class CatalogValueCheckModel(CatalogBaseModel):
    """
    Specialization to do a value check.
    """

    @classmethod
    def template_link(cls, request):
        return request.class_link(CatalogValueCheckModel,
                                  {"catalog_name": "${catalog_name}"},
                                  app=get_uisupport(request))


@App.path(path="catalog/{catalog_name}/valueCheck", model=CatalogValueCheckModel)
def _path_catalog_value_check(catalog_name):
    """
    """
    return CatalogValueCheckModel(catalog_name, {})


@App.json(model=CatalogValueCheckModel, request_method='POST')
def _get_value_check_result(self, request):
    """
    """
    try:
        c = self.get_catalog(request)
        return c.do_value_check()
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


class CatalogDisplayMappingModel(CatalogBaseModel):
    """
    Specialization to retrieve a display mapping
    """
    pass


@App.path(path="catalog/{catalog_name}/displaymapping",
          model=CatalogDisplayMappingModel)
def _path_display_mapping(catalog_name):
    return CatalogDisplayMappingModel(catalog_name, {})


@App.json(model=CatalogDisplayMappingModel,
          request_method='POST')
def _get_display_mapping_result(self, request):
    try:
        mapping_id = request.json.get("mapping_id")
        value = request.json.get("value")
        c = self.get_catalog(request)
        return {'new_value': c.getDisplayMapping(mapping_id, value)}
    except ElementsError:
        @request.after
        def set_status(response):
            response.status_code = 403


class CatalogStructureModel(CatalogBaseModel):
    """
    Specialization to retrieve values for structure catalogs
    """

    def _adjust_node(self, node, catalog_id, request):
        """
        Prepares the node for REST. Remove the fields
        we do not need and add further fields if necessary.
        """
        extra = self.extra_parameters.copy()
        extra["parent_node_id"] = node["id"]
        # We have to cache the catalogs id
        extra["catalog_id"] = catalog_id
        expand_model = CatalogStructureModel(self.catalog_name,
                                             extra)
        node["expand_url"] = request.link(expand_model)
        selection_id = node.get("selection_id")
        if selection_id:
            extra["selection_id"] = selection_id
            sel_model = CatalogSelectedValuesModel(self.catalog_name,
                                                   extra)
            node["selectURL"] = request.link(sel_model)

        no_of_subitems = node.pop("no_of_subitems", -1)
        if no_of_subitems == 0:
            node["subnodes"] = []
        else:
            node["subnodes"] = None

        # No one needs the internal id
        node.pop("id")

        oid = node.get("oid")
        if oid:
            obj = TableRowObject(oid)
            if obj:
                restLink = support.get_restlink(obj, request)
                if restLink is not None:
                    node["restLink"] = restLink

    def get_nodes(self, request):
        """Returns a list of dictionaries where every dictionary represents a
        node.

        If you provide a ``parent_node_id`` in `__init__` the nodes returned
        are the subnodes of this node. The root-nodes are returned otherwiese.
        Raises a `cdb.ElementsError` if the structure is not available.
        """
        result = []
        if self.extra_parameters:
            parent_node_id = self.extra_parameters.get("parent_node_id")
            catalog_id = self.extra_parameters.get("catalog_id")
        else:
            parent_node_id = ""
            catalog_id = ""

        c = self.get_catalog(request)
        if not catalog_id:
            catalog_id = CatalogCache().add_catalog(c)

        if not parent_node_id:
            # Get the root
            root_node = c.get_root()
            result.append(root_node)
        else:
            # Retrieve the subnodes
            result = c.get_nodes(parent_node_id)
        for node in result:
            self._adjust_node(node, catalog_id, request)
        return result


@App.path(path="catalog/{catalog_name}/structure", model=CatalogStructureModel)
def _path_catalog_tabdef(catalog_name, extra_parameters):
    return CatalogStructureModel(catalog_name, extra_parameters)


@App.json(model=CatalogStructureModel, request_method='POST')
def _view_structure_catalog(self, request):
    """
    """
    try:
        result = self.get_nodes(request)
        return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


def get_catalog_config(
    request, result, catalog_name, is_combobox, as_objs,
    dnd_parent_classname=None, dnd_parent_keys=None, dnd_relship=None, add_multiselect_hint=False
):
    app = get_uisupport_app(request)
    mask_args = []
    if None not in (dnd_parent_classname, dnd_parent_keys, dnd_relship):
        class_def = CDBClassDef(dnd_parent_classname)
        relship_name = class_def.getRelationshipByRolename(dnd_relship).get_name()
        keymap = mom.relships.Relship.ByKeys(relship_name).resolveKeymapping()
        referer_keymap = keymap[0][2] if keymap else []
        result['form_data'] = {x[0]: rest_objecthandle(class_def, dnd_parent_keys).getValue(x[0], False)
                               for x in referer_keymap}
        mask_args = mom.SimpleArguments(**result['form_data'])
    rest_catalog = RestCatalog(catalog_name, "", mask_args, None, add_multiselect_hint)
    stored_settings = SettingsModel('catalog.preview', catalog_name).get_setting()
    result["userSettings"] = {"settingKey": catalog_name, "preview": json.loads(stored_settings)}
    result["isMultiSelect"] = rest_catalog.is_multiselect() if not add_multiselect_hint else True
    result["catalogName"] = catalog_name
    result["directCreate"] = rest_catalog.get_definition_value("direct_create") == "1"
    if result["directCreate"]:
        try:
            # get_create_opinfo was introduced with CE 15.6.5
            from . import operations
            result["catalogCreateOps"] = [operations._op_info_data(op_info, request,
                                          form_settings_model = CatalogGetDirectCreateOpModel(
                                              catalog_name, {"classname": op_info.get_classname()}))
                                                  for op_info in rest_catalog.get_create_opinfo()]
        except AttributeError:
            result["directCreate"] = False
    result["offerOperations"] = rest_catalog.get_definition_value("offer_operations") == "1"

    result["isNewWindowOperation"] = False
    if request.method == 'POST':
        try:
            additional_params = request.json.get("additional_params", {})
            if "cdb::argument.isNewWindowOperation" in additional_params and \
                additional_params["cdb::argument.isNewWindowOperation"] == 1:
                result["isNewWindowOperation"] = True
        except ValueError:
            LOGGER.warning("Failed to read additional_params from request", exc_info=True)

    if rest_catalog.is_value_check_catalog():
        result["valueCheckURL"] = request.link(
            CatalogValueCheckModel(catalog_name, {}),
            app=app)
    sel_para = {}
    if as_objs:
        sel_para["as_objects"] = "1"
    elif bool(dnd_parent_classname and dnd_parent_keys and dnd_relship):
        sel_para["parent_keys"] = dnd_parent_keys
        sel_para["relship"] = dnd_relship
        sel_para["parent_classname"] = dnd_parent_classname
    if rest_catalog.is_structure_browser():
        result["structureRootURL"] = request.link(CatalogStructureModel(catalog_name, {}),
                                                  app=app)
        result["selectURL"] = request.link(CatalogSelectedValuesModel(catalog_name, sel_para),
                                           app=app)
    else:
        catalog_table_name = rest_catalog.get_definition_value("browser_tabelle")
        class_name = rest_catalog.get_definition_value("classname")
        result['className'] = class_name
        table_base_model = TableDefBaseModel({"class_name": class_name})
        if hasattr(table_base_model, 'extra_parameters') and table_base_model.extra_parameters.get('class_name') == class_name:
            result["tableDefURL"] = request.link(
                table_base_model, app=get_internal(request).child(
                    TableDefApp(catalog_table_name)
                )
            )
        catalog_items_url = request.link(CatalogItemsModel(catalog_name, {}),
                                         app=app)
        if is_combobox:  # Comboboxes should get their values as strings
            catalog_items_url += "?as_strings="
        else:
            # provide type ahead
            result["typeAheadURL"] = request.link(CatalogTypeAheadModel(catalog_name, {}),
                                                  app=app)
        result["selectURL"] = request.link(CatalogSelectedValuesModel(catalog_name, sel_para),
                                           app=app)
        result["catalogTableURL"] = request.link(
            CatalogTableDefWithValuesModel(
                catalog_name,
                {"allow_multi_select": json.dumps(add_multiselect_hint)}), app=app)

        result["itemsURL"] = catalog_items_url
        if rest_catalog.offer_proposals():
            purl = request.link(
                CatalogTableDefWithProposalsModel(
                    catalog_name,
                    {"allow_multi_select": json.dumps(add_multiselect_hint)}), app=app)
            result.update({"proposalLabel": rest_catalog.get_proposal_label(),
                           "proposalCatalogURL": purl})
        if rest_catalog.providesSearchDialog():
            furl = request.link(CatalogQueryFormModel(catalog_name, {}),
                                app=app)
            result.update({"queryFormURL": furl})

    return result


class CatalogGetDirectCreateOpModel(CatalogBaseModel):
    """
    Specialization to retrieve direct create operations for catalogs
    """

    @classmethod
    def template_link(cls, request):
        return request.class_link(CatalogGetDirectCreateOpModel,
                                  {"catalog_name": "${catalog_name}",
                                   "extra_parameters": {"classname": "${classname}"}},
                                  app=get_uisupport(request))


@App.path(path="catalog/{catalog_name}/get_direct_create_operation", model=CatalogGetDirectCreateOpModel)
def _path_catalog_create_op(catalog_name, extra_parameters):
    return CatalogGetDirectCreateOpModel(catalog_name, extra_parameters)


@App.json(model=CatalogGetDirectCreateOpModel, request_method='POST')
def _get_create_ops(self, request):
    """
    """
    classname = self.extra_parameters.get("classname", None)
    if classname:
        c = self.get_catalog(request)
        op = c.get_create_operation(classname)
        dav = op.get_dialog_and_values(SimpleWebUIArguments(**{constants.kArgumentDialogUseWebUICfg: "1"}))
        from . import forms
        clsdef = CDBClassDef(classname)
        return forms.FormInfoBase(clsdef).get_forminfo_dict(
                request,
                dav["dialog"],
                dav["values"],
                dav["operation_state"])
    raise HTTPForbidden()
