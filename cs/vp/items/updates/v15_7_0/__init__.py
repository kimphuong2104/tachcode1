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
from cdb.platform.gui import MaskReg
from cdb.platform.mom.operations import OperationConfig
from cdb.util import DBInserter
from cs.web.components.outlet_config import OutletPosition

sml_data_to_restore = defaultdict(list)

class CollectSMLData(object):
    """
    Collects sml default configuration in cs.vp.items.
    """

    def collect_mask_register(self):
        """
        Collects sml mask registers that have been removed in standard configuration.
        """
        mask_registers = [
            {
                "mask_name": "tv_comp",
                "name": "$Facet:sachgruppe",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_c",
                "name": "$Facet:sachgruppe",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_s",
                "name": "tv_sml_search_mask_s",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_s",
                "name": "$Facet:sachgruppe",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_web",
                "name": "tv_sml_search_mask_s",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_web",
                "name": "$Facet:sachgruppe",
                "mask_role_id": "public"
            }
        ]
        for mask_register in mask_registers:
            stmt = """
                SELECT * FROM cdb_mask_reg WHERE mask_name='{mask_name}' AND name='{name}' AND mask_role_id='{mask_role_id}'
            """.format(
                **mask_register
            )
            for record in sqlapi.RecordSet2(sql=stmt):
                mask_register["cdb_module_id"] = record["cdb_module_id"]
                mask_register["ordering"] = record["ordering"]
                mask_register["priority"] = record["priority"]
                mask_register["reg_title"] = record["reg_title"]
                sml_data_to_restore["cdb_mask_reg"].append(mask_register)
                protocol.logMessage("Found mask_register to restore: {}".format(mask_register))

    def run(self):
        self.collect_mask_register()


class RestoreSMLData(object):
    """
    Restores sml default configuration if this has been detected.
    """

    def run(self):
        if "cs" == comparch.get_dev_namespace():
            return
        module = Module.ByKeys('cs.vp.items')
        if not module:
            return
        patching_module_id = module.ModifiablePatchingModuleExt.module_id if module.ModifiablePatchingModuleExt else ""
        for table, recs in sml_data_to_restore.items():
            for rec in recs:
                ins = DBInserter(table)
                if "cdb_module_id" in rec:
                    rec["cdb_module_id"] = patching_module_id
                for col, value in rec.items():
                    ins.add(col, value)
                try:
                    ins.insert()
                    protocol.logMessage(
                        "Restoring SML default configuration: {} - {}".format(table, rec))
                except DBConstraintViolation as e:
                    protocol.logError(
                        "DBConstraintViolation while restoring SML default configuration: {}".format(e))


