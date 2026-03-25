#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import ddl, sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class UpdateSelectionCatalog:
    """
    The change of the catalog cdbpcs_tasks_for_efforts (E059047)
    from structure catalog to table catalog does not work
    when updating an environment
    """

    def run(self):
        table_browser = ddl.Table("browsers")
        if table_browser.exists():
            sqlapi.SQLupdate(
                "browsers SET show_rs_window = 0, comp_name=''"
                " WHERE katalog = 'cdbpcs_tasks_for_efforts'"
            )


pre = []
post = [UpdateSelectionCatalog]
