#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module cs.materials.classification.adjust_classification_units

Fixes unit object id references in the cs_property and cs_class_property tables.

During the materials classification tree import, some records from cs_unit might be skipped due to
a unique constraint violation - this can happen if a customer has already created a physical unit with the
same symbol. Since the physical units are referenced through their cdb_object_id, this might lead to
inconsistent unit assignments from the imported materials classes. This script fixes the unit_object_id and
default_unit_object_id references in the materials classes so that they point to the physical units which
already exist in the system and which have the same symbol as those which were skipped earlier.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import json
import os
import sys

from cdb import sqlapi
from cdb.comparch import protocol


class AdjustClassificationUnits(object):
    @staticmethod
    def getUnitsFromImportData():
        data_file = os.path.join(
            os.path.abspath(os.path.dirname(os.path.join(__file__))),
            "data",
            "data.json",
        )

        print("Reading cs_unit data from {} ...".format(data_file))

        with open(data_file, encoding="utf-8") as inputstream:
            classificationData = json.load(inputstream)
        unitDefinitions = classificationData["cs_unit"]["CONTENT"]

        imported_units = {}
        for unitDefinition in unitDefinitions:
            key = unitDefinition["PRIMARY_KEYS"]["cdb_object_id"]
            value = unitDefinition["DATA"]["symbol"]
            imported_units[key] = value

        print("{} cs_unit entries read.\n".format(len(imported_units)))
        return imported_units

    @staticmethod
    def getAvailableUnits():
        print("Retrieving existing cs_unit data from the database ...")

        result = {}
        stmt = """SELECT cdb_object_id, symbol FROM cs_unit"""
        for record in sqlapi.RecordSet2(sql=stmt):
            result[record.symbol] = record.cdb_object_id

        print("{} existing cs_unit entries retrieved.\n".format(len(result)))
        return result

    @staticmethod
    def adjustUnitObjectIds(column_name, table_name, mapping):
        print("Adjusting {} in {} ...".format(column_name, table_name))

        # Get properties with invalid references for unit_object_id
        stmt = """SELECT p.cdb_object_id, p.{column_name}
                  FROM {table_name} p
                  LEFT JOIN cs_unit u ON p.{column_name}=u.cdb_object_id
                  WHERE p.cdb_classname LIKE 'cs_float%' AND p.code LIKE 'cs_materials%' AND
                        p.{column_name} IS NOT NULL AND p.{column_name} <>'' AND u.cdb_object_id IS NULL
            """.format(
            column_name=column_name, table_name=table_name
        )

        # Fix invalid references
        count = 0
        for record in sqlapi.RecordSet2(sql=stmt):
            new_unit_object_id = mapping.get(record.get(column_name))
            if new_unit_object_id:
                protocol.logMessage(
                    "Adjusting {column_name} reference in {table_name} for {cdb_object_id}".format(
                        column_name=column_name,
                        table_name=table_name,
                        cdb_object_id=record.cdb_object_id,
                    )
                )
                stmt = """UPDATE {table_name}
                          SET {column_name}='{new_unit_object_id}'
                          WHERE cdb_object_id='{old_unit_object_id}'""".format(
                    table_name=table_name,
                    column_name=column_name,
                    new_unit_object_id=new_unit_object_id,
                    old_unit_object_id=record.cdb_object_id,
                )

                count += sqlapi.SQL(stmt)

        print("{} records updated.".format(count))

    @staticmethod
    def run():
        # get {symbol: cdb_object_id, ...} of all units available in the system
        availableUnits = AdjustClassificationUnits.getAvailableUnits()

        # get (cdb_object_id: symbol) of all units from classification import data
        unitsForMaterialProperties = AdjustClassificationUnits.getUnitsFromImportData()

        print("Calculating cdb_object_id mapping for inconsistent unit symbols  ...")

        # Create mapping {old_object_id: new_object_id, ...} to map cdb_object_id from classification import
        # data to the cdb_object_id which is actually available in the system for the same symbol
        mapping = {}
        for old_object_id, symbol in unitsForMaterialProperties.items():
            new_object_cid = availableUnits.get(symbol)
            if new_object_cid and new_object_cid != old_object_id:
                print("{}: {} => {}".format(symbol, old_object_id, new_object_cid))
                mapping[old_object_id] = new_object_cid

        # If there are no inconsistencies (all cs_unit cdb_object_ids from the materials classification import
        # are available in the system) then no actions are necessary.
        if not mapping:
            print("No inconsistencies found, all done.")
            return

        print("")
        AdjustClassificationUnits.adjustUnitObjectIds(
            "unit_object_id", "cs_property", mapping
        )
        print("")
        AdjustClassificationUnits.adjustUnitObjectIds(
            "unit_object_id", "cs_class_property", mapping
        )
        print("")
        AdjustClassificationUnits.adjustUnitObjectIds(
            "default_unit_object_id", "cs_class_property", mapping
        )


def main(_):
    AdjustClassificationUnits.run()


if __name__ == "__main__":
    main(sys.argv)
