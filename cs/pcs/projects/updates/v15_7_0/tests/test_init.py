#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import unittest
import pytest
from cdb import testcase
from cs.pcs.projects.updates import v15_7_0


@pytest.mark.unit
class TestUpdateObjectRulesToExcludeBaselines(testcase.RollbackTestCase):
    @mock.patch.object(v15_7_0.sqlapi, "SQL")
    @mock.patch.object(v15_7_0.sqlapi, "SQLrows", return_value=None)
    @mock.patch.object(v15_7_0.sqlapi, "SQLselect")
    def test_run_no_predicates_found(self, SQLselect, SQLrows, SQL):
        "No Terms are added, if no predicates are found"
        v15_7_0.UpdateObjectRulesToExcludeBaselines().run()
        SQLselect.assert_called_once()
        SQLrows.assert_called_once()
        SQL.assert_not_called()

    @mock.patch.object(v15_7_0.sqlapi, "SQL")
    @mock.patch.object(
        v15_7_0.sqlapi,
        "SQLstring",
        side_effect=[
            "foo_name",
            "foo_predicate_name",
            "foo_fqpyname",
            "foo_module",
            "0",
        ],
    )
    @mock.patch.object(v15_7_0.sqlapi, "SQLrows", return_value=1)
    @mock.patch.object(v15_7_0.sqlapi, "SQLselect")
    def test_run(self, SQLselect, SQLrows, SQLstring, SQL):
        "Adding Term to each predicate found"
        v15_7_0.UpdateObjectRulesToExcludeBaselines().run()
        SQLselect.assert_called_once()
        SQLrows.assert_called_once()
        SQLstring.assert_has_calls(
            [
                mock.call(SQLselect.return_value, 0, 0),
                mock.call(SQLselect.return_value, 1, 0),
                mock.call(SQLselect.return_value, 2, 0),
                mock.call(SQLselect.return_value, 3, 0),
                mock.call(SQLselect.return_value, 4, 0),
            ]
        )
        SQL.assert_called_once_with(
            """
            INSERT INTO cdb_pyterm
            (
                name,
                fqpyname,
                predicate_name,
                cdb_module_id,
                id,
                attribute,
                operator,
                expression
            )
            VALUES (
                'foo_name',
                'foo_fqpyname',
                'foo_predicate_name',
                'foo_module',
                '1',
                'ce_baseline_id',
                '=',
                ''
            )
        """
        )


if __name__ == "__main__":
    unittest.main()
