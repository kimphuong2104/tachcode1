#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import unittest
from cdb import ue
from cdb import testcase

from cs.workflow.tasks import ExecutionTask
from cs.workflow import briefcases
from cs.workflowtest import WFTestFixture
from cs.workflow import process_template


def setup_module():
    testcase.run_level_setup()


def method_is_connected(module, name, *slot):
    slot_names = [
        (x.__module__, x.__name__) for x in
        briefcases.sig.find_slots(*slot)
    ]
    return (module, name) in slot_names


class BriefcaseTestCase(testcase.RollbackTestCase):
    def test_getBriefcases(self):
        "mainly tests default and customized sort order"
        task = ExecutionTask.Create(cdb_process_id="TEST", task_id="TEST")

        for i, name in enumerate("BAC"):
            briefcases.Briefcase.Create(
                cdb_process_id=task.cdb_process_id,
                briefcase_id=i,
                name=name,
            )
            briefcases.BriefcaseLink.Create(
                briefcase_id=i,
                cdb_process_id=task.cdb_process_id,
                task_id=task.task_id,
                iotype=int(i == 0))

        task_briefcases = task.getBriefcases("all")
        self.assertEqual(
            [b.briefcase_id for b in task_briefcases], [1, 0, 2])
        self.assertEqual(
            [b.name for b in task_briefcases], ["A", "B", "C"])

        with mock.patch.object(
            briefcases.WithBriefcase,
            "__briefcase_sorting_key__",
            side_effect=lambda x: x.briefcase_id,
        ):
            task_briefcases = task.getBriefcases("all")
            self.assertEqual(
                [b.briefcase_id for b in task_briefcases], [0, 1, 2])
            self.assertEqual(
                [b.name for b in task_briefcases], ["B", "A", "C"])


class BriefcaseContentTestCase(testcase.RollbackTestCase):
    @mock.patch.object(process_template.json, "dumps")
    @mock.patch.object(process_template.support, "rest_key")
    @mock.patch.object(process_template.entities, "CDBClassDef")
    @mock.patch.object(process_template.relships.Relship, "ByKeys")
    def test_get_create_workflow_from_template_url(self, ByKeys, CDBClassDef, rest_key, dumps):
        ByKeys.return_value = mock.Mock()
        CDBClassDef.return_value = mock.Mock()
        rest_key.return_value = "rest@key"
        dumps.side_effect = [
            '["json_ahwf_content"]', '"json_rest@key"', '"json_classname"',
            '["json_ahwf_content"]', '"json_rest@key"', '"json_classname"'
        ]
        base_url = "/cs-workflow-web/create_from_template"
        expected = set([
            "{}?ahwf_content=%22json_classname%22&classname=%5B%22json_ahwf_content%22%5D&rest_key=%22json_rest%40key%22".
            format(base_url),
        ])
        ctx = mock.MagicMock()
        self.assertIn(
            process_template._get_create_workflow_from_template_url(WFTestFixture, ctx),
            expected
        )
        class Customized(WFTestFixture):
            @classmethod
            def GetFQPYName(cls):
                return "cs.workflow.tests.test_briefcases.Customized"

        # URL should always use base class's classname
        self.assertIn(
            process_template._get_create_workflow_from_template_url(Customized, ctx),
            expected
        )


class BriefcaseContentWhitelist(unittest.TestCase):
    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Query")
    def test_Classnames(self, Query):
        Query.return_value = mock.MagicMock(classname=['cdbwf_task'])
        self.assertEqual(
            briefcases.BriefcaseContentWhitelist.Classnames(),
            set([
                u'cdbwf_task',
                u'cdbwf_task_examination',
                u'cdbwf_task_approval',
                u'cdbwf_task_execution',
                u'cdbwf_interactive_task',
                u'cdbwf_system_task',
            ]),
        )


