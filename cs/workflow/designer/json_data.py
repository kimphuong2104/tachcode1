# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import defaultdict

from cdb import sqlapi
from cdb import util
from cdb.lru_cache import lru_cache
from cdb.objects import ByID
from cdb.platform.mom import operations

from cs.workflow.forms import Form
from cs.workflow.processes import Process
from cs.workflow.protocols import Protocol
from cs.workflow.tasks import Task
from cs.workflow.tasks import SystemTask
from cs.workflow.tasks import FilterParameter
from cs.workflow.taskgroups import ParallelTaskGroup
from cs.workflow.taskgroups import SequentialTaskGroup
from cs.workflow.taskgroups import ProcessCompletionTaskGroup
from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import BriefcaseLink
from cs.workflow.briefcases import FolderContent
from cs.workflow.briefcases import IOType
from cs.workflow.constraints import Constraint
from cs.workflow.schemacomponents import SchemaComponent
from cs.workflow.designer import router
from cs.workflow.designer import urls
from cs.workflow.designer import wfinterface
from cs.workflow.designer import LOOP_TASK_ID
from cs.workflow.webforms.main import MOUNTEDPATH

from cs.workflow.misc import get_pydate_format
from cs.workflow.misc import get_state_text
from cs.workflow import misc

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

PROCESS_COMPLETION = "cdbwf_aggregate_proc_completion"
STATUS_ICON = "/resources/icons/byname/cdbwf_status/0?status={}"
BRIEFCASE_CONTENT_OPCONTEXT = "CsWorkflowDesignerBriefcaseContentsCDBPC"
EDIT_SCHEMA = "edit schema"
PATTERN_CONDITION_1 = "{}_condition"
PATTERN_CONDITION_N = "{}_conditions"


@lru_cache(maxsize=1)
def check_access_proactively_enabled():
    """
    Returns ``True`` if the Designer should check write access for objects
    before rendering. This has performance implications and is discouraged.

    If the value of personal setting ``cs.workflow.designer`` /
    ``check_access_proactively`` is ``"1"``, the access checks are made.
    Otherwise, interactive elements just assume write access is granted (it is
    checked before actually doing something anyway).
    """
    settings = util.PersonalSettings()
    settings.invalidate()
    result = settings.getValueOrDefault(
        "cs.workflow.designer",
        "check_access_proactively",
        "1"
    )
    return result == "1"


def check_access_proactively(obj, access):
    """
    Returns ``True`` if the user is granted ``access`` on ``obj``. If proactive
    access checking is disabled for the user, no access is checked and ``True``
    is returned anyway. See ``check_access_proactively_enabled`` for details.
    """
    if check_access_proactively_enabled():
        return obj.CheckAccess(access)
    return True


@lru_cache(maxsize=None)
def get_cached_briefcase_contents(page, cdb_object_id):
    obj = ByID(cdb_object_id)
    if obj and obj.CheckAccess("read"):
        return get_briefcase_contents(page, obj)
    return None


def index_list(data, indexed_by):
    result = defaultdict(list)
    for x in data:
        result[x[indexed_by]].append(x)
    return result


