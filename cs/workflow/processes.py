#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This module contains the cdb.objects class of the workflow.
"""

import datetime

from cdb import ue
from cdb import auth
from cdb import util
from cdb import sqlapi
from cdb import transactions
from cdb import constants
from cdb import i18n
from cdb import misc

from cdb.objects import ByID
from cdb.objects import org
from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMapping_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import Rule
from cdb.objects import State
from cdb.objects import Transition
from cdb.objects import operations

from cdb.platform import gui, FolderContent
from cdb.platform import mom
from cdb import tools

from cs.workflow.misc import calc_deadline, is_csweb
from cs.workflow.misc import get_state_text
from cs.workflow.misc import set_state
from cs.workflow.misc import Link
from cs.workflow.misc import require_feature_viewing
from cs.workflow.misc import require_feature_templating

from cs.workflow.process_template import _cdbwf_ahwf_new_from_template

from cs.workflow import protocols
from cs.workflow import briefcases
from cs.workflow import exceptions
from cs.workflow import structure
from cs.sharing.share_objects import WithSharing

try:
    from cs.tools.powerreports import WithPowerReports
except ImportError:
    WithPowerReports = object

__all__ = ['Process']

fProcess = Forward(__name__ + ".Process")
fProcessPyruleAssignment = Forward(__name__ + ".ProcessPyruleAssignment")

fConstraint = Forward("cs.workflow.constraints.Constraint")
fSchemaComponent = Forward("cs.workflow.schemacomponents.SchemaComponent")
fTaskGroup = Forward("cs.workflow.taskgroups.TaskGroup")
fTask = Forward("cs.workflow.tasks.Task")
fBriefcase = Forward("cs.workflow.briefcases.Briefcase")
fBriefcaseLink = Forward("cs.workflow.briefcases.BriefcaseLink")
fProtocol = Forward("cs.workflow.protocols.Protocol")
fRule = Forward("cdb.objects.Rule")
fInfoMessage = Forward("cs.workflow.systemtasks.InfoMessage")
fUser = Forward("cdb.objects.org.User")


def get_root_process_cte():
    pass


class Process(org.WithSubject, briefcases.WithBriefcase, WithSharing, WithPowerReports):
    __maps_to__ = "cdbwf_process"
    __classname__ = "cdbwf_process"
    __obj_class__ = "cdbwf_process"

    TaskGroups = Reference_N(fTaskGroup,
                             fTaskGroup.cdb_process_id == fProcess.cdb_process_id,
                             fTaskGroup.parent_id == '',
                             fTaskGroup.cdb_classname != "cdbwf_aggregate_proc_completion",
                             order_by=fTaskGroup.position)

    Tasks = Reference_N(fTask,
                        fTask.cdb_process_id == fProcess.cdb_process_id,
                        fTask.parent_id == '',
                        order_by=fTaskGroup.position)
    # all top level tasks of current workflow

    Components = Reference_N(fSchemaComponent,
                             fSchemaComponent.cdb_process_id == fProcess.cdb_process_id,
                             fSchemaComponent.parent_id == '',
                             fSchemaComponent.cdb_classname != "cdbwf_aggregate_proc_completion",
                             order_by=fSchemaComponent.position)

    Protocols = Reference_N(fProtocol,
                            fProtocol.cdb_process_id == fProcess.cdb_process_id)

    # Queries below are intentionally unordered, because we want
    # to get all components from the schema tree, and ordering
    # does not make any sense.
    AllTaskGroups = Reference_N(fTaskGroup,
                                fTaskGroup.cdb_process_id == fProcess.cdb_process_id)

    def _ProcessCompletion(self):
        from cs.workflow.taskgroups import ProcessCompletionTaskGroup
        pctg = ProcessCompletionTaskGroup.KeywordQuery(
            cdb_process_id=self.cdb_process_id,
            cdb_classname=ProcessCompletionTaskGroup.__classname__)
        return pctg[0] if (pctg != []) else None
    ProcessCompletion = ReferenceMethods_1(fTaskGroup, lambda self: self._ProcessCompletion())

    AllTasks = Reference_N(fTask, fTask.cdb_process_id == fProcess.cdb_process_id)
    # all tasks of current workflow, no matter on which level

    AllComponents = Reference_N(fSchemaComponent,
                                fSchemaComponent.cdb_process_id == fProcess.cdb_process_id)

    # References to briefcases
    BriefcaseLinksByType = ReferenceMapping_N(
        fBriefcaseLink,
        (fBriefcaseLink.cdb_process_id == fTask.cdb_process_id) &
        (fBriefcaseLink.task_id == ''),
        indexed_by=fBriefcaseLink.iotype)

    AllBriefcaseLinksByType = ReferenceMapping_N(
        fBriefcaseLink,
        fBriefcaseLink.cdb_process_id == fTask.cdb_process_id,
        indexed_by=fBriefcaseLink.iotype)

    AllBriefcaseLinks = Reference_N(
        fBriefcaseLink,
        fBriefcaseLink.cdb_process_id == fProcess.cdb_process_id)

    BriefcaseLinks = Reference_N(fBriefcaseLink,
                                 fBriefcaseLink.cdb_process_id == fProcess.cdb_process_id,
                                 fBriefcaseLink.task_id == '')

    AllBriefcases = Reference_N(fBriefcase,
                                fBriefcase.cdb_process_id == fProcess.cdb_process_id)

    # References to the content of the process and every task
    def _getAllContent(self, iotype):
        return self.getContent(iotype, "AllBriefcaseLinksByType")

    AllInfoContent = ReferenceMethods_N(Object, lambda self: self._getAllContent("info"))
    AllEditContent = ReferenceMethods_N(Object, lambda self: self._getAllContent("edit"))
    AllContent = ReferenceMethods_N(Object, lambda self: self._getAllContent("all"))

    # Direct process constraints
    Constraints = Reference_N(fConstraint,
                              fConstraint.cdb_process_id == fSchemaComponent.cdb_process_id,
                              fConstraint.task_id == '')

    # All process and component constraints
    AllConstraints = Reference_N(fConstraint,
                                 fConstraint.cdb_process_id == fSchemaComponent.cdb_process_id)

    AttachmentsBriefcase = Reference_1(fBriefcase,
                                       fBriefcase.cdb_process_id == fProcess.cdb_process_id,
                                       fBriefcase.briefcase_id == 0)

    StartedBy = Reference_1(fUser, fProcess.started_by)

    def _get_parent_task(self):
        if self.parent_task_object_id:
            return ByID(self.parent_task_object_id)
        return None

    ParentTask = ReferenceMethods_1(fTask, _get_parent_task)

    def _get_parent_process(self):
        parent_task = self.ParentTask
        if parent_task:
            return parent_task.Process
        return None

    ParentProcess = ReferenceMethods_1(fProcess, _get_parent_process)

    def _get_root_process(self):
        pattern = structure.get_query_pattern("root_process")
        cte = pattern.format(self.cdb_process_id)
        for root in sqlapi.RecordSet2(sql=cte):
            return fProcess.ByKeys(root.cdb_process_id)

    RootProcess = ReferenceMethods_1(fProcess, _get_root_process)

    def _get_terminated_parents(self):
        pattern = structure.get_query_pattern("terminated_parents")
        cte = pattern.format(self.cdb_process_id)
        parent_ids = [
            parent.cdb_process_id
            for parent in sqlapi.RecordSet2(sql=cte)
        ]
        return fProcess.KeywordQuery(cdb_process_id=parent_ids)

    TerminatedParents = ReferenceMethods_1(fProcess, _get_terminated_parents)

    def _get_siblings(self):
        parent_task = self.ParentTask
        if parent_task:
            return parent_task.Cycles
        return []

    CycleSiblings = ReferenceMethods_N(fProcess, _get_siblings)

    def _get_cycles(self):
        return Process.Query(
            """parent_task_object_id IN (
                SELECT cdb_object_id
                FROM cdbwf_task
                WHERE cdb_process_id='{}'
            )""".format(self.cdb_process_id),
            addtl="ORDER BY current_cycle ASC"
        )

    Cycles = ReferenceMethods_N(fProcess, _get_cycles)

    event_map = {
        (('create', 'copy'), 'pre_mask'): ("set_template_access"),
        (('create', 'copy'), 'pre'): ("make_process_id", "setObjektArt"),
        (('create', 'copy'), 'post'): "set_follow_up",
        (('create'), 'post'): ('ensure_process_completion', 'make_attachments_briefcase',
                               'setup_ahwf'),
        (('create', 'copy', 'modify'), 'pre'): "check_max_duration",
        (('create', 'copy', 'modify'), 'post'): "update_cdb_project_id",
        ('modify', 'pre_mask'): "disable_template",
        ('cdbwf_start_workflow', 'now'): 'op_activate_process',
        ('cdbwf_onhold_workflow', 'now'): 'op_onhold_process',
        ('cdbwf_cancel_workflow', 'now'): 'op_cancel_process',
        ('cdbwf_dismiss_workflow', 'now'): 'op_dismiss_process',
        ('relship_copy', 'post'): 'deep_copy_briefcases',
        ('delete', 'pre'): ('deep_delete_briefcases', 'deep_delete_components'),
        ('copy', 'pre_mask'): 'reset_id',
        ('copy', 'pre'): 'check_copy_from_template',
        (("create", "copy"), "dialogitem_change"): "template_box_changed"
    }

    def set_template_access(self, ctx):
        """
        Updates ``self.is_template`` and sets the template checkbox as:

        - Unchecked as the initial state (by configuration).
        - Disabled if the user has no access to create templates.
        """
        self.disable_process_id(ctx)
        tempProcess = Process(is_template=1, status=0)
        if not tempProcess.CheckAccess("create"):
            ctx.set_readonly("is_template")

    @staticmethod
    def template_changed_hook(hook):
        new_value = hook.get_new_value("is_template")
        if new_value == 1:
            hook.set_readonly("cdbwf_process.start_date")
            hook.set_readonly("cdbwf_process.deadline")
            hook.set_writeable("cdbwf_process.cdb_process_id")
        else:
            hook.set_writeable("cdbwf_process.start_date")
            hook.set_writeable("cdbwf_process.deadline")
            hook.set_readonly("cdbwf_process.cdb_process_id")

    def template_box_changed(self, ctx):
        if ctx.changed_item == "is_template":
            if ctx.dialog.is_template == "1":
                ctx.set_readonly("start_date")
                ctx.set_readonly("deadline")
                self.enable_process_id(ctx)
            else:
                ctx.set_writeable("start_date")
                ctx.set_writeable("deadline")
                self.cdb_process_id = ""
                self.disable_process_id(ctx)

    def disable_process_id(self, ctx):
        ctx.set_readonly("cdb_process_id")
        ctx.set_optional("cdb_process_id")

    def enable_process_id(self, ctx):
        ctx.set_writeable("cdb_process_id")
        ctx.set_optional("cdb_process_id")

    def lock_is_template(self, ctx):
        # deprecated
        self.is_template = ctx.cdbtemplate.is_template
        ctx.set_readonly("is_template")

    def getWorkflowDesignerURL(self):
        from cs.workflow.designer import WorkflowDesigner
        return "{}?cdb_process_id={}".format(WorkflowDesigner.getModuleURL(),
                                             self.cdb_process_id)

    def set_follow_up(self, ctx):
        if ctx.error:
            return
        if not ctx.uses_webui:
            ctx.set_followUpOperation("cdbwf_start_workflow_designer",
                                      use_result=True)

    def op_activate_process(self, ctx=None):
        if self.status != self.EXECUTION.status:
            if self.isTemplate():
                raise ue.Exception("cdbwf_operation_template_not_allowed")
            if self.status != self.NEW.status and self.status != self.PAUSED.status:
                raise ue.Exception("cdbwf_process_not_activable")
            if self.ParentProcess:
                raise ue.Exception("cdbwf_process_has_parent_process")
            self.activate_process()

    def op_onhold_process(self, ctx=None):
        if self.status != self.PAUSED.status:
            if self.isTemplate():
                raise ue.Exception("cdbwf_operation_template_not_allowed")
            if self.status != self.EXECUTION.status:
                raise ue.Exception("cdbwf_process_not_holdable")
            self.onhold_process()

    def op_cancel_process(self, ctx=None):
        if self.status != self.FAILED.status:
            if self.isTemplate():
                raise ue.Exception("cdbwf_operation_template_not_allowed")
            if self.status not in [self.NEW.status, self.EXECUTION.status]:
                raise util.ErrorMessage("cdbwf_process_not_cancelable")
            else:
                self.cancel_process()

    def op_dismiss_process(self, ctx=None):
        if self.status != self.DISCARDED.status:
            if self.isTemplate():
                raise ue.Exception("cdbwf_operation_template_not_allowed")
            if self.status not in [self.NEW.status, self.FAILED.status]:
                raise util.ErrorMessage("cdbwf_process_not_dismissable")
            else:
                self.dismiss_process()

    def setup_ahwf(self, ctx):
        if set(["ahwf_classpath", "ahwf_content"]) <= \
                set(ctx.sys_args.get_attribute_names()):
            classpath = ctx.sys_args.ahwf_classpath
            cdbclass = tools.getObjectByName(classpath)

            object_ids = ctx.sys_args.ahwf_content.split(";")
            objects = cdbclass.Query(cdbclass.cdb_object_id.one_of(*object_ids))

            cdbclass.setup_ahwf(self.getPersistentObject(), objects, False)

    def handleSubscriptions(self):
        if (self.status == self.EXECUTION.status and
                self.GetClassDef().isActivityChannel()):
            from cs.activitystream.objects import Subscription
            for person in self.Subject.getPersons():
                Subscription.subscribeToChannel(
                    self.cdb_object_id,
                    person.personalnummer
                )

    # ===========================================================================
    # New interface
    # ===========================================================================

    def activate_process(self):
        """
        Start the current workflow.
        The tasks would be set to ready if possible.
        """
        try:
            require_feature_viewing()
            if self.status == self.PAUSED.status:
                self.setReady()
            else:
                # check constraints on process and global briefcases
                if self.Constraints:
                    self.addProtocol(
                        str(
                            util.get_label("cdbwf_process_starting")
                        ),
                        protocols.MSGSYSTEM)
                    for constraint in self.Constraints:
                        constraint.check_violation(self)

                self.set_briefcase_rights()

                self.update_change_log()

                self.setReady()

                # Subscribe to activity stream
                self.handleSubscriptions()

                if self.Components:
                    self.activate_tasks()
                else:
                    self.close_process()
        except exceptions.TaskCancelledException as ex:
            msg = str(ex)
            self.cancel_subtasks_and_close(msg)
        except RuntimeError as ex:
            raise ue.Exception(1024, str(ex))

    def onhold_process(self):
        """
        Hold on the current workflow.
        Do not reset the state of the tasks.
        """
        try:
            require_feature_viewing()
            self.setOnhold()
        except RuntimeError as ex:
            raise ue.Exception(1024, str(ex))

    def get_cancel_info_setting(self):
        cancel = util.PersonalSettings().getValueOrDefault(
            "cs.workflow",
            "cancel_info_on_failure",
            None)
        return cancel == "1"

    def _cancel_info_messages(self):
        with transactions.Transaction():
            info = fInfoMessage.KeywordQuery(
                cdb_process_id=self.cdb_process_id)

            if self.ProcessCompletion:
                completion_info = self.ProcessCompletion.AllTasks.task_id
                info = info.Query("task_id NOT IN ('{}')".format(
                    "', '".join(completion_info)))

            info.Update(is_active=0)
            self.addProtocol(
                str(util.get_label("cdbwf_cancel_info_messages")),
                protocols.MSGINFO)

    def cancel_info_messages(self):
        if self.get_cancel_info_setting():
            self._cancel_info_messages()

    def cancel_process(self, comment=""):
        """
        Cancel the current workflows.
        The `completion` tasks would be activated if exist.
        """
        require_feature_viewing()
        self.Update(completing_ok=0)
        from cs.workflow.taskgroups import TaskGroup
        components = self.Components.Query(
            fSchemaComponent.status.one_of(TaskGroup.EXECUTION.status,
                                           TaskGroup.NEW.status))

        for component in components:
            component.cancel_task(comment)

        self.cancel_info_messages()

        try:
            if self.ProcessCompletion and \
               (self.ProcessCompletion.status == self.ProcessCompletion.NEW.status):
                self.ProcessCompletion.activate_task()
            else:
                self.setCancelled(comment)
        except (exceptions.TaskCancelledException, exceptions.TaskClosedException):
            self.setCancelled(comment)
        except RuntimeError as ex:
            raise ue.Exception(1024, str(ex))

    def dismiss_process(self):
        """
        Dismiss the current workflow.
        The `completion` tasks would be cancelled.
        """
        require_feature_viewing()
        self.Update(completing_ok=0)
        from cs.workflow.taskgroups import TaskGroup
        components = self.Components.Query(
            fSchemaComponent.status.one_of(TaskGroup.EXECUTION.status,
                                           TaskGroup.NEW.status))

        for component in components:
            component.cancel_task()

        self.cancel_info_messages()

        if self.ProcessCompletion and self.ProcessCompletion.status in [
                self.ProcessCompletion.NEW.status,
                self.ProcessCompletion.EXECUTION.status,
        ]:
            self.ProcessCompletion.cancel_task()

        try:
            self.setDismissed()
        except RuntimeError as ex:
            raise ue.Exception(1024, str(ex))

    def close_process(self):
        """
        Attempts to close the workflow.
        The `completion` tasks would be activated if exist.
        """
        try:
            require_feature_viewing()
            if self.ProcessCompletion and \
               (self.ProcessCompletion.status == self.ProcessCompletion.NEW.status):
                self.ProcessCompletion.activate_task()
            else:
                self.setDone()
        except (exceptions.TaskCancelledException, exceptions.TaskClosedException):
            self.setDone()
        except RuntimeError as ex:
            raise ue.Exception(1024, str(ex))

    def cancel_subtasks_and_close(self, comment=""):
        """
        Attempts to cancel the subtasks and then
        closing the workflow.
        """
        from cs.workflow.taskgroups import TaskGroup
        components = self.Components.Query(
            fSchemaComponent.status.one_of(TaskGroup.READY.status,
                                           TaskGroup.NEW.status))

        for component in components:
            component.cancel_task(comment)

        self.close_process()

    def activate_tasks(self):
        require_feature_viewing()
        components = self.Components
        if components:
            first = components[0]
            first.activate_task()

    def propagate_done(self, child):
        from cs.workflow.taskgroups import TaskGroup

        if TaskGroup.has_finish_option(child):
            # cancel running and new tasks
            components = self.Components.KeywordQuery(status=[
                TaskGroup.EXECUTION.status,
                TaskGroup.NEW.status,
            ])
            for component in components:
                component.cancel_task()

            self.close_process()
        else:
            try:
                next_sibling = child.Next
                cycle = True

                while next_sibling and cycle:
                    try:
                        next_sibling.activate_task()
                        cycle = False
                    except exceptions.TaskClosedException:
                        next_sibling = next_sibling.Next

                if not next_sibling:
                    self.close_process()
            except exceptions.TaskCancelledException as ex:
                msg = str(ex)
                self.cancel_subtasks_and_close(msg)

    def propagate_onhold(self, child):
        self.onhold_process()

    def propagate_cancel(self, child, comment=""):
        if self.completing_ok:
            # one of the child task group is skipped
            # due to unmet constraints, but the workflow
            # should run
            self.propagate_done(child)
        else:  # if the process is already canceled then cancel
            self.cancel_process(comment)

    def propagate_refuse(self, child, comment=""):
        self.cancel_process(comment)

    # ===========================================================================
    # End new interface
    # ===========================================================================

    def is_sequential(self):
        return True

    def is_parallel(self):
        return False

    def newCycle(self):
        """
        Increases the parent task's ``current_cycle`` parameter by one and
        enqueues it to be run by the WFService again. Logs an error message to
        the parent process if the parent process was not waiting for this
        cycle.

        .. warning::
            The caller of this method has to ensure the workflow has a parent
            task (e.g. it is a cycle).

        """
        from cs.workflow.tasks import Task
        from cs.workflow import wfqueue

        if (
                self.ParentTask.status == Task.EXECUTION.status
                and self.ParentProcess.status == Process.EXECUTION.status
        ):
            task_cycle = self.ParentTask.AllParameters.KeywordQuery(
                name='current_cycle'
            )
            if task_cycle:
                # increase current_cycle
                old_value = int(task_cycle[0].value)
                task_cycle[0].Update(
                    value=(old_value + 1)
                )
            # execute run loop system task again
            wfqueue.wfqueue.put(
                cdb_process_id=self.ParentTask.cdb_process_id,
                task_id=self.ParentTask.task_id
            )
        else:
            self.ParentTask.addProtocol(
                util.get_label("cdbwf_cycle_parent_closed")
                % (self.current_cycle, self.cdb_process_id)
            )

    class NEW(State):
        status = 0

        def pre(state, self, ctx):  # @NoSelf
            self._reset_schema()

        def post(statem, self, ctx):  # @NoSelf
            if not ctx.error and self.isTemplate():
                for cycle in self.Cycles.KeywordQuery(status=[self.REVIEW.status,
                                                              self.COMPLETED.status]):
                    cycle.setNew()

    def get_violated_process_start_preconditions(self):
        from cs.workflow.tasks import TaskDataIncompleteException
        errmsgs = []
        for task in self.AllTasks:
            try:
                task.check_process_start_preconditions()
            except TaskDataIncompleteException as e:
                errmsgs.append((task, str(e)))

        if errmsgs:
            return "\n".join([
                "%s %s: %s" % (task.AbsolutePath(), task.title, errmsg)
                for (task, errmsg) in errmsgs
            ])

        return ""

    def check_process_start_preconditions(self):
        msg = self.get_violated_process_start_preconditions()
        if msg:
            raise util.ErrorMessage("cdbwf_err102", msg)

    class EXECUTION(State):
        status = 10

        def pre(state, self, ctx):  # @NoSelf
            for briefcase in self.AllBriefcaseLinks:
                try:
                    briefcase.check_obj_rights(ctx)
                except ue.Exception as ex:
                    msg = ''.join(str(x) for x in ex.errp[0])
                    briefcase.Process.addProtocol(msg)

            # Check project roles, if cs.pcs installed
            if hasattr(self, "_check_project_roles"):
                self._check_project_roles()

            self.check_process_start_preconditions()

            # Set the title, for those tasks which don't have one
            # Check that every task has a title
            from cs.workflow import tasks
            condition = (tasks.Task.title == '') | (tasks.Task.title == None)
            for task in self.AllTasks.Query(condition):
                task.set_title()

            # set start date and deadline
            self.start_date = datetime.date.today()
            calc_deadline(self)

            # Reset everything to NEW here if not recovered from on hold
            if int(ctx.old.status) != self.PAUSED.status:
                self._reset_schema()

        def post(state, self, ctx):  # @NoSelf
            self.addProtocol(
                str(util.get_label("cdbwf_process_started")),
                protocols.MSGSYSTEM)
            if int(ctx.old.status) == self.PAUSED.status:
                self.AllComponents.Update(process_is_onhold=0)

                for cycle in self.Cycles.KeywordQuery(status=self.PAUSED.status):
                    cycle.setReady()

                # re-enqueue system task jobs
                from cs.workflow.tasks import SystemTask
                from cs.workflow import wfqueue

                for systask in self.AllTasks.KeywordQuery(
                    status=SystemTask.EXECUTION.status,
                    cdb_classname=SystemTask.__classname__,
                ):
                    wfqueue.wfqueue.put(
                        cdb_process_id=self.cdb_process_id,
                        task_id=systask.task_id,
                    )

    class TERMINATE(Transition):
        transition = (10, "*")

        def post(state, self, ctx):  # @NoSelf
            if ctx.error:
                return

            # sync AS to parent on termination
            if state.state_to != self.PAUSED.status and self.ParentProcess:
                from cs.workflow.run_loop import add_activity_topic
                add_activity_topic(self, self.ParentProcess)

    class COMPLETED(State):  # or RELEASED (template)
        status = 20

        def pre(state, self, ctx):  # @NoSelf
            if self.isTemplate():
                lbl = util.get_label("cdbwf_process_template_approved")
                msg = protocols.MSGAPPROVED
            else:
                lbl = util.get_label("cdbwf_process_done")
                msg = protocols.MSGDONE
            self.addProtocol("%s " % lbl, msg)

        def post(state, self, ctx):  # @NoSelf
            if not ctx.error and self.ParentTask and not self.isTemplate():
                self.newCycle()
            if not ctx.error and self.isTemplate():
                for cycle in self.Cycles.KeywordQuery(status=self.REVIEW.status):
                    cycle.setDone()

    class FAILED(State):
        status = 30

        def pre(state, self, ctx):  # @NoSelf
            comment = getattr(ctx.dialog, 'comment', '')
            # intentionally using MSGREFUSE instead of MSGCANCEL
            lbl = util.get_label("cdbwf_process_cancelled")
            self.addProtocol("%s \n%s" % (lbl, comment), protocols.MSGREFUSE)

        def post(state, self, ctx):  # @NoSelf
            if int(ctx.old.status) == self.PAUSED.status:
                self.AllComponents.Update(process_is_onhold=0)
            if not ctx.error and self.ParentTask:
                self.newCycle()

    class DISCARDED(State):  # or INVALID (template)
        status = 40

        def pre(state, self, ctx):  # @NoSelf
            self.addProtocol(
                str(util.get_label("cdbwf_process_discarded")),
                protocols.MSGREFUSE)

        def post(state, self, ctx):  # @NoSelf
            if not ctx.error and self.isTemplate():
                for cycle in self.Cycles.KeywordQuery(status=[self.NEW.status,
                                                              self.COMPLETED.status,
                                                              self.REVIEW.status]):
                    cycle.setDismissed()

    class PAUSED(State):
        status = 50

        def pre(state, self, ctx):  # @NoSelf
            self.addProtocol(
                str(util.get_label("cdbwf_process_on_hold")),
                protocols.MSGSYSTEM)
            self.AllComponents.Update(process_is_onhold=1)

        def post(state, self, ctx):  # @NoSelf
            for cycle in self.Cycles.KeywordQuery(status=self.EXECUTION.status):
                cycle.setOnhold()

    class REVIEW(State):
        status = 100

        def post(state, self, ctx):  # @NoSelf
            if not ctx.error:
                for cycle in self.Cycles.KeywordQuery(status=self.NEW.status):
                    cycle.setReview()

    def on_cdbwf_start_workflow_designer_now(self, ctx):
        ctx.url(self.getWorkflowDesignerURL())

    def setObjektArt(self, ctx):
        self.cdb_objektart = self.GetObjectKind()

    def GetObjectKind(self):
        obj_art = self.GetClassname()
        if self.isTemplate():
            obj_art += '_template'
        return obj_art

    def GetStateText(self, state, lang=None):
        if lang is None:
            lang = i18n.default()

        return get_state_text(self.GetObjectKind(), state.status, lang)

    @classmethod
    def CreateFromTemplate(cls, template_id, defaults=None, ahwf_content="", ctx=None, keep_owner = False):
        """
        Creates a new process from an existing template.  

        :param cls: Represents the Process class.
        :param template_id: The ID of the template process to be used for creatig the new process.
        :param defaults: (Optonal) The dictionary of default values for the new process. The default is ``None``
        :param ahwf_content: (Optional) A string representing additional content of the workflow for the new process. The default is an emtpy string.
        :param ctx: (Optional) The context of the action. This is ``None`` per default.
        :param keep_owner: (Optional) A flag indicating if the author of the template process must be overwritten by the current user. 
                          The default value is ``False``. If ``True`` the author of the template will be kept for the new process.

        :raises ErrorMessage: If the template for the new process is nonexistent
        :raises ValueError: If either one of ``subject_id`` or ``subject_type`` but not both or none are provided.

        :return: If the ``ctx`` is provided it sets up a follow up operation for that context to copy the existing template with the 
                 given arguments. Otherwise it returns an ``operations.operation`` object, which represents the copy operation of the 
                 template with the given arguments.
        """
        
        args = defaults or {}
        args["is_template"] = "0"
        args["cdb_objektart"] = "cdbwf_process"

        template = Process.ByKeys(template_id)
        
        if template is None:
            raise util.ErrorMessage("cdbwf_err116", template_id)
        
        # check if both or none subject_id and subject_type are provided
        if ("subject_id" in args) != ("subject_type" in args):
            raise ValueError("subject_id and subject_type must be consistent")

        if keep_owner:
            args["subject_id"] = template.subject_id
            args["subject_type"] = template.subject_type
        
        if not keep_owner and "subject_id" not in args:
            args["subject_id"] = auth.persno
            args["subject_type"] = "Person"
                
        if ctx is not None:
            ctx.set_followUpOperation("CDB_Copy",
                                      predefined=args.items(),
                                      opargs=[("uses_create_from_template", True),
                                              ("ahwf_content", ','.join(ahwf_content))],
                                      keep_rship_context=False,
                                      op_object=template)
        else:
            return operations.operation(constants.kOperationCopy, template, **args)
        return None

    @classmethod
    def new_process_id(cls):
        return "P%08d" % util.nextval("cdbwf_process.cdb_process_id")

    @classmethod
    def new_template_id(cls):
        return "PT%08d" % util.nextval("cdbwf_process.cdb_process_id_template")

    @classmethod
    def on_cdbwf_ahwf_new_from_template_now(cls, ctx):
        _cdbwf_ahwf_new_from_template(cls, ctx)

    @classmethod
    def on_copy_post(cls, ctx=None):
        if is_csweb():
            if "uses_create_from_template" in ctx.sys_args.get_attribute_names():
                ctx.keep("ahwf_content", getattr(ctx.sys_args, "ahwf_content"))
                ctx.keep("context_object_id", getattr(ctx.sys_args, "context_object_id"))
        else:
            if "uses_create_from_template" in ctx.ue_args.get_attribute_names():
                template_id = getattr(ctx.cdbtemplate, "cdb_process_id")
                new_process = Process.ByKeys(getattr(ctx.object, "cdb_process_id"))
                new_process.addProtocol(util.get_label("cdbwf_process_from_template").format(template_id))


    @classmethod
    def add_attachments(cls, ctx):
        new_process = Process.ByKeys(getattr(ctx.object, "cdb_process_id"))
        if new_process.AttachmentsBriefcase is None:
            new_process.make_attachments_briefcase()
        ahwf_content_str = getattr(ctx.ue_args, "ahwf_content", None)
        context_object_id = getattr(ctx.ue_args, "context_object_id", None)
        if ahwf_content_str:
            ahwf_content = ahwf_content_str.split(",")
            objects = [ByID(uuid) for uuid in ahwf_content]
            briefcases.BriefcaseContent.setup_ahwf(new_process, objects, False)
        elif context_object_id:
            briefcase = new_process.AttachmentsBriefcase
            FolderContent.Create(cdb_folder_id=briefcase.cdb_object_id,
                                 cdb_content_id=context_object_id)

    @classmethod
    def on_cdbwf_new_process_from_template_now(cls, ctx):
        vals = {"cdb_project_id": ctx.dialog.cdb_project_id, "title": ctx.dialog.title}
        new_process = cls.CreateFromTemplate(ctx.dialog.cdb_process_id, defaults=vals)
        return new_process.Open(action="cdbwf_start_workflow_designer", plain=1)

    def on_wf_step_post(self, ctx):
        ctx.refresh_tables(['cdbwf_task'])

    def on_relship_copy_post(self, ctx):
        if ctx.relationship_name == 'cdbwf_p2task':
            from cs.workflow.tasks import Task
            self.AllTasks.Update(status=Task.NEW.status,
                                 cdb_status_txt=Task.GetStateText(Task.NEW),
                                 start_date='',
                                 end_date_act='',
                                 cdb_project_id=self.cdb_project_id)
        elif ctx.relationship_name == 'cdbwf_p2aggr2':
            from cs.workflow.taskgroups import TaskGroup
            self.AllTaskGroups.Update(
                status=TaskGroup.NEW.status,
                cdb_status_txt=TaskGroup.GetStateText(TaskGroup.NEW),
                cdb_project_id=self.cdb_project_id)

    def on_copy_pre(self, ctx):
        calc_deadline(self)

    def on_create_pre_mask(self, ctx):
        self.subject_type = 'Person'
        self.subject_id = auth.persno

    def on_copy_pre_mask(self, ctx):
        if self.subject_type == '':
            self.subject_type = 'Person'
            self.subject_id = auth.persno

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    def on_state_change_pre_mask(self, ctx):
        self.Super(Process).on_state_change_pre_mask(ctx)

        # Templates must not be set ready
        if self.isTemplate() and self.ParentTask and ctx.batch == 0:
            for state in ctx.statelist:
                ctx.excl_state(state)
        elif self.isTemplate() and self.status == 0:
            ctx.excl_state(10)

    def make_attachments_briefcase(self, ctx=None):
        if not self.AttachmentsBriefcase:
            briefcases.Briefcase.Create(cdb_process_id=self.cdb_process_id,
                                        briefcase_id=0,
                                        name=util.get_label("cdbwf_attachments"))
            briefcases.set_briefcase_count()

            briefcases.BriefcaseLink.Create(
                cdb_process_id=self.cdb_process_id,
                task_id='',
                briefcase_id=0,
                iotype=briefcases.IOType.info.value,  # @UndefinedVariable
                extends_rights=0)
            self.Reload()

    def reset_id(self, ctx):
        ctx.set("cdb_process_id", "")

    def make_process_id(self, ctx):
        """
        Updates ``self.cdb_process_id`` with a generated one if

        - The workflow is not a template or
        - The workflow is a template and ``self.cdb_process_id`` is empty.

        .. note ::
           When copying a workflow template, make sure to change its ID.
        """
        if self.isTemplate():
            if (
                (ctx.action == "copy" and not ctx.interactive) or
                self.cdb_process_id in [None, "", "#"]
                ):
                self.cdb_process_id = self.new_template_id()
        else:
            self.cdb_process_id = self.new_process_id()

    def ensure_process_completion(self, ctx=None):
        from cs.workflow.taskgroups import ProcessCompletionTaskGroup
        ProcessCompletionTaskGroup.ensure_exists_for_process(self)

    def check_max_duration(self, ctx):
        if self.max_duration is not None and self.max_duration < 1:
            raise ue.Exception("cdbwf_max_duration_greater_0")

    def update_cdb_project_id(self, ctx=None):
        def _update_pid(process, new_project_id):
            process.Update(cdb_project_id=new_project_id)
            process.AllComponents.Update(cdb_project_id=new_project_id)
            for cycle in process.Cycles:
                _update_pid(cycle, new_project_id)

        _update_pid(self, self.cdb_project_id)

    def deep_copy_briefcases(self, ctx):
        if ctx.relationship_name == 'cdbwf_process2briefcase':
            old_briefcases = briefcases.Briefcase.KeywordQuery(
                cdb_process_id=ctx.cdbtemplate.cdb_process_id)
            for old_briefcase in old_briefcases:
                new_briefcase = briefcases.Briefcase.ByKeys(
                    cdb_process_id=ctx.object.cdb_process_id,
                    briefcase_id=old_briefcase.briefcase_id)
                for content in old_briefcase.FolderContents:
                    content.copy_briefcase_contents(new_briefcase)
            self.add_attachments(ctx)

    def deep_delete_briefcases(self, ctx):
        old_briefcases = briefcases.Briefcase.KeywordQuery(
            cdb_process_id=ctx.object.cdb_process_id)
        for briefcase in old_briefcases:
            for link in briefcase.Links:
                link.Delete()
            for content in briefcase.FolderContents:
                content.Delete()

    def disable_template(self, ctx):
        ctx.set_readonly("is_template")

    def _Links(self):
        # Used for the email notifications
        linklist = []
        if hasattr(self, "Project") and self.Project:
            linklist.append(Link(self.Project.MakeURL("cdbpcs_project_info"),
                                 "%(project_name)s" % self.Project,
                                 "Projekt:"))
        return linklist

    def _reset_schema(self):
        from cs.workflow.tasks import Task
        from cs.workflow.taskgroups import TaskGroup
        self.AllTaskGroups.Query(TaskGroup.status != TaskGroup.NEW.status).\
            Update(status=TaskGroup.NEW.status,
                   cdb_status_txt=TaskGroup.GetStateText(TaskGroup.NEW))
        self.AllTasks.Query(Task.status != Task.NEW.status).\
            Update(status=Task.NEW.status,
                   cdb_status_txt=Task.GetStateText(Task.NEW),
                   start_date='', end_date_act='')

    def addProtocol(self, msg, msgtype=protocols.MSGSYSTEM, task_id=""):
        with transactions.Transaction():
            # workaround while E026300 is open
            if msgtype == protocols.MSGTASKREADY:
                persno = None
                from cs.workflow.services import WFServer
                persno = WFServer.get_service_user()
                if not persno:
                    # fallback to process responsible (service might not be running)
                    persons = self.Subject.getPersons()
                    if persons:
                        persno = persons[0].personalnummer
            else:
                persno = auth.persno

            msg = msg.replace("\\n", "\n")
            if len(msg) > protocols.Protocol.description.length:
                msg = "{}...".format(
                    msg[:protocols.Protocol.description.length - 3]
                )

            protocols.Protocol.Create(
                cdb_process_id=self.cdb_process_id,
                task_id=task_id,
                cdbprot_sortable_id=protocols.Protocol.MakeEntryId(),
                personalnummer=persno,
                timestamp=datetime.datetime.utcnow(),
                description=msg[:protocols.Protocol.description.length],
                msgtype=msgtype,
            )

    def setCancelled(self, comment=""):
        set_state(self, self.FAILED, comment=comment)

    def setDismissed(self):
        set_state(self, self.DISCARDED)

    def setReady(self):
        set_state(self, self.EXECUTION)

    def setDone(self):
        set_state(self, self.COMPLETED)

    def setNew(self):
        set_state(self, self.NEW)

    def setOnhold(self):
        set_state(self, self.PAUSED)

    def setReview(self):
        set_state(self, self.REVIEW)

    def Subjects(self):
        """
        Returns all subjects that are defined as responsibles for at least one interactive
        task within the process. System tasks are not considered. The returned dictionary
        contains a lists of subject ids for each subject type.
        """
        result = {}
        for t in self.AllTasks:
            if not t.isSystemTask():
                if t.subject_type not in list(result):
                    result[t.subject_type] = [t.subject_id]
                elif t.subject_id not in result[t.subject_type]:
                    result[t.subject_type].append(t.subject_id)
        return result

    @classmethod
    def get_processes_by_user(cls, persno):
        """
        All (non-new and non-discarded) processes with (non-new and non-cancelled)
        tasks which are either directly assigned to a given user id or indirectly
        via a role.
        """
        from cs.workflow.tasks import Task
        processes = [task.Process for task in Task.get_all_tasks_by_user()]
        processes = [proc for proc in processes if proc.status != cls.DISCARDED.status]
        return list(set(processes))

    @classmethod
    def get_global_coworkers(cls, persno):
        """
        All other users and roles participating in the same (non-new and non-discarded)
        processes as given user.
        """
        coworkers = []
        for process in cls.get_processes_by_user(persno):
            coworkers.extend(process.get_process_coworkers(persno))
        return list(set(coworkers))

    def get_process_coworkers(self, persno):
        """All other users and roles participating in this process."""
        coworkers = list(self.Subjects().values())
        # flatten the list
        coworkers = [coworker for sublist in coworkers for coworker in sublist]
        # always include the process owner (in case he's not a task owner)
        if self.subject_id not in coworkers:
            coworkers.append(self.subject_id)
        # exclude current user
        return [coworker for coworker in coworkers if coworker != auth.persno]

    def HandlesStateChange(self, obj, state):
        """ Returns True, if this process handles an automatic
        state change for the given object to the given target state."""
        raise Exception("not implemented since cs.workflow 2.0")

    def is_position_editable(self, position):
        """Check if the addition of a new task in the given position is allowed."""

        from cs.workflow.tasks import Task
        from cs.workflow.schemacomponents import SchemaComponent

        # Check ordering, if parent is already running and task processing is
        # sequential
        if self.status > self.NEW.status:
            positions = self.Components.Query(
                (SchemaComponent.status > Task.NEW.status) &
                (SchemaComponent.position >= position))

            if positions:
                return False
        return True

    def update_change_log(self):
        """ Set the attributes 'started_by' and 'started_at' """
        parent = self.ParentProcess

        if parent:
            started_by = parent.started_by
        else:
            started_by = auth.persno

        self.Update(
            started_by=started_by,
            started_at=datetime.datetime.now()
        )

    def GetActivityStreamTopics(self, posting):
        """Topics for Postings."""
        return [
            self,
            getattr(self, "Project", None),
        ] + [
            parent
            for parent in self.TerminatedParents
        ]

    def get_last_tasks(self):
        from cs.workflow.tasks import Task

        if self.Components:
            pos = max(self.Components.position)
            comp = self.Components.KeywordQuery(position=pos)[0]
            if isinstance(comp, Task):
                return [comp]
            else:
                return comp.get_last_tasks()
        else:
            return []

    def deep_delete_components(self, ctx):
        comps = self.Components
        compl = self.ProcessCompletion
        if compl:
            comps = comps + [compl]
        # force delete component in batch mode
        opargs = {"cdbwf_force_delete": 1}
        for component in comps:
            operations.operation(constants.kOperationDelete,  # @UndefinedVariable
                                 component,
                                 operations.system_args(**opargs))

    def isTemplate(self):
        # is_template is a text field
        return self.is_template == "1"

    def check_copy_from_template(self, ctx):
        if ctx.cdbtemplate.is_template == "1" and self.is_template != ctx.cdbtemplate.is_template:
            require_feature_templating()


class ProcessPyruleAssignment(Object):
    """
    Powerscript representation of the class
    ``class cdbwf_process_pyrule_assign``.
    """

    __maps_to__ = "cdbwf_process_pyrule_assign"
    __classname__ = "cdbwf_process_pyrule_assign"

    Process = Reference_1(fProcess, fProcessPyruleAssignment.cdb_process_id)
    Pyrule = Reference_1(fRule, fProcessPyruleAssignment.name)

class CatalogWorkflowTemplateProposals(Object):
    __maps_to__ = "cdbwf_process_temp_proposals"
    __classname__ = "cdbwf_process_temp_proposals"


class ProcessTemplateCatalogContent(gui.CDBCatalogContent):
    def __init__(self, catalog):
        """
        Initializes the content
        """
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self.data = None
        self.rule_assignments = None
        self.objects = catalog.getInvokingOpObjects()

    def _init_data(self):
        """
        Calculates the catalog content.
        """
        if self.data is None:
            self.data = []
            condition = self.getSQLCondition()
            if not condition:
                condition = "1=1"
            candidates = [
                process for process in
                Process.FromRecords(
                    sqlapi.RecordSet2(
                        self.cdef.getRelation(),
                        condition
                    )
                )
                if process.CheckAccess("read")
            ]
            # To avoid the garbage collection of all_rules before we use rule.ByKeys
            all_rules = None
            if not self.objects:
                self.data = candidates
            else:
                obj = self.objects[0]
                if self.rule_assignments is None:
                    self.rule_assignments = {}
                    assignments = ProcessPyruleAssignment.Query(order_by="cdb_process_id")
                    try:
                        # This is to get all Rules with one select
                        # The Rule.ByKeys construction will use the cached object
                        all_rules = Rule.Query(Rule.name.one_of(*assignments.name))
                        for rule in all_rules:
                            # Just to instantiate the rule
                            pass
                    except Exception as e:
                        misc.log_error("Failed to get all rules with one call:%s" % str(e))

                    last_process_id = None
                    rules = []
                    for ra in assignments:
                        if ra.cdb_process_id != last_process_id:
                            if last_process_id and rules:
                                self.rule_assignments[last_process_id] = rules
                                rules = []
                            last_process_id = ra.cdb_process_id
                        rules.append(ra)
                    if last_process_id and rules:
                        self.rule_assignments[last_process_id] = rules

                for candidate in candidates:
                    if candidate.cdb_process_id not in list(self.rule_assignments):
                        self.data.append(candidate)
                    else:
                        for ra in self.rule_assignments[candidate.cdb_process_id]:
                            rule = Rule.ByKeys(ra.name)
                            try:
                                if rule and rule.match(obj):
                                    self.data.append(candidate)
                                    break
                            except:
                                # Rule seems to be not suitable for the object
                                pass

    def onSearchChanged(self):
        """
        Callback if the users search changes.
        """
        self.data = None

    def getNumberOfRows(self):
        """Called by CDB to retrieve the number of rows in the catalog"""
        self._init_data()
        if self.data:
            return len(self.data)
        else:
            return 0

    def getRowObject(self, row):
        """
        """
        self._init_data()
        ft = self.data[row]
        if ft:
            return ft.ToObjectHandle()
        else:
            return mom.CDBObjectHandle()


# obsolete status classes
Process.READY = Process.EXECUTION
Process.DONE = Process.COMPLETED
Process.CANCELLED = Process.FAILED
Process.DISMISSED = Process.DISCARDED
Process.ONHOLD = Process.PAUSED
Process.CHECKING = Process.REVIEW