class OperationConfig(testcase.RollbackTestCase):
    def test_called_after_create(self):
        self.assertTrue(
            method_is_connected(
                "cs.workflow.briefcases",
                "create_whitelist_entry",
                briefcases.OperationConfig,
                "create",
                "post",
            )
        )

    def test_called_after_copy(self):
        self.assertTrue(
            method_is_connected(
                "cs.workflow.briefcases",
                "create_whitelist_entry",
                briefcases.OperationConfig,
                "copy",
                "post",
            )
        )

    def test_called_after_modify(self):
        self.assertTrue(
            method_is_connected(
                "cs.workflow.briefcases",
                "create_whitelist_entry",
                briefcases.OperationConfig,
                "modify",
                "post",
            )
        )

    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Create")
    def test_create_whitelist_entry_error(self, Create):
        ctx = mock.Mock(error=True)
        self.assertIsNone(briefcases.create_whitelist_entry(None, ctx))
        Create.assert_not_called()

    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Create")
    def test_create_whitelist_entry_irrelevant_op(self, Create):
        op = mock.Mock()
        op.name = "foo"
        ctx = mock.Mock(error=False)
        self.assertIsNone(briefcases.create_whitelist_entry(op, ctx))
        Create.assert_not_called()

    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Classnames",
                       return_value=["foo"])
    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Create")
    def test_create_whitelist_entry_already_whitelisted(self, Create, _):
        op = mock.Mock(classname="foo")
        op.name = "cdbwf_ahwf_new"
        ctx = mock.Mock(error=False)
        self.assertIsNone(briefcases.create_whitelist_entry(op, ctx))
        Create.assert_not_called()

    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Classnames",
                       return_value=[])
    @mock.patch.object(briefcases.BriefcaseContentWhitelist, "Create")
    def test_create_whitelist_entry(self, Create, _):
        op = mock.Mock(
            classname="foo",
            cdb_module_id="bar",
        )
        op.name = "cdbwf_ahwf_new"
        ctx = mock.Mock(error=False)
        self.assertIsNone(briefcases.create_whitelist_entry(op, ctx))
        Create.assert_called_once_with(classname="foo", cdb_module_id="bar")


class FolderContent(testcase.RollbackTestCase):
    """Test user exits of FolderContent classbody"""
    __org__ = "eb5af880-4be0-11e0-a016-005056c00008"
    __usr__ = "99504583-76e1-11de-a2d5-986f0c508d59"

    maxDiff = None

    @mock.patch.object(briefcases.BriefcaseContentWhitelist, 'Query')
    @mock.patch.object(briefcases, "ByID")
    def test_check_valid_content_other_folders(self, ByID, Query):
        self.assertIsNone(
            briefcases.FolderContent().check_valid_content(mock.MagicMock())
        )

        Query.assert_not_called()
        ByID.assert_not_called()

    @mock.patch.object(briefcases.BriefcaseContentWhitelist, 'Classnames')
    def test_check_valid_content(self, Classnames):
        Classnames.return_value = ['angestellter', 'cdbwf_task']

        self.assertIsNone(
            briefcases.FolderContent.check_valid_content(
                mock.MagicMock(
                    spec=briefcases.FolderContent,
                    Briefcase="foo",
                    cdb_content_id=self.__usr__,
                ),
                None,
            )
        )

    @mock.patch.object(process_template.logging, 'exception')
    @mock.patch.object(process_template, 'ByID')
    def test_content_in_whitelist(self, ByID, exception):
        ByID.return_value.GetClassname.return_value = "cdbwf_task"
        with mock.patch('cs.workflow.briefcases.BriefcaseContentWhitelist.Classnames', return_value=['angestellter', 'cdbwf_task']):
            process_template.content_in_whitelist("OID_1")
        exception.assert_not_called()

    @mock.patch.object(process_template.logging, 'exception')
    @mock.patch.object(process_template, 'ByID')
    def test_content_not_in_whitelist(self, ByID, exception):
        ByID.return_value.GetClassname.return_value = "cdbpcs_project"
        with mock.patch('cs.workflow.briefcases.BriefcaseContentWhitelist.Classnames', return_value=['angestellter', 'cdbwf_task']):
            with self.assertRaises(Exception):
                process_template.content_in_whitelist("OID_2")
        exception.assert_called_once()

    def test_check_valid_content_unknown_obj(self):
        with self.assertRaises(ue.Exception) as error:
            briefcases.FolderContent.check_valid_content(
                mock.MagicMock(
                    spec=briefcases.FolderContent,
                    Briefcase="foo",
                    cdb_content_id="does not exist",
                ),
                None
            )

        self.assertEqual(
            str(error.exception),
            str(ue.Exception(
                'cdbwf_briefcase_unknown_obj',
                'does not exist',
            ))
        )
