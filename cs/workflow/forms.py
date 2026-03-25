#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
"""
Workflow Forms

"""

import datetime
import isodate
import json

from cdb import util
from cdb.classbody import classbody
from cdb.constants import kOperationCopy
from cdb.objects import ByID
from cdb.objects import Forward
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects.operations import operation
from cdb.platform import FolderContent  # @UnusedImport
from cdb.typeconversion import from_legacy_date_format
from cdb.typeconversion import to_python_rep

from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import BriefcaseContent

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

fFormTemplate = Forward("{}.FormTemplate".format(__name__))
fForm = Forward("{}.Form".format(__name__))
fMask = Forward("cdb.platform.gui.Mask")
fProcess = Forward("cs.workflow.processes.Process")
fTask = Forward("cs.workflow.tasks.Task")
fBriefcase = Forward("cs.workflow.briefcases.Briefcase")
fBriefcaseLink = Forward("cs.workflow.briefcases.BriefcaseLink")
fFolderContent = Forward("cdb.platform.FolderContent")

CDB_ARGUMENT = "cdb::argument"
DATE_ITEMTYPE = 20
FORM_BLACKLIST = set(["cdb_object_id"])


def str2date(datestr):
    """
    :param datestr: The date string (either in legacy CDB or ISO format)
    :type datestr: basestring

    :returns: The parsed date object
    :rtype: datetime.datetime or datetime.date
    """
    try:
        return from_legacy_date_format(datestr)
    except ValueError:
        try:
            return isodate.parse_datetime(datestr)
        except isodate.ISO8601Error:
            return isodate.parse_date(datestr)


def transform_key(key, include_prefix=False):
    """
    Returns transformed key:

    If include_prefix is True and no prefix is detected in key, prepend it with
    "." for dialog usage.

    If include_prefix is False, drop detected prefixes from key for object
    usage.

    Always keep ``cdb::argument`` prefix.
    """
    try:
        prefix, attr = key.split(".", 1)
        if prefix == CDB_ARGUMENT:
            return key  # return cdb::argument.attr
        else:
            return key if include_prefix else attr
    except ValueError:
        return ".{}".format(key) if include_prefix else key


