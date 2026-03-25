#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module wfinterface

This module contains the interface for the Elink Designer
"""

import logging
from itertools import groupby
from urllib.parse import urlsplit
from cdb import ElementsError, classbody
from cdb import constants
from cdb import ue
from cdb import util
from cdb import auth
from cdb import transactions
from cdb.lru_cache import lru_cache
from cdb.objects import ByID
from cdb.objects import operations
from cdb.objects.org import CommonRole
from cdb.objects.org import Person
from cdb.platform import FolderContent

from cs.platform.web.rest import support
from cs.platform.web.rest.relship.main import make_relship_target
from cs.workflow.misc import _run_op
from cs.workflow.misc import ResponsibleBrowserEntry
from cs.workflow.misc import require_feature_setup
from cs.workflow.misc import require_feature_viewing
from cs.workflow.misc import format_in_condition
from cs.workflow import get_cdbwf_resp_browser_schema
from cs.workflow.tasks import ApprovalTask
from cs.workflow.tasks import ExaminationTask
from cs.workflow.tasks import ExecutionTask
from cs.workflow.tasks import FilterParameter
from cs.workflow.tasks import SystemTask
from cs.workflow.tasks import Task
from cs.workflow.taskgroups import ParallelTaskGroup
from cs.workflow.taskgroups import ProcessCompletionTaskGroup
from cs.workflow.taskgroups import SequentialTaskGroup
from cs.workflow.taskgroups import TaskGroup  # @UnusedImport
from cs.workflow.schemacomponents import SchemaComponent
from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import BriefcaseLink
from cs.workflow.briefcases import IOType
from cs.workflow.processes import Process
from cs.workflow.constraints import Constraint
from cs.workflow.designer import LOOP_TASK_ID
from cs.workflow import systemtasks
from cs.workflow import misc
from cs.workflow.process_template import content_in_whitelist

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = [
    'Briefcase',
    'Process',
    'SchemaComponent',
    'Task',
]


PCS_ROLE = "PCS Role"
TASK_GROUP_TITLES = {
    "sequential": "Sequential task group",
    "parallel": "Parallel task group",
}
POSITION_OFFSET = 10
USER_PICTURE_CACHE = {}

RESPONSIBLE_TYPES = [
    ('Person', Person, "personalnummer"),
    ('Common Role', CommonRole, "role_id"),
]


def _run(opname, target, **kwargs):
    return _run_op(
        opname,
        target,
        operations.form_input(target, **kwargs)
    )


def _is_pcs_enabled():
    result = True
    try:
        import cs.pcs   # @UnusedImport
    except ImportError:
        result = False
    return result


def get_obj_id_from_url(url):
    """
    Returns a ``cdb.objects.Object`` identified by the given ``url``.

    The url is split into its path components. Objects are resolved as follows:

    - The URL schema and host are dropped. So this resolves objects from links
      targeting foreign hosts, too.
    - If the path contains 4 components, treat URL as a regular cs.web UI link.
    - If the path contains 6 components, treat URL as relship link. Only handle
      unary relationships.
    - If the path contains 8 components, treat URL as file link.

    Returns ``None`` if no object exists or is not readable by the user or
    ``url`` doesn't match any of the above.
    """
    components = urlsplit(url)
    path_components = components.path.split("/")
    path_length = len(path_components)

    def _return_oid(obj):
        if obj and obj.CheckAccess("read"):
            return obj.GetObjectID()
        logging.error("obj does not exist or is not readable: %s", obj)
        return None

    if path_length in (4, 6):
        # 4: UI link: ['', 'info', rest_name, rest_key]
        # 6: relship link:
        #     ['', 'info', rest_name, rest_key, 'relship', relship_name]
        rest_name, rest_key = path_components[2:4]

        try:
            obj = support.get_object_from_rest_name(rest_name, rest_key)
        except (ValueError, AttributeError):
            logging.exception("cannot get object from url '%s'", url)
            return None

        if path_length == 4:
            return _return_oid(obj)

        elif path_length == 6:
            relship_name = path_components[5]

            try:
                relship_target = make_relship_target(obj, relship_name)
            except AttributeError:
                logging.exception(
                    "cannot get relship target from url '%s' "
                    "(obj %s, relship target %s)",
                    url,
                    obj,
                    relship_target,
                )
                return None

            if relship_target.is_unary:
                relship_obj = relship_target.resolve()[-1]
                return _return_oid(relship_obj)

            else:
                logging.error(
                    "more than one relship target found: %s",
                    relship_target.resolve(),
                )
                return None  # should we even handle 1:n relships?

    elif path_length == 8:
        # file link:
        #    ['', 'api', 'v1', 'collection', rest_name, rest_key,
        #     'files', file_object_id]
        obj_id = path_components[-1]
        return _return_oid(ByID(obj_id))

    logging.error("invalid URL: %s (path length %s)", url, path_length)
    return None


@lru_cache(maxsize=1)
def get_loop_definition_id():
    return LOOP_TASK_ID


@classbody.classbody  # noqa
class Task(object):
    def DeleteTask(self):
        """ Delete the task from the database and from the workflow.
            If needed rearrange the task groups.

            Checks permissions and executes user exits

            If the process is already running, the current task must not
            be running or closed. Otherwise an exception is raised.

            :raises: cdb.ue.Exception

            :return: the most derived unchanged component
        """
        if self.status != self.NEW.status:
            raise ue.Exception("cdbwf_task_delete_not_allowed")

        ancestors_ids = [
            a.task_id for a in self.Ancestors if hasattr(a, "task_id")
        ]
        _run(constants.kOperationDelete, self)

        self.Process.Reload()
        self.Process.SimplifyStructure()

        ancestor = None
        for aid in reversed(ancestors_ids):
            ancestor = SchemaComponent.ByKeys(
                cdb_process_id=self.cdb_process_id,
                task_id=aid
            )
            if ancestor:
                break

        if not ancestor or isinstance(ancestor, ProcessCompletionTaskGroup):
            return self.Process

        return ancestor

    def ModifyTask(self, **kwargs):
        """ Interface method to modify the current task.
            Checks permissions and executes user exits.

            If the process is already running, the current task must not
            be running or closed. Otherwise an exception is raised.

            :raises: cdb.ue.Exception
        """
        kwargs.setdefault("position", self.position)

        _run(constants.kOperationModify,  # @UndefinedVariable
             self, **kwargs)

    def AddParameters(self, rule_name="", **kwargs):
        for key, value in kwargs.items():
            _run(
                constants.kOperationNew,
                FilterParameter,
                cdb_process_id=self.cdb_process_id,
                task_id=self.task_id,
                rule_name=rule_name,
                name=key,
                value=value
            )

    def GetResponsiblePersonInfo(self, base_uri=None):
        result = {
            "id1": self.subject_id,
            "id2": "",
            "subject_type": self.subject_type,
            "name": self.mapped_subject_name,
            "picture": None,
        }

        subject = self.Subject

        if subject:
            ids = subject.SubjectID()
            subject_type = subject.SubjectType()
            result.update({
                "id1": ids[0],
                "id2": ids[1],
                "subject_type": subject_type,
            })
            if subject_type == "Person":
                subject_key = "@".join([ids[0], ids[1], subject_type])

                try:
                    pic = USER_PICTURE_CACHE[subject_key]
                except KeyError:
                    pic = subject.GetPreviewFile()
                    pic = get_picture_url(pic, base_uri) if pic else None
                    USER_PICTURE_CACHE[subject_key] = pic

                result["picture"] = pic

        return result

    def CloseTask(self, **kwargs):
        """ Interface method to close the current task.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_close_task", self, **kwargs)

    def RefuseTask(self, **kwargs):
        """ Interface method to refuse the current task.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_refuse_task", self, **kwargs)

    def ForwardTask(self, **kwargs):
        """ Interface method to forward the current task.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_forward_task", self, **kwargs)


