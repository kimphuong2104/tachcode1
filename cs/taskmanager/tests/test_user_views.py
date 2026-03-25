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

import json
import unittest

import mock

from cdb import auth, testcase, util
from cs.taskmanager import user_views
from cs.taskmanager.web.models.views import ViewBaseModel


def setUpModule():
    testcase.run_level_setup()


class TestUserViewUtility(testcase.RollbackTestCase):
    def test_get_frontend_condition(self):
        with self.assertRaises(TypeError):
            user_views.get_frontend_condition(None, None)

        self.assertEqual(
            user_views.get_frontend_condition({}, None),
            {
                "contexts": [],
                "types": [],
                "users": [],
            },
        )

        condition = {
            "types": ["cs_tasks_test_olc"],
            "contexts": ["38b7b6d1-9ee5-11ec-872a-334b6053520d"],
            "users": ["cs.tasks.test", "$(persno)"],
        }
        request = mock.MagicMock(application_url="BASE")
        result = user_views.get_frontend_condition(condition, request)
        self.assertEqual(
            set(result["contexts"]),
            {
                "BASE/api/v1/collection/test_task_olc/38b7b6d1-9ee5-11ec-872a-334b6053520d"
            },
        )
        self.assertEqual(set(result["types"]), {"BASE/api/v1/class/cs_tasks_test_olc"})
        self.assertEqual(
            set(result["users"]),
            {
                "BASE/api/v1/collection/person/cs.tasks.test",
                f"BASE/api/v1/collection/person/{auth.persno}",
            },
        )


