#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
import datetime
from cdb.classbody import classbody
from cdb import sig
from cdb import ue
from cdb import constants
from cdb import sqlapi

from cdb.objects import Reference_N
from cdb.objects import Reference_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import operations

from cdb.platform.olc import StateDefinition
from cs.pcs.projects import Project
from cs.costing.calculations import Calculation
from cs.costing.calculations import Component
from cs.costing.schemes import PARAMETER_SIGNAL
from cs.costing.schemes import CONTEXT_ONLY_KEY
from cs.costing.schemes import WithCalculationSchema
from cs.pcs.costs.sheets import CostSheet
from cs.pcs.costs.sheets import CostSheetFolder
from cs.pcs.costs.sheets import CostPosition
from cs.pcs.costs.sheets import copy_sheets
from cs.pcs.costs.definitions import CostSignificance
from cs.currency import CurrConversion
from cs.currency import Currency
import six


def get_cost_significance_for_calculation():
    allcs = CostSignificance.KeywordQuery(id="CALC")
    if len(allcs):
        return allcs[0]
    return None


@classbody
class Project(object):

    PCOCalculations = Reference_N(
        Calculation,
        Calculation.cdb_project_id == Project.cdb_project_id)

    ValidPCOCalculations = Reference_N(
        Calculation,
        Calculation.cdb_project_id == Project.cdb_project_id,
        Calculation.cdb_obsolete != 1)

    @sig.connect(Project, "delete", "post")
    def cdbpco_delete(self, ctx):
        """
        Delete Calculation-related objects.
        """
        for calcobj in self.PCOCalculations:
            calcobj.calcBatchDelete(ctx)

    @sig.connect(Project, "state_change", "post")
    def adjustCalculationStatus(self, ctx):
        if ctx.error:
            return
        if self.status == Project.DISCARDED.status:
            for calc in self.PCOCalculations:
                if calc.status not in (Calculation.DISCARDED.status,
                                       Calculation.OBSOLETE.status):
                    calc.ChangeState(Calculation.DISCARDED.status)
        elif self.status == Project.COMPLETED.status:
            for calc in self.ValidPCOCalculations:
                if calc.status == Calculation.NEW.status:
                    calc.ChangeState(Calculation.COMPLETED.status)

    def allowCalculationChanges(self):
        return self.status in [Project.NEW.status, Project.EXECUTION.status]


