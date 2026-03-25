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

from cdbwrapc import CDBClassDef
from cdb import auth
from cdb import sig
from cdb.constants import kOperationShowObject
from cdb.lru_cache import lru_cache
from cdb.objects.core import Object, ClassRegistry
from cdb.platform.mom import CDBObjectHandle
from cdb.platform.mom.operations import OperationInfo
from cdb.objects.iconcache import IconCache
from cs.platform.web import static
from cs.platform.web.rest import CollectionApp, get_collection_app
from cs.platform.web.rest import support
from cs.platform.web.uisupport import get_uisupport
from cs.web.components.ui_support.forms import FormSettings
from cs.web.components.ui_support.thumbnail import get_thumbnail_upload
from cs.web.components.ui_support.utils import ui_name_for_class
from cs.web.components.configurable_ui import ConfigurableUIModel
from cs.web.components.outlet_config import replace_outlets
from . import GenericUIApp, select_view, get_ui_app, NoViewError
from .class_view import ClassViewModel


class DetailViewModel(ConfigurableUIModel):
    """ Morepath model class for an "object detail" page, ie. a page that shows
        a single object. The page content is read from the configuration, based
        on the objects class name, with fallback to the REST visible name. The
        REST visible name is always used for the URL.
    """

    page_renderer = "cs-web-components-base-DetailPage"

    def __init__(self, rest_name, keys, viewname=None):
        super(DetailViewModel, self).__init__()
        self.rest_name = rest_name
        self.classname = support.class_name_for_rest_name(self.rest_name)
        self.keys = keys
        self.viewname = viewname
        self._object = None

    def get_object(self):
        if self._object is None:
            self._object = support.get_object_from_rest_name(self.rest_name, self.keys)
        return self._object

    def _load_detail_renderer(self):
        cfg = self.load_config("csweb_page_config_detail")
        config = select_view(cfg, self.classdef, self.viewname)
        self.set_page_frame(config["pageframe_id"])
        if self.viewname is None:
            self.viewname = config["viewname"]
        self.insert_component_configuration("detailView", config)

    def load_application_configuration(self):
        # Load own configuration first, because page_frame() depends on it to
        # determine which frame to use!
        self._load_detail_renderer()
        super(DetailViewModel, self).load_application_configuration()
        # needed for page renderer
        # self.add_library("cs-web-components-genericui", "15.1.0")

    @property
    def classdef(self):
        return self.get_object().GetClassDef()

    def all_classnames(self):
        cdef = self.classdef
        return [name for name in (cdef.getClassname(), ) + cdef.getBaseClassNames()]

    @property
    def python_class(self):
        return ClassRegistry().find(self.classdef.getPrimaryTable(), generate=True)

    @classmethod
    def provides_detail_view(cls, classdef):
        """
        Returns ``True`` if there is a detail page for classdef.
        At this time this means that the class is accessible with the REST
        API and that there has to be a detail page configuration. If there
        is no page explicitely configured for the class but a default detail
        view the operation ``CDB_ShowObject`` has to be active to make this
        function return ``True``.
        """
        if classdef:
            return _provides_detail_view(classdef.getClassname(), auth.persno)
        else:
            return False


@lru_cache(maxsize=1000, clear_after_ue=False)
def _provides_detail_view(classname, _persno):
    """ Cache for DetailViewModel.provides_detail_view. Has to have persno as an
        argument because under the hood the result depends on it; use _persno so
        that pep8 does not complain about unused parameters. Can't use classdef
        directly, because we get a different SWIG proxy each time, so there would
        be no cache hits (or we would have to implement __eq__ and __hash__, with
        whatever side effects that would have).
    """
    result = False
    classdef = CDBClassDef(classname)
    if classdef.getRESTName():
        # select_view() and OperationInfo() may yield different results for
        # different users. This will be relevant for CE 16, but does not hurt
        # in CE 15.
        cfgs = DetailViewModel.load_config("csweb_page_config_detail")
        try:
            config = select_view(cfgs, classdef, None)
            if config.get("classname", "*") == "*":
                # We have to check if info is provided
                uiocfg = OperationInfo(classname, kOperationShowObject)
                result = bool(uiocfg and uiocfg.offer_in_webui())
            else:
                result = True
        except NoViewError:
            result = False
    return result


@GenericUIApp.path(path="{rest_name}/{keys}", model=DetailViewModel)
def _get_model(rest_name, keys, viewname):
    if support.cls_def(name=rest_name) is None:
        return None
    detail_view_model = DetailViewModel(rest_name, keys, viewname)
    if detail_view_model.get_object() is None:
        return None
    return detail_view_model


