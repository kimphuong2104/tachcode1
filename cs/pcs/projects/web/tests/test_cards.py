#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
import pytest
from cdb.platform.mom.entities import CDBClassDef

import cs.pcs.projects.web.cards as project_card
from cs.pcs.projects.common import cards


class Map(dict):
    def __init__(self):
        super().__init__()
        self.real_dict = {"name": "foo", "rolename": "bar"}

    def __getattr__(self, attr):
        return self.real_dict[attr]


@pytest.mark.unit
class Cards(unittest.TestCase):
    @mock.patch.object(cards.logging, "exception")
    @mock.patch.object(
        cards.DisplayConfiguration, "get_mask_name", side_effect=cards.ElementsError
    )
    def test_add_card_exception(self, get_mask_name, exception):
        "logs exception if display config fails"
        self.assertIsNone(cards.add_card(None, "cls", "card"))
        get_mask_name.assert_called_once_with("cls", "card")
        exception.assert_called_once_with(
            "error while requesting DisplayConfiguration for: '%s', '%s'", "cls", "card"
        )

    @mock.patch.object(cards.logging, "warning")
    @mock.patch.object(cards.DisplayConfiguration, "get_mask_name", return_value=None)
    def test_add_card_warn(self, get_mask_name, warning):
        "logs warning if no display config exists"
        self.assertIsNone(cards.add_card(None, "cls", "card"))
        get_mask_name.assert_called_once_with("cls", "card")
        warning.assert_called_once_with(
            "no display configuration found: '%s', '%s'",
            "cls",
            "card",
        )

    @mock.patch.object(cards.logging, "error")
    @mock.patch.object(cards.DisplayConfiguration, "get_mask_name")
    def test_add_card_error(self, get_mask_name, error):
        "logs error if mask contains no register"
        cdef = mock.MagicMock(autospec=CDBClassDef)
        cdef.get_dialog = mock.Mock(return_value={"registers": None})
        with mock.patch.object(cards, "CDBClassDef", return_value=cdef) as cd:
            self.assertIsNone(cards.add_card(None, "cls", "card"))
            get_mask_name.assert_called_once_with("cls", "card")
            cd.assert_called_once_with("cls")
            cdef.get_dialog.assert_called_once_with(get_mask_name.return_value, {})
            error.assert_called_once_with(
                "mask not found: '%s'",
                get_mask_name.return_value,
            )

    @mock.patch.object(cards.DisplayConfiguration, "get_mask_name")
    def test_add_card_without_relship_without_link_target(self, get_mask_name):
        "extends app_setup successfully with a relship and without a link_target"
        app_setup = mock.MagicMock()
        relship = []
        cdef = mock.MagicMock(autospec=CDBClassDef)
        mask = {"registers": [{"maskitems": [{"config": {}}]}]}
        cdef.get_dialog = mock.Mock(return_value=mask)
        with mock.patch.object(
            cards, "CDBClassDef", return_value=cdef
        ) as cd, mock.patch.object(
            cards.Relship, "KeywordQuery", return_value=relship
        ) as rel:
            self.assertIsNone(cards.add_card(app_setup, "cls", "card"))
            get_mask_name.assert_called_once_with("cls", "card")
            cd.assert_called_once_with("cls")
            rel.assert_called_once_with(referer="cls", rs_profile="cdb_association_1_1")
            cdef.get_dialog.assert_called_once_with(get_mask_name.return_value, {})
            app_setup.merge_in.assert_called_once_with(
                ["applicationConfiguration", "cards", "card", "cls"],
                cdef.get_dialog.return_value,
            )

    @mock.patch.object(cards.DisplayConfiguration, "get_mask_name")
    def test_add_card_with_relship_without_link_target(self, get_mask_name):
        "extends app_setup successfully with a relship but without a link_target"
        app_setup = mock.MagicMock()

        real_dict = {"name": "foo", "rolename": "bar"}

        mock_relship = mock.MagicMock()
        mock_relship.__getitem__.side_effect = real_dict.__getitem__

        relship = [mock_relship]
        cdef = mock.MagicMock(autospec=CDBClassDef)
        mask = {"registers": [{"maskitems": [{"config": {}}]}]}
        cdef.get_dialog = mock.Mock(return_value=mask)
        with mock.patch.object(
            cards, "CDBClassDef", return_value=cdef
        ) as cd, mock.patch.object(
            cards.Relship, "KeywordQuery", return_value=relship
        ) as rel:
            self.assertIsNone(cards.add_card(app_setup, "cls", "card"))
            get_mask_name.assert_called_once_with("cls", "card")
            cd.assert_called_once_with("cls")
            rel.assert_called_once_with(referer="cls", rs_profile="cdb_association_1_1")
            cdef.get_dialog.assert_called_once_with(get_mask_name.return_value, {})
            app_setup.merge_in.assert_called_once_with(
                ["applicationConfiguration", "cards", "card", "cls"],
                cdef.get_dialog.return_value,
            )

    @mock.patch.object(cards.DisplayConfiguration, "get_mask_name")
    def test_add_card_with_relship_with_link_target(self, get_mask_name):
        "extends app_setup successfully with a relship and a link_target with the same relship"
        app_setup = mock.MagicMock()

        relship = [Map()]
        cdef = mock.MagicMock(autospec=CDBClassDef)
        mask = {"registers": [{"maskitems": [{"config": {"link_target": "foo"}}]}]}
        cdef.get_dialog = mock.Mock(return_value=mask)
        with mock.patch.object(
            cards, "CDBClassDef", return_value=cdef
        ) as cd, mock.patch.object(
            cards.Relship, "KeywordQuery", return_value=relship
        ) as rel:
            self.assertIsNone(cards.add_card(app_setup, "cls", "card"))
            get_mask_name.assert_called_once_with("cls", "card")
            cd.assert_called_once_with("cls")
            rel.assert_called_once_with(referer="cls", rs_profile="cdb_association_1_1")
            cdef.get_dialog.assert_called_once_with(get_mask_name.return_value, {})
            app_setup.merge_in.assert_called_once_with(
                ["applicationConfiguration", "cards", "card", "cls"],
                {"registers": [{"maskitems": [{"config": {"link_target": "bar"}}]}]},
            )

    @mock.patch.object(cards.DisplayConfiguration, "get_mask_name")
    def test_add_card_with_relship_with_wrong_link_target(self, get_mask_name):
        "extends app_setup successfully with a relship and a wrong link_target"
        app_setup = mock.MagicMock()

        relship = [Map()]
        cdef = mock.MagicMock(autospec=CDBClassDef)
        mask = {"registers": [{"maskitems": [{"config": {"link_target": "foz"}}]}]}
        cdef.get_dialog = mock.Mock(return_value=mask)
        with mock.patch.object(
            cards, "CDBClassDef", return_value=cdef
        ) as cd, mock.patch.object(
            cards.Relship, "KeywordQuery", return_value=relship
        ) as rel:
            self.assertIsNone(cards.add_card(app_setup, "cls", "card"))
            get_mask_name.assert_called_once_with("cls", "card")
            cd.assert_called_once_with("cls")
            rel.assert_called_once_with(referer="cls", rs_profile="cdb_association_1_1")
            cdef.get_dialog.assert_called_once_with(get_mask_name.return_value, {})
            app_setup.merge_in.assert_called_once_with(
                ["applicationConfiguration", "cards", "card", "cls"],
                {"registers": [{"maskitems": [{"config": {"link_target": ""}}]}]},
            )

    @mock.patch.object(project_card, "add_card")
    def test_setup_project_default_card(self, add_card):
        "calls add_card to add the project card config"
        self.assertIsNone(project_card.setup_project_default_card(None, None, "foo"))
        add_card.assert_called_once_with("foo", "cdbpcs_project", "table_card")


if __name__ == "__main__":
    unittest.main()
