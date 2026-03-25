#!/usr/bin/env python
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module Actions

This is the documentation for the Actions module.
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import logging
from datetime import date

from cdb import fls, sqlapi, ue, util
from cdb.ddl import Table
from cdb.objects import ByID, Forward, Object, Reference_1, Reference_N, State
from cdb.objects.org import WithSubject
from cdb.platform.mom import OperationContext
from cs.audittrail import WithAuditTrail
from cs.currency import Currency
from cs.sharing.share_objects import WithSharing
from cs.tools import powerreports
from cs.web.components import outlet_config
from cs.workflow import briefcases

from cs.actions import misc
from cs.actions.tasks_plugin import ActionWithCsTasks

fAction = Forward(__name__ + ".Action")

__all__ = ["Action"]

project_fields = ["project_name", "cdb_project_id"]
task_fields = ["task_id", "task_name"]

ACTION_STRUCTURE_LICENSE = "ACTIONS_003"


class ActionStatusProtocol(Object):
    __maps_to__ = "cdb_action_prot"
    __classname__ = "cdb_action_prot"


class Action(
    WithSubject,
    briefcases.BriefcaseContent,
    powerreports.WithPowerReports,
    WithSharing,
    ActionWithCsTasks,
    WithAuditTrail,
):

    __maps_to__ = "cdb_action"
    __classname__ = "cdb_action"

    Subactions = Reference_N(fAction, fAction.parent_object_id == fAction.cdb_object_id)
    Parentaction = Reference_1(
        fAction, fAction.cdb_object_id == fAction.parent_object_id
    )
    Currency = Reference_1(Currency, fAction.currency_object_id)

    class EDITING(State):
        status = 0

        def Constraints(state, self):
            return [
                (
                    "MatchStateList",
                    [
                        self.Subactions,
                        [Action.EDITING, Action.DISCARDED],
                        "cdb_action_wf_rej_1",
                    ],
                )
            ]

    class IN_WORK(State):
        status = 20

        def Constraints(state, self):
            return [
                (
                    "MatchStateList",
                    [
                        [self.Parentaction] if self.Parentaction else [],
                        [Action.IN_WORK],
                        "cdb_action_wf_rej_1",
                    ],
                )
            ]

    class DISCARDED(State):
        status = 100

        def FollowUpStateChanges(state, self):
            return [
                (
                    Action.DISCARDED,
                    [a for a in self.Subactions if a.status != Action.DISCARDED.status],
                    0,
                )
            ]

    class FINISHED(State):
        status = 200

        def Constraints(state, self):
            return [
                (
                    "MatchStateList",
                    [
                        self.Subactions,
                        [Action.FINISHED, Action.DISCARDED],
                        "cdb_action_wf_rej_1",
                    ],
                )
            ]

        def post(state, self, ctx):
            if not self.end_time_act:
                self.end_time_act = date.today()

    def setActionId(self, ctx):
        self.id = "%06d" % util.nextval("cdb_action")

    def presetFromRelationship(self, ctx):
        # pylint: disable=too-many-branches
        if ctx.relationship_name:
            if ctx.relationship_name == "cdb_action2subactions":
                parent = Action.ByKeys(ctx.parent.cdb_object_id)
                if parent:
                    if not self.cdb_project_id and parent.cdb_project_id:
                        ctx.set("cdb_project_id", parent.cdb_project_id)
                        if parent.task_id:
                            ctx.set("task_id", parent.task_id)
                    if not self.product_object_id and parent.product_object_id:
                        ctx.set("product_object_id", parent.product_object_id)
                    if not self.teilenummer and parent.teilenummer:
                        ctx.set("teilenummer", parent.teilenummer)
                        if parent.t_index:
                            ctx.set("t_index", parent.t_index)
                    if not self.subject_id and parent.subject_id:
                        ctx.set("subject_id", parent.subject_id)
                        ctx.set("subject_type", parent.subject_type)
                    if parent.currency_object_id:
                        ctx.set("currency_object_id", parent.currency_object_id)
            elif ctx.relationship_name == "cdb_defect2actions":
                from cs.defects import Defect

                defect = Defect.ByKeys(ctx.parent.cdb_object_id)
                if defect:
                    if not self.cdb_project_id and defect.cdb_project_id:
                        ctx.set("cdb_project_id", defect.cdb_project_id)
                    if not self.product_object_id and defect.product_object_id:
                        ctx.set("product_object_id", defect.product_object_id)
                    if not self.teilenummer and defect.teilenummer:
                        ctx.set("teilenummer", defect.teilenummer)
                        if defect.t_index:
                            ctx.set("t_index", defect.t_index)
            elif ctx.relationship_name == "cdbpcs_issue2actions":
                from cs.pcs.issues import Issue

                issue = Issue.ByKeys(
                    cdb_project_id=ctx.parent.cdb_project_id,
                    issue_id=ctx.parent.issue_id,
                )
                if issue:
                    if not self.cdb_project_id and issue.cdb_project_id:
                        ctx.set("cdb_project_id", issue.cdb_project_id)
                        if not self.task_id and issue.task_id:
                            ctx.set("task_id", issue.task_id)
                        if not self.subject_id and issue.subject_id:
                            ctx.set("subject_id", issue.subject_id)
                            ctx.set("subject_type", issue.subject_type)
            elif (
                ctx.relationship_name == "cdbqc_qualitychar2actions"
                and ctx.parent.cdb_object_id
            ):
                self.presetFromQC(ctx.parent.cdb_object_id, ctx)
        elif ctx.superior_operation_context_id:
            octx = OperationContext(ctx.superior_operation_context_id)
            if octx and octx.getClassname() == "cdbqc_action2qc":
                self.presetFromQC(
                    octx.getArgumentValueByName("cdbqc_action2qc.qc_object_id"), ctx
                )

    def presetFromQC(self, qc_object_id, ctx):
        qc = ByID(qc_object_id)
        if qc and qc.cdb_classname == "cdbqc_obj_quality_character":
            f_object = ByID(qc.cdbf_object_id)
            if f_object:
                f_tablename = f_object.GetTableName()
                if f_tablename == "cdbpcs_project":
                    if not self.cdb_project_id and f_object.cdb_project_id:
                        ctx.set("cdb_project_id", f_object.cdb_project_id)
                elif f_tablename == "cdbpcs_task":
                    if (
                        not self.task_id
                        and f_object.cdb_project_id
                        and f_object.task_id
                    ):
                        ctx.set("cdb_project_id", f_object.cdb_project_id)
                        ctx.set("task_id", f_object.task_id)
                        if not self.subject_id and f_object.subject_id:
                            ctx.set("subject_id", f_object.subject_id)
                            ctx.set("subject_type", f_object.subject_type)
                elif f_tablename == "cdbvp_product":
                    if not self.product_object_id and f_object.cdb_object_id:
                        ctx.set("product_object_id", f_object.cdb_object_id)
                        if not self.subject_id and f_object.subject_id:
                            ctx.set("subject_id", f_object.subject_id)
                            ctx.set("subject_type", f_object.subject_type)
                elif f_tablename == "teile_stamm":
                    if not self.teilenummer and f_object.teilenummer:
                        ctx.set("teilenummer", f_object.teilenummer)
                        if f_object.t_index:
                            ctx.set("t_index", f_object.t_index)
                elif f_tablename == "cdbrqm_specification":
                    if not self.product_object_id and f_object.product_object_id:
                        ctx.set("product_object_id", f_object.product_object_id)
                    if not self.cdb_project_id and f_object.cdb_project_id:
                        ctx.set("cdb_project_id", f_object.cdb_project_id)
                elif f_tablename == "cdbrqm_spec_object":
                    if not self.product_object_id and f_object.Specification:
                        ctx.set(
                            "product_object_id",
                            f_object.Specification.product_object_id,
                        )
                    if not self.cdb_project_id and f_object.Specification:
                        ctx.set("cdb_project_id", f_object.Specification.cdb_project_id)

    def presetCurrency(self, ctx):
        if not self.currency_object_id:
            dft_curr = Currency.getDefaultCurrency()
            if dft_curr:
                self.currency_object_id = dft_curr.cdb_object_id

    def checkCurrency(self, ctx):
        if self.cost:
            self.presetCurrency(ctx)

    def set_read_only(self, ctx):
        if (
            "cdb_project_id" in ctx.dialog.get_attribute_names()
            and "project_name" in ctx.dialog.get_attribute_names()
        ):
            if ctx.dialog.cdb_project_id and ctx.dialog.project_name:
                ctx.set_writeable("task_id")
                ctx.set_writeable("task_name")
            else:
                ctx.set_readonly("task_id")
                ctx.set_readonly("task_name")

    def checkResponsible(self, ctx):
        subject_id = self.subject_id
        subject_type = self.subject_type
        cdb_project_id = self.cdb_project_id

        if subject_type == "PCS Role":
            if not cdb_project_id:
                raise ue.Exception("cdbpcs_invalid_resp")

            team_data = sqlapi.RecordSet2(
                "cdb_action_resp_brows",
                "cdb_project_id = '{}' "
                "AND subject_id = '{}' "
                "AND subject_type = '{}'".format(
                    sqlapi.quote(cdb_project_id),
                    sqlapi.quote(subject_id),
                    sqlapi.quote(subject_type),
                ),
            )

            if not bool(team_data):
                raise ue.Exception("cdbpcs_invalid_resp")

    def setRelshipFieldsReadOnly(self, ctx):
        if not misc.is_installed("cs.pcs"):
            ctx.set_fields_readonly(project_fields + task_fields)
            return

        if ctx.relationship_name == "cdbpcs_project2actions":
            ctx.set_fields_readonly(project_fields)
        elif ctx.relationship_name in ["cdbpcs_task2actions", "cdbpcs_issue2actions"]:
            ctx.set_fields_readonly(project_fields + task_fields)

    def checkPartReference(self, ctx):
        # E073879: Ensure Reference between Part and Action is correct in all cases
        from cdb.comparch.packages import Package

        vp_pkg = Package.ByKeys(name="cs.vp")
        # only if cs.vp is installed
        if vp_pkg:
            # check if both ways of referencing (via teilenummer/t_index, via part_object_id)
            # are set and add one via SQL if it is missing
            if not (self.teilenummer and self.part_object_id):
                # Note: Importing only cs allows it to be patched during tests
                import cs

                Item = cs.vp.items.Item
                if self.teilenummer:
                    items = Item.KeywordQuery(
                        teilenummer=self.teilenummer, t_index=self.t_index
                    )
                    if items:
                        sqlapi.SQLupdate(
                            "cdb_action SET part_object_id='{}' WHERE cdb_object_id='{}'".format(
                                items[0].cdb_object_id, self.cdb_object_id
                            )
                        )
                else:
                    items = Item.KeywordQuery(cdb_object_id=self.part_object_id)
                    if items:
                        item = items[0]
                        sqlapi.SQLupdate(
                            """cdb_action
                                SET teilenummer='{}'
                                    AND t_index='{}'
                                WHERE cdb_object_id='{}'
                            """.format(
                                item.teilenummer, item.t_index, self.cdb_object_id
                            )
                        )

    event_map = {
        (("create", "copy"), "pre"): "setActionId",
        (("copy", "create"), "pre_mask"): "presetFromRelationship",
        (("create"), "pre_mask"): ("setRelshipFieldsReadOnly"),
        (("copy", "create", "modify"), "pre_mask"): ("presetCurrency", "set_read_only"),
        (("copy", "create", "modify"), "pre"): ("checkCurrency", "checkResponsible"),
        (("copy", "create", "modify"), "post"): ("checkPartReference"),
        (("create", "copy", "modify"), "dialogitem_change"): "set_read_only",
    }


