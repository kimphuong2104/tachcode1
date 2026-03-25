#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# CDB:Browse

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import ElementsError, util
from cdb.classbody import classbody
from cdb.objects import Object, State, Transition
from cdb.platform import olc

from cs.pcs.checklists import Checklist, ChecklistItem


class ChecklistStatusProtocol(Object):
    __maps_to__ = "cdbpcs_cl_prot"
    __classname__ = "cdbpcs_cl_prot"


@classbody
class Checklist:
    @classmethod
    def endStatus(cls, full_cls=True):
        """
        returns set of "final" status classes (full_cls True) or integer values
        (full_cls False) and cache them for subsequent access
        """
        if not hasattr(cls, "__end_status_cls__"):
            cls.__end_status_cls__ = set([cls.DISCARDED, cls.COMPLETED])
            cls.__end_status_int__ = {x.status for x in cls.__end_status_cls__}
        if full_cls:
            return cls.__end_status_cls__
        return cls.__end_status_int__

    class NEW(State):
        status = 0

        def Constraints(state, self):
            from cs.pcs.projects.tasks import Task

            return [
                (
                    "MatchStateList",
                    [
                        [self.Task],
                        [Task.NEW, Task.READY, Task.EXECUTION],
                        "pcscl_wf_rej_2",
                    ],
                )
            ]

        def post(state, self, ctx):
            self.Update(rating="", rating_id="")
            self.resetItems()

    class EVALUATION(State):
        status = 20

        def Constraints(state, self):
            from cs.pcs.projects import Project
            from cs.pcs.projects.tasks import Task

            return [
                (
                    "MatchStateList",
                    [[self.Project], [Project.EXECUTION], "pcscl_wf_rej_3"],
                ),
                (
                    "MatchStateList",
                    [
                        [self.Task],
                        [Task.READY, Task.EXECUTION, Task.DISCARDED],
                        "pcscl_wf_rej_2",
                    ],
                ),
            ]

        def FollowUpStateChanges(state, self):
            from cs.pcs.projects.tasks import Task

            if self.Task and self.Task.status == Task.NEW.status:
                self.Task.ChangeState(Task.READY.status, check_access=False)
            return [
                (
                    Task.EXECUTION,
                    [
                        task
                        for task in [self.Task]
                        if task and task.status == Task.READY.status
                    ],
                    0,
                    False,
                )
            ]

    class DISCARDED(State):
        status = 180

        def FollowUpStateChanges(state, self):
            if self.Task:
                target_status = self.Task.getFinalStatus()
                if target_status:
                    return [(target_status, [self.Task], 0, False)]
            return []

        def post(state, self, ctx):
            self.cancelItems()

    class COMPLETED(State):
        status = 200

        def Constraints(state, self):
            from cs.pcs.projects.tasks import Task

            constraints = [
                (
                    "MatchStateList",
                    [self.ChecklistItems, [ChecklistItem.COMPLETED], "pcscl_wf_rej_0"],
                ),
                (
                    "MatchStateList",
                    [[self.Task], [Task.READY, Task.EXECUTION], "pcscl_wf_rej_0"],
                ),
            ]
            # Bei Deliverables prüfen, ob die zu erstellenden Objekte existieren
            if self.type == "Deliverable":
                constraints.append(("matchRules", [self.Collection]))
            return constraints

        def FollowUpStateChanges(state, self):
            if self.Task:
                target_status = self.Task.getFinalStatus()
                if target_status:
                    return [(target_status, [self.Task], 0, False)]
            return []

        def post(state, self, ctx):
            # Bewertung aktualisieren
            self.setRating(True)

    class COMPLETED_TO_EVALUATION(Transition):
        transition = (200, 20)

        def Constraints(state, self):
            """Der uebergeordnete Checkpunkt darf nicht bewertet sein (sofern vorhanden)"""
            return [
                (
                    "MatchStateList",
                    [
                        [self.ParentChecklistItem],
                        [ChecklistItem.NEW, ChecklistItem.READY],
                        "pcscl_wf_rej_1",
                    ],
                )
            ]

    class NEW_TO_EVALUATION(Transition):
        transition = (0, 20)

        def post(transition, self, ctx):
            self.setItemsWaiting()

    class DISCARDED_TO_EVALUATION(Transition):
        transition = (180, 20)

        def post(transition, self, ctx):
            self.setItemsWaiting()

    class ALL_WF_STEPS(Transition):
        transition = ("*", "*")

        def post(transition, self, ctx):
            self._mirrorState()  # pylint: disable=protected-access

    def matchRules(self, objects):
        # Constraint checker for deliverables.
        # Matches assigned rules against a list of given objects.
        # At least one object must match for each rule.
        msg = ""
        not_matching_rules = []
        for ref in self.RuleReferences:
            rule = ref.Rule
            found = False
            for o in objects:
                if o.MatchRule(rule):
                    found = True
                    break
            if not found:
                not_matching_rules.append(rule)
        if not_matching_rules:
            from cdb.platform import gui

            msg = f'{gui.Message.GetMessage("pcs_deliv_mismatch")}\n - '
            msg += "\n - ".join([r.name for r in not_matching_rules])
        return msg

    def change_status_of_checklist(
        self, source_status, target_status, check_access=False
    ):
        """
        Changes the status of `self` from `source_status` to `target_status`.
        If current status is not `source_status`, do nothing.

        :param source_status: Expected current status
        :type source_status: cdb.objects.State

        :param target_status: Target status
        :type target_status: cdb.objects.State

        :param check_access: If `True`, check access for status change
            (defaults to `False`)
        :type check_access: bool

        :return: if status has been changed
        :rtype: bool

        :raises util.ErrorMessage: if status change was attempted but failed
        """
        if self.status == source_status.status:
            try:
                self.ChangeState(
                    target_status.status,
                    check_access=check_access,
                )
                return True
            except ElementsError as error:
                raise util.ErrorMessage(
                    "pcscl_wf_rej_4",
                    olc.StateDefinition.ByKeys(
                        statusnummer=target_status.status,
                        objektart=self.cdb_objektart,
                    ).StateText[""],
                    error,
                )
        return False

    def prepare_for_rating(self):
        """
        Called when user rates an item of this checklist (`self`):

        - If checklist's status is `NEW`, change it to `EVALUATION`,
        - If it already is `EVALUATION`, do nothing,
        - Otherwise raise an Exception.

        :raises cdb.util.ErrorMessage: if status is not `EVALUATION`
        """
        self.change_status_of_checklist(self.NEW, self.EVALUATION)

        if self.status != self.EVALUATION.status:
            raise util.ErrorMessage("cdbpcs_err_checklist")


