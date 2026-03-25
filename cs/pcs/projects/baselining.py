#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import logging
from datetime import datetime

from cdb import sig, sqlapi, transactions, typeconversion, ue, util
from cdb.classbody import classbody
from cdb.constants import kOperationDelete
from cdb.objects import Forward, operations
from cdb.storage.index import object_updater, updaters
from cs.baselining.support import BaselineTools, BaseliningNotSupportedError

from cs.pcs.projects import Project
from cs.pcs.projects.common.sql_mass_data import sql_mass_copy
from cs.pcs.projects.tasks import Task

fBaselineHead = Forward("cs.baselining.Baseline")
CANNOT_MODIFY_ERROR_MESSAGE_DEFAULT = "cdbpcs_cannot_modify_baselined"
CANNOT_MODIFY_ERROR_MESSAGES = {
    "create": "cdbpcs_cannot_create_baselined",
    "copy": "cdbpcs_cannot_create_baselined",
    "delete": "cdbpcs_cannot_delete_baselined",
}


@sig.connect(Project, "create", "pre")
@sig.connect(Project, "copy", "pre")
@sig.connect(Project, "modify", "pre")
@sig.connect(Project, "delete", "pre")
@sig.connect(Project, "state_change", "pre")
@sig.connect(Project, "create", "pre_mask")
@sig.connect(Project, "copy", "pre_mask")
@sig.connect(Project, "modify", "pre_mask")
@sig.connect(Project, "delete", "pre_mask")
@sig.connect(Project, "wf_step", "pre_mask")
@sig.connect(Task, "create", "pre")
@sig.connect(Task, "copy", "pre")
@sig.connect(Task, "modify", "pre")
@sig.connect(Task, "delete", "pre")
@sig.connect(Task, "state_change", "pre")
@sig.connect(Task, "create", "pre_mask")
@sig.connect(Task, "copy", "pre_mask")
@sig.connect(Task, "modify", "pre_mask")
@sig.connect(Task, "delete", "pre_mask")
@sig.connect(Task, "wf_step", "pre_mask")
def modification_pre(self, ctx):
    """
    Prevent modification of baselined project or task.

    - They must not be created interactively or modified at all
        (baselines should be immutable snapshots)
    - They must not be deleted interactively
        (relship profiles would delete related data of the original,
        such as roles)
    """
    if self.ce_baseline_id:
        message = CANNOT_MODIFY_ERROR_MESSAGES.get(
            ctx.action,
            CANNOT_MODIFY_ERROR_MESSAGE_DEFAULT,
        )
        raise util.ErrorMessage(message)


@sig.connect(Project, "query", "pre")
@sig.connect(Project, "requery", "pre")
@sig.connect(Task, "query", "pre")
@sig.connect(Task, "requery", "pre")
def enhance_search_condition(self, ctx):
    """
    Always search for non-baselines if ``ce_baseline_id``
    is not part of the dialog (which is the default).
    """
    id_field = "ce_baseline_id"
    if id_field not in ctx.dialog.get_attribute_names():
        ctx.set(id_field, '=""')


@classbody
class Project:
    def copy_baseline_elements(self, ce_baseline_id, restore=False):
        """
        Creates baseline copies of this project and all of its tasks.

        :param ce_baseline_id: The UUID of the baseline
            the copied project is to represent.
        :type ce_baseline_id: str

        :param restore: Unsupported
        :type restore: bool

        :returns: The copied project representing the baseline
        :rtype: cs.pcs.projects.Project

        :raises NotImplementedError: if ``restore`` is ``True``
        """
        if restore:
            raise NotImplementedError

        values = {
            "ce_baseline_id": ce_baseline_id,
            "ce_baseline_origin_id": "",
            "ce_baseline_object_id": self.cdb_object_id,
        }

        baselined_project = self.Copy(**values)

        sql_mass_copy(
            "cdbpcs_task",
            f"cdb_project_id = '{self.cdb_project_id}' AND ce_baseline_id = ''",
            values,
        )

        return baselined_project

    @sig.connect(Project, "ce_baseline_create", "pre_mask")
    def create_baseline_pre_mask(self, _):
        if BaselineTools.is_baseline(self):
            raise util.ErrorMessage("cdbpcs_cannot_baseline_baseline")

    @sig.connect(Project, "ce_baseline_create", "post_mask")
    def create_baseline_post_mask(self, ctx):
        if not ctx.dialog.ce_baseline_name:
            timestamp = typeconversion.to_user_repr_date_format(datetime.now())
            ctx.set("ce_baseline_name", timestamp)

    def check_baseline_name_unique(self, ctx):
        name = ctx.dialog.ce_baseline_name

        if not name:
            return

        existing_baseline = sqlapi.RecordSet2(
            sql="SELECT 1 FROM ce_baseline "
            f"WHERE ce_baseline_name = '{name}' "
            "AND cdb_object_id IN ("
            "  SELECT ce_baseline_id "
            "  FROM cdbpcs_project "
            f"  WHERE cdb_project_id = '{self.cdb_project_id}'"
            ")"
        )

        if existing_baseline:
            raise util.ErrorMessage("cdbpcs_baseline_name_not_unique")

    @sig.connect(Project, "ce_baseline_create", "now")
    def create_baseline(self, ctx):
        self.check_baseline_name_unique(ctx)

        try:
            _, baselined_project = BaselineTools.create_baseline(
                obj=self,
                name=ctx.dialog.ce_baseline_name,
                comment=ctx.dialog.ce_baseline_comment,
            )
        except (ValueError, BaseliningNotSupportedError) as exc:
            logging.exception("create_baseline %s", self._key_dict())
            raise util.ErrorMessage("cdbpcs_cannot_baseline_baseline") from exc

        if baselined_project:
            ctx.set_object_result(baselined_project)

    def remove_all_baseline_elements(self, ce_baseline_id, check_access):
        if not check_access or self.CheckAccess("save"):
            with transactions.Transaction():
                for table in ["cdbpcs_task", "cdbpcs_project"]:
                    sqlapi.SQLdelete(
                        f"FROM {table} "
                        f"WHERE cdb_project_id = '{self.cdb_project_id}' "
                        f"AND ce_baseline_id = '{ce_baseline_id}'"
                    )
        else:
            raise ue.Exception(
                "just_a_replacement", f"Not allowed: {self.GetDescription()}"
            )

    @sig.connect(Project, "delete", "post")
    def delete_baselines(self, ctx):
        if ctx.error:
            return

        baselines = fBaselineHead.KeywordQuery(
            ce_baselined_object_id=self.cdb_object_id,
        )
        with util.SkipAccessCheck():
            for baseline in baselines:
                operations.operation(kOperationDelete, baseline)
                self.remove_all_baseline_elements(baseline.cdb_object_id, False)


class BaselineUpdater(object_updater.ObjectUpdater):
    """Do NOT index baselines (task, project) for EnterpriseSearch."""

    def update(self):
        # if object has a non empty ce_baseline_id do not index it
        if self._object_handle and self._object_handle.ce_baseline_id:
            return False

        return super().update()

    @classmethod
    def setup(cls):
        factory = updaters.IndexUpdaterFactory()
        factory.add_updater("cdbpcs_project", BaselineUpdater)
        factory.add_updater("cdbpcs_task", BaselineUpdater)


BaselineUpdater.setup()