def load_process_data(page, cdb_process_id):
    """
    Load all process data in as few database queries as possible and return an
    indexed data structure to access data in-memory.

    .. warning ::
        Because read access is not limited in the default configuration of
        ``cs.workflow``, it is only checked for the workflow itself and
        briefcase contents, not for other related objects, including but not
        limited to tasks, constraints and forms.

    Returns a dictionary with the following keys:

    +--------------------+-------------------------------------------------------+
    | Key                | Contents                                              |
    +====================+=======================================================+
    | process            | The root ``cs.workflow.processes.Process`` object     |
    +--------------------+-------------------------------------------------------+
    | components         | "Flat" ``ObjectCollection`` of all process components |
    +--------------------+-------------------------------------------------------+
    | forms              | Dict of ``Forms`` indexed by ``task_id`` values       |
    +--------------------+-------------------------------------------------------+
    | constraints        | Dict of ``Constraints`` indexed by ``task_id``        |
    +--------------------+-------------------------------------------------------+
    | briefcases         | Dict of ``Briefcases`` indexed by ``briefcase_id``    |
    +--------------------+-------------------------------------------------------+
    | briefcase_links    | Dict of ``BriefcaseLinks`` indexed by ``task_id``     |
    +--------------------+-------------------------------------------------------+
    | briefcase_contents | Dict of ``Objects`` indexed by briefcase object IDs   |
    +--------------------+-------------------------------------------------------+
    | cycles             | Dict of ``Cycles`` indexed by ``task_id``             |
    +--------------------+-------------------------------------------------------+
    | success_conditions | Dict of ``Success Conditions`` indexed by ``task_id`` |
    +--------------------+-------------------------------------------------------+
    | failure_conditions | Dict of ``Failure Conditions`` indexed by ``task_id`` |
    +--------------------+-------------------------------------------------------+
    | max_cycles         | Number of Loops                                       |
    +--------------------+-------------------------------------------------------+
    """
    cdb_process_id = sqlapi.quote(cdb_process_id)
    process = Process.ByKeys(cdb_process_id)

    if not process or not process.CheckAccess("read"):
        return {"process": None}

    query = {"cdb_process_id": cdb_process_id}

    def _load(cls, indexed_by=None, **kwargs):
        query_args = dict(query)
        query_args.update(kwargs)
        data = cls.KeywordQuery(**query_args)
        if indexed_by:
            return index_list(data, indexed_by)
        else:
            return data

    get_cached_briefcase_contents.cache_clear()
    briefcases = _load(Briefcase)
    bc_links = _load(BriefcaseLink)
    links_by_bid = index_list(bc_links, "briefcase_id")
    bc_contents = defaultdict(list)
    forms = defaultdict(list)

    for x in FolderContent.KeywordQuery(
            cdb_folder_id=briefcases.cdb_object_id):
        content = get_cached_briefcase_contents(page, x.cdb_content_id)
        if content:
            bc_contents[x.cdb_folder_id].append(content)
            if isinstance(content, Form):
                for bc_link in links_by_bid[briefcases[x.cdb_folder_id]]:
                    forms[bc_link.task_id].append(content)

    return {
        "process": process,
        "components": _load(SchemaComponent, order_by="position"),
        "forms": forms,
        "constraints": _load(Constraint, "task_id"),
        "briefcases": {b.briefcase_id: b for b in briefcases},
        "briefcase_links": index_list(bc_links, "task_id"),
        "briefcase_contents": bc_contents,
        "cycles": _load(
            Process,
            "parent_task_object_id",
            order_by='current_cycle DESC'
        ),
        "success_conditions": _load(
            FilterParameter,
            "task_id",
            name="success_condition",
            order_by='value DESC'
        ),
        "failure_conditions": _load(
            FilterParameter,
            "task_id",
            name="failure_condition",
            order_by='value DESC'
        ),
        "max_cycles": _load(FilterParameter, "task_id", name="max_cycles")
    }


def get_process_structure(page, data):
    components = data["components"]

    # pass 1: index components by task_id
    nodes = {c.task_id: get_component_data(page, c, data) for c in components}
    # pass 2: create trees and parent-child relations
    result = {
        "main": [],
        "completion": [],
    }

    for c in components:
        node = nodes[c.task_id]
        # either make the node a new tree or link it to its parent
        if not c.parent_id:
            if c.cdb_classname == PROCESS_COMPLETION:
                forest = result["completion"]
            else:
                forest = result["main"]

            # start a new tree in the forest
            forest.append(node)
        else:
            # add new_node as child to parent
            nodes[c.parent_id]["components"].append(node)

    return result


def get_graph_data(page, data):
    process = data["process"]
    structure = get_process_structure(page, data)
    components = structure["main"]
    have_main_components = bool(components)

    # if there are no main components, we let the user add a new task
    if not have_main_components:
        components.append(make_new_task_component(page, process))

    components.append(make_process_end(page, process))

    # there _should_ always be a completion task, but we don't enforce it
    completion = structure["completion"]
    if completion and completion[0]["components"]:
        components.append(completion[0])

    # TODO: the path is double defined by router registration and here
    cdb_process_id = process.cdb_process_id
    result = {
        "iface": "cs-workflow-graph",
        "cdb_process_id": cdb_process_id,
        "components": components,
        "allowedOperationsUrl": page.make_link(
            [cdb_process_id, "allowed_operations"]
        ),
        "operationUrl": page.make_link([cdb_process_id, "create_task"]),
        "removeUrl": page.make_link([cdb_process_id, "remove_task"]),
        "cycleUrl": page.make_link([cdb_process_id, "create_cycle"]),
    }
    result.update(
        get_simple_status(
            process.status > 0,
            "cis_play"
        )
    )
    return result


def clean_text(txt):
    if txt is None:
        return ""
    return txt


def get_simple_status(completed, icon):
    statusIcon = "/static/powerscript/cs.workflow.designer/{}_{}.svg"

    if completed:
        return {
            "statusStyle": "status-completed",
            "statusIcon": statusIcon.format(icon, "success_darker"),
        }

    return {
        "statusStyle": "status-none",
        "statusIcon": statusIcon.format(icon, "gray"),
    }


def get_task_status(obj, is_process=False):
    result = {
        "statusStyle": "",
        "statusIcon": (
            "/resources/icons/byname/cdbwf_status/0?status={}".format(
                obj.status
            )
        ),
        "statusText": obj.GetStateText(obj.GetState(obj.status)),
    }

    if obj.status == obj.EXECUTION.status and not is_process:
        result["statusStyle"] = "status-execution"

    elif obj.status == obj.COMPLETED.status:
        result["statusStyle"] = "status-completed"

    elif obj.status == 30:
        if is_process:
            result["statusStyle"] = "status-failed"
        else:  # task
            result["statusStyle"] = "status-rejected"

    elif obj.status == obj.DISCARDED.status:
        result["statusStyle"] = "status-discarded"

    elif is_process:
        result.update(get_simple_status(False, "cis_ok-circle"))

    return result