def transform_data(data, date_attrs, include_prefix=False):
    """
    Returns a dict with transformed keys (see``tranform_key`` for details)
    and transformed values (all values of ``date_attrs`` are converted to ISO
    strings).

    Keys in `FORM_BLACKLIST` are dropped (by default only "cdb_object_id").
    """

    def transform_value(key, value):
        if key in date_attrs and not value is None and isinstance(
                value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        return value

    result = {}

    for k, v in data.items():
        if k not in FORM_BLACKLIST:
            raw_key = transform_key(k, False)
            key = transform_key(k, include_prefix)
            result[key] = transform_value(raw_key, v)

    return result


# FIXME not tested, as this is to become a public API of the platform (E043077)
def obj2dict(obj):
    """
    Returns a dictionary that contains the object's data as a
    dictionary that is suitable to be returned using JSON.
    """
    from cdbwrapc import CDBObjectHandle
    from cdbwrapc import is_cdb_pq
    from cs.platform.web.rest.generic.convert import dump
    cdef = obj.GetClassDef()
    data = {}
    for adef in cdef.getAttributeDefs():
        name = adef.getName()
        if adef.is_text():
            if isinstance(obj, CDBObjectHandle):
                data[name] = obj[name]
            else:
                data[name] = obj.GetText(name)
        else:
            sqltype = adef.getSQLType()
            if is_cdb_pq(sqltype):
                if isinstance(obj, CDBObjectHandle):
                    data[name] = obj[name]
                else:
                    # cdb.objects.Object cannot handle pq - we have to provide
                    # both attributes (name and name_pq)
                    for sqlname in adef.getSQLSelectNames():
                        try:
                            data[sqlname] = to_python_rep(adef.getSQLType(),
                                                          obj[sqlname])
                        except KeyError:
                            # If the pq is missing this is no problem at all
                            pass
            else:
                data[name] = to_python_rep(adef.getSQLType(), obj[name])

    return dump(data, cdef)


class FormTemplate(Object):
    __maps_to__ = "cdbwf_form_template"
    __classname__ = "cdbwf_form_template"

    Masks = Reference_N(fMask, fMask.name == fFormTemplate.mask_name)
    Forms = Reference_N(
        fForm, fForm.form_template_id == fFormTemplate.cdb_object_id)


class Form(Object, BriefcaseContent):
    __maps_to__ = "cdbwf_form"
    __classname__ = "cdbwf_form"
    __content_attr__ = "cdbwf_form_contents_txt"

    Template = ReferenceMethods_1(
        fFormTemplate,
        lambda self: ByID(self.form_template_id)
    )
    Masks = ReferenceMethods_N(fMask, lambda self: self.Template.Masks)
    Process = Reference_1(fProcess, fForm.cdb_process_id)

    @property
    def Data(self):
        return self.GetText(self.__content_attr__)

    event_map = {
        (("create", "copy"), "pre_mask"): "assert_parent",
    }

    def get_masks_attributes(self):
        return [
            attr for mask in self.Masks for attr in mask.Attributes
        ]

    def get_masks_attribute_names(self):
        return set([attr.attribut for attr in self.get_masks_attributes()])

    def filter_mask_attributes(self, data):
        masks_attributes = self.get_masks_attribute_names()
        return {
            k: v for k, v in data.items() if k in masks_attributes
        }

    def assert_parent(self, ctx):
        # No creation of tasks out of a process context
        if not ctx.parent.get_attribute_names():
            raise util.ErrorMessage("cdbwf_create_form_from_wf")

    def _get_date_attrs(self):
        "raises AttributeError if self.Template is None"
        result = set()
        for a in self.get_masks_attributes():
            if a.itemtyp == DATE_ITEMTYPE:
                result.add(a.attribut)
        return result

    def read_data(self, convert_dates=False):
        """
        :param convert_dates: If ``True``, values of mask attributes
            configured as dates are converted from ISO strings to ``date`` or
            ``datetime`` objects. Defaults to ``False``.
        :type convert_dates: bool

        :returns: Persisted form data.
        :rtype: dict
        """
        data = self.Data
        if data:
            result = self.filter_mask_attributes(json.loads(data))
            if convert_dates:
                for date_attr in self._get_date_attrs():
                    value = result.get(date_attr)
                    if value:
                        result[date_attr] = str2date(value)
            return result

        return {}

    def write_data(self, json_data):
        """
        Persist given ``json_data``, which must be a JSON-serializable dict.

        Raises a ValueError if json_data is not a dict.
        Raises a TypeError if json_data is not JSON-serializable.
        """
        if isinstance(json_data, dict):
            json_data = self.filter_mask_attributes(
                transform_data(json_data, self._get_date_attrs())
            )
            try:
                json_data = json.dumps(json_data)
            except TypeError:
                raise TypeError("need a JSON-serializable dictionary")
        else:
            raise ValueError("need a dictionary")

        self.SetText(self.__content_attr__, json_data)

    def preset_data(self):
        """
        Presets form data using all non-form objects in the same briefcase.
        Already present data is not overwritten.

        Caller is responsible for checking access, especially if the briefcase
        is an edit briefcase.

        .. warning ::
            Attributes in ``FORM_BLACKLIST`` are always
            ignored when presetting data. By default, the set only contains
            ``"cdb_object_id"``.
        """
        for briefcase in fBriefcase.ByContent(self):
            data = {}

            for content in briefcase.getContent():
                if not isinstance(content, Form):
                    obj_data = obj2dict(content)
                    data.update({
                        transform_key(k, False): v
                        for k, v in obj_data.items()
                        if k not in FORM_BLACKLIST
                    })

            data.update({
                k: v
                for k, v in self.read_data().items()
                if v != None
            })

            self.write_data(data)
            return data

        return self.read_data()

    def get_empty_mandatory_fields(self):
        """
        Returns a set of all mandatory field names containing NULL values.
        """
        data = self.read_data()
        mandatory = set()

        for m in self.Masks:
            for a in m.MandatoryAttributes():
                mandatory.add(a.attribut)

        return [a for a in mandatory if data.get(a, None) in [None,""]]

    def _get_form_counter(self):
        briefcases = fBriefcase.Query(
            "cdb_process_id='{}' AND name LIKE '{}%%'".format(
                self.cdb_process_id, self.joined_template_name))

        return len(briefcases) + 1

    @classmethod
    def InitializeForm(cls, task, form_template):
        """
        1. Initializes a form using FormTemplate object ``form_template``
        2. Creates a new local briefcase for given Task object ``task`` named
           like the form template
        3. Adds the form to the briefcase's contents
        4. Returns the new form
        """
        keys = {
            "cdb_process_id": task.cdb_process_id,
            "form_template_id": form_template.cdb_object_id,
        }

        form = cls.Create(**keys)

        briefcase = fBriefcase.Create(
            briefcase_id=fBriefcase.new_briefcase_id(),
            cdb_process_id=keys["cdb_process_id"],
            name="{} {}".format(form.joined_template_name,
                                form._get_form_counter()),
        )
        fBriefcaseLink.Create(
            cdb_process_id=keys["cdb_process_id"],
            task_id=task.task_id,
            briefcase_id=briefcase.briefcase_id,
            iotype=1,
            extends_rights=0,
        )
        fFolderContent.Create(cdb_folder_id=briefcase.cdb_object_id,
                              cdb_content_id=form.cdb_object_id)
        return form

    def on_cdbwf_submit_form_pre_mask(self, ctx):
        data = self.preset_data()

        for k, v in data.items():
            ctx.set(k, v)

        # support partially pre-filling forms in new or template wfs
        if (self.Process.isTemplate() or
            self.Process.status == self.Process.NEW.status
        ):
            ctx.set_optional(ctx.dialog.get_attribute_names())


    def on_cdbwf_submit_form_now(self, ctx):
        if not self.CheckAccess("save"):
            raise util.ErrorMessage(
                "authorization_fail",
                "cdbwf_submit_form",
                "cdbwf_form",
                "save",
            )

        dialog = {k: ctx.dialog[k] for k in ctx.dialog.get_attribute_names()}
        self.write_data(dialog)


class TaskWithForm(object):
    def _getForms(self, iotype):
        result = [x for x in self.getContent(iotype) if isinstance(x, Form)]
        if self.Process:
            result += [x for x in self.Process.getContent(iotype)
                       if isinstance(x, Form)]
        return result

    AllForms = ReferenceMethods_N(fForm, lambda self: self._getForms("all"))
    InfoForms = ReferenceMethods_N(fForm, lambda self: self._getForms("info"))
    EditForms = ReferenceMethods_N(fForm, lambda self: self._getForms("edit"))

    def preset_data(self):
        for form in self.AllForms:
            form.preset_data()

    def check_form_data(self):
        empty = []
        prefix = "\n- "

        for form in self.EditForms:
            empty_fields = form.get_empty_mandatory_fields()

            if empty_fields:
                empty.append("{}{}: {}".format(
                    prefix,
                    form.joined_template_name,
                    ", ".join(empty_fields)))

        if empty:
            raise util.ErrorMessage(
                "cdbwf_task_mandatory_fields", prefix.join(empty))

    def on_cdbwf_add_task_form_now(self, ctx):
        template_id = getattr(ctx.dialog, "form_template_id", None)
        success = False

        if template_id:
            template = ByID(template_id)
            if template:
                Form.InitializeForm(self, template)
                success = True

        if not success:
            raise util.ErrorMessage("cdbwf_form_template_missing", template_id)


@classbody
class FolderContent(object):
    def copy_briefcase_contents(self, new_briefcase):
        "replace references to template process's forms with copies"
        folder_obj = ByID(self.cdb_folder_id)
        content_obj = ByID(self.cdb_content_id)
        new_content_vals = {
            "cdb_folder_id": new_briefcase.cdb_object_id,
        }

        if (
            folder_obj and isinstance(folder_obj, Briefcase)
            and content_obj and isinstance(content_obj, Form)
        ):
            # also copy form, not only the reference
            with util.SkipAccessCheck(folder_obj.Process.cdb_object_id):
                new_form = operation(
                    kOperationCopy,
                    content_obj,
                    cdb_process_id=new_briefcase.cdb_process_id,
                )

            new_content_vals["cdb_content_id"] = new_form.cdb_object_id

        self.Copy(**new_content_vals)
