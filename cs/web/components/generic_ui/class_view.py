#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import six

from morepath.error import LinkError
from cs.web.components.ui_support.operations import OperationInfoClass
from cdb import sig
from cdb.objects.core import ClassRegistry
from cdb.objects.iconcache import IconCache
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web.uisupport import get_uisupport
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK
from cs.web.components.configurable_ui import ConfigurableUIModel
from cs.web.components.ui_support import forms
from cs.web.components.ui_support.search_favourites import SearchFavouriteCollection
from cs.web.components.ui_support.utils import resolve_ui_name
from . import GenericUIApp, _select_view_intern, get_ui_app


class ClassViewModel(ConfigurableUIModel):
    """ Morepath model class for a "class" page. A class page provides an entry
        point for searching and creating instances of the class. As a default,
        only the root of a class hierarchy is directly accessible through a
        separate URL, but it is possible to define UI names for subclasses, and
        configure pages for them.
    """

    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, rest_or_ui_name, viewname):
        super(ClassViewModel, self).__init__()
        (self.classname, self.rest_name, self.ui_name) = resolve_ui_name(rest_or_ui_name)
        self.viewname = viewname

    def is_valid(self):
        return self.rest_name is not None and self.classname is not None

    def _select_class_view(self, configurations):
        """ Analoguous to `cs.web.components.generic_ui.select_view`, but uses
            UI names or REST names instead of classnames.
        """
        # Build a list of all UI names for the class hierarchy starting at
        # self.classdef, incl. '*' as fallback.
        ui_names = []
        for cls_name in [self.classdef.getClassname()] + list(self.classdef.getBaseClassNames()):
            cd = CDBClassDef(cls_name)
            ui_name = cd.getUIName()
            if ui_name:
                ui_names.append(ui_name)
        ui_names.append('*')
        return _select_view_intern(configurations, self.classdef, ui_names, self.viewname)

    def _load_class_renderer(self):
        cfg = self.load_config("csweb_page_config_class")
        config = self._select_class_view(cfg)
        self.set_page_frame(config["pageframe_id"])
        if self.viewname is None:
            self.viewname = config["viewname"]
        self.insert_component_configuration("pageContent", config)

    def load_application_configuration(self):
        # Load own configuration first, because page_frame() depends on it to
        # determine which frame to use!
        self._load_class_renderer()
        super(ClassViewModel, self).load_application_configuration()
        # needed for page renderer
        # self.add_library("cs-web-components-genericui", "15.1.0")

    @property
    def classdef(self):
        return CDBClassDef(self.classname)

    @property
    def python_class(self):
        return ClassRegistry().find(self.classdef.getPrimaryTable(), generate=True)

    def all_sub_classdefs(self):
        cdef = self.classdef
        return [cd for cd in (cdef, ) + cdef.getSubClasses(True)]

    def all_sub_classnames(self):
        cdef = self.classdef
        return [name for name in (cdef.getClassname(), ) + cdef.getSubClassNames(True)]


@GenericUIApp.path(path="{rest_name}", model=ClassViewModel)
def _get_model(rest_name, viewname):
    # rest_name may also be a ui_name, but morepath requires the variables to
    # be named the same (here and in detail_view)!!
    mdl = ClassViewModel(rest_name, viewname)
    return mdl if mdl.is_valid() else None


@GenericUIApp.view(model=ClassViewModel, name="document_title", internal=True)
def _document_title(model, _request):
    return model.classdef.getTitle()


# Marker object for use with signals
CLASS_VIEW_SETUP = object()


@sig.connect(ClassViewModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    root_classname = model.classname
    us_app = get_uisupport(request)  # construct apps and models for link generation

    class_infos = {cdef.getClassname(): {"title": cdef.getTitle(),
                                         "designation": cdef.getDesignation(),
                                         "icon": IconCache.getIcon(cdef.getIconId())}
                   for cdef in model.all_sub_classdefs()}

    all_ops = [op_info for op_info in request.view(OperationInfoClass(root_classname), app=us_app)
               if op_info["submit_url"] or op_info["form_url"] or op_info["target_url"]]
    class_ops = {}
    for class_op in [op for op in all_ops if op['activation_mode'] == 0]:
        groupname = 'CDB_Create' if class_op['creates_object'] else class_op['opname']
        if groupname not in class_ops:
            class_ops[groupname] = []

        class_op['uiLink'] = {
            'search': ("?action=%s&cdb_class=%s&display_name=%s"
                       % (class_op['opname'],
                          class_op['classname'],
                          class_infos[class_op['classname']]['title']))
        }
        class_ops[groupname].append(class_op)

    obj_ops = {}
    for obj_op in [op for op in all_ops if op['activation_mode'] in [2, 3]]:
        if obj_op['opname'] not in obj_ops:
            obj_ops[obj_op['opname']] = {}
        obj_ops[obj_op['opname']][obj_op['classname']] = obj_op

    app_setup.merge_in(["class_view"], {
        "icons": {
            "CDB_Create": "/resources/icons/byname/Create/0"
        },
        "rootClassname": root_classname,
        "classInfos": class_infos,
        "objectOpInfos": obj_ops,
        "classOpInfos": class_ops,
        "searchFavourites": SearchFavouriteCollection(root_classname).make_link(request)
    })
    app_setup.merge_in(["links"], {
        # Send link to CDB_ShowObject form, used in Attributes.jsx
        "attribute_configuration": request.link(forms.FormSettings('CDB_ShowObject', model.classdef),
                                                app=get_uisupport(request)),
    })
    # Call additional slots that allow to specify settings based on the specific
    # class that is rendered.
    slot = sig.emit(model.python_class, CLASS_VIEW_SETUP)
    slot(model.classname, request, app_setup)

@sig.connect(GLOBAL_APPSETUP_HOOK)
def global_app_setup(app_setup, request):
    try:
        class_view_link = six.moves.urllib.parse.unquote(request.class_link(
            ClassViewModel,
            {'rest_name': '${class_ui_name}'},
            app=get_ui_app(request)
        ))
        app_setup.merge_in(['links', 'common'], {
            'classViewTemplate': class_view_link,
        })
    except LinkError:
        pass
