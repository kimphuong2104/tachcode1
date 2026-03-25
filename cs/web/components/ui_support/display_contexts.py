#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Access to configured forms without operations
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from webob.exc import HTTPNotFound

from cdbwrapc import CDBClassDef

from cdb.objects import Object, Reference_1, Reference_N, Forward
from cdb.platform.mom import CDBObjectHandle, SimpleArguments
from cs.platform.web.uisupport import get_uisupport, get_webui_link
from .forms import FormInfoClassDef, DisplayMapping
from . import App

DisplayContext = Forward(__name__ + ".DisplayContext")
DisplayConfiguration = Forward(__name__ + ".DisplayConfiguration")


class DisplayContext(Object):
    __maps_to__ = 'csweb_display_context'
    __classname__ = 'csweb_display_context'

    Configurations = Reference_N(DisplayConfiguration,
                                 DisplayConfiguration.name == DisplayContext.name)


class DisplayConfiguration(Object):
    __maps_to__ = 'csweb_display_configuration'
    __classname__ = 'csweb_display_configuration'

    Context = Reference_1(DisplayContext, DisplayConfiguration.name)

    # Cache for configuration data
    _Cache = None

    @classmethod
    def _fill_cache(cls):
        if cls._Cache is None:
            cls._Cache = {(u.name, u.classname): u.mask_name
                          for u in cls.Query()}

    @classmethod
    def _clear_cache(cls):
        cls._Cache = None

    def _post_change(self, ctx):
        if not ctx.error:
            self._clear_cache()

    @classmethod
    def get_mask_name(cls, classname, context_name):
        cls._fill_cache()
        classdef = CDBClassDef(classname)
        clsnames = ([classname] + [name for name in classdef.getBaseClassNames()])
        for clsname in clsnames:
            mask_name = cls._Cache.get((context_name, clsname))
            if mask_name is not None:
                return mask_name
        return cls._Cache.get((context_name, "*"))

    event_map = {
        (("create", "copy", "modify", "delete"), "post"): "_post_change"
    }


class DisplayContextModel(object):
    def __init__(self, context_name, classname):
        self.context_name = context_name
        self.classname = classname

    @classmethod
    def template_link(cls, request):
        return request.class_link(DisplayContextModel,
                                  {"context_name": "${context_name}",
                                   "classname": "${classname}"},
                                  app=get_uisupport(request))


@App.path(path="display_context/{context_name}/{classname}", model=DisplayContextModel)
def _get_model(context_name, classname):
    return DisplayContextModel(context_name, classname)


@App.json(model=DisplayContextModel, request_method='POST')
def _post_form_context(model, request):
    mask_name = DisplayConfiguration.get_mask_name(model.classname, model.context_name)
    if mask_name is None:
        return HTTPNotFound()
    ficdef = FormInfoClassDef(mask_name, CDBClassDef(model.classname))
    # Display contexts are readonly - no need to use the complicated form url
    # link mechanism
    info_url = ""
    vals = request.json.get("obj_values")
    if vals:
        info_url = vals.get("system:ui_link")
        if info_url and info_url[:3] == "cdb":
            # If we get a cdb-link as UI link this is not suitable as prefix
            # (E047906)
            cdef = CDBClassDef(model.classname)
            keys = {name: vals.get(name) for name in cdef.getKeyNames()}
            oh = CDBObjectHandle(cdef, SimpleArguments(**keys), True, True)
            info_url = get_webui_link(request, oh)
    ficdef.use_object_links(info_url)
    form_def_vals = ficdef.get_form_def_and_values(request)
    if "display_mapping_url" not in form_def_vals:
        form_def_vals["display_mapping_url"] = request.link(DisplayMapping())
    return form_def_vals
