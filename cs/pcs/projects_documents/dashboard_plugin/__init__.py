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
from cdb.platform.mom import entities
from cs.documents import Document

from cs.pcs.dashboard import WidgetBase

__all__ = []


class DocumentWidget(WidgetBase):
    # which filters should be displayed
    __filters__ = [
        "filter_mine",
        "filter_recently_created",
        "filter_categ_document",
        "filter_categ_model",
        "filter_released",
        "filter_not_released",
    ]

    # CDB class for result objects
    __result_cls__ = Document

    __stmt_attr__ = "cdb_object_id"

    # Rule to match CAD documents
    __model_rule__ = None

    # Rule for searching objects in period
    __released_rule__ = "cdbpcs: Kosmodrom: Released Objects"

    __order_by__ = "cdb_cdate desc"

    @classmethod
    def get_model_rule(cls):
        if cls.__model_rule__ is None:
            # Set model rule once if model class exists
            if len(entities.Entity.KeywordQuery(classname="model")):
                cls.__model_rule__ = f"{Document.cdb_classname >= 'model'}"
            else:
                cls.__model_rule__ = ""
        return cls.__model_rule__

    @classmethod
    def get_filter_cond(cls, cdb_project_id, filters):
        add_expr = cls.get_rule_add_expr(cdb_project_id)
        attr = cls.__stmt_attr__
        ands = cls._get_filter_cond(cdb_project_id, filters)

        # category
        cats = []
        model_rule = cls.get_model_rule()
        if model_rule:
            if "filter_categ_model" in filters:
                cats.append(model_rule)
            if "filter_categ_document" in filters:
                cats.append(f"NOT {model_rule}")
        if cats:
            ands.append(f"({' or '.join(cats)})")

        # released
        released = []
        from cdb.objects import Rule

        if "filter_released" in filters:
            myrule = Rule.ByKeys(name=cls.__released_rule__)
            if myrule:
                released.append(
                    cls.get_rule_stmt(
                        myrule, cls.__result_cls__, attr, add_expr=add_expr
                    )
                )
        # not released
        if "filter_not_released" in filters:
            myrule = Rule.ByKeys(name=cls.__released_rule__)
            if myrule:
                rule_stmt = cls.get_rule_stmt(
                    myrule, cls.__result_cls__, attr, add_expr=add_expr
                )
                released.append(f"NOT ({rule_stmt})")
        if released:
            ands.append(f"({' or '.join(released)})")

        return " and ".join(ands)


@elink.using_template_engine("chameleon")
class PluginImpl(elink.Application):

    __plugin_macro_file__ = "widget_documents.html"
    dashboard_widget = DocumentWidget


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.widget", "document")
@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PluginImpl()
    return (5, app)
