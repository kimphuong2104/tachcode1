#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# vim: set fileencoding=latin1 :
# -*- Python -*-
# $Id$
# CDB:Browse
# Copyright (C) 1990 - 2007 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     ecm.py
# Author:   aki
# Creation: 07.02.07
# Purpose:

# pylint: disable-msg=R0904

from cdb import ue
from cdb import sqlapi
from cdb import version
from cdb.classbody import classbody
from cdb.ddl import Table
from cdb.objects import Object
from cdb.objects import Reference_N
from cdb.objects import Reference_1
from cdb.objects import Forward
from cdb.objects import ReferenceMethods_N
from cdb.objects import ReferenceMapping_N
from cdb.objects import LocalizedField
from cdb.objects import org
from cdb.objects import Rule
from cdb.platform import acs
from cdb.platform import gui
from cdb.platform import FolderContent

from cs.workflow import processes
from cs.workflow import tasks
from cs.workflow import systemtasks
from cs.workflow import briefcases
from cs.sharing.share_objects import WithSharing

fEngineeringChange = Forward(__name__ + ".EngineeringChange")
fTemplateProcessReference = Forward(__name__ + ".TemplateProcessReference")
fRuleReference = Forward(__name__ + ".RuleReference")
fProcessReference = Forward(__name__ + ".ProcessReference")

from cdb import i18n


def _get_pydate_format(_format):
    # Workaround for E032998
    import re

    conversions = [
        ("YYYY", "%Y"),
        ("MM", "%m"),
        ("DD", "%d"),
        ("hh", "%H"),
        ("mm", "%M"),
        ("ss", "%S")
    ]

    result = _format
    for wrong, right in conversions:
        result = re.sub(wrong, right, result)
    return result


def get_pydate_format():
    return _get_pydate_format(i18n.get_date_format())


def get_pydatetime_format():
    return _get_pydate_format(i18n.get_datetime_format())


def generate_cdbec_resp_brows():

    def get_languages(classname, field_name):
        from cdb.platform.mom.fields import DDMultiLangFieldBase
        ml_field = DDMultiLangFieldBase.ByKeys(classname, field_name)
        return set([fld.cdb_iso_language_code for fld in ml_field.LangFields])

    def format_columns(
        languages, target_field_name, source_field_name, source_field_postfix='', de_without_postfix=False
    ):
        cols = ""
        for lang in languages:
            if source_field_postfix:
                if de_without_postfix and "de" == lang:
                    source_column = source_field_name
                else:
                    source_column = "{}{}{}".format(source_field_name, source_field_postfix, lang)
            else:
                source_column = source_field_name
            cols = cols + ", {} AS {}_{}".format(
                source_column, target_field_name, lang
            )
        return cols

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault
        collate = " COLLATE %s " % CollationDefault.get_default_collation()
    else:
        collate = ""

    t = Table('cdbpcs_prj_role')
    with_prj_role = t.exists()

    if with_prj_role:
        name_langs = get_languages("cdb_global_role", "name").intersection(
            get_languages("cdbpcs_role_def", "name_ml")
        )
        description_languages = get_languages("cdb_global_role", "description_ml").intersection(
            get_languages("cdbpcs_role_def", "description_ml")
        )
    else:
        name_langs = get_languages("cdb_global_role", "name")
        description_languages = get_languages("cdb_global_role", "description_ml")

    STATIC_PART = (
        "SELECT personalnummer AS subject_id {person_description_cols}"
        ", 'Person' {collate} AS subject_type {person_name_cols}"
        ", '' AS cdb_project_id, 1 AS order_by"
        " FROM angestellter WHERE active_account='1' and visibility_flag='1'"
        " UNION"
        " SELECT role_id AS subject_id {role_description_cols}"
        ", 'Common Role' {collate} AS subject_type {role_name_cols}"
        ", '' AS cdb_project_id, 2 AS order_by"
        " FROM cdb_global_role where is_org_role = 1").format(
        collate=collate,
        person_description_cols=format_columns(description_languages, 'description', 'name'),
        person_name_cols=format_columns(name_langs, 'subject_name', 'name'),
        role_description_cols = format_columns(description_languages, 'description', 'description', '_ml_', True),
        role_name_cols = format_columns(name_langs, 'subject_name', 'name', '_')
    )

    if with_prj_role:
        PCS_PART = (
            " UNION"
            " SELECT p.role_id AS subject_id {prj_role_description_cols}"
            ", 'PCS Role' {collate} AS subject_type {prj_role_name_cols}"
            ", p.cdb_project_id AS cdb_project_id, 3 AS order_by"
            " FROM cdbpcs_prj_role p, cdbpcs_role_def d"
            " WHERE p.role_id = d.name"
        ).format(
            collate=collate,
            prj_role_description_cols = format_columns(description_languages, 'description', 'd.description', '_ml_', True),
            prj_role_name_cols = format_columns(name_langs, 'subject_name', 'd.name', '_ml_', )
        )
        return (STATIC_PART + PCS_PART)
    else:
        return STATIC_PART