@classbody.classbody  # noqa
class TaskGroup(object):
    def SimplifyStructure(self):
        """ Simplify the task structure under the current component
        """
        require_feature_setup()

        for tg in self.TaskGroups:
            tg.SimplifyStructure()

        # If the current task group is sequential, join every sequential
        # task group to the current one
        if self.is_sequential():
            cdb_classname = SequentialTaskGroup.__classname__
            for tg in self.TaskGroups.KeywordQuery(cdb_classname=cdb_classname):
                tg._delete_taskgroup()

        # If the task group has only one component, delete the task group
        if len(self.Components) <= 1 and not isinstance(
                self, ProcessCompletionTaskGroup):
            self._delete_taskgroup()

    def _delete_taskgroup(self):
        require_feature_setup()

        if self.Parent:
            parent_id = self.parent_id
            self._shift_siblings("after", steps=len(self.Components) - 1)

            self.parent_id = None

            position = self.position
            for component in self.Components:
                component.Update(parent_id=parent_id, position=position)
                position += POSITION_OFFSET

            _run(constants.kOperationDelete, self)

    def CreateTask(self, ttype, title, **kwargs):
        """ Add a new task to the Task group.

            :param ttype: type of the new task
            :type ttype: one of ['execution', 'approval', 'examination',
                         'system']

            :param title: title of the new task
            :type title: string

            The following parameters are optional

            :param subject_id: ID of the responsible for the new task
            :type subject_id: string

            :param subject_type: type of the responsible for the new task
            :type subject_type: one of ['Person', 'Common Role', 'PCS Role']

            :param deadline: deadline for the new task
            :type deadline: string formatted as in "14.09.1983"

            :param description: description of the new task
            :type description: string

            :param finish_option: flag to close the process early in case of
                                  success
            :type finish_option: integer

            :param task_definition_id: cdb_object_id of the system task
                                       definition for the new tag,
                                       only for system tasks
            :type task_definition_id: a cdb_object_id

            :param parameters: parameters of the system task
            :type parameters: dictionary

            :raises: cdb.ue.Exception
        """
        max_pos = max(self.Components.position) if self.Components else 0

        task = Task._create_task_for_elink(
            ttype=ttype,
            title=title,
            subject_id=kwargs.get("subject_id", ""),
            subject_type=kwargs.get("subject_type", ""),
            cdb_process_id=self.cdb_process_id,
            parent_id=self.task_id,
            position=max_pos + POSITION_OFFSET,
            parameters=kwargs.get("parameters", {}),
            additional=kwargs.get("additional", {}),
            task_definition_id=kwargs.get("task_definition_id", ""),
            cdb_extension_class=kwargs.get("cdb_extension_class", "")
        )
        self.Reload()
        return task


