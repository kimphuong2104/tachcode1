#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import mock
import pytest

from cs.pcs.projects.catalogs import CatalogResponsible


@pytest.mark.unit
class TestCatalogResponsible(unittest.TestCase):
    def test_init_exception(self):
        mock_catalogResponsible = mock.MagicMock(CatalogResponsible)
        mock_catalogResponsible.getInvokingDlgValue.side_effect = Exception()

        with self.assertRaises(Exception):
            CatalogResponsible.init(mock_catalogResponsible)
        mock_catalogResponsible.getInvokingDlgValue.assert_called_once_with(
            "cdb_project_id"
        )
        mock_catalogResponsible.setResultData.assert_not_called()

    @mock.patch("cs.pcs.projects.catalogs.CatalogResponsibleData")
    def test_init_no_project_id(self, catRespData):
        catRespData.side_effect = lambda x, y: [x, y]
        mock_catalogResponsible = mock.MagicMock(CatalogResponsible)
        mock_catalogResponsible.getInvokingDlgValue.side_effect = KeyError()

        CatalogResponsible.init(mock_catalogResponsible)
        mock_catalogResponsible.getInvokingDlgValue.assert_called_once_with(
            "cdb_project_id"
        )
        mock_catalogResponsible.setResultData.assert_called_once_with(
            ["", mock_catalogResponsible]
        )

    @mock.patch("cs.pcs.projects.catalogs.CatalogResponsibleData")
    def test_init_with_project_id(self, catRespData):
        catRespData.side_effect = lambda x, y: [x, y]
        mock_catalogResponsible = mock.MagicMock(CatalogResponsible)
        mock_catalogResponsible.getInvokingDlgValue.return_value = "LoremIpsum"

        CatalogResponsible.init(mock_catalogResponsible)
        mock_catalogResponsible.getInvokingDlgValue.assert_called_once_with(
            "cdb_project_id"
        )
        mock_catalogResponsible.setResultData.assert_called_once_with(
            ["LoremIpsum", mock_catalogResponsible]
        )


if __name__ == "__main__":
    unittest.main()