class ECCategory(Object):
    __maps_to__ = "cdbecm_ec_categ"

    Name = LocalizedField("name")


class EngineeringChange(org.WithSubject, briefcases.BriefcaseContent, WithSharing):
    __maps_to__ = "cdbecm_ec"
    __classname__ = "cdbecm_ec"
    __wf__access_profile__ = "cdbecm_assign_rights"

    process_briefcase_map = {"ECR": (lambda self: [self]),
                             "ECO": (lambda self: [self])}

    ProcessTemplateReferencesByState = ReferenceMapping_N(fTemplateProcessReference,
                                                          fTemplateProcessReference.cdb_ec_id == fEngineeringChange.cdb_ec_id,
                                                          indexed_by=fTemplateProcessReference.start_state)

    ProcessTemplateReferences = Reference_N(fTemplateProcessReference,
                                            fTemplateProcessReference.cdb_ec_id == fEngineeringChange.cdb_ec_id)

    ProcessReferences = Reference_N(fProcessReference,
                                    fProcessReference.cdb_ec_id == fEngineeringChange.cdb_ec_id)

    RuleReferences = Reference_N(fRuleReference, fRuleReference.cdb_ec_id == fEngineeringChange.cdb_ec_id)
    Template = Reference_1(fEngineeringChange, fEngineeringChange.template_ec_id)

    Category = Reference_1(ECCategory, fEngineeringChange.category)

    # Briefcases in which self is contained
    def _getBriefcases(self):
        briefcase_ids = FolderContent.KeywordQuery(cdb_content_id=self.cdb_object_id).cdb_folder_id

        bfcs = briefcases.Briefcase.Query(briefcases.Briefcase.cdb_object_id.one_of(*briefcase_ids))
        return bfcs

    Briefcases = ReferenceMethods_N(briefcases.Briefcase, _getBriefcases)

    @classmethod
    def registerManagedProcessBriefcase(cls, briefcase_name, ec_obj_relship):
        cls.process_briefcase_map[briefcase_name] = (lambda obj: ec_obj_relship.get_referenced(obj))

    @classmethod
    def allow(cls, obj, ec):
        """ Checks whether the EC is suitable for the given object.
        Raises exception with possible ec templates listet, if not.
        EC can be None, to check whether the given object requires an ec assignment."""
        allow = True
        valid_names = []
        for t in EngineeringChange.KeywordQuery(template=1):
            for ref in t.RuleReferences:
                if ref.Rule and obj.MatchRule(ref.Rule):
                    valid_names.append(t.title)
                    if ec and ec.template_ec_id == t.cdb_ec_id:
                        return
                    else:
                        allow = False
        if not allow:
            if ec:
                # ec does not match
                raise ue.Exception("cdbecm_err_match", "\n,".join(valid_names))
            else:
                # ec required but missing
                raise ue.Exception("cdbecm_err_match2", "\n,".join(valid_names))

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = super(EngineeringChange, self).GetDisplayAttributes()
        results["attrs"].update({"heading": str(self.ToObjectHandle().mapped_category_name)})
        return results

    @staticmethod
    def ApplyDefaultsFromEC(change_notice, ctx=None):

        if not change_notice.EC or not hasattr(change_notice, "ECDefaultsMap"):
            return
        upd_dict = {}
        for source_attr, target_attr in change_notice.ECDefaultsMap.items():
            if not change_notice[target_attr]:
                if ctx:
                    ctx.set(target_attr, change_notice.EC[source_attr])
                else:
                    upd_dict[target_attr] = change_notice.EC[source_attr]
        if not ctx and upd_dict:
            change_notice.Update(**upd_dict)

    def _CreateProcessInstance(self, template_process_id):
        process = processes.Process.CreateFromTemplate(template_process_id, {"cdb_project_id": self.cdb_project_id})

        # append ec_id to process title
        new_title = "%s (%s)" % (process.title, self.cdb_ec_id)
        if len(new_title) <= processes.Process.title.length:
            process.title = new_title

        # populate briefcases
        for briefcase in process.AllBriefcases:
            objects = self.process_briefcase_map.get(briefcase.name, lambda self: [])
            for obj in objects(self):
                briefcase.AddObject(obj.cdb_object_id)  # TODO: implement method
        return process

    def _RunProcesses(self):
        for templ_ref in self.ProcessTemplateReferencesByState[self.status]:
            if templ_ref.Process:
                process = self._CreateProcessInstance(templ_ref.cdb_process_id)
                process.op_activate_process()
            templ_ref.Delete()

    @classmethod
    def _get_ready_state(cls, process_or_task_class):
        """
        Helper to get the correct ready status for workflow processes or tasks depending on the
        different versions of cs.workflow in ce 15.2 and newer.
        """
        if "15.2" in version.getVersionDescription():
            return process_or_task_class.READY
        else:
            return process_or_task_class.EXECUTION

    @classmethod
    def _get_onhold_state(cls, process_or_task_class):
        """
        Helper to get the correct onhold status for workflow processes or tasks depending on the
        different versions of cs.workflow in ce 15.2 and newer.
        """
        if "15.2" in version.getVersionDescription():
            return process_or_task_class.ONHOLD
        else:
            try:
                return process_or_task_class.FROZEN
            except AttributeError:
                return process_or_task_class.PAUSED

    def _StateChangeByManagedProcess(self, target_state):
        """ Return True the status change can only be done by
            a managed process.

            You can override this method if you want to customize
            this behavior.
        """
        stds = systemtasks.SystemTaskDefinition.KeywordQuery(name="Statuswechsel")
        if not stds:
            return False
        std = stds[0]

        for briefcase in self.Briefcases:
            if briefcase.Process.status == EngineeringChange._get_ready_state(processes.Process).status:
                for link in briefcase.Links:
                    if isinstance(link.Task, tasks.SystemTask) and\
                            link.Task.status in [EngineeringChange._get_ready_state(tasks.Task).status,
                                                 tasks.Task.NEW.status] and\
                            link.Task.Definition == std and\
                            link.Task.AllParameters.KeywordQuery(name="target_state",
                                                                 value=target_state):
                        return True
        return False

    def copy_template_process_refs(self, ctx):
        # Copy references of assigned process templates, if copied ec was a template.
        copied_ec = EngineeringChange.ByKeys(ctx.cdbtemplate.cdb_ec_id)
        if copied_ec.template == 1:
            for ref in copied_ec.ProcessTemplateReferences:
                ref.Copy(cdb_ec_id=self.cdb_ec_id)
            # ggf. Prozesse starten, deren Startbedingung der Initialstatus ist
            self._RunProcesses()

    def addToRunningWorkflows(self, briefcase_names, obj):
        condition = briefcases.Briefcase.name.one_of(*briefcase_names)

        for pr in self.ProcessReferences:
            if pr.Process and pr.Process.status == EngineeringChange._get_ready_state(processes.Process).status:
                for briefcase in pr.Process.AllBriefcases.Query(condition):
                    briefcase.AddObject(obj.cdb_object_id)

    def removeFromRunningWorkflows(self, briefcase_names, obj):
        condition = briefcases.Briefcase.name.one_of(*briefcase_names)

        for pr in self.ProcessReferences:
            if pr.Process and pr.Process.status == EngineeringChange._get_ready_state(processes.Process).status:
                for briefcase in pr.Process.AllBriefcases.Query(condition):
                    briefcase.RemoveObject(obj.cdb_object_id)

    def _CheckRoles(self, process):
        for subject_type, subjects in process.Subjects().items():
            if subject_type not in ['Common Role', 'Person']:
                oc = acs.OrgContext.ByRoleType(subject_type)
                if oc:
                    if not hasattr(self, oc.context_attr):
                        # Der Vorgang '%s' enthält Aufgaben mit den Rollen %s als verantwortliche Personen.
                        # Das Attribut '%s' fehlt in Relation '%s'.
                        raise ue.Exception("cdbecm_err_role1", process.title, ', '.join(subjects), oc.context_attr, self.GetTableName())
                    if not self[oc.context_attr]:
                        # Der Vorgang '%s' enthält Aufgaben mit den Rollen %s als verantwortliche Personen,
                        # die über die Zuordnung im Feld '%s' definiert werden. Das Feld '%s' muß gefüllt sein.
                        label = gui.Mask.GetAttributeLabel('cdbecm_ec', oc.context_attr)
                        if not label:
                            label = oc.context_attr
                        raise ue.Exception("cdbecm_err_role2", process.title, ', '.join(subjects), label, label)
                    else:
                        # Prüfung, ob das Kontextobjekt die durch die zugeordneten Prozesse benötigten Rollen bereitstellt.
                        t = sqlapi.SQLselect("role_id FROM %s WHERE %s = '%s'" % (oc.role_relation,
                                                                                  oc.context_attr,
                                                                                  self[oc.context_attr]))
                        defined_roles = []
                        for i in range(sqlapi.SQLrows(t)):
                            defined_roles.append(sqlapi.SQLstring(t, 0, i))
                        for s in subjects:
                            if s not in defined_roles:
                                # Der Vorgang '%s' enthält Aufgaben mit der Rolle '%s' als verantwortliche Personen.
                                # Die Rolle '%s' ist durch die Zuordnung '%s' im Feld '%s' jedoch nicht definiert.
                                label = gui.Mask.GetAttributeLabel('cdbecm_ec', oc.context_attr)
                                if not label:
                                    label = oc.context_attr
                                raise ue.Exception("cdbecm_err_role3", process.title, s, s, self[oc.context_attr], label)

    def disable_register(self, ctx):
        if self.template:
            ctx.disable_registers(["cdbecm_ec"])
        else:
            ctx.disable_registers(["cdbecm_ec_template"])

    def create_reference_to_defect(self, ctx):
        # If the operation 'new from template' is called within a defect
        # create a reference to the defect after copying

        if "cdb_defect_object_id" in ctx.sys_args.get_attribute_names():
            from cs.ec_defects import Defect2EC
            Defect2EC.Create(cdb_defect_object_id=ctx.sys_args.cdb_defect_object_id,
                             cdb_ec_id=self.cdb_ec_id)

    def allocate_template_license(self, ctx=None):
        if self.template == 1:
            from cdb.fls import allocate_license
            allocate_license("ECM_050")

    event_map = {
        ("copy", "pre_mask"): "disable_register",
        (("create", "copy", "modify", "delete"), "pre"): "allocate_template_license"
    }


