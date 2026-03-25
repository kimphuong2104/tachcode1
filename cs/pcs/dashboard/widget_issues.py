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

from cdb import elink, sig, sqlapi

from cs.pcs.dashboard import LOAD_OBJECT_STEP, WidgetBase
from cs.pcs.issues import Issue

__all__ = []


class IssueWidget(WidgetBase):
    # which filters should be displayed
    __filters__ = [
        "filter_mine",
        "filter_today",
        "filter_tomorrow",
        "filter_later",
        "filter_overdue",
        "filter_not_scheduled",
    ]

    # CDB class for result objects
    __result_cls__ = Issue

    __stmt_attr__ = "issue_id"

    __load_step__ = LOAD_OBJECT_STEP / 2

    __order_by__ = "target_date"

    __not_scheduled_cond__ = ""

    @classmethod
    def get_filter_cond(cls, cdb_project_id, filters):
        ands = cls._get_filter_cond(cdb_project_id, filters)

        # not scheduled
        if "filter_not_scheduled" in filters:
            default_not_scheduled_cond = (
                "(target_date is null or target_date='')"
                if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE
                else "target_date is null"
            )
            ands.append(cls.__not_scheduled_cond__ or default_not_scheduled_cond)

        return " and ".join(ands)


@elink.using_template_engine("chameleon")
class PluginImpl(elink.Application):

    __plugin_macro_file__ = "widget_issues.html"
    dashboard_widget = IssueWidget


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.widget", "issue")
@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PluginImpl()
    return (4, app)
