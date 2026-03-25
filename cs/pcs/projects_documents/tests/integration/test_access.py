import pytest
from cdb import auth, testcase
from cdb.validationkit import operation
from cdb.validationkit.SwitchRoles import run_with_project_roles, run_with_roles

from cs.pcs.projects.tests import common
from cs.pcs.projects_documents.folders import Docfolder_dynamic


@pytest.mark.integration
class ProjectFolderAccessTestCase(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.project = common.generate_project()
        self.folder = operation(
            "CDB_Create",
            Docfolder_dynamic,
            user_input={"name": "Dynamic Folder"},
            preset={
                "cdb_project_id": self.project.cdb_project_id,
                "ce_baseline_id": self.project.ce_baseline_id,
            },
        )

    @run_with_roles([])
    def test_access_as_nobody(self):
        self.assertFalse(self.folder.CheckAccess("read", auth.persno))

    def test_access_as_prolektleiter(self):
        @run_with_roles(["public"])
        @run_with_project_roles(self.project, ["Projektleiter"])
        def check_folder_access():
            self.assertTrue(self.folder.CheckAccess("read", auth.persno))
            self.assertTrue(self.folder.CheckAccess("create", auth.persno))
            self.assertTrue(self.folder.CheckAccess("save", auth.persno))
            self.assertTrue(self.folder.CheckAccess("accept", auth.persno))
            self.assertTrue(self.folder.CheckAccess("delete", auth.persno))

        check_folder_access()

    def test_access_as_projektmitglied(self):
        @run_with_roles(["public"])
        @run_with_project_roles(self.project, ["Projektmitglied"])
        def check_folder_access():
            self.assertTrue(self.folder.CheckAccess("read", auth.persno))
            self.assertTrue(self.folder.CheckAccess("create", auth.persno))
            self.assertTrue(self.folder.CheckAccess("save", auth.persno))
            self.assertTrue(self.folder.CheckAccess("accept", auth.persno))
            self.assertTrue(self.folder.CheckAccess("delete", auth.persno))

        check_folder_access()
