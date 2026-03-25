#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import ddl, sqlapi

MODULE_ID = "cs.documents"


class UpdateDashboardWidget(object):
    """
    There has been a widget named ``my-documents`` in cs.web which has to be
    replaced by ``recently-modified-documents-widget``.
    """

    def run(self):  # pylint: disable=no-self-use
        if ddl.Table("csweb_dashboard_item").exists():
            sqlapi.SQLupdate(
                "csweb_dashboard_item SET widget_id='recently-modified-documents-widget' "
                "WHERE widget_id='my-documents'"
            )


pre = []
post = [UpdateDashboardWidget]
