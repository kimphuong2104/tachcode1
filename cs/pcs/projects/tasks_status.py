#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines,protected-access

import logging

from cdb import ElementsError, sig, sqlapi, ue, util
from cdb.classbody import classbody
from cdb.objects import Object, Reference_N, State, Transition
from cdb.objects.objectlifecycle import StateChangeHandler
from cdb.objects.operations import operation
from cdb.platform import olc

from cs.pcs.projects import status_updates, utils
from cs.pcs.projects.tasks import (
    Task,
    kTaskDependencyAA,
    kTaskDependencyAE,
    kTaskDependencyEA,
    kTaskDependencyEE,
)


class TaskStatusProtocol(Object):
    __maps_to__ = "cdbpcs_tsk_prot"
    __classname__ = "cdbpcs_task_prot"


Task.__taskrel_constraints__ = {
    20: False,
    200: True,
}


def no_other_predecessors(successor):
    if successor.status != Task.NEW.status:
        return None
    tasks = successor.getPredecessors(kTaskDependencyAA) + successor.getPredecessors(
        kTaskDependencyEA
    )
    preds = [
        p
        for p in tasks
        if p.status in [Task.NEW.status, Task.READY.status, Task.EXECUTION.status]
    ]
    return not preds


@classbody
class Task:
    StatusProtocol = Reference_N(
        TaskStatusProtocol,
        TaskStatusProtocol.cdb_project_id == Task.cdb_project_id,
        TaskStatusProtocol.task_id == Task.task_id,
    )

    def on_wf_step_pre(self, ctx):
        if self.status == 0 and (len(self.Subtasks) or len(self.Checklists)):
            self.user_confirmation(ctx, "cdbpcs_reset_task", "ask_reset_task")
        if self.status == 250 and len(self.Subtasks):
            self.user_confirmation(ctx, "cdbpcs_finish_task", "ask_finish_task")

    def on_cdbpcs_cancel_task_pre_mask(self, ctx):
        if self.has_ended():
            raise util.ErrorMessage("cdbpcs_cancel_task_noop")

        message = util.ErrorMessage("cdbpcs_cancel_task_desc")
        ctx.set("operation_description", str(message))

    def on_cdbpcs_cancel_task_now(self, ctx):
        if self.has_ended():
            raise util.ErrorMessage("cdbpcs_cancel_task_noop")

        current_task = None

        try:
            for child in self.OrderedSubTasks:
                current_task = child
                if not child.has_ended():
                    if child.is_group:
                        operation("cdbpcs_cancel_task", child)
                    else:
                        child.ChangeState(self.DISCARDED.status)

            current_task = self
            self.Reload()

            if not self.has_ended():
                parent_status = self.DISCARDED.status
                if self.Subtasks.KeywordQuery(
                    status=[self.FINISHED.status, self.COMPLETED.status]
                ):
                    parent_status = self.FINISHED.status
                self.ChangeState(parent_status)
        except (ElementsError, util.ErrorMessage) as error:
            logging.exception(
                "discard_task %s.%s (child %s.%s)",
                self.cdb_project_id,
                self.task_id,
                current_task.cdb_project_id,
                current_task.task_id,
            )
            raise util.ErrorMessage(
                "just_a_replacement",
                f"{current_task.GetDescription()}: {error}",
            )

    def user_confirmation(self, ctx, question, attr):
        attr_value = getattr(ctx.dialog, attr, "")
        if attr_value == "":
            msgbox = ctx.MessageBox(question, [self.task_name], attr)
            msgbox.addYesButton(1)
            msgbox.addNoButton()
            ctx.show_message(msgbox)
            return False
        else:
            result = ctx.dialog[attr]
            if result == "0":
                # Statuswechsel abgebrochen.
                raise ue.Exception("cdbpcs_sc_cancel")
        return None

    def getTaskRelConstraintViolations(self, volatile_relation=None):
        """
        Get list of error messages for constraint violations
        pertaining to self's predecessors

        :param volatile_relation: Non-persistent task relation (optional).
        :type volatile_relation: cs.pcs.projects.tasks.TaskRelation
        """
        messages = [
            getattr(StateChangeHandler, method)(*constraints)
            for method, constraints in self._getTaskRelConstraints(
                self.status, volatile_relation
            )
        ]
        return [msg for msg in messages if msg]

    def _getTaskRelConstraints(self, to_status, volatile_relation=None):
        """
        Enforcement of task relationship constraints is customizable in
        Task.__taskrel_constraints__

        :param to_status: Target status to return constraint lists for
        :type to_status: int

        :param volatile_relation: Non-persistent task relation (optional).
        :type volatile_relation: cs.pcs.projects.tasks.TaskRelation
        """
        if to_status == 20 and self.__taskrel_constraints__[20]:
            return [
                (
                    "MatchStateList",
                    [
                        self.getPredecessors(kTaskDependencyEA, volatile_relation),
                        Task.endStatus(),
                        "pcstask_wf_rej_7",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        self.getPredecessors(kTaskDependencyAA, volatile_relation),
                        [Task.EXECUTION] + Task.endStatus(),
                        "pcstask_wf_rej_6",
                    ],
                ),
            ]
        if to_status == 200 and self.__taskrel_constraints__[200]:
            return [
                (
                    "MatchStateList",
                    [
                        self.getPredecessors(kTaskDependencyEA, volatile_relation),
                        Task.endStatus(),
                        "pcstask_wf_rej_7",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        self.getPredecessors(kTaskDependencyAA, volatile_relation),
                        [Task.EXECUTION] + Task.endStatus(),
                        "pcstask_wf_rej_6",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        self.getPredecessors(kTaskDependencyEE, volatile_relation),
                        Task.endStatus(),
                        "pcstask_wf_rej_10",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        self.getPredecessors(kTaskDependencyAE, volatile_relation),
                        [Task.EXECUTION] + Task.endStatus(),
                        "pcstask_wf_rej_11",
                    ],
                ),
            ]
        return []

    def accept_new_task(self):
        """
        Finalized tasks may not accept new sub tasks.
        Check if task is able to accept sub tasks.

        :raises Exception if task is not able to accept sub tasks
        """
        if self.has_ended():
            raise ue.Exception("pcs_err_new_task2", self.task_name)

    def accept_new_parent_task(self, parent):
        """
        Finalized tasks may not be assigned to a new parent.
        Additionally the status of the new parent task has to match
        consistency conditions with status of the called task.
        Check if task is able to accept the new parent task.

        :raises Exception if task is not able to accept given parent
        """
        # check if task is already in final status
        if self.has_ended():
            txt = self.get_status_txt(self.status)
            raise ue.Exception("pcs_task_has_ended", self.task_name, txt)
        # status of task has to fit status of parent task
        if self.status == Task.READY.status and parent.status == Task.NEW.status:
            txt = parent.get_status_txt(Task.NEW.status)
            raise ue.Exception(
                "pcs_reset_parent_task_status", parent.task_name, txt, txt
            )
        if self.status == Task.EXECUTION.status and parent.status in [
            Task.NEW.status,
            Task.READY.status,
        ]:
            txt = parent.get_status_txt(Task.EXECUTION.status)
            raise ue.Exception(
                "pcs_advance_parent_task_status", parent.task_name, txt, txt
            )

    def has_ended(self):
        """
        Evaluates if the task matches one of the end status

        :return: True if task has ended, else False
        """
        return self.status in Task.endStatus(False)

    @classmethod
    def endStatus(cls, full_cls=True):
        """
        returns set of "final" status classes (full_cls True) or integer values
        (full_cls False) and cache them for subsequent access
        """
        if not hasattr(cls, "__end_status_cls__"):
            cls.__end_status_cls__ = [cls.DISCARDED, cls.FINISHED, cls.COMPLETED]
            cls.__end_status_int__ = [x.status for x in cls.__end_status_cls__]
        if full_cls:
            return cls.__end_status_cls__
        return cls.__end_status_int__

    def getFinalStatus(self):
        """
        returns next status for this task after one of its children's status
        was changed.

        if all children's status is final and at least one child is FINISHED or
        COMPLETED -> FINISHED

        else None
        """
        result = None

        for relship in [self.Subtasks, self.Checklists, self.Issues]:
            for child in relship:
                if child.status not in child.endStatus(full_cls=False):
                    return False
                if child.status != child.DISCARDED.status:
                    result = self.FINISHED

        return result

    def getPredecessors(self, dependency, volatile_relation=None):
        """
        :param dependency: Task relation type
        :type dependency: str ("AA", "AE", "EA" or "EE")

        :param volatile_relation: Non-persistent task relation (optional).
            If present, pretend this relation would exist, too.
        :type volatile_relation: cs.pcs.projects.tasks.TaskRelation
        """
        result = [
            task_rel.PredecessorTask
            for task_rel in self.PredecessorTaskRelationsByType[dependency]
        ]
        if volatile_relation and volatile_relation.rel_type == dependency:
            result.append(volatile_relation.PredecessorTask)
        return result

    def getSuccessors(self, dependency, volatile_relation=None):
        """
        :param dependency: Task relation type
        :type dependency: str ("AA", "AE", "EA" or "EE")

        :param volatile_relation: Non-persistent task relation (optional).
            If present, pretend this relation would exist, too.
        :type volatile_relation: cs.pcs.projects.tasks.TaskRelation
        """
        result = [
            task_rel.SuccessorTask
            for task_rel in self.SuccessorTaskRelationsByType[dependency]
        ]
        if volatile_relation and volatile_relation.rel_type == dependency:
            result.append(volatile_relation.SuccessorTask)
        return result

    def getInitialSubtasks(self):
        end = self.endStatus(False)

        def predecessors(task):
            for rel in [kTaskDependencyEA, kTaskDependencyEE]:
                if [p for p in task.getPredecessors(rel) if p.status not in end]:
                    return True
            return None

        return [sub for sub in self.OrderedSubTasks if not predecessors(sub)]

    def getSubtasksMeetingPredecessorCondition(self):
        """
        "Predecessor Condition" - this is referenced throughout status change
        logic

        return all subtasks that meet alle the following criteria:
          - all FS predecessors are COMPLETED or FINISHED
          - all SS predecessors are EXECUTION, DISCARDED, COMPLETED, or FINISHED
        """
        ea_status = [Task.COMPLETED.status, Task.FINISHED.status]
        aa_status = [
            Task.EXECUTION.status,
            Task.DISCARDED.status,
            Task.COMPLETED.status,
            Task.FINISHED.status,
        ]
        return [
            sub
            for sub in self.OrderedSubTasks
            if not [
                pre
                for pre in sub.getPredecessors(kTaskDependencyEA)
                if int(pre.status) not in ea_status
            ]
            and not [
                succ
                for succ in sub.getSuccessors(kTaskDependencyAA)
                if int(succ.status) not in aa_status
            ]
        ]

    def _getTransitions(self, source_status, target_status):
        import itertools

        for x in itertools.product(["*", source_status], [target_status]):
            transition = Task.__transitions__.get(x, None)
            if transition:
                copied_transition = transition.__class__()
                copied_transition.init(source_status, target_status)
                yield copied_transition

    def adjustSuccessorStatus(self):
        if self.IsDeleted():
            source_status = self.status
            target_status = self.DISCARDED.status
        else:
            source_status = self.NEW.status
            target_status = self.status

        self.GetState(target_status).PerformFollowUpStateChanges(self)
        for transition in self._getTransitions(source_status, target_status):
            transition.PerformFollowUpStateChanges(self)

    def isDiscarded(self):
        return self.status == Task.DISCARDED.status

    class NEW(State):
        status = 0

        def checkStructureConsistency(state, self):
            if not self.checkStructureStatus([0]):
                raise ue.Exception("cdbpcs_structure_consistency_new")

        def Constraints(state, self):
            """
            - Project's status has to be NEW, EXECUTION, or FROZEN
            - Parent task's status has to be NEW, READY or EXECUTION
            """
            from cs.pcs.projects import Project

            return [
                (
                    "MatchStateList",
                    [
                        [self.Project],
                        [Project.NEW, Project.EXECUTION, Project.FROZEN],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [self.ParentTask],
                        [Task.NEW, Task.READY, Task.EXECUTION],
                        "pcstask_wf_rej_1",
                    ],
                ),
            ]

        # Transition TO_NEW implements FollowUpStateChanges

    class READY(State):
        status = 20

        def Constraints(state, self):
            """
            - Optional task relationship constraints may be enabled
            - Project's status has to be either EXECUTION or FROZEN
            - Parent task's status has to be either NEW or EXECUTION
            - Status of subtasks has to be anything but COMPLETED and FINISHED
            - Status of Checklists has to be NEW, or DISCARDED
            """
            from cs.pcs.checklists import Checklist
            from cs.pcs.projects import Project

            return self._getTaskRelConstraints(state.status) + [
                (
                    "MatchStateList",
                    [
                        [self.Project],
                        [Project.EXECUTION, Project.FROZEN],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [self.ParentTask],
                        [Task.READY, Task.EXECUTION],
                        "pcstask_wf_rej_1",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        self.Subtasks,
                        [Task.NEW, Task.READY, Task.EXECUTION, Task.DISCARDED],
                        "pcstask_wf_rej_3",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        self.Checklists,
                        [Checklist.NEW, Checklist.EVALUATION, Checklist.DISCARDED],
                        "pcstask_wf_rej_0",
                    ],
                ),
            ]

        # Transitions TO_READY implement FollowUpStateChanges

    class EXECUTION(State):
        status = 50

        def Constraints(state, self):
            """
            - Project's status has to be either EXECUTION or FROZEN
            - Parent task's status has to be either READY, EXECUTION,
              DISCARDED, or FINISHED
            """
            return [
                (
                    "MatchStateList",
                    [
                        [self.Project],
                        [self.Project.EXECUTION, self.Project.FROZEN],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [self.ParentTask],
                        [Task.READY, Task.EXECUTION, Task.DISCARDED, Task.FINISHED],
                        "pcstask_wf_rej_1",
                    ],
                ),
            ]

        # see also Transition FINISHED_EXECUTION
        def FollowUpStateChanges(state, self):
            """
            - ParentTask * -> EXECUTION
            - SubTasks NEW -> READY if they have no FS or FF predecessors
            - SS Successors NEW -> READY
            """
            conditionMet = self.getInitialSubtasks()
            return [
                (
                    Task.EXECUTION,
                    [task for task in [self.ParentTask] if task],
                    0,
                    False,
                ),
                (
                    Task.READY,
                    [s for s in conditionMet if s.status == Task.NEW.status],
                    0,
                    False,
                ),
                (
                    Task.READY,
                    [
                        s
                        for s in self.getSuccessors(kTaskDependencyAA)
                        if s.status == Task.NEW.status
                    ],
                    0,
                    False,
                ),
            ]

    class DISCARDED(State):
        status = 180

        def Constraints(state, self):
            """
            - Status of subtask structure has to be anything but COMPLETED and FINISHED
              (direct subtasks in status EXECUTION may themselves contain COMPLETED or FINISHED subtasks)
            """
            return self._getTaskRelConstraints(state.status) + [
                (
                    "MatchStateList",
                    [
                        self.AllSubTasksOptimized,
                        [Task.NEW, Task.READY, Task.EXECUTION, Task.DISCARDED],
                        "pcs_taskgroup_discard",
                    ],
                ),
            ]

        def FollowUpStateChanges(state, self):
            """
            - Non-final SubTasks -> DISCARDED
            - Non-final Issues -> DISCARDED
            - Non-final Checklists -> DISCARDED
            - ParentTask * -> FINISHED (if all children in final status)
            """
            from cs.pcs.checklists import Checklist
            from cs.pcs.issues import Issue

            result = [
                (
                    Task.DISCARDED,
                    [
                        task
                        for task in self.OrderedSubTasks
                        if task.status not in Task.endStatus(False)
                    ],
                    0,
                    False,
                ),
                (
                    Issue.DISCARDED,
                    [i for i in self.Issues if i.status not in Issue.endStatus(False)],
                    0,
                    False,
                ),
                (
                    Checklist.DISCARDED,
                    [
                        cl
                        for cl in self.Checklists
                        if cl.status not in Checklist.endStatus(False)
                    ],
                    0,
                    False,
                ),
            ]

            if self.ParentTask:
                target_status = self.ParentTask.getFinalStatus()
                if target_status:
                    result.append((target_status, [self.ParentTask], 0, 0))

            return result

        def pre_mask(state, self, ctx):
            # only allow changing status back to READY or EXECUTION if task's
            # status has been READY since last planning cycle
            sd = olc.StateDefinition.ByKeys(
                statusnummer=Task.READY.status, objektart=self.GetObjectKind()
            )
            ready_txt = sd.statusbezeich
            sd = olc.StateDefinition.ByKeys(
                statusnummer=Task.NEW.status, objektart=self.GetObjectKind()
            )
            planned_txt = sd.statusbezeich
            t = sqlapi.SQLselect(
                "cdbprot_neustat FROM cdbpcs_tsk_prot WHERE "
                f"cdb_project_id='{self.cdb_project_id}' AND task_id='{self.task_id}' "
                f"AND cdbprot_neustat IN ('{ready_txt}', '{planned_txt}') "
                "ORDER BY cdbprot_sortable_id"
            )
            rows = sqlapi.SQLrows(t)
            if rows and sqlapi.SQLstring(t, 0, rows - 1) != ready_txt:
                ctx.excl_state(Task.EXECUTION.status)
                ctx.excl_state(Task.READY.status)

        def pre(state, self, ctx):
            if self.Project.msp_active == 2:
                raise ue.Exception(
                    "cdbpcs_msp_standard_no_discarded_tasks", self.GetDescription()
                )

    class FINISHED(State):
        status = 200

        def Constraints(state, self):
            """
            - Project EXECUTION, FROZEN, or DISCARDED
            - Parent Task EXECUTION, FINISHED, or DISCARDED
            - Status of all children has to be final (Tasks, Checklists,
              Issues)
            """
            from cs.pcs.checklists import Checklist
            from cs.pcs.issues import Issue
            from cs.pcs.projects import Project

            return self._getTaskRelConstraints(state.status) + [
                (
                    "MatchStateList",
                    [
                        [self.Project],
                        [Project.EXECUTION, Project.FROZEN, Project.DISCARDED],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [self.ParentTask],
                        [Task.READY, Task.EXECUTION, Task.FINISHED, Task.DISCARDED],
                        "pcstask_wf_rej_1",
                    ],
                ),
                (
                    "MatchStateList",
                    [self.Subtasks, Task.endStatus(), "pcstask_wf_rej_3"],
                ),
                (
                    "MatchStateList",
                    [self.Checklists, Checklist.endStatus(), "pcstask_wf_rej_0"],
                ),
                (
                    "MatchStateList",
                    [self.Issues, Issue.endStatus(), "pcstask_wf_rej_8"],
                ),
            ]

        def FollowUpStateChanges(state, self):
            """
            - FS and FF Successors NEW -> READY
                FS, SS Successors only if they do not have another FS, SS
                    predecessor in status NEW or READY
            - ParentTask * -> FINISHED (if all children in final status)
            """
            result = [
                (
                    Task.READY,
                    list(
                        filter(
                            no_other_predecessors,
                            self.getSuccessors(kTaskDependencyAA)
                            + self.getSuccessors(kTaskDependencyEA),
                        )
                    ),
                    0,
                    False,
                ),
                (
                    Task.READY,
                    [
                        s
                        for s in self.getSuccessors(kTaskDependencyEE)
                        if int(s.status) == Task.NEW.status
                    ],
                    0,
                    False,
                ),
            ]

            if self.ParentTask:
                target_status = self.ParentTask.getFinalStatus()
                if target_status:
                    result.append((target_status, [self.ParentTask], 0, 0))

            return result

    class COMPLETED(State):
        status = 250

        def Constraints(transition, self):
            """
            - Status of all children has to be final (Tasks, Checklists,
              Issues)
            """
            from cs.pcs.checklists import Checklist
            from cs.pcs.issues import Issue

            return [
                (
                    "MatchStateList",
                    [self.Subtasks, Task.endStatus(), "pcstask_wf_rej_3"],
                ),
                (
                    "MatchStateList",
                    [self.Checklists, Checklist.endStatus(), "pcstask_wf_rej_0"],
                ),
                (
                    "MatchStateList",
                    [self.Issues, Issue.endStatus(), "pcstask_wf_rej_8"],
                ),
            ]

        def FollowUpStateChanges(state, self):
            return [(Task.COMPLETED, self.OrderedSubTasks, 0, False)]

    class TO_NEW(Transition):
        transition = ("*", 0)

        def FollowUpStateChanges(transition, self):
            """
            - SubTasks* -> NEW
            - Checklists* -> NEW
            - FS- and SS successors READY -> NEW (if old status was not
              DISCARDED)

            *) If self's old status was DISCARDED, only change SubTasks and
               Checklists which are not in an "end" status. All other
               transitions change SubTasks and Checklists that are not DISCARDED
            """
            from cs.pcs.checklists import Checklist

            old = transition.SourceState(self).status

            result = []

            if old == Task.DISCARDED.status:
                filtered_subtasks = [
                    t for t in self.OrderedSubTasks if t.status in Task.endStatus(False)
                ]
                filtered_checklists = [
                    c for c in self.Checklists if c.status in Checklist.endStatus(False)
                ]
            else:
                result.append(
                    (
                        Task.NEW,
                        [
                            s
                            for s in self.getSuccessors(kTaskDependencyEA)
                            + self.getSuccessors(kTaskDependencyAA)
                            if s.status == self.READY.status
                        ],
                        0,
                        False,
                    )
                )

                filtered_subtasks = [
                    t for t in self.OrderedSubTasks if t.status != Task.DISCARDED.status
                ]
                filtered_checklists = [
                    c for c in self.Checklists if c.status != Checklist.DISCARDED.status
                ]
            return [
                (Task.NEW, filtered_subtasks, 0, False),
                (Checklist.NEW, filtered_checklists, 0, False),
            ] + result

    class TO_READY(Transition):
        transition = ("*", 20)

        def FollowUpStateChanges(transition, self):
            """

            From status NEW:
              - SubTasks NEW -> READY if they have no unfinished FS or FF predecessor

            From status EXECUTION or DISCARDED:
              - SubTasks NEW, EXECUTION -> READY if they have no unfinished FS or FF predecessor
              - All other SubTasks EXECUTION -> NEW
              - Checklists EVALUATION -> NEW

            - (opt-in; only if `__taskrel_constraints__[20]` is `True`)
              SS and FS successors NEW -> READY
            """
            result = []
            old = transition.SourceState(self).status
            conditionMet = self.getInitialSubtasks()

            if old == Task.NEW.status:
                result.append(
                    (
                        Task.READY,
                        [s for s in conditionMet if s.status == Task.NEW.status],
                        0,
                        False,
                    )
                )

            if old in [Task.EXECUTION.status, Task.DISCARDED.status]:
                from cs.pcs.checklists import Checklist

                result.append(
                    (
                        Task.READY,
                        [
                            s
                            for s in conditionMet
                            if s.status in [Task.NEW.status, Task.EXECUTION.status]
                        ],
                        0,
                        False,
                    )
                )
                result.append(
                    (
                        Task.NEW,
                        [
                            s
                            for s in self.OrderedSubTasks
                            if s not in conditionMet
                            and s.status == Task.EXECUTION.status
                        ],
                        0,
                        False,
                    )
                )
                result.append(
                    (
                        Checklist.NEW,
                        [
                            c
                            for c in self.Checklists
                            if c.status == Checklist.EVALUATION.status
                        ],
                        0,
                        False,
                    )
                )

            if self.__taskrel_constraints__[20]:
                result.append(
                    (
                        Task.NEW,
                        [
                            s
                            for s in self.getSuccessors(kTaskDependencyEA)
                            + self.getSuccessors(kTaskDependencyAA)
                            if s.status == Task.READY.status
                        ],
                        0,
                        0,
                    )
                )

            return result

    class FINISHED_EXECUTION(Transition):
        transition = (200, 50)

        def FollowUpStateChanges(state, self):
            """
            - FS Successors READY -> NEW
            """
            return [
                (
                    Task.NEW,
                    [
                        s
                        for s in self.getSuccessors(kTaskDependencyEA)
                        if int(s.status) == Task.READY.status
                    ],
                    0,
                    False,
                ),
            ]

    class TO_FINISHED(Transition):
        transition = ("*", 200)

        def post(state, self, ctx):
            c_ctrl = self.MakeChangeControlAttributes()
            if not ctx.error:
                self.Update(cdb_finishedby=c_ctrl["cdb_mpersno"])

    def msp_to_cdb_consistency_check(self):
        # pylint: disable=too-many-branches
        if self.status == self.NEW.status:
            # propagate status "New" to children
            for subtask in self.Subtasks:
                if subtask.status in [
                    self.READY.status,
                    self.EXECUTION.status,
                    self.FINISHED.status,
                ]:
                    subtask.ChangeState(self.NEW.status)
            for checklist in self.Checklists:
                if checklist.status == checklist.EVALUATION.status:
                    checklist.ChangeState(checklist.NEW.status)

        elif self.status == self.READY.status:
            if [s for s in self.Subtasks if s.status == self.COMPLETED.status]:
                raise ue.Exception("pcs_msp_closed_subtask", self.GetDescription())

            new_predecessors = [
                rel.PredecessorTask
                for rel in self.PredecessorTaskRelations
                if rel.PredecessorTask.status == Task.NEW.status
            ]
            if new_predecessors:
                # reset task if a predecessor is in initial status
                self.ChangeState(self.NEW.status)
            else:
                # aggregate status if children are final and parent is active
                target_status = self.getFinalStatus()
                if target_status:
                    if target_status == self.FINISHED:
                        self.ChangeState(self.EXECUTION.status)
                    self.ChangeState(target_status.status)

        elif self.status == self.EXECUTION.status:
            # aggregate status "execution" to parents
            if self.ParentTask and self.ParentTask.status in [
                self.READY.status,
                self.FINISHED.status,
            ]:
                self.ParentTask.ChangeState(self.EXECUTION.status)
            # aggregate status if children are final and parent is active
            target_status = self.getFinalStatus()
            if target_status:
                self.ChangeState(target_status.status)

        elif self.status == self.FINISHED.status:
            # change parent's status to "execution"
            if self.ParentTask and self.ParentTask.status == self.READY.status:
                self.ParentTask.ChangeState(self.EXECUTION.status)
            # change to "execution" if children are still active
            active_subs = [
                sub
                for sub in self.Subtasks
                if sub.status
                in [self.NEW.status, self.READY.status, self.EXECUTION.status]
            ]
            active_cls = [
                cl
                for cl in self.Checklists
                if cl.status in [cl.NEW.status, cl.EVALUATION.status]
            ]
            active_iss = [
                i
                for i in self.Issues
                if i.status in [i.NEW.status, i.EVALUATION.status]
            ]
            if active_subs or active_cls or active_iss:
                self.ChangeState(self.EXECUTION.status)

        elif self.status == self.COMPLETED.status:
            # make sure final tasks are treated as final
            if self.ParentTask and self.ParentTask.status in [
                self.NEW.status,
                self.READY.status,
            ]:
                raise ue.Exception("pcs_msp_closed_subtask", self.GetDescription())
            non_final = [
                sub
                for sub in self.Subtasks
                if sub.status not in [self.COMPLETED.status, self.DISCARDED.status]
            ]
            if non_final:
                raise ue.Exception("pcs_msp_closed_task", self.GetDescription())

        elif self.status == self.DISCARDED.status:
            # propagate to non-final children
            for sub in self.Subtasks:
                if sub.status not in self.endStatus(False):
                    sub.ChangeState(self.DISCARDED.status)
            for cl in self.Checklists:
                if cl.status not in cl.endStatus(False):
                    cl.ChangeState(cl.DISCARDED.status)
            for i in self.Issues:
                if i.status not in i.endStatus(False):
                    i.ChangeState(i.DISCARDED.status)

        # recursion
        for sub in self.Subtasks:
            sub.msp_to_cdb_consistency_check()


