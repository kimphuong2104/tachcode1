#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import copy
import datetime

from cdb import cmsg, misc, ue
from cdb.typeconversion import to_user_repr_date_format
from cs.documents import Document
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal
from webob.exc import HTTPInternalServerError, HTTPNotFound

from cs.pcs.helpers import get_and_check_object
from cs.pcs.msp.import_results import DiffType
from cs.pcs.msp.misc import KeyObject
from cs.pcs.msp.web.imports.main import IMPORT_RESULT_APP_NAME
from cs.pcs.projects import Project
from cs.pcs.projects.helpers import is_cdbpc


class ImportResultApp(JsonAPI):
    pass


@Internal.mount(app=ImportResultApp, path=IMPORT_RESULT_APP_NAME)
def _mount_app():
    return ImportResultApp()


def get_import_result(request):
    return get_internal(request).child(IMPORT_RESULT_APP_NAME)


def is_date(val):
    return isinstance(val, (datetime.datetime, datetime.date))


def to_locale_date(date):
    return to_user_repr_date_format(date)


def format_date_time(diff):
    for k, v in diff.items():
        if is_date(v):
            diff[k] = to_locale_date(v)
        elif isinstance(v, dict):
            format_date_time(v)


def copy_diffs(diffs):
    copied_diff = copy.deepcopy(diffs)
    format_date_time(copied_diff)
    return copied_diff