@classbody
class Calculation(object):

    Project = Reference_1(Project, Calculation.cdb_project_id)

    def _getCostSheets(self, obsolete=False):
        costsignificance = CostSignificance.KeywordQuery(id='CALC')
        addtl = {}
        if not obsolete:
            addtl.update(cdb_obsolete=0)
        if costsignificance:
            return CostSheet.KeywordQuery(order_by="c_index",
                                          cdb_project_id=self.cdb_project_id,
                                          costsignificance_object_id=costsignificance[0].cdb_object_id,
                                          calc_object_id=self.cdb_object_id,
                                          **addtl)
        return []

    ProjectCostSheets = ReferenceMethods_N(
            CostSheet,
            lambda self: self._getCostSheets(obsolete=False))

    AllProjectCostSheets = ReferenceMethods_N(
            CostSheet,
            lambda self: self._getCostSheets(obsolete=True))

    ProjectCostPositions = Reference_N(
        CostPosition,
        CostPosition.calc_object_id == Calculation.cdb_object_id,
        CostPosition.cdb_obsolete != 1)

    def preset_project(self, ctx):
        if ctx.relationship_name == 'cdbpco_project2calculation':
            ctx.set("cdb_project_id", ctx.parent["cdb_project_id"])
            prj = Project.ByKeys(ctx.parent["cdb_project_id"])
            ctx.set("project_name", prj.project_name)

    @sig.connect(Calculation, "copy", "pre_mask")
    def _preset_project(self, ctx):
        self.preset_project(ctx)

    @sig.connect(Calculation, "create", "pre_mask")
    @sig.connect(Calculation, "create", "pre")
    @sig.connect(Calculation, "copy", "pre")
    @sig.connect(Calculation, "modify", "pre")
    def checkProjectStatus(self, ctx):
        if self.Project and not self.Project.allowCalculationChanges():
            raise ue.Exception("cdbpco_calculation_invalid_project_status")

    @sig.connect(Calculation, "create", "pre_mask")
    def presetProjectCurrency(self, ctx):
        if not self.curr_object_id:
            if self.cdb_project_id and self.Project.currency_object_id:
                self.curr_object_id = self.Project.currency_object_id
            else:
                self.curr_object_id = Currency.getDefaultCurrency().cdb_object_id

    def set_template_flag(self, ctx):
        # If the Calculation object belong to a template project, it is also a
        # template.
        if self.Project:
            self.template = self.Project.template
            ctx.set_readonly("template")

    @sig.connect(Calculation, "create", "pre_mask")
    def _set_template_flag(self, ctx):
        self.set_template_flag(ctx)

    @classmethod
    def on_cdbxml_excel_report_now(cls, ctx):
        if hasattr(ctx.dialog, 'cdbxml_report_title'):
            if ctx.dialog.cdbxml_report_title == 'Projektkosten':
                obj = cls.PersistentObjectsFromContext(ctx)[0]
                if not obj.ProjectCostSheets:
                    raise ue.Exception("cdbpco_no_valid_project_costsheet")
                elif len(obj.ProjectCostSheets) > 1:
                    raise ue.Exception("cdbpco_more_valid_project_costsheeet")
        super(Calculation, cls).on_cdbxml_excel_report_now(ctx)

    @sig.connect(Calculation, PARAMETER_SIGNAL)
    def getProjectCosts(self, classname, calculation, ctx, exch_factor):
        calc_curr = self.curr_object_id
        cdb_project_id = self.cdb_project_id
        costs = [0, 0]
        for allocated in (0, 1):
            for pcp in Calculation.ByKeys(self.cdb_object_id).ProjectCostPositions.KeywordQuery(
                    allocate_costs=allocated):
                exch = exch_factor.setdefault(
                    (pcp.currency_object_id, calc_curr),
                    CurrConversion.getCurrExchangeFactor(
                        pcp.currency_object_id,
                        calc_curr,
                        cdb_project_id))
                costs[allocated] += pcp.costs * exch
        result = dict(values={
            "IPCAL": costs[1],
            "IPCAC": costs[0]
        })
        result[CONTEXT_ONLY_KEY] = ["IPCAL", "IPCAC"]
        return result

    @sig.connect(Calculation, "create", "post")
    @sig.connect(Calculation, "copy", "post")
    def autoGenerateCostSheet(self, ctx):
        if ctx.action == "copy":
            calc_templ = Calculation.ByKeys(ctx.cdbtemplate.cdb_object_id)
            if calc_templ and calc_templ.AllProjectCostSheets:
                return
        costsig = get_cost_significance_for_calculation()
        new_sheet = CostSheet.createSheet(
            self.Project,
            calc_object_id=self.cdb_object_id,
            costsignificance_object_id=costsig.cdb_object_id)
        if new_sheet:
            new_sheet.setSheetName(suffix=new_sheet.getNameSuffixForCalculation(),
                                   force=True)

    @sig.connect(Calculation, "modify", "pre")
    def markProjectChanges(self, ctx):
        if not ctx.object.cdb_project_id and ctx.dialog.cdb_project_id:
            ctx.keep("cs_costing_project_changed", 1)

    @sig.connect(Calculation, "modify", "post")
    def autoGenerateCostSheetOnModifyPost(self, ctx):
        if "cs_costing_project_changed" in ctx.ue_args.get_attribute_names():
            self.autoGenerateCostSheet(ctx)

    @sig.connect(Calculation, "state_change", "post")
    def adjustCostSheetStatus(self, ctx):
        if not ctx.error:
            for sheet in self.ProjectCostSheets:
                if sheet.status != self.status:
                    sheet.ChangeState(self.status)

    @sig.connect(Calculation, "copy", "pre")
    def rememberCostSheet(self, ctx):
        # remember the valid cost sheet because in the
        # copy post hook the source sheet would be set
        # to obsolete and can not be determined any more
        if "followup_cdbpco_new_revision" in ctx.ue_args.get_attribute_names() and \
                len(self.ProjectCostSheets):
            ctx.keep("valid_cost_sheet_id", self.ProjectCostSheets[0].cdb_object_id)
            ctx.keep("valid_cost_sheet_status", self.ProjectCostSheets[0].status)

    @sig.connect(Calculation, "copy", "post")
    def copyCostSheet(self, ctx):
        if not ctx.error and \
           "no_copy_cost_sheets" not in ctx.sys_args.get_attribute_names():
            calc_tmpl = Calculation.ByKeys(ctx.cdbtemplate.cdb_object_id)
            kwargs = dict(calc_object_id=self.cdb_object_id)
            if calc_tmpl.cdb_project_id != self.cdb_project_id:
                kwargs.update(cdb_project_id=self.cdb_project_id)
            valid_sheet = ""
            valid_sheet_status = CostSheet.NEW.status
            if not "followup_cdbpco_new_revision" in ctx.ue_args.get_attribute_names():
                # copy valid cost sheet only when copying a calculation
                sheets = calc_tmpl.ProjectCostSheets
            else:
                # copy all cost sheets and reset the status of the kept valid sheet
                # when revisioning a calculation
                sheets = calc_tmpl.AllProjectCostSheets
                # get the remembered valid cost sheet id and status
                if "valid_cost_sheet_id" in ctx.ue_args.get_attribute_names() and \
                    "valid_cost_sheet_status" in ctx.ue_args.get_attribute_names():
                    valid_sheet = ctx.ue_args.valid_cost_sheet_id
                    valid_sheet_status = ctx.ue_args.valid_cost_sheet_status
                elif len(sheets):
                    # If all sheets are obsolete in template calculation:
                    # the sheet with the highest index should be reset to new status
                    latest_sheet = sheets[-1]
                    if latest_sheet.status == CostSheet.OBSOLETE.status:
                        valid_sheet = latest_sheet.cdb_object_id
                        valid_sheet_status = CostSheet.NEW.status
            for sheet in sheets:
                new_sheet = sheet.copySheet(**kwargs)
                if new_sheet:
                    # reset sheet name to new calculation name and index
                    new_sheet.setSheetName(suffix=new_sheet.getNameSuffixForCalculation(),
                                           force=True)
                    # reset the status of the kept sheet that has been set to obsolete
                    # when revisioning
                    if valid_sheet and sheet.cdb_object_id == valid_sheet:
                        sd = StateDefinition.ByKeys(objektart=sheet.cdb_objektart,
                                                    statusnummer=valid_sheet_status)
                        new_sheet.Update(status=valid_sheet_status,
                                         cdb_obsolete=0,
                                         cdb_status_txt=sd.statusbezeich)
                    # reset the status of all other sheets to the templates statuses
                    elif new_sheet.status != sheet.status:
                        sd = StateDefinition.ByKeys(objektart=sheet.cdb_objektart,
                                                    statusnummer=sheet.status)
                        new_sheet.Update(status=sheet.status,
                                         cdb_obsolete=sheet.cdb_obsolete,
                                         cdb_status_txt=sd.statusbezeich)

    # FIXME: for demo
    @sig.connect(Calculation, "delete", "pre")
    def deleteCostSheet(self, ctx):
        if self.AllProjectCostSheets:
            self.AllProjectCostSheets.Delete()

    @sig.connect(Calculation, "delete", "post")
    def refreshCostSheet(self, ctx):
        prev = len(self.PreviousVersions)
        if prev and prev == len(self.OtherVersions):
            last_one = self.PreviousVersions[-1]
            sheets = last_one.AllProjectCostSheets
            if sheets:
                last_sheet = sheets[-1]
                if last_sheet.status == CostSheet.OBSOLETE.status:
                    try:
                        last_sheet.ChangeState(CostSheet.NEW.status)
                    except:
                        sd = StateDefinition.ByKeys(objektart=last_sheet.cdb_objektart,
                                                    statusnummer=CostSheet.NEW.status)
                        last_sheet.Update(status=CostSheet.NEW.status,
                                          cdb_obsolete=0,
                                          cdb_status_txt=sd.statusbezeich)
                    last_sheet.Positions.Update(cdb_obsolete=0)


