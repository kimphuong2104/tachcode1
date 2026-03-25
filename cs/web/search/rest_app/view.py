#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
import six
__revision__ = "$Id: view.py 198563 2019-07-12 07:11:33Z tst $"


import json
from morepath.error import LinkError
from webob import exc
from cdb import misc
from cdb.storage.index.errors import ESException
from cs.platform.web.rest import get_collection_app
from cs.platform.web.uisupport import get_ui_link
from cs.web.components.ui_support.files import file_link_by_blob_id
from cs.web.search.rest_app.main import InternalSearchApp
from .model import FullTextSearchModel, TermSearchModel, HighlightSearchModel


class assert_properties(object):
    def __init__(self, obj, props):
        self.__obj = obj
        self.__props = props if isinstance(props, (list, tuple)) else [props]

    def __enter__(self):
        if not all(k in self.__obj for k in self.__props):
            raise exc.HTTPBadRequest()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Return an explicit Response objects here instead of raising an exception,
# because WebOb exceptions insist on formatting the response body as HTML or
# plain text, no JSON possible

@InternalSearchApp.json(model=FullTextSearchModel)
def _fulltext_search(model, request):
    """ Run the ES query, and post-processes the result to swap JSON
        representations for CDB objects.
    """
    try:
        search_result = model._prepare_result(request)
        result_list = []
        for entry in search_result['result']:
            try:
                obj = entry['self']
                # Fix E048087: We don't need to construct the whole
                # object using request.view(...). The only required
                # information is the object's ui_link as well as the
                # object icon and file links.
                entry['self'] = {
                    "system:ui_link": get_ui_link(request, obj),
                    "system:icon_link": obj.GetObjectIcon()
                }
                for file_entry in entry.get('files', []):
                    file_entry['date'] = file_entry['date'].isoformat()
                    file_entry['system:ui_link'] = file_link_by_blob_id(request, file_entry['cdb_object_id'])
                    del file_entry['self']
                entry['date'] = entry['date'].isoformat()
                result_list.append(entry)
            except LinkError:
                # Silently drop results that are not REST API accessible
                # TODO: correct counters
                pass
        search_result['result'] = result_list
        return {'result': search_result}
    except ESException as e:
        misc.log_traceback("Enterprise Search")
        res = request.ResponseClass(text=six.text_type(json.dumps(six.text_type(e))),
                                    status=exc.HTTPInternalServerError.code,
                                    content_type="application/json")
        return res


@InternalSearchApp.json(model=TermSearchModel)
def _term_search(model, request):
    try:
        search_result = model.search(request)
        return {'result': search_result}
    except ESException as e:
        misc.log_traceback("Term Search")
        res = request.ResponseClass(text=six.text_type(json.dumps(six.text_type(e))),
                                    status=exc.HTTPInternalServerError.code,
                                    content_type="application/json")
        return res


@InternalSearchApp.json(model=HighlightSearchModel)
def _highlight_search(model, request):
    try:
        search_result = model.search(request)
        return {'result': search_result}
    except ESException as e:
        misc.log_traceback("Highlight Search")
        res = request.ResponseClass(json_body=json.dumps(six.text_type(e)),
                                    status=exc.HTTPInternalServerError.code,
                                    content_type="application/json")
        return res
