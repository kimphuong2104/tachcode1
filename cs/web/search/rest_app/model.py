# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Model classes for the search app
"""

from __future__ import absolute_import
__revision__ = "$Id: model.py 198563 2019-07-12 07:11:33Z tst $"

import html

from cdb import constants, util
from cdb.objects import ByID
from cdb.storage.index.queries import ESQueryPage
from cdb.storage.index import terms_query, standard_query, highlight_query, errors


class FullTextSearchModel(ESQueryPage):
    """ Model for ES related activities. Re-uses the existing ES logic, only
        overwriting things that are related to the old elink/template stuff.
    """
    HIGHLIGHT_BLOCK_SIZE = 150

    @property
    def request(self):
        if not hasattr(self._request, "image_uri"):
            setattr(self._request, "image_uri", "")
        return self._request

    def __init__(self, searchtext, query_params):
        super(FullTextSearchModel, self).__init__()
        query_params["fulltextsearch"] = searchtext.strip() if searchtext else ""

        self.classname = query_params.get("classname", "").split(",")
        # Rewrite the date filter
        df = query_params.get("df", None)
        if df is not None:
            query_params["df"] = ";;[%s]" % df
        self.__query_params = query_params

    def settings(self):
        """ This is called from the superclass' _prepare_result method: return
            the parameters of the current search to the client.
        """
        result = self._base_settings()
        if self.classname:
            result["classname"] = self.classname

        total_rows = self._query_helper.curr_total if self._query_helper else 0
        result["page"] = self._page_no + 1
        result["has_more"] = total_rows > 0 and (self._page_no + 1) * result["rpp"] < total_rows
        result["df"] = result["df"].strip(";;[").strip("]") if result["df"] is not None else ""
        return result

    def _prepare_result(self, request):
        """ Runs the actual ES query
        """
        # TODO: get all params from request (via self)
        self._request = request
        return super(FullTextSearchModel, self)._prepare_result(self.__query_params)


class TermSearchModel(object):
    def __init__(self, searchtext):
        self.searchtext = searchtext

    def search(self, request):
        query = terms_query.TermsQuery(self.searchtext)
        names = [term.term for term in query.execute()]
        return names


class HighlightSearchModel(object):
    """ Model for ES highlighting.
    """
    FRAGMENT_SIZE = 300

    def __init__(self, searchtext, object_id):
        self.searchtext = searchtext
        self.object_id = object_id

    def search(self, request):
        obj = ByID(self.object_id)

        if obj and obj.CheckAccess(constants.kAccessRead) and obj.IsSearchSummaryAllowed():

            def _clean_for_html(txt):
                if txt:
                    txt = html.escape(txt)
                    return txt.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
                return ""

            std_query = standard_query.StandardQuery(self.searchtext.strip())
            hls = highlight_query.HighlightQuery(std_query,
                                                 self.FRAGMENT_SIZE,
                                                 15).execute([self.object_id])

            return [_clean_for_html(curr) for curr in hls[self.object_id].all_blocks()]

        raise errors.ESException(util.Labels()["cdbes_errortitle"], None)