@classbody
class CostSheet(object):

    Calculation = Reference_1(Calculation, CostSheet.calc_object_id)

    def getNameSuffixForCalculation(self):
        return " (%s)" % self.Calculation.GetDescription()

    @sig.connect(CostSheet, "create", "pre_mask")
    def _preset_category_with_calculation(self, ctx):
        if self.Calculation:
            costsig = get_cost_significance_for_calculation()
            if costsig:
                ctx.set("costsignificance_object_id", costsig.cdb_object_id)
                self.costsignificance_object_id = costsig.cdb_object_id
                joined_attrs = self.GetDependendJoinedAttrs(
                    costsignificance_object_id=self.costsignificance_object_id)
                for attr, value in list(six.iteritems(joined_attrs)):
                    if attr in ctx.dialog.get_attribute_names():
                        ctx.set(attr, value)
            self.presetSheetName(ctx, suffix=self.getNameSuffixForCalculation())

    @sig.connect(CostSheet, "create", "pre_mask")
    @sig.connect(CostSheet, "modify", "pre_mask")
    @sig.connect(CostSheet, "copy", "pre_mask")
    def _check_category_with_calculation(self, ctx):
        if ctx.action == "copy" and \
           ctx.relationship_name != "cdbpco_calc2costsheets":
            return
        if self.Calculation:
            ctx.set_fields_readonly(
                ["costsignificance_object_id", "costsignificance_name"])

    @sig.connect(CostSheet, "copy", "pre")
    def fixCalculationReference(self, ctx):
        if "should_fix_costing_references" not in \
                ctx.sys_args.get_attribute_names():
            return
        if self.cdb_project_id and \
           self.calc_object_id == ctx.cdbtemplate.calc_object_id:
            # reference is copied, change that
            cond = "cdb_project_id='%s' and template_object_id='%s'" % (
                self.cdb_project_id, self.calc_object_id
            )
            rset = sqlapi.RecordSet2(table=Calculation.GetTableName(),
                                     condition=cond,
                                     columns=["cdb_object_id"])
            if len(rset):
                self.calc_object_id = rset[0].cdb_object_id
            # TODO: else?

    @sig.connect(CostSheet, "copy", "pre_mask")
    def presetCalculationFields(self, ctx):
        if ctx.relationship_name == "cdbpco_calc2costsheets":
            self.calc_object_id = ctx.cdbtemplate.calc_object_id
            self._preset_category_with_calculation(ctx)

    @sig.connect(CostSheet, "copy", "post")
    def resetCalculationFieldsByPositions(self, ctx):
        if not self.calc_object_id:
            self.Positions.Update(component_object_id="", allocate_costs=0)


