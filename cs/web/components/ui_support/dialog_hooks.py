# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This module implements the infrastructure for calling dialog hooks
implemented in the backend.
"""

from __future__ import absolute_import
import six
import logging
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from . import App
from .configuration import WebUIDialogHookFunction
from cdb import constants, ElementsError, misc, sqlapi, tools, typeconversion, ue, util
from cdb.platform.mom import SimpleArgument
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.mom.operations import OperationInfo, OperationStateInfo
from cs.platform.web.rest.generic import convert
from cdbwrapc import Operation

LOGGER = logging.getLogger(__name__)
__all__ = []


class WizardProgress(object):
    """
    Class that provides the wizard progress data for backend dialog hooks.
    """

    BUTTON_NEXT_LABEL = "web.base.dialog.button.next"
    STEP_KIND_OPTIONAL = -1
    STEP_KIND_NORMAL = 0

    def __init__(self, data):
        self.data = data

    def get_data(self, request=None, classname=None):
        """
        Returns a dictionary that contains the wizard progress information.
        If request is set, create backend links for the dialog names.
        {'steps': [
                    {'dialog_name', 'mask_one',
                     'label':'test.mask_one',
                     'tooltip':'test.mask_one_tooltip',
                     'dialog_link', '...'},
                    {'...'}
                  ],
                  'position' : 0,
                  'button_label': hook.BUTTON_NEXT_LABEL}
        """
        from .forms import FormInfoClassDef, FormInfoSimple
        if 'steps' in self.data:
            if not classname and request.body and request.json:
                op_state = request.json.get("operation_state", None)
                if op_state:
                    classname = op_state.get('classname')
            for step in self.data['steps']:
                if 'dialog_link' not in step and 'dialog_name' in step and step['dialog_name']:
                    if classname:
                        formInfoClassDef = FormInfoClassDef(step['dialog_name'], CDBClassDef(classname))
                        step['dialog_link'] = request.link(formInfoClassDef)
                    else:
                        formInfoSimple = FormInfoSimple(step['dialog_name'])
                        step['dialog_link'] = request.link(formInfoSimple)
        return self.data

    def append_step(self, label, tooltip=None, dialog_name=None, button_label=None, kind=STEP_KIND_NORMAL):
        """
        Add a step to the wizard progress.
        """
        step = {'label': label if label else '',
                'tooltip': tooltip if tooltip else '',
                'kind': kind,
                'dialog_name': dialog_name,
                'button_label': button_label if button_label else None}
        if 'steps' in self.data:
            self.data['steps'].append(step)
        else:
            self.data['steps'] = [step]
        if 'position' not in self.data:
            self.data['position'] = 0

    def change_step(self, pos, label, tooltip=None, kind=None):
        """
        Change the data of the wizard progress step at position 'pos'.
        """
        if 'steps' in self.data and len(self.data['steps']) - 1 > pos:
            self.data['steps'][pos]['label'] = label
            if tooltip:
                self.data['steps'][pos]['tooltip'] = tooltip
            if kind:
                self.data['steps'][pos]['kind'] = kind

    def change_current_step(self, label, tooltip=None, kind=None):
        """
        Change the data of the current wizard progress step.
        """
        if 'position' in self.data:
            pos = self.data['position']
        self.change_step(pos, label, tooltip, kind)

    def append_optional_step(self, tooltip=None, dialog_name=None):
        """
        Add an optional step to the wizard progress.
        """
        self.append_step('', tooltip, dialog_name, None, self.STEP_KIND_OPTIONAL)

    def activate_mask(self, dialog_name):
        """
        Set the active mask in wizard progress.
        """
        if 'steps' in self.data:
            steps = self.data['steps']
            for step in steps:
                if 'dialog_name' in step and step['dialog_name'] == dialog_name:
                    step['kind'] = self.STEP_KIND_NORMAL

    def set_button_label(self, label):
        """
        Set the button name to label.
        """
        self.data['button_label'] = label

    def remove_button_label(self):
        """
        Set the button name to the default.
        """
        if 'button_label' in self.data:
            self.data.pop('button_label')


class DialogHook(object):
    """
    Class that provides the context to implement dialog hooks
    that are part of the backend.
    """
    def __init__(self):
        """
        Construction of the hook. This is usually done by the system.
        """
        self._new_values = {}
        self._dlg_ro = {}
        self._dlg_mandatory = {}
        self._request_json = {}
        self._request = None
        self._errors = []
        self._dialog = None
        self._next_dialog_link_data = None
        self._wizard_progress = None
        self._opstate = None
        self._current_hook_name = None

    def set_request(self, request):
        """
        Sets the request that is e.g. used to generate links.
        """
        self._request = request
        if request is not None:
            try:
                self._request_json = request.json
            except ValueError:
                # A GET request without query parameter
                # would raise ValueError at that moment
                # the "json" get accessed
                self._request_json = {}

    def _get_opstate(self):
        if self._opstate is None and self._request_json:
            self._opstate = self._request_json.get("operation_state", None)
        return self._opstate

    def get_hooks(self):
        """
        Returns a list of type `WebUIDialogHookFunction` that
        contains the hooks to be called with the actual request.
        """
        return [WebUIDialogHookFunction.get_config(hook_id)
                for hook_id in self._request_json.get("ids")]

    def current_hook_name(self, name):
        self._current_hook_name = name

    def get_operation(self):
        """
        Retrieve the `cdbwrapc.Operation` object this hook works with.
        The call is quite expensive so you should try to avoid to call
        this function if possible.
        """
        op_state = self._get_opstate()
        if op_state:
            return Operation(op_state)
        return None

    def get_operation_state_info(self):
        """
        Returns the `cdb.platform.mom.operations.OperationStateInfo` object
        for the operation the hook works with. You can use this object to
        get further information about the operation context.
        """
        op_state = self._get_opstate()
        if op_state:
            return OperationStateInfo(op_state)
        return None

    def get_operation_name(self):
        """
        Returns the operation name for the operation the hook works with.
        """
        osi = self.get_operation_state_info()
        if osi:
            return osi.get_operation_name()
        return ""

    def _to_python_rep(self, values):
        """
        Converts the JSON representation of the values dictionary to
        typed values.
        """
        try:
            result = {}
            for k, v in six.iteritems(values):
                if v is not None and self.get_fieldtype(k) == sqlapi.SQL_DATE:
                    # Convert the date - all other types are ok
                    if v == '':
                        v = None
                    else:
                        v = convert.load_datetime(v)
                result[k] = v
            return result
        except convert.LoadConversionError as e:
            # load_datetime may raise LoadConversionError, we raise an
            # ElementsError to get a correct JSON response payload
            raise ElementsError(str(e))

    def get_changed_fields(self):
        """
        Returns a map of fields that have changed with the identifier as key
        and the new value as value.
        """
        return self._to_python_rep(self._request_json.get("changes", {}))

    def get_new_values(self):
        """
        Returns a dictionary that contains the actual values of the dialog.
        """
        return self._to_python_rep(self._request_json.get("new_values"))

    def get_new_value(self, name):
        """
        Returns the typed value of the field `name` which should be the
        attribute identifier. Using the attribute name is also supported but
        less performant. Raises a `KeyError` if name is not accessible
        """
        vals = self.get_new_values()
        try:
            return vals[name]
        except KeyError as ke:
            # Try the identifier
            cdef = self._get_cldef()
            if cdef:
                id = cdef.getAttrIdentifier(name)
                return vals[id]
            raise ke

    def get_new_object_value(self, name):
        """
        Like `get_new_value` but if `name` is not part of the
        new values and the operation works on an object the value
        is retrieved from that object.
        """
        try:
            return self.get_new_value(name)
        except KeyError as ke:
            oi = self.get_operation_state_info()
            objs = oi.get_objects()
            if objs:
                obj = objs[0]
                return obj[name]
            raise ke

    def set(self, name, value):
        """
        Set the value of the field identified by `name`
        to the JSON representation of `value`.
        """
        self._new_values[name] = convert.dump_value(value)

    def _change_editability(self, fieldname, edit_val):
        if isinstance(fieldname, list):
            for fname in fieldname:
                self._dlg_ro[fname] = edit_val
        else:
            self._dlg_ro[fieldname] = edit_val

    def set_readonly(self, fieldname):
        """
        Prevents the field specified in `fieldname` from being
        edited on the display mask. `fieldname` can be a string
        or a list of strings.
        """
        self._change_editability(fieldname, 1)

    def set_writeable(self, fieldname):
        """
        Allows the field specified in `fieldname` to be edited on the display
        mask. `fieldname` can be a string
        or a list of strings.
        """
        self._change_editability(fieldname, 0)

    def _change_mandatory(self, fieldname, new_val):
        if isinstance(fieldname, list):
            for fname in fieldname:
                self._dlg_mandatory[fname] = new_val
        else:
            self._dlg_mandatory[fieldname] = new_val

    def set_mandatory(self, fieldname):
        """
        Turns the field specified in `fieldname` into a mandatory
        field on the display mask. `fieldname` can be a string
        or a list of strings.
        """
        self._change_mandatory(fieldname, True)

    def set_optional(self, fieldname):
        """
        Turns the field specified in `fieldname` into an optional field
        on the display mask. `fieldname` can be a string
        or a list of strings.
        """
        self._change_mandatory(fieldname, False)

    def get_fieldtype(self, fieldname):
        """
        Returns the type of the attribute `fieldname` that is used
        in the UI. Usually this is the type defined in the data dictionary.
        The most common types are ``sqlapi.SQL_CHAR``, ``sqlapi.SQL_INTEGER``,
        ``sqlapi.SQL_FLOAT`` and ``sqlapi.SQL_DATE``.
        If the type could not be determined the function returns ``-1``.
        """
        result = -1
        type_info = None
        operation_state = self._get_opstate()
        if operation_state:
            type_info = operation_state.get("json_field_types")
            if type_info:
                result = type_info.get(fieldname, -1)
                if result == -1 and '.' not in fieldname:
                    # Non qualified name
                    for k, t in six.iteritems(type_info):
                        if k.split(".")[-1] == fieldname:
                            result = t
                            break
        if result == -1:
            # No UI-Info use DD
            cdef = self._get_cldef()
            if cdef:
                adef = cdef.getAttributeDefinition(fieldname)
                if adef:
                    id = adef.getIdentifier()
                    result = adef.getSQLType()
                    if id != fieldname and type_info:
                        # prefer UI info if there is one for the id
                        result = type_info.get(id, result)
        return result

    def apply_dlg_changes(self, changes):
        """
        Set the changes you got by calling `Operation.get_dialog_changes`.
        """
        for change in changes:
            if "new_readonly" in change:
                self._change_editability(change["id"],
                                         change["new_readonly"])
            elif "new_mandatory" in change:
                self._change_mandatory(change["id"],
                                       change["new_mandatory"])
            elif "new_value" in change:
                # get_dialog_changes returns legacy values
                # If this is a date we have to convert the value
                val = change["new_value"]
                ft = self.get_fieldtype(change["id"])
                if ft != -1:
                    val = typeconversion.to_python_rep(ft, val)
                self.set(change["id"], val)
            elif "catalog_values" in change:
                for id, val in change["catalog_values"]:
                    ft = self.get_fieldtype(id)
                    if ft != -1:
                        val = typeconversion.to_python_rep(ft, val)
                    self.set(id, val)

    def set_error(self, title, message):
        """ Adds an error message to be displayed in the frontend
        """
        self._errors.append({"title": title, "message": message})

    def set_dialog(self, dialog):
        """
        Sets a dialog to be shown in the frontend

        :param dialog: The dialog to be displayed
        :type dialog: :py:class:`cs.web.components.ui_support.frontend_dialog.FrontendDialog`
        """
        self._dialog = dialog
        self._dialog.set_hook_name(self._current_hook_name)

    def set_next_dialog(self, dialog_name, classname=None):
        """
        Sets a dialog to replace the current dialog in the frontend.

        If `classname` is not ``None``, the dialog is replaced by a dialog from
        the |elements| dialog configuration in the context of the given class.

        If `classname` is ``None``, the operation state of the hook is used to get the
        specific class. If the class can not be determined, a dialog without the
        context of a specific class is used.
        """
        from .forms import FormInfoClassDef, FormInfoSimple
        if classname is None:
            classname = self._get_classname()
        formInfo = None
        if classname:
            formInfo = FormInfoClassDef(dialog_name,
                                        CDBClassDef(classname))
        else:
            formInfo = FormInfoSimple(dialog_name)
        # We need the operation to be informed about the new dialog
        formInfo.set_use_operation_state()
        self._next_dialog_link_data = {
            "link": self._request.link(formInfo),
            "dialog_name": dialog_name}

    def get_wizard_progress(self):
        if self._wizard_progress is None:
            self._wizard_progress = WizardProgress(self._request_json.get("wizard_progress", {}))
        return self._wizard_progress

    def set_wizard_progress(self, wizard_progress):
        self._wizard_progress = wizard_progress

    def _get_classname(self):
        opInfo = self.get_operation_state_info()
        if opInfo:
            return opInfo.get_classname()
        return ""

    def _get_cldef(self):
        cname = self._get_classname()
        if cname:
            return CDBClassDef(cname)
        return None


class DialogHookPreDisplay(DialogHook):
    """
    A dialog hook that is called to manipulate values before they are sent
    to the frontend. At this time the hook only supports setting values and wizard progess data.
    """
    def __init__(self, hook, values, wizard_progress, opstate):
        """
        Get the context object for `hook` which is a `WebUIDialogHook` object
        or just a string that contains the hooks name.
        `values` is a dictionary that contains the actual values.
        `type_dict` is dictionary that contains the types of the actual form.
        """
        super(DialogHookPreDisplay, self).__init__()
        self._opstate = opstate
        if values:
            self.actual_values = {key: convert.dump_value(value) for key, value in six.iteritems(values)}
        else:
            self.actual_values = {}
        self._wizard_progress = WizardProgress(wizard_progress)
        if isinstance(hook, six.string_types):
            self.hook_name = hook
        else:
            self.hook_name = hook.hook_name

    def get_new_values(self):
        """
        Returns a dictionary that contains the actual values of the dialog.
        """
        return self._to_python_rep(self.actual_values)

    def perform(self):
        """
        Executes the configured callable and returns the values set during
        the execution in the JSON Format of the values.
        """
        cfg = WebUIDialogHookFunction.get_config(self.hook_name)
        f = tools.load_callable(cfg.function_name)
        try:
            f(self)
        except ue.Exception as e:
            title = util.Labels()["web.hook_ue_exception_notification"] + ": %s" % self.hook_name
            self.set_error(title, misc.unescape_string(six.text_type(e)))
        classname = None
        op_state = self._get_opstate()
        if op_state:
            classname = op_state.get("classname")
        return {'new_values': self._new_values,
                'wizard_progress': self.get_wizard_progress().get_data(self._request, classname),
                'readonly_changes': self._dlg_ro,
                'mandatory_changes': self._dlg_mandatory}


@App.path(path="form/hook", model=DialogHook)
def dialog_hook_path():
    return DialogHook()


@App.json(model=DialogHook, request_method='POST')
def get_dialog_hook_changes(self, request):
    # NOTE: this function is not invoked, when running ::PRE_DISPLAY:: dialog hooks.
    # Features added here must also be added to forms.py:FormInfoBase._call_pre_display_hook
    try:
        self.set_request(request)
        hooks = self.get_hooks()
        for hook in hooks:
            f = tools.load_callable(hook.function_name)
            self.current_hook_name(hook.hook_name)
            try:
                f(self)
            except ue.Exception as e:
                title = util.Labels()["web.hook_ue_exception_notification"] + ": %s" % hook.hook_name
                self.set_error(title, misc.unescape_string(six.text_type(e)))

        changes = {
            "new_values": self._new_values,
            "ro_changes": self._dlg_ro,
            "mandatory_changes": self._dlg_mandatory,
            "errors": self._errors,
            "dialog": None if self._dialog is None else self._dialog.to_json(),
            "next_dialog_link_data": self._next_dialog_link_data,
            "wizard_progress": self.get_wizard_progress().get_data(request),
        }
        if hasattr(self, "_from_cdb_classification_hook"):
            changes["from_cdb_classification_hook"] = self._from_cdb_classification_hook
        return changes
    except ElementsError as e:
        LOGGER.exception(e)
        @request.after
        def set_status(response):
            response.status_code = 403


def __emulate_maskaction(hook, is_button):
    op = hook.get_operation()
    if op:
        values = []
        for k, v in six.iteritems(hook.get_new_values()):
            values.append(SimpleArgument(k,
                                         typeconversion.to_untyped_c_api(v)))
        if is_button:
            barg = SimpleArgument(constants.kArgumentDialogButtonPressed, 1)
            values.append(barg)
        for changed_field in list(hook.get_changed_fields()):
            try:
                changes = op.getDialogChanges(changed_field, values)
                hook.apply_dlg_changes(changes)
            except ElementsError as e:
                hook.set_error("", six.text_type(e))


def emulate_maskaction_ue(hook):
    """
    This backend hook function emulates the
    behaviour of the windows client. An operation is constructed and usually
    an user exit of kind ``dialogitem_change`` is called.
    """
    __emulate_maskaction(hook, False)


def emulate_button_ue(hook):
    """
    This backend hook function emulates the
    behaviour of the windows client. An operation is constructed and usually
    an user exit of kind ``button_pressed`` is called.
    """
    __emulate_maskaction(hook, True)


def handle_predicate_masks(hook):
    """
    A dialog hook injected automatically to handle predicate masks.
    """

    def getMask(osi):
        classname = osi.get_classname()
        oi = OperationInfo(classname, osi.get_operation_name())
        if oi:
            mask = oi.get_mask_name_webui()
            if not mask:
                mask = oi.get_mask_name()
            return mask
        return None

    osi = hook.get_operation_state_info()
    if osi.get_predicate_mask_flag():
        mask = getMask(osi)
        wizard_progress = hook.get_wizard_progress()
        if isinstance(hook, DialogHookPreDisplay):
            # We have to set the wizard info later
            wizard_progress.append_step(
                util.get_label("web.predmask_wizard"),
                util.get_label("web.predmask_wizard_tooltip"))
            wizard_progress.append_optional_step(
                util.get_label("web.predmask_wizard_moredata_tooltip"), mask)
        else:
            # We have to call get_dialog again
            actual_registers = osi.get_predicate_mask_registers()
            classname = osi.get_classname()
            if mask:
                # Check if there are any new registers
                cdef = CDBClassDef(classname)
                d = cdef.get_dialog(mask, hook.get_new_values())
                if d:
                    regs = [r["mask_name"] for r in d.get("registers", [])]
                    new_regs = [reg for reg in regs if reg not in actual_registers]
                    if new_regs:
                        wizard_progress.activate_mask(mask)
