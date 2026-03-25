#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.checklists import checklist_status


@pytest.mark.unit
class Checklist(testcase.RollbackTestCase):
    def test_change_status_of_checklist(self):
        source_status = mock.MagicMock(status=20)
        target_status = mock.MagicMock(status=40)
        cl = mock.MagicMock(spec=checklist_status.Checklist, status=20)
        checklist_status.Checklist.change_status_of_checklist(
            cl, source_status, target_status
        )
        cl.ChangeState.assert_called_once_with(40, check_access=False)

    @mock.patch.object(checklist_status, "olc")
    def test_change_status_of_checklist_exception(self, olc):
        source_status = mock.MagicMock(status=20)
        target_status = mock.MagicMock(status=40)
        olc.StateDefinition.ByKeys.return_value.StateText = {"": "text"}

        cl = mock.MagicMock(
            spec=checklist_status.Checklist,
            status=20,
            ChangeState=mock.MagicMock(
                side_effect=checklist_status.ElementsError("foo")
            ),
            cdb_objektart="foo",
        )

        with self.assertRaises(checklist_status.util.ErrorMessage) as error:
            checklist_status.Checklist.change_status_of_checklist(
                cl, source_status, target_status
            )

        self.assertEqual(
            str(error.exception),
            str(
                "Die Checkliste befindet sich nicht "
                "im erforderlichen Status (text): foo"
            ),
        )
        cl.ChangeState.assert_called_once_with(40, check_access=False)

    def test_prepare_for_rating(self):
        cl = mock.MagicMock(
            spec=checklist_status.Checklist,
            status="foo",
            EVALUATION=mock.MagicMock(status="foo"),
        )
        self.assertIsNone(checklist_status.Checklist.prepare_for_rating(cl))
        cl.change_status_of_checklist.assert_called_once_with(
            cl.NEW,
            cl.EVALUATION,
        )

    def test_prepare_for_rating_fails(self):
        cl = mock.MagicMock(spec=checklist_status.Checklist)
        with self.assertRaises(checklist_status.util.ErrorMessage) as error:
            checklist_status.Checklist.prepare_for_rating(cl)

        self.assertEqual(
            str(error.exception),
            str(
                "Die Checkliste wurde bereits abgeschlossen/verworfen. "
                "Es können daher keine Prüfpunkte mehr angelegt oder "
                "geändert werden."
            ),
        )
        cl.change_status_of_checklist.assert_called_once_with(
            cl.NEW,
            cl.EVALUATION,
        )


if __name__ == "__main__":
    unittest.main()
