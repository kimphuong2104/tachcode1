#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import six

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import constants, misc, sig, ue
from cdb.classbody import classbody
from cdb.objects import Forward, Reference_1
from cdb.objects.operations import operation
from cs.pcs.projects.tasks import Task

fTask = Forward("cs.pcs.projects.tasks.Task")
fCostCenter = Forward("cs.pcs.costs.definitions.CostCenter")
fCurrency = Forward("cs.currency.Currency")


def __log__(txt, lvl=7):
    misc.cdblogv(misc.kLogMsg, lvl, six.text_type(txt))


class TaskPathAlreadyAllocatedException(ue.Exception):
    def __init__(self, task):
        super(TaskPathAlreadyAllocatedException, self).__init__(
            "cdbpcs_cost_task_path_already_allocated", task.GetDescription()
        )


@classbody  # noqa
class Task(object):
    PROJECTCOSTS_RELATED_FIELDS = [
        "costs_allocated",
        "hourly_rate",
        "currency_object_id",
        "costtype_object_id",
        "costcenter_object_id",
        "currency_name",
    ]

    CostCenter = Reference_1(fCostCenter, fTask.costcenter_object_id)
    Currency = Reference_1(fCurrency, fTask.currency_object_id)

    event_map = {
        (
            ("create", "copy", "modify"),
            ("pre_mask", "dialogitem_change"),
        ): "adjustCostFieldsInMask",
        (("create", "copy", "modify"), "pre"): "ensureUniqueCostsInTaskPath",
        (("create", "copy", "modify"), "post"): "ensure_allocated_costs_removed",
    }

    def costsAreAllocated(self, raise_on_allocation=False):
        if self.costs_allocated == 1:
            if raise_on_allocation:
                raise TaskPathAlreadyAllocatedException(self)
            return True
        return False

    def adjustCostFieldsInMask(self, ctx):
        toggled_fields = self.PROJECTCOSTS_RELATED_FIELDS[:]
        if self.costs_allocated is None:
            ctx.set("costs_allocated", 0)
        try:
            # disable and clear all cost related fields when the costs
            # of any parent or child task are already allocated
            if not (ctx.action == "create" and ctx.mode == "pre_mask"):
                # checking this in create_pre_mask event is unnecessary and misleading
                for task in self.AllParentTasks + self.AllSubTasks:
                    task.costsAreAllocated(True)
        except TaskPathAlreadyAllocatedException:
            for field in toggled_fields:
                # don't set costs_allocated to None since it's not nullable
                if getattr(self, field, None):
                    ctx.set(field, "0" if (field == "costs_allocated") else None)
            ctx.set_fields_readonly(toggled_fields)
        else:
            if self.costsAreAllocated():
                if not self.Project:
                    raise ue.Exception("cdbpcs_costs_missing_project")
                if not self.Project.currency_object_id:
                    raise ue.Exception("cdbpcs_cost_missing_project_currency")
                if (
                    ctx
                    and ctx.dialog
                    and (
                        "currency_object_id" not in ctx.dialog.get_attribute_names()
                        or not ctx.dialog.currency_object_id
                    )
                ):
                    ctx.set("currency_object_id", self.Project.currency_object_id)
                    ctx.set("currency_name", self.Project.Currency.name)
                # p.r.n. adopt the hourly_rate from the cost center,
                if (
                    getattr(ctx, "changed_item", None) == "costcenter_object_id"
                    and self.CostCenter
                    and self.CostCenter.hourly_rate
                ):
                    ctx.set("hourly_rate", self.CostCenter.hourly_rate)
                    ctx.set("currency_name", self.CostCenter.Currency.name)
                    ctx.set("currency_object_id", self.CostCenter.currency_object_id)

                toggled_fields.remove("costs_allocated")
                ctx.set_fields_writeable(toggled_fields)
                toggled_fields.remove("costcenter_object_id")
                if ctx.mode == "pre_mask":
                    ctx.set_fields_mandatory(toggled_fields)
                else:
                    ctx.set_mandatory(toggled_fields)
            else:
                # disable and clear everything except of "costs_allocated"
                toggled_fields.remove("costs_allocated")
                for field in toggled_fields:
                    if getattr(self, field, None):
                        ctx.set(field, None)
                ctx.set_fields_readonly(toggled_fields)
                toggled_fields.remove("costcenter_object_id")
                ctx.set_optional(toggled_fields)

    def ensureUniqueCostsInTaskPath(self, ctx):
        if self.costsAreAllocated():
            for task in self.AllParentTasks + self.AllSubTasks:
                task.costsAreAllocated(True)

    def ensure_allocated_costs_removed(self, ctx):
        if not self.costs_allocated:
            from cs.pcs.costs.sheets import CostPosition

            cps = CostPosition.KeywordQuery(task_object_id=self.cdb_object_id)
            for cp in cps:
                operation(constants.kOperationDelete, cp)


@sig.connect(Task, "collect_additional_info_before_create_from_template")
def checkAllParentTasksOfNewTaskForCostAllocation(sig_args):
    # signal 'collect_additional_info_before_create_from_template' is emitted
    # during Create from Template for Tasks.
    # The field "target_parent" include the object the task to be created from
    # template will be added under.
    # If that new parent object is a task, we check if it or any of it's
    # ParentTasks has allocated costs.
    # If so we hand back the information, that the task to be created from
    # template as well as all it's subtasks have to have no cost allocation
    # in the form of a key value pair.
    return_value = False
    if "target_parent" in sig_args:
        target_parent = sig_args["target_parent"]
        if isinstance(target_parent, Task):
            all_parents = [target_parent] + target_parent.AllParentTasks
            return_value = any([t.costsAreAllocated() for t in all_parents])
    return {"remove_cost_allocation": return_value}


@sig.connect(Task, "modify_new_task_created_from_template")
def determineChangesForNewTaskFromTemplate(sig_args):
    # signal 'modify_new_task_created_from_template' is emitted during
    # 'Create from Template' for Tasks, once for the newly created task and
    # each of its copied subtasks.
    # If value of key 'remove_cost_allocation' is True, we give back a mapping
    # of all projectcost related fields and their new empty values to
    # deactivate cost allocation for the newly created task

    changes = {}
    if "params" in sig_args and "new_task" in sig_args:
        params = sig_args["params"]
        new_task = sig_args["new_task"]
        remove_allocation = False
        if "remove_cost_allocation" in params:
            remove_allocation = params["remove_cost_allocation"]
        if (
            remove_allocation
            and isinstance(new_task, Task)
            and new_task.costsAreAllocated()
        ):
            changes = {
                "costs_allocated": False,
                "hourly_rate": None,
                "currency_object_id": None,
                "costtype_object_id": None,
                "costcenter_object_id": None,
                "currency_name": None,
            }
    return changes


@sig.connect(Task, "copy_task_hook")
def copy_generated_cost_positions(old_task, _, new_task):
    if old_task.costs_allocated:
        new_task.Update(template_object_id=old_task.cdb_object_id)