class TemplateProcessReference(Object):
    __maps_to__ = "cdbecm_ec_templ2proc"
    __classname__ = "cdbecm_ec_templ2proc"

    Process = Reference_1(processes.Process, fTemplateProcessReference.cdb_process_id)
    EC = Reference_1(EngineeringChange, fTemplateProcessReference.cdb_ec_id)

    def on_create_pre(self, ctx):
        # Only templates can be assigned to each other
        if self.Process.is_template == '0' or self.EC.template == 0:
            raise ue.Exception("cdbecm_err_assign")


class RuleReference(Object):
    __maps_to__ = "cdbecm_ec_templ2rule"
    __classname__ = "cdbecm_ec_templ2rule"

    Rule = Reference_1(Rule, fRuleReference.rule_id)
    EC = Reference_1(EngineeringChange, fRuleReference.cdb_ec_id)


class ProcessReference(Object):
    __maps_to__ = "cdbecm_briefcase2ec_v"
    __classname__ = "cdbecm_briefcase2ec"

    Process = Reference_1(processes.Process, fProcessReference.cdb_process_id)
    Briefcase = Reference_1(briefcases.Briefcase,
                            briefcases.Briefcase.cdb_process_id == fProcessReference.cdb_process_id,
                            briefcases.Briefcase.briefcase_id == fProcessReference.briefcase_id)
    EC = Reference_1(EngineeringChange, fProcessReference.cdb_ec_id)


class ECStatusProtocol(Object):
    __maps_to__ = "cdbecm_ec_prot"
