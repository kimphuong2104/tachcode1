#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import functools

from cdb import sqlapi, util
from cdb.comparch import updutils


class DataMigrations:
    def run(self):
        # use a new property to determine whether the update
        # needs to run
        rset = sqlapi.RecordSet2("cdb_prop", "attr='rpda'")
        if len(rset) > 0:
            return

        self.upd_SL000_120531_pcs3_conf_changes_1()
        self.upd_SL000_120531_pcs3_conf_changes_3_adjust_data()
        self.upd_SL000_120531_pcs3_conf_changes_4_adjust_data()
        self.upd_SL000_120601_organizations_resource_browsable()
        self.upd_SL000_120607_pcs3_bugfixes()
        self.upd_SL000_120726_i18n_checklists()
        self.upd_SL000_120802_i18n_issues()
        self.upd_SL000_120929_sorting_cl_items()
        self.upd_SL000_130213_pcs_add_sync_to_project_ctx()

        # FIXME: from upd-SL000-130129-pcs_masks_manual_lights.py
        # "* FROM cdb_pyterm where name='cdbpcs: Task Panel Objects' and
        # fqpyname='cs.pcs.projects.tasks.Task' and predicate_name='Aufgaben mit
        # Ressourcenzuweisungen' and attribute='is_group'",
        # "* FROM cdb_pyterm where name='cdbpcs: TimeSheet: Bookable Tasks (All/All)' and
        # fqpyname='cs.pcs.projects.tasks.Task' and
        # predicate_name='cdbpcs: TimeSheet: Bookable Tasks (All/All)' and attribute='is_group'",
        # "* FROM cdb_pyterm where name='ccdbpcs: TimeSheet: Bookable Tasks (All/Open)'
        # and fqpyname='cs.pcs.projects.tasks.Task' and
        # predicate_name='cdbpcs: TimeSheet: Bookable Tasks (All/Open)' and attribute='is_group'",
        # "* FROM cdb_pyterm where name='cdbpcs: TimeSheet: Bookable Tasks (Mine/All)'
        # and fqpyname='cs.pcs.projects.tasks.Task' and attribute='is_group'",
        # "* FROM cdb_pyterm where name='cdbpcs: TimeSheet: Bookable Tasks (Mine/Open)' and
        # fqpyname='cs.pcs.projects.tasks.Task' and attribute='is_group'"

    # ----  upd_SL000_130213_pcs_add_sync_to_project_ctx ----

    def upd_SL000_130213_pcs_add_sync_to_project_ctx(self):
        i = util.DBInserter("cdb_org_ctxattr")
        i.add("context_name", "ProjectContext")
        i.add("relation", "cdbpcs_sync_constraint")
        i.add("context_attr", "cdb_project_id")
        i.add("cdb_module_id", "cs.pcs.synchrolinks")
        i.insert()

    # ---- upd_SL000_120531_pcs3_conf_changes_1 ----

    def upd_SL000_120531_pcs3_conf_changes_1(self):

        new_props = [
            ("rpda", "demand"),
            ("rpdv", "values"),
            ("rpld", "true"),
            ("rprm", "true"),
            ("tpld", "true"),
            ("tp00", "0x444444"),
            ("tp01", "0xffffff"),
            ("tp02", "0xff0000"),
            ("tp03", "0x404040"),
            ("tp04", "0xaa8811"),
            ("tp05", "0x404040"),
            ("tp06", "0x47630c"),
            ("tp07", "0xffffff"),
            ("tp08", "0x93a76b"),
            ("tp09", "0x404040"),
            ("tp10", "0xd3e7ab"),
            ("tp11", "0x404040"),
            ("tp12", "0xdddddd"),
            ("tp13", "0x404040"),
            ("tp14", "0xff0000"),
            ("tp15", "0xffffff"),
            ("tp16", "0xaa8811"),
            ("tp17", "0x404040"),
            ("tp18", "0x47630c"),
            ("tp19", "0xffffff"),
            ("tp20", "0x93a76b"),
            ("tp21", "0x404040"),
            ("tp22", "0xd3e7ab"),
            ("tp23", "0x404040"),
            ("tp24", "0xdddddd"),
        ]
        for prop, value in new_props:
            updutils.initialize_prop(prop, value, "cs.pcs.resources")

        sqlstr = "cdbpcs_prj_demand SET resource_type = 'manpower'"
        sqlapi.SQLupdate(sqlstr)
        sqlstr = (
            " SET start_time_fcast=start_time_plan, end_time_fcast=end_time_plan,"
            "effort_plan=effort_fcast,"
            "status_time_fcast=1,status_effort_fcast=1"
        )
        sqlapi.SQLupdate("cdbpcs_task" + sqlstr)
        sqlapi.SQLupdate("cdbpcs_project" + sqlstr)

    # ---- upd_SL000_120531_pcs3_conf_changes_3_adjust_data ----

    def upd_SL000_120531_pcs3_conf_changes_3_adjust_data(self):
        from cs.pcs.projects.tasks import Task

        openTasks = Task.Query("status IN (0, 20, 50)")
        for t in openTasks:
            if hasattr(t, "adjustAllocations"):
                t.adjustAllocations()
        self._updateProjects()

    def _updateProjects(self):
        from cs.pcs.projects import Project

        sqlapi.SQLupdate("cdbpcs_project SET effort_fcast_d=0.0, effort_fcast_a=0.0")
        sqlapi.SQLupdate("cdbpcs_task SET effort_fcast_d=0.0, effort_fcast_a=0.0")
        cond0 = (
            "cdb_project_id IN (SELECT DISTINCT cdb_project_id FROM cdbpcs_prj_demand)"
        )
        cond1 = (
            "cdb_project_id IN (SELECT DISTINCT cdb_project_id FROM cdbpcs_prj_alloc)"
        )
        ps = Project.Query(cond0 + " OR " + cond1)
        for p in ps:
            tasks = p.TasksByParentTask[""]
            for t in tasks:
                self._updateTask(t)
            my_effort_fcast_d = functools.reduce(
                lambda a, b: a + b, [x.getDemandForeCast() for x in tasks], 0.0
            )
            my_effort_fcast_a = functools.reduce(
                lambda a, b: a + b, [x.getAssignmentForeCast() for x in tasks], 0.0
            )
            p.Update(effort_fcast_d=my_effort_fcast_d, effort_fcast_a=my_effort_fcast_a)

    def _updateTask(self, task):
        my_effort_fcast_d = task.assignedDemands("hours")
        my_effort_fcast_a = task.assignedResources("hours")
        for t in task.OrderedSubTasks:
            self._updateTask(t)
        if len(task.OrderedSubTasks):
            my_effort_fcast_d += functools.reduce(
                lambda a, b: a + b,
                [x.getDemandForeCast() for x in task.OrderedSubTasks],
                0.0,
            )
            my_effort_fcast_a += functools.reduce(
                lambda a, b: a + b,
                [x.getAssignmentForeCast() for x in task.OrderedSubTasks],
                0.0,
            )
        task.Update(effort_fcast_d=my_effort_fcast_d, effort_fcast_a=my_effort_fcast_a)

    # ---- upd_SL000_120531_pcs3_conf_changes_4_adjust_data ----

    def upd_SL000_120531_pcs3_conf_changes_4_adjust_data(self):
        from cs.pcs.resources import RessourceAssignment, RessourceDemand

        objs = sqlapi.RecordSet2(RessourceDemand.GetTableName())
        for o in objs:
            RessourceDemand.updateScheduleViews(o)

        objs = sqlapi.RecordSet2(RessourceAssignment.GetTableName())
        for o in objs:
            RessourceAssignment.updateScheduleViews(o)

    # ---- upd_SL000_120601_organizations_resource_browsable ----

    def upd_SL000_120601_organizations_resource_browsable(self):
        from cdb.objects.org import Organization

        # pylint: disable=unused-import
        from cs.pcs.resources import (  # noqa; required to activate classbody with relship Organization.Resources
            org_extensions,
        )

        toplevel_organizations = Organization.Query(
            "is_resource_browsable IS NULL and org_id_head=''"
        )
        for organization in toplevel_organizations:
            if self.contains_resources_recursive(organization):
                organization.is_resource_browsable = 1
            else:
                organization.is_resource_browsable = 0

    def contains_resources_recursive(self, organization):
        """
        Check organization whether it is a resource already
        Check corresponding suborganizations recursive
        Note: organizations are browsable resources when is_resource=1 or they
              have direct or recursive resource children employees/suborganizations
        """
        if organization.is_resource or len(organization.Resources):
            return True
        for suborganization in organization.SubOrganizations:
            if self.contains_resources_recursive(suborganization):
                return True
        return False

    # ---- upd_SL000_120607_pcs3_bugfixes ----

    def upd_SL000_120607_pcs3_bugfixes(self):
        constr0 = len(sqlapi.RecordSet2("cdbpcs_sync_con_type", "type_id = 0"))
        constr1 = len(sqlapi.RecordSet2("cdbpcs_sync_con_type", "type_id = 1"))

        if not constr0:
            cons0 = sqlapi.Record(
                "cdbpcs_sync_con_type",
                type_id=0,
                name_de="Aufgabe beendet vor Termin",
                name_en="Task finished before target date",
                cdb_object_id="211f3acf-abe9-11e1-ab43-00248c9e4be2",
            )
            cons0.insert()

        if not constr1:
            cons1 = sqlapi.Record(
                "cdbpcs_sync_con_type",
                type_id=1,
                name_de="Aufgabe startet nach Termin",
                name_en="Task start after target date",
                cdb_object_id="2a7c3ba2-abe9-11e1-bc30-00248c9e4be2",
            )
            cons1.insert()

    # ---- upd_SL000_120726_i18n_checklists ----

    def upd_SL000_120726_i18n_checklists(self):
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='1', rating_value_en='1', rating_value_cs='1', rating_value_es='1', rating_value_fr='1', rating_value_it='1', rating_value_pl='1', rating_value_pt='1', rating_value_tr='1' WHERE name='GermanSchoolmarks' AND rating_id='1'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='2', rating_value_en='2', rating_value_cs='2', rating_value_es='2', rating_value_fr='2', rating_value_it='2', rating_value_pl='2', rating_value_pt='2', rating_value_tr='2' WHERE name='GermanSchoolmarks' AND rating_id='2'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='3', rating_value_en='3', rating_value_cs='3', rating_value_es='3', rating_value_fr='3', rating_value_it='3', rating_value_pl='3', rating_value_pt='3', rating_value_tr='3' WHERE name='GermanSchoolmarks' AND rating_id='3'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='4', rating_value_en='4', rating_value_cs='4', rating_value_es='4', rating_value_fr='4', rating_value_it='4', rating_value_pl='4', rating_value_pt='4', rating_value_tr='4' WHERE name='GermanSchoolmarks' AND rating_id='4'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='5', rating_value_en='5', rating_value_cs='5', rating_value_es='5', rating_value_fr='5', rating_value_it='5', rating_value_pl='5', rating_value_pt='5', rating_value_tr='5' WHERE name='GermanSchoolmarks' AND rating_id='5'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='6', rating_value_en='6', rating_value_cs='6', rating_value_es='6', rating_value_fr='6', rating_value_it='6', rating_value_pl='6', rating_value_pt='6', rating_value_tr='6' WHERE name='GermanSchoolmarks' AND rating_id='6'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='nicht bewertet', rating_value_en='unrated', rating_value_cs='ne hodnotit', rating_value_es='sin clasificar', rating_value_fr='non class�', rating_value_it='senza valutazione', rating_value_pl='nie oceniono', rating_value_pt='n�o classificado', rating_value_tr='oylanmamis' WHERE name='GermanSchoolmarks' AND rating_id='clear'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='nicht relevant', rating_value_en='not relevant', rating_value_cs='irelevantn�', rating_value_es='irrelevante', rating_value_fr='pertinence', rating_value_it='irrilevante', rating_value_pl='nieistotny', rating_value_pt='irrelevante', rating_value_tr='ilgisiz' WHERE name='GermanSchoolmarks' AND rating_id='nicht_relevant'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='gelb', rating_value_en='yellow', rating_value_cs='zlut�', rating_value_es='amarillo', rating_value_fr='jaune', rating_value_it='giallo', rating_value_pl='z�tty', rating_value_pt='amarelo', rating_value_tr='sari' WHERE name='RedGreenYellow' AND rating_id='gelb'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='gr�n', rating_value_en='green', rating_value_cs='zelen�', rating_value_es='verde', rating_value_fr='verde', rating_value_it='verde', rating_value_pl='zielony', rating_value_pt='verde', rating_value_tr='yesil' WHERE name='RedGreenYellow' AND rating_id='gruen'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='rot', rating_value_en='red', rating_value_cs='cerven�', rating_value_es='rojo', rating_value_fr='rouge', rating_value_it='rosso', rating_value_pl='czerwony', rating_value_pt='vermelho', rating_value_tr='kirmizi' WHERE name='RedGreenYellow' AND rating_id='rot'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='nicht relevant', rating_value_en='not relevant', rating_value_cs='irelevantn�', rating_value_es='irrelevante', rating_value_fr='pertinence', rating_value_it='irrilevante', rating_value_pl='nieistotny', rating_value_pt='irrelevante', rating_value_tr='ilgisiz' WHERE name='RedGreenYellow' AND rating_id='nicht_relevant'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET rating_value_de='nicht bewertet', rating_value_en='unrated', rating_value_cs='ne hodnotit', rating_value_es='sin clasificar', rating_value_fr='non class�', rating_value_it='senza valutazione', rating_value_pl='nie oceniono', rating_value_pt='n�o classificado', rating_value_tr='oylanmamis' WHERE name='RedGreenYellow' AND rating_id='clear'"  # noqa
        )

    # ---- upd_SL000_120802_i18n_issues ----

    def upd_SL000_120802_i18n_issues(self):
        sqlapi.SQLupdate(
            "cdbpcs_iss_cat SET category_d='Frage', category_uk='Question', category_s='Pregunta', category_f='Question', category_i='Domanda' WHERE category='Frage'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_cat SET category_d='Korrektur', category_uk='Correction', category_s='Correcci�n', category_f='Correction', category_i='Correzione' WHERE category='Korrektur'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_cat SET category_d='Zusatz', category_uk='Addition', category_s='Aditivo', category_f='Additif', category_i='Additivo' WHERE category='Zusatz'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_cat SET category_d='offen', category_uk='open', category_s='abrir', category_f='ouvrir', category_i='aprire' WHERE category='offen'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_cat SET category_d='zu vervollst�ndigen', category_uk='to complete', category_s='para completar', category_f='� remplir', category_i='per completare' WHERE category='zu vervollst�ndigen'"  # noqa
        )

        sqlapi.SQLupdate(
            "cdbpcs_iss_prio SET priority_d='hoch', priority_uk='high', priority_s='alto', priority_f='haut', priority_i='alto' WHERE priority='hoch'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_prio SET priority_d='kritisch', priority_uk='critical', priority_s='critico', priority_f='critique', priority_i='critico' WHERE priority='kritisch'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_prio SET priority_d='niedrig', priority_uk='low', priority_s='bajo', priority_f='faible', priority_i='basso' WHERE priority='niedrig'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_prio SET priority_d='normal', priority_uk='normal', priority_s='normal', priority_f='normal', priority_i='normale' WHERE priority='normal'"  # noqa
        )
        sqlapi.SQLupdate(
            "cdbpcs_iss_prio SET priority_d='offen', priority_uk='open', priority_s='abrir', priority_f='ouvrir', priority_i='aprire' WHERE priority='offen'"  # noqa
        )

    # ---- upd_SL000_120929_sorting_cl_items ----

    def upd_SL000_120929_sorting_cl_items(self):
        from cs.pcs.checklists import Checklist

        pos_val = 10
        s = """SELECT * FROM cdbpcs_checklst"""
        rs = sqlapi.RecordSet2(sql=s)
        i = 0
        if rs and len(rs):
            while i < len(rs):
                clist = Checklist.ByKeys(
                    checklist_id=rs[i].checklist_id, cdb_project_id=rs[i].cdb_project_id
                )
                cl_items = clist.ChecklistItems
                for cl_item in cl_items:
                    pos = cl_item.position
                    if not pos:
                        cl_item.position = pos_val
                    pos_val += 10
                i += 1
                pos_val = 10

    # ----------------------------------------------------------


pre = []
post = [DataMigrations]
