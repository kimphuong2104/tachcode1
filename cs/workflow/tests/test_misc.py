#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
from datetime import date

from cdb import rte
from cdb import sqlapi
from cdb import testcase
from cdb import util
from cdb.objects.org import User
from cdb.objects.cdb_file import CDB_File

from cs.workflow import misc
from cs.workflow.processes import Process


def setup_module():
    testcase.run_level_setup()


class MiscellaneousTestCase(testcase.RollbackTestCase):
    def test_get_pydate_format(self):
        for input_format, expected in [
                ("YYYY", "%Y"),
                ("MM", "%m"),
                ("DD", "%d"),
                ("hh", "%H"),
                ("mm", "%M"),
                ("ss", "%S"),
                ("hh mm:ss_DD.MM/YYYY", "%H %M:%S_%d.%m/%Y"),
                ("a-ok", "a-ok"),
                ("", ""),
                ("DD.MM.YYYY", "%d.%m.%Y"),
                ("DD.MM.YYYY hh:mm:ss", "%d.%m.%Y %H:%M:%S"),
        ]:
            self.assertEqual(misc._get_pydate_format(input_format), expected)

        for input_format in [1, None]:
            with self.assertRaises(TypeError):
                misc._get_pydate_format(input_format)

    def test_calc_deadline_simple(self):
        sqlapi.SQLdelete(
            "FROM cdb_setting "
            "WHERE setting_id='cs.workflow' "
            "AND setting_id2='calc_deadline_workdays'"
        )
        util.PersonalSettings().invalidate()
        wf = Process.Create(
            cdb_process_id="TEST",
            start_date=date(2017, 1, 1)
        )
        misc.calc_deadline(wf)
        self.assertEqual(wf.deadline, None)

        for duration, result in [
                (0, date(2017, 1, 1)),
                (1, date(2017, 1, 2)),
                (-1, date(2016, 12, 31)),
                (31, date(2017, 2, 1)),
        ]:
            wf.Update(max_duration=duration)
            misc.calc_deadline(wf)
            self.assertEqual(wf.deadline, result)

    def test_calc_deadline_workdays(self):
        sqlapi.SQLupdate(
            "cdb_setting "
            "SET default_val='1' "
            "WHERE setting_id='cs.workflow' "
            "AND setting_id2='calc_deadline_workdays'"
        )
        util.PersonalSettings().invalidate()
        wf = Process.Create(
            cdb_process_id="TEST",
            start_date=date(2017, 1, 1)
        )
        misc.calc_deadline(wf)
        self.assertEqual(wf.deadline, None)

        for duration, result in [
                (0, date(2017, 1, 1)),
                (1, date(2017, 1, 2)),
                (-1, date(2016, 12, 30)),
                (31, date(2017, 2, 13)),
        ]:
            wf.Update(max_duration=duration)
            misc.calc_deadline(wf)
            self.assertEqual(wf.deadline, result)

    def test_get_state_text(self):
        # cache is language-agnostic; first olc/status fills cache
        for olc, status, lang, expected in [
                ("cdbwf_aggregate", 0, "de", "Neu"),
                ("cdbwf_aggregate", 0, "en", "Neu"),
                ("cdbwf_process_template", 20, "en", "Released"),
                ("cdbwf_process_template", 20, "de", "Released"),
                (None, None, "zh", ""),
        ]:
            self.assertEqual(misc.get_state_text(olc, status, lang), expected)

        with self.assertRaises(KeyError):
            misc.get_state_text("cdbwf_process_template", 0, "d")

    def test_is_converted_file(self):
        original = CDB_File.Create(cdbf_object_id="BO")

        fobj = CDB_File.Create(cdbf_object_id="BO")  # cdbf_derived_from None
        self.assertEqual(misc.is_converted_file(fobj), False)

        fobj = CDB_File.Create(cdbf_object_id="BO2",
                               cdbf_derived_from=original.cdb_object_id)
        self.assertEqual(misc.is_converted_file(fobj), False)

        fobj = CDB_File.Create(cdbf_object_id="BO",
                               cdbf_derived_from=original.cdb_object_id)
        self.assertEqual(misc.is_converted_file(fobj), True)

    def test_is_auxiliary_file(self):
        fobj = CDB_File.Create(cdbf_object_id="BO")  # cdb_belongsto None
        self.assertEqual(misc.is_auxiliary_file(fobj), False)

        fobj = CDB_File.Create(cdbf_object_id="BO", cdb_belongsto="a")
        self.assertEqual(misc.is_auxiliary_file(fobj), True)

    def test_is_installed(self):
        self.assertEqual(misc.is_installed("cs.workflow"), True)
        self.assertEqual(misc.is_installed("not.existing"), False)

    def test_get_object_class_by_name(self):
        self.assertEqual(misc.get_object_class_by_name(0), None)
        self.assertEqual(misc.get_object_class_by_name(None), None)
        self.assertEqual(misc.get_object_class_by_name("not_existing"), None)
        self.assertNotEqual(misc.get_object_class_by_name("cdbwf_task"), None)

    def test_notification_enabled(self):
        for value, expected in [
                (None, True),
                ("", False),
                ("True", False),
        ]:
            with mock.patch.dict(
                    rte.environ,
                    {"CADDOK_STOP_EMAIL_NOTIFICATION": value}
            ):
                self.assertEqual(misc.notification_enabled(), expected)

    @mock.patch.dict(rte.environ, {"CADDOK_PREFER_LEGACY_URLS": None})
    def test_prefer_web_urls_None(self):
        misc.prefer_web_urls.cache_clear()
        self.assertEqual(misc.prefer_web_urls(), True)

    @mock.patch.dict(rte.environ, {"CADDOK_PREFER_LEGACY_URLS": ""})
    def test_prefer_web_urls_empty_str(self):
        misc.prefer_web_urls.cache_clear()
        self.assertEqual(misc.prefer_web_urls(), True)

    @mock.patch.dict(rte.environ, {"CADDOK_PREFER_LEGACY_URLS": "true"})
    def test_prefer_web_urls_true_str(self):
        misc.prefer_web_urls.cache_clear()
        self.assertEqual(misc.prefer_web_urls(), True)

    @mock.patch.dict(rte.environ, {"CADDOK_PREFER_LEGACY_URLS": "True"})
    def test_prefer_web_urls_unknown_str(self):
        misc.prefer_web_urls.cache_clear()
        self.assertEqual(misc.prefer_web_urls(), False)

    @mock.patch.dict(rte.environ, {})
    def test_sync_global_briefcases_missing(self):
        self.assertEqual(
            misc.sync_global_briefcases(),
            False,
        )

    @mock.patch.dict(rte.environ, {"CADDOK_WORKFLOW_SYNC_GLOBALS": "true"})
    def test_sync_global_briefcases_true(self):
        self.assertEqual(
            misc.sync_global_briefcases(),
            False,
        )

    @mock.patch.dict(rte.environ, {"CADDOK_WORKFLOW_SYNC_GLOBALS": "TRUE"})
    def test_sync_global_briefcases_TRUE(self):
        self.assertEqual(
            misc.sync_global_briefcases(),
            False,
        )

    @mock.patch.dict(rte.environ, {"CADDOK_WORKFLOW_SYNC_GLOBALS": "True"})
    def test_sync_global_briefcases_True(self):
        self.assertEqual(
            misc.sync_global_briefcases(),
            True,
        )

    def test_urljoin(self):
        self.assertEqual(
            misc.urljoin("A", "B", "C"),
            "A/B/C",
        )

    def test_urljoin_relative(self):
        self.assertEqual(
            misc.urljoin("/A", "B", "C"),
            "/A/B/C",
        )

    @mock.patch.object(misc.logging, "error")
    @mock.patch.object(misc, "urljoin")
    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": u"BASE"})
    def test_make_absolute_url(self, urljoin, error):
        self.assertEqual(
            misc.make_absolute_url("foo", "bar"),
            urljoin.return_value,
        )
        urljoin.assert_called_once_with("BASE", "foo", "bar")
        error.assert_not_called()

    @mock.patch.object(misc.logging, "error")
    @mock.patch.object(misc, "urljoin")
    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": u""})
    def test_make_absolute_url_no_root(self, urljoin, error):
        self.assertEqual(
            misc.make_absolute_url("foo", "bar"),
            urljoin.return_value,
        )
        urljoin.assert_called_once_with(u"", "foo", "bar")
        error.assert_called_once_with("Root URL not set: '%s'", u"")

    def test_get_email_language_ok(self):
        "preferred language is OK for e-mail templates"
        user = mock.MagicMock(spec=User)
        user.GetPreferredLanguage.return_value = "de"
        self.assertEqual(misc.get_email_language(user), "de")
        user.GetPreferredLanguage.assert_called_once()

    def test_get_email_language_nok(self):
        "preferred language is not OK for e-mail templates -> default"
        user = mock.MagicMock(spec=User)
        user.GetPreferredLanguage.return_value = None
        self.assertEqual(misc.get_email_language(user), "en")
        user.GetPreferredLanguage.assert_called_once()

    def test_format_in_condition(self):
        colName = 'cdb_object_id'
        values = ['val0', 'val1', 'val2', 'val3', 'val4', 'val5', 'val6', 'val7', 'val8', 'val9']
        for val in values:
            stmt = "INSERT INTO cdbwf_test (name, cdb_object_id) " \
                "VALUES ('%s', '%s')" % ("name_{}".format(val), val,)
            sqlapi.SQL(stmt)
        in_condition = misc.format_in_condition(colName, values, 3)
        uvRecords = sqlapi.RecordSet2(
            "cdbwf_test", in_condition,
            )
        self.assertEqual(len(uvRecords), len(values))
