# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This module contains functions that implements the batch loading REST-API for
objects.

Note that POST request are used because the object informations might be too
large to be transferred using the request parameters. They do not alter the
database state as it might be expected during a POST request.
"""

from __future__ import absolute_import
import six
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


__all__ = []

from collections import defaultdict
from webob.exc import HTTPForbidden
from cdbwrapc import CDBClassDef
from cdb import ElementsError
try:
    from cdb.platform.mom import increase_eviction_queue_limit
except ImportError:
    # CE 16 has no eviction queue any more - remove this code if and when cs.web
    # is branched for CE 16
    from contextlib import nullcontext as increase_eviction_queue_limit
from cs.platform.web.rest.classdef.main import get_classdef
from cs.platform.web.rest import get_collection_app, support
from . import App, get_uisupport_app
from cdb.objects import Object


class BatchModel(Object):

    @classmethod
    def make_link(cls, request):
        return request.class_link(BatchModel, app=get_uisupport_app(request))


@App.path(path='/batchload', model=BatchModel)
def _batch():
    return BatchModel()


@App.json(model=BatchModel, request_method='POST')
def _json_post(self, request):
    colApp = get_collection_app(request)
    result = {"objects": [], "errors": {}}
    try:
        identifiers = request.json.get("identifiers")
        rest_name2ids = defaultdict(list)
        for the_id, restname, keys in identifiers:
            rest_name2ids[restname].append((the_id, keys))
        for restname, idkeylist in rest_name2ids.items():
            try:
                # If the platform needs to construct object handles
                # they should stay in the cache. If the limit is
                # lower than the actual limit the call is ignored
                keylist = [idandkey[1] for idandkey in idkeylist]
                with increase_eviction_queue_limit(len(keylist) + 500):
                    objs = support.get_objects_from_rest_name(restname, keylist, False)
                    for obj, idandkey in six.moves.zip(objs, idkeylist):
                        if obj:
                            result["objects"].append(request.view(obj,
                                                                  name="base_data",
                                                                  app=colApp))
                        else:
                            result["errors"][idandkey[0]] = "Object not found (%s, %s)" % (restname, idandkey[1])
            except AttributeError as e:
                for the_id, _ in idkeylist:
                    result["errors"][the_id] = six.text_type(e)
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))
    return result

class ClassdefsModel(object):
    @classmethod
    def make_link(cls, request):
        return request.class_link(cls, app=get_uisupport_app(request))

@App.path('classes', model=ClassdefsModel)
def get_model():
    return ClassdefsModel()

@App.json(model=ClassdefsModel, request_method='POST')
def get_cldefs(_, request):
    result = {'classes': [], 'errors': {}}
    clnames = set(request.json['classes'])
    for clname in clnames:
        try:
            cldef = CDBClassDef(clname)
            cldef_json = request.view(cldef, app=get_classdef(request))
            result['classes'].append(cldef_json)
        except ElementsError as e:
            result['errors'][clname] = str(e)
    return result