def _retrieve_languages(classname, field_name):
    # It seems to be a problem to access the cdb.objects
    # classes at the very first time by using something like
    # CommonRole.name.getLanguageFields().keys()
    from cdb.platform.mom.fields import DDMultiLangFieldBase

    ml_field = DDMultiLangFieldBase.ByKeys(classname, field_name)
    if ml_field:
        return [fld.cdb_iso_language_code for fld in ml_field.LangFields]
    else:
        return []


def _generate_select(
    iso_langs, view_attr, src_classname, src_attrname, src_alias, fallback="''"
):
    """
    :param isolangs:
      The ISO language codes for the attributes to generate
    :param view_attr:
      The name of the multilanguage attribute in the view.
    :param src_classname:
      The name of the class where the data is retrieved
    :param src_attrname:
      The name of the attribute where the data is retrieved
    :src_alias:
      The alias name of the source class in the view
    :fallback:
      Value that is used if there is no attribute for an iso lang
      in the source
    """
    from cdb.platform.mom.fields import DDField, DDMultiLangFieldBase

    alias = "{}.".format(src_alias) if src_alias else ""
    result = []
    target_field = None
    if src_attrname:
        target_field = DDField.ByKeys(src_classname, src_attrname)
    for iso_lang in iso_langs:
        fld = None
        if target_field:
            if isinstance(target_field, DDMultiLangFieldBase):
                language_fields = target_field.LangFields
                language_fields_iso_code = language_fields.cdb_iso_language_code
                language_fields_names = language_fields.field_name
                # Find the specific language
                if iso_lang in language_fields_iso_code:
                    fld = language_fields_names[
                        language_fields_iso_code.index(iso_lang)
                    ]
            else:
                fld = target_field.field_name  # noqa: F812

        result.append((fld, iso_lang))
    return "".join(
        [
            ", {} AS {}_{}".format(
                "{}{}".format(alias, fld) if fld else fallback, view_attr, lang
            )
            for fld, lang in result  # noqa: F812
        ]
    )