def make_node(page, component, **kwargs):
    node = {
        "iface": "cs-workflow-node",
        "task_id": kwargs.get(
            "task_id",
            component.get(
                "task_id",
                "process-end"
            )
        ),
    }
    node.update(kwargs)
    node["task"] = component
    return node


def get_constraints(page, obj, readonly=False, data=None):
    # currently only task constraints
    constraints = []

    if data is None:  # use cdb.objects - slow
        obj_constraints = obj.Constraints
    else:  # use pre-fetched objects
        obj_constraints = data["constraints"].get(obj.task_id, [])

    for constraint in obj_constraints:
        constraints.append(get_constraint_data(page, constraint))

    if check_access_proactively(obj, EDIT_SCHEMA):
        add_url = page.make_link([
            obj.cdb_process_id,
            "tasks",
            obj.task_id,
            "add_constraint",
        ])
    else:
        add_url = ""

    return {
        "iface": "cs-workflow-constraints",
        "constraints": constraints,
        "addConstraintUrl": add_url,
    }


def get_constraint_data(page, constraint, readonly=False):
    rule = constraint.RuleWrapper
    result = {
        "iface": "cs-workflow-constraint",
        "rule_name": rule.name if rule else "",
        "invert_rule": constraint.invert_rule,
        "briefcase_id": clean_text(constraint.briefcase_id),
        "briefcase_name": clean_text(constraint.briefcase_name),
        "modifyUrl": "",
        "deleteUrl": "",
    }
    if not readonly:
        save_granted = check_access_proactively(constraint, "save")
        delete_granted = check_access_proactively(constraint, "delete")

        result.update({
            "modifyUrl": page.make_link([
                constraint.cdb_process_id,
                "tasks",
                constraint.task_id,
                "constraints",
                constraint.cdb_object_id,
                "modify",
            ]) if save_granted else "",
            "deleteUrl": page.make_link([
                constraint.cdb_process_id,
                "tasks",
                constraint.task_id,
                "constraints",
                constraint.cdb_object_id,
                "delete",
            ]) if delete_granted else "",
        })
    return result


def get_component_data(page, obj, data=None):
    result = None

    if isinstance(obj, Task):
        # wrap the node for layouts
        result = get_task_data(page, obj, data)
    elif isinstance(obj, ParallelTaskGroup):
        result = get_parallel_data(page, obj, data)
    elif isinstance(obj, SequentialTaskGroup):
        result = get_sequential_data(page, obj, data)
    elif isinstance(obj, ProcessCompletionTaskGroup):
        result = get_completion_data(page, obj, data)
    elif isinstance(obj, Process):
        if data is None:
            # SLOW; will reload the whole process
            # used to get results of write operations
            data = load_process_data(page, obj.cdb_process_id)
        # wrap the node for layouts
        result = get_graph_data(page, data)
    return result


def get_responsible_info(page, obj, save_granted=None):
    if save_granted is None:
        save_granted = check_access_proactively(obj, "save")

    result = {
        "iface": "cs-workflow-responsible",
        "setResponsibleUrl": page.make_link([
            obj.cdb_process_id,
            "tasks",
            obj.task_id,
            "set_responsible",
        ]) if save_granted else "",
    }
    return dict(result, **obj.GetResponsiblePersonInfo())


def get_description(page, obj, **url_dict):
    return {
        "iface": "cs-workflow-description",
        "description": obj.description if obj.description else "",
        "modifyUrl": url_dict.get("modify", ""),
    }


def _get_deadline(obj):
    return obj.deadline.strftime(get_pydate_format()) if obj.deadline else ""


def get_task_info(page, obj, **kwargs):
    task_info = {
        "modifyUrl": kwargs["modify"],
        "schemaEditable": kwargs["schemaEditable"],
    }
    if isinstance(obj, SystemTask):
        task_info.update({
            "iface": "cs-workflow-systemtask-info",
            "picture": obj.get_system_task_icon(),
            "parameters": get_parameters(
                page,
                obj,
                readonly=kwargs["readonly"],
                edit_schema_granted=kwargs["schemaEditable"]
            ),
        })
    else:
        task_info.update({
            "iface": "cs-workflow-task-info",
            "responsible": kwargs["responsible"],
            "deadline": kwargs["deadline"],
            "cdb_status_txt": kwargs["cdb_status_txt"],
        })
    return task_info