class ImportResultModel:
    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters

        # check access rights and existence for given Id's Project
        untrusted_cdb_project_id = extra_parameters.get("cdb_project_id")
        untrusted_ce_baseline_id = extra_parameters.get("ce_baseline_id", "")
        kwargs = {
            "cdb_project_id": untrusted_cdb_project_id,
            "ce_baseline_id": untrusted_ce_baseline_id,
        }
        project = get_and_check_object(Project, "read", **kwargs)
        if project is None:
            # if no project was returned either doc does not exists
            # or access rights are not given
            raise HTTPNotFound
        # now the id can be trusted
        self.project = project
        self.cdb_project_id = self.project.cdb_project_id
        self.ce_baseline_id = self.project.ce_baseline_id

        # check access rights and existence for given keys' Document
        untrusted_z_nummer = extra_parameters.get("z_nummer")
        untrusted_z_index = extra_parameters.get("z_index", "")
        kwargs = {"z_nummer": untrusted_z_nummer, "z_index": untrusted_z_index}
        doc = get_and_check_object(Document, "read", **kwargs)
        if doc is None:
            # if no doc was returned either doc does not exists
            # #or access rights are not given
            raise HTTPNotFound
        # now the keys can be trusted
        self.z_nummer = doc.z_nummer
        self.z_index = doc.z_index

        self.called_from_officelink = (
            extra_parameters.get("called_from_officelink") == "True"
        )

    def get_title(self, diff_object, title_format, attrs):
        # CAUTION:
        # Original percent characters in the 'title_format' parameter must be escaped before.
        # E.g. '20% (%s - %s)' -> '20%% (%s - %s)'
        if isinstance(diff_object.pcs_object, dict):
            _values = [(diff_object.pcs_object.get(attr, "") or "") for attr in attrs]
        else:
            _values = [
                (getattr(diff_object.pcs_object, attr, "") or "") for attr in attrs
            ]
        values = []
        for val in _values:
            values.append(to_locale_date(val) if is_date(val) else val)
        return title_format % tuple(values)

    def MakeURLWithoutObj(self, class_name, rest_name, search_cond, rest_order):
        """Creates a cdb URL without instantiating the object it refers to"""
        if is_cdbpc():
            url = cmsg.Cdbcmsg(class_name, "CDB_ShowObject", 0)
            for key in list(search_cond):
                url.add_item(key, class_name, search_cond[key])
            string = url.cdbwin_url()
            return string
        return f'/info/{rest_name}/{"@".join([search_cond[r] for r in rest_order])}'

    def jsonable_dict(self, diff_object, tasks=None):
        url = ""
        if diff_object.classname == "cdbpcs_project":
            title = self.get_title(
                diff_object,
                "%s (%s - %s)",
                ["project_name", "start_time_fcast", "end_time_fcast"],
            )
            if "cdb_project_id" in diff_object.pcs_object:
                url = self.MakeURLWithoutObj(
                    "cdbpcs_project",
                    "project",
                    {
                        "cdb_project_id": diff_object.pcs_object.cdb_project_id,
                        "ce_baseline_id": diff_object.pcs_object.ce_baseline_id,
                    },
                    ["cdb_project_id", "ce_baseline_id"],
                )
        elif diff_object.classname == "cdbpcs_task":
            title = self.get_title(
                diff_object,
                "%s (%s - %s)",
                ["task_name", "start_time_fcast", "end_time_fcast"],
            )
            if (
                "cdb_project_id" in diff_object.pcs_object
                and "task_id" in diff_object.pcs_object
            ):
                try:
                    url = self.MakeURLWithoutObj(
                        "cdbpcs_task",
                        "project_task",
                        {
                            "cdb_project_id": diff_object.pcs_object.cdb_project_id,
                            "task_id": diff_object.pcs_object.task_id,
                            "ce_baseline_id": diff_object.pcs_object.ce_baseline_id,
                        },
                        ["cdb_project_id", "task_id", "ce_baseline_id"],
                    )
                except AttributeError:
                    url = ""
        elif diff_object.classname == "cdbpcs_taskrel":
            title_format = "%s+%s"
            # workaround to see a descriptive task link name in the import preview
            task_name = getattr(
                diff_object.pcs_object, "task_id2", None
            ) or diff_object.pcs_object.get("task_id2")
            if task_name:
                if task_name.startswith("@"):
                    task_name = task_name[1:]
                else:
                    cdb_project_id2 = getattr(
                        diff_object.pcs_object, "cdb_project_id2", None
                    ) or diff_object.pcs_object.get("cdb_project_id2")
                    from cs.pcs.projects.tasks import Task

                    task = Task.ByKeys(
                        cdb_project_id=cdb_project_id2,
                        task_id=task_name,
                        ce_baseline_id=self.ce_baseline_id,
                    )
                    if task:
                        task_name = task.task_name
                    else:
                        task = tasks[
                            KeyObject(cdb_project_id=cdb_project_id2, task_id=task_name)
                        ]
                        task_name = task.pcs_object["task_name"]
            if task_name:
                task_name = task_name.replace("%", "%%")
                title_format = f"{task_name} {title_format}"
            title = self.get_title(
                diff_object, title_format, ["rel_type", "minimal_gap"]
            )
        elif diff_object.classname == "cdbpcs_checklist":
            title = self.get_title(diff_object, "%s", ["checklist_name"])
            if (
                "cdb_project_id" in diff_object.pcs_object
                and "checklist_id" in diff_object.pcs_object
            ):
                cdb_project_id = getattr(
                    diff_object.pcs_object, "cdb_project_id", None
                ) or diff_object.pcs_object.get("cdb_project_id")
                checklist_id = getattr(
                    diff_object.pcs_object, "checklist_id", None
                ) or diff_object.pcs_object.get("checklist_id")
                url = self.MakeURLWithoutObj(
                    "cdbpcs_checklist",
                    "checklist",
                    {
                        "cdb_project_id": cdb_project_id,
                        "checklist_id": str(checklist_id),
                    },
                    ["cdb_project_id", "checklist_id"],
                )
        elif diff_object.classname == "cdbwf_process":
            title = self.get_title(diff_object, "%s", ["title"])
            if "cdb_process_id" in diff_object.pcs_object:
                cdb_process_id = getattr(
                    diff_object.pcs_object, "cdb_process_id", None
                ) or diff_object.pcs_object.get("cdb_process_id")
                url = self.MakeURLWithoutObj(
                    "cdbwf_process",
                    "workflow",
                    {"cdb_process_id": cdb_process_id},
                    ["cdb_process_id"],
                )
        references = {}
        for ref_type, refs in diff_object.references.items():
            references[ref_type] = [
                self.jsonable_dict(ref_diff_object, tasks)
                for ref_diff_object in refs.values()
            ]
        return {
            "diff_type": diff_object.diff_type,
            "classname": diff_object.classname,
            "icon_name": diff_object.icon_name,
            "title": title,
            "hyperlink": url,
            "diffs": copy_diffs(diff_object.diffs),
            "references": references,
            "exceptions": diff_object.exceptions,
        }

    def get_hide_import_preview(self, result):
        def no_tasks_added():
            return not bool(result.tasks.added)

        def only_system_attributes_changed():
            return result.only_system_attributes and all(result.only_system_attributes)

        def no_tasks_deleted():
            return not bool(result.tasks.deleted)

        return (
            only_system_attributes_changed() and no_tasks_added() and no_tasks_deleted()
        )

    def get_result(self, request, dry_run):
        doc_keys = {"z_nummer": self.z_nummer, "z_index": self.z_index}
        result = self.project.XML_IMPORT_CLASS.import_project_from_xml(
            self.project, doc_keys, dry_run, self.called_from_officelink
        )

        data = {}
        data["project"] = self.jsonable_dict(result.project)

        data["tasks"] = []
        for diff_object in result.tasks.all.values():
            data["tasks"].append(self.jsonable_dict(diff_object, result.tasks.all))

        total = (
            1
            + len(result.tasks.excepted)
            + len(result.tasks.added)
            + result.num_old_tasks
        )
        num_excepted = (1 if len(result.project.exceptions) else 0) + len(
            result.tasks.excepted
        )
        num_modified = (
            1 if (result.project.diff_type == DiffType.MODIFIED) else 0
        ) + len(result.tasks.modified)
        data["info"] = {
            "dryRun": (1 if dry_run else 0),
            "exceptedPercentage": num_excepted * 100.0 / total,
            "exceptedCount": num_excepted,
            "deletedPercentage": len(result.tasks.deleted) * 100.0 / total,
            "deletedCount": len(result.tasks.deleted),
            "addedPercentage": len(result.tasks.added) * 100.0 / total,
            "addedCount": len(result.tasks.added),
            "modifiedPercentage": num_modified * 100.0 / total,
            "modifiedCount": num_modified,
            "hideImportPreview": self.get_hide_import_preview(result),
        }
        return data


@ImportResultApp.path(path="/", model=ImportResultModel)
def get_model(extra_parameters):
    return ImportResultModel(extra_parameters)


@ImportResultApp.json(model=ImportResultModel)
def result_get(model, request):
    try:
        return model.get_result(request, True)
    except Exception as ex:
        misc.log_traceback("")
        raise HTTPInternalServerError(
            f"{ex if isinstance(ex, ue.Exception) else repr(ex)}"
        ) from ex


@ImportResultApp.json(model=ImportResultModel, request_method="POST")
def result_post(model, request):
    try:
        return model.get_result(request, False)
    except Exception as ex:
        misc.log_traceback("")
        raise HTTPInternalServerError(
            f"{ex if isinstance(ex, ue.Exception) else repr(ex)}"
        ) from ex
