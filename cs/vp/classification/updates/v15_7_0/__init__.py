# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from collections import defaultdict

from cdb import sqlapi
from cdb import comparch
from cdb.comparch import protocol
from cdb.comparch.modules import Module
from cdb.dberrors import DBConstraintViolation
from cdb.util import DBInserter

sml_classification_data_to_restore = defaultdict(list)

class CollectSMLClassificationData(object):
    """
    Collects sml default configuration in cs.vp.classification.
    """

    def collect_operation_owner(self):
        """
        Collects sml operation owner that have been removed in standard configuration.
        """
        op_owners = [
            {
                "name": "cdbsml_oplan",
                "classname": "part",
                "role_id": "public"
            }
        ]
        for op_owner in op_owners:
            stmt = "SELECT * FROM cdb_op_owner WHERE name='{name}' AND classname='{classname}' AND role_id='{role_id}'".format(
                **op_owner
            )
            for record in sqlapi.RecordSet2(sql=stmt):
                op_owner["cdb_module_id"] = record["cdb_module_id"]
                sml_classification_data_to_restore["cdb_op_owner"].append(op_owner)
                protocol.logMessage("Found cdb_op_owner to restore: {}".format(op_owner))

    def collect_tree_owner(self):
        """
        Collects sml tree owner that have been removed in standard configuration.
        """
        artikel_sml_id = "92ad1e2d-2528-11df-b716-e1f861774235"
        produkte_sml_id = "920b08a2-2528-11df-b716-e1f861774235"
        tree_owners = [
            {
                "id": artikel_sml_id,
                "role_id": "public"
            },
            {
                "id": produkte_sml_id,
                "role_id": "Administrator"
            },
            {
                "id": produkte_sml_id,
                "role_id": "SML-Bearbeiter"
            },
        ]
        for tree_owner in tree_owners:
            stmt = "SELECT * FROM cdb_tree_owner WHERE id='{id}' AND role_id='{role_id}'".format(
                **tree_owner
            )
            for record in sqlapi.RecordSet2(sql=stmt):
                tree_owner["cdb_module_id"] = record["cdb_module_id"]
                sml_classification_data_to_restore["cdb_tree_owner"].append(tree_owner)
                protocol.logMessage("Found cdb_op_owner to restore: {}".format(tree_owner))

    def run(self):
        self.collect_operation_owner()
        self.collect_tree_owner()


class RestoreSMLClassificationData(object):
    """
    Restores sml default configuration if this has been detected.
    """

    def run(self):
        if "cs" == comparch.get_dev_namespace():
            return
        module = Module.ByKeys('cs.vp.classification')
        if not module:
            return
        patching_module_id = module.ModifiablePatchingModuleExt.module_id if module.ModifiablePatchingModuleExt else ""
        for table, recs in sml_classification_data_to_restore.items():
            for rec in recs:
                ins = DBInserter(table)
                if "cdb_module_id" in rec:
                    rec["cdb_module_id"] = patching_module_id
                for col, value in rec.items():
                    ins.add(col, value)
                try:
                    ins.insert()
                    protocol.logMessage("Restoring SML default configuration: {} - {}".format(table, rec))
                except DBConstraintViolation as e:
                    protocol.logError("DBConstraintViolation while restoring SML default configuration: {}".format(e))

pre = [CollectSMLClassificationData]
post = [RestoreSMLClassificationData]
