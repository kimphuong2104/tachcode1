# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from webob.exc import HTTPForbidden

from cdb.constants import kAccessRead
from cs.platform.web.uisupport import get_webui_link
from cs.platform.web.rest.support import get_object_from_rest_name, get_restlink, rest_name_for_class_name

from . import App


class Context(object):
    """
    Class that offers the context for an object.
    The GetObjectContext method must be implemented by the respective class.
    It must return a list of objects starting with the root over all intermediate
    objects up to the object on which the method was called.
    """

    def __init__(self, classname, keys):
        self.classname = classname
        self.keys = keys

    def _get_context(self, request):
        result = {"context": []}
        rest_name = rest_name_for_class_name(self.classname)
        try:
            rest_obj = get_object_from_rest_name(rest_name, self.keys)
        except (AttributeError, ValueError):
            raise HTTPForbidden()
        else:
            if rest_obj is None:
                raise HTTPForbidden()
            if not rest_obj.CheckAccess(kAccessRead):
                context_objects = []
            elif hasattr(rest_obj, "GetObjectContext"):
                context_objects = rest_obj.GetObjectContext()
            else:
                context_objects = [rest_obj]
            for value in context_objects:
                if value.CheckAccess(kAccessRead):
                    context_object = {'system:description': value.GetDescription(),
                                      'system:icon_link': value.GetObjectIcon(),
                                      'ui_link': get_webui_link(request, value),
                                      'rest_link': get_restlink(value, request)}
                    result["context"].append(context_object)
        return result


@App.path(path='context/{classname}/{keys}', model=Context)
def _init_name_model(classname, keys):
    return Context(classname, keys)


@App.json(model=Context)
def _context(model, request):
    return model._get_context(request)
