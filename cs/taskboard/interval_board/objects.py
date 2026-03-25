#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig
from cdb.constants import kOperationNew
from cdb.util import SkipAccessCheck
from cdb.objects.operations import operation
from cs.taskboard.objects import Board
from cs.taskboard.objects import Iteration
from cs.taskboard.interval_board import INTERVAL_BOARD_TYPE


@sig.connect(Iteration, "create", "pre_mask")
@sig.connect(Iteration, "create", "pre")
def init_interval_values(self, ctx):
    if self.Board and self.Board.board_type == INTERVAL_BOARD_TYPE:
        count = len(self.Board.Iterations)
        changes = {}
        if not self.title:
            changes.update(title=self.generateName())
        if not self.description:
            changes.update(description="")
        if not self.start_date and not self.end_date:
            last_sprint = self.Board.Iterations[count - 1] if count else None
            changes.update(self.Board._next_iteration_timeframe(last_iteration=last_sprint))
        self.Update(**changes)


# @sig.connect(Object, "cs_taskboard_create_board", "pre_mask")
# def on_create_board_pre_mask(self, ctx):
#     # for now the interval board is the default
#     templates = Board.KeywordQuery(board_type=INTERVAL_BOARD_TYPE, is_template=True)
#     if len(templates) < 1:
#         return
#     template = templates[0]
#     content_types = template.content_types.split(',')
#     content_types_names = template._convert_to_content_names(content_types)
#     ctx.set("content_types_names", ','.join(content_types_names))
#     ctx.set("content_types", template.content_types)
#     ctx.set("template_object_id", template.cdb_object_id)
#
#     fields = ["interval_length", "interval_name", "interval_type"]
#     ctx.set_fields_writeable(fields + ["start_date"])
#     ctx.set_fields_mandatory(fields + ["start_date"])
#     ctx.set_readonly("auto_create_iteration")
#     for field in fields:
#         ctx.set_mandatory(field)
#         ctx.set(field, template[field])


@sig.connect(Board, "copyBoard")
@sig.connect(Board, "create", "post")
@sig.connect(Board, "copy", "post")
def init_interval(self, ctx=None):
    if self.board_type == INTERVAL_BOARD_TYPE and not self.is_template:
        adapter = self.getAdapter()
        iter_cls = adapter.get_iteration_class()
        if iter_cls:
            with SkipAccessCheck():
                operation(kOperationNew,
                          iter_cls._getClassDef(),
                          board_object_id=self.cdb_object_id)