def get_task_fields(page, obj, **kwargs):
    task_fields = {
        "modifyUrl": kwargs["modify"],
        "schemaEditable": kwargs["schemaEditable"],
        "description": get_description(page, obj, modify=kwargs["modify"]),
        "loop_task": 1 if (hasattr(obj, "task_definition_id") \
                            and obj.task_definition_id == LOOP_TASK_ID) else 0
    }
    if obj.isSystemTask():
        task_fields.update({
            "iface": "cs-workflow-systemtask-fields",
            "uses_global_maps": int(bool(obj.uses_global_maps)),
        })
    else:
        task_fields.update({
            "iface": "cs-workflow-task-fields",
            "responsible": kwargs["responsible"],
            "deadline": kwargs["deadline"],
            "max_duration": obj.max_duration if obj.max_duration else "",
            "cdb_status_txt": kwargs["cdb_status_txt"],
            "has_finish_option": False,
        })
        if util.get_prop("wffo") == "true":
            task_fields.update({
                "has_finish_option": (
                    obj.isApprovalTask() or obj.isExaminationTask()
                ),
                "finish_option": int(bool(obj.finish_option)),
            })
    return task_fields


def get_parameters(page, task, readonly=False, edit_schema_granted=None):
    if not task.isSystemTask() or not task.Definition:
        return None
    defid = task.Definition.name
    handler = router.handle_request(page, ["parameter_extensions", defid])
    if handler is None:
        return {
            "iface": "cs-workflow-parameters",
            "parameters": [],
        }
    plabel = handler.get("label", "")
    plist_class = handler.get("parameter_list_class", "")
    parameters = []
    if "getter" in handler:
        parameters = handler["getter"](page, task, readonly)
    result = {
        "iface": "cs-workflow-parameters",
        "label": plabel,
        "plist_class": plist_class,
        "parameters": parameters,
        "modifyUrl": "",
        "deleteUrl": "",
    }
    if not readonly:
        if edit_schema_granted is None:
            edit_schema_granted = check_access_proactively(task, EDIT_SCHEMA)
        result.update({
            "modifyUrl": page.make_link([
                task.cdb_process_id,
                "tasks",
                task.task_id,
                "modify_parameter",
            ]) if edit_schema_granted else "",
            "deleteUrl": page.make_link([
                task.cdb_process_id,
                "tasks",
                task.task_id,
                "delete_parameter",
            ]) if edit_schema_granted else "",
        })
    return result


def get_task_extension(page, task, readonly=False, save_granted=None):
    extension_object = None
    if hasattr(task, "getExtensionObject"):
        extension_object = task.getExtensionObject()
        if extension_object:
            extension_name = extension_object.getDesignerExtensionName()
            handler = router.handle_request(
                page,
                ["task_extension", extension_name],
            )
            if handler and "getter" in handler:
                result = {
                    "iface": "cs-workflow-task-extension",
                    "title": extension_object.getExtensionAreaTitle(),
                    "icon": extension_object.getExtensionIcon(),
                }
                result.update({
                    "extension_object": handler["getter"](
                        page,
                        extension_object,
                        readonly,
                    ),
                })
                modify_url = ""
                if not readonly:
                    if save_granted is None:
                        save_granted = check_access_proactively(task, "save")
                    if save_granted:
                        modify_url = page.make_link([
                            task.cdb_process_id,
                            "tasks",
                            task.task_id,
                            "modify_extension"
                        ])
                result.update({
                    "modifyUrl": modify_url,
                    "readonly": readonly,
                })
                return result
    return None


def get_task_data(page, obj, data):
    save_granted = check_access_proactively(obj, "save")
    edit_schema_granted = check_access_proactively(obj, EDIT_SCHEMA)
    delete_granted = check_access_proactively(obj, "delete")

    shared_vals = {
        "save_granted": save_granted,
        "schemaEditable": edit_schema_granted,
        "modify": page.make_link([
            obj.cdb_process_id,
            "tasks",
            obj.task_id,
            "modify",
        ]) if save_granted else "",
        "responsible": get_responsible_info(page, obj, save_granted),
        "deadline": _get_deadline(obj),
        "cdb_status_txt": get_state_text(obj.cdb_objektart, obj.status),
    }
    if edit_schema_granted:
        shared_vals.update({"readonly": False})
    else:
        shared_vals.update({"readonly": True})
    if isinstance(obj, SystemTask):
        class_type_description = str(
            obj.Definition.GetDescription()
        )
    else:
        class_type_description = str(obj.mapped_classname)
    cycles = get_cycles(page, obj, data)
    result = {
        "iface": "cs-workflow-task",
        "components": [],
        "modifyUrl": shared_vals["modify"],
        "title": obj.title,
        "task_id": obj.task_id,
        "status": obj.status,
        "constraints": get_constraints(page, obj, data=data),
        "forms": get_task_forms(page, obj, data),
        "briefcaselinks": get_briefcase_links(page, obj, data),
        "success_conditions": get_success_conditions(page, obj, data),
        "failure_conditions": get_failure_conditions(page, obj, data),
        "cycles": cycles,
        "cycle_info": get_cycle_info(page, obj, data, cycles) if cycles else "",
        "cycle_link": cycles["current_cycle_link"] if cycles else "",
        "taskDeletable": delete_granted,
        "confirmDeletion": util.Labels()[
            "cdbwf_task_delete_confirmation"
        ].format(obj.task_id if obj.title == '' else obj.title),
        "schemaEditable": edit_schema_granted,
        "info": get_task_info(page, obj, **shared_vals),
        "fields": get_task_fields(page, obj, **shared_vals),
        "task_extension": get_task_extension(
            page,
            obj,
            save_granted=save_granted
        ),
        "icon": obj.GetObjectIcon(),
        "type_desc": class_type_description,
    }
    result.update(get_task_status(obj))

    result = make_node(page, result)
    result["id"] = obj.task_id
    return result


