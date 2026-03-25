#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
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
from cs.vp.items import Item

__all__ = []


class ItemWidget(WidgetBase):
    # which filters should be displayed
    __filters__ = [
        "filter_mine",
        "filter_recently_created",
        "filter_released",
        "filter_not_released",
    ]

    # CDB class for result objects
    __result_cls__ = Item

    __stmt_attr__ = "cdb_object_id"

    # Rule for searching objects in period
    __released_rule__ = "cdbpcs: Kosmodrom: Released Objects"

    __order_by__ = "cdb_cdate desc"

    @classmethod
    def get_rule_add_expr(cls, cdb_project_id):
        return "cdb_t_project_id='%s'" % (cdb_project_id)

    @classmethod
    def get_filter_cond(cls, cdb_project_id, filters):
        add_expr = cls.get_rule_add_expr(cdb_project_id)
        attr = cls.__stmt_attr__
        ands = cls._get_filter_cond(cdb_project_id, filters)

        # released
        released = []
        from cdb.objects import Rule

        if "filter_released" in filters:
            myrule = Rule.ByKeys(cls.__released_rule__)
            if myrule:
                released.append(
                    cls.get_rule_stmt(
                        myrule, cls.__result_cls__, attr, add_expr=add_expr
                    )
                )
        # not released
        if "filter_not_released" in filters:
            myrule = Rule.ByKeys(cls.__released_rule__)
            if myrule:
                released.append(
                    "NOT (%s)"
                    % cls.get_rule_stmt(
                        myrule, cls.__result_cls__, attr, add_expr=add_expr
                    )
                )
        if released:
            ands.append("(%s)" % (" or ".join(released)))

        return " and ".join(ands)


@elink.using_template_engine("chameleon")
class PluginImpl(elink.Application):
    __plugin_macro_file__ = "widget_items.html"
    dashboard_widget = ItemWidget


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.widget", "item")
@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=W0603
    if app is None:
        app = PluginImpl()
    return (6, app)