@classbody.classbody  # noqa
class SchemaComponent(object):
    def AppendTask(self, position, ttype, title, **kwargs):
        """ Create a new Workflow task and append it before of, after of or
            parallel to the current component. If needed rearrange the task
            groups.

            If the process is already running the current component must not
            be running or closed. Otherwise an exception is raised.

            :param position: one of ['before', 'after', 'parallel']
            :type position: string

            :param ttype: type of the new task
            :type ttype: one of ['execution', 'approval', 'examination',
                         'system']

            :param title: title of the new task
            :type title: string

            The following parameters are optional

            :param subject_id: ID of the responsible for the new task
            :type subject_id: string

            :param subject_type: type of the responsible for the new task
            :type subject_type: one of ['Person', 'Common Role', 'PCS Role']

            :param deadline: deadline for the new task
            :type deadline: string formatted as in "14.09.1983"

            :param description: description of the new task
            :type description: string

            :param finish_option: flag to close the process early in case of
                                  success
            :type finish_option: integer

            :param task_definition_id: cdb_object_id of the system task
                                       definition for the new tag,
                                       only for system tasks
            :type task_definition_id: a cdb_object_id

            :param parameters: parameters of the system task
            :type parameters: dictionary

            :raises: cdb.ue.Exception
        """
        require_feature_setup()

        if (self.status != self.NEW.status) and position in [
                'before', 'parallel']:
            raise ue.Exception("cdbwf_task_modify_not_allowed")

        # Process completion task groups have to be handled separately
        if isinstance(self, ProcessCompletionTaskGroup):
            if position != "parallel":
                components_ids = self.Components.task_id
                self.Components.Update(parent_id=None)

                taskgroup = self.Process._create_task_group_for_elink(
                    "parallel",
                    POSITION_OFFSET,
                    self.task_id
                )

                SchemaComponent.KeywordQuery(
                    cdb_process_id=self.cdb_process_id
                ).Query(
                    SchemaComponent.task_id.one_of(*components_ids)
                ).Update(parent_id=taskgroup.task_id)
                taskgroup.Reload()

                return taskgroup.AppendTask(position, ttype, title, **kwargs)
        else:
            self._ensure_parent_has_the_right_type(position)

            # If needed, we have to shift the position of other tasks
            new_task_position = self._shift_siblings(position)

            subject_id = kwargs.get("subject_id", "")
            subject_type = kwargs.get("subject_type", "")
            parameters = kwargs.get("parameters", {})
            additional = kwargs.get("additional", {})
            task_definition_id = kwargs.get("task_definition_id", "")
            cdb_extension_class = kwargs.get("cdb_extension_class", "")

            return self._create_task_for_elink(
                ttype=ttype,
                title=title,
                subject_id=subject_id,
                subject_type=subject_type,
                cdb_process_id=self.cdb_process_id,
                parent_id=self.parent_id,
                position=new_task_position,
                parameters=parameters,
                additional=additional,
                task_definition_id=task_definition_id,
                cdb_extension_class=cdb_extension_class
                )

        return None

    def ReplaceTaskWithCycle(self):
        require_feature_setup()

        if self.status != self.NEW.status:
            raise ue.Exception("cdbwf_task_modify_not_allowed")

        with transactions.Transaction():
            # move self to allow copy at the same position
            old_position = self.position
            self.Update(position=-1)

            definition = get_loop_definition_id()

            loop_task = _run(
                constants.kOperationNew,
                SystemTask,
                cdb_process_id=self.cdb_process_id,
                position=old_position,
                parent_id=self.parent_id,
                title=self.title,
                task_definition_id=definition,
            )

            new_cycle = loop_task.create_first_cycle()
            _run(  # copied_task
                constants.kOperationCopy,
                self,
                cdb_process_id=new_cycle.cdb_process_id,
                position=10,
                parent_id="",
            )
            # briefcase links are copied, but not briefcases, so do this now
            links = set(new_cycle.AllBriefcaseLinks.briefcase_id)
            briefcases = set(new_cycle.AllBriefcases.briefcase_id)

            for missing in links.difference(briefcases):
                missing_briefcase = Briefcase.KeywordQuery(
                    cdb_process_id=self.cdb_process_id,
                    briefcase_id=missing
                )[0]
                operations.operation(
                    operations.constants.kOperationCopy,
                    missing_briefcase,
                    **dict(cdb_process_id=new_cycle.cdb_process_id)
                )

            _run(constants.kOperationDelete, self)

        return loop_task

    def MoveToPosition(self, position, component):
        """ Move the current component to the position before of, after of or
            parallel to the given component.
            If needed rearrange the task groups.

            If the process is already running both 'self' and 'task'
            must not be running nor closed. Otherwise an exception is raised.

            :param task: An existing task or task group
            :type task: cs.workflow.schemacomponents.SchemaComponent

            :param position: one of ['before', 'after', 'parallel']
            :type position: string

            :raises: cdb.ue.Exception
        """
        require_feature_setup()

        if (self.status != self.NEW.status
                or component.status != component.NEW.status):
            raise ue.Exception("cdbwf_task_move_not_allowed")

        with transactions.Transaction():
            component._ensure_parent_has_the_right_type(position)

            new_position = component._shift_siblings(position)
            self.Update(parent_id=component.parent_id, position=new_position)

        self.Process.Reload()
        self.Process.SimplifyStructure()

        self.Reload()

    def AddConstraint(self, rule_name, invert_rule=0, briefcase_id=None):
        """
        Add a constraint to the task or taskgroup.

        :param rule_name: the name of a cdb object rule.

        :param invert_rule: if negative, the object rule is inverted.
        :type invert_rule: either 0 or 1.

        :param briefcase_id: the id of a briefcase in the process (optional);
                             the briefcase should be assigned to the current
                             task or be a global briefcase.
        """
        return self.Process.AddConstraint(
            rule_name,
            invert_rule,
            self.task_id,
            briefcase_id
        )

    # ==========================================================================
    # Help methods
    # ==========================================================================

    def _ensure_parent_has_the_right_type(self, position):
        mode = "parallel" if position == "parallel" else "sequential"

        # First check if self.Parent has the right type
        needs_new_task_group = True
        if (mode == "sequential" and self.Parent.is_sequential()) or\
                (mode == "parallel" and self.Parent.is_parallel()):
            needs_new_task_group = False

        # If not ..
        if needs_new_task_group:
            if (not isinstance(self.Parent,
                               (Process, ProcessCompletionTaskGroup))
                    and len(self.Parent.Components) == 1):
                # .. and I have no siblings, change the type of self.Parent
                if mode == "parallel":
                    cdb_classname = ParallelTaskGroup.__classname__
                else:
                    cdb_classname = SequentialTaskGroup.__classname__

                _run(
                    constants.kOperationModify,
                    self.Parent,
                    cdb_classname=cdb_classname,
                    position=self.Parent.position,
                    title=TASK_GROUP_TITLES[mode]
                )
            else:
                # otherwise create a new task group with the right type
                self._create_task_group_and_add_me_to_it(mode)

    def _create_task_group_and_add_me_to_it(self, mode):
        require_feature_setup()
        with transactions.Transaction():
            position = self.position
            parent_id = self.parent_id

            self.position = 0
            self.parent_id = None

            taskgroup = self.Process._create_task_group_for_elink(
                mode,
                position,
                parent_id
            )

            # Set the new task group as parent
            self.parent_id = taskgroup.task_id
            self.position = POSITION_OFFSET
        self.Reload()

    def _shift_siblings(self, position, steps=1):
        require_feature_setup()
        if position != "parallel":
            if position == "before":
                condition = SchemaComponent.position >= self.position
                result = self.position
            else:
                condition = SchemaComponent.position > self.position
                result = self.position + steps * POSITION_OFFSET

            siblings = self.Parent.Components.Query(condition)

            for sibling in siblings:
                sibling.position += steps * POSITION_OFFSET
        else:
            result = max(self.Parent.Components.position) + POSITION_OFFSET

        return result

    @classmethod
    def _create_task_for_elink(cls, ttype, title, cdb_process_id, parent_id,
                               position, **kwargs):
        require_feature_setup()
        target_cls = SystemTask
        if ttype == 'execution' or ttype == ExecutionTask.__classname__:
            target_cls = ExecutionTask
        elif ttype == 'approval' or ttype == ApprovalTask.__classname__:
            target_cls = ApprovalTask
        elif ttype == 'examination' or ttype == ExaminationTask.__classname__:
            target_cls = ExaminationTask

        # clean up fields typed strictly
        parameters = kwargs.pop("parameters", {})
        additional = kwargs.pop("additional", {})
        if target_cls == SystemTask:
            if "cdb_extension_class" in kwargs:
                del kwargs["cdb_extension_class"]
        elif "task_definition_id" in kwargs:
            del kwargs["task_definition_id"]

        task = _run(
            constants.kOperationNew,
            target_cls,
            title=title,
            cdb_process_id=cdb_process_id,
            parent_id=parent_id,
            position=float(position),
            **kwargs
        )

        if target_cls == SystemTask:
            task.AddParameters(**parameters)

            if task.task_definition_id == LOOP_TASK_ID:
                template_id = additional.get("template_process_id", None)
                if template_id:
                    task.create_first_cycle(template_id)

        return task


