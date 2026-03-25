# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Unit Tests for cs.audittrail
"""

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


import unittest
from datetime import date

from cdb import constants, sqlapi, testcase
from cdb.objects.operations import operation

from cs.actions import Action


def setUpModule():
    testcase.run_level_setup()
    sqlapi.SQLdelete("FROM cdb_audittrail")
    sqlapi.SQLdelete("FROM cdb_audittrail_detail")


class AuditTrailTestCase(unittest.TestCase):
    def test_auditTrailAvailable(self):
        auditTrail_0 = sqlapi.RecordSet2("cdb_audittrail")
        assert len(auditTrail_0) == 0  # pylint: disable=len-as-condition

        action_1 = operation(
            constants.kOperationNew,
            Action,
            name="Test 1",
            status=20,
            cdb_status_txt="Execution",
            subject_id="caddok",
            subject_type="Person",
            currency_object_id="c3fef935-6c9c-11df-8e74-d05fa2b39649",
            cost=0.81,
            effort=9876.50,
            end_time_plan=date(2018, 9, 1),
        )

        operation(
            constants.kOperationNew,
            Action,
            name="Test 2",
            status=20,
            cdb_status_txt="Execution",
            subject_id=action_1.subject_id,
            subject_type="Person",
            parent_object_id=action_1.cdb_object_id,
        )

        auditTrail_1 = sqlapi.RecordSet2("cdb_audittrail", "type='create'")
        assert len(auditTrail_1) == 2

        operation(
            constants.kOperationModify,
            action_1,
            effort=2.50,
        )

        auditTrail_2 = sqlapi.RecordSet2("cdb_audittrail", "type='modify'")
        assert len(auditTrail_2) == 1

        auditTrail_3 = sqlapi.RecordSet2(
            "cdb_audittrail_detail", "attribute_name='effort' AND old_value='9876.5'"
        )

        print("INFO: " + str(len(auditTrail_3)))
        assert len(auditTrail_3) == 1
        assert auditTrail_3[0].new_value == "2.5"

        operation(
            constants.kOperationDelete,
            action_1,
        )  # deleting action_1 will also delete action_2 because action_2 is a subaction

        auditTrail_4 = sqlapi.RecordSet2("cdb_audittrail", "type='delete'")

        assert len(auditTrail_4) == 1


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
