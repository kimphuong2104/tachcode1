#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from collections import OrderedDict
import logging
import cdbwrapc

from webob.exc import HTTPBadRequest, HTTPNotFound

from cdb.constants import kOperationDelete
from cdb.constants import kOperationNew
from cdb.objects import ByID
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cdb.platform.olc import StatusInfo
from cdb.platform import FolderContent
from cs.platform.web.rest.app import get_collection_app
from cs.platform.web.rest.classdef.main import get_classdef
from cs.platform.web.rest.support import get_restlink, get_value_dict
from cs.platform.web.root import Internal
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

from cs.workflow.forms import Form
from cs.workflow.systemtasks import InfoMessage
from cs.workflow.tasks_plugin import PLUGIN

MOUNT = "{}/briefcases".format(PLUGIN)


class BriefcasesApp(BaseApp):
    pass


class BriefcasesModel(object):
    def __init__(self, cdb_object_id):
        # self.task might also be an InfoMessage object
        obj = ByID(cdb_object_id)

        if not (obj and obj.CheckAccess("read")):
            raise HTTPNotFound()

        if isinstance(obj, InfoMessage):
            self.task = obj.Task

            if not (self.task and self.task.CheckAccess("read")):
                raise HTTPNotFound()
        else:
            self.task = obj

    def _get_status_attr(self, obj):
        wf_info = obj.GetClassDef().get_workflow_info()
        if wf_info:
            return wf_info['attr_status']
        else:
            return None

    def get_view(self, obj, request, app):
        if isinstance(obj, CDB_File):
            classdef_app = get_classdef(request)
            file_classdef = obj.GetClassDef()
            view = get_value_dict(file_classdef, obj.cdb_object_id)
            view.update({
                "@id": get_restlink(obj, request),
                "@type": request.view(file_classdef, app=classdef_app)["@id"],
                "system:description": obj.GetDescription(),
                "system:icon_link": obj.GetObjectIcon(),
                "system:ui_link": get_restlink(obj, request),
            })
            return view

        view = request.view(obj, app=app)
        status_attr = self._get_status_attr(obj)
        status = getattr(obj, status_attr, None) if status_attr else None
        if status != None:
            info = StatusInfo(obj.ToObjectHandle().getOLC(), status)
            label = info.getLabel()
            color = info.getCSSColor()
            view["status"] = {
                "status": status,
                "color": color,
                "label": label
            }
        return view

    def _get_briefcases(self, request):
        collection_app = get_collection_app(request)

        briefcases = OrderedDict()
        objects = {}
        seen = {}

        for mode in ["info", "edit"]:
            for obj in [self.task.Process, self.task]:  # global and local briefcases
                for b in obj.getBriefcases(mode):
                    if b.cdb_object_id not in list(seen) and b.CheckAccess("read"):
                        contents = [
                            self.get_view(x, request, collection_app)
                            for x in b.Content
                            if not isinstance(x, Form) and x.CheckAccess("read")
                        ]
                        objects.update({c["cdb_object_id"]: c for c in contents})

                        briefcase_object = request.view(b, app=collection_app)
                        briefcase_object["mode"] = mode
                        briefcase_id = briefcase_object["@id"]
                        briefcases[b.cdb_object_id] = {
                            "@id": briefcase_id,
                            "references": [x["@id"] for x in contents]
                        }
                        objects[briefcase_id] = briefcase_object

                        seen[b.cdb_object_id] = None

        return briefcases, list(objects.values())

    def get_data(self, request):
        briefcases, objects = self._get_briefcases(request)
        return {
            "briefcases": briefcases,
            "objects": objects,
        }


class FolderContentModel(object):
    def __init__(self, cdb_folder_id):
        self.cdb_folder_id = cdb_folder_id

    def _run_operation(self, opname, context, **kwargs):
        try:
            operation(opname, context, **kwargs)
        except Exception as error:
            logging.exception(str(error))
            raise error

    def create_foldercontent(self, cdb_content_ids):
        for cdb_content_id in cdb_content_ids:
            self._run_operation(
                kOperationNew,
                FolderContent,
                cdb_folder_id=self.cdb_folder_id,
                cdb_content_id=cdb_content_id,
            )

    def delete_foldercontent(self, cdb_content_id):
        content = FolderContent.ByKeys(
            cdb_folder_id=self.cdb_folder_id,
            cdb_content_id=cdb_content_id,
        )
        if content:
            self._run_operation(
                kOperationDelete,
                content,
            )


class RestlinkModel(object):

    def get_restlink(self, cmsg):
        op = cdbwrapc.createOperationFromCMSGUrl(cmsg)
        handle = op.getObjectResult()
        obj = ByID(handle.getUUID())
        return get_restlink(obj)


@Internal.mount(app=BriefcasesApp, path=MOUNT)
def _mount_app():
    return BriefcasesApp()


@BriefcasesApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@BriefcasesApp.path(path="{cdb_object_id}", model=BriefcasesModel)
def _get_model(cdb_object_id):
    return BriefcasesModel(cdb_object_id)


@BriefcasesApp.json(model=BriefcasesModel)
def get_data(model, request):
    return model.get_data(request)


@BriefcasesApp.path(path="folder_content/{cdb_folder_id}",
                    model=FolderContentModel)
def _folder_content(request, cdb_folder_id):
    return FolderContentModel(cdb_folder_id)


def _get_json_payload(request, key):
    payload = request.json.get(key, None)

    if payload is None:
        logging.error("request missing key '%s': %s", key, request.json)
        raise HTTPBadRequest

    return payload

@BriefcasesApp.json(model=FolderContentModel, request_method="POST")
def create_folder_content(model, request):
    cdb_content_ids = _get_json_payload(request, "cdb_content_ids")
    return model.create_foldercontent(cdb_content_ids)


@BriefcasesApp.json(model=FolderContentModel, name="detach", request_method="POST")
def detach_folder_content(model, request):
    cdb_content_id = _get_json_payload(request, "cdb_content_id")
    return model.delete_foldercontent(cdb_content_id)


@BriefcasesApp.path(path="fetch_restlink", model=RestlinkModel)
def _restlink(request):
    return RestlinkModel()

@BriefcasesApp.json(model=RestlinkModel, request_method="POST")
def fetch_restlink(model, request):
    cmsg = _get_json_payload(request, "cmsg")
    return model.get_restlink(cmsg)
