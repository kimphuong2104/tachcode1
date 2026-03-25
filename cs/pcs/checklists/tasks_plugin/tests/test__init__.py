#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.checklists import Checklist, ChecklistItem, tasks_plugin


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(
        tasks_plugin.fRatingValue,
        "Query",
        return_value=[
            {"name": "A", "rating_id": 1},
            {"name": "B", "rating_id": 2},
            {"name": "A", "rating_id": 3},
        ],
    )
    def test_get_ratings(self, Query):
        "returns cached ratings"
        tasks_plugin.get_ratings.cache_clear()
        self.assertEqual(
            tasks_plugin.get_ratings(),
            {
                "A": {
                    1: {"name": "A", "rating_id": 1},
                    3: {"name": "A", "rating_id": 3},
                },
                "B": {
                    2: {"name": "B", "rating_id": 2},
                },
            },
        )
        tasks_plugin.get_ratings()
        Query.assert_called_once_with(access="read", addtl="ORDER BY name, rating_id")

    @mock.patch.object(
        tasks_plugin, "get_ratings", return_value={"foo": {"bar": "baz"}}
    )
    def test_get_rating(self, get_ratings):
        "returns the first rating matching the args"
        self.assertEqual(tasks_plugin.get_rating("foo", "bar"), "baz")
        get_ratings.assert_called_once_with()


@pytest.mark.unit
class ChecklistWithCsTasks(unittest.TestCase):
    def test_getCsTasksContexts(self):
        "resolves checklist context"
        cl = mock.MagicMock(spec=Checklist)
        self.assertEqual(
            tasks_plugin.ChecklistWithCsTasks.getCsTasksContexts(cl), [cl.Project]
        )

    def test_csTasksDelegate_get_default(self):
        "returns project manager"
        cl = mock.MagicMock(spec=Checklist)
        self.assertEqual(
            tasks_plugin.ChecklistWithCsTasks.csTasksDelegate_get_default(cl),
            cl.csTasksDelegate_get_project_manager.return_value,
        )

    @mock.patch.object(tasks_plugin, "assert_team_member", autospec=True)
    def test_csTasksDelegate(self, assert_team_member):
        "supports delegating multiple tasks of a single project"
        cl = mock.MagicMock(spec=Checklist)
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks_plugin.ChecklistWithCsTasks.csTasksDelegate(cl, ctx),
        )
        assert_team_member.assert_called_once_with(ctx, cl.cdb_project_id)
        cl.Super.assert_called_once_with(tasks_plugin.ChecklistWithCsTasks)
        cl.Super.return_value.csTasksDelegate.assert_called_once_with(ctx)

    def test_preset_csTasksDelegate(self):
        "presets project when delegating multiple tasks of a single project"
        cl = mock.MagicMock(spec=Checklist)
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo"},
                {"cdb_project_id": "foo"},
            ]
        )
        self.assertIsNone(
            tasks_plugin.ChecklistWithCsTasks.preset_csTasksDelegate(cl, ctx),
        )
        ctx.set.assert_called_once_with(
            "cdb_project_id",
            "foo",
        )
        cl.Super.assert_called_once_with(tasks_plugin.ChecklistWithCsTasks)
        cl.Super.return_value.preset_csTasksDelegate.assert_called_once_with(ctx)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_preset_csTasksDelegate_error(self, CDBMsg):
        "fails if ctx.objects contain multiple project IDs"
        cl = mock.MagicMock(spec=Checklist)
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo"},
                {"cdb_project_id": "bar"},
            ]
        )
        with self.assertRaises(tasks_plugin.ue.Exception):
            tasks_plugin.ChecklistWithCsTasks.preset_csTasksDelegate(
                cl,
                ctx,
            )
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_delegate")
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 0)


