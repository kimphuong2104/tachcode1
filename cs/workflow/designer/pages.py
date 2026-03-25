# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module cs.workflow.designer.pages
"""

import json
import logging
import collections
import datetime

from cdb import elink
from cdb import sqlapi
from cdb import transaction
from cdb import util
from cdb.objects.operations import operation
from cdb.objects.operations import form_input

from cs.workflow.forms import Form
from cs.workflow.processes import Process
from cs.workflow.tasks import Task
from cs.workflow.tasks import SystemTask
from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import BriefcaseLink
from cs.workflow.briefcases import IOType
from cs.workflow.constraints import Constraint
from cs.workflow.pyrules import RuleWrapper
from cs.workflow.schemacomponents import SchemaComponent
from cs.workflow.designer import json_data
from cs.workflow.designer import nanoroute
from cs.workflow.designer import router
from cs.workflow.designer import wfinterface

# load parameter extensions for standard system task types
from cs.workflow.designer import parameter_extension  # @UnusedImport

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class DesignerPage(elink.Template):
    __template__ = "index.html"

    def render(self, context, cdb_process_id=""):
        app_url = self.application.getURLPaths()["approot"]
        return {
            "app_url": "{}app/{}".format(app_url, cdb_process_id),
            "template_url": "{}templates/".format(app_url),
            "resposible_roles_url": "{}get_roles".format(app_url),
            "responsible_catalog_url": "{}responsibles".format(app_url),
            "form_template_catalog_url": "{}form_templates".format(app_url),
            "operation_catalog_url": "{}operations".format(app_url),
            "constraints_catalog_url": "{}constraints".format(app_url),
            "filters_catalog_url": "{}filters".format(app_url),
            "conditions_catalog_url": "{}conditions".format(app_url),
            "project_catalog_url": "{}projects".format(app_url),
            "worfklow_template_catalog_url": "{}workflow_templates".format(app_url),
            "cdb_process_id": cdb_process_id,
            "extension_resources": router.handle_request(
                self,
                ["extension_resources"]
            )["resources"],
            "task_title_placeholder": util.get_label(
                "cdbwf_task_title_placeholder"
            ),
        }


class DataProviderBase(elink.VirtualPathTemplate):
    __text__ = "${result}"

    def _render(self, req):
        self.content_type("application/json")
        super(DataProviderBase, self)._render(req)

    def make_link(self, path=None):
        if path is None:
            path = []
        if isinstance(path, str):
            path = path.split("/")
        paths = list(map(str, path + [""]))
        return "{}process/{}".format(
            self.application.getURLPaths()["approot"],
            "/".join(paths)
        )

    def get_form_data(self, keyname, default=None):
        from collections.abc import Iterable
        form_data = getattr(self.request, 'form_data', {}).copy()
        result = form_data.get(keyname, default)
        if isinstance(result, str):
            return result
        elif isinstance(result, Iterable):
            return [url for url in result]
        return result

class AppData(DataProviderBase):
    def render(self, context, **varkw):
        vpath = self.get_path_segments(cleanup=True)
        cdb_process_id = vpath[0] if vpath else ""
        result = json_data.get_app_data(self, cdb_process_id)
        return {"result": json.dumps(result)}


class ProcessData(DataProviderBase):
    def render(self, context, **varkw):
        vpath = self.get_path_segments(cleanup=True)
        result = None
        try:
            result = router.handle_request(self, vpath)
        except Exception as e:
            result = str(e)
        return {"result": result}


class TemplateProvider(elink.VirtualPathTemplate):
    __cache_expires__ = 365  # days
    __task_types_obvt__ = 'templates/new_task_menu.obvt'

    def _add_caching_headers(self, req):
        "clients may cache .obvt resources"
        cache_limit = self.__cache_expires__
        if req.path == self.__task_types_obvt__:
            cache_limit = 1  # task types cached for one day
        req.add_extra_header(
            "Cache-Control",
            "public, max-age={}".format(
                cache_limit * 86400  # days -> seconds
            ),
        )
        expires = datetime.date.today() + datetime.timedelta(
            days=cache_limit,
        )
        req.add_extra_header(
            "Expires",
            expires.strftime("%a, %d %b %Y 00:00:00 GMT"),
        )
        req.add_extra_header("Pragma", "")

    def _render(self, req):
        # Let the template files be registered somewhere using router.
        # Then the template for "parameter" block of system tasks can be
        # customized.
        segs = self.get_path_segments(cleanup=True)
        self.__template__ = segs[0]
        # force using "templates" segment to avoid conflict with json handler
        # maybe redundant
        segs = ["templates"] + segs
        self._router_handled = router.handle_request(self, segs)
        # if the handler returns also the template file location, take it
        if isinstance(self._router_handled, tuple):
            # add the path to template loader
            self.application.addEngineCustomTemplatePath(
                self._router_handled[0])
            self.__template__ = self._router_handled[1]
            self._router_handled = self._router_handled[2]
        if self._router_handled is None:
            self._router_handled = {}
        self._add_caching_headers(req)
        super(TemplateProvider, self)._render(req)

    def render(self, context):
        return self._router_handled


def _get_attr_label(cls, attr):
    clsdef = cls._getClassDef()
    return str(clsdef.getAttributeDefinition(attr).getLabel())


# =======================
# handle template request
# =======================
@router.resource("templates/main.obvt")
def render_main(page):
    return {
        "label_title": _get_attr_label(Process, "title"),
        "label_project": _get_attr_label(Process, "cdb_project_id"),
    }


@router.resource("templates/new_task_menu.obvt")
def render_new_task_menu(page):
    return wfinterface.get_possible_task_types()


@router.resource("templates/task_fields.obvt")
def render_task_fields(self):
    return {
        "deadline_label": _get_attr_label(Task, "deadline"),
        "status_label": _get_attr_label(Task, "joined_status_name"),
        "finish_option_label": _get_attr_label(Task, "finish_option"),
        "max_duration_label": _get_attr_label(Task, "max_duration"),
    }


@router.resource("templates/systemtask_fields.obvt")
def render_systemtask_fields(self):
    return {
        "uses_global_maps_label": _get_attr_label(
            SystemTask,
            "uses_global_maps",
        ),
    }


@router.resource("templates/constraints.obvt")
def render_constraints(self):
    return {
        "icon": Constraint.GetClassIcon(),
        "label": str(Constraint._getClassDef().getDesignation()),
    }


@router.resource("templates/constraint.obvt")
def render_constraint(self):
    return {
        "label_invert": _get_attr_label(Constraint, "invert_rule"),
    }


@router.resource("templates/forms.obvt")
def render_forms(self):
    return {
        "icon": Form.GetClassIcon(),
        "label": str(Form._getClassDef().getTitle()),
    }


@router.resource("templates/briefcase_links.obvt")
def render_briefcase_links(self):
    return {
        "icon": Briefcase.GetClassIcon(),
        "label": str(BriefcaseLink._getClassDef().getDesignation()),
    }


@router.resource("templates/parallel.obvt")
def render_parallel(self):
    return {
        "constraint_icon": Constraint.GetClassIcon(),
    }


@router.resource("templates/task.obvt")
def render_task(self):
    finish_option_label = _get_attr_label(Task, "finish_option")
    uses_global_maps_label = _get_attr_label(SystemTask, "uses_global_maps")
    return {
        "constraint_icon": Constraint.GetClassIcon(),
        "briefcase_icon": Briefcase.GetClassIcon(),
        "finish_option_label": finish_option_label,
        "uses_global_maps_label": uses_global_maps_label,
    }


@router.resource("templates/description.obvt")
def render_description(self):
    return {
        "label_description": _get_attr_label(Process, "description"),
    }


@router.resource("templates/briefcase_link_meanings.obvt")
def render_briefcase_link_meanings(self):
    return {
        "label_meaning": _get_attr_label(BriefcaseLink, "iotype"),
        "meanings": IOType,
    }


@router.resource("templates/parameters.obvt")
def render_parameters(self):
    from cs.workflow.tasks import FilterParameter
    return {
        "default_label": str(
            FilterParameter._getClassDef().getDesignation()
        ),
    }


@router.json(":cdb_process_id/allowed_operations")
def allowed_operations(page, cdb_process_id):
    try:
        positions = ["loop", "before", "after", "parallel"]
        result = []
        process = Process.ByKeys(cdb_process_id)
        if process:
            selection = page.get_form_data("selection", [])
            if not isinstance(selection, list):
                selection = [selection]
            result = process.AllowedOperationsForSelection(selection)
        return {k: k in result for k in positions}
    except:
        logging.exception("cannot determine allowed operations")


@router.json(":cdb_process_id/create_task")
def create_task(page, cdb_process_id):
    data = nanoroute.posted_json(page.request)
    ttype = data.get("ttype")
    if ttype is None:
        return []
    process = Process.ByKeys(cdb_process_id)
    if not process:
        return []
    selection = data.get('selection', [])
    where = data.get("where")
    title = data.get("title", "")
    textension = data.get("extension", "")
    tdef = data.get("task_definition", None)
    parameters = data.get("parameters", None)
    additional = data.get("additional", None)
    defargs = {}
    if tdef:
        defargs["task_definition_id"] = tdef
    if textension:
        defargs["cdb_extension_class"] = textension
    if parameters:
        defargs["parameters"] = parameters
    if additional:
        defargs["additional"] = additional
    if selection:
        process.AppendTaskToSelection(
            where,
            selection,
            ttype,
            title,
            **defargs
        )
    elif where == "completion":
        # add task into completion group
        process.ProcessCompletion.CreateTask(ttype, title, **defargs)
    else:
        process.CreateTask(ttype, title, **defargs)
    return [json_data.get_component_data(page, process)]


@router.json(":cdb_process_id/create_cycle")
def create_cycle(page, cdb_process_id):
    data = nanoroute.posted_json(page.request)
    process = Process.ByKeys(cdb_process_id)
    if not process:
        return []
    selection = data.get('selection', [])
    if selection:
        process.ReplaceSelectionWithCycle(
            selection
        )
    return [json_data.get_component_data(page, process)]


@router.json(":cdb_process_id/remove_task")
def remove_task(page, cdb_process_id):
    data = nanoroute.posted_json(page.request)
    process = Process.ByKeys(cdb_process_id)
    if not process:
        return []
    task_id = data
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return []

    task.DeleteTask()
    return [json_data.get_component_data(page, process)]


@router.json(":cdb_process_id/modify")
def modify_process(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    if not process:
        return None
    attr = page.get_form_data("attribute", None)
    value = page.get_form_data("value", None)
    result = {}
    if attr and attr in process:
        process.ModifyProcess(**dict([(attr, value)]))
        result[attr] = process[attr]
    return result


@router.json(":cdb_process_id/start")
def start_process(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    if process:
        try:
            process.ActivateProcess()
        except RuntimeError as e:
            # Should be an ue.Exception, but is a RuntimeError
            return {"message": "%s" % str(e)}
    return {"success": 1}


@router.json(":cdb_process_id/hold")
def hold_process(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    if process:
        try:
            process.OnHoldProcess()
        except Exception as e:
            return {"message": "%s" % str(e)}
    return {"success": 1}


@router.json(":cdb_process_id/cancel")
def cancel_process(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    if process:
        try:
            process.CancelProcess()
        except RuntimeError as e:
            return {"message": "%s" % str(e)}
    return {"success": 1}


@router.json(":cdb_process_id/dismiss")
def dismiss_process(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    if process:
        try:
            process.DismissProcess()
        except RuntimeError as e:
            return {"message": "%s" % str(e)}
    return {"success": 1}


@router.json(":cdb_process_id/tasks/:task_id/modify")
def modify_task(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    attr = page.get_form_data("attribute", None)
    value = page.get_form_data("value", None)
    result = {}
    if attr and attr in task:
        task.ModifyTask(**dict([(attr, value)]))
        result[attr] = task[attr] if task[attr] != None else ""
    if "deadline" in result:
        result["deadline"] = json_data._get_deadline(task)
    return result


@router.json(":cdb_process_id/tasks/:task_id/get_responsible")
def get_responsible(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    return json_data.get_responsible_info(page, task)


@router.json(":cdb_process_id/tasks/:task_id/add_form")
def add_form(page, cdb_process_id, task_id):
    form_template_id = page.get_form_data("form_template_id", "")
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    operation(
        "cdbwf_add_task_form",
        task,
        form_input(task, form_template_id=form_template_id)
    )
    return {
        "task_local_briefcases": json_data.get_briefcase_links(page, task),
        "sidebar_local_briefcases": json_data.get_local_briefcases(
            page,
            task.Process
        ),
    }


@router.json(":cdb_process_id/tasks/:task_id/set_responsible")
def set_responsible(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    subject_id = page.get_form_data("subject_id", "")
    subject_type = page.get_form_data("subject_type", "")
    if not (subject_id and subject_type) and task.status != Task.NEW.status:
        raise util.ErrorMessage("cdbwf_err115")
    task.ModifyTask(subject_id=subject_id, subject_type=subject_type)
    return json_data.get_responsible_info(page, task)


@router.json(":cdb_process_id/create_global_briefcase")
def create_global_briefcase(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    data = nanoroute.posted_json(page.request)
    briefcase = process.CreateBriefcase(data['name'])
    briefcase.SetGlobalMeaning(data['meaning'])
    return json_data.get_global_briefcases(page, process)


@router.json(":cdb_process_id/global_briefcases/:briefcase_id/modify")
@router.json(":cdb_process_id/local_briefcases/:briefcase_id/modify")
def modify_briefcase(page, cdb_process_id, briefcase_id):
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    attr = page.get_form_data("attribute", None)
    value = page.get_form_data("value", None)
    result = {}
    if attr and attr in briefcase:
        briefcase.ModifyBriefcase(**dict([(attr, value)]))
        result[attr] = briefcase[attr]
    return result


@router.json(":cdb_process_id/global_briefcases/:briefcase_id/setmeaning")
def set_global_briefcase_meaning(page, cdb_process_id, briefcase_id):
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    value = page.get_form_data("value", None)

    try:
        link = briefcase.SetGlobalMeaning(value)
    except util.ErrorMessage:
        raise util.ErrorMessage("cdbwf_operation_allowed")

    return {
        "iotype": link.iotype,
        "meaning": IOType(link.iotype).name,
        "icon": link.GetObjectIcon(),
    }


@router.json(":cdb_process_id/global_briefcases/:briefcase_id/delete")
def delete_global_briefcase(page, cdb_process_id, briefcase_id):
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    for blink in briefcase.Links:
        blink.DeleteBriefcaseLink()

    briefcase.DeleteBriefcase()
    process = Process.ByKeys(cdb_process_id)
    return json_data.get_global_briefcases(page, process)


@router.json(":cdb_process_id/create_local_briefcase")
def create_local_briefcase(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    data = nanoroute.posted_json(page.request)
    process.CreateBriefcase(data['name'])
    return json_data.get_local_briefcases(page, process)


@router.json(":cdb_process_id/local_briefcases/:briefcase_id/delete")
def delete_local_briefcase(page, cdb_process_id, briefcase_id):
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    briefcase.DeleteBriefcase()
    process = Process.ByKeys(cdb_process_id)
    return json_data.get_local_briefcases(page, process)


def add_contents_to_briefcase(page, briefcase):
    def add_links(url):
        if url.startswith("cdb://"):
            briefcase.AddObjectFromCmsg(url)
        else:
            briefcase.AddObjectFromLink(url)

    cmsgs = page.get_form_data("cmsgs[]", "")

    if isinstance(cmsgs, str):
        # single link
        add_links(cmsgs)
    else:
        # multiple links
        for cmsg in cmsgs:
            add_links(cmsg)


@router.json(":cdb_process_id/global_briefcases/:briefcase_id/add_content")
def add_content_to_global_briefcase(page, cdb_process_id, briefcase_id):
    process = Process.ByKeys(cdb_process_id)
    # for global briefcase we need return the link for iotype and icon
    bcl = process.BriefcaseLinks.KeywordQuery(briefcase_id=briefcase_id)[0]
    add_contents_to_briefcase(page, bcl.Briefcase)
    return json_data.get_global_briefcase(page, bcl)


@router.json(":cdb_process_id/global_briefcases/:briefcase_id/delete_content")
def delete_global_briefcase_content(page, cdb_process_id, briefcase_id):
    process = Process.ByKeys(cdb_process_id)
    # for global briefcase we need return the link for iotype and icon
    bcl = process.BriefcaseLinks.KeywordQuery(briefcase_id=briefcase_id)[0]
    briefcase = bcl.Briefcase
    content_object_id = page.get_form_data("content_object_id", "")
    briefcase.RemoveObject(content_object_id)
    return json_data.get_global_briefcase(page, bcl)


@router.json(":cdb_process_id/local_briefcases/:briefcase_id/add_content")
def add_content_to_local_briefcase(page, cdb_process_id, briefcase_id):
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    add_contents_to_briefcase(page, briefcase)
    return json_data.get_local_briefcase(page, briefcase)


@router.json(":cdb_process_id/local_briefcases/:briefcase_id/delete_content")
def delete_local_briefcase_content(page, cdb_process_id, briefcase_id):
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    content_object_id = page.get_form_data("content_object_id", "")
    briefcase.RemoveObject(content_object_id)
    return json_data.get_local_briefcase(page, briefcase)


@router.json(":cdb_process_id/tasks/:task_id/add_constraint")
def add_constraint(page, cdb_process_id, task_id):
    component = SchemaComponent.ByKeys(
        cdb_process_id=cdb_process_id,
        task_id=task_id
    )
    if not component:
        return None
    rule_name = page.get_form_data("constraint", "")
    if not rule_name:
        return None
    component.AddConstraint(rule_name)
    # Constraint can be added: can also be modified
    return json_data.get_constraints(page, component, readonly=False)


@router.json(":cdb_process_id/tasks/:task_id/constraints/"
             ":constraint_object_id/modify")
def modify_constraint(page, cdb_process_id, task_id, constraint_object_id):
    constraint = Constraint.ByKeys(constraint_object_id)
    if not constraint:
        return None
    attr = page.get_form_data("attribute", None)
    value = page.get_form_data("value", None)
    if attr and attr in constraint:
        constraint.ModifyConstraint(**dict([(attr, value)]))
    return json_data.get_constraint_data(page, constraint, readonly=False)


@router.json(":cdb_process_id/tasks/:task_id/constraints/"
             ":constraint_object_id/delete")
def delete_constraint(page, cdb_process_id, task_id, constraint_object_id):
    constraint = Constraint.ByKeys(constraint_object_id)
    if constraint:
        constraint.DeleteConstraint()
    task = SchemaComponent.ByKeys(
        cdb_process_id=cdb_process_id,
        task_id=task_id
    )
    # Constraint can be deleted: can also be modified
    return json_data.get_constraints(page, task, readonly=False)


@router.json(":cdb_process_id/tasks/:task_id/link_briefcase")
def link_briefcase(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    briefcase_id = page.get_form_data("briefcase_id", "")
    if not briefcase_id:
        return None
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    briefcase.SetTaskMeaning(IOType(0).name, task, False)
    return json_data.get_briefcase_links(page, task)


@router.json(":cdb_process_id/tasks/:task_id/briefcaselinks/"
             ":briefcase_id/delete")
def delete_briefcase_link(page, cdb_process_id, task_id, briefcase_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    briefcase.RemoveTaskMeaning(task)
    return json_data.get_briefcase_links(page, task)


@router.json(":cdb_process_id/tasks/:task_id/briefcaselinks/"
             ":briefcase_id/modify")
def modify_briefcase_link(page, cdb_process_id, task_id, briefcase_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    attr = page.get_form_data("attribute", None)
    briefcase = Briefcase.ByKeys(
        cdb_process_id=cdb_process_id,
        briefcase_id=briefcase_id
    )
    if not task or not attr or not briefcase:
        return None
    value = page.get_form_data("value", None)
    brlink = briefcase.ChangeTaskMeaning(task, **dict([(attr, value)]))
    return json_data.get_briefcase_link(page, brlink)


@router.json(":cdb_process_id/tasks/:task_id/modify_parameter")
def modify_parameter(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    defid = task.Definition.name
    # looks handler up
    handler = router.handle_request(page, ["parameter_extensions", defid])
    if handler is not None and "setter" in handler:
        handler["setter"](page, task)
    return json_data.get_parameters(page, task, readonly=False)


@router.json(":cdb_process_id/tasks/:task_id/delete_parameter")
def delete_parameter(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    defid = task.Definition.name
    handler = router.handle_request(page, ["parameter_extensions", defid])
    if handler is not None and "deleter" in handler:
        handler["deleter"](page, task)
    else:
        for parameter in task.AllParameters:
            parameter.DeleteParameter()
    return json_data.get_parameters(page, task, readonly=False)


@router.json(":cdb_process_id/set_project")
def set_project(page, cdb_process_id):
    process = Process.ByKeys(cdb_process_id)
    if not process:
        return None
    pcs_installed = wfinterface._is_pcs_enabled()
    if not pcs_installed:
        return None
    cdb_project_id = page.get_form_data("cdb_project_id", None)
    if cdb_project_id is None:
        return None
    process.ModifyProcess(cdb_project_id=cdb_project_id)
    return json_data.get_project_data(page, process)


@router.json(":cdb_process_id/tasks/:task_id/modify_extension")
def modify_extension(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return None
    extension_object = task.getExtensionObject()
    extension_name = extension_object.getDesignerExtensionName()
    handler = router.handle_request(page, ["task_extension", extension_name])
    if handler is not None and "setter" in handler:
        task.ModifyTask(**handler["setter"](page, extension_object))
    return json_data.get_task_extension(page, task, readonly=False)


def add_condition(page, task, condition):
    rule_name = page.get_form_data(condition, "")
    position = page.get_form_data("position", "01")
    if not rule_name:
        return False
    args = {}
    args[condition] = position
    conditions = task.AllParameters.KeywordQuery(name=condition,
                                                 order_by="value DESC")
    if conditions:
        args[condition] = "%02d" % (int(conditions[0].value) + 1)
    task.AddParameters(rule_name=rule_name,
                       **args)
    return True


@router.json(":cdb_process_id/tasks/:task_id/success_condition")
def add_success_condition(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return False
    if add_condition(page, task, "success_condition"):
        return json_data.get_success_conditions(page, task)
    return None


@router.json(":cdb_process_id/tasks/:task_id/failure_condition")
def add_failure_condition(page, cdb_process_id, task_id):
    task = Task.ByKeys(cdb_process_id=cdb_process_id, task_id=task_id)
    if not task:
        return False
    if add_condition(page, task, "failure_condition"):
        return json_data.get_failure_conditions(page, task)
    return None


def move_condition_param(task, name, original_position, action):
    """
    "Moves" a condition up or down by swapping its value with the one of its
    next greater or smaller positioned sibling.

    :param task: The task the parameters belong to
    :type task: cs.workflow.tasks.SystemTask

    :param name: The parameters' name. Should be either "success_condition" or
        "failure_condition", but this is not enforced
    :type condition_param: str

    :param original_position: Position to be moved
    :type: str

    :param action: Denotes movement direction, either "up" or "down"
    :type: str

    :returns: The condition parameter that has been moved
    :rtype: cs.workflow.tasks.FilterParameter

    :raises: IndexError if original parameter can't be identified
    """
    original_param = task.AllParameters.KeywordQuery(
        name=name,
        value=original_position,
    )[0]

    # always make value to swap with the first result
    if action == "up":
        operator = "<="
        order_by = "value ASC"
    else:  # down
        operator = ">="
        order_by = "value DESC"

    query_stmt = (
        "name='{name}' AND "
        "value{operator}'{position}'".format(
            name=sqlapi.quote(name),
            operator=operator,
            position=sqlapi.quote(original_position),
        )
    )
    siblings = task.AllParameters.Query(
        query_stmt,
        order_by=order_by,
    )

    if len(siblings) > 1:
        new_position = siblings[0].value

        with transaction.Transaction():
            siblings[0].ModifyParameter(
                value=original_position
            )
            original_param.ModifyParameter(
                value=new_position
            )

    return original_param


def delete_condition_param(page, task, condition, rule_name, position):
    wrapper = RuleWrapper.ByName(rule_name)  # actual name in login language

    if not wrapper:
        logging.error(
            "no wrapper found for '%s'",
            rule_name
        )
        return False

    conditions = task.AllParameters.KeywordQuery(
        name=condition,
        value=position,
        rule_name=wrapper.cdb_object_id,
    )

    if not conditions:
        logging.error(
            "no parameters found for '%s', '%s', '%s'",
            condition,
            position,
            rule_name
        )
        return False

    for x in conditions:
        x.DeleteParameter()

    return True


@router.json(":cdb_process_id/tasks/:task_id/:condition/:rule_name/delete/"
             ":position")
def delete_condition(page, cdb_process_id, task_id, condition, rule_name,
                     position):
    if condition == "failure_condition":
        result_function = json_data.get_failure_conditions
    elif condition == "success_condition":
        result_function = json_data.get_success_conditions
    else:
        raise ValueError(
            "unknown condition type '{}'".format(
                condition
            )
        )

    task = Task.ByKeys(
        cdb_process_id=cdb_process_id,
        task_id=task_id
    )

    if not task:
        return False

    result = delete_condition_param(
        page,
        task,
        condition,
        rule_name,
        position
    )

    if result:
        return result_function(
            page,
            task
        )

    return None


@router.json(":cdb_process_id/tasks/:task_id/:conditions/:rule_name/"
             ":direction/:position")
def move_condition(page, cdb_process_id, task_id, conditions, rule_name,
                   direction, position):
    if conditions == "failure_conditions":
        condition = "failure_condition"
        result_function = json_data.get_failure_conditions
    elif conditions == "success_conditions":
        condition = "success_condition"
        result_function = json_data.get_success_conditions
    else:
        raise ValueError(
            "unknown condition type '{}'".format(
                conditions
            )
        )

    if direction not in ["up", "down"]:
        raise ValueError(
            "unknown direction '{}'".format(
                direction
            )
        )

    task = Task.ByKeys(
        cdb_process_id=cdb_process_id,
        task_id=task_id
    )

    if not task:
        return False

    result = move_condition_param(
        task,
        condition,
        position,
        direction
    )

    if result:
        return result_function(
            page,
            task
        )