@GenericUIApp.view(model=DetailViewModel, name="document_title", internal=True)
def _document_title(model, request):
    return model.classdef.getTitle()


@GenericUIApp.view(model=DetailViewModel, name="app_icon", internal=True)
def _app_icon(model, request):
    return IconCache.getIcon(model.classdef.getIconId())


@GenericUIApp.view(model=DetailViewModel, name="application_id", internal=True)
def _app_id(model, request):
    return "detail_%s" % model.rest_name


# Marker object for use with signals
DETAIL_VIEW_SETUP = object()


def _determine_ui_name(_request, cdef):
    # Only here for backward compatibility reasons, use ui_name_for_class directly!
    # This function will be removed with release 15.5
    return ui_name_for_class(cdef)


@sig.connect(DetailViewModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    cdef = model.classdef
    # construct apps and models for link generation
    us_app = get_uisupport(request)
    form_settings = FormSettings(kOperationShowObject, cdef, {})
    collection_app = get_collection_app(request)
    class_ui_name = ui_name_for_class(cdef)

    app_setup.merge_in(["detail_view"], {
        "appInfo": {
            "classDesignation": cdef.getDesignation(),
            "classTitle": cdef.getTitle(),
            "classIcon": IconCache.getIcon(cdef.getIconId())
        },
        "uploadThumbnail": get_thumbnail_upload(model.get_object(), request)
    })
    app_setup.merge_in(["links", "detail_view"], {
        "object_url_template": six.moves.urllib.parse.unquote(request.class_link(Object,
 	                                                                             {'rest_name': cdef.getRESTName(),
	                                                                              'keys': '${keys}'},
	                                                                             app=collection_app)),
        "object_url": six.moves.urllib.parse.unquote(request.link(model.get_object(), app=collection_app)),
        "info_form_url": six.moves.urllib.parse.unquote(request.link(form_settings, app=us_app)),
        "classUiLink": six.moves.urllib.parse.unquote(request.class_link(ClassViewModel, {"rest_name": class_ui_name}))
    })

    # Replace outlets with actual configuration. Called before any specific
    # hooks are invoked, so that the hooks already see the expanded outlets.
    replace_outlets(model, app_setup)

    # Call additional slots that allow to specify settings based on the specific
    # class that is rendered.
    slot = sig.emit(model.python_class, DETAIL_VIEW_SETUP)
    slot(model.get_object(), request, app_setup)

    # There may be libraries registered using the "new" configurations implemented
    # with 15.4.1. Extract these from the setup, and register them with the model
    # for inclusion into the generated HTML.
    _add_configured_libraries(model, app_setup["applicationConfiguration"]["detailView"])


def _add_configured_libraries(model, conf):
    if isinstance(conf, six.string_types):
        # configuration uses a registered component instead of .json-file
        return

    libs = conf.get("libraries", [])
    for lib in libs:
        # This is a workaround while we have not yet eliminated library versions
        # from the platform code: assuming that there is only one version, just
        # take the version of this instance.
        libname = lib["library_name"]
        all_versions = static.Registry().getall(libname)
        if len(all_versions) >= 1:
            model.add_library(libname, all_versions[0].version)
    for child_conf in conf.get("children", []):
        _add_configured_libraries(model, child_conf)


@GenericUIApp.view(model=DetailViewModel, name="base_path", internal=True)
def get_base_path(_model, request):
    # pop off the last path component (ie. the keys)
    return '/'.join(request.path.split('/')[:-1])


# These views will be called from the generic REST API and other places to
# determine the correct UI URL for an object.

@CollectionApp.view(model=CDBClassDef, name="detail_link_pattern", internal=True)
def _get_classdef_ui_link(cdef, request):
    if DetailViewModel.provides_detail_view(cdef):
        the_link = request.class_link(DetailViewModel,
                                      {"rest_name": cdef.getRESTName(),
                                       "keys": "{keys}"},
                                      app=get_ui_app(request))
        return six.moves.urllib.parse.unquote(the_link)
    return None

@CollectionApp.view(model=Object, name="ui_link", internal=True)
def _get_object_ui_link(model, request):
    return _determine_ui_link(model, request, model.GetClassDef())


@CollectionApp.view(model=CDBObjectHandle, name="ui_link", internal=True)
def _get_handle_ui_link(model, request):
    return _determine_ui_link(model, request, model.getClassDef())


def _determine_ui_link(model, request, cdef):
    if DetailViewModel.provides_detail_view(cdef):
        the_link = request.class_link(DetailViewModel,
                                      {"rest_name": cdef.getRESTName(),
                                       "keys": support.rest_key(model)},
                                      app=get_ui_app(request))
        return six.moves.urllib.parse.unquote(the_link)
    return None
