#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,no-value-for-parameter

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock

from cdb import ddl, testcase
from cdb.platform.gui import Label
from cs.taskmanager import user_views
from cs.taskmanager.updates.v15_6_0 import InitUserViewNamesAndPosition, protocol

LEGACY_FIELDS = ["name", "label"]
LANG_FIELDS = ["name_de", "name_en"]


def setUpModule():
    testcase.run_level_setup()


class TestInitUserViewNamesAndPosition(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        table = ddl.Table("cs_tasks_user_view")
        table.addAttributes(*[ddl.Char(field, 25) for field in LEGACY_FIELDS])

    @classmethod
    def tearDownClass(cls):
        table = ddl.Table("cs_tasks_user_view")
        table.dropAttributes(*[ddl.Char(field, 25) for field in LEGACY_FIELDS])

    def setUp(self):
        super(TestInitUserViewNamesAndPosition, self).setUp()
        user_views.UserView.Query().Delete()

    def test__get_lang_fields(self):
        self.assertEqual(
            InitUserViewNamesAndPosition()._get_lang_fields(),
            {
                "en": "name_en",
                "de": "name_de",
            },
        )

    @mock.patch.object(
        InitUserViewNamesAndPosition, "_has_label_field", return_value=[]
    )
    @mock.patch.object(protocol, "logWarning")
    def test_not_relevant(self, logWarning, _):
        InitUserViewNamesAndPosition().run()
        logWarning.assert_called_once_with("Update not relevant.")

    def assertPositions(self, expected):
        actual = {v.cdb_object_id: v.view_position for v in user_views.UserView.Query()}
        self.assertEqual(actual, expected)

    def _preconfigured(self, categ):
        labels = [
            Label.Create(
                ausgabe_label="cs.tasks.test.preconf_0",
                d="Ungenutzt",
                uk="Unused",
            ),
            Label.Create(
                ausgabe_label="cs.tasks.test.preconf_1",
                d="Eins",
                uk="One",
            ),
            Label.Create(
                ausgabe_label="cs.tasks.test.preconf_2",
                d="Zwei",
                uk="Two",
            ),
        ]
        views = [
            user_views.UserView.Create(
                cdb_object_id="preconf_{}".format(index),
                category=categ,
                label=labels[index].ausgabe_label,
                name_de="Foo",  # overwritten if name_en not empty
                name_en=name_en,  # overwritten if not empty
            )
            for index, name_en in enumerate(["Already filled", "", None])
        ]
        InitUserViewNamesAndPosition().run()
        for view in views:
            view.Reload()

        self.assertEqual(
            [[view[field] for field in LANG_FIELDS] for view in views],
            [
                ["Foo", "Already filled"],
                ["Eins", "One"],
                ["Zwei", "Two"],
            ],
        )
        self.assertPositions(
            {
                # sorted by name_en, name_de
                "preconf_0": 10,
                "preconf_1": 20,
                "preconf_2": 30,
            }
        )

    def test_update_categ_default(self):
        self._preconfigured("default")

    def test_update_categ_preconfigured(self):
        self._preconfigured(user_views.CATEG_PRECONFIGURED)

    def _personal(self, categ):
        de_filled = user_views.UserView.Create(
            cdb_object_id="de_filled",
            category=categ,
            name="NAME",
            subject_id="foo",
            subject_type="Person",
            name_de="Eins",
            name_en="",
        )
        en_filled = user_views.UserView.Create(
            cdb_object_id="en_filled",
            category=categ,
            name="NAME",
            subject_id="bar",
            subject_type="Person",
            name_en="One",
        )
        InitUserViewNamesAndPosition().run()

        de_filled.Reload()
        self.assertEqual(
            {field: de_filled[field] for field in LANG_FIELDS},
            {"name_de": "Eins", "name_en": "NAME"},
        )
        en_filled.Reload()
        self.assertEqual(
            {field: en_filled[field] for field in LANG_FIELDS},
            {"name_de": "NAME", "name_en": "One"},
        )
        self.assertPositions(
            {
                "de_filled": 10,
                "en_filled": 20,
            }
        )

    def test_update_categ_user(self):
        self._personal(user_views.CATEG_USER)

    def test_update_categ_edited(self):
        self._personal(user_views.CATEG_EDITED)


if __name__ == "__main__":
    unittest.main()