@classbody.classbody  # noqa
class Briefcase(object):
    def DeleteBriefcase(self):
        """ Interface method to delete a briefcase. Checks permissions
            and executes user exits.
        """
        _run(constants.kOperationDelete, self)

    def ModifyBriefcase(self, **args):
        """ Interface method to modify the current briefcase.
            Checks permissions and executes user exits.
        """
        _run(constants.kOperationModify, self, **args)

    def SetGlobalMeaning(self, meaning, extends_rights=None):
        """ Set the global meaning of the briefcase for the current process.
            Overwrites an already existing global meaning.

            There should be no task specific meaning for any task
            in the process. Otherwise an exception is raised.

            :raises: cdb.ue.Exception
        """
        condition = ((BriefcaseLink.task_id != "") &
                     (BriefcaseLink.task_id != None))
        if self.Links.Query(condition):
            raise ue.Exception("cdbwf_global_is_not_local")

        link = self._set_meaning(
            task_id='',
            meaning=meaning,
            extends_rights=extends_rights
        )
        self.Reload()

        return link

    def SetTaskMeaning(self, meaning, task, extends_rights):
        """ Set the meaning of the briefcase for a specific task.
            Overwrites an already existing meaning for the given task.

            There should be no global meaning for the given briefcase
            in the process. Otherwise an exception is raised.

            :raises: cdb.ue.Exception
        """
        condition = ((BriefcaseLink.task_id == "") |
                     (BriefcaseLink.task_id == None))
        if self.Links.Query(condition):
            raise ue.Exception("cdbwf_global_is_not_local")

        link = self._set_meaning(
            task_id=task.task_id,
            meaning=meaning,
            extends_rights=extends_rights
        )
        self.Reload()

        return link

    def RemoveTaskMeaning(self, task):
        """ Interface method to remove meaning of the briefcase
            for a specific task. Checks permissions and executes user exits.
        """
        links = self.Links.KeywordQuery(task_id=task.task_id)
        if links:
            link = links[0]
            _run(constants.kOperationDelete, link)

    def ChangeTaskMeaning(self, task, meaning=None, extends_rights=None):
        require_feature_setup()
        updating = {}
        if meaning is not None:
            assert(meaning in [iotype.name for iotype in IOType])
            updating["iotype"] = IOType[meaning].value
        if extends_rights is not None:
            updating["extends_rights"] = int(extends_rights)
        links = self.Links.KeywordQuery(task_id=task.task_id)
        if not links:
            return None
        link = links[0]
        if meaning is not None:
            link.check_obj_rights_with_updated_iotype(
                ctx=None,
                new_iotype=updating["iotype"],
                persno=None
            )
        _run(constants.kOperationModify, link, **updating)
        link.Reload()
        return link

    def AddObject(self, object_id):
        """ Add an object to the briefcase

            :param object_id: the cdb_object_id of an existing object
            :type object_id: a cdb_object_id
        """
        require_feature_viewing()
        if not self.FolderContents.KeywordQuery(cdb_content_id=object_id):
            if content_in_whitelist(object_id, False):
                try:
                    _run(
                        constants.kOperationNew,
                        FolderContent,
                        cdb_folder_id=self.cdb_object_id,
                        cdb_content_id=object_id
                    )
                except (Exception, ElementsError) as error:
                    logging.exception(
                        "Briefcase '%s' AddObject '%s'",
                        self.cdb_object_id,
                        object_id,
                    )
                    raise util.ErrorMessage("just_a_replacement", error)

    def RemoveObject(self, object_id):
        """ Remove an object from the briefcase

            :param object_id: the cdb_object_id of an existing object
            :type object_id: a cdb_object_id
        """
        require_feature_viewing()
        fc = self.FolderContents.KeywordQuery(cdb_content_id=object_id)
        if fc:
            _run(constants.kOperationDelete, fc[0])

    # ==========================================================================
    # Help functions
    # ==========================================================================

    def _set_meaning(self, task_id, meaning, extends_rights):
        require_feature_setup()
        assert(meaning in [iotype.name for iotype in IOType])
        iotype = IOType[meaning].value
        links = self.Links.KeywordQuery(task_id=task_id)

        if links:
            link = links[0]
            link.iotype = iotype

            if extends_rights is not None:
                link.extends_rights = int(extends_rights)
        else:
            extends_rights = 1 if extends_rights else 0
            link = _run(
                constants.kOperationNew,
                BriefcaseLink,
                cdb_process_id=self.cdb_process_id,
                briefcase_id=self.briefcase_id,
                task_id=task_id,
                iotype=iotype,
                extends_rights=extends_rights,
            )

        return link

    def AddObjectFromCmsg(self, msg):
        """ Add an object to the briefcase from a `cdb.cmsg.Cdbcmsg` link.

            :param msg: A `cdb.cmsg.Cdbcmsg` link
        """
        # Searches for parameters
        require_feature_viewing()
        urlparts = msg.split("?")
        if len(urlparts) != 2:
            return None
        paramstr = urlparts[1]

        from urllib.parse import parse_qs
        key_dict = parse_qs(paramstr, True)
        # Gets relation
        relation = list(key_dict)[0].split('.')[0]
        # Finds out object class
        from cdb.objects import ClassRegistry
        objcls = ClassRegistry().find(relation)
        if not objcls:
            return None
        querydict = {}
        knames = objcls.KeyNames()
        # Removes relation prefix by attribute names
        # (relation name + ".")
        kidx = len(relation) + 1
        for k, v in key_dict.items():
            # Queries objects only with keys
            attr = k[kidx:]
            if attr in knames:
                querydict[attr] = v
        if not querydict:
            return None

        objs = objcls.KeywordQuery(**querydict)
        # Distinct check
        if len(objs) != 1:
            return None
        obj = objs[0]
        obj_id = obj.GetObjectID()
        if not obj_id:
            raise ue.Exception(
                "cdbwf_briefcase_content_not_allowed",
                obj.GetDescription()
            )
        self.AddObject(obj_id)
        return None

    def AddObjectFromLink(self, msg):
        """
        Add an object to the briefcase from a UI link.

        :param msg:
            UI link (/info/{rest_name}/{rest_key})
            or relship link (/info/{rest_name}/{rest_key}/relship/{relship})
            or file link (.../files/{file_object_id})
        """
        require_feature_viewing()
        obj_id = get_obj_id_from_url(msg)

        if obj_id is None:
            raise ue.Exception("cdbwf_briefcase_content_not_allowed", msg)

        self.AddObject(obj_id)