def get_parallel_data(page, obj, data):
    return {
        "task_id": obj.task_id,
        "components": [],
        "iface": "cs-workflow-parallel",
        "constraints": get_constraints(page, obj, data=data),
        "statusIcon": "",
        "statusStyle": "",
    }


def get_sequential_data(page, obj, data):
    return {
        "task_id": obj.task_id,
        "components": [],
        "iface": "cs-workflow-sequential",
    }


def get_completion_data(page, obj, data):
    result = get_parallel_data(page, obj, data)
    result["isCompletion"] = True
    process = None

    if data:
        process = data.get("process", None)

    result.update(
        get_task_status(
            process or Process.ByKeys(obj.cdb_process_id),
            is_process=True
        )
    )
    return result


def get_briefcase_contents(page, cnt):
    # the delete url for each content would not be generated:
    # - content object is out of scope of workflow designer:
    #   it is not the reference, but the real object
    # - the "global_briefcases" or "local_briefcases" part differs
    return {
        "iface": "cs-workflow-briefcase-content",
        "content_object_id": cnt.GetObjectID(),
        "icon": cnt.GetObjectIcon(),
        "description": cnt.GetDescription(),
        "url": urls.get_object_url(cnt),
        "deletable": False,  # may be overridden later on
        "operations": get_briefcase_content_operations(page, cnt),
    }


def get_contents_for_briefcase(page, briefcase, data, deletable=False):
    result = []

    if data is None:
        contents = []
        for x in FolderContent.KeywordQuery(
                cdb_folder_id=briefcase.cdb_object_id):
            content = get_cached_briefcase_contents(page, x.cdb_content_id)
            if content:
                contents.append(content)
    else:
        contents = data["briefcase_contents"].get(briefcase.cdb_object_id, [])

    for cnt in contents:
        cnt_data = dict(cnt)
        cnt_data["deletable"] = deletable
        result.append(cnt_data)

    return result


def get_briefcase_content_operations(page, obj):
    oplist = []
    ophelper = page.application.getOptions()["operations"]
    if not misc.is_csweb():
        for op in ophelper.get_object_operations_for_context(
                obj,
                context_name=BRIEFCASE_CONTENT_OPCONTEXT,
        ):
            oplist.append({
                "url": op["url"],
                "tooltip": op["tooltip"],
                "icon": op["icon"],
                "label": op["fullpath_label"],
            })
    return {
        "iface": "cs-workflow-operation-dropdown",
        "oplist": oplist,
    }


def get_global_briefcase(page, obj, data=None, edit_schema_granted=True):
    bc = obj.Briefcase
    if edit_schema_granted:
        modify_url = page.make_link([
            obj.cdb_process_id,
            'global_briefcases',
            bc.briefcase_id,
            'modify',
        ])
        set_meaning_url = page.make_link([
            obj.cdb_process_id,
            'global_briefcases',
            bc.briefcase_id,
            'setmeaning',
        ])
        delete_url = page.make_link([
            obj.cdb_process_id,
            'global_briefcases',
            bc.briefcase_id,
            'delete',
        ])
        ac_url = page.make_link([
            obj.cdb_process_id,
            'global_briefcases',
            bc.briefcase_id,
            'add_content',
        ])
        dc_url = page.make_link([
            obj.cdb_process_id,
            'global_briefcases',
            bc.briefcase_id,
            'delete_content',
        ])
    else:
        modify_url = ""
        set_meaning_url = ""
        delete_url = ""
        ac_url = ""
        dc_url = ""
    return {
        "iface": "cs-workflow-global-briefcase",
        "briefcase_id": bc.briefcase_id,
        "name": bc.name,
        "iotype": obj.iotype,
        "meaning": IOType(obj.iotype).name,
        "icon": obj.GetObjectIcon(),
        "modifyUrl": modify_url,
        "setMeaningUrl": set_meaning_url,
        "addContentUrl": ac_url,
        "deleteUrl": delete_url,
        "deleteContentUrl": dc_url,
        "contents": get_contents_for_briefcase(page, bc, data, bool(dc_url)),
    }


def get_global_briefcases(page, process, data=None, edit_schema_granted=True):
    if data is None:
        global_links = process.BriefcaseLinks
    else:
        global_links = data["briefcase_links"].get("", [])

    return {
        "iface": "cs-workflow-global-briefcases",
        "briefcases": [
            get_global_briefcase(page, l, data, edit_schema_granted)
            for l in global_links
        ],
        "addUrl": page.make_link(
            [process.cdb_process_id, "create_global_briefcase"]
        ) if edit_schema_granted else "",
    }


