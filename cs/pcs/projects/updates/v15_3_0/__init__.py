#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from cdb import cdbuuid, sqlapi
from cdb.comparch import content, modules, protocol
from cdb.platform.acs import RelshipAccessProfile
from cdb.platform.mom.relships import Relship


class UpdateCatalogs:
    def run(self):
        self.update_catalogs()

    def update_catalogs(self):
        self.reset_catalog(
            module_id="cs.pcs.efforts",
            classname="cdbpcs_billable",
            attrs_to_update=["name_de", "name_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.checklists",
            classname="cdbpcs_cl_cat",
            attrs_to_update=["name_de", "name_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.efforts",
            classname="cdbpcs_effort_activity_type",
            attrs_to_update=["name_de", "name_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.efforts",
            classname="cdbpcs_effort_cat",
            attrs_to_update=["name_de", "name_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.issues",
            classname="cdbpcs_iss_cat",
            attrs_to_update=["category_d", "category_uk"],
        )
        self.reset_catalog(
            module_id="cs.pcs.issues",
            classname="cdbpcs_iss_prio",
            attrs_to_update=["priority_d", "priority_uk"],
        )
        self.reset_catalog(
            module_id="cs.pcs.issues",
            classname="cdbpcs_iss_val",
            attrs_to_update=["close_flag_de", "close_flag_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.projects",
            classname="cdbpcs_project_cat",
            attrs_to_update=["name_d", "name_uk"],
        )
        self.reset_catalog(
            module_id="cs.pcs.checklists",
            classname="cdbpcs_rat_val",
            attrs_to_update=["rating_value_de", "rating_value_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.projects",
            classname="cdbpcs_rat_val_lights",
            attrs_to_update=["rating_value_de", "rating_value_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.projects",
            classname="cdbpcs_role_def",
            attrs_to_update=[
                "name_ml_de",
                "name_ml_en",
                "description",
                "description_ml_en",
            ],
        )
        self.reset_catalog(
            module_id="cs.pcs.projects",
            classname="cdbpcs_task_category",
            attrs_to_update=["name_de", "name_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.timeschedule",
            classname="cdbpcs_time_schedule_timerange",
            attrs_to_update=["name_de", "name_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.projects",
            classname="cdbpcs_tr_types",
            attrs_to_update=["name_de", "name_en", "description_de", "description_en"],
        )
        self.reset_catalog(
            module_id="cs.pcs.projects",
            classname="cdbrm_risk_class",
            attrs_to_update=["name_de", "name_en"],
        )

    def reset_catalog(self, module_id, classname, attrs_to_update):
        # load module content
        m = modules.Module.ByKeys(module_id=module_id)
        content_filter = content.ModuleContentFilter([classname])
        mc = content.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

        # update data as defined by module content
        for item in mc.getItems(classname).values():
            rec = item._getPersistentRecord()
            if rec:
                updates = {
                    attr: item.getAttr(attr)
                    for attr in attrs_to_update
                    if not rec[attr]
                }
                if updates:
                    rec.update(**updates)


class UpdateRelshipAccessProfiles:
    def run(self):
        self.update_rs_acc_prof()

    def update_rs_acc_prof(self):
        # cs.pcs.projects
        self._update_rs_acc_prof("Projektaufgaben", "Project Tasks")
        self._update_rs_acc_prof("Aufgabenbeziehungen", "Task Dependencies")

        # cs.pcs.checklists
        self._update_rs_acc_prof("Checklisten", "Checklists")
        self._update_rs_acc_prof("Checkpunkte", "Checklist Items")

        # cs.pcs.timeschedule
        self._update_rs_acc_prof("Terminplanobjekte", "Time schedule objects")

    def _isEquivalent(self, old, new):
        def get_mapping(rs_acc_prof):
            mapping = [dict(x) for x in rs_acc_prof.AccessMapping]
            for x in mapping:
                del x["rs_acc_prof"]
            mapping.sort()
            return mapping

        return old.mandatory == new.mandatory and get_mapping(old) == get_mapping(new)

    def _update_relships(self, old, new):
        Relship.KeywordQuery(rs_acc_prof=old).Update(rs_acc_prof=new)

    def _update_rs_acc_prof(self, old_name, new_name):
        old = RelshipAccessProfile.ByKeys(rs_acc_prof=old_name)
        new = RelshipAccessProfile.ByKeys(rs_acc_prof=new_name)

        if old and new:
            if self._isEquivalent(old, new):
                self._update_relships(old_name, new_name)
                old.Delete()
            else:
                protocol.logWarning(
                    f"cdb_rs_acc_prof '{old_name}' is not equivalent to '{new_name}'. "
                    "Please check its usages manually."
                )


class UpdateChecklistItemsOIDs:
    def run(self):
        try:
            if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
                sqlapi.SQL(
                    "ALTER TABLE cdbpcs_cl_item ADD cdb_object_id VARCHAR2(40) NOT NULL"
                )
            elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
                sqlapi.SQL(
                    "ALTER TABLE cdbpcs_cl_item ADD cdb_object_id VARCHAR(40) NOT NULL"
                )
            elif sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
                sqlapi.SQL(
                    "ALTER TABLE cdbpcs_cl_item ADD cdb_object_id CHAR(40) NOT NULL"
                )
            elif sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
                sqlapi.SQL(
                    "ALTER TABLE cdbpcs_cl_item ADD cdb_object_id CHAR(40) NOT NULL"
                )
        except Exception as e:
            protocol.logMessage(
                msg="Table 'cdbpcs_cl_item' can not or does not need to be altered.",
                details_longtext="The attribute 'cdb_object_id' could not be added"
                f" to the table 'cdbpcs_cl_item'. Column might already exist.\n{e}",
            )

        sqlstr = "SELECT * FROM cdbpcs_cl_item WHERE cdb_object_id = '' OR cdb_object_id IS NULL"
        for r in sqlapi.RecordSet2(table="cdbpcs_cl_item", sql=sqlstr):
            r.update(cdb_object_id=cdbuuid.create_uuid())


pre = [UpdateChecklistItemsOIDs]
post = [UpdateCatalogs, UpdateRelshipAccessProfiles]