@classbody.classbody  # noqa
class BriefcaseLink(object):
    def show_checkbox(self):
        if self.Task and self.Task.isSystemTask():
            return False
        else:
            return True

    def DeleteBriefcaseLink(self):
        """ Interface method to delete a briefcase link. Checks permissions
            and executes user exits.
        """
        _run(constants.kOperationDelete, self)


@classbody.classbody  # noqa
class Constraint(object):
    def DeleteConstraint(self):
        """ Delete the constraint from the database and from the workflow.

            Checks permissions and executes user exits
        """
        _run(constants.kOperationDelete, self)

    def ModifyConstraint(self, **kwargs):
        """ Interface method to modify the current constraint.
            Checks permissions and executes user exits.

            :raises: cdb.ue.Exception
        """
        _run(constants.kOperationModify, self, **kwargs)


@classbody.classbody  # noqa
class Process(object):
    """
    Extend workflow with advanced APIs to manage it by programming.
    """
    def AddAttachment(self, object_id):
        """
        Add an object to the attachment briefcase of this process.
        """
        if self.AttachmentsBriefcase:
            self.AttachmentsBriefcase.AddObject(object_id)

    def RemoveAttachment(self, object_id):
        """
        Remove an object from the attachment briefcase of this process.
        """
        if self.AttachmentsBriefcase:
            self.AttachmentsBriefcase.RemoveObject(object_id)

    def AddConstraint(self, rule_name, invert_rule=0, task_id=None,
                      briefcase_id=None):
        """
        Add a constraint to the process.

        :param rule_name: the ``cdb_object_id`` of an entry in
            ``cdbwf_pyrule``.

        :param invert_rule: if negative, the object rule is inverted
        :type invert_rule: either 0 or 1.

        :param task_id: the id of a task in the process (optional).

        :param briefcase_id: the id of a briefcase in the process (optional);
                             if a task_id is specified, the briefcase should
                             be assigned to the given task
                             or be a global briefcase.
        """
        args = {
            "cdb_process_id": self.cdb_process_id,
            "rule_name": rule_name,
            "invert_rule": invert_rule,
        }

        if task_id is not None:
            args["task_id"] = task_id

        if briefcase_id is not None:
            args["briefcase_id"] = briefcase_id

        return _run(constants.kOperationNew, Constraint, **args)

    def CreateTask(self, ttype, title, relative_position=None, other_task=None,
                   **kwargs):
        """ Add a new task to the workflow.

            If the workflow has no task group, a parallel task group is created.
            Otherwise it is possible to add a task, specifying the relative
            position (before, after, parallel) of the new task with regard
            to another task (other_task)

            The workflow should have no tasks and at most one task group.
            Otherwise an exception is raised.

            :param ttype: type of the new task
            :type ttype: one of ['execution', 'approval', 'examination',
                         'system']

            :param title: title of the new task
            :type title: string

            The following parameters are optional

            :param subject_id: ID of the responsible for the new task
            :type subject_id: string

            :param subject_type: type of the responsible for the new task
            :type subject_type: one of ['Person', 'Common Role', 'PCS Role']

            :param deadline: deadline for the new task
            :type deadline: string formatted as in "14.09.1983"

            :param description: description of the new task
            :type description: string

            :param finish_option: flag to close the process early in case of
                                  success
            :type finish_option: integer

            :param task_definition_id: cdb_object_id of the system task
                                       definition for the new tag,
                                       only for system tasks
            :type task_definition_id: a cdb_object_id

            :param parameters: parameters of the system task
            :type parameters: dictionary

            :raises: cdb.ue.Exception
        """
        if relative_position and other_task:
            task = other_task.AppendTask(
                relative_position,
                ttype,
                title,
                **kwargs
            )
        else:
            max_pos = max(self.Components.position) if self.Components else 0
            task = Task._create_task_for_elink(
                ttype=ttype,
                title=title,
                subject_id=kwargs.get("subject_id", ""),
                subject_type=kwargs.get("subject_type", ""),
                cdb_process_id=self.cdb_process_id,
                parent_id='',
                position=max_pos + POSITION_OFFSET,
                parameters=kwargs.get("parameters", {}),
                additional=kwargs.get("additional", {}),
                task_definition_id=kwargs.get("task_definition_id", ""),
                cdb_extension_class=kwargs.get("cdb_extension_class", "")
            )
            self.Reload()

        return task

    @classmethod
    def CreateProcess(cls, **kwargs):
        """ Interface method to create a process. Checks permissions
            and executes user exits. All the parameters are optional

            :param title: The title of the workflow. If not given a standard
                          title will be used. This is defined in the CDB-label
                          cdbwf_standard_workflow_title.
            :type title: string

            :param subject_id: The subject_id of the workflow responsible.
                               If not given, the id of the current user is used.
            :type subject_id: string

            :param subject_type: The subject_type of the workflow responsible.
                                 If not given 'Person' is used.
            :type subject_type: string

            :param categ_id: The id of the worflow category
            :type categ_id: string

            :param cdb_project_id: The id of the project associated to
                                   the workflow.
            :type cdb_project_id: string

            :param start_date: Start date of the workflow.
            :type start_date: string

            :param deadline: A deadline for the workflow.
            :type deadline: string

            :param max_duration: Maximum duration of the workflow in days.
            :type max_duration: integer

            :param org_id: Id of an organization, to which the workflow belongs.
            :type org_id: string

            :return: The new process
        """
        kwargs.setdefault(
            "title",
            util.get_label("cdbwf_standard_workflow_title")
        )
        kwargs.setdefault("subject_id", auth.persno)
        kwargs.setdefault("subject_type", "Person")
        return _run(constants.kOperationNew, cls, **kwargs)

    def DeleteProcess(self):
        """ Interface method to delete the current process.
            Checks permissions and executes user exits.
        """
        _run(constants.kOperationDelete, self)

    def ModifyProcess(self, **kwargs):
        """ Interface method to modify the current process.
            Checks permissions and executes user exits.
        """
        _run(constants.kOperationModify, self, **kwargs)

    def ActivateProcess(self, **kwargs):
        """ Interface method to freeze the current process.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_start_workflow", self, **kwargs)

    def OnHoldProcess(self, **kwargs):
        """ Interface method to freeze the current process.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_onhold_workflow", self, **kwargs)

    def CancelProcess(self, **kwargs):
        """ Interface method to freeze the current process.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_cancel_workflow", self, **kwargs)

    def DismissProcess(self, **kwargs):
        """ Interface method to freeze the current process.
            Checks permissions and executes user exits.
        """
        _run("cdbwf_dismiss_workflow", self, **kwargs)

    def CreateBriefcase(self, name):
        """ Interface method to create a briefcase. Checks permissions
            and executes user exits.
        """
        bc = _run(
            constants.kOperationNew,
            Briefcase,
            cdb_process_id=self.cdb_process_id,
            name=name
        )
        self.Reload()
        return bc

    def AllowedOperationsForSelection(self, selection):
        """ Given a selection of tasks, return a list of operations
            which are allowed on this selections. The possibile operations are
            - wrap the selection in a new loop task
            - insert a task before the selection
            - insert a task after the selection
            - insert a task parallel the selection

            :param selection: A list of task_ids of tasks
            :type selection: list of strings

            :return: a sublist of ['loop', 'before', 'after', 'parallel']
        """
        # Check rights
        if not self.CheckAccess("edit schema"):
            return []

        # if process is closed or cancelled return []
        if self.status not in [self.NEW.status, self.EXECUTION.status]:
            return []

        outer_context = self._find_outer_context(selection)

        # If the outer context is a single task, every operation is
        # allowed
        if isinstance(outer_context, Task):
            if outer_context.status == outer_context.NEW.status:
                return ['loop', 'before', 'after', 'parallel']
            else:
                return ['after']

        # Which components of the outer context have been selected?
        selected_components = self._get_selected_components(
            outer_context,
            selection
        )

        if selected_components:
            # If the outer context is sequential, is the selection connected?
            if outer_context.is_sequential():
                minpos = selected_components[0].position
                maxpos = selected_components[-1].position

                condition = (SchemaComponent.position >= minpos) & \
                            (SchemaComponent.position <= maxpos)
                components = outer_context.Components.Query(condition)

                if not set(components) <= set(selected_components):
                    return []

                result = []
                if outer_context.is_position_editable(minpos):
                    result.extend(['loop', 'before', 'parallel'])
                if outer_context.is_position_editable(maxpos + 1):
                    result.append('after')
                return result

            # If the outer context is parallel and not every component has
            # been selected, you can only add parallel tasks
            else:
                result = []
                if outer_context.is_position_editable(0):
                    result.append('loop')
                    result.append('parallel')

                if set(outer_context.Components) <= set(selected_components):
                    # completion task groups have to be handled separately
                    if isinstance(outer_context, ProcessCompletionTaskGroup):
                        if outer_context.status == outer_context.NEW.status:
                            result.append('before')
                        if outer_context.status in [outer_context.NEW.status,
                                                    outer_context.EXECUTION.status]:
                            result.append('after')
                    else:
                        parent = outer_context.Parent
                        context_position = outer_context.position

                        if parent:
                            if parent.is_position_editable(context_position):
                                result.append('before')
                            if parent.is_position_editable(
                                    context_position + 1):
                                result.append('after')
                return result
        return []

    def AppendTaskToSelection(self, where, selection, ttype, title, **kwargs):
        """ Append a new task to the selection.

            The selection has to be valid (see also
            Process.AllowedOperationsForSelection).

            :return: the most derived unchanged task
        """
        require_feature_setup()
        outer_context = self._find_outer_context(selection)

        if isinstance(outer_context, Task):
            result = outer_context.Parent
            outer_context.AppendTask(where, ttype, title, **kwargs)

        elif where in ["before", "after"]:
            extremal_task = self._find_extremal_task(
                selection,
                where,
                outer_context
            )
            result = extremal_task.Parent
            extremal_task.AppendTask(where, ttype, title, **kwargs)

        elif where == "parallel":
            if isinstance(outer_context, ParallelTaskGroup):
                result = outer_context

                new_position = max(
                    outer_context.Components.position
                ) + POSITION_OFFSET
                kwargs["position"] = new_position
                kwargs["parent_id"] = outer_context.task_id
                kwargs["cdb_process_id"] = self.cdb_process_id

                SchemaComponent._create_task_for_elink(ttype, title, **kwargs)
            else:
                if isinstance(outer_context, Process) and len(
                        outer_context.Components) == 1:
                    taskgroup = outer_context.Components[0]
                elif (not isinstance(outer_context, Process) and
                      set(
                          [task.task_id for task in outer_context.AllTasks
                      ]) <= set(selection)):
                    taskgroup = outer_context
                else:
                    selected_components = self._get_selected_components(
                        outer_context,
                        selection
                    )

                    with transactions.Transaction():
                        position = selected_components[0].position
                        selected_components.Update(parent_id=None)

                        parent_id = getattr(outer_context, "task_id", "")
                        taskgroup = self._create_task_group_for_elink(
                            "sequential",
                            position,
                            parent_id
                        )
                        selected_components.Update(parent_id=taskgroup.task_id)

                result = taskgroup.Parent

                with transactions.Transaction():
                    new_created_task = taskgroup.AppendTask("parallel", ttype, title, **kwargs)

                    new_sequential_taskgroup = SchemaComponent.Create(
                                                    task_id=TaskGroup.new_aggregate_number(),
                                                    cdb_process_id=new_created_task.cdb_process_id,
                                                    parent_id=new_created_task.parent_id,
                                                    position=new_created_task.position,
                                                    title="Sequential task group",
                                                    status=0,
                                                    cdb_status_txt="New",
                                                    cdb_objektart="cdbwf_aggregate",
                                                    cdb_classname="cdbwf_aggregate_sequential",
                                                    process_is_onhold=int(0))

                    new_created_task.Update(parent_id=new_sequential_taskgroup.task_id, position=POSITION_OFFSET)

        self.Reload()
        return result

    def ReplaceSelectionWithCycle(self, selection):
        """ Replace the selection with a cycle.

            The selection has to be valid (see also
            Process.AllowedOperationsForSelection).

            :return: the most derived unchanged task
        """
        require_feature_setup()
        outer_context = self._find_outer_context(selection)

        if isinstance(outer_context, Task):
            result = outer_context.Parent
            outer_context.ReplaceTaskWithCycle()
        else:
            if isinstance(outer_context, Process) and len(
                    outer_context.Components) == 1:
                taskgroup = outer_context.Components[0]
            elif (not isinstance(outer_context, Process) and
                  set(
                      [task.task_id for task in outer_context.AllTasks
                       ]) <= set(selection)):
                taskgroup = outer_context
            else:
                selected_components = self._get_selected_components(
                    outer_context,
                    selection
                )

                with transactions.Transaction():
                    position = selected_components[0].position
                    selected_components.Update(parent_id=None)

                    parent_id = getattr(outer_context, "task_id", "")
                    taskgroup = self._create_task_group_for_elink(
                        "sequential",
                        position,
                        parent_id
                    )

                    selected_components.Update(parent_id=taskgroup.task_id)
            taskgroup.ReplaceTaskWithCycle()
            result = taskgroup.Parent
        self.Reload()
        return result

    def SimplifyStructure(self):
        """ Simplify the task structure under the current component
        """
        require_feature_setup()

        for tg in self.TaskGroups:
            tg.SimplifyStructure()

        if self.ProcessCompletion:
            self.ProcessCompletion.SimplifyStructure()

        # delete every sequential task group and attach its components to
        # the process
        cdb_classname = SequentialTaskGroup.__classname__
        for tg in self.TaskGroups.KeywordQuery(cdb_classname=cdb_classname):
            tg._delete_taskgroup()

    # ==========================================================================
    # Help methods
    # ==========================================================================

    def _create_task_group_for_elink(self, mode, position, parent_id):
        args = {
            "title": TASK_GROUP_TITLES[mode],
            "parent_id": parent_id,
            "position": position,
            "cdb_project_id": self.cdb_project_id,
            "cdb_process_id": self.cdb_process_id,
        }

        # Create a new task group
        grp_cls = ParallelTaskGroup
        if mode == "sequential":
            grp_cls = SequentialTaskGroup

        return _run(constants.kOperationNew, grp_cls, **args)

    def _find_outer_context(self, selection):
        # Find the outer context for the selected tasks.
        # This is done as follows:
        # - for every task compute the path in the task-group-structure from
        #   the root (process) to the task itself
        # - take the common prefix to all the paths at the previous point
        # - the last element thereof is the outer context

        paths_from_root = []
        for task_id in selection:
            task = SchemaComponent.ByKeys(cdb_process_id=self.cdb_process_id,
                                          task_id=task_id)
            ancestors = task.Ancestors + [task]
            paths_from_root.append(ancestors)

        outer_context = self
        for tpl in zip(*paths_from_root):
            if len(set(tpl)) == 1:
                outer_context = tpl[0]
            else:
                break

        return outer_context

    def _find_extremal_task(self, selection, where, outer_context=None):
        if not outer_context:
            outer_context = self._find_outer_context(selection)

        if where == "before":
            func = min
        elif where == "after":
            func = max
        else:
            raise RuntimeError("Invalid position")

        if outer_context.is_parallel():
            if set([task.task_id for task in outer_context.AllTasks]) <= set(
                    selection):
                return outer_context
            else:
                raise RuntimeError("Invalid selection")
        else:
            # find out all direct children of outer_context
            components = []
            _tasks = SchemaComponent.Query("{} AND cdb_process_id='{}'".format(
                SchemaComponent.task_id.one_of(*selection),
                self.cdb_process_id)
            )
            for task in _tasks:
                ancestors = task.Ancestors + [task]
                idx = ancestors.index(outer_context)
                if idx > -1:
                    components.append(ancestors[idx + 1])
            return func(components, key=lambda x: x.position)

    def _get_selected_components(self, outer_context, selection):
        if isinstance(outer_context, Task):
            selected_ids = selection
        else:
            set_selection = set(selection)
            selected_ids = []

            for component in outer_context.Components:
                if isinstance(component, Task):
                    if component.task_id in selection:
                        selected_ids.append(component.task_id)
                else:
                    task_ids = set([
                        task.task_id for task in component.AllTasks
                    ])

                    # make sure every subtask of task group has been selected
                    if task_ids <= set_selection:
                        selected_ids.append(component.task_id)
                    elif task_ids & set_selection:
                        return []

        # Return an ObjectCollection (not a list!)
        return self.AllComponents.Query(
            SchemaComponent.task_id.one_of(*selected_ids),
            order_by="position"
        )

    def GetGlobalBriefcases(self):
        return self.Briefcases

    def GetLocalBriefcases(self):
        from operator import attrgetter
        return sorted(
            set(self.AllBriefcases) - set(self.GetGlobalBriefcases()),
            key=attrgetter("briefcase_id")
        )

    def isActivatable(self):
        """
        Manually check whether a process can be started(activated) or not.
        """
        return self.status in [self.NEW.status, self.PAUSED.status] and \
            not self.isTemplate()

    def isHoldableOrCancelable(self):
        """
        Manually check whether a process can be put on hold (paused) or not.
        """
        return self.status == self.EXECUTION.status and \
            not self.isTemplate()

    def isDismissable(self):
        """
        Manually check whether a process can be discarded or not.
        """
        return self.status not in [
            self.EXECUTION.status,
            self.COMPLETED.status,
            self.DISCARDED.status,
        ]

    def GetSubjectCandidates(self, addtl_cond=""):
        tbl = ResponsibleBrowserEntry.GetTableName()
        addtl_cond = addtl_cond or "1=1"

        if self.cdb_project_id:
            condition = "cdb_project_id IN ('', '{}') AND {}".format(
                self.cdb_project_id, addtl_cond)
            sqlstr = "SELECT * FROM {} WHERE {} ORDER BY order_by".format(
                tbl, condition)

        else:
            # E038064, select distinct project roles
            attrs = ", ".join([
                "t3.{}".format(x) if x != "cdb_project_id"
                else "'' AS cdb_project_id"
                for x in get_cdbwf_resp_browser_schema()])
            sqlstr = """
                SELECT *
                FROM (
                    SELECT t2.*
                    FROM {table} t2
                    WHERE t2.cdb_project_id=''

                    UNION SELECT DISTINCT {attrs}
                    FROM {table} t3
                    WHERE t3.cdb_project_id>''
                ) x
                WHERE {where}
                ORDER BY subject_type
            """.format(table=tbl, attrs=attrs, where=addtl_cond)

        all_entries = ResponsibleBrowserEntry.SQL(sqlstr)
        grouped_entries = {}
        for key, group in groupby(all_entries, lambda x: x.subject_type):
            grouped_entries[key] = list(group)
        readable_entries = self.getReadableEntries(grouped_entries)
        result = []
        for e in all_entries:
            if (e.subject_id, e.subject_type) in readable_entries and e["subject_name"]:  # E036872
                result.append(e)
        return result

    def getReadableEntries(self, entries):
        responsible_types = list(RESPONSIBLE_TYPES)
        result = []
        for subject_type, subject_cls, id_attr in responsible_types:
            if subject_type in entries:
                ids_list = []
                for obj in entries[subject_type]:
                    ids_list.append(str(obj.subject_id))

                in_condition = format_in_condition(id_attr, ids_list)
                readable_entries = subject_cls.Query(in_condition, access="read")
                result += [(o[id_attr], subject_type) for o in readable_entries]

        if misc.is_installed("cs.pcs.projects"):
            from cs.pcs.projects import Role
            all_entries = entries.get(PCS_ROLE, [])

            if self.cdb_project_id:
                readable_entries = Role.Query(
                    "cdb_project_id = '{}' AND role_id IN ('{}')".format(
                        self.cdb_project_id,
                        "','".join([
                            str(entry.subject_id) for entry in all_entries
                        ]),
                    ),
                    access="read",
                )
                result += [(o.role_id, PCS_ROLE) for o in readable_entries]
            else:
                # Project roles: Check read access for project-specific roles
                # only, not for roles of _any_ project
                result += [(o.subject_id, PCS_ROLE) for o in all_entries]

        return result

    def GetRoleCandidates(self, addtl_cond=""):
        condition = "subject_type NOT IN ('Person')"
        if not self.cdb_project_id:
            condition = "{} AND {}".format("cdb_project_id=''", condition)
        if addtl_cond:
            condition = "{} AND {}".format(condition, addtl_cond)
        return self.GetSubjectCandidates(condition)


@classbody.classbody  # noqa
class FilterParameter(object):
    def DeleteParameter(self):
        """ Interface method to delete a filter parameter.
            Checks permissions and executes user exits.
        """
        _run(constants.kOperationDelete, self)

    def ModifyParameter(self, **args):
        """ Interface method to modify the current filter parameter.
            Checks permissions and executes user exits.
        """
        _run(constants.kOperationModify, self, **args)


def get_system_task_definitions():
    return systemtasks.SystemTaskDefinition.KeywordQuery(
        order_by=systemtasks.SystemTaskDefinition.ml_name.getLanguageField().name
    )


def get_picture_url(pic, base_uri=None):
    if base_uri is None:
        from cdb import elink
        base_uri = getattr(
            elink.getCurrentRequest(),
            'base_uri',
            "BASE_URI/",
        )
    return "{}powerscript/cdb.apps.preview/pic?cdb_file_id={}".format(
        base_uri,
        pic.cdb_object_id,
    )


def get_possible_task_types():
    def _get_task_type_label(cls):
        return str(cls._getClassDef().getDesignation())

    def _get_task_extensions(cls):
        extensions = cls.getPossibleExtensions()
        return [{
            "type": extn["classname"],
            "label": extn["label"],
        } for extn in extensions]

    def _get_task_types(cls):
        return {
            "type": cls._getClassname(),
            "label": _get_task_type_label(cls),
            "extensions": _get_task_extensions(cls),
        }

    systask_type = SystemTask._getClassname()
    types = [ExaminationTask, ApprovalTask, ExecutionTask]
    return {
        "heading": _get_task_type_label(Task),
        "task_types": [_get_task_types(cls) for cls in types],
        "heading_systemtask": _get_task_type_label(SystemTask),
        "systemtask_types": [
            {
                "type": systask_type,
                "label": stdef.Name[''],
                "id": stdef.cdb_object_id,
            }
            for stdef in get_system_task_definitions()
        ],
    }
