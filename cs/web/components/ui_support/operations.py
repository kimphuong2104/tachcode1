# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath app to access configured operations.
"""

from __future__ import absolute_import

from cdb import ElementsError
from cdb import cmsg
from cdb import constants
from cdb import misc
from cdb import sqlapi
from cdb import auth
from cdb.objects.core import class_from_handle
from cdb.platform.gui import Message
from cdb.platform.mom.entities import CDBClassDef
from cdb.wsgi.util import proxyserver_base
from cdbwrapc import (Operation, OperationInfo, RelshipContext,
                      kObjectType, kHtmlViewType, kClassType, kRecordUnknown, RelationshipDefinition)
from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.generic import convert
from cs.platform.web.rest.support import rest_objecthandle, rest_objecthandles, rest_key
from cs.platform.web.uisupport import get_ui_link, get_webui_link
from cs.platform.web.uisupport.resttable import RestTableWrapper

import six
from webob.exc import HTTPNotFound

from . import App, catalogs, get_uisupport_app
from .forms import FormSettings, FormSettingsRelship, FormSettingsMeta
from .utils import WebFileUploadHelper, SimpleWebUIArguments, ui_name_for_class
from .operations_catalog import OperationCatalogModel
from cs.web.components.history.view import update_history_collection


def inject_proxy_base(request, values):
    values.update({
        'cdb:argument.www_root_url': proxyserver_base(request.environ)
    })


def _op_info_data(op_info, request,
                  run_operation_model=None,
                  form_settings_model=None,
                  relship_context_id=None,
                  target_clname=None):
    """
    Render the information about an operation available to the frontend
    """
    try:
        clname = op_info.get_classname()
        if clname:
            cdef = CDBClassDef(clname)
        else:
            cdef = None
    except AttributeError as e:
        raise HTTPNotFound(six.text_type(e))
    except ElementsError as e:
        raise HTTPNotFound(six.text_type(e))

    if cdef:
        ui_name = ui_name_for_class(cdef)
    else:
        ui_name = None

    # TODO: rewrite this whole stuff, there is no win ui any more! The hasattr
    # check is a test for CE 15.x
    is_IIOP_server = (hasattr(misc, 'kAppl_IIOPServer')
                      and misc.CDBApplicationInfo().rootIsa(misc.kAppl_IIOPServer))
    opname = op_info.get_opname()
    iconurls = op_info.get_icon_urls()
    prefer_webui = not is_IIOP_server or not op_info.prefer_winui()
    menu_visible_webui = op_info.is_visible_webui()
    # Standard values
    essential = False
    form_settings = None
    run_op = None
    presentation_id = None
    url = None
    activation_mode = op_info.get_activation_mode()
    if op_info.offer_in_webui() and prefer_webui:
        if form_settings_model is None:
            form_settings = \
                FormSettingsMeta(opname) \
                if cdef is None else \
                FormSettings(opname, cdef)
        else:
            form_settings = form_settings_model
        if run_operation_model is None:
            if cdef is None:
                run_op = RunOperationMetaModel(opname)
            else:
                run_op = RunOperationClassModel(clname, opname)
        else:
            run_op = run_operation_model
        essential = op_info.is_essential_op()
        presentation_id = op_info.get_render_comp_id()
    else:
        if is_IIOP_server and op_info.is_visible_webui() and cdef:
            (op, rsname) = OperationInfo.parse_opname(opname)
            add_relship_context = bool(relship_context_id)
            if rsname == "RelshipFromReference" and activation_mode >= 2:
                if target_clname:
                    clname = target_clname
                    cdef = CDBClassDef(clname)
            elif rsname == "SkipRelshipContext":
                opname = op
                add_relship_context = False
            msg = cmsg.Cdbcmsg(clname, opname, True)
            if add_relship_context:
                msg.add_sys_item("relship_context", relship_context_id)
            # Add the keys for object operations
            if activation_mode == 3:
                # We do not have urls for multi selection so reduce
                # to single selection
                activation_mode = 2
            if activation_mode == 2:
                for key in cdef.getKeyNames():
                    msg.add_item(key, cdef.getPrimaryTable(), "${%s}" % key)
            # We have to unquote because of the {var} syntax
            # We only use variable names so the url cannot contain any
            # other dangerous char
            url = six.moves.urllib.parse.unquote(msg.cdbwin_url())
            essential = op_info.is_essential_op()

    ui_app = get_uisupport_app(request)
    return {"label": op_info.get_label(),
            "opname": opname,
            "creates_object": op_info.creates_object(),
            "menu_path": op_info.get_label_path(False),
            "menu_visible_winclient": op_info.is_visible(),
            "menu_visible": menu_visible_webui,
            "classname": clname if clname else None,
            "class_ui_name": ui_name,
            "tooltip": op_info.get_tooltip(),
            "icon": ("/%s" % iconurls[0]) if iconurls else None,
            "form_url": request.link(form_settings, app=ui_app) if form_settings else None,
            "submit_url": request.link(run_op, app=ui_app) if run_op else None,
            "activation_mode": activation_mode,
            "essential": essential,
            "presentation_id": presentation_id,
            "frontend_script": op_info.get_frontend_script(),
            "target_url": url,
            "menugroup": op_info.get_menugroup(),
            "ordering": op_info.get_order(),
            "class_designation": cdef.getDesignation() if cdef else ui_name,
            "op_designation": op_info.get_tooltip(),
            "offer_in_webui": op_info.offer_in_webui()}

# access to operations via operation contexts ---


class OpContextModel(object):

    def __init__(self, context_name, classname):
        self.context_name = context_name
        self.classname = classname


@App.path(path="operation/context/{context_name}/{classname}", model=OpContextModel)
def _operation_context_path(context_name, classname):
    return OpContextModel(context_name, classname)


@App.json(model=OpContextModel)
def _get_op_context(model, request):
    try:
        cdef = CDBClassDef(model.classname)
    except ElementsError as e:
        raise HTTPNotFound(six.text_type(e))
    return [_op_info_data(op_info, request)
            for op_info in cdef.getOperationInfos(False, model.context_name)
            if op_info]

# getting operation infos for a single operation for a class ---


@App.path(path="operation/class/{classname}/{opname}", model=OperationInfo)
def _operation_info_path(classname, opname):
    return OperationInfo(classname, opname)


@App.json(model=OperationInfo)
def _get_op_info(model, request):
    return _op_info_data(model, request)

# getting operation infos for a class ---


class OperationInfoClass(object):
    """
    Morepath model class to retrieve all operations for
    a class (without context)
    """

    def __init__(self, classname):
        self.classname = classname

    def getOperationInfos(self, visible):
        """
        Retrieve all operation infos for the
        class provided during construction.
        If `visible` is ``True`` only the operations
        that are marked as menu visible for the user are returned.
        """
        return CDBClassDef(self.classname).getOperationInfos(visible)


@App.path(path="operation/class/{classname}", model=OperationInfoClass)
def _operation_info_class_path(classname):
    return OperationInfoClass(classname)


@App.json(model=OperationInfoClass)
def _get_op_info_class(model, request):
    try:
        return [_op_info_data(op_info, request)
                for op_info in model.getOperationInfos(False)
                if op_info]

    except ElementsError as e:
        raise HTTPNotFound(six.text_type(e))

# getting operation info for a single operation in a relationship context


class RSReferenceOperationInfo(object):
    """
    Morepath model class to retrieve a single operation info for the reference
    class of a relationship.
    """

    def __init__(self, parent_classname, keys, relship_name, opname):
        """
        Class used to retrieve operation info for the relationship
        `relship_name` called for the parent object identified by
        `parent_classname` and the REST key `keys`.
        """
        self.parent_classname = parent_classname
        self.keys = keys
        self.relship_name = relship_name
        self.opname = opname


@App.path(path="operation/relship/reference/{parent_classname}/{keys}/{relship_name}/{opname}",
          model=RSReferenceOperationInfo)
def _rs_operation_info_path(parent_classname, keys, relship_name, opname):
    return RSReferenceOperationInfo(parent_classname, keys, relship_name, opname)


@App.json(model=RSReferenceOperationInfo)
def _rs_operation_info_view(model, request):
    """
    """
    oir = OperationInfoRelship(model.parent_classname,
                               model.keys,
                               model.relship_name)
    ref_info = oir.getOperationInfo().get_reference_op_info()
    ois = ref_info.get_opinfo_list()
    for oi in ois:
        if oi.get_configured_opname() == model.opname:
            return (_op_info_data(oi,
                                  request,
                                  oir.run_operation_model(oi),
                                  oir.form_settings_model(oi)))

# getting operation infos for relationships ---


class OperationInfoRelship(object):
    """
    Morepath model class to retrieve the operations for a relationship context
    """

    def __init__(self, parent_classname, keys, relship_name, target_classname=''):
        self.parent_classname = parent_classname
        self.keys = keys
        self.relship_name = relship_name
        self.target_classname = target_classname
        self.relship_catalog = ''
        self.relship_context_id = ''

    def getOperationInfo(self):
        """
        Returns the `RelshipOperationInfo` object for the specific operation.
        """
        hndl = rest_objecthandle(CDBClassDef(self.parent_classname), self.keys)
        rc = RelshipContext(hndl, self.relship_name)
        self.relship_context_id = rc.get_id()
        return rc.getOperationInfo(False, self.target_classname, '', True)

    def run_operation_model(self, op_info):
        return RunOperationRelshipModel(self.parent_classname,
                                        self.keys,
                                        self.relship_name,
                                        op_info.get_opname())

    def form_settings_model(self, op_info):
        # When we have at least one object, the kernel will determine the correct
        # class from there.
        target_class_name = self.target_classname if op_info.is_object_operation() else op_info.get_classname()
        return FormSettingsRelship(self.parent_classname,
                                   self.keys,
                                   self.relship_name,
                                   op_info.get_opname(),
                                   target_classname=target_class_name)

    def get_reference_opinfo(self, request):

        def _get_rsopinfo(key, rsopinfo, model, request):
            result = {}
            opinfos = rsopinfo.get_opinfo_list()
            if opinfos:
                result[key] = (rsopinfo.get_label(),
                               [_op_info_data(op_info, request,
                                              model.run_operation_model(op_info),
                                              model.form_settings_model(op_info),
                                              model.relship_context_id,
                                              model.target_classname)
                                for op_info in opinfos if op_info])
                for opinfo in result[key][1]:
                    if opinfo['opname'] == 'CDB_SelectAndAssign':
                        catalog_model = OperationCatalogModel(self.parent_classname, self.keys, self.relship_name)
                        opinfo['catalog_url'] = catalog_model.link(request)

            return result

        info = self.getOperationInfo()
        result = {}
        loi = info.get_link_op_info()
        result.update(_get_rsopinfo("link_opinfo",
                                    loi,
                                    self,
                                    request))

        # If there are separate operations for the link operation do not
        # offer Delete as an essential reference operation to avoid
        # misunderstandings (Removing link vs. Removing target)
        target_delete_is_not_essential = loi and loi.get_opinfo_list()
        ref_ops = _get_rsopinfo("reference_opinfo",
                                info.get_reference_op_info(),
                                self, request)
        if target_delete_is_not_essential:
            ops = ref_ops.get("reference_opinfo", [])
            for op in ops[1]:
                if op.get("opname", "") == constants.kOperationDelete:
                    op["essential"] = False
        result.update(ref_ops)
        return result


@App.path(path="operation/relship/{parent_classname}/{keys}/{relship_name}",
          model=OperationInfoRelship)
def _relship_operation_info_relship_path(parent_classname, keys, relship_name, target_classname=''):
    return OperationInfoRelship(parent_classname, keys, relship_name, target_classname)


@App.json(model=OperationInfoRelship)
def _get_op_info_relship(model, request):
    return model.get_reference_opinfo(request)


class BatchOperationInfoRelship(object):
    """
    Morepath model class to retrieve the operations for multiple relationship contexts
    """

    def __init__(self, parent_classname, keys):
        self.parent_classname = parent_classname
        self.keys = keys


@App.path(path="batchload/operation/relship/{parent_classname}/{keys}",
          model=BatchOperationInfoRelship)
def _relship_operation_info_relship_path(parent_classname, keys):
    return BatchOperationInfoRelship(parent_classname, keys)


@App.json(model=BatchOperationInfoRelship, request_method='POST')
def _get_batch_op_info_relship(model, request):
    relship_names = request.json.get("relship_names")
    target_classnames = request.json.get("target_classnames")
    ops_relships = {}
    for relship_name in relship_names:
        target_classname = target_classnames[relship_name]
        obj = rest_objecthandle(CDBClassDef(model.parent_classname), model.keys)
        clsdef = obj.getClassDef()
        relship_def = clsdef.getRelationshipByRolename(relship_name)
        result = {}
        if not relship_def.get_acl() or obj.getAccessInfo(auth.persno).get(
                relship_def.get_acl())[0]:
            result = OperationInfoRelship(model.parent_classname,
                                          model.keys,
                                          relship_name,
                                          target_classname).get_reference_opinfo(request)
        ops_relships.update({relship_name: {target_classname: result}})

    return ops_relships

# helper functions for building & executing an operation from a request ---


def _extract_values(request_data):
    # Combine additional_params and values into a single argument list for
    # the operation. For keys that exist in both dicts, values (ie. the
    # values entered by the user in the form fields) take precedence.
    values = request_data.get("additional_params", {})
    values.update(request_data.get("values", {}))
    operation_state = request_data.get("operation_state")

    # remove kArgumentLocalfilename because the file will get uploaded
    # after running the operation
    if request_data.get("create_before_uploading", False) and \
        constants.kArgumentLocalFilename in values:
        del values[constants.kArgumentLocalFilename]

    if operation_state:
        type_info = operation_state.get("json_field_types")
        if type_info:
            for attr, typeinfo in six.iteritems(type_info):
                if typeinfo == sqlapi.SQL_DATE and attr in values:
                    json_value = values[attr]
                    if json_value:
                        values[attr] = convert.load_datetime(json_value)
                if attr not in values:
                    values[attr] = None
    return (values, operation_state)


def _make_target(request_data, target_classdef, opname):
    # The operation target is either a single object, if a string ID is given,
    # or a list of objects if a list of IDs is given.
    object_navigation_id = request_data.get("object_navigation_id")
    clnames = set()
    if object_navigation_id is None or object_navigation_id == []:
        target = None
        clnames.add(target_classdef.getClassname())
    else:
        if isinstance(object_navigation_id, six.string_types):
            oids = [object_navigation_id]
        else:
            oids = object_navigation_id
        targets = rest_objecthandles(target_classdef, oids)
        if len(targets) == 1:
            target = targets[0]
        else:
            target = targets
    # Check if the operation is activated for all classes
    for clname in clnames:
        op_cfg = OperationInfo(clname, opname)
        if not op_cfg or not op_cfg.offer_in_webui():
            error = Message.GetMessage("csweb_err_op_not_available",
                                       opname,
                                       clname)
            raise ElementsError(error)
    return target


def _run_operation(request, op, request_json):
    try:
        # DBEventCollector was introduced with CE 15.6.0
        from cdb.util import DBEventCollector
        with DBEventCollector() as event_collector:
            run_result = op.run()
    except ImportError:
        run_result = op.run()
        event_collector = None
        pass
    result_type, result_value = op.get_result()
    result = {'result_type': result_type}
    if run_result and run_result[1]:
        result['operation_message'] = run_result[1]
    if result_type == kObjectType:
        if result_value.is_valid():
            cls = class_from_handle(result_value)
            result_object = cls._FromObjectHandle(result_value)
            # Delete should not return the deleted object E050141
            if op.getOperationState()['opname'] != "CDB_Delete":
                result_rest_data = request.view(result_object,
                                                app=get_collection_app(request))
            else:
                result_rest_data = {}
            # Check if result_rest_data is dict.
            # If we operate on CDB_File, it will be a 'Response' object,
            # instead of dict.
            if isinstance(result_rest_data, dict):
                # The operation always returns the web_ui_link. This allows to avoid navigation
                # when using web ui pages in the Windows Client, while custom handlers may use
                # the context-dependent URL. See E041117.
                ui_link = get_ui_link(request, result_object)
                web_ui_link = get_webui_link(request, result_object)
                object_handle = result_object.ToObjectHandle()
                if object_handle.isRecentObjectRelevant():
                    rest_name = object_handle.getClassDef().getRESTName()
                    rest_id = rest_key(object_handle)
                    ref_object_id = object_handle.getUUID()
                    update_history_collection(rest_name, rest_id, ref_object_id)
                result['object'] = result_rest_data
                if ui_link:
                    result['ui_link'] = ui_link
                if web_ui_link:
                    result['web_ui_link'] = web_ui_link
    elif result_type == kHtmlViewType:
        # Elements UI uses web_ui_link field, so we provide that too, see E046292
        result.update({'ui_link': result_value[0],
                       'web_ui_link': result_value[0],
                       'view_extern': result_value[1]})
    elif result_type == kClassType:
        try:
            request_data = request_json
        except ValueError:
            request_data = {}
        tableName = request_data.get("tableName", "")
        rest_table = result_value.as_table(tableName)
        result.update(RestTableWrapper(rest_table).get_rest_data(request))

    refresh_info = op.getRefreshInfo()
    result['refreshInfo'] = refresh_info
    if event_collector is not None:
        # DBEventCollector was introduced with CE 15.6.0
        events = event_collector.get_events()
        rest_links = [event.get_rest_link(request) for event in events
                      if event.get_event_type() != kRecordUnknown and
                      event.get_rest_link() is not None]
        result['refreshInfo']['restLinks'] = rest_links
    return result

# running operations without context ---


class RunOperationMetaModel(object):

    def __init__(self, opname):
        self.opname = opname


@App.path(path="operation/meta/{opname}/run", model=RunOperationMetaModel)
def _run_operation_class_path(opname):
    return RunOperationMetaModel(opname)


@App.json(model=RunOperationMetaModel, request_method='POST')
def _run_operation_meta(model, request):
    try:
        op = None
        request_data = _get_request_data(request)
        (values, operation_state) = _extract_values(request_data)
        inject_proxy_base(request, values)
        if operation_state:
            op = Operation(operation_state, SimpleWebUIArguments(**values))
        return _run_operation(request, op, request_data)
    except ElementsError as exc:

        @request.after
        def set_status(response):
            response.status_code = 403

        result = op.getOperationResult() if op else {}
        result['message'] = '%s' % exc
        return result


class RunOperationClassModel(object):
    """
    Morepath model class to execute an operation without a context
    """

    def __init__(self, classname, opname):
        self.classname = classname
        self.opname = opname


@App.path(path="operation/class/{classname}/{opname}/run", model=RunOperationClassModel)
def _run_operation_class_path(classname, opname):
    return RunOperationClassModel(classname, opname)


@App.json(model=RunOperationClassModel, request_method='POST')
def _run_operation_class(model, request):
    """ To initiate configured operations on an object, a POST request is used.
        The name and classdef of the operation are computed from the URL, the
        arguments to use are contained in the request body.

        The arguments must conform to the internal formats, independent of the
        user's settings like date formats or decimal separators.
    """
    try:
        op = None
        request_data = _get_request_data(request)
        (values, operation_state) = _extract_values(request_data)
        inject_proxy_base(request, values)
        target_classdef = CDBClassDef(model.classname)
        target = _make_target(request_data, target_classdef, model.opname)
        args = SimpleWebUIArguments(**values)
        if target is None:
            target = model.classname
        if operation_state:
            op = Operation(operation_state, args)
        else:
            op = Operation(model.opname, target, args)
        return _run_operation(request, op, request_data)
    except ElementsError as exc:

        @request.after
        def set_status(response):
            response.status_code = 403

        result = op.getOperationResult() if op else {}

        result['message'] = '%s' % exc
        return result

# running operations in relationship context ---


class RunOperationRelshipModel(object):
    """
    Morepath model class to execute an operation in a relationship context
    """

    def __init__(self, parent_classname, keys, relship_name, opname):
        self.parent_classname = parent_classname
        self.keys = keys
        self.relship_name = relship_name
        self.opname = opname


@App.path(path="operation/relship/{parent_classname}/{keys}/{relship_name}/{opname}/run",
          model=RunOperationRelshipModel)
def _run_operation_relship_path(parent_classname, keys, relship_name, opname):
    return RunOperationRelshipModel(parent_classname, keys, relship_name, opname)


@App.json(model=RunOperationRelshipModel, request_method='POST')
def _run_operation_relship(model, request):
    """ See _run_operation_class above
    """
    try:
        # Check wether parent of relship is still valid
        parent_handle = rest_objecthandle(CDBClassDef(model.parent_classname), model.keys)
        if not parent_handle.exists():
            msg = "Parent object %s / %s not found" % (model.parent_classname, model.keys)
            raise HTTPNotFound(detail=msg)

        # Now instantiate the operation and run it.
        op = None
        request_data = _get_request_data(request)
        (values, operation_state) = _extract_values(request_data)
        inject_proxy_base(request, values)
        args = SimpleWebUIArguments(**values)
        if operation_state:
            op = Operation(operation_state, args)
        else:
            relship_ctx = RelshipContext(parent_handle, model.relship_name)
            target_classdef = relship_ctx.get_rship_def().get_reference_cldef()
            target = _make_target(request_data, target_classdef, model.opname)
            if target:
                op = relship_ctx.operation(model.opname, target, args)
            else:
                op = relship_ctx.operation(model.opname, args)
        return _run_operation(request, op, request_data)
    except (ValueError, ElementsError) as exc:

        @request.after
        def set_status(response):
            response.status_code = 403

        result = op.getOperationResult() if op else {}
        result['message'] = '%s' % exc
        return result


def _get_request_data(request):
    request_data = {}
    if request.content_type=="application/json":
        request_data = request.json
    else: # multipart/form-data
        json_data = ""
        items = request.POST.items()
        for item in items:
            fs = item[1]
            if fs.file:
                if fs.name == 'json':
                    json_data = fs.value
                    import json
                    request_data = json.loads(json_data)
                else:
                    WebFileUploadHelper.append_stream(fs.filename, fs.file)
    return request_data
