#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import six

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants, misc, sig, sqlapi, transaction, ue, util
from cdb.objects import Forward, Object, Reference_1, Reference_N, State, Transition
from cdb.objects.operations import operation, system_args
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.sharing.share_objects import WithSharing
from cs.tools.powerreports import WithPowerReports
from cs.workflow import briefcases

fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")

fCostCenter = Forward("cs.pcs.costs.definitions.CostCenter")
fCostType = Forward("cs.pcs.costs.definitions.CostType")
fCostSignificance = Forward("cs.pcs.costs.definitions.CostSignificance")
fCostSheet = Forward(__name__ + ".CostSheet")
fCostSheetFolder = Forward(__name__ + ".CostSheetFolder")
fCostPosition = Forward(__name__ + ".CostPosition")
fCostSheetFolderPosition = Forward(__name__ + ".CostSheetFolderPosition")
fCurrency = Forward("cs.currency.Currency")

PROJECTCOSTROLE = "Project Cost Management"


def __log__(txt, lvl=7):
    misc.cdblogv(misc.kLogMsg, lvl, six.text_type(txt))


class CostSheet(Object, WithPowerReports, briefcases.BriefcaseContent, WithSharing):
    __maps_to__ = "cdbpcs_cost_sheet"
    __classname__ = "cdbpcs_cost_sheet"

    CostSignificance = Reference_1(
        fCostSignificance, fCostSheet.costsignificance_object_id
    )
    Project = Reference_1(fProject, fCostSheet.cdb_project_id)
    Positions = Reference_N(
        fCostPosition, fCostPosition.costsheet_object_id == fCostSheet.cdb_object_id
    )
    TopFolders = Reference_N(
        fCostSheetFolder,
        fCostSheetFolder.costsheet_object_id == fCostSheet.cdb_object_id,
        fCostSheetFolder.parent_object_id == "",
    )
    NotTaskPositions = Reference_N(
        fCostPosition,
        fCostPosition.costsheet_object_id == fCostSheet.cdb_object_id,
        fCostPosition.generated_from_task == 0,
    )
    OtherVersions = Reference_N(
        fCostSheet,
        fCostSheet.cdb_project_id == fCostSheet.cdb_project_id,
        fCostSheet.calc_object_id == fCostSheet.calc_object_id,
        fCostSheet.costsignificance_object_id == fCostSheet.costsignificance_object_id,
        fCostSheet.c_index != fCostSheet.c_index,
        order_by=fCostSheet.c_index,
    )
    PreviousVersions = Reference_N(
        fCostSheet,
        fCostSheet.cdb_project_id == fCostSheet.cdb_project_id,
        fCostSheet.calc_object_id == fCostSheet.calc_object_id,
        fCostSheet.costsignificance_object_id == fCostSheet.costsignificance_object_id,
        fCostSheet.c_index < fCostSheet.c_index,
        order_by=fCostSheet.c_index,
    )

    event_map = {
        (
            ("cdbpcs_costs_create_index", "create", "copy"),
            ("pre_mask"),
        ): "checkProjectStatus",
        (("create", "copy"), ("pre_mask")): "setDefaults",
        ("copy", "pre_mask"): "clearCopy",
        ("modify", "pre_mask"): "setreadOnly",
        (("create", "copy"), ("dialogitem_change")): "presetSheetName",
        (("create", "copy", "modify"), "pre"): "ensureUniqueValidSignificance",
        (("create", "copy"), "pre"): ("presetSheetName", "setWorkflow"),
        ("cdbpcs_costs_create_index", "now"): "createIndex",
        ("delete", "pre"): "deleteIndex",
        ("copy", "pre"): ("setIndex"),
        ("create", "dialogitem_change"): "setIndex",
        ("copy", "post"): ("copySheetFoldersPositions", "refreshCurrencyConversion"),
        ("cdbpcs_reset_positions", "now"): (
            "resetPositions",
            "refreshCurrencyConversion",
        ),
        ("cdbpcs_costs_copy_folder_struct", "now"): (
            "copyFolderStructure",
            "refreshCurrencyConversion",
        ),
        ("cdbpcs_costs_refresh_conversion", "now"): "refreshCurrencyConversion",
        ("cdbpcs_costs_sync_with_tasks", "now"): (
            "syncTasks",
            "refreshCurrencyConversion",
        ),
        ("cdbpcs_reinit_position", "now"): ("reinit_positions"),
    }

    class NEW(State):
        status = 0

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(CostSheet.OBSOLETE.status)
            super(CostSheet.NEW, state).pre_mask(self, ctx)

        def post(state, self, ctx):
            self.cdb_obsolete = 0
            self.Positions.Update(cdb_obsolete=0)
            self.refreshCurrencyConversion()

    class COMPLETED(State):
        status = 250

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(CostSheet.OBSOLETE.status)
            super(CostSheet.COMPLETED, state).pre_mask(self, ctx)

    class DISCARDED(State):
        status = 180

        def post(state, self, ctx):  # @NoSelf
            self.cdb_obsolete = 1
            self.Positions.Update(cdb_obsolete=1)

    class OBSOLETE(State):
        status = 190

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(CostSheet.NEW.status)
                ctx.excl_state(CostSheet.DISCARDED.status)
            super(CostSheet.OBSOLETE, state).pre_mask(self, ctx)

        def post(state, self, ctx):  # @NoSelf
            self.cdb_obsolete = 1
            self.Positions.Update(cdb_obsolete=1)

    class NEW_TO_DISCARDED(Transition):
        transition = (0, 180)

        def pre(transition, self, ctx):  # @NoSelf
            if not ctx.batch:
                if not self.Project.allowCostSheetChanges():
                    raise ue.Exception("cdbpcs_cost_invalid_project_status_change")

    class NEW_TO_COMPLETED(Transition):
        transition = (0, 250)

    class OBSOLETE_TO_DISCARDED(Transition):
        transition = (190, 180)

    class COMPLETED_TO_DISCARDED(Transition):
        transition = (250, 180)

        def pre(transition, self, ctx):  # @NoSelf
            if not ctx.batch:
                if not self.Project.allowCostSheetChanges():
                    raise ue.Exception("cdbpcs_cost_invalid_project_status_change")

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the Project and the CostSheet itself.
        """
        return [self, self.Project]

    def checkProjectStatus(self, ctx):
        if not self.Project:
            raise ue.Exception("cdbpcs_costs_no_project")
        elif not self.Project.allowCostSheetChanges():
            raise ue.Exception("cdbpcs_cost_invalid_project_status")

    @classmethod
    def getDefaults(cls, newIndex, project=None, ctx=None):
        dflts = dict(status=CostSheet.NEW.status, cdb_obsolete=0)
        if project and project.template:
            dflts.update(is_template=1)
        else:
            dflts.update(is_template=0)
        if newIndex:
            dflts.update(c_index=0)
        return dflts

    def setDefaults(self, ctx):
        dflts = self.getDefaults(
            newIndex=ctx.action == "create", project=self.Project, ctx=ctx
        )
        for k in dflts:
            ctx.set(k, dflts[k])

    def clearCopy(self, ctx):
        ctx.set("calc_object_id", "")
        values = self.GetLocalizedValues("name")
        for lang in values:
            self.SetLocalizedValue("name", lang, "")
        values = self.GetLocalizedValues("costsignificance_name")
        for lang in values:
            ctx.set("costsignificance_name_%s" % lang, "")
        ctx.set("costsignificance_object_id", "")

    def setreadOnly(self, ctx):
        ctx.set_readonly("costsignificance_object_id")

    def setSheetName(self, suffix="", force=True):
        """Auto fill the sheet name according to chosen cost significance"""
        if self.Project and self.CostSignificance:
            prefix = "%s: " % self.Project.project_name
            values = self.GetLocalizedValues("name")
            cs_names = self.CostSignificance.GetLocalizedValues("name")
            for lang in values:
                cs_name = cs_names.get(lang)
                if (force or not values[lang]) and cs_name:
                    self.SetLocalizedValue("name", lang, f"{prefix}{cs_name}{suffix}")

    def presetSheetName(self, ctx=None, suffix=""):
        """Auto fill the sheet name according to chosen cost significance"""
        self.setSheetName(suffix, False)

    def setWorkflow(self, ctx):
        if self.CostSignificance:
            self.cdb_objektart = "cdbpcs_cost_sheet_" + self.CostSignificance.id.lower()

    def ensureUniqueValidSignificance(self, ctx):
        """Prevent using multiple valid sheets of the same significance"""
        if self.Project:
            for sheet in self.Project.ValidCostSheets:
                if sheet.cdb_object_id == self.cdb_object_id:
                    continue
                if (
                    sheet.costsignificance_object_id == self.costsignificance_object_id
                    and (
                        not self.calc_object_id
                        or sheet.calc_object_id == self.calc_object_id
                    )
                ):
                    raise ue.Exception(
                        "cdbpcs_cost_valid_sheet_significance_not_unique"
                    )

    def setIndex(self, ctx):
        calc_object_id = self.calc_object_id
        costsignificance_object_id = self.costsignificance_object_id
        if ctx.dialog:
            if "calc_object_id" in ctx.dialog.get_attribute_names():
                calc_object_id = ctx.dialog.calc_object_id
            if "costsignificance_object_id" in ctx.dialog.get_attribute_names():
                costsignificance_object_id = ctx.dialog.costsignificance_object_id

        if not self.calc_object_id:
            costsheets = CostSheet.KeywordQuery(
                cdb_project_id=self.cdb_project_id,
                costsignificance_object_id=costsignificance_object_id,
            )
        else:
            costsheets = CostSheet.KeywordQuery(
                calc_object_id=calc_object_id,
                cdb_project_id=self.cdb_project_id,
                costsignificance_object_id=costsignificance_object_id,
            )
        index = 0
        if costsheets:
            index = max(costsheets.c_index) + 1
        ctx.set("c_index", index)

    def createIndex(self, ctx):
        with transaction.Transaction():
            if self.status in [CostSheet.NEW.status, CostSheet.COMPLETED.status]:
                self.ChangeState(CostSheet.OBSOLETE.status)
            elif len(self.OtherVersions):
                latest_version = self.OtherVersions[-1]
                if latest_version.status in [
                    CostSheet.NEW.status,
                    CostSheet.COMPLETED.status,
                ]:
                    latest_version.ChangeState(CostSheet.OBSOLETE.status)
            self.copySheet(revisioning=True, cdb_obsolete=0)
            self.Positions.Update(cdb_obsolete=1)
            ctx.refresh_tables(["cdbpcs_cost_sheet"])

    def deleteIndex(self, ctx):
        with transaction.Transaction():
            # only if current version is the newest one
            prev = len(self.PreviousVersions)
            if prev and prev == len(self.OtherVersions):
                last_one = self.PreviousVersions[-1]
                if last_one.status == CostSheet.OBSOLETE.status:
                    last_one.ChangeState(CostSheet.NEW.status)
                    last_one.cdb_obsolete = 0
                    last_one.Positions.Update(cdb_obsolete=0)

    def copySheet(self, revisioning=False, **kwargs):
        if not revisioning:
            sys_args = system_args(should_fix_costing_references=1)
        else:
            sys_args = system_args()
        return operation("CDB_Copy", self.ToObjectHandle(), sys_args, **kwargs)

    def getNewPosValues(self):
        return {
            "costsheet_object_id": self.cdb_object_id,
            "cdb_project_id": self.cdb_project_id,
            "cdb_obsolete": 0,
        }

    def copySheetFoldersPositions(self, ctx):
        sheet_tmpl = CostSheet.ByKeys(ctx.cdbtemplate.cdb_object_id)
        sameProject = False
        if self.cdb_project_id == sheet_tmpl.cdb_project_id:
            sameProject = True
        with transaction.Transaction():
            alreadycopied = []
            for folder in sheet_tmpl.TopFolders:
                alreadycopied += self.copySubFolders(folder, sameProject=sameProject)
            if sameProject:
                # For cost positions without folder assignment
                for pos in sheet_tmpl.Positions:
                    if pos.cdb_object_id not in alreadycopied:
                        pos_args = self.getNewPosValues()
                        operation("CDB_Copy", pos.ToObjectHandle(), **pos_args)
            else:
                # For cost positions without folder assignment
                for pos in sheet_tmpl.NotTaskPositions:
                    if pos.cdb_object_id not in alreadycopied:
                        pos_args = self.getNewPosValues()
                        operation("CDB_Copy", pos.ToObjectHandle(), **pos_args)

    def copySubFolders(self, folder, folderid="", sameProject=False):
        alreadycopied = []
        kwargs = {
            "costsheet_object_id": self.cdb_object_id,
            "parent_object_id": folderid,
        }
        newfolder = operation("CDB_Copy", folder.ToObjectHandle(), **kwargs)
        f2ps = CostSheetFolderPosition.KeywordQuery(
            costsheet_folder_object_id=folder.cdb_object_id
        )
        for f2p in f2ps:
            pos = f2p.CostPosition
            pos_args = self.getNewPosValues()
            if (pos and sameProject) or (pos and not pos.generated_from_task):
                newpos = operation("CDB_Copy", pos.ToObjectHandle(), **pos_args)
                f2p_args = {
                    "costsheet_folder_object_id": newfolder.cdb_object_id,
                    "costpos_object_id": newpos.cdb_object_id,
                }
                operation("CDB_Create", CostSheetFolderPosition, **f2p_args)
                alreadycopied.append(pos.cdb_object_id)
            elif pos and pos.generated_from_task:
                newpos = CostPosition.ByKeys(template_object_id=pos.cdb_object_id)
                if not newpos:
                    newpos = operation("CDB_Copy", pos.ToObjectHandle(), **pos_args)
                f2p_args = {
                    "costsheet_folder_object_id": newfolder.cdb_object_id,
                    "costpos_object_id": newpos.cdb_object_id,
                }
                operation("CDB_Create", CostSheetFolderPosition, **f2p_args)
                alreadycopied.append(pos.cdb_object_id)
        for subfolder in folder.SubFolders:
            alreadycopied += self.copySubFolders(subfolder, newfolder.cdb_object_id)
        return alreadycopied

    def refreshTreeNodes(self):
        util.refresh_structure_node(self.cdb_object_id)

    def resetPositions(self, ctx):
        if ctx and ctx.interactive:
            if "cdbpcs_costs_reset_positions" not in ctx.dialog.get_attribute_names():
                msgbox = ctx.MessageBox(
                    "cdbpcs_costs_reset_positions", [], "cdbpcs_costs_reset_positions"
                )
                msgbox.addYesButton(is_dflt=1)
                msgbox.addNoButton()
                ctx.show_message(msgbox)
                return
            else:
                if (
                    ctx.dialog["cdbpcs_costs_reset_positions"]
                    == ctx.MessageBox.kMsgBoxResultYes
                ):
                    for pos in self.Positions:
                        if pos.generated_from_task:
                            pos.Delete()
                        else:
                            kwargs = {
                                "period_from_task": 0,
                                "start_time": "",
                                "end_time": "",
                                "effort": "0.00",
                                "costs": "0.00",
                                "costs_proj_curr": "0.00",
                            }
                            pos.Update(**kwargs)
            self.refreshTreeNodes()

    def copyFolderStructure(self, ctx):
        if not ctx.catalog_selection:
            browser_attr = {}
            ctx.start_selection(catalog_name="cdbpcs_cost_sheets", **browser_attr)
        else:
            selected_costsheet = CostSheet.ByKeys(
                ctx.catalog_selection[0]["cdb_object_id"]
            )
            for folder in selected_costsheet.TopFolders:
                self.copyonlyFolders(folder)
        self.refreshTreeNodes()

    def copyonlyFolders(self, folder, folderid=""):
        kwargs = {
            "costsheet_object_id": self.cdb_object_id,
            "parent_object_id": folderid,
        }
        new_folder = folder.Copy(**kwargs)
        for subfolder in folder.SubFolders:
            self.copyonlyFolders(subfolder, new_folder.cdb_object_id)

    def refreshCurrencyConversion(self, ctx=None, currency_object_id=None):
        currency_oid = self.Project.currency_object_id
        if currency_object_id:
            currency_oid = currency_object_id
        for position in self.Positions:
            if position.currency_object_id != currency_oid:
                position.costs_proj_curr = position.Currency.convertTo(
                    currency_oid, position.costs, cdb_project_id=self.cdb_project_id
                )
            else:
                position.costs_proj_curr = position.costs
        for folder in self.TopFolders:
            folder.recalculateEffortCosts(currency_oid)

    def reinit_positions(self, ctx):
        pos = 10
        for cp in self.Positions.Query("1=1", order_by="position"):
            cp.position = pos
            pos += 10
        CostSheetFolder.resetPosition(self.cdb_object_id)

    def syncTasks(self, ctx):
        # remove positions of non-existing and cdb_obsolete tasks
        orphaned_positions = []
        for position in self.Positions:
            if position.task_object_id and not position.Task:
                orphaned_positions.append(position)
            elif position.Task and (position.Task.status == Task.DISCARDED.status):
                orphaned_positions.append(position)
        for position in orphaned_positions:
            position.Delete()
        # update positions with tasks
        for position in self.NotTaskPositions.KeywordQuery(period_from_task=1):
            task = position.Task
            if self.CostSignificance.id == "ACTU":
                start_time = task.start_time_act
                end_time = task.end_time_act
            else:
                start_time = (
                    task.start_time_fcast
                    if task.start_time_fcast
                    else task.start_time_plan
                )
                end_time = (
                    task.end_time_fcast if task.end_time_fcast else task.end_time_plan
                )
            attrs = {"start_time": start_time, "end_time": end_time}
            position.Update(**attrs)
            ctx.enable_ok()

        # update/create remaining positions
        for task in self.Project.TasksWithCostsAllocated:
            position = self.Positions.KeywordQuery(
                task_object_id=task.cdb_object_id, generated_from_task=1
            )
            if self.CostSignificance.id == "ACTU":
                start_time = task.start_time_act
                end_time = task.end_time_act
                effort = task.effort_act if task.effort_act else 0.0
            else:
                start_time = (
                    task.start_time_fcast
                    if task.start_time_fcast
                    else task.start_time_plan
                )
                end_time = (
                    task.end_time_fcast if task.end_time_fcast else task.end_time_plan
                )
                effort = task.effort_fcast if task.effort_fcast else task.effort_plan
            costs = effort * task.hourly_rate
            costs_proj_curr = costs
            if task.currency_object_id != self.Project.currency_object_id:
                costs_proj_curr = task.Currency.convertTo(
                    self.Project.currency_object_id,
                    costs,
                    cdb_project_id=self.cdb_project_id,
                )
            chg_ctrl = CostPosition.MakeChangeControlAttributes()
            attrs = {
                "costsheet_object_id": self.cdb_object_id,
                "name_de": task.task_name,
                "name_en": task.task_name,
                "hourly_rate": task.hourly_rate,
                "effort": effort,
                "costs": costs,
                "costs_proj_curr": costs_proj_curr,
                "currency_object_id": task.currency_object_id,
                "costtype_object_id": task.costtype_object_id,
                "costcenter_object_id": task.costcenter_object_id,
                "costplant_object_id": task.costplant_object_id,
                "calc_object_id": self.calc_object_id,
                "cdb_mdate": chg_ctrl["cdb_mdate"],
                "cdb_mpersno": chg_ctrl["cdb_mpersno"],
            }
            if "component_object_id" in self:
                attrs["component_object_id"] = self.component_object_id

            if position:
                for p in position:
                    if p.period_from_task:
                        attrs.update(
                            **{
                                "start_time": start_time,
                                "end_time": end_time,
                            }
                        )
                    p.Update(**attrs)
            else:
                t = sqlapi.SQLselect(
                    f"MAX(position) FROM cdbpcs_cost_position WHERE costsheet_object_id='{self.cdb_object_id}'"
                )
                max_pos = sqlapi.SQLinteger(t, 0, 0)
                attrs.update(
                    **{
                        "generated_from_task": 1,
                        "task_object_id": task.cdb_object_id,
                        "period_from_task": 1,
                        "start_time": start_time,
                        "end_time": end_time,
                        "position": max_pos + 1,
                        "cdb_project_id": self.cdb_project_id,
                        "cdb_cdate": chg_ctrl["cdb_cdate"],
                        "cdb_cpersno": chg_ctrl["cdb_cpersno"],
                    }
                )
                CostPosition.Create(**attrs)
        self.refreshTreeNodes()

    @classmethod
    def createSheet(cls, project, **params):
        if not project or not project.allowCostSheetChanges():
            return None
        kwargs = cls.getDefaults(newIndex=True, project=project)
        kwargs.update(cdb_project_id=project.cdb_project_id)
        kwargs.update(**params)
        return operation(constants.kOperationNew, cls, **kwargs)


class CostSheetFolder(Object):
    __maps_to__ = "cdbpcs_costsheet_folder"
    __classname__ = "cdbpcs_costsheet_folder"

    CostSheet = Reference_1(fCostSheet, fCostSheetFolder.costsheet_object_id)
    ParentFolder = Reference_1(fCostSheetFolder, fCostSheetFolder.parent_object_id)
    SubFolders = Reference_N(
        fCostSheetFolder,
        fCostSheetFolder.parent_object_id == fCostSheetFolder.cdb_object_id,
    )
    CostSheetFolderPositions = Reference_N(
        fCostSheetFolderPosition,
        fCostSheetFolderPosition.costsheet_folder_object_id
        == fCostSheetFolder.cdb_object_id,
    )

    event_map = {
        (("create", "copy"), ("pre_mask")): ("setDefaults", "setPosition"),
    }

    def setDefaults(self, ctx):
        ctx.set("cdb_obsolete", 0)
        ctx.set("folder_costs", 0)
        ctx.set("folder_efforts", 0)
        if ctx.relationship_name == "cdbpcs_costsheetfolder2subfolder":
            if ctx.parent:
                csf = CostSheetFolder.ByKeys(ctx.parent.cdb_object_id)
                if csf:
                    cs_oid = getattr(csf, "costsheet_object_id", "")
                    ctx.set("costsheet_object_id", cs_oid)
                    self.costsheet_object_id = cs_oid

    def calculateEffortCosts(self):
        costs = 0.0
        effort = 0.0
        for f in self.SubFolders:
            costs += f.folder_costs if f.folder_costs else 0
            effort += f.folder_effort if f.folder_effort else 0
        for csfp in self.CostSheetFolderPositions:
            if csfp.CostPosition and csfp.CostPosition.cdb_obsolete == 0:
                costs += (
                    csfp.CostPosition.costs_proj_curr
                    if csfp.CostPosition.costs_proj_curr
                    else 0
                )
                effort += csfp.CostPosition.effort if csfp.CostPosition.effort else 0
        self.Update(folder_costs=costs, folder_effort=effort)
        if self.ParentFolder:
            self.ParentFolder.calculateEffortCosts()

    def recalculateEffortCosts(self, currency_object_id):
        costs = 0.0
        effort = 0.0
        for csfp in self.CostSheetFolderPositions:
            if csfp.CostPosition and csfp.CostPosition.cdb_obsolete == 0:
                costs += (
                    csfp.CostPosition.costs_proj_curr
                    if csfp.CostPosition.costs_proj_curr
                    else 0
                )
                effort += csfp.CostPosition.effort if csfp.CostPosition.effort else 0
        for f in self.SubFolders:
            f.recalculateEffortCosts(currency_object_id)
            costs += f.folder_costs if f.folder_costs else 0
            effort += f.folder_effort if f.folder_effort else 0
        self.Update(folder_costs=costs, folder_effort=effort)

    def setPosition(self, ctx):
        t = sqlapi.SQLselect(
            f"MAX(position) FROM cdbpcs_costsheet_folder WHERE costsheet_object_id='{self.costsheet_object_id}' and parent_object_id = '{self.parent_object_id}' "
        )
        max_pos = sqlapi.SQLinteger(t, 0, 0)
        if max_pos:
            ctx.set("position", max_pos + 10)
        else:
            ctx.set("position", 10)

    @classmethod
    def resetPosition(cls, costsheet_object_id, parent_object_id=""):
        cfs = CostSheetFolder.KeywordQuery(
            costsheet_object_id=costsheet_object_id,
            parent_object_id=parent_object_id,
            order_by="position",
        )
        pos = 10
        for cf in cfs:
            cf.position = pos
            pos += 10
            CostSheetFolder.resetPosition(
                costsheet_object_id, parent_object_id=cf.cdb_object_id
            )


class CostPosition(Object, briefcases.BriefcaseContent, WithSharing):
    __maps_to__ = "cdbpcs_cost_position"
    __classname__ = "cdbpcs_cost_position"

    CostSheet = Reference_1(fCostSheet, fCostPosition.costsheet_object_id)
    CostCenter = Reference_1(fCostCenter, fCostPosition.costcenter_object_id)
    CostType = Reference_1(fCostType, fCostPosition.costtype_object_id)
    Project = Reference_1(fProject, fCostPosition.cdb_project_id)
    Task = Reference_1(fTask, fTask.cdb_object_id == fCostPosition.task_object_id)
    CostSheetFolderPosition = Reference_1(
        fCostSheetFolderPosition,
        fCostSheetFolderPosition.costpos_object_id == fCostPosition.cdb_object_id,
    )
    Currency = Reference_1(fCurrency, fCostPosition.currency_object_id)

    event_map = {
        ("create", "pre_mask"): ("setDefaults", "setPosition"),
        ("copy", "pre_mask"): ("resetGenerated", "setPosition"),
        ("copy", "pre"): (
            "setCopyDefaults",
            "resetTaskReferences",
        ),
        (("create", "copy", "modify"), ("pre_mask", "dialogitem_change")): (
            "setHourlyRate",
            "setStartAndEnd",
            "updateMaskFields",
        ),
        (("create", "copy", "modify"), ("pre")): "updateProjectCurrencyCosts",
        (("create", "copy", "modify", "delete"), "post"): (
            "recalculateEffortCosts",
            "refreshTree",
        ),
    }

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the CostSheet and the CostPosition itself.
        """
        return [self, self.CostSheet]

    def setDefaults(self, ctx):
        ctx.set("cdb_obsolete", 0)

        if self.CostSheet:
            ctx.set("cdb_project_id", self.CostSheet.cdb_project_id)
            ctx.set("currency_object_id", self.CostSheet.currency_object_id)
        else:
            if ctx.relationship_name == "cdbpcs_costsheetfolder2positions":
                if ctx.parent:
                    csf = CostSheetFolder.ByKeys(ctx.parent.cdb_object_id)
                    if csf:
                        ctx.set("costsheet_object_id", csf.costsheet_object_id)
                        self.costsheet_object_id = csf.costsheet_object_id
                        cs = CostSheet.ByKeys(csf.costsheet_object_id)
                        if cs:
                            ctx.set("cdb_project_id", cs.cdb_project_id)
                            ctx.set("currency_object_id", cs.currency_object_id)

    def setCopyDefaults(self, ctx):
        self.cdb_obsolete = 0
        if self.cdb_project_id != ctx.cdbtemplate.cdb_project_id:
            self.period_from_task = 0
            self.start_time = ""
            self.end_time = ""
        if self.generated_from_task and self.Task:
            new_task = Task.ByKeys(template_object_id=self.task_object_id)
            if new_task:
                self.task_object_id = new_task.cdb_object_id
                self.template_object_id = ctx.cdbtemplate.cdb_object_id

    def resetGenerated(self, ctx):
        ctx.set("generated_from_task", 0)
        ctx.set("cdb_obsolete", 0)

    def updateMaskFields(self, ctx):
        if self.CheckAccess("save"):
            readonly_fields = []
            writable_fields = []

            if self.CostType:
                if self.CostType.isGatheredAsEffort():
                    readonly_fields.append("costs")
                    writable_fields.append("effort")
                    writable_fields.append("hourly_rate")
                else:
                    if self.effort:
                        ctx.set("effort", None)
                    if self.hourly_rate:
                        ctx.set("hourly_rate", None)
                    readonly_fields.append("effort")
                    readonly_fields.append("hourly_rate")
                    writable_fields.append("costs")
            if self.generated_from_task:
                readonly_fields = [
                    "costtype_object_id",
                    "costcenter_object_id",
                    "costplant_object_id",
                    "period_from_task",
                    "task_object_id",
                    "effort",
                    "costs",
                    "hourly_rate",
                    "currency_name",
                    "name",
                ]
            if writable_fields:
                ctx.set_fields_writeable(writable_fields)
            if readonly_fields:
                ctx.set_fields_readonly(readonly_fields)
        ctx.set(constants.kArgumentEnableApply, "0")

    def setHourlyRate(self, ctx):
        """
        For project costs adopt the hourly rate from the cost center, but only if the cost type is gathered as effort
        """
        if self.Project:
            if (
                getattr(ctx, "changed_item", None) == "costcenter_object_id"
                and self.CostType
                and self.CostType.isGatheredAsEffort()
                and self.CostCenter
                and self.CostCenter.hourly_rate
            ):
                ctx.set("hourly_rate", self.CostCenter.hourly_rate)
                ctx.set("currency_name", self.CostCenter.Currency.name)
                ctx.set(
                    "costs", float(ctx.dialog.effort) * self.CostCenter.hourly_rate
                ) if ctx.dialog.effort else 0.0
        # TODO: elif self.Calculation

    def setPosition(self, ctx):
        t = sqlapi.SQLselect(
            f"MAX(position) FROM cdbpcs_cost_position WHERE costsheet_object_id='{self.costsheet_object_id}'"
        )
        max_pos = sqlapi.SQLinteger(t, 0, 0)
        if max_pos:
            ctx.set("position", max_pos + 10)
        else:
            ctx.set("position", 10)

    def setStartAndEnd(self, ctx):
        """Auto fill position's 'start_time' and 'end_time' depending on task association"""
        if self.CheckAccess("save"):
            ctx.set_fields_writeable(["start_time", "end_time", "period_from_task"])
            if self.Task:
                if getattr(ctx, "changed_item", None) in [
                    "task_object_id",
                    "period_from_task",
                ]:
                    if ctx.changed_item == "task_object_id":
                        ctx.set("period_from_task", 1)
                        self.period_from_task = 1
                    if self.period_from_task:
                        if self.Task.start_time_fcast:
                            ctx.set("start_time", self.Task.start_time_fcast)
                        if self.Task.end_time_fcast:
                            ctx.set("end_time", self.Task.end_time_fcast)
                if self.period_from_task:
                    ctx.set_fields_readonly(["start_time", "end_time"])
            else:
                if self.period_from_task:
                    ctx.set("period_from_task", 0)
                ctx.set_readonly("period_from_task")

    def updateProjectCurrencyCosts(self, ctx):
        if self.CostType.isGatheredAsEffort():
            self.costs = (self.effort if self.effort else 0.0) * (
                self.hourly_rate if self.hourly_rate else 0.0
            )
        if self.currency_object_id != self.Project.currency_object_id:
            self.costs_proj_curr = self.Currency.convertTo(
                self.Project.currency_object_id,
                self.costs,
                cdb_project_id=self.cdb_project_id,
            )
        else:
            self.costs_proj_curr = self.costs

    def recalculateEffortCosts(self, ctx=None):
        if self.CostSheetFolderPosition:
            self.CostSheetFolderPosition.CostSheetFolder.calculateEffortCosts()
        elif self.costsheet_folder_object_id:
            CostSheetFolder.ByKeys(
                self.costsheet_folder_object_id
            ).calculateEffortCosts()

    def resetTaskReferences(self, ctx):
        if self.cdb_project_id == ctx.cdbtemplate.cdb_project_id:
            return
        # copying from another project, so look for new task in new project
        cond = "cdb_project_id='%s' and template_oid='%s'" % (
            self.cdb_project_id,
            self.task_object_id,
        )
        rset = sqlapi.RecordSet2(
            table=Task.GetTableName(), condition=cond, columns=["cdb_object_id"]
        )
        if len(rset) > 0:
            self.task_object_id = rset[0].cdb_object_id
        else:
            self.task_object_id = ""
            self.period_from_task = 0

    def refreshTree(self, ctx):
        refresh_children = True
        if self.CostSheetFolderPosition:
            util.refresh_structure_node(self.CostSheetFolderPosition.cdb_object_id)
            refresh_children = False
        util.refresh_structure_node(
            self.costsheet_object_id, refresh_children=refresh_children
        )