@classbody
class CostPosition(object):

    Calculation = Reference_1(Calculation, CostPosition.calc_object_id)

    @sig.connect(CostPosition, "create", "pre_mask")
    @sig.connect(CostPosition, "copy", "pre_mask")
    def _preset_calculation(self, ctx):
        if self.CostSheet:
            if self.CostSheet.calc_object_id:
                self.calc_object_id = self.CostSheet.calc_object_id
            else:
                ctx.set_fields_readonly(["component_object_id", "allocate_costs"])
        else:
            if ctx.relationship_name == "cdbpcs_costsheetfolder2positions":
                if ctx.parent:
                    csf = CostSheetFolder.ByKeys(ctx.parent.cdb_object_id)
                    if csf:
                        ctx.set("costsheet_object_id", csf.costsheet_object_id)
                        cs = CostSheet.ByKeys(csf.costsheet_object_id)
                        if cs and cs.calc_object_id:
                            ctx.set("calc_object_id", cs.calc_object_id)
                            if not self.component_object_id:
                                ctx.set("allocate_costs", 0)
                                ctx.set_fields_readonly(["allocate_costs"])
                        else:
                            ctx.set_fields_readonly(["component_object_id", "allocate_costs"])

    @sig.connect(CostPosition, "modify", "pre_mask")
    def disableCalculationFields(self, ctx):
        if not self.calc_object_id:
            ctx.set_fields_readonly(["component_object_id", "allocate_costs"])
        elif not self.component_object_id:
            ctx.set("allocate_costs", 0)
            ctx.set_fields_readonly(["allocate_costs"])

    @sig.connect(CostPosition, "copy", "pre")
    def fixCalculationReference(self, ctx):
        calc_object_id = self.CostSheet.calc_object_id
        if calc_object_id == self.calc_object_id:
            # not copied from another calculation
            return
        self.calc_object_id = calc_object_id
        if not self.component_object_id:
            return
        # component reference is copied, change that
        cond = "calc_object_id='%s' and template_object_id='%s'" % (
            calc_object_id, self.component_object_id
        )
        rset = sqlapi.RecordSet2(table=Component.GetTableName(),
                                 condition=cond,
                                 columns=["cdb_object_id"])
        if len(rset):
            self.component_object_id = rset[0].cdb_object_id
        else:
            # component is not copied/does not exist
            self.component_object_id = ""

    @sig.connect(CostPosition, "create", "dialogitem_change")
    @sig.connect(CostPosition, "copy", "dialogitem_change")
    @sig.connect(CostPosition, "modify", "dialogitem_change")
    def setAllocateCostsWriteable(self, ctx):
        if ctx.changed_item == "component_object_id":
            if ctx.dialog.component_object_id:
                ctx.set_fields_writeable(["allocate_costs"])
            else:
                ctx.set("allocate_costs", 0)
                ctx.set_fields_readonly(["allocate_costs"])
        if ctx.changed_item == "allocate_costs":
            if ctx.dialog.allocate_costs == "1":
                ctx.set_mandatory("component_object_id")
            else:
                ctx.set_optional("component_object_id")