def get_local_briefcase(page, obj, data=None, edit_schema_granted=True):
    if edit_schema_granted:
        modify_url = page.make_link([
            obj.cdb_process_id,
            'local_briefcases',
            obj.briefcase_id,
            'modify',
        ])
        delete_url = page.make_link([
            obj.cdb_process_id,
            'local_briefcases',
            obj.briefcase_id,
            'delete',
        ])
        ac_url = page.make_link([
            obj.cdb_process_id,
            'local_briefcases',
            obj.briefcase_id,
            'add_content',
        ])
        dc_url = page.make_link([
            obj.cdb_process_id,
            'local_briefcases',
            obj.briefcase_id,
            'delete_content',
        ])
    else:
        modify_url = ""
        delete_url = ""
        ac_url = ""
        dc_url = ""
    return {
        "iface": "cs-workflow-local-briefcase",
        "briefcase_id": obj.briefcase_id,
        "name": obj.name,
        "icon": obj.GetObjectIcon(),
        "modifyUrl": modify_url,
        "addContentUrl": ac_url,
        "deleteUrl": delete_url,
        "deleteContentUrl": dc_url,
        "contents": get_contents_for_briefcase(page, obj, data, bool(dc_url)),
    }


def get_local_briefcases(page, process, data=None, edit_schema_granted=True):
    if data is None:
        briefcases = process.GetLocalBriefcases()
    else:
        global_links = [
            l.briefcase_id for l in data["briefcase_links"].get("", [])
        ]
        briefcases = [
            b for b in data["briefcases"].values()
            if b.briefcase_id not in global_links
        ]

    return {
        "iface": "cs-workflow-local-briefcases",
        "briefcases": [
            get_local_briefcase(page, b, data, edit_schema_granted)
            for b in briefcases
        ],
        "addUrl": page.make_link([
            process.cdb_process_id,
            "create_local_briefcase",
        ]) if edit_schema_granted else "",
    }


def get_sidebar(page, data, edit_schema_granted=True):
    process = data["process"]
    return {
        "iface": "cs-workflow-sidebar",
        "briefcases": get_briefcases(page, process, data, edit_schema_granted),
        "process_object_id": process.cdb_object_id,
    }


def get_briefcases(page, process, data=None, edit_schema_granted=True):
    return {
        "iface": "cs-workflow-briefcases",
        "globalBriefcases": get_global_briefcases(page, process,
            data, edit_schema_granted),
        "localBriefcases": get_local_briefcases(page, process,
            data, edit_schema_granted),
    }


def get_task_forms(page, task, data=None):
    if check_access_proactively(task, EDIT_SCHEMA):
        add_url = page.make_link([
            task.cdb_process_id,
            "tasks",
            task.task_id,
            "add_form",
        ])
    else:
        add_url = ""

    display_url = "{}/{}".format(MOUNTEDPATH, task.cdb_object_id)

    return {
        "iface": "cs-workflow-forms",
        "displayFormUrl": display_url,
        "addFormUrl": add_url,
    }


def get_briefcase_links(page, task, data=None):
    if data is None:
        links = task.BriefcaseLinksByType.all()
    else:
        links = data["briefcase_links"].get(task.task_id, [])

    edit_schema_granted = check_access_proactively(task, EDIT_SCHEMA)
    if edit_schema_granted:
        add_url = page.make_link([
            task.cdb_process_id,
            "tasks",
            task.task_id,
            "link_briefcase",
        ])
    else:
        add_url = ""

    return {
        "iface": "cs-workflow-briefcase-links",
        "links": [
            get_briefcase_link(page, l, edit_schema_granted) for l in links
        ],
        "addUrl": add_url,
    }


def get_briefcase_link(page, brlink, edit_schema_granted=None):
    brlink.Reload()
    result = {
        "iface": "cs-workflow-briefcase-link",
        "briefcase_name": str(brlink.briefcase_name),
        "briefcase_id": brlink.briefcase_id,
        "icon": brlink.GetObjectIcon(),
        "iotype": brlink.iotype,
        "meaning": IOType(brlink.iotype).name,
        "deleteUrl": "",
        "modifyUrl": "",
    }
    if edit_schema_granted is None:
        edit_schema_granted = brlink.Task.CheckAccess(EDIT_SCHEMA)

    if edit_schema_granted:
        result.update({
            "deleteUrl": page.make_link([
                brlink.cdb_process_id,
                "tasks",
                brlink.task_id,
                "briefcaselinks",
                brlink.briefcase_id,
                "delete",
            ]),
            "modifyUrl": page.make_link([
                brlink.cdb_process_id,
                "tasks",
                brlink.task_id,
                "briefcaselinks",
                brlink.briefcase_id,
                "modify",
            ]),
        })
    return result