class CostSheetFolderPosition(Object):
    __maps_to__ = "cdbpcs_csfolder2costpos"
    __classname__ = "cdbpcs_csfolder2costpos"

    CostSheetFolder = Reference_1(
        fCostSheetFolder, fCostSheetFolderPosition.costsheet_folder_object_id
    )
    CostPosition = Reference_1(
        fCostPosition, fCostSheetFolderPosition.costpos_object_id
    )

    event_map = {
        (("create", "copy"), "pre"): "ensureSheet",
        (("create", "copy"), "post"): "ensureCardinality",
        (("create", "copy", "delete"), "post"): (
            "recalculateEffortCosts",
            "refreshTreeViews",
        ),
    }

    def ensureSheet(self, ctx):
        if self.CostSheetFolder and self.CostPosition:
            if (
                self.CostSheetFolder.costsheet_object_id
                != self.CostPosition.costsheet_object_id
            ):
                raise ue.Exception("cdbpcs_cost_postion_sheet_error")

    def ensureCardinality(self, ctx):
        if self.CostPosition:
            csfp = CostSheetFolderPosition.Query(
                f"costpos_object_id = '{self.CostPosition.cdb_object_id}' and costsheet_folder_object_id != '{self.costsheet_folder_object_id}'"
            )
            if csfp:
                csfp.Delete()

    def recalculateEffortCosts(self, ctx):
        if self.CostSheetFolder:
            self.CostSheetFolder.CostSheet.refreshCurrencyConversion()

    def refreshTreeViews(self, ctx):
        if self.CostPosition and (
            ctx.dragged_obj_parent_keys or ctx.action == "delete"
        ):
            util.refresh_structure_node(self.CostPosition.costsheet_object_id)


@sig.connect(Project, "copy_project_hook")
def copy_sheets(tmpl_project, new_project):
    if not tmpl_project:
        return
    from cdb import auth, util
    from cdb.objects import org
    from cs.pcs.projects import PersonAssignment

    pm = org.Person.ByKeys(auth.persno)
    delete_role = False
    if not PersonAssignment.KeywordQuery(
        subject_id=pm.personalnummer,
        role_id=PROJECTCOSTROLE,
        cdb_project_id=new_project.cdb_project_id,
    ):
        tm = new_project.assignTeamMember(pm)
        pcm = new_project.createRole(PROJECTCOSTROLE)
        pcm.assignSubject(pm)
        util.reload_cache(util.kCGAccessSystem, util.kLocalReload)
        delete_role = True

    for sheet in tmpl_project.ValidCostSheets:
        sheet.copySheet(cdb_project_id=new_project.cdb_project_id)

    if delete_role:
        tm.Delete()
        pcm.Delete()
        PersonAssignment.KeywordQuery(
            subject_id=pm.personalnummer,
            role_id=PROJECTCOSTROLE,
            cdb_project_id=new_project.cdb_project_id,
        ).Delete()
        util.reload_cache(util.kCGAccessSystem, util.kLocalReload)
