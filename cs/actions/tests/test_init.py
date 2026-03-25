# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


import unittest

import mock
from cdb import sqlapi

from cs.actions import Action


class ActionTestCase(unittest.TestCase):
    @mock.patch.object(sqlapi, "RecordSet2")
    def test_checkResponsible_otherRole(self, recordSet):
        ctx = mock.MagicMock()
        action = mock.MagicMock(
            Action, subject_id="sId", subject_type="sType", cdb_project_id="pId"
        )

        Action.checkResponsible(action, ctx)
        recordSet.assert_not_called()

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(sqlapi, "RecordSet2")
    def test_checkResponsible_noProject(self, recordSet, cdbmsg):
        ctx = mock.MagicMock()
        action = mock.MagicMock(
            Action, subject_id="sId", subject_type="PCS Role", cdb_project_id=None
        )

        with self.assertRaises(Exception):
            Action.checkResponsible(action, ctx)

        recordSet.assert_not_called()
        cdbmsg.assert_called_once_with(cdbmsg.kFatal, "cdbpcs_invalid_resp")

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(sqlapi, "quote", return_value="quoted")
    @mock.patch.object(sqlapi, "RecordSet2", return_value=False)
    def test_checkResponsible_invalid(self, recordSet, quote, cdbmsg):
        ctx = mock.MagicMock()
        action = mock.MagicMock(
            Action,
            subject_id="sId",
            subject_type="PCS Role",
            cdb_project_id="Some Project",
        )

        with self.assertRaises(Exception):
            Action.checkResponsible(action, ctx)

        recordSet.assert_called_once_with(
            "cdb_action_resp_brows",
            "cdb_project_id = 'quoted' "
            "AND subject_id = 'quoted' "
            "AND subject_type = 'quoted'",
        )
        cdbmsg.assert_called_once_with(cdbmsg.kFatal, "cdbpcs_invalid_resp")

    @mock.patch.object(sqlapi, "quote", return_value="quoted")
    @mock.patch.object(sqlapi, "RecordSet2", return_value=True)
    def test_checkResponsible(self, recordSet, quote):
        ctx = mock.MagicMock()
        action = mock.MagicMock(
            Action,
            subject_id="sId",
            subject_type="PCS Role",
            cdb_project_id="Some Project",
        )

        Action.checkResponsible(action, ctx)

        recordSet.assert_called_once_with(
            "cdb_action_resp_brows",
            "cdb_project_id = 'quoted' "
            "AND subject_id = 'quoted' "
            "AND subject_type = 'quoted'",
        )

    @mock.patch.object(sqlapi, "SQLupdate")
    @mock.patch("cdb.comparch.packages.Package.ByKeys")
    def test_checkPartReference_reference_intact(self, package_by_keys, SQLupdate):
        "No need to do something since Action-Part reference is intact"
        # Mock module cs for test duration only in order to mock cs.vp.items.KeywordQuery
        # even when cs.vp is not installed
        mocked_module = mock.MagicMock()
        item_keyword_query = mocked_module.vp.items.Item.KeywordQuery
        replacing_import = mock.patch.dict("sys.modules", cs=mocked_module)

        replacing_import.start()
        package_by_keys.return_value = "something"  # non-falsy value
        mock_ctx = mock.MagicMock()
        mock_action = mock.Mock(
            Action, teilenummer="foo", t_index="bar", part_object_id="baz"
        )
        Action.checkPartReference(mock_action, mock_ctx)
        item_keyword_query.assert_not_called()
        SQLupdate.assert_not_called()
        replacing_import.stop()

    @mock.patch.object(sqlapi, "SQLupdate")
    @mock.patch("cdb.comparch.packages.Package.ByKeys")
    def test_checkPartReference_missing_part_object_id(
        self, package_by_keys, SQLupdate
    ):
        "Update missing part_object_id"
        # Mock module cs for test duration only in order to mock cs.vp.items.KeywordQuery
        # even when cs.vp is not installed
        mocked_module = mock.MagicMock()
        item_keyword_query = mocked_module.vp.items.Item.KeywordQuery
        replacing_import = mock.patch.dict("sys.modules", cs=mocked_module)

        replacing_import.start()
        package_by_keys.return_value = "something"  # non-falsy value
        item_keyword_query.return_value = [mock.MagicMock(cdb_object_id="bam")]
        mock_ctx = mock.MagicMock()
        mock_action = mock.Mock(
            Action,
            teilenummer="foo",
            t_index="bar",
            part_object_id="",  # Not set
            cdb_object_id="baz",
        )
        Action.checkPartReference(mock_action, mock_ctx)
        item_keyword_query.assert_called_once_with(teilenummer="foo", t_index="bar")
        SQLupdate.assert_called_once_with(
            "cdb_action SET part_object_id='bam' WHERE cdb_object_id='baz'"
        )
        replacing_import.stop()

    @mock.patch.object(sqlapi, "SQLupdate")
    @mock.patch("cdb.comparch.packages.Package.ByKeys")
    def test_checkPartReference_missing_teilenummer_t_index(
        self, package_by_keys, SQLupdate
    ):
        "Update missing teilenummer, t_index"
        # Mock module cs for test duration only in order to mock cs.vp.items.KeywordQuery
        # even when cs.vp is not installed
        mocked_module = mock.MagicMock()
        item_keyword_query = mocked_module.vp.items.Item.KeywordQuery
        replacing_import = mock.patch.dict("sys.modules", cs=mocked_module)

        replacing_import.start()
        package_by_keys.return_value = "something"  # non-falsy value
        item_keyword_query.return_value = [
            mock.MagicMock(teilenummer="bam", t_index="foo")
        ]
        mock_ctx = mock.MagicMock()
        mock_action = mock.Mock(
            Action,
            part_object_id="bar",
            cdb_object_id="baz",
            teilenummer="",  # Not set
            t_index="",  # Not set
        )
        Action.checkPartReference(mock_action, mock_ctx)
        item_keyword_query.assert_called_once_with(cdb_object_id="bar")
        SQLupdate.assert_called_once_with(
            """cdb_action
                                SET teilenummer='bam'
                                    AND t_index='foo'
                                WHERE cdb_object_id='baz'
                            """
        )
        replacing_import.stop()
