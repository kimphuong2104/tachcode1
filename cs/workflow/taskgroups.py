#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module TaskGroups

This is the documentation for the TaskGroups module.
"""

from cdb import sqlapi
from cdb import ue
from cdb import util
from cdb import constants

from cdb.objects import Forward
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import State
from cdb.objects import operations

from cs.workflow.misc import set_state
from cs.workflow.schemacomponents import SchemaComponent
from cs.workflow import exceptions

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = [
    'ParallelTaskGroup',
    'ProcessCompletionTaskGroup',
    'SequentialTaskGroup',
    'TaskGroup',
]

IMPLEMENTED_BY_SUBCLASS = "To be implemented by the subclasses"

fTaskGroup = Forward(__name__ + ".TaskGroup")

fSchemaComponent = Forward("cs.workflow.schemacomponents.SchemaComponent")
fTask = Forward("cs.workflow.tasks.Task")


class TaskGroup(SchemaComponent):
    __classname__ = "cdbwf_aggregate"
    __match__ = fSchemaComponent.cdb_classname >= __classname__
    __wf_handler_attr__ = "task_handler"
    __obj_class__ = "cdbwf_aggregate"

    Tasks = Reference_N(fTask,
                        fTask.cdb_process_id == fTaskGroup.cdb_process_id,
                        fTask.parent_id == fTaskGroup.task_id,
                        order_by=fTask.position)

    TaskGroups = Reference_N(fTaskGroup,
                             fTaskGroup.cdb_process_id == fTaskGroup.cdb_process_id,
                             fTaskGroup.parent_id == fTaskGroup.task_id,
                             order_by=fTaskGroup.position)

    Components = Reference_N(fSchemaComponent,
                             fSchemaComponent.cdb_process_id == fTaskGroup.cdb_process_id,
                             fSchemaComponent.parent_id == fTaskGroup.task_id,
                             order_by=fSchemaComponent.position)

    def _get_all_tasks(self):
        result = self.Tasks

        for tg in self.TaskGroups:
            result += tg.AllTasks
        return result
    AllTasks = ReferenceMethods_N(fTask, _get_all_tasks)

    def _get_first(self):
        if self.Components:
            return self.Components[0]
        return None
    First = ReferenceMethods_1(fSchemaComponent, _get_first)

    event_map = {
        (('create', 'copy'), 'pre'): ("check_position",
                                      "make_aggregate_number"),
        (('create', 'copy'), 'pre_mask'): ("allow_new_task",
                                           "make_position",
                                           "make_project_id"),
        (('modify'), 'pre'): "check_position",
    }

    # ==========================================================================
    # New interface
    # ==========================================================================

    def activate_task(self):
        """ Starts a task group

            :raise: exceptions.TaskCancelledException,
                    exceptions.TaskClosedException
        """

        try:
            if not self.check_constraints():
                raise exceptions.TaskCancelledException()

            self.setReady()
            self.activate_subtasks()
        except exceptions.TaskCancelledException as ex:
            msg = str(ex)
            self.cancel_task(msg)
            raise
        except exceptions.TaskClosedException as ex:
            self.close_task()
            raise

    def cancel_task(self, comment=""):
        self.cancel_subtasks(comment)
        self.setCancelled(comment)

    def cancel_subtasks(self, comment=""):
        from cs.workflow.tasks import Task
        components = (self.TaskGroups.Query(TaskGroup.status
                                            .one_of(self.EXECUTION.status,
                                                    self.NEW.status)) +
                      self.Tasks.Query(Task.status
                                       .one_of(Task.EXECUTION.status,
                                               Task.NEW.status)))

        for component in components:
            component.cancel_task(comment)

    def close_task(self):
        self.setDone()

    def refuse_task(self, comment=""):
        self.setRefused(comment)

    def propagate_refuse(self, child, comment=""):
        self.refuse_task(comment)
        self.cancel_subtasks(comment)
        if self.Parent:
            self.Parent.propagate_refuse(self, comment)

    def activate_subtasks(self):
        raise NotImplementedError(IMPLEMENTED_BY_SUBCLASS)

    def propagate_done(self, child):
        raise NotImplementedError(IMPLEMENTED_BY_SUBCLASS)

    def propagate_cancel(self, child, comment=""):
        raise NotImplementedError(IMPLEMENTED_BY_SUBCLASS)

    # ==========================================================================
    # End new interface
    # ==========================================================================

    def is_sequential(self):
        raise NotImplementedError(IMPLEMENTED_BY_SUBCLASS)

    def is_parallel(self):
        return not self.is_sequential()

    @classmethod
    def has_finish_option(cls, child):
        from cs.workflow.tasks import Task
        return (isinstance(child, Task) and child.finish_option
                and not getattr(child, '__forwarded__', ''))

    class NEW(State):
        status = 0

    class EXECUTION(State):
        status = 10

    class COMPLETED(State):
        status = 20

        def post(state, self, ctx):  # @NoSelf
            super(TaskGroup.COMPLETED, state).post(self, ctx)

    class REJECTED(State):
        status = 30

        def post(state, self, ctx):  # @NoSelf
            super(TaskGroup.REJECTED, state).post(self, ctx)

    class DISCARDED(State):
        status = 35

    @classmethod
    def new_aggregate_number(cls):
        return "T%08d" % util.nextval("cdbwf_task.task_id")

    def on_modify_pre_mask(self, ctx):
        if self.status > TaskGroup.NEW.status:
            ctx.set_fields_readonly(["position", "mapped_classname"])

    def make_aggregate_number(self, ctx):
        if ctx.action == "copy":
            # No need to change the task_id if the process id has changed
            template_id = getattr(ctx.cdbtemplate, "cdb_process_id", self.cdb_process_id)
            if template_id == self.cdb_process_id:
                self.task_id = self.new_aggregate_number()
        else:
            self.task_id = self.new_aggregate_number()

    def allow_new_task(self, ctx):
        # No creation of tasks out of a process context
        if not ctx.parent.get_attribute_names():
            raise util.ErrorMessage("cdbwf_err104")
        self.Super(TaskGroup).allow_new_task(ctx)

    def make_project_id(self, ctx):
        if self.Process:
            # derive process's project id
            self.cdb_project_id = self.Process.cdb_project_id

    def on_delete_pre(self, ctx):
        self.allow_delete()

        # Delete the subtasks before deleting the task group.
        # This needs to be done in User Exit because the delete right
        # is controlled by a relationship
        for component in self.Components:
            operations.operation(constants.kOperationDelete,  # @UndefinedVariable
                                 component)

    def allow_delete(self):
        # Task groups can only be deleted it none of their subtasks
        # has been finished
        from cs.workflow.tasks import Task
        if self.status == TaskGroup.EXECUTION.status:
            for t in self.Tasks + self.TaskGroups:
                if t.status == Task.COMPLETED.status:
                    raise util.ErrorMessage("cdbwf_err113")
            for g in self.TaskGroups:
                g.allow_delete()

    def setReady(self):
        set_state(self, self.EXECUTION)

    def setDone(self):
        set_state(self, self.COMPLETED)

    def setNew(self):
        set_state(self, self.NEW)

    def setRefused(self, comment=""):
        set_state(self, self.REJECTED, comment=comment)

    def setCancelled(self, comment=""):
        set_state(self, self.DISCARDED, comment=comment)

    def stopReadyTasks(self):
        from cs.workflow.tasks import Task
        for t in self.Tasks:
            if t.status == Task.EXECUTION.status:
                t.setNew()

    def stop(self):
        if self.status == self.EXECUTION.status:
            self.stopReadyTasks()
            for tg in self.TaskGroups:
                if tg.stop():
                    tg.setNew()
            return True
        else:
            return False

    def notifyRefused(self, child, comment):
        self.setRefused(comment)

    def allDone(self):
        # FIXME: the implementation relies on a particular sequence
        # of the state numbers. Better would be an implementation
        # which does not require a particular sequence of state numbers.
        from cs.workflow.tasks import Task
        rset = sqlapi.RecordSet2(
            "cdbwf_task",
            (Task.parent_id == self.task_id)
            & (Task.cdb_process_id == self.cdb_process_id)
            & (Task.status < Task.COMPLETED.status),
            columns=["DISTINCT status"])
        return len(rset) == 0

    def allCancelled(self):
        from cs.workflow.tasks import Task

        if not self.Tasks and not self.TaskGroups:
            return False

        all_task_cancelled = not self.Tasks.Query(
            Task.status.not_one_of(Task.DISCARDED.status))

        all_task_groups_cancelled = not self.TaskGroups.Query(
            TaskGroup.status.not_one_of(TaskGroup.DISCARDED.status))

        return all_task_cancelled and all_task_groups_cancelled

    def get_last_tasks(self):
        """ Return a list of the tasks which cause this task group to be closed
            (i.e. the last tasks in this group).
        """
        raise NotImplementedError(IMPLEMENTED_BY_SUBCLASS)


class ParallelTaskGroup(TaskGroup):
    __classname__ = "cdbwf_aggregate_parallel"
    __match__ = fTaskGroup.cdb_classname >= __classname__

    # ==========================================================================
    # New interface
    # ==========================================================================

    def activate_subtasks(self):
        for component in self.Components:
            try:
                component.activate_task()
            except exceptions.TaskCancelledException:
                pass
            except exceptions.TaskClosedException:
                pass

        if self.allCancelled():
            raise exceptions.TaskCancelledException()

        if self.allDone():
            raise exceptions.TaskClosedException()

    def propagate_done(self, child):
        close = False

        if self.has_finish_option(child):
            self.cancel_subtasks()
            close = True
        elif self.allDone():
            close = True

        if close:
            self.close_task()
            if self.Parent:
                self.Parent.propagate_done(self)

    def propagate_cancel(self, child, comment=""):
        if self.allCancelled():
            self.cancel_task()
            if self.Parent:
                self.Parent.propagate_cancel(self)
        elif self.allDone():
            self.close_task()
            if self.Parent:
                self.Parent.propagate_done(self)

    # ==========================================================================
    # End new interface
    # ==========================================================================

    def is_sequential(self):
        return False

    def is_position_editable(self, position):
        """Check if the addition of a new task in the given position is allowed."""
        if self.status is None:
            return True
        if self.status > self.NEW.status:
            return False
        return True

    class EXECUTION(TaskGroup.EXECUTION):
        def post(state, self, ctx):  # @NoSelf
            super(ParallelTaskGroup.EXECUTION, state).post(self, ctx)

    def get_last_tasks(self):
        result = []
        for tg in self.Components:
            result.extend(tg.get_last_tasks())

        return result


class SequentialTaskGroup(TaskGroup):
    __classname__ = "cdbwf_aggregate_sequential"
    __match__ = fTaskGroup.cdb_classname >= __classname__

    # ==========================================================================
    # New interface
    # ==========================================================================

    def activate_subtasks(self):
        subtask = self.First

        # Information Tasks are closed immediately before starting.
        cycle = True
        while subtask and cycle:
            try:
                subtask.activate_task()
                cycle = False
            except exceptions.TaskClosedException:
                subtask = subtask.Next

        if not subtask:
            raise exceptions.TaskClosedException()

    def propagate_done(self, child):
        close = False

        if self.has_finish_option(child):
            self.cancel_subtasks()
            close = True
        elif not child.NextSibling:
            close = True
        else:
            try:
                child.NextSibling.activate_task()
            except exceptions.TaskCancelledException as ex:
                msg = str(ex)
                self.cancel_task(msg)
                if self.Parent:
                    self.Parent.propagate_cancel(self)

        if close:
            self.close_task()
            if self.Parent:
                self.Parent.propagate_done(self)

    def propagate_cancel(self, child, comment=""):
        # one of the children is cancelled
        # so cancel all the subtasks but close the current task
        self.cancel_subtasks(comment)
        self.close_task()
        if self.Parent:
            self.Parent.propagate_cancel(self, comment)

    # ==========================================================================
    # End new interface
    # ==========================================================================

    def is_sequential(self):
        return True

    class EXECUTION(TaskGroup.EXECUTION):
        def post(state, self, ctx):  # @NoSelf
            super(SequentialTaskGroup.EXECUTION, state).post(self, ctx)

    def is_position_editable(self, position):
        """Check if the addition of a new task in the given position is allowed."""

        from cs.workflow.tasks import Task

        # Check ordering, if parent is already running and task processing is
        # sequential
        if self.status > self.NEW.status:
            positions = self.Components.Query(
                (SchemaComponent.status > Task.NEW.status) &
                (SchemaComponent.position >= position))

            if positions:
                return False
        return True

    def get_last_tasks(self):
        if self.Components:
            pos = max(self.Components.position)
            comp = self.Components.KeywordQuery(position=pos)[0]
            return comp.get_last_tasks()
        else:
            return []


class ProcessCompletionTaskGroup(TaskGroup):
    """
    A ProcessCompletionTaskGroup is a special top level task group, which gets always
    started when a process is going to end:
    a) either after all other top level task groups have been done
    b) or after one top level task group has been refused.
    Only one ProcessCompletionTaskGroup per process is allowed.
    """

    __classname__ = "cdbwf_aggregate_proc_completion"
    __match__ = fTaskGroup.cdb_classname >= __classname__

    event_map = {
        (('copy', 'modify', 'delete'), 'pre'): "deny_copy_modify_delete"
    }

    # ==========================================================================
    # New interface
    # ==========================================================================

    def activate_subtasks(self):  # FIXME: Duplicate from ParallelTaskGroup
        for component in self.Components:
            try:
                component.activate_task()
            except exceptions.TaskCancelledException:
                pass
            except exceptions.TaskClosedException:
                pass

        if self.allCancelled():
            raise exceptions.TaskCancelledException()

        if self.allDone():
            raise exceptions.TaskClosedException()

    def propagate_done(self, child):
        close = True

        if self.has_finish_option(child):
            self.cancel_subtasks()
        else:
            # check if there's still a READY child
            for c in self.Components:
                if c.status == c.EXECUTION.status:
                    close = False
                    break

        if close:
            if self.Process.completing_ok:
                self.close_task()
                if self.Parent:
                    self.Parent.propagate_done(self)
            else:
                self.cancel_task()
                self.Parent.propagate_cancel(self)

    def propagate_cancel(self, child, comment=""):
        if self.allCancelled() or self.allDone():
            if self.Process.completing_ok:
                self.close_task()
                if self.Parent:
                    self.Parent.propagate_done(self)
            else:
                self.cancel_task()
                self.Parent.propagate_cancel(self)

    # ==========================================================================
    # End new interface
    # ==========================================================================

    def is_sequential(self):
        return False

    def is_position_editable(self, position):
        """Check if the addition of a new task in the given position is allowed."""
        if self.status > self.NEW.status:
            return False
        return True

    def get_last_tasks(self):
        result = []
        for tg in self.Components:
            result.extend(tg.get_last_tasks())

        return result

    class EXECUTION(TaskGroup.EXECUTION):
        def post(state, self, ctx):  # @NoSelf
            super(ProcessCompletionTaskGroup.EXECUTION, state).post(self, ctx)

    @classmethod
    def Create(cls, **kwargs):
        if "cdb_process_id" in list(kwargs) \
           and cls.KeywordQuery(cdb_process_id=kwargs["cdb_process_id"]) != []:
            # don't allow multiple completion task groups per process
            raise Exception("There already exists a completion task for the given process")

        if not kwargs.get("cdb_extension_class", None):
            kwargs["cdb_extension_class"] = ""

        return super(ProcessCompletionTaskGroup, cls).Create(**kwargs)

    @classmethod
    def create_for_process(cls, process):
        from cs.workflow.tasks import Task
        return cls.Create(**{"cdb_process_id": process.cdb_process_id,
                             "task_id": Task.new_task_id(),
                             "cdb_classname": cls.__classname__,
                             "status": TaskGroup.NEW.status,
                             "cdb_objektart": TaskGroup.__obj_class__,
                             "title": "Process completion"})

    @classmethod
    def ensure_exists_for_process(cls, process):
        if process.ProcessCompletion is None:
            cls.create_for_process(process)

    def deny_copy_modify_delete(self, ctx):
        # Deny modifying
        # also deny deleting and copying if not deleting and copying process
        # TODO: somehow deny changing the task group type, too
        if ctx.relationship_name == "cdbwf_process2process_completion" and \
           ctx.action == "copy" and \
           ctx.interactive == 0:
            return
        if ctx.action == "delete" and \
           ctx.interactive == 0 and \
           "cdbwf_force_delete" in ctx.sys_args.get_attribute_names():
            return
        raise ue.Exception("cdbwf_copy_modify_delete_proc_compl_not_allowed")


# obsolete status classes
TaskGroup.READY = TaskGroup.EXECUTION
TaskGroup.DONE = TaskGroup.COMPLETED
TaskGroup.REFUSED = TaskGroup.REJECTED
TaskGroup.CANCELLED = TaskGroup.DISCARDED
ParallelTaskGroup.READY = ParallelTaskGroup.EXECUTION
SequentialTaskGroup.READY = SequentialTaskGroup.EXECUTION
ProcessCompletionTaskGroup.READY = ProcessCompletionTaskGroup.EXECUTION