def _generate_resp_sql(collate, active=False):
    active_str = ""
    if active:
        active_str = "active_account='1' and visibility_flag=1 and"

    global_role_langs = _retrieve_languages("cdb_global_role", "name")
    proj_role_langs = _retrieve_languages("cdbpcs_role_def", "name_ml")

    t = Table("cdbpcs_prj_role")
    if t.exists():
        role_langs = list(set(global_role_langs).intersection(proj_role_langs))
    else:
        role_langs = global_role_langs

    select_global = _generate_select(
        role_langs, "subject_name", "cdb_global_role", "name", "gr"
    )
    select_angestellter = _generate_select(
        role_langs, "subject_name", "cdb_person", "name", "angestellter"
    )
    select_pcs = _generate_select(
        role_langs, "subject_name", "cdbpcs_role_def", "name_ml", "rdef"
    )

    STATIC_ANGESTELLTER = """
        SELECT
            angestellter.personalnummer AS subject_id,
            'Person' {collation} AS subject_type
            {select_angestellter},
            '' {collation} AS cdb_project_id,
            1 AS order_by
        FROM angestellter
        WHERE {active_str}
            (is_system_account=0 OR is_system_account IS NULL)""".format(
        collation=collate,
        select_angestellter=select_angestellter,
        active_str=active_str,
    )

    STATIC_GLOBAL = """
        UNION SELECT
            gr.role_id  AS subject_id,
            'Common Role' {collation} AS subject_type
            {select_global},
            '' {collation} AS cdb_project_id,
            2 AS order_by
        FROM cdb_global_role gr
        WHERE is_org_role = 1 """.format(
        collation=collate, select_global=select_global
    )

    # All Roles with project
    STATIC_PCS = """
        UNION SELECT
            prj_role.role_id AS subject_id,
            'PCS Role' {collation} AS subject_type
            {select_pcs},
            prj_role.cdb_project_id AS cdb_project_id,
            3 AS order_by
        FROM cdbpcs_role_def rdef, cdbpcs_prj_role prj_role
        WHERE prj_role.role_id=rdef.name""".format(
        collation=collate, select_pcs=select_pcs
    )

    # All project roles without specific project
    STATIC_PCS1 = """
        UNION SELECT
            rdef.name AS subject_id,
            'PCS Role' {collation} AS subject_type
            {select_pcs},
            '' {collation} AS cdb_project_id,
            4 AS order_by
        FROM cdbpcs_role_def rdef""".format(
        collation=collate, select_pcs=select_pcs
    )

    # Person with project
    STATIC_PCS2 = """
        UNION SELECT
            s.subject_id AS subject_id,
            s.subject_type {collation} AS subject_type
            {select_angestellter},
            s.cdb_project_id {collation} AS cdb_project_id,
            5 AS order_by
        FROM angestellter, cdbpcs_subject s
        WHERE
            s.subject_id = angestellter.personalnummer
            AND s.subject_type = 'Person'
            AND (angestellter.is_system_account=0 or angestellter.is_system_account is null)""".format(
        collation=collate, select_angestellter=select_angestellter
    )

    PARTS = [STATIC_ANGESTELLTER, STATIC_GLOBAL]
    if t.exists():
        PARTS += [STATIC_PCS, STATIC_PCS1, STATIC_PCS2]
    return " ".join(PARTS)


def generate_cdb_action_resp_brows():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        collate = " COLLATE %s " % CollationDefault.get_default_collation()
    else:
        collate = ""
    return _generate_resp_sql(collate, True)


def generate_cdb_action_resp_brows_all():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        collate = " COLLATE %s " % CollationDefault.get_default_collation()
    else:
        collate = ""
    return _generate_resp_sql(collate, False)


class ActionStructureOutletCallback(outlet_config.OutletPositionCallbackBase):
    """
    If the action structure  feature is not licensed in the system, this callback
    will not show the tab of the ActionStructure (e.g. return an empty list).
    """

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        if not fls.is_available(ACTION_STRUCTURE_LICENSE):
            logging.warning("Missing license feature %s", ACTION_STRUCTURE_LICENSE)
            # do not show tab if action structure overview is not licensed
            return []
        return [pos_config]


if __name__ == "__main__":
    pass
