# pylint: disable=W0212

from cdb import auth, sqlapi, testcase
from cs.taskmanager.user_views import SELECTED
from cs.taskmanager.web.models import ModelWithUserSettings


class UserSettings(testcase.RollbackTestCase):
    """
    Tests the retrieving of selectedView user settings.
    """

    @classmethod
    def setUpClass(cls):
        super(UserSettings, cls).setUpClass()
        # reset selectedView user settings (WARNING: will not be rolled back)
        sqlapi.SQLdelete(
            "FROM cdb_usr_setting "
            "WHERE setting_id='cs.taskmanager' AND setting_id2 LIKE 'selectedView--%'"
            "AND personalnummer='{}'".format(auth.persno)
        )

        # Add settings
        cls.model = ModelWithUserSettings()
        cls.model._set_setting("selectedView--test", "test_UUID_1")
        cls.model._set_setting("selectedView-test", "test_UUID_2")
        cls.model._set_setting("selectedView---test", "test_UUID_3")
        cls.model._set_setting("selectedView", "test_UUID_4")

    def test_get_settings(self):
        settings = self.model._get_setting(SELECTED)
        self.assertEqual(len(settings), 2)
