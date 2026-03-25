# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module dashboard_widget

This is the documentation for the dashboard_widget module.
"""


__docformat__ = "restructuredtext en"


from webob.exc import HTTPBadRequest

from cdb.objects import Rule
from cdb.platform.olc import StatusInfo
from cs.documents import Document
from cs.platform.web.rest import get_collection_app

from .internal_app import InternalDocApp


class RecentlyModifiedDocs(object):
    """
    Class that is used to generate the information the
    frontend needs to display the dashboard widget for
    recently modified documents
    """

    _pyrule = None

    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters
        _maxrows = extra_parameters.pop("maxrows", None)
        try:
            self.maxrows = None if _maxrows is None else int(_maxrows)
        except ValueError:
            raise HTTPBadRequest("maxrows must be an integer")
        if self.maxrows is not None and self.maxrows < 1:
            raise HTTPBadRequest("maxrows value must be > 0")

    @classmethod
    def get_pyrule(cls):
        if cls._pyrule is None:
            cls._pyrule = Rule.ByKeys("cs-web-dashboard: My Documents")
        return cls._pyrule

    def get_object_data(self, request, doc):  # pylint: disable=no-self-use
        stateName = ""
        stateColor = ""
        try:
            si = StatusInfo(doc.GetObjectKind(), doc.z_status)
            if si:
                stateColor = si.getCSSColor()
                stateName = si.getLabel()
        except ValueError:
            # Probably a None value for badly initialized docs
            pass
        app = get_collection_app(request)
        return {
            "stateColor": stateColor,
            "stateName": stateName,
            "object": request.view(doc, app=app),
        }

    def get_docs(self, request):
        r = self.get_pyrule()
        docs = []
        if r:
            mod_date = (
                "CASE WHEN cdb_m2date IS NULL THEN cdb_mdate "
                "WHEN cdb_mdate IS NULL THEN cdb_m2date "
                "WHEN cdb_m2date > cdb_mdate THEN cdb_m2date "
                "ELSE cdb_mdate END AS last_mod_date"
            )
            condition = str(r.expr(Document))
            stmt = (
                "SELECT zeichnung.*, %s "
                "FROM zeichnung WHERE %s "
                "ORDER BY last_mod_date DESC"
            ) % (mod_date, condition)
            docs = Document.SQL(stmt, max_rows=self.maxrows)

        result = {}
        result["objects"] = [
            self.get_object_data(request, doc)
            for doc in docs
            if doc.CheckAccess("read")
        ]
        return result


@InternalDocApp.path(path="recentlymodifieddocs", model=RecentlyModifiedDocs)
def get_docs(extra_parameters):
    return RecentlyModifiedDocs(extra_parameters)


@InternalDocApp.json(model=RecentlyModifiedDocs)
def get_docs_json(self, request):
    return self.get_docs(request)


# Guard importing as main module
if __name__ == "__main__":
    pass
