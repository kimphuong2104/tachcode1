# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST backend for cs.workflow.forms, mounted @ /internal/cs-workflow-forms
"""

import webob
from cdb.objects import ByID
from cs.platform.web import JsonAPI
from cs.platform.web.rest.support import rest_key
from cs.platform.web.root import Internal
from cs.workflow.forms import transform_data
from cs.workflow.tasks import Task
from cs.workflow.webforms.main import MOUNTEDPATH
from cs.workflow.processes import Process
from cs.workflow.briefcases import Briefcase
from cs.workflow.systemtasks import InfoMessage

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


class TaskFormsModel(object):
    def __init__(self, object_id):
        obj = ByID(object_id)
        if obj and obj.CheckAccess("read"):
            if (isinstance(obj, (Task, InfoMessage))):
                self.task = obj
                self.indexed_forms = self._get_indexed_forms()
            elif (isinstance(obj, Process)):
                self.process = obj
                self.indexed_forms = self._get_indexed_all_forms()
            else:
                raise webob.exc.HTTPNotFound
        else:
            raise webob.exc.HTTPNotFound

    def _get_indexed_forms(self):
        """
        index task's form objects by iotype and form_object_id
        """
        return {
            "edit": {f.cdb_object_id: f for f in self.task.EditForms},
            "info": {f.cdb_object_id: f for f in self.task.InfoForms},
        }

    def _get_indexed_all_forms(self):
        """
        index all task's form objects by iotype and form_object_id
        """
        editForms = []
        infoForms = []
        for task in self.process.AllTasks:
            editForms.append(task.EditForms)
            infoForms.append(task.InfoForms)
        return {
            "edit": {f.cdb_object_id: f for f in [item for sublist in editForms for item in sublist]},
            "info": {f.cdb_object_id: f for f in [item for sublist in infoForms for item in sublist]},
        }

    def _read_data(self, form):
        dialog_name = form.Masks[0].name
        form_rest_key = rest_key(form)
        bcase_list = []
        for bcase in Briefcase.ByContent(form.cdb_object_id):
            bcase_list.append(bcase.GetDescription())
        bcase_name = ", ".join(bcase_list)
        return {
            "cdb_object_id": form.cdb_object_id,
            "system:navigation_id": form_rest_key,
            "system:classname": "cdbwf_form",
            "name": "{0} - {1}".format(bcase_name, form.GetDescription()),
            "dialog_name": dialog_name,
            "data": transform_data(
                form.preset_data(),
                # pylint: disable=protected-access
                form._get_date_attrs(),
                include_prefix=True,
            ),
        }

    def getFormsData(self, forms):
        """
        return forms indexed by mode (info/edit)

        if parameter forms is given, only include forms matching the contained
        cdb_object_ids
        """
        result = {
            "info": [self._read_data(f)
                     for f in self.indexed_forms["info"].values()],
            "edit": [self._read_data(f)
                     for f in self.indexed_forms["edit"].values()]
        }
        if forms:
            result = {
                "info": [f for f in result["info"]
                         if f["cdb_object_id"] in forms],
                "edit": [f for f in result["edit"]
                         if f["cdb_object_id"] in forms],
            }
        return result


class App(JsonAPI):
    pass


@Internal.mount(app=App, path=MOUNTEDPATH)
def _mount_app():
    return App()


@App.path(path="{task_object_id}", model=TaskFormsModel)
def _get_model(task_object_id):
    return TaskFormsModel(task_object_id)


@App.json(model=TaskFormsModel)
def get_forms_data(model, request):
    forms = request.params.getall("forms")
    if forms:
        forms = set(forms)
    return model.getFormsData(forms)