class TestUserView(testcase.RollbackTestCase):
    def test_Edited(self):
        edited_view = user_views.UserView.Create()
        edited_view_edited = user_views.UserView.Create(
            customizes=edited_view.cdb_object_id,
            category="edited",
            subject_id=auth.persno,
            subject_type="Person",
        )
        self.assertEqual(edited_view.Edited, edited_view_edited)
        unedited_view = user_views.UserView.Create()
        user_views.UserView.Create(
            customizes=unedited_view.cdb_object_id,
            category="Wrong Category",
            subject_id=auth.persno,
            subject_type="Person",
        )
        user_views.UserView.Create(
            customizes=unedited_view.cdb_object_id,
            category="edited",
            subject_id="unknown user ID",
            subject_type="Person",
        )
        user_views.UserView.Create(
            customizes=unedited_view.cdb_object_id,
            category="edited",
            subject_id=auth.persno,
            subject_type="Common Role",
        )
        self.assertEqual(unedited_view.Edited, None)

    def test_Customizes(self):
        base_view = user_views.UserView.Create()
        customized_view = user_views.UserView.Create(
            customizes=base_view.cdb_object_id,
        )
        self.assertEqual(base_view.Customizes, None)
        self.assertEqual(customized_view.Customizes, base_view)

    def test_GetCustomAttributes(self):
        self.assertEqual(
            user_views.UserView.GetCustomAttributes("name", "condition"),
            {
                "category": "user",
                "subject_id": auth.persno,
                "subject_type": "Person",
                "name_de": "name",
                "cs_tasks_user_view_condition": "condition",
                "is_default": 0,
            },
        )

    def test_toDict(self):
        view = user_views.UserView.Create(
            name_de="A",
            name_en="B",
            category="preconfigured",
        )
        view.SetText("cs_tasks_user_view_condition", "condition")
        self.assertEqual(
            view.toDict(),
            {
                "cdb_cdate": None,
                "cdb_cpersno": None,
                "cdb_mdate": None,
                "cdb_mpersno": None,
                "cdb_object_id": view.cdb_object_id,
                "cs_tasks_user_view_condition": "condition",
                "category": "preconfigured",
                "customizes": "",
                "name_de": "A",
                "name_en": "B",
                "subject_id": None,
                "subject_type": None,
                "is_default": 0,
                "view_position": None,
            },
        )

    def test_toDict_legacy_field(self):
        view = mock.MagicMock(
            spec=user_views.UserView,
            name_de="A",
            category="preconfigured",
            name_it="Non presente nel database",
        )
        view.keys.return_value = ["name", "category", "name_it"]
        view.GetFieldNames.return_value = ["name", "category"]
        self.assertTrue("name_it" in dict(view))
        self.assertEqual(
            set(user_views.UserView.toDict(view).keys()),
            set(["name", "category", view.__condition_attr__]),
        )

    def test_getCustomCopyAttributes(self):
        view = user_views.UserView.Create(
            name_de="A",
            category="preconfigured",
        )
        self.assertEqual(
            view.getCustomCopyAttributes("B", "condition"),
            {
                "category": "user",
                "subject_id": auth.persno,
                "subject_type": "Person",
                "name_de": "B",
                "cs_tasks_user_view_condition": "condition",
                "is_default": 0,
                "cdb_object_id": None,
            },
        )

    def test_GetDefaultView(self):
        user_views.UserView.KeywordQuery(is_default=1).Delete()
        self.assertEqual(user_views.UserView.GetDefaultView(), None)
        public = user_views.UserView.Create(
            category="preconfigured",
            is_default=1,
            name_de="public",
            subject_id="public",
            subject_type="Common Role",
        )
        self.assertEqual(user_views.UserView.GetDefaultView().name, public.name)
        # FIXME we should probably only look at the user's actual roles
        non_public = user_views.UserView.Create(
            category="preconfigured",
            is_default=1,
            name_de="non-public",
            subject_id="cs_tasks_test1",
            subject_type="Common Role",
        )
        self.assertEqual(user_views.UserView.GetDefaultView().name, non_public.name)
        personal = user_views.UserView.Create(
            category="preconfigured",
            is_default=1,
            name_de="personal",
            subject_id=auth.persno,
            subject_type="Person",
        )
        self.assertEqual(user_views.UserView.GetDefaultView().name, personal.name)

    def test_ForUser(self):
        # WARNING: relies on granted read access
        # can't be mocked, unfortunately
        user_views.UserView.Query().Delete()
        user_views.UserView.Create(
            name_de="A",
            category="preconfigured",
            customizes="",
            subject_id="public",
            subject_type="Common Role",
        )
        user_views.UserView.Create(
            name_de="B",
            category="user",
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="default",
            category="preconfigured",
            is_default=1,
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="edited",
            category="edited",
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
        )
        c = user_views.UserView.Create(
            name_de="C",
            category="preconfigured",
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
        )
        d = user_views.UserView.Create(
            name_de="D",
            category="user",
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
        )
        # customized is used for edited views only starting in 15.6.0
        user_views.UserView.Create(
            name_de="customized C",
            category="user",
            customizes=c.cdb_object_id,
            subject_id=auth.persno,
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="2nd level customization",
            category="user",
            customizes=c.cdb_object_id,
            subject_id=auth.persno,
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="customizes categ user",
            category="user",
            customizes=d.cdb_object_id,
            subject_id=auth.persno,
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="wrong person 1",
            category="preconfigured",
            customizes="",
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="wrong person 2",
            category="user",
            customizes="",
            subject_id="somebody someone",
            subject_type="Person",
        )
        user_views.UserView.Create(
            name_de="E",
            category="user",
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
        )
        custom_none = user_views.UserView.Create(
            name_de="customizes None",
            category="user",
            subject_id=auth.persno,
            subject_type="Person",
        )
        custom_none.Update(customizes=None)
        self.assertEqual(
            {v.name for v in user_views.UserView.ForUser()},
            set("ABCDE"),
        )

    def test_get_all_views_for_admin(self):
        user_views.UserView.Query().Delete()
        user_view_def = user_views.UserView.Create(
            name_de="default",
            category="preconfigured",
            is_default=1,
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
            cdb_object_id="1",
        )
        user_view_def.SetText(user_view_def.__condition_attr__, json.dumps({}))
        user_view_a = user_views.UserView.Create(
            name_de="A",
            category="preconfigured",
            customizes="",
            subject_id="public",
            subject_type="Common Role",
            cdb_object_id="2",
        )
        user_view_a.SetText(user_view_a.__condition_attr__, json.dumps({}))
        user_view_b = user_views.UserView.Create(
            name_de="B",
            category="user",
            customizes="",
            subject_id=auth.persno,
            subject_type="Person",
            cdb_object_id="3",
        )
        user_view_b.SetText(user_view_b.__condition_attr__, json.dumps({}))
        user_view_c = user_views.UserView.Create(
            name_de="C",
            category="user",
            customizes="",
            subject_id="test_person",
            subject_type="Person",
            cdb_object_id="4",
        )
        user_view_c.SetText(user_view_c.__condition_attr__, json.dumps({}))
        model = mock.MagicMock(spec=ViewBaseModel)
        request = mock.MagicMock(application_url="BASE")
        result = ViewBaseModel.get_all_views(model, request)
        self.assertEqual(len(result["byID"]), 3)
        self.assertEqual(
            {result["byID"][v]["name"] for v in result["byID"]},
            set({"A", "B", "default"}),
        )

    def test_toJSON(self):
        self.maxDiff = None
        view = user_views.UserView.Create(category="foo")

        view.SetText("cs_tasks_user_view_condition", None)
        with self.assertRaises(ValueError):
            view.toJSON({})

        view.SetText("cs_tasks_user_view_condition", "'{}'")
        with self.assertRaises(ValueError):
            view.toJSON({})

        view.SetText("cs_tasks_user_view_condition", {})
        self.assertEqual(
            view.toJSON({}),
            {
                "@id": view.cdb_object_id,
                "filters": {
                    "contexts": [],
                    "types": [],
                    "users": [],
                },
                "edited": [],
                "name": "",
                "name_multilang": {
                    "de": None,
                    "en": None,
                },
                "category": "foo",
                "is_default": 0,
                "subject_id": None,
                "subject_name": "",
                "subject_type": None,
                "view_position": None,
            },
        )

        view.SetText(
            "cs_tasks_user_view_condition",
            json.dumps(
                {
                    "types": ["cs_tasks_test_olc"],
                    "contexts": ["38b7b6d1-9ee5-11ec-872a-334b6053520d"],
                    "users": ["cs.tasks.test", "$(persno)"],
                }
            ),
        )
        edited = user_views.UserView.Create(
            category="edited",
            customizes=view.cdb_object_id,
            subject_id=auth.persno,
            subject_type="Person",
        )
        view.Reload()

        with self.assertRaises(AttributeError):
            view.toJSON({})

        edited.SetText(
            "cs_tasks_user_view_condition",
            json.dumps(
                {
                    "types": ["cs_tasks_test_custom"],
                    "contexts": ["38b7b6d1-9ee5-11ec-872a-334b6053520d"],
                    "users": ["$(persno)"],
                }
            ),
        )
        request = mock.MagicMock(application_url="BASE")
        result = view.toJSON(request)
        self.assertEqual(
            set(result.keys()),
            {
                "@id",
                "filters",
                "edited",
                "name",
                "name_multilang",
                "category",
                "subject_id",
                "subject_type",
                "subject_name",
                "is_default",
                "view_position",
            },
        )
        self.assertEqual(result["category"], "foo")
        self.assertEqual(
            set(result["filters"].keys()),
            {"contexts", "types", "users"},
        )
        self.assertEqual(
            set(result["filters"]["contexts"]),
            {
                "BASE/api/v1/collection/test_task_olc/38b7b6d1-9ee5-11ec-872a-334b6053520d"
            },
        )
        self.assertEqual(
            set(result["filters"]["types"]),
            {"BASE/api/v1/class/cs_tasks_test_custom"},
        )
        self.assertEqual(
            set(result["filters"]["users"]),
            {f"BASE/api/v1/collection/person/{auth.persno}"},
        )
        self.assertEqual(
            set(result["edited"]),
            {"types", "users"},
        )

    def _validate_public_default(self, view, others, is_delete, expected):
        "persistent self is not public default, volatile self isn't either"
        result = view._validate_public_default(others, is_delete)
        self.assertEqual(str(result), expected)

    def test__validate_public_default_00(self):
        "persistent self is not public default, volatile self isn't either"
        self._validate_public_default(
            user_views.UserView(cdb_object_id="self"),
            [],
            False,
            'Es muss genau eine Standard-Benutzersicht für die Rolle "public" existieren (0 gefunden).',
        )

    def test__validate_public_default_00_others(self):
        "persistent self is not public default, volatile self isn't either"
        self._validate_public_default(
            user_views.UserView(cdb_object_id="self"),
            ["a", "b"],
            False,
            'Es muss genau eine Standard-Benutzersicht für die Rolle "public" existieren (2 gefunden).',
        )

    def test__validate_public_default_01(self):
        "persistent self is not public default, volatile self is"
        self._validate_public_default(
            user_views.UserView(
                cdb_object_id="self",
                is_default=1,
                subject_id="public",
                subject_type="Common Role",
            ),
            [],
            False,
            "None",
        )

    def test__validate_public_default_10(self):
        "persistent self is public default, volatile self is not"
        self._validate_public_default(
            user_views.UserView(cdb_object_id="self"),
            ["self"],
            False,
            'Es muss genau eine Standard-Benutzersicht für die Rolle "public" existieren (0 gefunden).',
        )

    def test__validate_public_default_11(self):
        "persistent self is public default, volatile self also is"
        self._validate_public_default(
            user_views.UserView(
                cdb_object_id="self",
                is_default=1,
                subject_id="public",
                subject_type="Common Role",
            ),
            ["self"],
            False,
            "None",
        )

    def test__validate_name_user_None(self):
        view = user_views.UserView(name_de=None)
        result = view._validate_name(True)
        self.assertEqual(str(result), "Bitte geben Sie einen Namen ein.")

    def test__validate_name_user(self):
        view = user_views.UserView(name_de="x")
        result = view._validate_name(True)
        self.assertEqual(str(result), "None")

    def test__validate_name_predef_None(self):
        view = user_views.UserView(name_de=None, name_en=None)
        result = view._validate_name(False)
        self.assertEqual(
            str(result),
            "Bitte übersetzen Sie den Namen in alle Sprachen: ['de', 'en']",
        )

    def test__validate_name_predef(self):
        view = user_views.UserView(name_de="x", name_en="x")
        result = view._validate_name(False)
        self.assertEqual(str(result), "None")

    def _validate_condition(self, condition, expected):
        ctx = mock.MagicMock()
        setattr(ctx.dialog, user_views.UserView.__condition_attr__, condition)
        result = user_views.UserView()._validate_condition(ctx)
        self.assertEqual(str(result), expected)

    def test__validate_condition_invalid(self):
        self._validate_condition("''", "Ungültiges JSON (cs_tasks_user_view_condition)")

    def test__validate_condition_valid(self):
        self._validate_condition('""', "None")

    def test__validate_condition_empty(self):
        self._validate_condition("", "None")

    def _validate_customizes(self, view_categ, base_categ, expected):
        view = mock.MagicMock(
            spec=user_views.UserView,
            category=view_categ,
            __customizes_whitelist__=user_views.UserView.__customizes_whitelist__,
        )
        if base_categ:
            view.Customizes.category = base_categ
        else:
            view.Customizes = None

        result = user_views.UserView._validate_customizes(view)
        self.assertEqual(str(result), expected)

    def test__validate_customizes_invalid(self):
        self._validate_customizes(
            "edited", "not whitelisted", "Ungültige Referenz in 'Basiert auf'."
        )

    def test__validate_customizes_valid(self):
        self._validate_customizes("edited", "user", "None")

    def test__validate_customizes_empty(self):
        self._validate_customizes(
            "edited", None, "Ungültige Referenz in 'Basiert auf'."
        )

    def test__validate_customizes_irrelevant(self):
        self._validate_customizes(
            "not edited, so we don't care", "not whitelisted", "None"
        )

    def test__validate_subject_user_not_person(self):
        view = user_views.UserView(
            subject_id="Administrator", subject_type="Common Role"
        )
        result = view._validate_subject(True)
        self.assertEqual(
            str(result), "Persönliche Sichten müssen einer Person zugeordnet sein."
        )

    def test__validate_subject_user(self):
        view = user_views.UserView(subject_id="caddok", subject_type="Person")
        result = view._validate_subject(True)
        self.assertEqual(str(result), "None")

    def test__validate_subject_predef_not_common_role(self):
        view = user_views.UserView(subject_id="caddok", subject_type="Person")
        result = view._validate_subject(False)
        self.assertEqual(
            str(result),
            "Vordefinierte Sichten müssen einer allgemeinen Rolle zugeordnet sein.",
        )

    def test__validate_subject_predef(self):
        view = user_views.UserView(
            subject_id="Administrator", subject_type="Common Role"
        )
        result = view._validate_subject(False)
        self.assertEqual(str(result), "None")

    def test__validate_default_user_other(self):
        view = user_views.UserView(subject_id="foo", is_default=1)
        result = view._validate_default(True, ["another default"], False)
        self.assertEqual(str(result), "None")

    def test__validate_default_user_other_delete(self):
        view = user_views.UserView(subject_id="foo", is_default=1)
        result = view._validate_default(True, ["another default"], True)
        self.assertEqual(str(result), "None")

    def test__validate_default_predef_other(self):
        view = user_views.UserView(subject_id="foo", is_default=1)
        result = view._validate_default(False, ["another default"], False)
        self.assertEqual(
            str(result),
            "Es existiert bereits eine Standard-Benutzersicht für die Rolle 'foo (None)'.",
        )

    def test__validate_default_predef_other_delete(self):
        view = user_views.UserView(subject_id="foo", is_default=1)
        result = view._validate_default(False, ["another default"], True)
        self.assertEqual(str(result), "None")

    def test__validate_default_predef(self):
        view = user_views.UserView(subject_id="foo", is_default=1)
        result = view._validate_default(False, [], False)
        self.assertEqual(str(result), "None")

    def _validate(self, sys_args, category, expected_is_user):
        ctx = mock.MagicMock(
            sys_args=sys_args,
            action="modify",
        )
        view = mock.MagicMock(
            spec=user_views.UserView,
            category=category,
            __defaults__=user_views.UserView.__defaults__,
        )
        view.get_defaults.return_value = {
            "public": "PUBLIC_DEFAULTS",
            view.subject_id: "ROLE_DEFAULTS",
        }

        with self.assertRaises(util.ErrorMessage) as error:
            user_views.UserView.validate(view, ctx)

        view._validate_public_default.assert_called_once_with("PUBLIC_DEFAULTS", False)
        view._validate_default.assert_called_once_with(
            expected_is_user, "ROLE_DEFAULTS", False
        )
        view._validate_name.assert_called_once_with(expected_is_user)
        view._validate_condition.assert_called_once_with(ctx)
        view._validate_customizes.assert_called_once_with()
        view._validate_subject.assert_called_once_with(expected_is_user)

        self.assertEqual(
            str(error.exception).split("\n"),
            [
                "- {}".format(x)
                for x in [
                    view._validate_public_default.return_value,
                    view._validate_default.return_value,
                    view._validate_name.return_value,
                    view._validate_condition.return_value,
                    view._validate_customizes.return_value,
                    view._validate_subject.return_value,
                ]
            ],
        )

    def _validate_delete(self, sys_args, category, expected_is_user):
        ctx = mock.MagicMock(
            sys_args=sys_args,
            action="delete",
        )
        view = mock.MagicMock(
            spec=user_views.UserView,
            category=category,
            __defaults__=user_views.UserView.__defaults__,
        )
        view.get_defaults.return_value = {
            "public": "PUBLIC_DEFAULTS",
            view.subject_id: "ROLE_DEFAULTS",
        }

        with self.assertRaises(util.ErrorMessage) as error:
            user_views.UserView.validate(view, ctx)

        view._validate_public_default.assert_called_once_with("PUBLIC_DEFAULTS", True)
        view._validate_default.assert_called_once_with(
            expected_is_user, "ROLE_DEFAULTS", True
        )
        view._validate_name.assert_not_called()
        view._validate_condition.assert_not_called()
        view._validate_customizes.assert_not_called()
        view._validate_subject.assert_not_called()

        self.assertEqual(
            str(error.exception).split("\n"),
            [
                "- {}".format(x)
                for x in [
                    view._validate_public_default.return_value,
                    view._validate_default.return_value,
                ]
            ],
        )

    def test_validate_predef(self):
        self._validate({}, "preconfigured", False)

    def test_validate_predef_delete(self):
        self._validate_delete({}, "preconfigured", False)

    def test_validate_user(self):
        self._validate({}, "user", True)

    def test_validate_user_delete(self):
        self._validate_delete({}, "user", True)

    def test_validate_edited(self):
        self._validate({}, "edited", True)

    def test_validate_edited_delete(self):
        self._validate_delete({}, "edited", True)


class TestUserViewCategoryBrowser(testcase.RollbackTestCase):
    def test_handlesSimpleCatalog(self):
        self.assertEqual(
            user_views.UserViewCategoryBrowser().handlesSimpleCatalog(), True
        )

    def test_getCatalogEntries(self):
        self.assertEqual(
            user_views.UserViewCategoryBrowser().getCatalogEntries(),
            ["preconfigured", "user", "edited"],
        )


if __name__ == "__main__":
    unittest.main()
