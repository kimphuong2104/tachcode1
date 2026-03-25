#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=reimported


from cdb import i18n, sig, sqlapi, transactions, ue, util
from cdb.classbody import classbody
from cdb.objects import Object, State, Transition
from cdb.objects.operations import operation
from cdb.platform import gui
from cs.web.components.ui_support.frontend_dialog import FrontendDialog

from cs.pcs.projects import Project, tasks_efforts
from cs.pcs.projects.tasks import Task


def get_schedule_related_changes():
    return {
        # from: to (set)
        Task.NEW.status: set([Task.DISCARDED.status]),
        Task.READY.status: set([Task.DISCARDED.status]),
        Task.EXECUTION.status: set(
            [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]
        ),
        Task.FINISHED.status: set(
            [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]
        ),
        Task.COMPLETED.status: set(
            [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]
        ),
        Task.DISCARDED.status: set(
            [
                Task.NEW.status,
                Task.READY.status,
                Task.EXECUTION.status,
                Task.FINISHED.status,
                Task.COMPLETED.status,
            ]
        ),
    }


def is_scheduling_related_change(all_status_changes):
    scedule_related_changes = get_schedule_related_changes()
    for from_status, to_status in all_status_changes.values():
        if (
            from_status in scedule_related_changes
            and to_status in scedule_related_changes[from_status]
        ):
            return True
    return False


def get_target_status_no(olc, status_name):
    name_fields = [
        f"statusbez_{i18n.default()}",
        "statusbezeich",
    ]

    for name_field in name_fields:
        query = f"objektart = '{olc}' AND {name_field} = '{status_name}'"

        for row in sqlapi.RecordSet2("objektstati", query):
            return row["statusnummer"]

    raise ValueError(f"status not found: '{olc}'/'{status_name}'")


def user_confirmation_project_state_change(hook):
    target_state_id = get_target_status_no(
        hook.get_new_object_value("cdb_objektart"),  # loaded from object / DB
        hook.get_new_values()[".zielstatus"],  # from dialog field
    )

    current_project_id = hook.get_new_values()["cdbpcs_project.cdb_project_id"]
    current_project = Project.ByKeys(cdb_project_id=current_project_id)

    if target_state_id == Project.NEW.status:
        fe = FrontendDialog(
            util.get_label("pccl_cap_quest"),
            gui.Message.GetMessage(
                "cdbpcs_reset_proj",
                current_project.project_name,
                current_project.cdb_project_id,
            ),
        )
        fe.add_button(
            util.get_label("web.base.dialog_yes"),
            0,
            FrontendDialog.ActionSubmit,
            is_default=False,
        )
        fe.add_button(
            util.get_label("web.base.dialog_no"),
            0,
            FrontendDialog.ActionBackToDialog,
            is_default=True,
        )
        hook.set_dialog(fe)
    elif (
        target_state_id in Project.endStatus(False)
        and current_project.containsNonFinalObjects()
    ):
        project_text = (
            f'"{current_project.project_name}" ({current_project.cdb_project_id})'
        )
        fe = FrontendDialog(
            util.get_label("pccl_cap_quest"),
            gui.Message.GetMessage("cdbpcs_complete_proj", project_text),
        )
        fe.add_button(
            util.get_label("web.base.dialog_yes"),
            0,
            FrontendDialog.ActionSubmit,
            is_default=False,
        )
        fe.add_button(
            util.get_label("web.base.dialog_no"),
            0,
            FrontendDialog.ActionBackToDialog,
            is_default=True,
        )
        hook.set_dialog(fe)


class ProjectStatusProtocol(Object):
    __maps_to__ = "cdbpcs_prj_prot"
    __classname__ = "cdbpcs_prj_prot"


