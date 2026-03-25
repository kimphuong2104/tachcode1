#!/usr/bin/env python


import unittest

from cdb import testcase
from mock import Mock, patch

from cs.pcs.projects import Project, Role
from cs.pcs.projects.common.lists.list_help_functions import (
    generateClassIconProperties,
    generateDateProperties,
    generateLabelProperties,
    generateStatusIconProperties,
    generateThumbnailProperties,
)
from cs.pcs.projects.tasks import Task


class TestListHelpFunctions(testcase.RollbackTestCase):
    def _generateThumbnailProperties(self):
        # Since __getattr__ is not mockable (reserved magic function)
        # create a real ObjectHandle here without the sortKey attribute
        dummyProject = Project.Create(
            cdb_project_id="dummyProjectId", ce_baseline_id=""
        )
        dummyRole = Role.Create(
            role_id="dummyRoleId",
            cdb_project_id=dummyProject.cdb_project_id,
            team_assigned=0,
            team_needed=0,
        )
        dummyTask = Task.Create(
            cdb_project_id="dummyProjectId",
            ce_baseline_id="",
            task_id="dummyTaskId",
            subject_type="PCS Role",
            subject_id=dummyRole.role_id,
        )
        return dummyTask.ToObjectHandle()

    def test_generateThumbnailProperties_ok(self):
        "test with thumbnail"
        inputObj = self._generateThumbnailProperties()
        # fake having a thumbnail
        with patch(
            "cs.pcs.projects.common.lists.list_help_functions.get_restlink",
            new=Mock(return_value="URL"),
        ):
            funcs = generateThumbnailProperties("subject_id")
            resultName = funcs["name"](inputObj)
            resultUrl = funcs["thumbnail"](inputObj)
        self.assertEqual(resultName, "dummyRoleId")
        self.assertEqual(resultUrl, "URL")

    def test_generateThumbnailProperties_none(self):
        "test without thumbnail"
        inputObj = self._generateThumbnailProperties()
        funcs = generateThumbnailProperties("subject_id")
        resultName = funcs["name"](inputObj)
        resultUrl = funcs["thumbnail"](inputObj)
        self.assertEqual(resultName, "dummyRoleId")
        self.assertEqual(resultUrl, None)

    def test_generateClassIconProperties(self):
        # Since __getattr__ is not mockable (reserved magic function)
        # create a real ObjectHandle here without the sortKey attribute
        dummyProject = Project.Create(
            cdb_project_id="dummyProjectId", ce_baseline_id=""
        )
        inputObj = dummyProject.ToObjectHandle()
        funcs = generateClassIconProperties("IGNORED_PARAMETER")
        title = funcs["title"](inputObj)
        name = funcs["name"](inputObj)
        self.assertEqual(title, "cdbpcs_project")
        self.assertEqual(name, "cdbpcs_project")

    def test_generateLabelProperties(self):
        # Since __getattr__ is not mockable (reserved magic function)
        # create a real ObjectHandle here without the sortKey attribute
        dummyProject = Project.Create(
            cdb_project_id="dummyProjectId", ce_baseline_id=""
        )
        inputObj = dummyProject.ToObjectHandle()
        funcs = generateLabelProperties("cdb_project_id")
        content = funcs["content"](inputObj)
        title = funcs["title"](inputObj)
        self.assertEqual(title, "Projektnummer")
        self.assertEqual(content, "dummyProjectId")

        funcs = generateLabelProperties("this_attribute_does_not_exist")
        with self.assertRaises(AttributeError):
            content = funcs["content"](inputObj)
        with self.assertRaises(AttributeError):
            title = funcs["title"](inputObj)

    def test_generateStatusIconProperties(self):
        # Since __getattr__ is not mockable (reserved magic function)
        # create a real ObjectHandle here without the sortKey attribute
        dummyProject = Project.Create(
            cdb_project_id="dummyProjectId", ce_baseline_id=""
        )
        inputObj = dummyProject.ToObjectHandle()

        # Mock record set in order to force an IndexError
        with patch(
            "cs.pcs.projects.common.lists.list_help_functions.sqlapi.RecordSet2",
            return_value=[],
        ):
            funcs = generateStatusIconProperties("IGNORED_PARAMETER")
            status = funcs["status"](inputObj)
            color = funcs["color"](inputObj)
            label = funcs["label"](inputObj)
        self.assertEqual(status, "")
        self.assertEqual(label, "")
        self.assertEqual(color, "rgb(247, 247, 247)")  # white

    def test_generateDateProperties(self):
        # Since __getattr__ is not mockable (reserved magic function)
        # create a real ObjectHandle here without the sortKey attribute
        dummyProject = Project.Create(
            cdb_project_id="dummyProjectId", ce_baseline_id=""
        )
        inputObj = dummyProject.ToObjectHandle()
        funcs = generateDateProperties("start_time_fcast")
        date = funcs["date"](inputObj)
        title = funcs["title"](inputObj)
        self.assertEqual(date, "")
        self.assertEqual(title, "Beginn (Soll)")


if __name__ == "__main__":
    unittest.main()