def get_max_cycles(page, task, data=None):
    if hasattr(task, "task_definition_id") and task.task_definition_id == LOOP_TASK_ID:
        if data is None:
            max_cycles = FilterParameter.KeywordQuery(
                cdb_process_id=task.cdb_process_id,
                task_id=task.task_id,
                name='max_cycles'
            )
        else:
            max_cycles = data["max_cycles"].get(task.task_id, [])
        if max_cycles:
            return max_cycles[0].value
    return 1


def get_condition(page, condition, success, edit_schema_granted=None):
    type_str = "success" if success else "failure"

    rule_name = condition.getRuleName()
    result = {
        "iface": "cs-workflow-{}-condition".format(type_str),
        "condition_name": rule_name,
        "position": condition.value,
        "deleteUrl": "",
        "upUrl": "",
        "downUrl": ""
    }
    if edit_schema_granted is None:
        edit_schema_granted = condition.Task.CheckAccess(EDIT_SCHEMA)

    if edit_schema_granted:
        result.update({
            "deleteUrl": page.make_link([
                condition.cdb_process_id,
                "tasks",
                condition.task_id,
                PATTERN_CONDITION_1.format(type_str),
                rule_name,
                "delete",
                condition.value
            ]),
            "upUrl": page.make_link([
                condition.cdb_process_id,
                "tasks",
                condition.task_id,
                PATTERN_CONDITION_N.format(type_str),
                rule_name,
                "up",
                condition.value
            ]),
            "downUrl": page.make_link([
                condition.cdb_process_id,
                "tasks",
                condition.task_id,
                PATTERN_CONDITION_N.format(type_str),
                rule_name,
                "down",
                condition.value
            ]),
        })
    return result


def get_conditions(page, task, success, data=None):
    if hasattr(task, "task_definition_id") and task.task_definition_id == LOOP_TASK_ID:
        type_str = "success" if success else "failure"
        name = PATTERN_CONDITION_1.format(type_str)
        name_n = PATTERN_CONDITION_N.format(type_str)

        if data is None:
            conditions = FilterParameter.KeywordQuery(
                cdb_process_id=task.cdb_process_id,
                task_id=task.task_id,
                name=name,
                order_by='value ASC'
            )
        else:
            conditions = data[name_n].get(
                task.task_id,
                []
            )

        edit_schema_granted = check_access_proactively(task, EDIT_SCHEMA)

        if edit_schema_granted:
            add_url = page.make_link([
                task.cdb_process_id,
                "tasks",
                task.task_id,
                name,
            ])
        else:
            add_url = ""

        return {
            "iface": "cs-workflow-{}-conditions".format(type_str),
            name_n: [
                get_condition(page, sc, success, edit_schema_granted)
                for sc in conditions
            ],
            "addUrl": add_url,
        }

    return None


def get_success_conditions(page, task, data=None):
    return get_conditions(
        page,
        task,
        success=True,
        data=data
    )


def get_success_condition(page, success_condition, edit_schema_granted=None):
    return get_condition(
        page,
        success_condition,
        success=True,
        edit_schema_granted=edit_schema_granted
    )


def get_failure_conditions(page, task, data=None):
    return get_conditions(
        page,
        task,
        success=False,
        data=data
    )


def get_failure_condition(page, failure_condition, edit_schema_granted=None):
    return get_condition(
        page,
        failure_condition,
        success=False,
        edit_schema_granted=edit_schema_granted
    )


def get_cycles(page, task, data=None):
    if hasattr(task, "task_definition_id") and task.task_definition_id == LOOP_TASK_ID:
        cycles = task.Cycles.Query(
            "1=1",
            order_by='current_cycle DESC'
        )

        return {
            "iface": "cs-workflow-cycles",
            "cycles": [
                get_cycle(page, i, cycles[0]) for i in cycles
            ],
            "current_cycle": (
                cycles[0].current_cycle
                if cycles
                else 1
            ),
            "current_cycle_link": (
                urls.get_object_url(cycles[0], page)
                if cycles
                else ""
            ),
        }

    return None


def get_cycle(page, cycle, current_cycle):
    if cycle.status > 0:
        icon = STATUS_ICON.format(cycle.status)
    else:
        icon = ""

    return {
        "iface": "cs-workflow-cycle",
        "cycle_name": str(cycle.GetDescription()),
        "cycle_link": urls.get_object_url(cycle, page),
        "cycle_icon": icon,
    }


def get_cycle_info(page, task, data, cycles):
    max_cycles = get_max_cycles(page, task, data)
    if max_cycles:
        current_cycle = (
            cycles["current_cycle"]
            if cycles
            else 1
        )
        return {
            "iface": "cs-workflow-task-cycle-info",
            "currentCycle": current_cycle,
            "max_cycles": max_cycles,
            "cycle_link": cycles["current_cycle_link"],
        }
    return None