@classbody
class Component(object):
    ProjectCostPositions = Reference_N(
        CostPosition,
        CostPosition.component_object_id == Component.cdb_object_id,
        CostPosition.cdb_obsolete != 1)

    @sig.connect(Component, PARAMETER_SIGNAL)
    def getProjectCosts(self, classname, calculation, ctx, exch_factor):
        calc_curr = self.curr_object_id
        cdb_project_id = self.cdb_project_id
        costs = [0, 0]
        for allocated in (0, 1):
            for pcp in Component.ByKeys(self.cdb_object_id).ProjectCostPositions.KeywordQuery(
                    allocate_costs=allocated):
                exch = exch_factor.setdefault(
                    (pcp.currency_object_id, calc_curr),
                    CurrConversion.getCurrExchangeFactor(
                        pcp.currency_object_id,
                        calc_curr,
                        cdb_project_id))
                costs[allocated] += pcp.costs * exch
        result = dict(values={
            "IPCAL": costs[1],
            "IPCAC": costs[0]
        })
        result[CONTEXT_ONLY_KEY] = ["IPCAL", "IPCAC"]
        return result


@sig.connect(WithCalculationSchema, PARAMETER_SIGNAL)
def get_default_project_costs(record, classname, calculation, ctx, exch_factor):
    result = dict(values={
        "IPCAL": 0,
        "IPCAC": 0
    })
    result[CONTEXT_ONLY_KEY] = ["IPCAL", "IPCAC"]
    return result


@sig.connect_before(copy_sheets)
def copy_project_calucations(tmpl_project, new_project):
    if not tmpl_project:
        return
    for calc in tmpl_project.PCOCalculations.KeywordQuery(status=0):
        sys_args = operations.system_args(no_copy_cost_sheets=1)
        kwargs = dict(cdb_project_id=new_project.cdb_project_id)
        if tmpl_project.template == 1 and \
           new_project.template == 0 and \
           calc.template == 1:
            kwargs.update(template=0, para_year=str(datetime.date.today().year))
        try:
            operations.operation(
                constants.kOperationCopy,
                calc.ToObjectHandle(),
                sys_args,
                **kwargs
            )
        except Exception:
            raise ue.Exception("cdbpco_calculation_project_creation_failed")


@classbody
class Currency(object):
    def checkRefCurr(self, ctx):
        """
        Check uniqueness of the reference currency: there can be only one for each scheam.
        """
        if self.is_ref_curr != 1:
            if len(Currency.KeywordQuery(is_ref_curr=1,
                                         schema_object_id=self.schema_object_id)) > 0:
                ctx.set_readonly("is_ref_curr")
