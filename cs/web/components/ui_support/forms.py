# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module forms

This is the documentation for the forms module.
"""

from __future__ import absolute_import
import json
import logging
import math
import datetime

import six
from webob.exc import HTTPBadRequest, HTTPNotFound, HTTPForbidden

from cdbwrapc import Operation, RelshipContext, SQL_DATE

from cdb import constants
from cdb import misc
from cdb import sqlapi
from cdb import typeconversion
from cdb import ElementsError
from cdb import i18n
from cdb.objects.core import ObjectHandleWrapper
from cdb.platform import mom
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.mom.operations import OperationInfo, OperationStateInfo
from cdb.platform import gui
from cs.platform.web import util
from cs.platform.web.rest import support
from cs.platform.web.rest.generic import convert
from cs.platform.web.uisupport.util import get_link_suffix_to_relship_target

from . import catalogs
from . import App, get_uisupport_app
from .configuration import WebUIDialogHook, WebUIDialogHookFunction
from .dialog_hooks import DialogHook, DialogHookPreDisplay
from .utils import drl_encode_strings

__docformat__ = "restructuredtext en"
__revision__ = "$Id: forms.py 213746 2020-06-26 13:10:27Z gwe $"

# Exported objects
__all__ = ["FormSettings"]


LOGGER = logging.getLogger(__name__)
DROPZONE_FILES_ATTRIBUTE = "cdb::argument.webui_dropzone_files"


def get_opstate(old_state, operation):
    """
    Retrieves the operation state from operation and adds further information,
    especially the json_field_types from `old_state`.
    """
    if operation:
        result = operation.getOperationState()
        fts = old_state.get("json_field_types", None)
        if fts is not None:
            result["json_field_types"] = fts
    return result


def _from_iso_date_format(val):
    if isinstance(val, (datetime.date, datetime.datetime)) or val is None:
        return val
    for date_format in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(val, date_format)
        except ValueError:
            pass


class FormInfoBase(object):
    """
    Class to provide operation dialogs customized with the
    |elements| dialog configuration to the REST API.
    """
    def __init__(self, clsdef=None, extra_parameters=None):
        """
        Construction of a form with the class `clsdef` which is of type
        `cdb.platform.mom.entities.CDBClassDef`.
        """
        self.clsdef = clsdef
        self.obj_link_prefix = None
        self.extra_parameters = extra_parameters if extra_parameters else {}
        self.is_search_form = False

    _allowed_types = {
        0: "text",
        2: "checkbox",
        4: "combobox",
        10: "catalog",
        11: "longtext",
        12: "image",
        13: "button",
        17: "fileopenbrowser",
        20: "calendar",
        21: "hyperlink",
        22: "email",
        23: "enumcombobox",  # A combobox with display mappings
        24: "password",
        25: "objectuuid",
        26: "numericedit",
        35: "component"
    }

    _Fallback_Catalog_Config = {"itemsURL": "",
                                "selectURL": "",
                                "catalogTableURL": "",
                                "typeAheadURL": "",
                                "valueCheckURL": ""}

    @classmethod
    def get_catalog_config(cls, request, catalog_name, is_combobox,
                           as_objs=False, add_multiselect_hint=False):
        """
        Returns a dictionary that contains the properties the catalog
        components of the Elements-UI usually needs to display a catalog.
        `is_combobox` is ``True`` if the catalog is bound to a combobox
        in a form. If you set `as_objs` to ``True`` the URL use to select
        the result will return objects instead of attribute value pairs.
        If you set `add_multiselect_hint` to ``True`` the catalog allows
        multi selection regardless of field configuration.
        """
        # Fallback if not supported
        result = cls._Fallback_Catalog_Config.copy()
        if catalog_name:
            catalogs.get_catalog_config(
                request, result, catalog_name, is_combobox, as_objs,
                add_multiselect_hint=add_multiselect_hint
            )
        return result

    def set_use_operation_state(self):
        """
        If set and the caller provides an operation state, the form is
        generated using the operation. This is recommended if you want
        to use dialog hooks that uses the operation, e.g. the
        `` EmulateLegacyDialogButton`` hook.
        At this time the flag ist only evaluated if you use
        `get_form_def_and_values` to retrieve the form.
        """
        self.extra_parameters["use_opstate"] = "1"

    def use_operation_state(self):
        """
        Returns ``True`` if the form should be generated using the
        operation state.
        """
        return self.extra_parameters.get("use_opstate", "0") == "1"

    def use_object_links(self, prefix):
        """
        Call this function if you want to navigate the relationship links
        defined in the form using the object's values and not the
        the form values. `prefix` is the UI link of the object the form
        displays. if no prefix is given, no link is returned.
        """
        if not prefix:
            prefix = ""  # Avoid None because we do not want to render form links
        self.obj_link_prefix = prefix

    def set_search_form_flag(self):
        """
        Call this function if your dialog is used for a kind of search
        operation. This will prevent logging errors if a search value does
        not match the type of an attribute, e.g. ``!=0`` for an integer field.
        """
        self.is_search_form = True

    def _calc_maskitem_span(self, maskitems):
        """ calculate span for the bootstrap grid system
        """
        def _get_row_max(maskitems):
            result = 0
            for m in maskitems:
                result = max(result, m["row"])
            return result

        rows = [[] for _ in six.moves.range(_get_row_max(maskitems) + 1)]
        for maskitem in maskitems:
            if maskitem["row"] > -1 and maskitem["column"] > -1:
                if rows[maskitem["row"]]:
                    rows[maskitem["row"]].append(maskitem)
                else:
                    rows[maskitem["row"]] = [maskitem, ]
        for row in rows:
            count = len(row)
            if count:
                span = int(math.floor(12 / count))
                for m in row:
                    m["span"] = span
                    if not m["label"]:
                        m["label"] = " "

    def _get_fieldtypes_from_form(self, registers):
        """
        Returns a `dict` that maps the dialog field attribute ids to
        their data type.
        """
        id2type = {}
        for register in registers:
            for field in register["fields"]:
                id2type[field["attribute"]] = field["data_type"]
                if "multilang" in field:
                    for mfield in field["multilang"]:
                        id2type[mfield["attribute"]] = mfield["data_type"]
        return id2type

    def _get_adef(self, identifier):
        """
        Returns the definition that belongs to identifier
        """
        adef = None
        if self.clsdef:
            adef = self.clsdef.getAttributeDefinition(identifier)
            if not adef:
                try:
                    adef = self.clsdef.getFacetAttributeDefinition(identifier)
                except AttributeError:
                    pass  # CE 16 does not support getFacetAttributeDefinition
        return adef

    def _adapt_value_names(self, values, type_dict):
        """
        Check the keys of the `values` dictionary. If the name is not
        an identifier - which at this time means that the name does not
        contain a dot - the name might be changed if it is an attribute name
        or the form contains an identifier that matches the name.
        The function returns the adapted dictionary
        """
        result = {}
        for attr, val in six.iteritems(values):
            new_name = attr
            if attr not in type_dict and attr.find(".") == -1:
                # If someone configures a name in a mask that is not
                # an attribute it results in a name like ``.attr``
                if "." + attr in type_dict:
                    new_name = "." + attr
                else:
                    if self.clsdef:
                        adef = self._get_adef(attr)
                        if adef:
                            new_name = adef.getIdentifier()
            result[new_name] = val
        return result

    def _adapt_value_type(self, values, type_dict):
        """
        Uses the form information to adapt the type of the values in `values`
        using the informations of type_dict. Returns the adapted `dict`.
        """
        result = {}
        for attr, val in six.iteritems(values):
            attr_type = type_dict.get(attr, None)
            iso_convert_failed = False
            if self.clsdef and attr_type in [None, SQL_DATE]:
                # Try to receive the type from the data dictionary
                adef = self._get_adef(attr)
                if adef:
                    if adef.is_text():
                        attr_type = sqlapi.SQL_CHAR
                    elif attr_type == SQL_DATE:
                        # If we have an SQL_DATE, we want to know wether we should display time or not
                        attr_type = adef
                        # Provide support for ISO-8601 format without timezone offset
                        converted_date = _from_iso_date_format(val)
                        if converted_date is not None:
                            val = typeconversion.to_legacy_date_format(converted_date)
                        else:
                            iso_convert_failed = True
                    else:
                        attr_type = adef.getSQLType()
            try:
                result[attr] = convert.dump_value(typeconversion.to_python_rep(attr_type, val))
            except ValueError as v:
                if not self.is_search_form:
                    err = v
                    if iso_convert_failed:
                        err = "Time data must be provided in iso format without timezone offset " \
                              "('%s' / '%s') or in CE standard format ('%s' / '%s')" \
                              % ("YYYY-MM-DD", "YYYY-MM-DDThh:mm:ss",
                                 "DD.MM.YYYY", "DD.MM.YYYY HH:mm:ss")
                    LOGGER.error("Failed to convert value %s of type %s for attr %s to %d: %s"
                                 % (val, type(val), attr, type_dict.get(attr, None), err))
                result[attr] = convert.dump_value(val)
        return result

    def _adapt_values_for_uicontrols(self, values, registers):
        result = values.copy()
        for register in registers:
            for field in register["fields"]:
                self._adapt_value_for_uicontrol_checkbox(result, field)
        return result

    def _adapt_value_for_uicontrol_checkbox(self, values, field):
        """ Initialize values for checkbox fields to 1 or 0, if they are neither
            readonly nor mandatory. Set values also for fields that don't have
            one yet, so that the operation the form belongs to does not get an
            empty value (see E055030).
        """
        if (field["fieldtype"] == "checkbox"
            and not field["mandatory"]
            and field["readonly"] == 0
            and ("tri_state" not in field["config"] or not field["config"]["tri_state"])
        ):
            key = field["attribute"]
            value = values.get(key)
            values[key] = 1 if value and value != "0" else 0

    def _add_fieldtype(self, maskitem):
        """
        Sets the attribute `fieldtype` in the maskitem dictionary.
        Returns ``True`` if a valid type has been found.
        """
        result = maskitem["itemtype"] in self._allowed_types
        if result:
            if "numeric_edit" in maskitem["config"]:
                maskitem["fieldtype"] = self._allowed_types[26]
            elif maskitem["config"].get("password", False):
                maskitem["fieldtype"] = self._allowed_types[24]
            else:
                maskitem["fieldtype"] = self._allowed_types[maskitem["itemtype"]]
        return result

    def _clear_item(self, maskitem):
        """
        Removes informations that are not for the REST-API,
        e.g. itemtyp.
        """
        maskitem.pop("itemtype", None)
        maskitem["config"].pop("link_target", None)
        maskitem["config"].pop("catalog_name", None)

    def _add_attrdef_label(self, maskitem):
        """
        Sometimes the dialog is not used as configured. For this case it is
        more suitable to use the Labels configured for the data dictionary
        attribute. This function adds a field named ``attribute_label``
        """
        adef = self._get_adef(maskitem["attribute"])
        if adef:
            maskitem["attribute_label"] = adef.getLabel()
        else:
            maskitem["attribute_label"] = maskitem["label"]

    def _prepare_maskitem(self, maskitem, request):
        """
        Append additional config settings (link, catalog) to maskitem
        """
        # if there is a target_link create the url
        link_target = maskitem["config"].get("link_target")
        if link_target:
            if self.obj_link_prefix:
                # At this time this is a hint that we have no operation
                uuid_attr = maskitem["config"].get("uuid_link_attr_name")
                if uuid_attr:
                    obj_values = request.json.get("obj_values", None)
                    if obj_values:
                        uuid = obj_values.get(uuid_attr)
                        if uuid:
                            from cs.platform.web.uisupport import get_ui_link
                            obj = mom.getObjectHandleFromObjectID(uuid)
                            maskitem["config"]["link_target_url"] = get_ui_link(request, obj)
                elif self.clsdef:
                    rs = self.clsdef.getRelationship(link_target)
                    if rs:
                        rs_name = rs.get_rolename()
                        link = self.obj_link_prefix + get_link_suffix_to_relship_target(rs_name)
                        maskitem["config"]["link_target_url"] = link
            elif self.obj_link_prefix is None:
                lt = FormLinkTarget(link_target)
                maskitem["config"]["link_target_url"] = request.link(lt)
        itemtype = maskitem["itemtype"]
        if itemtype == 12:  # Image
            if maskitem["config"]["icon"] and maskitem["config"]["icon"][0] != "/":
                maskitem["config"]["icon"] = "/" + maskitem["config"]["icon"]
        if itemtype == 35 and "icon_cfg" in maskitem.get("config", {}):
            # React Component with Icon
            icon_url = maskitem["config"]["icon_cfg"]["icon"]
            if icon_url and icon_url[0] != "/":
                maskitem["config"]["icon_cfg"]["icon"] = "/" + icon_url
        if itemtype in (4, 10):  # Catalogs
            catalog_name = maskitem["config"]["catalog_name"]
            try:
                catalog_config = self.get_catalog_config(request,
                                                         catalog_name,
                                                         itemtype == 4)
                if not catalog_name and not \
                   maskitem["config"].get("catalog_values", None):
                    maskitem["readonly"] = 1
            except ElementsError as exc:
                catalog_config = self._Fallback_Catalog_Config
                maskitem["readonly"] = 1
                misc.log(0,
                         "Failed to retrieve configuration for catalog '%s' in field '%s':%s" %
                         (catalog_name, maskitem["attribute"], str(exc)))

            maskitem["config"].update(catalog_config)
            if self.clsdef:
                maskitem["config"]["contextClass"] = self.clsdef.getClassname()
        if itemtype == 11 or itemtype == 35:  # LongText, ReactComponent
            adef = self._get_adef(maskitem["attribute"])
            if adef:
                maskitem["config"].update({'content_type': adef.getContentType()})

    def _get_fields(self, mask, request, values):
        maskitems = []
        for maskitem in mask["maskitems"]:
            maskitem["origin_attribute"] = maskitem["attribute"]
            maskitem["origin_mandatory"] = maskitem["mandatory"]
            maskitem["origin_label"] = maskitem["label"]

            # Remember the state so that you can return to the original state if necessary E058563
            maskitem["origin_readonly"] = maskitem["readonly"]
            # handle multilanguage field
            if "multilang_mask" in maskitem and "multilang_mask_lang" in maskitem:
                # login language first, then fallback languages
                user_priority_iso_langs = [i18n.default()] + i18n.FallbackLanguages()
                parent_mi = maskitem
                # search for the first filled field in user priority order
                main_idx = None
                for iso_lang in user_priority_iso_langs:
                    try:
                        main_idx = maskitem["multilang_mask_lang"].index(iso_lang)
                    except ValueError:
                        pass
                    if main_idx is not None:
                        mask_at_index = maskitem["multilang_mask"][main_idx]
                        attr = mask_at_index["attribute"]
                        if values and attr in values and values[attr]:
                            break
                        else:
                            main_idx = None

                # Use the first filled field if no other has priority
                if main_idx is None:
                    main_idx = 0
                    for idx, mask in enumerate(maskitem["multilang_mask"]):
                        attr = mask["attribute"]
                        if values and attr in values and values[attr]:
                            main_idx = idx
                            break

                # mask item to show in form
                maskitem = maskitem["multilang_mask"][main_idx]
                maskitem["row"] = parent_mi["row"]
                maskitem["column"] = parent_mi["column"]
                maskitem["origin_attribute"] = parent_mi["origin_attribute"]
                maskitem["origin_mandatory"] = parent_mi["origin_mandatory"]
                maskitem["origin_label"] = parent_mi["origin_label"]
                maskitem["origin_readonly"] = parent_mi["readonly"]
                maskitem["label"] = parent_mi["label"] + " (" + parent_mi["multilang_mask_lang"][main_idx] + ")"
                maskitem["config"].update({"iso_lang": parent_mi["multilang_mask_lang"][main_idx]})
                if "link_target" in parent_mi["config"] and parent_mi["config"]["link_target"]:
                    maskitem["config"].update({"link_target": parent_mi["config"]["link_target"]})
                maskitem["tooltip"] = parent_mi["tooltip"]

                # mask items to show in group dialog
                mls = parent_mi["multilang_mask"][0:main_idx] + parent_mi["multilang_mask"][main_idx+1:]
                mls_lang = parent_mi["multilang_mask_lang"][0:main_idx] + parent_mi["multilang_mask_lang"][main_idx+1:]

                if mls:
                    maskitem["multilang"] = mls
                    for idx, ml in enumerate(maskitem["multilang"]):
                        if self._add_fieldtype(ml):
                            self._prepare_maskitem(ml, request)
                            ml["config"].update({"iso_lang": mls_lang[idx]})
                            ml["label"] = parent_mi["label"] + " (" + mls_lang[idx] + ")"
                            ml["parent_label"] = parent_mi["label"]
                            ml["parent_attribute"] = parent_mi["origin_attribute"]
                            ml["origin_readonly"] = ml["readonly"]
                            self._add_attrdef_label(ml)
            if self._add_fieldtype(maskitem):
                self._add_attrdef_label(maskitem)
                self._prepare_maskitem(maskitem, request)
                maskitems.append(maskitem)
        self._calc_maskitem_span(maskitems)
        for mi in maskitems:
            self._clear_item(mi)
        return maskitems

    def _call_pre_display_hook(self,
                               hook_id, values, type_dict,
                               wizard_progress, opstate, registers,
                               request=None, request_json=None):
        """
        Call the hook with the given id
        """
        def modify_field_property(attribute, property, value):
            for reg in registers:
                for field in reg['maskitems']:
                    if 'multilang_mask' in field:
                        for ml in field['multilang_mask']:
                            if ml['attribute'] == attribute:
                                ml[property] = value
                    if field['attribute'] == attribute:
                        field[property] = value

        if request_json and request_json.get("wizard_progress"):
            wizard_progress.update(request_json.get("wizard_progress"))
        h = DialogHookPreDisplay(hook_id, values, wizard_progress, opstate)
        h.set_request(request)
        result = h.perform()
        for attribute, value in result['readonly_changes'].items():
            modify_field_property(attribute, 'readonly', value)
        for attribute, value in result['mandatory_changes'].items():
            modify_field_property(attribute, 'mandatory', value)
        pre_display_vals = self._adapt_value_names(result['new_values'], type_dict)
        values = values if values else {}
        values.update(pre_display_vals)
        wizard_progress.update(result['wizard_progress'])

    def _handle_dialog_hooks(self, request, registers, values, type_dict, wizard_progress, opstate):
        """
        Provide the REST information for dialog hooks and call
        hooks configured with ``::PRE_DISPLAY::``. Values set by the
        hook implementation will be set or replaced in the `values`
        dictionary.
        """
        def _get_mask_identifier(hook):
            ha = hook.attribut
            result = ha
            # Do not iterate through all registers for standard
            # hooks (::PRE_DISPLAY::, ::PRE_SUBMIT::) or Wildcard
            if ha == "*" or ha[:2] == "::":
                return ha
            for reg in registers:
                if hook.dialog_name == reg["mask_name"]:
                    for m in reg["maskitems"]:
                        if m["attribute"] == ha:
                            # Exact match
                            return ha
                        else:
                            if m["attribute"].split(".")[-1] == ha:
                                # Best match so far
                                result = m["attribute"]
            return result

        def _get_hook_data(hook, hook_func):
            result = {"attribute": _get_mask_identifier(hook),
                      "backend_hook": hook_func.backend,
                      "synchronous": hook.synchronous}
            if hook_func.backend:
                result.update({"hook_id": hook.hook_name})
            else:
                result.update({"function_name": hook_func.function_name})
            return result

        def _get_predicate_mask_hook_data():
            """
            A hook injected for predicate masks.
            """
            return {"attribute": "::PRE_SUBMIT::",
                    "backend_hook": 1,
                    "hook_id": "HandleMaskCompositionsWithPredicateMasks"}

        def _get_request_json(request):
            """
            Returns the JSON Data for a POST request and an empty dict
            for a GET request.
            """
            request_json = {}
            try:
                request_json = request.json
            except ValueError:
                # A GET request without query parameter
                # would raise ValueError at that moment
                # the "json" get accessed
                pass
            return request_json

        def _get_all_values(req, values, opstate):
            """
            `values` are the form values but the hook might need
            further values set in previous masks.
            """
            result = values
            obj_values = req.get("obj_values", None)
            if obj_values and opstate:
                jft = opstate.get("json_field_types", None)
                if jft:
                    for k, v in six.iteritems(jft):
                        if k not in values and k in obj_values:
                            val = obj_values[k]
                            if v == sqlapi.SQL_DATE:
                                val = convert.load_datetime(val)
                            result[k] = val
            return result

        dialog_names = [reg["mask_name"] for reg in registers]
        all_hooks = WebUIDialogHook.get_active_hooks(dialog_names)
        fe_hook_data = []
        be_hook_data = []
        request_json = _get_request_json(request)
        all_values = None
        isSearchAgain = opstate and opstate.get('opname') == 'CDB_SearchAgain'
        for hook in all_hooks:
            hook_func = WebUIDialogHookFunction.get_config(hook.hook_name)
            if hook_func:
                if hook_func.backend:
                    if hook.attribut == "::PRE_DISPLAY::":
                        if isSearchAgain:
                              # We prevent pre_display dialog hooks for RelshipTables (this
                            # is indicated by CDB_SearchAgain) as this may affect the
                            # dialog being used in other contexts. See E060526.
                            # https://code.contact.de/platform/cs.web/-/merge_requests/354
                            continue

                        if all_values is None:
                            all_values = _get_all_values(request_json, values, opstate)
                        self._call_pre_display_hook(
                            hook.hook_name, all_values, type_dict,
                            wizard_progress, opstate, registers,
                            request, request_json)
                    else:
                        be_hook_data.append(_get_hook_data(hook, hook_func))
                else:
                    fe_hook_data.append(_get_hook_data(hook, hook_func))
            else:
                misc.log_error("Dialog hook function '%s' not found" % hook.function_name)

        # Inject a hook if we display a predicate mask
        # We have to use opstate first because catalogs will call this
        # function too during requests that also contains the state of the
        # surrounding operaiopm
        op_state = opstate if opstate is not None \
            else request_json.get("operation_state", None)
        if op_state:
            oi = OperationStateInfo(op_state)
            if oi.get_predicate_mask_flag():
                hd = _get_predicate_mask_hook_data()
                be_hook_data.append(hd)
                self._call_pre_display_hook(hd["hook_id"], values, type_dict,
                                            wizard_progress, opstate, registers,
                                            request, request_json)
        dh = {}
        if fe_hook_data:
            dh.update({"frontend_hooks": fe_hook_data})
        if be_hook_data:
            hook_url = request.link(DialogHook())
            dh.update({"backend_hooks": {"url": hook_url,
                                         "hooks": be_hook_data}})
        return dh

    def get_forminfo_dict(self, request, form_info, values=None, opstate=None):
        """
        Returns a dictionary with the formula info. `form_info` is a dictionary
        returned from the platform, e.g. when calling `gui.get_dialog`. The
        dictionary is manipulated by this function.
        `values` is a dict of attribute names an their values. The function
        will add the values to the result dictionary in a way suitable to
        be used with a REST API.
        """
        # Remove the registers from the dict because we have to
        # adapt the values
        registers = form_info.pop("registers")
        form_info["registers"] = []  # Will be handled later
        for register in registers:
            fields = self._get_fields(register, request, values)
            if fields:
                form_info["registers"].append({"label": register["label"],
                                               "mask_name": register["mask_name"],
                                               "fields": fields,
                                               "help_url": register["help_url"],
                                               "icon": register["icon"]
                                               })
        # Handle the type of the values
        type_dict = self._get_fieldtypes_from_form(form_info["registers"])
        form_vals = None
        if isinstance(values, dict):
            form_vals = self._adapt_value_type(values, type_dict)
            form_vals = self._adapt_values_for_uicontrols(form_vals, form_info["registers"])
            form_info["values"] = form_vals
        if isinstance(opstate, dict):
            # We add the type dict of the fields to the operation_state
            # This will allow us to convert the json-Values back to the
            # correct types in the post request
            if "json_field_types" in opstate:
                opstate["json_field_types"].update(type_dict)
            else:
                opstate["json_field_types"] = type_dict
            form_info["operation_state"] = opstate
            form_info["display_mapping_url"] = request.link(DisplayMapping())

        # Add information for registered & active dialog hooks
        wizard_progress = {}
        form_info["dialog_hooks"] = self._handle_dialog_hooks(request,
                                                              registers,
                                                              form_vals,
                                                              type_dict,
                                                              wizard_progress,
                                                              opstate)

        # clean up simulated localfilename attribute, i.e. it
        # is added by forms.FormSettingsForOperation and not
        # configured in dialog
        if form_vals and \
           DROPZONE_FILES_ATTRIBUTE in form_vals and \
           constants.kArgumentLocalFilename in form_vals and \
           constants.kArgumentLocalFilename not in type_dict:
            del form_info["values"][constants.kArgumentLocalFilename]

        form_info["wizard_progress"] = wizard_progress

        return form_info


class FormInfoSimple(FormInfoBase):
    """
    Class to provide dialogs customized with the
    |elements| dialog configuration to the REST API.
    """
    def __init__(self, dialog_name, extra_parameters=None):
        super(FormInfoSimple, self).__init__(None, extra_parameters)
        self.dialog_name = dialog_name

    def get_form_def(self, request):
        """
        Returns a dictionary with the form informations
        """
        return self.get_forminfo_dict(request,
                                      gui.get_dialog(self.dialog_name))

    def get_form_def_and_values(self, request):
        """
        Returns a dictionary with the form informations including form values
        and operation state
        """
        obj_values = request.json.get("obj_values", None)
        opstate = request.json.get("operation_state", None)

        form_info = None
        if opstate and self.use_operation_state():
            # Use the operation to create the form - otherwise
            # we cannot use the legacy hooks
            op = Operation(opstate)
            form_info = op.get_dialog(self.dialog_name)
            # The state might have changed
            opstate = get_opstate(opstate, op)
        else:
            form_info = gui.get_dialog(self.dialog_name)
        return self.get_forminfo_dict(request,
                                      form_info,
                                      obj_values,
                                      opstate)


@App.path(path="form/info/{dialog_name}",
          model=FormInfoSimple)
def get_simpleform(dialog_name, extra_parameters):
    return FormInfoSimple(dialog_name, extra_parameters)


@App.json(model=FormInfoSimple)
def form_view(self, request):
    try:
        return self.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


@App.json(model=FormInfoSimple, request_method='POST')
def form_view_with_values(self, request):
    try:
        return self.get_form_def_and_values(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


class FormInfoClassDef(FormInfoBase):
    """
    Class to provide dialogs customized with the
    |elements| dialog configuration to the REST API in
    the context of a specific class
    """
    def __init__(self, dialog_name, clsdef, extra_parameters=None):
        super(FormInfoClassDef, self).__init__(clsdef, extra_parameters)
        self.dialog_name = dialog_name

    def get_form_def(self, request):
        """
        Returns a dictionary with the form informations
        """
        return self.get_forminfo_dict(request,
                                      self.clsdef.get_dialog(self.dialog_name))

    def get_form_def_and_values(self, request):
        """
        Returns a dictionary with the form informations and a dictionary that
        contains the form values suitable to the type of the form fields.
        The values has to be provided in the ``obj_values`` key of the json data.
        You can add a ``refresh=1`` parameter to get the actual values - in this case
        ``obj_values`` must contain at least the objects primary keys.
        """
        def refresh_object(vals):
            """
            Loads and reloads an object from class definition and key values.
            """
            keynames = self.clsdef.getKeyNames()
            # We have to provide the actual values, so reload object data
            key_vals = {k: v for k, v in six.iteritems(obj_values) if k in keynames}
            obj = mom.getObjectHandle(self.clsdef, **key_vals)
            try:
                obj.reload()
                # Wrap object handle to get typed values
                wrapped = ObjectHandleWrapper(obj)
                for k in vals:
                    if self.clsdef.getAttributeDefinition(k):
                        vals[k] = wrapped[k]
                return obj
            except:
                return None

        obj_values = request.json.get("obj_values", None)
        values = {}
        form_info = None
        if obj_values and self.clsdef:
            vals = convert.load(obj_values, self.clsdef)
            need_refresh = self.extra_parameters.get("refresh", 0)
            obj = None
            if need_refresh:
                obj = refresh_object(vals)

            opstate = request.json.get("operation_state", None)
            if opstate and self.use_operation_state():
                # Use the operation to create the form - otherwise
                # we cannot use the legacy hooks (E045473)
                op = Operation(opstate)
                form_info = op.get_dialog(self.dialog_name,
                                          self.clsdef.getClassname(),
                                          vals)
                # The state might have changed
                opstate = get_opstate(opstate, op)
            else:
                form_info = self.clsdef.get_dialog(self.dialog_name, vals)

            # Adapt the attribute names to match the dialog that uses
            # the attribute identifiers and not the names
            for reg in form_info["registers"]:
                for item in reg["maskitems"]:
                    items = [item]
                    if "multilang_mask" in item:
                        items += item["multilang_mask"]
                    for item in items:
                        item_name = item["attribute"]
                        adef = self.clsdef.getAttributeDefinition(item_name)
                        if adef:
                            if obj:
                                values[item_name] = obj[item_name]
                                continue
                        if item_name in vals:
                            values[item_name] = vals[item_name]
                        elif adef and adef.getName() in vals:
                            values[item_name] = vals[adef.getName()]
                        elif item_name in obj_values:
                            # Seems to be a value of a previous form
                            val = obj_values[item_name]
                            if val is not None and \
                               item["data_type"] == sqlapi.SQL_DATE:
                                val = convert.load_datetime(val)
                            values[item_name] = val
                        else:
                            if not obj and adef:
                                obj = refresh_object(vals)
                                if obj:
                                    values[item_name] = obj[item_name]

        if not form_info:
            if opstate and self.use_opstate():
                # Use the operation to create the form - otherwise
                # we cannot use the legacy hooks (E045473)
                op = Operation(opstate)
                form_info = op.get_dialog(self.dialog_name,
                                          "",
                                          vals)
                # The state might have changed
                opstate = get_opstate(opstate, op)
            else:
                form_info = self.clsdef.get_dialog(self.dialog_name, vals)

        return self.get_forminfo_dict(request,
                                      form_info,
                                      values,
                                      opstate)


@App.path(path="form/classdef/{clsdef}/{dialog_name}",
          model=FormInfoClassDef,
          converters={'clsdef': util.classdef_converter})
def get_classdef_form(clsdef, dialog_name, extra_parameters):
    return FormInfoClassDef(dialog_name, clsdef, extra_parameters)


@App.json(model=FormInfoClassDef)
def classef_form_view(self, request):
    try:
        return self.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


@App.json(model=FormInfoClassDef, request_method='POST')
def classef_form_view_with_values(self, request):
    """
    Returns the form and adapts the values sent with the POST
    request to match the identifiers used in the form.
    """
    try:
        return self.get_form_def_and_values(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


class FormSettingsForOperation(FormInfoBase):
    """ Abstract parent class for form settings that use an operation.
    """
    def __init__(self, opname, clsdef, object_navigation_ids=None, extra_parameters=None):
        """
        Construction of a form used for the operation
        `opname` with the class `clsdef` which is of type
        `cdb.platform.mom.entities.CDBClassDef`.
        """
        super(FormSettingsForOperation, self).__init__(clsdef, extra_parameters)
        self.object_navigation_ids = []
        self.additional_params = {}
        self._add_object_navigation_ids(object_navigation_ids)
        if extra_parameters:
            self._add_additional_params(json.loads(extra_parameters.get("additional_params", "{}")))
        self.opname = opname

    def add_object_navigation_ids_from_request(self, request):
        if request.method == 'POST':
            try:
                object_navigation_ids = request.json.get("object_navigation_id", [])
                self._add_object_navigation_ids(object_navigation_ids)
            except ValueError:
                LOGGER.warning("Failed to read object_navigation_id from request", exc_info=True)

    def _add_object_navigation_ids(self, object_navigation_ids):
        if object_navigation_ids:
            self.object_navigation_ids.extend([oid for oid in object_navigation_ids if oid])

    def add_additional_params_from_request(self, request):
        if request.method == 'POST':
            try:
                additional_params = request.json.get("additional_params", {})
                self._add_additional_params(additional_params)
            except ValueError:
                LOGGER.warning("Failed to read additional_params from request", exc_info=True)

    def _add_additional_params(self, additional_params):
        self.additional_params.update(additional_params)

    def _resolve_object_navigation_ids(self):
        return support.rest_objecthandles(self.clsdef,
                                          self.object_navigation_ids)

    def _get_op_info(self):
        if not hasattr(self, "cached_op_info"):
            opinfo = mom.operations.OperationInfo(self.clsdef.getClassname() if self.clsdef else None,
                                                  self.opname)
            if not opinfo:
                if self.clsdef is None:
                    error = gui.Message.GetMessage("op_not_configured_meta",
                                                   self.opname)
                else:
                    error = gui.Message.GetMessage("op_not_configured",
                                                   self.opname,
                                                   self.clsdef.getTitle())
                raise HTTPNotFound(error)
            self.cached_op_info = opinfo
        return self.cached_op_info

    def _get_dialog_args(self):
        from .operations import SimpleWebUIArguments
        opinfo = self._get_op_info()
        if not opinfo or not opinfo.offer_in_webui():
            if self.clsdef is None:
                error = gui.Message.GetMessage("csweb_err_op_not_available_meta",
                                               self._get_op_info().get_label())
            else:
                error = gui.Message.GetMessage("csweb_err_op_not_available",
                                               self._get_op_info().get_label(),
                                               self.clsdef.getTitle())
            raise HTTPForbidden(error)
        sargs = SimpleWebUIArguments()
        dialog_name = self.extra_parameters.get("dialog_name")
        if dialog_name:
            sargs.append(mom.SimpleArgument(constants.kArgumentDialogName,
                                            dialog_name))
        else:
            sargs.append(mom.SimpleArgument(constants.kArgumentDialogUseWebUICfg, "1"))
        # Add any additional parameters to the op args. If "additional_params"
        # is given, it is assumed to be a JSON encoded dict.
        for k, v in six.iteritems(self.additional_params):
            sargs.append(mom.SimpleArgument(k, v))

        # Information of files if existing
        file_info = self.extra_parameters.get(DROPZONE_FILES_ATTRIBUTE)
        if file_info:
            sargs.append(mom.SimpleArgument(DROPZONE_FILES_ATTRIBUTE, file_info))
            fname = None
            try:
                finfo = json.loads(file_info)
                if len(finfo):
                    fname = finfo[0]["name"]
            except ValueError:
                pass
            sargs.append(mom.SimpleArgument(constants.kArgumentLocalFilename, fname))
        return sargs


class FormSettingsMeta(FormSettingsForOperation):
    def __init__(self, opname):
        super(FormSettingsMeta, self).__init__(opname, None)

    def get_form_def(self, request):
        """
        Returns a dictionary with the form informations and the
        initial values. The form informations are stored with the key
        ``registers``. the values with the key ``values``.
        If the operation works on one ore more objects these objects
        has to be provided as a list of `cdb.platform.mom.CDBObjectHandle`
        objects.
        """
        objects = self._resolve_object_navigation_ids()
        opinfo = self._get_op_info()
        sargs = self._get_dialog_args()
        dav = opinfo.get_dialog_and_values(objects, sargs)
        return self.get_forminfo_dict(request,
                                      dav["dialog"],
                                      dav["values"],
                                      dav["operation_state"])


@App.path(path="form/operation/meta/{opname}",
          model=FormSettingsMeta)
def get_form_settings(opname):
    return FormSettingsMeta(opname)


@App.json(model=FormSettingsMeta)
def form_settings_view(self, request):
    try:
        return self.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


@App.json(model=FormSettingsMeta, request_method='POST')
def form_settings_view(self, request):
    try:
        self.add_object_navigation_ids_from_request(request)
        return self.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


class FormSettings(FormSettingsForOperation):
    """
    Class to provide operation dialogs customized with the
    |elements| dialog configuration to the REST API.
    """

    def get_form_def(self, request):
        """
        Returns a dictionary with the form informations and the
        initial values. The form informations are stored with the key
        ``registers``. the values with the key ``values``.
        If the operation works on one ore more objects these objects
        has to be provided as a list of `cdb.platform.mom.CDBObjectHandle`
        objects.
        """
        objects = self._resolve_object_navigation_ids()
        opinfo = self._get_op_info()
        sargs = self._get_dialog_args()
        dav = opinfo.get_dialog_and_values(objects, sargs)
        return self.get_forminfo_dict(request,
                                      dav["dialog"],
                                      dav["values"],
                                      dav["operation_state"])


@App.path(path="form/operation/class/{opname}/{clsdef}",
          model=FormSettings,
          converters={'clsdef': util.classdef_converter,
                      'object_navigation_id': [six.text_type],
                      'object_navigation_id[]': [six.text_type]})
def get_form_settings(opname, clsdef, extra_parameters):
    object_navigation_ids = extra_parameters.get('object_navigation_id[]',
                                                 extra_parameters.get('object_navigation_id', []))
    return FormSettings(opname, clsdef, object_navigation_ids, extra_parameters)


@App.json(model=FormSettings)
def form_settings_view(self, request):
    try:
        return self.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


@App.json(model=FormSettings, request_method='POST')
def form_settings_view(self, request):
    try:
        self.add_object_navigation_ids_from_request(request)
        self.add_additional_params_from_request(request)
        return self.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


class FormSettingsRelship(FormSettingsForOperation):
    """ Provides form settings for operations in a relationship context.
    """
    def __init__(self, parent_classname, keys, relship_name, opname,
                 target_classname=None,
                 object_navigation_ids=None, extra_parameters=None):
        self.parent_classname = parent_classname
        self.keys = keys
        self.relship_name = relship_name
        self.parent_clsdef = CDBClassDef(self.parent_classname)
        self.parent_handle = support.rest_objecthandle(self.parent_clsdef, keys)
        self.relship_ctx = RelshipContext(self.parent_handle, self.relship_name)
        self.reference_clsdef = self.relship_ctx.get_rship_def().get_reference_cldef()
        self.target_classname = target_classname or self.reference_clsdef.getClassname()
        self.target_clsdef = (CDBClassDef(target_classname)
                              if target_classname
                              else self.reference_clsdef)
        self.link_clsdef = self.relship_ctx.get_rship_def().get_link_cldef()
        # To avoid the retrieval of the operation info we use the trick that
        # in a relationship the operation works on the link class if the
        # operation name differs from the configured operation name
        op_cldef = self.target_clsdef
        (op, rsname) = OperationInfo.parse_opname(opname)
        if op != opname and rsname != "SkipRelshipContext":
            op_cldef = self.link_clsdef
        super(FormSettingsRelship, self).__init__(opname, op_cldef,
                                                  object_navigation_ids, extra_parameters)

    def _resolve_object_navigation_ids(self):
        # Overwritten, because the object_navigation_ids for relship
        # operations are always target objects but the classdef for
        # the dialogs may be the link cldef
        return support.rest_objecthandles(self.target_clsdef,
                                          self.object_navigation_ids)

    def _get_op_info(self):
        if hasattr(self, "cached_op_info"):
            return self.cached_op_info

        self.cached_op_info = None
        try:
            opInfos = self.relship_ctx.getOperationInfos(False, "", self.clsdef.getClassname())
        except TypeError:
            opInfos = self.relship_ctx.getOperationInfos(False)
        class_hierarchy = [self.clsdef.getClassname()]
        class_hierarchy.extend(self.clsdef.getBaseClassNames())
        # I'm not sure wether opInfos may contain one operation for multiple classes in the hierarchy,
        # so search whole list, before searching with the next classname up the hierarchy
        for class_name in class_hierarchy:
            for info in opInfos:
                if info.get_opname() == self.opname and info.get_classname() == class_name:
                    self.cached_op_info = info
                    return self.cached_op_info

        error = gui.Message.GetMessage("op_not_configured",
                                       self.opname,
                                       self.clsdef.getTitle())
        raise HTTPNotFound(error)

    def _get_persistent_ids(self, request):
        try:
            if request.method == 'POST':
                persistent_ids = request.json.get("persistent_ids")
                if persistent_ids:
                    return drl_encode_strings(persistent_ids)
        except ValueError:
            pass
        return ""


    def get_form_def(self, request):
        """ See FormSettings.get_form_def
        """
        objects = self._resolve_object_navigation_ids()
        sargs = self._get_dialog_args()
        persistent_ids = self._get_persistent_ids(request)
        sargs.append(mom.SimpleArgument(constants.kArgumentPersistentTableIDs,
                                        persistent_ids))
        if len(objects) == 0:
            # When we are creating a reference object and reference class of
            # relship is subclassable, we need to determine exact subclass.
            creates_link_class = (
                self.link_clsdef is not None and
                self.reference_clsdef.getClassname() != self.link_clsdef.getClassname() and
                self._get_op_info().get_classname() == self.link_clsdef.getClassname()
            )
            if self.reference_clsdef.isSubclassable() and not creates_link_class:
                sargs.push_back(mom.SimpleArgument(
                    self.target_clsdef.getAttrIdentifier('cdb_classname'),
                    self.target_classname))
            op = self.relship_ctx.operation(self.opname, sargs, False, creates_link_class)
        elif len(objects) == 1:
            op = self.relship_ctx.operation(self.opname, objects[0], sargs, False)
        else:
            op = self.relship_ctx.operation(self.opname, objects, sargs, False)
        dav = op.get_dialog_and_values(mom.SimpleArguments())
        return self.get_forminfo_dict(request,
                                      dav["dialog"],
                                      dav["values"],
                                      dav["operation_state"])


@App.path(path="form/operation/relship/{parent_classname}/{keys}/{relship_name}/{opname}/{target_classname}",
          model=FormSettingsRelship,
          converters={'object_navigation_id': [six.text_type],
                      'object_navigation_id[]': [six.text_type]})
def get_form_settings_relship(parent_classname, keys, relship_name, opname, target_classname, extra_parameters):
    object_navigation_ids = extra_parameters.get('object_navigation_id[]',
                                                 extra_parameters.get('object_navigation_id', []))
    return FormSettingsRelship(parent_classname, keys, relship_name, opname, target_classname,
                               object_navigation_ids, extra_parameters)


@App.json(model=FormSettingsRelship)
def form_settings_relship_view(model, request):
    try:
        return model.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


@App.json(model=FormSettingsRelship, request_method='POST')
def form_settings_relship_view(model, request):
    try:
        model.add_object_navigation_ids_from_request(request)
        model.add_additional_params_from_request(request)
        return model.get_form_def(request)
    except ElementsError as e:
        raise HTTPNotFound(str(e))


class FormLinkTarget(object):
    def __init__(self, link_id):
        self.link_id = link_id


@App.path(path="form/link_target/{link_id}",
          model=FormLinkTarget)
def generic_formlinktarget_path(link_id):
    return FormLinkTarget(link_id)


@App.json(model=FormLinkTarget,
          request_method='POST')
def _retrieve_form_link(self, request):
    from cs.platform.web.uisupport import get_ui_link
    result = {"ok": True}
    try:
        op_state = request.json.get("operation_state", None)
        if op_state:
            op = Operation(op_state)
            args = mom.SimpleArguments()
            jft = op_state.get("json_field_types", {})
            # Currently there also values for the icon fields. We ignore these
            # dictionaries
            for key, value in six.iteritems(request.json.get("values")):
                if not isinstance(value, dict):
                    if value and jft.get(key) == sqlapi.SQL_DATE:
                        value = convert.load_datetime(value)
                    args.append(mom.SimpleArgument(key, value))
            obj = op.getFormLinkTarget(self.link_id, args)
            result['ui_link'] = get_ui_link(request, obj)
        else:
            raise HTTPBadRequest(detail=u"Missing parameter `operation_state`.")

    except ElementsError as exc:
        result["ok"] = False
        result["error_message"] = '%s' % exc
    return result


class DisplayMapping(object):
    """
    Class for conversion from internal value to display value.
    """
    pass


@App.path(path="form/displaymapping",
          model=DisplayMapping)
def path():
    return DisplayMapping()


@App.json(model=DisplayMapping,
          request_method='POST')
def get_display_mapping(self, request):
    from cs.platform.web.uisupport import get_ui_link
    try:
        mapping_id = request.json.get("mapping_id")
        value = request.json.get("value")
        op_state = request.json.get("operation_state", None)
        if op_state:
            op = Operation(op_state)
            return {'new_value': op.getDisplayMapping(mapping_id, value)}
        else:
            if mapping_id == "CDBObjectUUIDMapping":
                oh = mom.getObjectHandleFromObjectID(value)
                if oh:
                    return {'new_value': oh.getDesignation(), 'ui_link': get_ui_link(request, oh)}
        return {'new_value': value}

    except ElementsError:
        @request.after
        def set_status(response):
            response.status_code = 403
