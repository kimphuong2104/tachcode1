#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import sqlapi
from cdb.comparch import protocol
from cdb.sqlapi import SQLdelete
from cdb.transactions import Transaction
from cs.variants.selection_condition import SelectionCondition
from cs.vp.bom import AssemblyComponent
from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence


class MigrateSelectionConditions:
    """
    Migrate old filter rules to selection conditions
    """

    _halt_on_error_ = False

    def run(self):
        filter_rules = sqlapi.RecordSet2("cs_bom_filter_rule")

        with Transaction():
            for each in filter_rules:
                SQLdelete(
                    "FROM cdb_object WHERE id='{0}'".format(each["cdb_object_id"])
                )

                if each["occurrence_id"] is None:
                    reference_object = AssemblyComponent.ByKeys(
                        baugruppe=each["baugruppe"],
                        b_index=each["b_index"],
                        teilenummer=each["teilenummer"],
                        t_index=each["t_index"],
                        position=each["bom_position"],
                        variante=each["variante"],
                    )
                else:
                    reference_object = AssemblyComponentOccurrence.ByKeys(
                        baugruppe=each["baugruppe"],
                        b_index=each["b_index"],
                        teilenummer=each["teilenummer"],
                        t_index=each["t_index"],
                        position=each["bom_position"],
                        variante=each["variante"],
                        occurrence_id=each["occurrence_id"],
                        assembly_path=each["assembly_path"],
                    )

                if reference_object is None:
                    protocol.logError(
                        "Not able to find reference object for filter rule. Skipping filter rule: {0}".format(
                            each.sqlkey()
                        )
                    )
                    continue

                if (
                    reference_object.cdb_object_id is None
                    or reference_object.cdb_object_id == ""
                ):
                    protocol.logError(
                        "Reference object has no cdb_object_id: {0}. Skipping filter rule: {1}".format(
                            reference_object.DBInfo(), each.sqlkey()
                        )
                    )
                    continue

                SelectionCondition.CreateNoResult(
                    cdb_object_id=each["cdb_object_id"],
                    variability_model_id=each["variability_model_id"],
                    ref_object_id=reference_object.cdb_object_id,
                    expression=each["expression"],
                    cdb_cdate=each["cdb_cdate"],
                    cdb_mdate=each["cdb_mdate"],
                    cdb_cpersno=each["cdb_cpersno"],
                    cdb_mpersno=each["cdb_mpersno"],
                )


pre = []
post = [MigrateSelectionConditions]


if __name__ == "__main__":
    MigrateSelectionConditions().run()
