#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import copy
import json
import six
from cdb.objects import ByID
from cdb.platform.mom.entities import Class
from cs.platform.web.rest.generic.convert import dump_datetime
from cdb.storage.index import standard_query
from cdb.storage.index.errors import ESException
from cdb.storage.index.queries import ESQueryPage
from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.support import rest_name_for_class_name
from webob.exc import HTTPInternalServerError
from . import App


class SearchModel(ESQueryPage):

    @property
    def request(self):
        if not hasattr(self._request, "image_uri"):
            setattr(self._request, "image_uri", "")
        return self._request

    # Cache for indexable rest enabled classes
    _Indexed_REST_Activ_Class_Cache = None

    @classmethod
    def _get_indexed_classnames(cls):
        if cls._Indexed_REST_Activ_Class_Cache is not None:
            return cls._Indexed_REST_Activ_Class_Cache
        cls._Indexed_REST_Activ_Class_Cache = [
            c.classname for c in Class.KeywordQuery(is_indexed=1) if rest_name_for_class_name(c.classname)
            ]
        return cls._Indexed_REST_Activ_Class_Cache

    def __init__(self, query_type=standard_query.StandardQuery):
        super(SearchModel, self).__init__(query_type)
        self.__include_classes__ = [c for c in self._get_indexed_classnames()]

    def get_result(self, request):
        self._request = request
        query_parameters = self.extra_parameters
        if self.__include_classes__:
            include_classes = self.__include_classes__
            if self.extra_parameters and "classes" in self.extra_parameters:
                classes = self.extra_parameters["classes"].split(",")
                include_classes = set(include_classes).intersection(classes)
            if self.extra_parameters and "exclude_classes" in self.extra_parameters:
                excl_classes = self.extra_parameters["exclude_classes"].split(",")
                include_classes = set(include_classes).difference(excl_classes)
            if not include_classes:
                return {"no_index_for_class": True}
            query_parameters["classname"] = ",".join(include_classes)
        query_parameters["classes"] = None
        query_parameters["exclude_classes"] = None
        query_parameters["basicResults"] = "True"
        result = self._prepare_result(query_parameters)
        collection_app = get_collection_app(request)
        # remove object reference to fit json serialization
        for entry in result["result"]:
            rest_object = request.view(entry['self'], app=collection_app)
            entry['ui_link'] = rest_object.get("system:ui_link")
            entry['rest_url'] = rest_object["@id"]
            del entry['self']
            entry["date"] = dump_datetime(entry["date"])

            for file_entry in entry.get('files', []):
                del file_entry['self']
                file_entry["date"] = dump_datetime(file_entry["date"])

            entryObject = ByID(entry["cdb_object_id"])
            entry["system:description"] = entryObject.GetDescription()

        return result

    def settings(self):
        return self._base_settings()


class ObjectSearchModel(SearchModel):
    def __init__(self, extra_parameters):
        super(ObjectSearchModel, self).__init__()
        self.extra_parameters = extra_parameters


@App.path(path="object_search", model=ObjectSearchModel)
def _object_search(request, extra_parameters):
    return ObjectSearchModel(extra_parameters)


@App.json(model=ObjectSearchModel)
def get_search_results(model, request):
    try:
        return {"result": model.get_result(request)}
    except ESException as e:
        res = request.ResponseClass(text=six.text_type(json.dumps(six.text_type(e))),
                                    status="%d %s" % (HTTPInternalServerError.code,
                                                      "Enterprise Search Error"),
                                    content_type="application/json")
        return res


class ObjectSearchModelAllowdClasses(object):
    # Cache for rest enabled classes with subclasses list
    _REST_Activ_Class_Cache = None

    @classmethod
    def _getRestVisibleClassesAndSub(cls):
            if cls._REST_Activ_Class_Cache is not None:
                return cls._REST_Activ_Class_Cache
            cls._REST_Activ_Class_Cache = [
                {"classname": c.classname,
                 "name": c.beschriftung,
                 "rest": rest_name_for_class_name(c.classname),
                 "isIndexed": c.is_indexed,
                 "rest_api_active": c.rest_api_active,
                 "rest_visible_name": c.rest_visible_name,
                 "subClassNames": [clsname for clsname in c.getSubClassNames()]}
                for c in Class.Query() if rest_name_for_class_name(c.classname)]
            return cls._REST_Activ_Class_Cache

    def __init__(self, extra_parameters):
        excl_classes = []
        if "exclude_classes" in extra_parameters:
            excl_classes = extra_parameters["exclude_classes"].split(",")
        self.classes = [
            copy.copy(c) for c in self._getRestVisibleClassesAndSub() if c["classname"] not in excl_classes]
        for c in self.classes:
            c["subClasses"] = [
                clsname for clsname in c["subClassNames"]
                if clsname not in excl_classes]
            del c["subClassNames"]


@App.path(path="object_search_allowed_classes", model=ObjectSearchModelAllowdClasses)
def _object_search(request, extra_parameters):
    return ObjectSearchModelAllowdClasses(extra_parameters)


@App.json(model=ObjectSearchModelAllowdClasses)
def get_search_results(model, request):
    return {"classes": model.classes}
