#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
from cdb import auth, testcase, ue
from cdb.objects import ByID
from cdb.objects.rules import Rule
from cs.workflow.constraints import Constraint
from cs.workflow.processes import Process
from cs.workflow.tasks import ApprovalTask,Task
from cs.workflow.taskgroups import ParallelTaskGroup


WF_OID = "42507da1-c86a-11e8-b50b-5cc5d4123f3b"
TASK_OID = "464892cf-c86a-11e8-9558-5cc5d4123f3b"
WRAPPER_OID = "03d8ab8f-22e4-11e9-97e9-68f7284ff046"
RULE_NAME = "wf-designer: process completing successfully"
BRIEFCASE_OID = "e0a0e70f-c86a-11e8-a02e-5cc5d4123f3b"


def setup_module():
    testcase.run_level_setup()


class ConstraintTestCase(testcase.RollbackTestCase):
    def _setup_constraint(self, **kwargs):
        self.process = ByID(WF_OID)
        self.task = ByID(TASK_OID)
        self.briefcase = ByID(BRIEFCASE_OID)
        self.rule = Rule.ByKeys(RULE_NAME)
        self.rule_wrapper = ByID(WRAPPER_OID)
        vals = {
            "cdb_process_id": "JSON_TEST",
            "task_id": "T00003984",
            "briefcase_id": 147,
            "rule_name": WRAPPER_OID,
            "invert_rule": 0,
        }
        vals.update(kwargs)
        self.constraint = Constraint.Create(**vals)

    def test_references(self):
        self._setup_constraint()
        self.assertEqual(
            self.constraint.Briefcase,
            self.briefcase
        )

    def test_WithRuleWrapper(self):
        self._setup_constraint()
        self.assertEqual(
            self.constraint.RuleWrapper,
            self.rule_wrapper
        )
        self.assertEqual(
            self.constraint.Rule,
            self.rule
        )
        self.assertEqual(
            self.constraint.getRuleName(),
            self.rule_wrapper.name
        )

    def test_get_message_constraint_violated(self):
        self._setup_constraint(briefcase_id=None)

        with self.assertRaises(AttributeError):
            self.constraint.get_message_constraint_violated(None)

        self.assertEqual(
            self.constraint.get_message_constraint_violated(self.process),
            u"Constraint verletzt (Objekt='JSON Test (Wdh. 0)', "
            u"Regel='Workflow abgeschlossen')"
        )
        # mock task.GetDescription to avoid language depending differences
        # in casting numerical values ('.' or ',' as seperator)
        self.task.GetDescription = mock.MagicMock(return_value="foo")
        self.assertEqual(
            self.constraint.get_message_constraint_violated(self.task),
            u"Constraint verletzt (Objekt='foo', "
            u"Regel='Workflow abgeschlossen')"
        )

    def test_get_message_constraint_violated_Briefcase(self):
        self._setup_constraint()
        for parent in [None, self.process, self.task]:
            self.assertEqual(
                self.constraint.get_message_constraint_violated(parent),
                u"Constraint verletzt (Objekt='Testformular 1', "
                u"Regel='Workflow abgeschlossen')"
            )

    def test_is_violated(self):
        self._setup_constraint(briefcase_id=None)
        for parent in [None, self.process]:
            self.assertEqual(
                self.constraint.is_violated(parent),
                True
            )
        self.assertEqual(
            self.constraint.is_violated(self.task),
            False
        )

    def test_is_violated_inverted(self):
        self._setup_constraint(briefcase_id=None, invert_rule=1)
        for parent in [None, self.process]:
            self.assertEqual(
                self.constraint.is_violated(parent),
                False
            )
        self.assertEqual(
            self.constraint.is_violated(self.task),
            True
        )

    def test_is_violated_Briefcase(self):
        self._setup_constraint()
        for parent in [None, self.process, self.task]:
            self.assertEqual(
                self.constraint.is_violated(parent),
                True
            )

    def test_check_violation(self):
        self._setup_constraint()
        with self.assertRaises(AttributeError):
            self.constraint.check_violation(None)

        for parent in [self.process, self.task]:
            with self.assertRaises(ue.Exception):
                self.constraint.check_violation(parent)
                # Constraint verletzt (Objekt='Testformular 1', Regel='Workflow abgeschlossen')

    def create_wf_with_constraints(self, discarded_tasks=None, completed_tasks=None):
        completed_tasks.append("A")
        Process.Create(
            cdb_process_id="wf_id",
            status=Process.EXECUTION.status
        )
        ParallelTaskGroup.Create(
            cdb_process_id="wf_id",
            task_id="par",
            position=15,
            status=0,
            parent_id=""
            )
        tasks = [("A", 11, ""), ("B", 12, "par"), ("C", 13, "par"), ("D", 16, "")]
        task_dict = {}
        for t_id, position, parent in tasks:
            task_dict[t_id] = ApprovalTask.Create(
                cdb_process_id="wf_id",
                task_id=t_id,
                position=position,
                parent_id=parent,
                subject_id=auth.persno,
                subject_type="Person",
                status=ApprovalTask.COMPLETED.status if t_id in completed_tasks else 0
                )
        for task in discarded_tasks:
            task_to_discard = task_dict[task]
            task_to_discard.Update(status=task_to_discard.DISCARDED.status)
        return task_dict

    def test_tasks_with_constraints_all_completed(self):
        task_dict = self.create_wf_with_constraints(
            discarded_tasks=[],
            completed_tasks=["B", "C"])
        task = task_dict["D"]
        self.assertEqual(task.PreviousTasks, [task_dict["B"], task_dict["C"]])

    def test_tasks_with_constraints_C_discarded(self):
        task_dict = self.create_wf_with_constraints(
            discarded_tasks=["C"],
            completed_tasks=["B"])
        task = task_dict["D"]
        self.assertEqual(task.PreviousTasks, [task_dict["B"]])

    def test_tasks_with_constraints_B_discarded(self):
        task_dict = self.create_wf_with_constraints(
            discarded_tasks=["B"],
            completed_tasks=["C"])
        task = Task.ByKeys(cdb_process_id="wf_id", task_id="D")
        self.assertEqual(task.PreviousTasks, [task_dict["C"]])

    def test_tasks_with_constraints_B_C_discarded(self):
        task_dict = self.create_wf_with_constraints(
            discarded_tasks=["B", "C"],
            completed_tasks=[])
        task = task_dict["D"]
        self.assertEqual(task.PreviousTasks, [task_dict["A"]])

    def test_tasks_with_constraints_C_failed(self):
        task_dict = self.create_wf_with_constraints(
            discarded_tasks=[],
            completed_tasks=["B"])
        task = task_dict["C"]
        task.Update(status=task.REJECTED.status)
        task = task_dict["D"]
        self.assertEqual(task.PreviousTasks, [task_dict["B"], task_dict["C"]])

    def test_tasks_with_constraints_B_failed(self):
        task_dict = self.create_wf_with_constraints(
            discarded_tasks=[],
            completed_tasks=["C"])
        task = task_dict["B"]
        task.Update(status=task.REJECTED.status)
        task = task_dict["D"]
        self.assertEqual(task.PreviousTasks, [task_dict["B"], task_dict["C"]])

