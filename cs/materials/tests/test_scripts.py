# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cs.materials.classification.adjust_classification_units import (
    AdjustClassificationUnits,
)
from cs.materials.classification.import_materials_classification import run
from cs.materials.tests import MaterialsTestCase


class TestScripts(MaterialsTestCase):
    def test_import_materials_classification_(self):
        # Use cs_classification_class as test table for the import

        # Delete all rows
        sqlapi.SQLdelete("FROM cs_classification_class")
        rset = sqlapi.RecordSet2(
            sql="SELECT COUNT(*) AS count FROM cs_classification_class"
        )
        rowCount = int(rset[0]["count"])
        self.assertEqual(rowCount, 0)

        # Re-import the classification data
        run()

        # check if the proper number of rows have been imported
        rset = sqlapi.RecordSet2(
            sql="SELECT COUNT(*) AS count FROM cs_classification_class"
        )
        rowCount = int(rset[0]["count"])
        self.assertEqual(rowCount, 127)

    def test_adjust_classification_units(self):
        # Intentionally introduce a physical unit inconsistency
        sqlapi.SQLupdate(
            """cs_unit SET cdb_object_id='aaa7f551-3bc0-11e7-8db9-28d24433bbb'
               WHERE       cdb_object_id='1e57f551-3bc0-11e7-8db9-28d24433bf35'"""
        )
        sqlapi.SQLupdate(
            """cdb_object SET   id='aaa7f551-3bc0-11e7-8db9-28d24433bbb'
               WHERE            id='1e57f551-3bc0-11e7-8db9-28d24433bf35'"""
        )

        rset = sqlapi.RecordSet2(
            sql="""SELECT count(*) AS count
                   FROM cs_property
                   WHERE unit_object_id = 'aaa7f551-3bc0-11e7-8db9-28d24433bbb'"""
        )
        rowCount = int(rset[0]["count"])
        self.assertEqual(rowCount, 0)
        # rset = sqlapi.RecordSet2(sql="SELECT unit_object_id FROM cs_class_property")
        # rset = sqlapi.RecordSet2(sql="SELECT default_unit_object_id FROM cs_class_property")

        # Launch the physical units adjustment
        AdjustClassificationUnits.run()

        rset = sqlapi.RecordSet2(
            sql="""SELECT count(*) AS count
                   FROM cs_property
                   WHERE unit_object_id = 'aaa7f551-3bc0-11e7-8db9-28d24433bbb'"""
        )
        rowCount = int(rset[0]["count"])
        self.assertEqual(rowCount, 12)
        # rset = sqlapi.RecordSet2(sql="SELECT unit_object_id FROM cs_class_property")
        # rset = sqlapi.RecordSet2(sql="SELECT default_unit_object_id FROM cs_class_property")
