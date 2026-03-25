#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_N, ReferenceMethods_N
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.vp.items import Item

fTaskItemReference = Forward(__name__ + ".TaskItemReference")


class TaskItemReference(Object):
    __maps_to__ = "cdbpcs_part2task"
    __classname__ = "cdbpcs_part2task"

    Item = Reference_1(Item, fTaskItemReference.teilenummer, fTaskItemReference.t_index)
    Task = Reference_1(
        Task, fTaskItemReference.cdb_project_id, fTaskItemReference.task_id
    )

    def on_create_pre(self, ctx=None):
        if not self.rel_type:
            self.rel_type = "part2task"


@classbody
class Task(object):
    ItemReferences = Reference_N(
        TaskItemReference,
        TaskItemReference.cdb_project_id == Task.cdb_project_id,
        TaskItemReference.task_id == Task.task_id,
    )
    Items = ReferenceMethods_N(
        Item, lambda self: [ref.Item for ref in self.ItemReferences]
    )


@classbody
class Project(object):
    Items = Reference_N(Item, Item.cdb_t_project_id == Project.cdb_project_id)

    def check_items_delete_pre(self, ctx):
        if self.Items:
            raise ue.Exception("pcs_err_del_proj3")

    @sig.connect(Project, "delete", "pre")
    def _check_items_delete_pre(self, ctx):
        self.check_items_delete_pre(ctx)

    @sig.connect(Project, "delete", "post")
    def _part_relation_delete_post(self, ctx):
        rel = "cdbpcs_part2task"
        sqlapi.SQLdelete(
            "from %s where cdb_project_id = '%s'" % (rel, self.cdb_project_id)
        )


@classbody
class Item(object):
    Project = Reference_1(Project, Item.cdb_t_project_id)
