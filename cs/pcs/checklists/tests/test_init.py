#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,too-many-lines,consider-using-f-string

import datetime
import os
import unittest

import mock
import pytest
from cdb import testcase
from cdb.objects import ObjectCollection

from cs.pcs import checklists
from cs.pcs.projects.project_status import Project


@pytest.mark.unit
class Checklist(testcase.RollbackTestCase):
    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_checkState_task_id_changed_NEW(self, Exception_):
        "does nothing if task_id was changed and status is NEW"
        cl = checklists.Checklist(status=checklists.Checklist.NEW.status)
        ctx = mock.MagicMock()
        ctx.object.task_id = "foo"
        self.assertIsNone(cl.checkState(ctx))
        self.assertEqual(Exception_.call_count, 0)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkState_task_id_changed_not_NEW(self, CDBMsg):
        "fails if task_id was changed and status is not NEW"
        cl = checklists.Checklist(status=42)
        ctx = mock.MagicMock()
        ctx.object.task_id = "foo"

        with self.assertRaises(checklists.ue.Exception):
            cl.checkState(ctx)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_err_cl_move")

    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_checkState_task_not_completed(self, Exception_):
        "does nothing if task has not been completed yet"
        cl = checklists.Checklist()
        ctx = mock.MagicMock(object=None)
        task = mock.MagicMock(spec=checklists.Task, status="not end")
        task.endStatus.return_value = ["end"]

        with mock.patch.object(
            checklists.Checklist,
            "Task",
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            self.assertIsNone(cl.checkState(ctx))

        self.assertEqual(Exception_.call_count, 0)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkState_task_completed(self, CDBMsg):
        "fails if task has already been completed"
        cl = checklists.Checklist()
        ctx = mock.MagicMock(object=None)
        task = mock.MagicMock(spec=checklists.Task, status="end")
        task.endStatus.return_value = ["end"]

        with mock.patch.object(
            checklists.Checklist,
            "Task",
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            with self.assertRaises(checklists.ue.Exception):
                cl.checkState(ctx)

        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "cdbpcs_err_task_checklist",
        )

    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_checkState_no_task_or_proj(self, Exception_):
        "does nothing if task is missing both Task and Project"
        cl = checklists.Checklist()
        ctx = mock.MagicMock(object=None)
        self.assertIsNone(cl.checkState(ctx))
        self.assertEqual(Exception_.call_count, 0)

    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_checkState_project_not_ended(self, Exception_):
        "does nothing if Project has not been completed yet"
        cl = checklists.Checklist()
        ctx = mock.MagicMock(object=None)
        project = mock.MagicMock(spec=Project, status="not end")
        project.endStatus.return_value = ["end"]

        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            self.assertIsNone(cl.checkState(ctx))

        project.endStatus.assert_called_once_with(False)
        self.assertEqual(Exception_.call_count, 0)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkState_project_ended(self, CDBMsg):
        "fails if Project has already been completed"
        cl = checklists.Checklist()
        ctx = mock.MagicMock(object=None)
        project = mock.MagicMock(spec=Project, status="end")
        project.endStatus.return_value = ["end"]

        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            with self.assertRaises(checklists.ue.Exception):
                cl.checkState(ctx)

        project.endStatus.assert_called_once_with(False)
        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "cdbpcs_err_project_checklist",
        )

    @mock.patch.object(checklists.Checklist, "calcRating", return_value=42)
    @mock.patch.object(checklists.Checklist, "Update")
    def test_setRating_without_force_new(self, update, calc_rating):
        """Test for setRating without force and checklist in NEW"""
        checklist = checklists.Checklist()
        checklist.status = checklists.Checklist.NEW.status
        checklist.setRating()
        calc_rating.assert_called_once_with(
            checklist.cdb_project_id, checklist.checklist_id, None
        )
        update.assert_called_once_with(rating_id=42)

    @mock.patch.object(checklists.Checklist, "calcRating", return_value=42)
    @mock.patch.object(checklists.Checklist, "Update")
    def test_setRating_with_force_completed(self, update, calc_rating):
        """Test for setRating with force, checklist in COMPLETED and ParentCheckListItem"""
        checklist = checklists.Checklist()
        checklist.status = checklists.Checklist.COMPLETED.status

        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        checklistitem.calcRating.return_value = 24
        checklistitem.rating_id = 10

        with mock.patch.object(
            checklists.Checklist,
            "ParentChecklistItem",
            new_callable=mock.PropertyMock,
            return_value=checklistitem,
        ):
            checklist.setRating(force=True)
            calc_rating.assert_called_once_with(
                checklist.cdb_project_id, checklist.checklist_id, None
            )
            update.assert_called_once_with(rating_id=42)
            checklistitem.calcRating.assert_called_once_with(
                checklistitem.cdb_project_id,
                checklistitem.checklist_id,
                checklistitem.cl_item_id,
            )
            self.assertEqual(checklistitem.rating_id, 24)

    @mock.patch.object(checklists.Checklist, "calcRating", return_value=42)
    @mock.patch.object(checklists.Checklist, "Update")
    def test_setRating_with_force_completed_no_rating(self, update, calc_rating):
        """Test for setRating with force, checklist in COMPLETED and ParentCheckListItem without rating"""
        checklist = checklists.Checklist()
        checklist.status = checklists.Checklist.COMPLETED.status

        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        checklistitem.calcRating.return_value = None
        checklistitem.rating_id = 10

        with mock.patch.object(
            checklists.Checklist,
            "ParentChecklistItem",
            new_callable=mock.PropertyMock,
            return_value=checklistitem,
        ):
            checklist.setRating(force=True)
            calc_rating.assert_called_once_with(
                checklist.cdb_project_id, checklist.checklist_id, None
            )
            update.assert_called_once_with(rating_id=42)
            checklistitem.calcRating.assert_called_once_with(
                checklistitem.cdb_project_id,
                checklistitem.checklist_id,
                checklistitem.cl_item_id,
            )
            self.assertEqual(checklistitem.rating_id, 10)

    @mock.patch.object(checklists, "allocate_license")
    def test_checkLicense_QualityGate(self, allocate_license):
        """Test for checkLicense with a QualityGate type"""
        checklist = checklists.Checklist()
        checklist.type = "QualityGate"
        checklist.checkLicense()
        allocate_license.assert_called_once_with("CHECKLISTS_006")

    @mock.patch.object(checklists, "allocate_license")
    def test_checkLicense_Deliverable(self, allocate_license):
        """Test for checkLicense with a Deliverable type"""
        checklist = checklists.Checklist()
        checklist.type = "Deliverable"
        checklist.checkLicense()
        allocate_license.assert_called_once_with("CHECKLISTS_007")

    @mock.patch.object(checklists, "allocate_license")
    def test_checkLicense_Foo(self, allocate_license):
        """Test for checkLicense with a random type"""
        checklist = checklists.Checklist()
        checklist.type = "Foo"
        checklist.checkLicense()
        allocate_license.assert_not_called()

    @mock.patch.object(checklists.util, "nextval", return_value=0)
    def test_setChecklistID_first_time(self, nextval):
        """Test setChecklistID with first run"""
        checklist = checklists.Checklist()
        checklist.setChecklistID(None)
        nextval.assert_has_calls(
            [mock.call("cdbpcs_checklist"), mock.call("cdbpcs_checklist")]
        )

    @mock.patch.object(checklists.util, "nextval", return_value=1)
    def test_setChecklistID_other_times(self, nextval):
        """Test setChecklistID in any other run"""
        checklist = checklists.Checklist()
        checklist.setChecklistID(None)
        nextval.assert_called_once_with("cdbpcs_checklist")

    def test_updateParentCheckpoint_with_parent(self):
        """Test updateParentCheckpoint with a parent"""
        ctx = mock.Mock(spec=["error"])
        ctx.error = False

        checklist = checklists.Checklist()
        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        with mock.patch.object(
            checklists.Checklist,
            "ParentChecklistItem",
            new_callable=mock.PropertyMock,
            return_value=checklistitem,
        ):
            checklist.updateParentCheckpoint(ctx)
            checklistitem.updateSubChecklistsFlag.assert_called_once()

    def test_updateParentCheckpoint_without_parent(self):
        """Test updateParentCheckpoint without a parent"""
        ctx = mock.Mock(spec=["error"])
        ctx.error = False

        checklist = checklists.Checklist()
        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        with mock.patch.object(
            checklists.Checklist,
            "ParentChecklistItem",
            new_callable=mock.PropertyMock,
            return_value=[],
        ):
            checklist.updateParentCheckpoint(ctx)
            checklistitem.updateSubChecklistsFlag.assert_not_called()

    def test_updateParentCheckpoint_with_error(self):
        """Test updateParentCheckpoint with an error"""
        ctx = mock.Mock(spec=["error"])
        ctx.error = True

        checklist = checklists.Checklist()
        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        with mock.patch.object(
            checklists.Checklist,
            "ParentChecklistItem",
            new_callable=mock.PropertyMock,
            return_value=[],
        ):
            checklist.updateParentCheckpoint(ctx)
            checklistitem.updateSubChecklistsFlag.assert_not_called()

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.Checklist, "KeyDict", return_value={"a": 1, "b": 2})
    def test_copyDraggedChecklists_with_object_checklist_item_and_no_clitmpl(
        self, KeyDict
    ):
        """Test copyDraggedChecklists with an object, a checklist item and no checklist item tmpl"""

        def table_side_effect(*args, **kwargs):
            table = mock.MagicMock(autospec=checklists.ddl.Table)
            if "cdbpcs_cli2doctmpl" in args:
                table.exists.return_value = True
            else:
                table.exists.return_value = True
            return table

        ctx = mock.Mock(spec=["dragged_obj"])
        ctx.dragged_obj.cdb_project_id = "project_id_do"
        ctx.dragged_obj.checklist_id = 10

        checklist = checklists.Checklist()
        checklist.cdb_project_id = "project_id"
        checklist.checklist_id = 10
        checklist.MakeChangeControlAttributes = lambda: {"change": "control"}

        templatedocref = mock.MagicMock()

        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        copied_checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        dragged_checklist = mock.MagicMock(autospec=checklists.Checklist)
        dragged_checklist.ChecklistItems = [checklistitem]
        dragged_checklist.TemplateDocRefs = [templatedocref]

        checklistitem.Copy.return_value = copied_checklistitem
        checklistitem.GetText.return_value = "foo"
        checklistitem.TemplateDocRefs = []
        with mock.patch.object(
            checklists.Checklist, "ByKeys", return_value=dragged_checklist
        ):
            with mock.patch("cdb.ddl.Table", side_effect=table_side_effect):
                checklist.copyDraggedChecklists(ctx)
                checklistitem.Copy.assert_called_once_with(
                    cdb_project_id=checklist.cdb_project_id,
                    checklist_id=checklist.checklist_id,
                    has_sub_cl=0,
                    change="control",
                    template=None,
                )
                copied_checklistitem.Reset.assert_called_once()
                copied_checklistitem.SetText.assert_has_calls(
                    [
                        mock.call("cdbpcs_cli_txt", "foo"),
                        mock.call("cdbpcs_clir_txt", "foo"),
                    ]
                )
                checklistitem.GetText.assert_has_calls(
                    [mock.call("cdbpcs_cli_txt"), mock.call("cdbpcs_clir_txt")]
                )
                templatedocref.Copy.assert_has_calls([mock.call(a=1, b=2)])
                KeyDict.assert_has_calls([mock.call()])

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.Checklist, "KeyDict", return_value={"a": 1, "b": 2})
    def test_copyDraggedChecklists_with_object_checklist_item_and_no_cltmpl(
        self, KeyDict
    ):
        """Test copyDraggedChecklists with an object, a checklist item and no checklist tmpl"""

        def table_side_effect(*args, **kwargs):
            table = mock.MagicMock(autospec=checklists.ddl.Table)
            if "cdbpcs_cli2doctmpl" in args:
                table.exists.return_value = True
            else:
                table.exists.return_value = True
            return table

        ctx = mock.Mock(spec=["dragged_obj"])
        ctx.dragged_obj.cdb_project_id = "project_id_do"
        ctx.dragged_obj.checklist_id = 10

        checklist = checklists.Checklist()
        checklist.cdb_project_id = "project_id"
        checklist.checklist_id = 10
        checklist.MakeChangeControlAttributes = lambda: {"change": "control"}

        templatedocref = mock.MagicMock()

        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        copied_checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        dragged_checklist = mock.MagicMock(autospec=checklists.Checklist)
        dragged_checklist.ChecklistItems = [checklistitem]
        dragged_checklist.TemplateDocRefs = []

        checklistitem.Copy.return_value = copied_checklistitem
        checklistitem.GetText.return_value = "foo"
        checklistitem.TemplateDocRefs = [templatedocref]
        with mock.patch.object(
            checklists.Checklist, "ByKeys", return_value=dragged_checklist
        ):
            with mock.patch("cdb.ddl.Table", side_effect=table_side_effect):
                checklist.copyDraggedChecklists(ctx)
                checklistitem.Copy.assert_called_once_with(
                    cdb_project_id=checklist.cdb_project_id,
                    checklist_id=checklist.checklist_id,
                    has_sub_cl=0,
                    change="control",
                    template=None,
                )
                copied_checklistitem.Reset.assert_called_once()
                copied_checklistitem.SetText.assert_has_calls(
                    [
                        mock.call("cdbpcs_cli_txt", "foo"),
                        mock.call("cdbpcs_clir_txt", "foo"),
                    ]
                )
                checklistitem.GetText.assert_has_calls(
                    [mock.call("cdbpcs_cli_txt"), mock.call("cdbpcs_clir_txt")]
                )
                templatedocref.Copy.assert_has_calls([mock.call(a=1, b=2)])
                KeyDict.assert_has_calls([mock.call()])

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.Checklist, "KeyDict", return_value={"a": 1, "b": 2})
    def test_copyDraggedChecklists_with_object_checklist_item_and_no_tmpl(
        self, KeyDict
    ):
        """Test copyDraggedChecklists with an object, a checklist item and no tmpl"""

        def table_side_effect(*args, **kwargs):
            table = mock.MagicMock(autospec=checklists.ddl.Table)
            if "cdbpcs_cli2doctmpl" in args:
                table.exists.return_value = True
            else:
                table.exists.return_value = True
            return table

        ctx = mock.Mock(spec=["dragged_obj"])
        ctx.dragged_obj.cdb_project_id = "project_id_do"
        ctx.dragged_obj.checklist_id = 10

        checklist = checklists.Checklist()
        checklist.cdb_project_id = "project_id"
        checklist.checklist_id = 10
        checklist.MakeChangeControlAttributes = lambda: {"change": "control"}

        templatedocref = mock.MagicMock()

        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        copied_checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        dragged_checklist = mock.MagicMock(autospec=checklists.Checklist)
        dragged_checklist.ChecklistItems = [checklistitem]
        dragged_checklist.TemplateDocRefs = []

        checklistitem.Copy.return_value = copied_checklistitem
        checklistitem.GetText.return_value = "foo"
        checklistitem.TemplateDocRefs = []
        with mock.patch.object(
            checklists.Checklist, "ByKeys", return_value=dragged_checklist
        ):
            with mock.patch("cdb.ddl.Table", side_effect=table_side_effect):
                checklist.copyDraggedChecklists(ctx)
                checklistitem.Copy.assert_called_once_with(
                    cdb_project_id=checklist.cdb_project_id,
                    checklist_id=checklist.checklist_id,
                    has_sub_cl=0,
                    change="control",
                    template=None,
                )
                copied_checklistitem.Reset.assert_called_once()
                copied_checklistitem.SetText.assert_has_calls(
                    [
                        mock.call("cdbpcs_cli_txt", "foo"),
                        mock.call("cdbpcs_clir_txt", "foo"),
                    ]
                )
                checklistitem.GetText.assert_has_calls(
                    [mock.call("cdbpcs_cli_txt"), mock.call("cdbpcs_clir_txt")]
                )
                templatedocref.Copy.assert_not_called()
                KeyDict.assert_not_called()

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.Checklist, "KeyDict", return_value={"a": 1, "b": 2})
    def test_copyDraggedChecklists_without_object_checklist_item_and_cltmpl(
        self, KeyDict
    ):
        """Test copyDraggedChecklists without an object, a checklist item and no checklist tmpl"""

        def table_side_effect(*args, **kwargs):
            table = mock.MagicMock(autospec=checklists.ddl.Table)
            if "cdbpcs_cli2doctmpl" in args:
                table.exists.return_value = True
            else:
                table.exists.return_value = True
            return table

        ctx = mock.Mock(spec=["dragged_obj"])
        ctx.dragged_obj.cdb_project_id = "project_id_do"
        ctx.dragged_obj.checklist_id = 10

        checklist = checklists.Checklist()
        checklist.cdb_project_id = "project_id"
        checklist.checklist_id = 10

        templatedocref = mock.MagicMock()

        dragged_checklist = mock.MagicMock(autospec=checklists.Checklist)
        dragged_checklist.ChecklistItems = []
        dragged_checklist.TemplateDocRefs = [templatedocref]

        with mock.patch.object(
            checklists.Checklist, "ByKeys", return_value=dragged_checklist
        ):
            with mock.patch("cdb.ddl.Table", side_effect=table_side_effect):
                checklist.copyDraggedChecklists(ctx)
                templatedocref.Copy.assert_has_calls([mock.call(a=1, b=2)])
                KeyDict.assert_has_calls([mock.call()])

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.Checklist, "KeyDict", return_value={"a": 1, "b": 2})
    def test_copyDraggedChecklists_with_object_and_checklist_item(self, KeyDict):
        """Test copyDraggedChecklists without an object, a checklist item and checklist item tmpl"""

        def table_side_effect(*args, **kwargs):
            table = mock.MagicMock(autospec=checklists.ddl.Table)
            if "cdbpcs_cli2doctmpl" in args:
                table.exists.return_value = True
            else:
                table.exists.return_value = True
            return table

        ctx = mock.Mock(spec=["dragged_obj"])
        ctx.dragged_obj.cdb_project_id = "project_id_do"
        ctx.dragged_obj.checklist_id = 10

        checklist = checklists.Checklist()
        checklist.cdb_project_id = "project_id"
        checklist.checklist_id = 10
        checklist.MakeChangeControlAttributes = lambda: {"change": "control"}

        templatedocref = mock.MagicMock()

        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        copied_checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)
        dragged_checklist = mock.MagicMock(autospec=checklists.Checklist)
        dragged_checklist.ChecklistItems = [checklistitem]
        dragged_checklist.TemplateDocRefs = [templatedocref]

        checklistitem.Copy.return_value = copied_checklistitem
        checklistitem.GetText.return_value = "foo"
        checklistitem.TemplateDocRefs = [templatedocref]

        with mock.patch.object(
            checklists.Checklist, "ByKeys", return_value=dragged_checklist
        ):
            with mock.patch("cdb.ddl.Table", side_effect=table_side_effect):
                checklist.copyDraggedChecklists(ctx)
                checklistitem.Copy.assert_called_once_with(
                    cdb_project_id=checklist.cdb_project_id,
                    checklist_id=checklist.checklist_id,
                    has_sub_cl=0,
                    change="control",
                    template=None,
                )
                copied_checklistitem.Reset.assert_called_once()
                copied_checklistitem.SetText.assert_has_calls(
                    [
                        mock.call("cdbpcs_cli_txt", "foo"),
                        mock.call("cdbpcs_clir_txt", "foo"),
                    ]
                )
                checklistitem.GetText.assert_has_calls(
                    [mock.call("cdbpcs_cli_txt"), mock.call("cdbpcs_clir_txt")]
                )
                templatedocref.Copy.assert_has_calls(
                    [mock.call(a=1, b=2), mock.call(a=1, b=2)]
                )
                KeyDict.assert_has_calls([mock.call(), mock.call()])

    def test_check_project_role_needed(self):
        """Test check_project_role_needed"""
        checklist = checklists.Checklist()
        project = mock.MagicMock()
        ctx = mock.Mock(spec=[])
        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            checklist.check_project_role_needed(ctx)
            project.check_project_role_needed.assert_called_once_with(ctx)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    def test_on_create_pre_mask_with_project_in_cdbpcs_cl_item2checklist_with_dnd(self):
        """Test on_create_pre_mask with project in cdbpcs_cl_item2checklist and dnd"""
        ctx = mock.Mock(
            spec=["set", "relationship_name", "parent", "set_readonly", "dragged_obj"]
        )
        ctx.parent.cdb_project_id = "PARENT Project"
        ctx.parent.checklist_id = 10
        ctx.dragged_obj.type = "Test Type"
        ctx.dragged_obj.rating_scheme = "Test Scheme"
        ctx.dragged_obj.subject_id = "Test Person"
        ctx.dragged_obj.subject_type = "Person"
        ctx.dragged_obj.auto = 1
        ctx.dragged_obj.rating_id = "clear"
        ctx.relationship_name = "cdbpcs_cl_item2checklist"

        parent_checklist = mock.MagicMock(autospec=checklists.Checklist())
        parent_checklist.template = 1
        parent_checklist.rating_scheme = "TEST Scheme"
        parent_checklist.type = "TEST"

        checklist = checklists.Checklist()
        project = mock.MagicMock()
        project.project_name = "TEST Project"
        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            with mock.patch.object(
                checklists.Checklist, "ByKeys", return_value=parent_checklist
            ):
                with mock.patch.object(
                    checklists.auth, "get_department", return_value="my_test_department"
                ):

                    checklist.on_create_pre_mask(ctx)
                    checklists.auth.get_department.assert_called_once()
                    self.assertEqual(checklist.division, "my_test_department")
                    ctx.set.assert_called_once_with(
                        "project_name", project.project_name
                    )
                    checklists.Checklist.ByKeys.assert_called_once_with(
                        cdb_project_id=ctx.parent.cdb_project_id,
                        checklist_id=ctx.parent.checklist_id,
                    )
                    self.assertEqual(checklist.template, parent_checklist.template)
                    ctx.set_readonly.assert_called_once_with("template")

                    self.assertEqual(
                        checklist.rating_scheme, ctx.dragged_obj.rating_scheme
                    )
                    self.assertEqual(checklist.type, ctx.dragged_obj.type)
                    self.assertEqual(checklist.subject_id, ctx.dragged_obj.subject_id)
                    self.assertEqual(
                        checklist.subject_type, ctx.dragged_obj.subject_type
                    )
                    self.assertEqual(checklist.auto, ctx.dragged_obj.auto)
                    self.assertEqual(checklist.rating_id, ctx.dragged_obj.rating_id)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    def test_on_create_pre_mask_with_project_in_cdbpcs_cl_item2checklist(self):
        """Test on_create_pre_mask with project in cdbpcs_cl_item2checklist"""
        ctx = mock.Mock(
            spec=["set", "relationship_name", "parent", "set_readonly", "dragged_obj"]
        )
        ctx.parent.cdb_project_id = "PARENT Project"
        ctx.parent.checklist_id = 10
        ctx.relationship_name = "cdbpcs_cl_item2checklist"
        ctx.dragged_obj = ""

        parent_checklist = mock.MagicMock(autospec=checklists.Checklist())
        parent_checklist.template = 1
        parent_checklist.rating_scheme = "TEST Scheme"
        parent_checklist.type = "TEST"

        checklist = checklists.Checklist()
        project = mock.MagicMock()
        project.project_name = "TEST Project"
        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            with mock.patch.object(
                checklists.Checklist, "ByKeys", return_value=parent_checklist
            ):
                with mock.patch.object(
                    checklists.auth, "get_department", return_value="my_test_department"
                ):
                    checklist.on_create_pre_mask(ctx)
                    checklists.auth.get_department.assert_called_once()
                    self.assertEqual(checklist.division, "my_test_department")
                    ctx.set.assert_called_once_with(
                        "project_name", project.project_name
                    )
                    checklists.Checklist.ByKeys.assert_called_once_with(
                        cdb_project_id=ctx.parent.cdb_project_id,
                        checklist_id=ctx.parent.checklist_id,
                    )
                    self.assertEqual(checklist.template, parent_checklist.template)
                    self.assertEqual(
                        checklist.rating_scheme, parent_checklist.rating_scheme
                    )
                    self.assertEqual(checklist.type, parent_checklist.type)
                    ctx.set_readonly.assert_called_once_with("template")

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    def test_on_create_pre_mask_with_project(self):
        """Test on_create_pre_mask with project"""
        ctx = mock.Mock(
            spec=["set", "relationship_name", "parent", "set_readonly", "dragged_obj"]
        )
        ctx.parent.cdb_project_id = "PARENT Project"
        ctx.parent.checklist_id = 10
        ctx.relationship_name = ""
        ctx.dragged_obj = None

        parent_checklist = mock.MagicMock(autospec=checklists.Checklist())
        parent_checklist.template = 1
        parent_checklist.rating_sheme = "TEST Scheme"
        parent_checklist.type = "TEST"

        checklist = checklists.Checklist()
        project = mock.MagicMock()
        project.project_name = "TEST Project"
        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            with mock.patch.object(
                checklists.Checklist, "ByKeys", return_value=parent_checklist
            ):
                with mock.patch.object(
                    checklists.auth, "get_department", return_value="my_test_department"
                ):
                    checklist.on_create_pre_mask(ctx)
                    checklists.auth.get_department.assert_called_once()
                    self.assertEqual(checklist.division, "my_test_department")
                    ctx.set.assert_called_once_with(
                        "project_name", project.project_name
                    )
                    checklists.Checklist.ByKeys.assert_not_called()
                    ctx.set_readonly.assert_not_called()

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    def test_on_create_pre_mask_without_project_in_cdbpcs_doc2topchecklists_with_preset_and_dnd(
        self,
    ):
        """Test on_create_pre_mask without_project in cdbpcs_doc2topchecklists with preset and dnd"""
        ctx = mock.Mock(
            spec=["set", "relationship_name", "parent", "set_readonly", "dragged_obj"]
        )
        ctx.parent.cdb_project_id = "PARENT Project"
        ctx.parent.checklist_id = 10
        ctx.dragged_obj = ""
        ctx.relationship_name = "cdbpcs_doc2topchecklists"

        checklist = checklists.Checklist()
        checklist.cdb_project_id = "foo"
        project = None
        parent_project = mock.MagicMock()
        parent_project.project_name = "TEST Project"
        with mock.patch.object(
            checklists.Checklist,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            with mock.patch.object(checklists.Checklist, "_preset_project_from_doc"):
                with mock.patch.object(
                    checklists.Project, "ByKeys", return_value=parent_project
                ):
                    with mock.patch.object(
                        checklists.auth,
                        "get_department",
                        return_value="my_test_department",
                    ):
                        checklist.on_create_pre_mask(ctx)
                        checklists.auth.get_department.assert_called_once()
                        self.assertEqual(checklist.division, "my_test_department")
                        checklists.Checklist._preset_project_from_doc.assert_called_once_with(
                            ctx
                        )
                        ctx.set.assert_called_once_with(
                            "project_name", parent_project.project_name
                        )
                        checklists.Project.ByKeys.assert_called_once_with(
                            cdb_project_id=checklist.cdb_project_id
                        )
                        self.assertEqual(checklist.subject_id, "my_test_user")
                        self.assertEqual(checklist.subject_type, "Person")

    @mock.patch.object(checklists.Checklist, "detachFromCheckpoint")
    def test_on_copy_pre_mask(self, detachFromCheckpoint):
        """Test on_copy_pre_mask"""
        ctx = mock.Mock(
            spec=[
                "object",
            ]
        )
        ctx.object.type = "test"
        ctx.object.subject_id = "foo"
        ctx.object.subject_type = "bar"

        checklist = checklists.Checklist()
        checklist.on_copy_pre_mask(ctx)
        self.assertEqual(checklist.rating_id, "clear")
        self.assertEqual(checklist.type, ctx.object.type)
        self.assertEqual(checklist.subject_id, ctx.object.subject_id)
        self.assertEqual(checklist.subject_type, ctx.object.subject_type)
        detachFromCheckpoint.assert_called_once()

    @mock.patch.object(checklists.Checklist, "Update")
    def test_setEvaluator_status_180(self, Update):
        """Test setEvaluator with status 180"""

        checklist = checklists.Checklist()
        checklist.status = 180
        checklist.cdb_mpersno = "foo"

        checklist.setEvaluator(ctx=None)
        Update.assert_called_once_with(evaluator="foo")

    @mock.patch.object(checklists.Checklist, "Update")
    def test_setEvaluator_status_200(self, Update):
        """Test setEvaluator with status 200"""

        checklist = checklists.Checklist()
        checklist.status = 200
        checklist.cdb_mpersno = "foo"

        checklist.setEvaluator(ctx=None)
        Update.assert_called_once_with(evaluator="foo")

    @mock.patch.object(checklists.Checklist, "Update")
    def test_setEvaluator_status_0(self, Update):
        """Test setEvaluator with status 0"""

        checklist = checklists.Checklist()
        checklist.status = 0
        checklist.cdb_mpersno = "foo"

        checklist.setEvaluator(ctx=None)
        Update.assert_called_once_with(evaluator="")

    def test_copy_rating_scheme_relship_with_correct_relship(self):
        ctx = mock.Mock(
            spec=[
                "relationship_name",
            ]
        )
        ctx.relationship_name = "cdbpcs_checklist2cl_items"
        checklist = checklists.Checklist()
        checklist.rating_scheme = "foo"
        checklistitems = mock.MagicMock(autospec=ObjectCollection)

        with mock.patch.object(
            checklists.Checklist,
            "ChecklistItems",
            new_callable=mock.PropertyMock,
            return_value=checklistitems,
        ):
            checklist.copy_rating_scheme_relship(ctx)
            checklistitems.Update.assert_called_once_with(
                rating_scheme=checklist.rating_scheme
            )

    def test_copy_rating_scheme_relship_with_wrong_relship(self):
        ctx = mock.Mock(
            spec=[
                "relationship_name",
            ]
        )
        ctx.relationship_name = "other_relship"
        checklist = checklists.Checklist()
        checklist.rating_scheme = "foo"
        checklistitems = mock.MagicMock(autospec=ObjectCollection)

        with mock.patch.object(
            checklists.Checklist,
            "ChecklistItems",
            new_callable=mock.PropertyMock,
            return_value=checklistitems,
        ):
            checklist.copy_rating_scheme_relship(ctx)
            checklistitems.Update.assert_not_called()

    def test_on_relship_copy_post_with_corrent_relship(self):
        ctx = mock.Mock(
            spec=[
                "relationship_name",
            ]
        )
        ctx.relationship_name = "cdbpcs_checklist2cl_items"
        checklist = checklists.Checklist()
        checklist.rating_scheme = "foo"
        checklistitem = mock.MagicMock(autospec=checklists.ChecklistItem)

        with mock.patch.object(
            checklists.Checklist,
            "ChecklistItems",
            new_callable=mock.PropertyMock,
            return_value=[checklistitem],
        ):
            checklist.on_relship_copy_post(ctx)
            checklistitem.Update.assert_called_once_with(
                template=checklist.template, has_sub_cl=0
            )
            checklistitem.Reset.assert_called_once_with()

    def test_on_relship_copy_post_with_wrong_relship(self):
        ctx = mock.Mock(
            spec=[
                "relationship_name",
            ]
        )
        ctx.relationship_name = "other_relship"
        checklist = checklists.Checklist()
        checklist.rating_scheme = "foo"
        checklistitems = mock.MagicMock(autospec=ObjectCollection)

        with mock.patch.object(
            checklists.Checklist,
            "ChecklistItems",
            new_callable=mock.PropertyMock,
            return_value=checklistitems,
        ):
            checklist.on_relship_copy_post(ctx)
            checklistitems.Reset.assert_not_called()

    def test_on_delete_pre_with_sub_check_list(self):
        checklist = checklists.Checklist()
        ctx = mock.Mock()
        with mock.patch.object(
            checklists.Checklist, "hasSubChecklists", return_value=True
        ):
            with self.assertRaises(checklists.ue.Exception):
                checklist.on_delete_pre(ctx)

    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_on_delete_pre_without_sub_check_list(self, Exception_):
        checklist = checklists.Checklist()
        ctx = mock.Mock()
        with mock.patch.object(
            checklists.Checklist, "hasSubChecklists", return_value=False
        ):
            checklist.on_delete_pre(ctx)
            self.assertEqual(Exception_.call_count, 0)

    @mock.patch.object(checklists.sqlapi, "SQLdelete")
    def on_delete_post(self, SQLdelete):
        ctx = mock.Mock(
            spec=[
                "error",
            ]
        )
        ctx.error = 0
        checklist = checklists.Checklist()
        checklist.cdb_project_id = "foo"
        checklist.checklist_id = "bar"

        checklist.on_delete_post(ctx)
        SQLdelete.assert_has_calls(
            [
                mock.call(
                    "FROM %s WHERE cdb_project_id = '%s' AND checklist_id = '%s'"
                    % (
                        "cdbpcs_cli_prot",
                        checklist.cdb_project_id,
                        checklist.checklist_id,
                    )
                ),
                mock.call(
                    "FROM %s WHERE cdb_project_id = '%s' AND checklist_id = '%s'"
                    % (
                        "cdbpcs_doc2cli",
                        checklist.cdb_project_id,
                        checklist.checklist_id,
                    )
                ),
            ]
        )


@pytest.mark.unit
class ChecklistItem(testcase.RollbackTestCase):
    def test_checkState_with_Checklist_NEW(self):
        """Test for checkState on ChecklistItem with Checklist in NEW"""
        checklistitem = checklists.ChecklistItem()
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        checklist.status = checklists.Checklist.NEW.status

        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ):
            checklistitem.checkState("foo")
            checklist.checkState.assert_called_once_with("foo")

    def test_checkState_with_Checklist_EVALUATION(self):
        """Test for checkState on ChecklistItem with Checklist in EVALUATION"""
        checklistitem = checklists.ChecklistItem()
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        checklist.status = checklists.Checklist.EVALUATION.status

        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ):
            checklistitem.checkState("foo")
            checklist.checkState.assert_called_once_with("foo")

    def test_checkState_with_Checklist_COMPLETED(self):
        """Test for checkState on ChecklistItem with Checklist in COMPLETED"""
        checklistitem = checklists.ChecklistItem()
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        checklist.status = checklists.Checklist.COMPLETED.status

        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ):
            with self.assertRaises(checklists.ue.Exception):
                checklistitem.checkState("foo")

    def test_get_mandatory_remark_from_ctx(self):
        ctx = mock.MagicMock()
        ctx.dialog = mock.MagicMock(mandatory_remark="1")
        return_val = checklists.ChecklistItem.get_mandatory_remark_from_ctx(ctx)
        self.assertEqual(return_val, True)

        ctx.dialog = mock.MagicMock(mandatory_remark="a")  # non int
        return_val = checklists.ChecklistItem.get_mandatory_remark_from_ctx(ctx)
        self.assertEqual(return_val, False)

    @mock.patch.object(checklists.ChecklistItem, "get_mandatory_remark_from_ctx")
    def test_set_evaluate_remark_mandatory_premask_quickeval(
        self, get_mandatory_remark_from_ctx
    ):
        get_mandatory_remark_from_ctx.return_value = True
        ctx = mock.MagicMock()
        ctx.dialog = mock.MagicMock(quickEvaluation=True)
        checklists.ChecklistItem.set_evaluate_remark_mandatory(ctx, True)
        ctx.set_mandatory.assert_called_once_with(checklists.CL_ITEM_EVALUATE_REMARK)

        get_mandatory_remark_from_ctx.return_value = False
        checklists.ChecklistItem.set_evaluate_remark_mandatory(ctx, True)
        ctx.set_optional.assert_called_once_with(checklists.CL_ITEM_EVALUATE_REMARK)

    @mock.patch.object(checklists.RatingValue, "KeywordQuery")
    def test_set_evaluate_remark_mandatory_premask_kwquery(self, kwQuery):
        kwQuery.return_value = [{"mandatory_remark": True}]
        ctx = mock.MagicMock()
        ctx.dialog = mock.MagicMock(rating_id="id", rating_scheme="scheme")

        del ctx.dialog.quickEvaluation

        checklists.ChecklistItem.set_evaluate_remark_mandatory(ctx, True)
        kwQuery.assert_called_once_with(name="scheme", rating_id="id")

        ctx.set_mandatory.assert_called_once_with(checklists.CL_ITEM_EVALUATE_REMARK)

    @mock.patch.object(checklists.ChecklistItem, "get_mandatory_remark_from_ctx")
    def test_set_evaluate_remark_mandatory(self, get_mandatory_remark_from_ctx):
        get_mandatory_remark_from_ctx.return_value = False
        ctx = mock.MagicMock()
        checklists.ChecklistItem.set_evaluate_remark_mandatory(ctx, False)
        ctx.set_optional.assert_called_once_with(checklists.CL_ITEM_EVALUATE_REMARK)

    @mock.patch.object(checklists.ChecklistItem, "get_mandatory_remark_from_ctx")
    def test_evaluate_skip_dialog_if_necessary(self, get_mandatory_remark_from_ctx):
        get_mandatory_remark_from_ctx.return_value = False
        ctx = mock.MagicMock(uses_webui=True)
        checklists.ChecklistItem.evaluate_skip_dialog_if_necessary(ctx)
        ctx.skip_dialog.assert_called_once()

    @mock.patch.object(
        checklists.ChecklistItem,
        "PersistentObjectsFromContext",
        return_value=[
            mock.MagicMock(
                cdb_project_id="A",
                checklist_id=1,
                Checklist=mock.MagicMock(
                    status="new",
                    NEW=mock.MagicMock(status="new"),
                ),
            ),
            mock.MagicMock(cdb_project_id="A", checklist_id=1),
        ],
    )
    def test_check_cdbpcs_clitem_rating_objects_cl_ok(self, items):
        ctx = mock.MagicMock()  # has "objects"
        self.assertEqual(
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx),
            items.return_value[0].Checklist,
        )
        items.return_value[0].Checklist.checkLicense.assert_called_once_with()

    @mock.patch.object(
        checklists.ChecklistItem,
        "PersistentObjectsFromContext",
        return_value=[
            mock.MagicMock(cdb_project_id="A", checklist_id=1),
            mock.MagicMock(cdb_project_id="A", checklist_id=1),
        ],
    )
    def test_check_cdbpcs_clitem_rating_objects_cl_not_ok(self, items):
        ctx = mock.MagicMock()  # has "objects"
        with self.assertRaises(checklists.ue.Exception) as error:
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx)

        self.assertEqual(
            str(error.exception),
            str(
                "Die Checkliste wurde bereits abgeschlossen/verworfen. "
                "Es können daher keine Prüfpunkte mehr angelegt "
                "oder geändert werden."
            ),
        )
        items.return_value[0].Checklist.checkLicense.assert_called_once_with()

    @mock.patch.object(
        checklists.ChecklistItem, "PersistentObjectsFromContext", return_value=[]
    )
    def test_check_cdbpcs_clitem_rating_objects_no_cl(self, _):
        ctx = mock.MagicMock()  # has "objects"
        with self.assertRaises(checklists.ue.Exception) as error:
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx)

        self.assertEqual(
            str(error.exception),
            str(
                "Diese Operation kann nur auf Prüfpunkten "
                "einer einzigen Checkliste ausgeführt werden."
            ),
        )

    @mock.patch.object(
        checklists.ChecklistItem,
        "PersistentObjectsFromContext",
        return_value=[
            mock.MagicMock(cdb_project_id="A", checklist_id=1),
            mock.MagicMock(cdb_project_id="B", checklist_id=1),
        ],
    )
    def test_check_cdbpcs_clitem_rating_objects_multi_cl(self, items):
        ctx = mock.MagicMock()  # has "objects"
        with self.assertRaises(checklists.ue.Exception) as error:
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx)

        self.assertEqual(
            str(error.exception),
            str(
                "Diese Operation kann nur auf Prüfpunkten "
                "einer einzigen Checkliste ausgeführt werden."
            ),
        )
        items.return_value[0].checkLicense.assert_not_called()

    @mock.patch.object(
        checklists.Checklist,
        "ByKeys",
        return_value=mock.MagicMock(
            cdb_project_id="A",
            checklist_id=1,
            status="eva",
            EVALUATION=mock.MagicMock(status="eva"),
        ),
    )
    def test_check_cdbpcs_clitem_rating_object_cl_ok(self, cl):
        ctx = mock.MagicMock(
            object={
                "cdb_project_id": "P",
                "checklist_id": 8,
                "cl_item_id": 15,
            }
        )
        del ctx.objects
        self.assertEqual(
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx),
            cl.return_value,
        )
        cl.assert_called_once_with(**ctx.object)
        cl.return_value.checkLicense.assert_called_once_with()

    @mock.patch.object(
        checklists.Checklist,
        "ByKeys",
        return_value=mock.MagicMock(cdb_project_id="A", checklist_id=1),
    )
    def test_check_cdbpcs_clitem_rating_object_cl_not_ok(self, cl):
        ctx = mock.MagicMock(
            object={
                "cdb_project_id": "P",
                "checklist_id": 8,
                "cl_item_id": 15,
            }
        )
        del ctx.objects
        with self.assertRaises(checklists.ue.Exception) as error:
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx)

        self.assertEqual(
            str(error.exception),
            str(
                "Die Checkliste wurde bereits abgeschlossen/verworfen. "
                "Es können daher keine Prüfpunkte mehr angelegt "
                "oder geändert werden."
            ),
        )
        cl.assert_called_once_with(**ctx.object)
        cl.return_value.checkLicense.assert_called_once_with()

    @mock.patch.object(checklists.Checklist, "ByKeys", return_value=None)
    def test_check_cdbpcs_clitem_rating_object_no_cl(self, cl):
        ctx = mock.MagicMock(
            object={
                "cdb_project_id": "P",
                "checklist_id": 8,
                "cl_item_id": 15,
            }
        )
        del ctx.objects
        with self.assertRaises(checklists.ue.Exception) as error:
            checklists.ChecklistItem.check_cdbpcs_clitem_rating(ctx)

        self.assertEqual(
            str(error.exception),
            str(
                "Diese Operation kann nur auf Prüfpunkten "
                "einer einzigen Checkliste ausgeführt werden."
            ),
        )
        cl.assert_called_once_with(**ctx.object)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.ChecklistItem, "set_evaluate_remark_mandatory")
    @mock.patch.object(checklists.ChecklistItem, "evaluate_skip_dialog_if_necessary")
    def test_on_cdbpcs_clitem_rating_pre_mask(
        self,
        evaluate_skip_dialog_if_necessary,
        set_evaluate_remark_mandatory,
    ):
        """Test for cdbpcs_clitem_rating pre_mask with data from context"""
        ctx = mock.Mock(spec=["set", "objects"])
        cl = mock.MagicMock(
            spec=checklists.Checklist,
            rating_scheme="rating_scheme",
            cdb_project_id="project_id",
            checklist_id="checklist_id",
        )
        with mock.patch.object(
            checklists.ChecklistItem, "check_cdbpcs_clitem_rating", return_value=cl
        ):
            checklists.ChecklistItem.on_cdbpcs_clitem_rating_pre_mask(ctx)
            ctx.set.assert_has_calls(
                [
                    mock.call("rating_scheme", cl.rating_scheme),
                    mock.call("cdb_project_id", cl.cdb_project_id),
                    mock.call("checklist_id", cl.checklist_id),
                    mock.call("evaluator", "my_test_user"),
                ]
            )
            evaluate_skip_dialog_if_necessary.assert_called_once_with(ctx)
            set_evaluate_remark_mandatory.assert_called_once_with(ctx, True)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_on_cdbpcs_clitem_rating_now_without_error(self, Exception_):
        "Test for cdbpcs_clitem_rating now without an error"
        real_dict = {
            "rating_id": "rating_id",
            "cdbpcs_clir_txt": "foo",
        }
        ctx = mock.Mock(
            spec=["refresh_tables", "dialog"],
            dialog=mock.MagicMock(
                get_attribute_names=mock.MagicMock(return_value=real_dict.keys()),
                __getitem__=mock.MagicMock(side_effect=real_dict.__getitem__),
            ),
        )
        cl = mock.MagicMock(spec=checklists.Checklist)
        item = mock.MagicMock(
            spec=checklists.ChecklistItem,
            tryRating=mock.MagicMock(return_value=""),
            Checklist=cl,
        )

        with mock.patch.object(
            checklists.ChecklistItem, "check_cdbpcs_clitem_rating", return_value=cl
        ):
            with mock.patch.object(
                checklists.ChecklistItem,
                "PersistentObjectsFromContext",
                return_value=[item],
            ):
                checklists.ChecklistItem.on_cdbpcs_clitem_rating_now(ctx)
                self.assertEqual(item.evaluator, "my_test_user")
                item.tryRating.assert_called_once_with(
                    real_dict["rating_id"],
                    True,
                    rating_remark=real_dict["cdbpcs_clir_txt"],
                )
                cl.setRating.assert_called_once()
                ctx.refresh_tables.assert_called_once_with(
                    ["cdbpcs_checklst", "cdbpcs_cl_item"]
                )
                self.assertEqual(Exception_.call_count, 0)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_on_cdbpcs_clitem_rating_now_without_error_and_status_unchanged(
        self, Exception_
    ):
        "cdbpcs_clitem_rating now without an error and status unchanged"
        real_dict = {
            "rating_id": "rating_id",
            "cdbpcs_clir_txt": "foo",
        }
        ctx = mock.Mock(
            spec=["refresh_tables", "dialog"],
            dialog=mock.MagicMock(
                get_attribute_names=mock.MagicMock(return_value=real_dict.keys()),
                __getitem__=mock.MagicMock(side_effect=real_dict.__getitem__),
            ),
        )
        cl = mock.MagicMock(spec=checklists.Checklist)
        item = mock.MagicMock(
            spec=checklists.ChecklistItem,
            tryRating=mock.MagicMock(return_value=""),
            Checklist=cl,
        )

        with mock.patch.object(
            checklists.ChecklistItem, "check_cdbpcs_clitem_rating", return_value=cl
        ):
            with mock.patch.object(
                checklists.ChecklistItem,
                "PersistentObjectsFromContext",
                return_value=[item],
            ):
                checklists.ChecklistItem.on_cdbpcs_clitem_rating_now(ctx)
                self.assertEqual(item.evaluator, "my_test_user")
                item.Reload.assert_not_called()
                item.tryRating.assert_called_once_with(
                    real_dict["rating_id"],
                    True,
                    rating_remark=real_dict["cdbpcs_clir_txt"],
                )
            cl.setRating.assert_called_once()
            ctx.refresh_tables.assert_called_once_with(
                ["cdbpcs_checklst", "cdbpcs_cl_item"]
            )
            self.assertEqual(Exception_.call_count, 0)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    def test_on_cdbpcs_clitem_rating_now_without_error_and_no_remark(self, Exception_):
        "Test for cdbpcs_clitem_rating now without an error and no remark"
        real_dict = {"rating_id": "rating_id"}
        ctx = mock.Mock(
            spec=["refresh_tables", "dialog"],
            dialog=mock.MagicMock(
                get_attribute_names=mock.MagicMock(return_value=real_dict.keys()),
                __getitem__=mock.MagicMock(side_effect=real_dict.__getitem__),
            ),
        )
        cl = mock.MagicMock(spec=checklists.Checklist)
        item = mock.MagicMock(
            spec=checklists.ChecklistItem,
            tryRating=mock.MagicMock(return_value=""),
            Checklist=cl,
        )
        with mock.patch.object(
            checklists.ChecklistItem, "check_cdbpcs_clitem_rating", return_value=cl
        ):
            with mock.patch.object(
                checklists.ChecklistItem,
                "PersistentObjectsFromContext",
                return_value=[item],
            ):
                checklists.ChecklistItem.on_cdbpcs_clitem_rating_now(ctx)
                self.assertEqual(item.evaluator, "my_test_user")

                item.Reload.assert_not_called()
                item.tryRating.assert_called_once_with(
                    real_dict["rating_id"],
                    True,
                    rating_remark=None,
                )
                cl.setRating.assert_called_once()
                ctx.refresh_tables.assert_called_once_with(
                    ["cdbpcs_checklst", "cdbpcs_cl_item"]
                )
                self.assertEqual(Exception_.call_count, 0)

    @mock.patch.dict(os.environ, {"CADDOK_AUTH_PERSNO": "my_test_user"})
    def test_on_cdbpcs_clitem_rating_now_with_error(self):
        "Test for cdbpcs_clitem_rating now with error"
        real_dict = {
            "rating_id": "rating_id",
            "cdbpcs_clir_txt": "foo",
        }
        ctx = mock.Mock(
            spec=["refresh_tables", "dialog"],
            dialog=mock.MagicMock(
                get_attribute_names=mock.MagicMock(return_value=real_dict.keys()),
                __getitem__=mock.MagicMock(side_effect=real_dict.__getitem__),
            ),
        )

        cl = mock.MagicMock(spec=checklists.Checklist)
        item = mock.MagicMock(
            spec=checklists.ChecklistItem,
            tryRating=mock.MagicMock(return_value="ERROR"),
        )

        with mock.patch.object(
            checklists.ChecklistItem, "check_cdbpcs_clitem_rating", return_value=cl
        ):
            with mock.patch.object(
                checklists.ChecklistItem,
                "PersistentObjectsFromContext",
                return_value=[item],
            ):
                with self.assertRaises(checklists.ue.Exception):
                    checklists.ChecklistItem.on_cdbpcs_clitem_rating_now(ctx)

                self.assertEqual(item.evaluator, "my_test_user")
                item.tryRating.assert_called_once_with(
                    real_dict["rating_id"],
                    True,
                    rating_remark=real_dict["cdbpcs_clir_txt"],
                )
                cl.setRating.assert_called_once()
                ctx.refresh_tables.assert_called_once_with(
                    ["cdbpcs_checklst", "cdbpcs_cl_item"]
                )

    def test_on_cdbpcs_clitem_rating_now_with_no_items(self):
        "Test for cdbpcs_clitem_rating now with no items"
        ctx = mock.Mock(spec=["refresh_tables"])
        with mock.patch.object(checklists.ChecklistItem, "check_cdbpcs_clitem_rating"):
            with mock.patch.object(
                checklists.ChecklistItem,
                "PersistentObjectsFromContext",
                return_value=[],
            ):
                checklists.ChecklistItem.on_cdbpcs_clitem_rating_now(ctx)
                ctx.refresh_tables.assert_not_called()

    def test_subChecklistsRated_no_lists(self):
        """Test subChecklistsRated with no lists"""
        checklistitem = checklists.ChecklistItem()
        with mock.patch.object(
            checklists.ChecklistItem,
            "SubChecklists",
            new_callable=mock.PropertyMock,
            return_value=[],
        ):
            result = checklistitem.subChecklistsRated()
            self.assertTrue(result)

    def test_subChecklistsRated_with_list_in_NEW(self):
        """Test subChecklistsRated with list in NEW"""
        checklistitem = checklists.ChecklistItem()
        subchecklist = mock.MagicMock(autospec=checklists.Checklist)
        subchecklist.status = checklists.Checklist.NEW.status

        with mock.patch.object(
            checklists.ChecklistItem,
            "SubChecklists",
            new_callable=mock.PropertyMock,
            return_value=[subchecklist],
        ):
            result = checklistitem.subChecklistsRated()
            self.assertFalse(result)

    def test_subChecklistsRated_with_list_in_COMPLETED(self):
        """Test subChecklistsRated with list in COMPLETED"""
        checklistitem = checklists.ChecklistItem()
        subchecklist = mock.MagicMock(autospec=checklists.Checklist)
        subchecklist.status = checklists.Checklist.COMPLETED.status

        with mock.patch.object(
            checklists.ChecklistItem,
            "SubChecklists",
            new_callable=mock.PropertyMock,
            return_value=[subchecklist],
        ):
            result = checklistitem.subChecklistsRated()
            self.assertTrue(result)

    def test_subChecklistsRated_with_list_in_DISCARDED(self):
        """Test subChecklistsRated with list in DISCARDED"""
        checklistitem = checklists.ChecklistItem()
        subchecklist = mock.MagicMock(autospec=checklists.Checklist)
        subchecklist.status = checklists.Checklist.DISCARDED.status

        with mock.patch.object(
            checklists.ChecklistItem,
            "SubChecklists",
            new_callable=mock.PropertyMock,
            return_value=[subchecklist],
        ):
            result = checklistitem.subChecklistsRated()
            self.assertTrue(result)

    @mock.patch.object(checklists.ChecklistItem, "clearRating")
    @mock.patch.object(
        checklists.ChecklistItem, "subChecklistsRated", return_value=True
    )
    def test_setRating_with_clear_id_and_update_cl_rating(
        self, subChecklistsRated, clearRating
    ):
        """Test setRating with clear id and update_cl_rating"""
        checklistitem = checklists.ChecklistItem()
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ):
            result = checklistitem.setRating("clear")
            subChecklistsRated.assert_called_once()
            clearRating.assert_called_once()
            checklist.setRating.assert_called_once()
            self.assertTrue(result)

    @mock.patch.object(checklists.ChecklistItem, "clearRating")
    @mock.patch.object(
        checklists.ChecklistItem, "subChecklistsRated", return_value=True
    )
    def test_setRating_with_clear_id_and_no_update_cl_rating(
        self, subChecklistsRated, clearRating
    ):
        """Test setRating with clear id and no update_cl_rating"""
        checklistitem = checklists.ChecklistItem()
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ):
            result = checklistitem.setRating("clear", update_cl_rating=False)
            subChecklistsRated.assert_called_once()
            clearRating.assert_called_once()
            checklist.setRating.assert_not_called()
            self.assertTrue(result)

    @mock.patch.object(
        checklists.ChecklistItem, "subChecklistsRated", return_value=False
    )
    def test_setRating_without_rated_subchecklists(self, subChecklistsRated):
        """Test setRating without rated subchecklists"""
        checklistitem = checklists.ChecklistItem()
        result = checklistitem.setRating("clear")
        subChecklistsRated.assert_called_once()
        self.assertFalse(result)

    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    @mock.patch.object(checklists.ChecklistItem, "GetDescription")
    @mock.patch.object(checklists.ChecklistItem, "ChangeState")
    @mock.patch.object(checklists.ChecklistItem, "SetText")
    @mock.patch.object(checklists.ChecklistItem, "clearRating")
    @mock.patch.object(
        checklists.ChecklistItem, "subChecklistsRated", return_value=True
    )
    def test_setRating_without_clear_id_and_update_rating_same_statue(
        self,
        subChecklistsRated,
        clearRating,
        SetText,
        ChangeState,
        GetDescription,
        Exception_,
    ):
        """Test setRating without clear id and update_rating in the same status"""
        checklistitem = checklists.ChecklistItem()
        checklistitem.status = checklists.ChecklistItem.NEW.status
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        checklist.TypeDefinition.rating_state = checklists.ChecklistItem.NEW.status
        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ), mock.patch.object(checklists.ChecklistItem, "Update") as Update:
            result = checklistitem.setRating("rating_id")
            subChecklistsRated.assert_called_once()
            clearRating.assert_not_called()
            Update.assert_called_once_with(rating_id="rating_id")
            SetText.assert_called_once_with("cdbpcs_clir_txt", "")
            ChangeState.assert_not_called()
            checklist.setRating.assert_called_once()
            GetDescription.assert_not_called()
            self.assertTrue(result)
            self.assertEqual(Exception_.call_count, 0)

    @mock.patch.object(checklists.ue, "Exception", autospec=True)
    @mock.patch.object(checklists.ChecklistItem, "GetDescription")
    @mock.patch.object(checklists.ChecklistItem, "ChangeState")
    @mock.patch.object(checklists.ChecklistItem, "SetText")
    @mock.patch.object(checklists.ChecklistItem, "clearRating")
    @mock.patch.object(
        checklists.ChecklistItem, "subChecklistsRated", return_value=True
    )
    def test_setRating_without_clear_id_and_update_rating_diffent_status(
        self,
        subChecklistsRated,
        clearRating,
        SetText,
        ChangeState,
        GetDescription,
        Exception_,
    ):
        """Test setRating without clear id and update_rating in a different status"""
        checklistitem = checklists.ChecklistItem()
        checklistitem.status = checklists.ChecklistItem.NEW.status
        checklist = mock.MagicMock(autospec=checklists.Checklist)
        checklist.TypeDefinition.rating_state = (
            checklists.ChecklistItem.COMPLETED.status
        )
        with mock.patch.object(
            checklists.ChecklistItem,
            "Checklist",
            new_callable=mock.PropertyMock,
            return_value=checklist,
        ), mock.patch.object(checklists.ChecklistItem, "Update") as Update:

            result = checklistitem.setRating("rating_id")
            subChecklistsRated.assert_called_once()
            clearRating.assert_not_called()
            Update.assert_called_once_with(rating_id="rating_id")
            SetText.assert_called_once_with("cdbpcs_clir_txt", "")
            ChangeState.assert_called_once_with(
                checklists.ChecklistItem.COMPLETED.status
            )
            checklist.setRating.assert_called_once()
            GetDescription.assert_not_called()
            self.assertTrue(result)
            self.assertEqual(Exception_.call_count, 0)

    def test_on_create_pre_mask(self):
        real_dict = {
            "subject_id": "subid",
            "subject_type": "subtyp",
            "division": "div",
            "target_date": datetime.date(2020, 5, 17),
            "rating_scheme": "sch",
            "type": "typ",
            "category": "cat",
            "template": "templ",
        }

        # method for get item of dict
        def getitem(name):
            return real_dict[name]

        cl = mock.MagicMock(status=0)
        cl.__getitem__.side_effect = getitem
        cl.TypeDefinition.cli_objektart = "obj_art"

        clItem = checklists.ChecklistItem()
        ctx = mock.MagicMock()
        with mock.patch.object(checklists.ChecklistItem, "Checklist", cl):
            clItem.on_create_pre_mask(ctx)

        del real_dict["template"]
        computed_dict = {}
        for key in real_dict:
            computed_dict[key] = clItem[key]
        self.assertEqual(computed_dict, real_dict)

        ctx.set.assert_called_once_with("template", "templ")
        self.assertEqual(clItem.cdb_objektart, "obj_art")

    @mock.patch.object(checklists.ChecklistItem, "Reset")
    def test_on_copy_pre_mask(self, reset):
        ctx = mock.MagicMock()
        clItem = checklists.ChecklistItem()
        clItem.on_copy_pre_mask(ctx)

        # cl_item_id is int field. When given an empty
        # string the value is set to None by object framework
        self.assertEqual(None, clItem.cl_item_id)
        reset.assert_called_once()

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_on_delete_pre(self, CDBMsg):
        ctx = mock.MagicMock()
        subChecklists = ["subchecklist"]
        clItem = checklists.ChecklistItem()

        with mock.patch.object(
            checklists.ChecklistItem, "SubChecklists", subChecklists
        ), self.assertRaises(checklists.ue.Exception):
            clItem.on_delete_pre(ctx)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_err_del_cli1")

    def test_on_modify_pre_exception(self):
        clItem = mock.MagicMock(
            spec=checklists.ChecklistItem,
            rating_id="foo",
            checklist_id=0,
        )
        ctx = mock.MagicMock()
        ctx.object.rating_id = "bar"
        ctx.object.__getitem__.return_value = "clName"
        clItem.subChecklistsRated.return_value = False

        with self.assertRaises(checklists.ue.Exception) as e:
            checklists.ChecklistItem.on_modify_pre(clItem, ctx)

        clItem.subChecklistsRated.assert_called_once_with()
        self.assertEqual(
            str(e.exception),
            (
                "Der Abschluss des Prüfpunktes 'clName (0)' ist nicht möglich,"
                " da nicht abgeschlossene Checklisten zu diesem Prüfpunkt exis"
                "tieren. Bitte schließen Sie diese zunächst ab."
            ),
        )

    def test_on_modify_pre_clear_rating(self):
        kv = {"rating_id": 1, "weight": 10, "ko_criterion": 0}

        ctx = mock.MagicMock()
        ctx.object = mock.MagicMock()
        ctx.object.__getitem__.side_effect = lambda x: str(kv[x]) + "_new"

        clItem = checklists.ChecklistItem()
        for k, v in kv.items():
            clItem[k] = v

        clItem.rating_id = "clear"
        clItem.on_modify_pre(ctx)

        ctx.keep.assert_has_calls(
            [mock.call(attr + "_changed", "1") for attr in kv], any_order=True
        )
        ctx.set.assert_called_once_with("rating_id", "clear")

    def test_on_modify_pre_rating_status_change(self):
        kv = {"rating_id": 1, "weight": 10, "ko_criterion": 0}

        ctx = mock.MagicMock()
        ctx.object = mock.MagicMock()
        ctx.object.__getitem__.side_effect = lambda x: str(kv[x]) + "_new"

        clItem = checklists.ChecklistItem()
        for k, v in kv.items():
            clItem[k] = v

        clItem.rating_id = "r1"

        cl = mock.MagicMock(NEW="new", EVALUATION="eval")

        with mock.patch.object(checklists.ChecklistItem, "Checklist", cl):
            clItem.on_modify_pre(ctx)

        ctx.keep.assert_has_calls(
            [mock.call(attr + "_changed", "1") for attr in kv], any_order=True
        )
        # change_status.assert_called_once_with("new", "eval")
        ctx.refresh_tables.assert_called_once_with(["cdbpcs_checklst"])

    @mock.patch.object(checklists.ChecklistItem, "checkLicense")
    @mock.patch.object(checklists.ChecklistItem, "clearRating")
    def test_on_modify_post_clear_rating(self, clearRating, checkLicense):
        ctx = mock.MagicMock()
        ctx.ue_args.get_attribute_names = mock.MagicMock(
            return_value=["rating_id_changed"]
        )
        clItem = checklists.ChecklistItem()
        clItem.rating_id = "clear"

        ctx.refresh_tables = mock.MagicMock()

        clItem.on_modify_post(ctx)

        checkLicense.assert_called_once()
        clearRating.assert_called_once()
        ctx.refresh_tables.assert_called_once_with(["cdbpcs_checklst"])

    @mock.patch.object(checklists.ChecklistItem, "checkLicense")
    @mock.patch.object(checklists.ChecklistItem, "getPersistentObject")
    @mock.patch.object(checklists, "operation")
    def test_on_modify_post_operation(self, operation, getObj, checkLicense):
        getObj.return_value = "persistent"

        ctx = mock.MagicMock()
        ctx.ue_args.get_attribute_names = mock.MagicMock(
            return_value=["rating_id_changed"]
        )

        clItem = checklists.ChecklistItem()
        clItem.rating_id = "rat"

        clItem.on_modify_post(ctx)
        checkLicense.assert_called_once()
        getObj.assert_called_once()
        operation.assert_called_once_with(
            "cdbpcs_clitem_rating", "persistent", rating_id="rat"
        )

    @mock.patch.object(checklists.ChecklistItem, "checkLicense")
    def test_on_modify_post_ue_args(self, checkLicense):
        ctx = mock.MagicMock()
        ctx.ue_args.get_attribute_names = mock.MagicMock(
            return_value=["weight_changed"]
        )
        clItem = checklists.ChecklistItem()
        cl = mock.MagicMock()
        with mock.patch.object(checklists.ChecklistItem, "Checklist", cl):
            clItem.on_modify_post(ctx)

        checkLicense.assert_called_once()
        cl.setRating.assert_called_once()
        ctx.refresh_tables.assert_called_once_with(["cdbpcs_checklst"])

    @mock.patch.object(checklists.ChecklistItem, "openSubject")
    def test_on_cdb_show_responsible_now(self, openSubject):
        clItem = checklists.ChecklistItem()
        clItem.on_cdb_show_responsible_now(mock.MagicMock)
        openSubject.assert_called_once()

    @mock.patch.object(checklists, "gui")
    def test_getNotificationTitle(self, gui):
        gui.Message.GetMessage = mock.MagicMock(return_value="branding")
        clItem = checklists.ChecklistItem()

        self.assertEqual(
            clItem.getNotificationTitle(),
            "branding - Prüfpunkt bereit / Checklist item ready",
        )

    def test_getNotificationReceiver(self):
        clItem = checklists.ChecklistItem()
        subject = mock.MagicMock()
        person = mock.MagicMock(e_mail="email@abc.com", name="pers")
        subject.getPersons = mock.MagicMock(return_value=[person])
        result = None
        with mock.patch.object(checklists.ChecklistItem, "Subject", subject):
            result = clItem.getNotificationReceiver()

        self.assertEqual(result, [{"to": [(person.e_mail, person.name)]}])

    def test_checkLicense(self):
        clItem = checklists.ChecklistItem()
        cl = mock.MagicMock()

        with mock.patch.object(checklists.ChecklistItem, "Checklist", cl):
            clItem.checkLicense()

        cl.checkLicense.assert_called_once()

    def test_setEvaluator(self):
        clItem = checklists.ChecklistItem(status=180, cdb_mpersno="1234")
        update = mock.MagicMock()
        with mock.patch.object(checklists.ChecklistItem, "Update", update):
            clItem.setEvaluator(None)

        update.assert_called_once_with(evaluator="1234")

    def test_check_project_role_needed(self):
        clItem = checklists.ChecklistItem()
        prj = mock.MagicMock()
        ctx = mock.MagicMock
        with mock.patch.object(checklists.ChecklistItem, "Project", prj):
            clItem.check_project_role_needed(ctx)

        prj.check_project_role_needed.assert_called_once_with(ctx)

    @mock.patch.object(checklists.ChecklistItem, "getPersistentObject")
    @mock.patch.object(checklists, "auth")
    def test_update_evaluator_checklist_item(self, auth, getPersistentObject):
        d = {"rating_id": 123}
        auth.persno = "persno"
        dialog = mock.MagicMock()
        dialog.__getitem__.side_effect = d.__getitem__
        ctx = mock.MagicMock(dialog=dialog, error=None)
        update = mock.MagicMock()
        getPersistentObject.return_value = mock.MagicMock(Update=update)
        clItem = checklists.ChecklistItem()

        clItem.update_evaluator_checklist_item(ctx)

        update.assert_called_once_with(evaluator="persno")
        ctx.refresh_tables.assert_called_once_with(
            ["cdbpcs_checklst", "cdbpcs_cl_item"]
        )


@pytest.mark.unit
@unittest.skip("RatingSchema tests missing.")
class RatingSchema(testcase.RollbackTestCase):
    pass


@pytest.mark.unit
@unittest.skip("RedGreenYellowRating tests missing.")
class RedGreenYellowRating(testcase.RollbackTestCase):
    pass


@pytest.mark.unit
@unittest.skip("GermanSchoolmarksRating tests missing.")
class GermanSchoolmarksRating(testcase.RollbackTestCase):
    pass


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