@classbody
class Project:
    def _do_status_change_adjustments(self, obj_ids, adjustments):
        for method, kwargs in adjustments.items():
            # get tasks to adjust
            tasks = self.Tasks.KeywordQuery(cdb_object_id=obj_ids, **kwargs)
            # call method to adjust
            if tasks:
                method(tasks)

    def _do_aggregation_adjustments(self):
        # aggregate tasks and projects
        tasks_efforts.aggregate_changes(self)

        # adjust role assignments
        self.adjust_role_assignments()

    def do_status_updates(self, changes):
        if self.ce_baseline_id != "":
            from cs.pcs.projects.baselining import CANNOT_MODIFY_ERROR_MESSAGE_DEFAULT

            raise util.ErrorMessage(CANNOT_MODIFY_ERROR_MESSAGE_DEFAULT)

        from cs.pcs.projects.tasks_status import STATUS_CHANGE_ADJUSTMENTS

        self._do_status_change_adjustments(
            list(changes.keys()), STATUS_CHANGE_ADJUSTMENTS
        )
        if is_scheduling_related_change(changes):
            self.recalculate()
        else:
            self.aggregate()
        self._do_aggregation_adjustments()

    def on_wf_step_post_mask(self, ctx):
        # TODO E056430 The event tpye has to be post_mask, because within a pre event it is
        # not possible to call a user_confirmation method. Note, post_mask is in cs.web not existent.
        if self.status == self.NEW.status:
            self.user_confirmation(ctx, "ask_reset_project", "cdbpcs_reset_proj")
        if (
            self.status in (self.COMPLETED.status, self.DISCARDED.status)
            and self.containsNonFinalObjects()
        ):
            self.user_confirmation(ctx, "ask_complete_project", "cdbpcs_complete_proj")

    def user_confirmation(self, ctx, attr, msg):
        if attr not in ctx.dialog.get_attribute_names() or ctx.dialog[attr] == "":
            msgbox = ctx.MessageBox(msg, [self.project_name, self.cdb_project_id], attr)
            msgbox.addYesButton(1)
            msgbox.addNoButton()
            ctx.show_message(msgbox)
            return False
        else:
            result = ctx.dialog[attr]
            if result == "0":
                raise ue.Exception("cdbpcs_sc_cancel")
        return None

    def containsNonFinalObjects(self):
        for relship in [self.TopTasks, self.Issues, self.TopLevelChecklists]:
            if [x for x in relship if x.status not in x.endStatus(False)]:
                return True
        return None

    @sig.connect(Project, "state_change", "post")
    def setFrozen(self, ctx=None):
        if ctx and getattr(ctx, "error", None):
            return

        frozen = int(self.status == self.FROZEN.status)
        with transactions.Transaction():
            self.Checklists.Update(cdbpcs_frozen=frozen)
            self.ChecklistItems.Update(cdbpcs_frozen=frozen)
            self.Issues.Update(cdbpcs_frozen=frozen)
            self.Tasks.Update(cdbpcs_frozen=frozen)

    def accept_new_task(self):
        """
        Finalized projects may not accept new tasks.
        Check if project is able to accept tasks.

        :raises Exception if project is not able to accept tasks
        """
        if self.has_ended():
            raise ue.Exception("pcs_err_new_task1", self.project_name)

    def has_ended(self):
        """
        Evaluates if the project matches one of the end status

        :return: True if project has ended, else False
        """
        return self.status in Project.endStatus(False)

    @classmethod
    def endStatus(cls, full_cls=True):
        """
        returns set of "final" status classes (full_cls True) or integer values
        (full_cls False) and cache them for subsequent access
        """
        if not hasattr(cls, "__end_status_cls__"):
            cls.__end_status_cls__ = [cls.DISCARDED, cls.COMPLETED]
            cls.__end_status_int__ = [x.status for x in cls.__end_status_cls__]
        if full_cls:
            return cls.__end_status_cls__
        return cls.__end_status_int__

    class NEW(State):
        status = 0

        def Constraints(state, self):
            return [
                (
                    "MatchStateList",
                    [
                        [self.ParentProject],
                        [self.NEW, self.EXECUTION],
                        "pcs_proj_wf_rej_0",
                    ],
                )
            ]

        def FollowUpStateChanges(state, self):
            from cs.pcs.checklists import Checklist

            return [
                (
                    Checklist.NEW,
                    [
                        c
                        for c in self.TopLevelChecklists
                        if c.status != Checklist.DISCARDED.status
                    ],
                    0,
                    False,
                ),
            ]

    class EXECUTION(State):
        status = 50

        def Constraints(state, self):
            return [
                (
                    "MatchStateList",
                    [[self.ParentProject], [self.EXECUTION], "pcs_proj_wf_rej_0"],
                )
            ]

    class FROZEN(State):
        status = 60

        def Constraints(state, self):
            return [
                (
                    "MatchStateList",
                    [
                        self.Subprojects,
                        [self.FROZEN, self.DISCARDED, self.COMPLETED],
                        "pcs_proj_wf_rej_1",
                    ],
                )
            ]

    class DISCARDED(State):
        status = 180

        def pre(state, self, ctx):
            from cs.pcs.projects.tasks import Task

            unfinished_tasks = [
                t for t in self.TopTasks if t.status not in Task.endStatus(False)
            ]
            for task in unfinished_tasks:
                operation("cdbpcs_cancel_task", task)

        def FollowUpStateChanges(state, self):
            from cs.pcs.checklists import Checklist
            from cs.pcs.issues import Issue

            return [
                (
                    Issue.DISCARDED,
                    [
                        i
                        for i in self.Issues
                        if not i.task_id and i.status not in Issue.endStatus(False)
                    ],
                    0,
                    False,
                ),
                (
                    Checklist.DISCARDED,
                    [
                        c
                        for c in self.TopLevelChecklists
                        if c.status not in Checklist.endStatus(False)
                    ],
                    0,
                    False,
                ),
            ]

    class COMPLETED(State):
        status = 200

        def pre(state, self, ctx):
            from cs.pcs.projects.tasks import Task

            unfinished_tasks = [
                t for t in self.TopTasks if t.status not in Task.endStatus(False)
            ]
            for task in unfinished_tasks:
                operation("cdbpcs_cancel_task", task)

        def FollowUpStateChanges(state, self):
            from cs.pcs.checklists import Checklist
            from cs.pcs.issues import Issue
            from cs.pcs.projects.tasks import Task

            result = [
                (
                    Task.COMPLETED,
                    [t for t in self.TopTasks if t.status == Task.FINISHED.status],
                    0,
                    False,
                ),
                (
                    Issue.COMPLETED,
                    [
                        i
                        for i in self.Issues
                        if not i.task_id and i.status not in Issue.endStatus(False)
                    ],
                    0,
                    False,
                ),
                (
                    Checklist.DISCARDED,
                    [
                        c
                        for c in self.TopLevelChecklists
                        if c.status not in Checklist.endStatus(False)
                    ],
                    0,
                    False,
                ),
            ]
            return result

    class NEW_EXECUTION(Transition):
        transition = (0, 50)

        def FollowUpStateChanges(transition, self):
            from cs.pcs.projects.tasks import (
                Task,
                kTaskDependencyAA,
                kTaskDependencyEA,
                kTaskDependencyEE,
            )

            def predecessors(task):
                if task.getPredecessors(kTaskDependencyAA):
                    return True
                if task.getPredecessors(kTaskDependencyEA):
                    return True
                if task.getPredecessors(kTaskDependencyEE):
                    return True
                return None

            return [
                (
                    Task.READY,
                    [t for t in self.TopTasks if not predecessors(t)],
                    0,
                    False,
                )
            ]

    class TO_NEW(Transition):
        transition = ("*", 0)

        def FollowUpStateChanges(transition, self):
            from cs.pcs.projects.tasks import Task

            old = transition.SourceState(self).status

            if old == self.DISCARDED.status:
                return [
                    (
                        Task.NEW,
                        [
                            t
                            for t in self.TopTasks
                            if t.status
                            not in [Task.FINISHED.status, Task.COMPLETED.status]
                        ],
                        0,
                        False,
                    )
                ]

            return [
                (
                    Task.NEW,
                    [t for t in self.TopTasks if t.status != Task.DISCARDED.status],
                    0,
                    False,
                )
            ]

    class DISCARDED_EXECUTION(Transition):
        transition = (180, 50)

        def FollowUpStateChanges(transition, self):
            from cs.pcs.projects.tasks import Task

            ready = []
            new = []

            for task in self.TopTasks:
                if task.status == Task.DISCARDED.status:
                    if task.getSubtasksMeetingPredecessorCondition():
                        ready.append(task)
                    else:
                        new.append(task)

            return [
                (Task.READY, ready, 0, False),
                (Task.NEW, new, 0, False),
            ]
