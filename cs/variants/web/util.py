# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
from urllib.parse import unquote

from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.support import rest_object


def link_rest_object(request, obj):
    result = request.link(obj, app=get_collection_app(request))
    return unquote(result)


def view_rest_objects(request, objs):
    return [request.view(o, app=get_collection_app(request)) for o in objs]


def get_object_from_rest_link(object_class, rest_link):
    rest_key = rest_link.rsplit("/", maxsplit=1)[-1]
    return rest_object(object_class, rest_key)
