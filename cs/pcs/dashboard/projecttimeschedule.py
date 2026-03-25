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

from cdb import elink, sig
from cdb.platform.mom.fields import DDField

from cs.pcs.dashboard import KosmodromTools, WidgetBase
from cs.pcs.timeschedule import Project2TimeSchedule

__all__ = []


class TimeScheduleWidget(WidgetBase):

    __result_cls__ = Project2TimeSchedule

    __stmt_attr__ = "cdb_project_id"

    __order_by__ = None

    __active_rule__ = None

    @classmethod
    def get_objects(cls, cdb_project_id, filters, pageno, step=None):
        if step is None:
            step = cls.__load_step__
        _results = cls.__result_cls__.Query(
            cls.get_filter_cond(cdb_project_id, filters),
            order_by=cls.__order_by__,
            access="read",
        )
        results = [x.TimeSchedule for x in _results]
        results = [x for x in results if x is not None]
        return KosmodromTools.make_page(results, pageno, step)

    @staticmethod
    def get_field_label(classname, field_name):
        ddf = DDField.ByKeys(classname=classname, field_name=field_name)
        if ddf:
            return ddf.Label[""]
        else:
            return ""


@elink.using_template_engine("chameleon")
class PluginImpl(elink.Application):

    __plugin_macro_file__ = "widget_projecttimeschedule.html"
    dashboard_widget = TimeScheduleWidget


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PluginImpl()
    return (8, app)