STATUS_CHANGE_ADJUSTMENTS = {
    status_updates.reset_checklists: {"status": [Task.NEW.status]},
    status_updates.reset_start_time_act: {
        "status": [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]
    },
    status_updates.set_start_time_act_to_now: {
        "status": [Task.EXECUTION.status, Task.FINISHED.status],
        "start_time_act": ["", None],
    },
    status_updates.reset_end_time_act: {
        "status": [
            Task.NEW.status,
            Task.READY.status,
            Task.EXECUTION.status,
            Task.DISCARDED.status,
        ]
    },
    status_updates.set_end_time_act_to_now: {
        "status": [Task.FINISHED.status],
        "end_time_act": ["", None],
    },
    status_updates.set_percentage_to_0: {
        "status": [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]
    },
    status_updates.set_percentage_to_1: {"status": [Task.EXECUTION.status]},
    status_updates.set_percentage_to_100: {"status": [Task.FINISHED.status]},
}


def add_status_change_adjustment(method_to_be_called, **arguments):
    STATUS_CHANGE_ADJUSTMENTS[method_to_be_called] = dict(arguments)


def disable_status_change_adjustment(method_to_be_called):
    STATUS_CHANGE_ADJUSTMENTS.pop(method_to_be_called)


@sig.connect("starting_iteration")
@sig.connect("changing_cards")
def enable_update_lock(blocking_object, *args, **kwargs):
    utils.clear_update_stack()
    utils.add_to_change_stack(blocking_object)


@sig.connect("cards_changed")
@sig.connect("iteration_started")
def disable_update_lock(blocking_object, *args, **kwargs):
    changes = utils.remove_from_change_stack(blocking_object)
    if changes:
        projects = Task.get_projects_by_task_object_ids(changes)
        for p in projects:
            p.do_status_updates(changes)