@pytest.mark.unit
class ChecklistItemWithCsTasks(unittest.TestCase):
    def test_getCsTasksContexts(self):
        "resolves checklist item context"
        cli = mock.MagicMock(spec=ChecklistItem)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks.getCsTasksContexts(cli), [cli.Project]
        )

    def test_csTasksDelegate_get_default(self):
        "returns project manager"
        cli = mock.MagicMock(spec=ChecklistItem)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks.csTasksDelegate_get_default(cli),
            cli.csTasksDelegate_get_project_manager.return_value,
        )

    @mock.patch.object(tasks_plugin, "assert_team_member", autospec=True)
    def test_csTasksDelegate(self, assert_team_member):
        "supports delegating multiple clis of a single project"
        cli = mock.MagicMock(spec=ChecklistItem)
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks_plugin.ChecklistItemWithCsTasks.csTasksDelegate(cli, ctx),
        )
        assert_team_member.assert_called_once_with(ctx, cli.cdb_project_id)
        cli.Super.assert_called_once_with(tasks_plugin.ChecklistItemWithCsTasks)
        cli.Super.return_value.csTasksDelegate.assert_called_once_with(ctx)

    def test_preset_csTasksDelegate(self):
        "presets project when delegating multiple clis of a single project"
        cli = mock.MagicMock(spec=ChecklistItem)
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo"},
                {"cdb_project_id": "foo"},
            ]
        )
        self.assertIsNone(
            tasks_plugin.ChecklistItemWithCsTasks.preset_csTasksDelegate(
                cli,
                ctx,
            ),
        )
        ctx.set.assert_called_once_with(
            "cdb_project_id",
            "foo",
        )
        cli.Super.assert_called_once_with(
            tasks_plugin.ChecklistItemWithCsTasks,
        )
        cli.Super.return_value.preset_csTasksDelegate.assert_called_once_with(ctx)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_preset_csTasksDelegate_error(self, CDBMsg):
        "fails if ctx.objects contain multiple project IDs"
        cli = mock.MagicMock(spec=ChecklistItem)
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo"},
                {"cdb_project_id": "bar"},
            ]
        )
        with self.assertRaises(tasks_plugin.ue.Exception):
            tasks_plugin.ChecklistItemWithCsTasks.preset_csTasksDelegate(
                cli,
                ctx,
            )
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_delegate")
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 0)

    @mock.patch.object(tasks_plugin, "_LabelValueAccessor", autospec=True)
    @mock.patch.object(tasks_plugin.IconCache, "getIcon")
    def test__getObjIcon(self, getIcon, LVA):
        "returns custom object icon"
        cli = mock.MagicMock(spec=ChecklistItem)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks._getObjIcon(
                cli,
                "foo",
                "bar",
            ),
            getIcon.return_value,
        )
        getIcon.assert_called_once_with("foo", None, LVA.return_value)
        LVA.assert_called_once_with("bar", True)

    def test__getCustomRatingIcon(self):
        "returns custom OLC icon"
        cli = mock.MagicMock(spec=ChecklistItem)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks._getCustomRatingIcon(
                cli,
                "föö",
                [("key", "valü"), ("k2", "v2")],
            ),
            "/resources/icons/byname/f%C3%B6%C3%B6?key=val%C3%BC&k2=v2",
        )

    @mock.patch.object(tasks_plugin, "get_rating")
    def test_getCsTasksStatusData_noRatID(self, get_rating):
        self.maxDiff = None
        cli = mock.MagicMock(spec=ChecklistItem, Rating=None, rating_id=None)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks.getCsTasksStatusData(cli),
            {
                "dialog": {
                    "rating_id": get_rating.return_value.rating_id,
                    "rating_value_de": get_rating.return_value.rating_value_de,
                    "rating_value_en": get_rating.return_value.rating_value_en,
                },
                "icon": cli._getCustomRatingIcon.return_value,
                "label": get_rating.return_value.Value.__getitem__.return_value,
                "priority": get_rating.return_value.position,
            },
        )
        get_rating.assert_called_once_with(
            cli.rating_scheme,
            "clear",
        )
        get_rating.return_value.Value.__getitem__.assert_called_once_with("")
        cli._getCustomRatingIcon.assert_called_once_with(
            "cdbpcs_cl_item_object",
            {
                "rating_id": get_rating.return_value.rating_id,
                "rating_scheme": cli.rating_scheme,
                "type": "Checklist",
            },
        )

    @mock.patch.object(tasks_plugin, "get_rating")
    def test_getCsTasksStatusData_noRating(self, get_rating):
        self.maxDiff = None
        cli = mock.MagicMock(spec=ChecklistItem, Rating=None)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks.getCsTasksStatusData(cli),
            {
                "dialog": {
                    "rating_id": get_rating.return_value.rating_id,
                    "rating_value_de": get_rating.return_value.rating_value_de,
                    "rating_value_en": get_rating.return_value.rating_value_en,
                },
                "icon": cli._getCustomRatingIcon.return_value,
                "label": get_rating.return_value.Value.__getitem__.return_value,
                "priority": get_rating.return_value.position,
            },
        )
        get_rating.assert_called_once_with(cli.rating_scheme, cli.rating_id)
        get_rating.return_value.Value.__getitem__.assert_called_once_with("")
        cli._getCustomRatingIcon.assert_called_once_with(
            "cdbpcs_cl_item_object",
            {
                "rating_id": get_rating.return_value.rating_id,
                "rating_scheme": cli.rating_scheme,
                "type": "Checklist",
            },
        )

    @mock.patch.object(tasks_plugin, "get_rating")
    def test_getCsTasksStatusData(self, get_rating):
        self.maxDiff = None
        cli = mock.MagicMock(spec=ChecklistItem)
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks.getCsTasksStatusData(cli),
            {
                "label": get_rating.return_value.Value.__getitem__.return_value,
                "icon": cli._getCustomRatingIcon.return_value,
                "dialog": {
                    "rating_id": get_rating.return_value.rating_id,
                    "rating_value_de": get_rating.return_value.rating_value_de,
                    "rating_value_en": get_rating.return_value.rating_value_en,
                },
                "priority": get_rating.return_value.position,
            },
        )
        get_rating.assert_called_once_with(cli.rating_scheme, cli.rating_id)
        cli._getCustomRatingIcon.assert_called_once_with(
            "cdbpcs_cl_item_object",
            {
                "rating_id": get_rating.return_value.rating_id,
                "rating_scheme": cli.rating_scheme,
                "type": "Checklist",
            },
        )

    @mock.patch.object(tasks_plugin, "get_rating")
    def test_getCsTasksStatusData_explicit(self, get_rating):
        self.maxDiff = None
        cli = mock.MagicMock(spec=ChecklistItem)
        rating = mock.MagicMock()
        self.assertEqual(
            tasks_plugin.ChecklistItemWithCsTasks.getCsTasksStatusData(
                cli,
                rating,
            ),
            {
                "dialog": {
                    "rating_id": rating.rating_id,
                    "rating_value_de": rating.rating_value_de,
                    "rating_value_en": rating.rating_value_en,
                },
                "icon": cli._getCustomRatingIcon.return_value,
                "label": rating.Value.__getitem__.return_value,
                "priority": rating.position,
            },
        )
        get_rating.assert_not_called()
        cli._getCustomRatingIcon.assert_called_once_with(
            "cdbpcs_cl_item_object",
            {
                "rating_id": rating.rating_id,
                "rating_scheme": cli.rating_scheme,
                "type": "Checklist",
            },
        )
        rating.Value.__getitem__.assert_called_once_with("")


if __name__ == "__main__":
    unittest.main()