class RemoveClassificationConfigurationForParts(object):
    """
    Removes the new default configuration for part classification.
    """

    def remove_mask_register(self):
        """
        Removes the classification mask register for part masks.
        """
        mask_regs = [
            {
                "mask_name": "tv_comp_c",
                "name": "cs_classification",
                "ordering": 17,
                "reg_title": "cs_classification",
                "priority": 0,
                "cdb_module_id": "cs.vp.items",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_c",
                "name": "cs_classification_web",
                "ordering": 18,
                "reg_title": "cs_classification",
                "priority": 0,
                "cdb_module_id": "cs.vp.items",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_s",
                "name": "cs_classification",
                "ordering": 17,
                "reg_title": "cs_classification",
                "priority": 0,
                "cdb_module_id": "cs.vp.items",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp_web",
                "name": "cs_classification_web",
                "ordering": 17,
                "reg_title": "cs_classification",
                "priority": 0,
                "cdb_module_id": "cs.vp.items",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp",
                "name": "cs_classification",
                "ordering": 17,
                "reg_title": "cs_classification",
                "priority": 0,
                "cdb_module_id": "cs.vp.items",
                "mask_role_id": "public"
            },
            {
                "mask_name": "tv_comp",
                "name": "cs_classification_web",
                "ordering": 18,
                "reg_title": "cs_classification",
                "priority": 0,
                "cdb_module_id": "cs.vp.items",
                "mask_role_id": "public"
            }
        ]
        for mask_reg in mask_regs:
            for register in MaskReg.KeywordQuery(**mask_reg):
                protocol.logMessage("Removing mask register: {}".format(mask_reg))
                register.Delete()

    def remove_operation_config(self):
        """
        Removes the operation config for classification operations to ensure that the classification
        user exists are not registered.
        """
        op_configs = [
            {
                "name": "cs_classification_multiple_edit",
                "classname": "part",
                "cdb_module_id": "cs.vp.items",
                "ordering": 10,
                "menugroup": 1000
            },
            {
                "name": "cs_classification_object_plan",
                "classname": "part",
                "cdb_module_id": "cs.vp.items",
                "ordering": 241,
                "menugroup": 40
            },
        ]
        for op_config in op_configs:
            for op in OperationConfig.KeywordQuery(**op_config):
                protocol.logMessage("Removing operation config: {}".format(op_config))
                op.Delete()

    def remove_outlet_config(self):
        """
        Removes the outlet config for part detail page.
        """
        outlet_configs = [
            {
                "classname": "part",
                "outlet_name": "object_details",
                "child_name": "cs-classification-web-info",
                "cdb_module_id": "cs.vp.items",
                "pos": 16,
                "priority": 10
            }
        ]
        for outlet_config in outlet_configs:
            for outlet_pos in OutletPosition.KeywordQuery(**outlet_config):
                protocol.logMessage("Removing outlet position: {}".format(outlet_config))
                outlet_pos.Delete()

    def run(self):
        if "cs" == comparch.get_dev_namespace():
            return
        self.remove_mask_register()
        self.remove_operation_config()
        self.remove_outlet_config()


class UpdateIsMBOMTerm(object):

    def run(self):
        """
        Fixes the term of predicate 'cs.vp: Parts (mBOM)' used in access control domain 'cs.vp: Parts (mBOM)'.
        This updated covers two cases:
        1. The term is based on the deprecated is_mbom flag 
        2. The term is based on the new attribute type_object_id but contains an empty expression. 
           With cs.vp 15.7.0 eBOMs are identified by an explicit BOM Type with 
           cdb_object_id af664278-1938-11eb-9e9d-10e7c6454cd1 instead of an empty value.
        
        In both cases the update deletes the existing term and inserts the new one.
        The update also changes the module assignment of the term from cs.vp.bom to cs.vp.items.
        """
        from cdb.comparch import modules
        from cdb.comparch import content

        is_mbom_term = sqlapi.RecordSet2("cdb_term", "predicate_name='cs.vp: Parts (mBOM)' and table_name='teile_stamm'"
                                         " and attribute='is_mbom' and operator='=' and expression='1'")

        type_object_id_term = sqlapi.RecordSet2("cdb_term", "predicate_name='cs.vp: Parts (mBOM)' and table_name='teile_stamm'"
                                                " and attribute='type_object_id' and operator='!=' and expression=''")
        if is_mbom_term or type_object_id_term:
            m = modules.Module.ByKeys('cs.vp.items')
            content_filter = content.ModuleContentFilter(['cdb_term'])
            mc = content.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
            new_term_keys = {"predicate_name": "cs.vp: Parts (mBOM)",
                             "table_name": "teile_stamm",
                             "attribute": "type_object_id",
                             "operator": "!=",
                             "expression": "af664278-1938-11eb-9e9d-10e7c6454cd1"}
            new_term = mc.findItem("cdb_term", **new_term_keys)
            if new_term:
                # Delete old term based on is_mbom attribute
                if is_mbom_term:
                    is_mbom_term[0].delete()
                # Delete term based on type_object_id with empty expression
                if type_object_id_term:
                    type_object_id_term[0].delete()
                # insert new term
                new_term.insertIntoDB()


pre = [CollectSMLData]
post = [RemoveClassificationConfigurationForParts, RestoreSMLData, UpdateIsMBOMTerm]