class ChecklistItemStatusProtocol(Object):
    __maps_to__ = "cdbpcs_cli_prot"
    __classname__ = "cdbpcs_cli_prot"


@classbody
class ChecklistItem:
    def prevent_interactive_status_change(self, ctx):
        if not getattr(ctx, "batch", 0) == 1:
            raise util.ErrorMessage("workflow_no_auth")

    class NEW(State):
        status = 0

        def pre_mask(state, self, ctx):
            self.prevent_interactive_status_change(ctx)

    class READY(State):
        status = 20

        def pre_mask(state, self, ctx):
            self.prevent_interactive_status_change(ctx)

    class COMPLETED(State):
        status = 200

        def pre_mask(state, self, ctx):
            self.prevent_interactive_status_change(ctx)

        def post(state, self, ctx):
            if not ctx.error:
                # ggf. Checkliste bewerten
                cl = self.Checklist
                if (
                    cl.auto
                    and cl.GetState(Checklist.COMPLETED.status).EvalConstraints(
                        cl, False
                    )[0]
                ):
                    self.Checklist.ChangeState(Checklist.COMPLETED, check_access=False)

    class DISCARDED(State):
        status = 180

        def pre_mask(state, self, ctx):
            self.prevent_interactive_status_change(ctx)

    class COMPLETED_TO_READY(Transition):
        transition = (200, 20)

        def post(state, self, ctx):
            if not ctx.error:
                self.Update(rating="", rating_id="")

    def change_status_of_checklist(
        self, source_status, target_status, check_access=False
    ):
        self.Checklist.change_status_of_checklist(
            source_status, target_status, check_access=False
        )
