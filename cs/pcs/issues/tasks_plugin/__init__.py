# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import ue
from cs.taskmanager.mixin import WithTasksIntegration

from cs.pcs.projects.common import assert_team_member

PROCEED_FLAG = "cs.taskmanager.proceed"


class IssueWithCsTasks(WithTasksIntegration):
    def getCsTasksContexts(self):
        return [self.Project]

    def csTasksDelegate_get_default(self):
        return self.csTasksDelegate_get_project_manager()

    def csTasksDelegate(self, ctx):
        prj_id = None
        for obj in ctx.objects:
            if not prj_id:
                prj_id = obj["cdb_project_id"]
            if prj_id and prj_id != obj["cdb_project_id"]:
                raise ue.Exception("cdbpcs_delegate")
        assert_team_member(ctx, self.cdb_project_id)
        self.Super(IssueWithCsTasks).csTasksDelegate(ctx)

    def preset_csTasksDelegate(self, ctx):
        prj_id = None
        for obj in ctx.objects:
            if not prj_id:
                prj_id = obj["cdb_project_id"]
            if prj_id and prj_id != obj["cdb_project_id"]:
                raise ue.Exception("cdbpcs_delegate")
        ctx.set("cdb_project_id", prj_id)
        self.Super(IssueWithCsTasks).preset_csTasksDelegate(ctx)

    def getCsTasksBasePriority(self, request=None):
        if self.priority == "hoch":
            return self.PRIO_MEDIUM
        if self.priority == "kritisch":
            return self.PRIO_HIGH
        return self.PRIO_LOW

    def getCsTasksNextStatuses(self):
        result = super().getCsTasksNextStatuses()
        for target in result:
            target["dialog"]["zielstatus_int"] = target["status"]
        return result
