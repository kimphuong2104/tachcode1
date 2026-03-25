from webtest import TestApp as Client

from cdb import auth
from cdb import testcase

from cs.platform.web.root import Root


class TestOperationsCatalog(testcase.RollbackTestCase):
    def setUp(self):
        """
        Set up the test case
        """
        try:
            from cs.webtest import CANCEL_ROLE_ASSIGNMENT_MESSAGE
        except ImportError:
            raise unittest.SkipTest("this test needs cs.webtest")

        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestOperationsCatalog, self).setUp()

        app = Root()
        self.c = Client(app)
        self.msg = CANCEL_ROLE_ASSIGNMENT_MESSAGE

    def test_catalog_result(self):
        response = self.c.get(f'/internal/uisupport/operation/catalog/angestellter/{auth.persno}/RoleAssignmentGeneralRoles')
        self.assertTrue('catalog' in response.json)

    def test_cancel_result(self):
        response = self.c.get(f'/internal/uisupport/operation/catalog/angestellter/{auth.persno}/RoleAssignmentCancelHook')
        self.assertEquals(response.json['cancelled'], self.msg)
