#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import ue
from cs.taskmanager.mixin import WithTasksIntegration

from cs.pcs.projects.common import assert_team_member


def assert_single_project(ctx):
    prj_id = None
    bid = None

    for obj in ctx.objects:
        if not prj_id:
            prj_id = obj["cdb_project_id"]
            bid = obj["ce_baseline_id"]

        if (prj_id and prj_id != obj["cdb_project_id"]) and (
            bid and bid != obj["ce_baseline_id"]
        ):
            raise ue.Exception("cdbpcs_delegate")

    return prj_id, bid


class TaskWithCsTasks(WithTasksIntegration):
    def getCsTasksContexts(self):
        return [self.Project]

    def csTasksDelegate_get_default(self):
        return self.csTasksDelegate_get_project_manager()

    def csTasksDelegate(self, ctx):
        assert_single_project(ctx)
        assert_team_member(ctx, self.cdb_project_id)
        self.Super(TaskWithCsTasks).csTasksDelegate(ctx)

    def preset_csTasksDelegate(self, ctx):
        prj_id, bid = assert_single_project(ctx)
        ctx.set("cdb_project_id", prj_id)
        ctx.set("ce_baseline_id", bid)
        self.Super(TaskWithCsTasks).preset_csTasksDelegate(ctx)
