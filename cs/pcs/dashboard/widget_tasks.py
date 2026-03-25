#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Widget plugin for cs.pcs.dashboard.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import elink, sig

from cs.pcs.dashboard import WidgetBase
from cs.pcs.projects.tasks import Task

__all__ = []


class TaskWidget(WidgetBase):

    # which filters should be displayed
    __filters__ = [
        "filter_mine",
        "filter_today",
        "filter_tomorrow",
        "filter_later",
        "filter_overdue",
        "filter_not_begun",
        "filter_categ_task_group",
        "filter_categ_task",
        "filter_categ_milestone",
    ]

    # CDB class for result objects
    __result_cls__ = Task

    __stmt_attr__ = "task_id"

    __order_by__ = "end_time_fcast"

    @classmethod
    def get_filter_cond(cls, cdb_project_id, filters):
        add_expr = cls.get_rule_add_expr(cdb_project_id)
        attr = cls.__stmt_attr__
        ands = cls._get_filter_cond(cdb_project_id, filters)

        # category
        cats = []
        if "filter_categ_task_group" in filters:
            cats.append("is_group=1")
        if "filter_categ_task" in filters:
            cats.append("not (is_group=1 or milestone=1)")
        if "filter_categ_milestone" in filters:
            cats.append("milestone=1")
        if cats:
            ands.append(f'({" or ".join(cats)})')

        # not begun
        if "filter_not_begun" in filters:
            from cdb.objects import Rule

            myrule = Rule.ByKeys(name="cdbpcs: Kosmodrom: Tasks Not Begun")
            if myrule:
                ands.append(
                    cls.get_rule_stmt(
                        myrule, cls.__result_cls__, attr, add_expr=add_expr
                    )
                )

        return " and ".join(ands)


@elink.using_template_engine("chameleon")
class PluginImpl(elink.Application):

    __plugin_macro_file__ = "widget_tasks.html"
    dashboard_widget = TaskWidget


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.widget", "task")
@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PluginImpl()
    return (3, app)
