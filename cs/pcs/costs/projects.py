#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import ue
from cdb.classbody import classbody
from cdb.objects import Forward, Reference_1, Reference_Methods, Reference_N
from cs.currency import Currency
from cs.pcs.projects import Project, kProjectManagerRole
from cs.pcs.projects.tasks import Task

fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")
fCurrency = Forward("cs.currency.Currency")
fCostSheet = Forward("cs.pcs.costs.sheets.CostSheet")
fCostPosition = Forward("cs.pcs.costs.sheets.CostPosition")


@classbody  # noqa
class Project(object):
    ValidCostSheets = Reference_N(
        fCostSheet,
        fCostSheet.cdb_project_id == fProject.cdb_project_id,
        fCostSheet.cdb_obsolete == 0,
    )
    CostSheets = Reference_N(
        fCostSheet, fCostSheet.cdb_project_id == fProject.cdb_project_id
    )
    ValidCostPositions = Reference_Methods(
        fCostPosition,
        lambda self: self._allValidPositions(),  # pylint: disable=protected-access
    )
    TasksWithCostsAllocated = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.costs_allocated == 1,
        fTask.status != Task.DISCARDED.status,
    )
    Currency = Reference_1(fCurrency, fProject.currency_object_id)

    def _allValidPositions(self):
        result = []
        for vcs in self.ValidCostSheets:
            result.append(vcs.Positions)
        return result

    event_map = {
        ("modify", "pre"): "fixateCosts",
        ("wf_step", "post"): "adjustCostSheetStatus",
        ("create", "post"): "createProjectCostManagement",
        ("create", "pre_mask"): "setDefaultCurrency",
    }

    def fixateCosts(self, ctx):
        if self.ValidCostPositions:
            if ctx.object.currency_object_id != self.currency_object_id:
                if 250 in self.ValidCostSheets.status or not self.currency_object_id:
                    raise ue.Exception("cdbpcs_cost_currency_must_not_be_changed")
                else:
                    for sheet in self.CostSheets:
                        sheet.refreshCurrencyConversion(
                            currency_object_id=self.currency_object_id
                        )

    def adjustCostSheetStatus(self, ctx):
        if not ctx.error and self.status in [180, 200]:
            if self.status == 180:
                for sheet in self.CostSheets:
                    if sheet.status not in (180, 190):
                        sheet.ChangeState(self.status)
            elif self.status == 200:
                for sheet in self.ValidCostSheets:
                    if sheet.status == 0:
                        sheet.ChangeState(250)

    def createProjectCostManagement(self, ctx):
        pcm = self.createRole("Project Cost Management")
        pm = self.getRole(kProjectManagerRole)
        if not pm:
            pm = self.createRole(kProjectManagerRole)
        pcm.assignSubject(pm)

    def setDefaultCurrency(self, ctx):
        ctx.set("currency_object_id", Currency.getDefaultCurrency().cdb_object_id)

    def allowCostSheetChanges(self):
        return self.status in [0, 50]
