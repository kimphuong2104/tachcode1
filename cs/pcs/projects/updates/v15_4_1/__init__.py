#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module __init__.py

Update scripts of cs.pcs 15.4.1
"""

import re
from urllib.parse import parse_qsl, unquote, urlencode, urlparse

from cdb import ddl, transactions
from cdb.comparch import protocol

# Exported objects
__all__ = []


class DropViews:

    tbd_views = [
        "cdbpcs_taskrel_parent_v",
        "cdbpcs_taskrel_cal_v",
        "cdbpcs_taskrel_cal",
        "cdbpcs_critical_path_v",
        "cdbpcs_task_calendar_v",
        "cdbpcs_taskrel_type_v",
    ]

    def run(self):

        for tbd_view in self.tbd_views:

            view = ddl.View(tbd_view)
            if not view:
                continue
            view.drop(check_existence=True)


class MigrateFavorites:
    """
    This script migrates the existing favorites.
    """

    def migrate_favorite(self, fav):
        # migrate search favorites
        # change search for cdbpcs_task.subject_name
        # in cdbpcs_task.mapped_subject_name_de
        # also change url build with the old operation 'query'
        kCategoryExp = re.compile("^.subject_name$")
        if fav and fav.fav_link:
            url = urlparse.urlparse(fav.fav_link)
            exp = (
                "^byname/classname/"
                "(?P<classname>cdbpcs_task|cdbpcs_issue|cdbpcs_checklst|cdbpcs_cl_item)/"
                "(?P<operation>CDB_Search|query)/"
                "(?P<mode>batch|interactive)"
            )
            if re.match(exp, url.path):
                query = dict(parse_qsl(url.query))
                for attr, value in list(query.items()):
                    if kCategoryExp.match(attr):
                        query[".mapped_subject_name_de"] = value
                        del query[attr]
                args = (
                    url.scheme,
                    url.netloc,
                    url.path,
                    url.params,
                    unquote(urlencode(query)),
                    url.fragment,
                )
                fav.fav_link = urlparse.urlunparse(args)

    def run(self):
        try:
            from cdb.platform import favourite
        except ImportError:
            protocol.logWarning(
                "Skip v15_4_1.MigrateFavorites due to failed import."
                " If you're on CE 16 or later, you can ignore this."
            )
            return

        with transactions.Transaction():
            # migrate favorites
            for favorite in favourite.Favourite.Query():
                self.migrate_favorite(favorite)


pre = []
post = [DropViews]