def get_project_data(page, process):
    pcs_installed = wfinterface._is_pcs_enabled()
    result = {
        "iface": "cs-workflow-project",
        "pcs_installed": pcs_installed,
        "cdb_project_id": clean_text(process.cdb_project_id),
        "description": "",
        "link": "",
        "setProjectUrl": "",
    }

    if pcs_installed and hasattr(process, "Project"):
        if process.Project:
            result.update({
                "description": clean_text(process.Project.GetDescription()),
                "link": urls.get_object_url(process.Project),
            })

        result["setProjectUrl"] = page.make_link(
            [process.cdb_process_id, "set_project"]
        )

    return result


def get_app_data(page, cdb_process_id):
    data = load_process_data(page, cdb_process_id)
    process = data["process"]

    if not process:
        return {
            "iface": "cs-workflow-designer-no-process",
            "processId": cdb_process_id,
        }

    edit_schema_granted = check_access_proactively(process, EDIT_SCHEMA)
    process_manage_granted = process.CheckAccess("process manage")

    forms_url = "{}/{}".format(MOUNTEDPATH, process.GetObjectID())
    actions = {
        "iface": "cs-workflow-actions",
        "isCycle": bool(process.ParentProcess),
        "addTask": edit_schema_granted,
        "selectTaskTip": util.get_label("cdbwf_select_task_tip"),
        "addCompletion": edit_schema_granted,
        "protocol": None,
        "showAllFormsUrl": forms_url,
    }

    if process_manage_granted:
        if process.isActivatable():
            actions["startUrl"] = page.make_link([cdb_process_id, "start"])
        else:
            if process.isHoldableOrCancelable():
                actions.update({
                    "onHoldUrl": page.make_link([cdb_process_id, "hold"]),
                    "cancelUrl": page.make_link([cdb_process_id, "cancel"]),
                    "cancelConfirmHeader": util.get_label("cdbwf_confirm"),
                    "cancelConfirmText": util.get_label(
                        "cdbwf_confirm_cancel_workflow"
                    ),
                    "cancelOK": util.get_label("cdbwf_yes"),
                    "cancelNO": util.get_label("cdbwf_no"),
                })
            elif process.isDismissable():
                actions.update({
                    "dismissUrl": page.make_link([cdb_process_id, "dismiss"]),
                    "cancelConfirmHeader": util.get_label("cdbwf_confirm"),
                    "dismissConfirmText": util.get_label(
                        "cdbwf_confirm_dismiss_workflow"
                    ),
                })

    try:
        op_info = operations.OperationInfo(
            Protocol._getClassname(),
            "CDB_Search"
        )
        disable = not op_info.is_visible()
    except AttributeError:
        disable = True

    if not disable:
        protocol_url = urls.get_protocol_url(cdb_process_id)
        actions["protocol"] = {
            "url": protocol_url,
            "img": Protocol.GetClassIcon(),
        }

    modifyUrl = page.make_link([cdb_process_id, "modify"])
    project = get_project_data(page, process)
    parent = process.ParentProcess

    if parent:
        parentLink = urls.get_object_url(parent)
        parentTitle = parent.title
    else:
        parentLink = None
        parentTitle = None

    return {
        "iface": "cs-workflow-designer",
        "title": process.title,
        "pcs_installed": project.get('pcs_installed', False),
        "project": project,
        "description": get_description(page, process, modify=modifyUrl),
        "icon": process.GetObjectIcon(),
        "cdb_status_txt": get_state_text(process.cdb_objektart, process.status),
        "graph": get_graph_data(page, data),
        "sidebar": get_sidebar(page, data, edit_schema_granted),
        "modifyUrl": modifyUrl,
        "actions": actions,
        "autoScale": True,
        "parentProcessLink": parentLink,
        "parentProcessTitle": parentTitle,
        "cycleLinks": get_cycle_links(page, process),
    }


def get_cycle_links(page, process):
    cycles = [
        {
            "is_current": cycle.cdb_process_id == process.cdb_process_id,
            "link": urls.get_object_url(cycle),
        }
        for cycle in process.CycleSiblings
    ]
    if cycles:
        return {
            "iface": "cs-workflow-cycle-links",
            "cycles": cycles,
            "shownCycle": process.current_cycle,
            "label_shown_cycle": util.Labels()[
                "cdbwf_designer_shown_cycle"
            ],
        }
    return None


def make_new_task_component(page, process):
    return make_node(
        page,
        {
            "iface": "cs-workflow-new-task",
        },
        nonselectable=1,
        task_id="add-task",
    )


def make_process_end(page, process):
    node_data = {
        "iface": "cs-workflow-process-end",
        "followedByCompletion": "",
        "statusStyle": "",
        "statusIcon": "",
    }
    completion = process.ProcessCompletion

    if completion and completion.Components:
        # this node represents just the end of the first part of the process
        node_data["followedByCompletion"] = "followed-by-completion"
        node_data.update(
            get_simple_status(
                completion.status > 0,
                "cis_ok-circle"
            )
        )
    else:
        # this node represents the actual end of the process
        # use process status's icon and color
        node_data.update(
            get_task_status(
                process,
                is_process=True
            )
        )

    return make_node(
        page,
        node_data,
        nonselectable=1,
    )
