# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import os

from cdbwrapc import CDBClassDef

import urllib.parse

from webob import exc
from cdb import rte
from cdb import sig
from cdb import util
from cdb import fls
from cdb import sqlapi
from cdb import auth
from cdb.objects import Rule
from cdb.objects.org import Organization

from cs.platform.web import static
from cs.platform.web import root

from cs.web.components import plugin_config
from cs.web.components.configurable_ui import ConfigurableUIApp
from cs.web.components.configurable_ui import SinglePageModel
from cs.web.components.outlet_config import replace_outlets
from cs.web.components.pdf import setup_worker_url
from cs.web.components.ui_support import forms

from cs.vp import items
from cs.vp import products
from cs.vp import variants
from cs.vp import bom
from cs.vp.bom.web.bommanager import XBOM_FEATURE, BOMMANAGER_FEATURES, VERSION as BOM_MANAGER_VERSION, get_active_bom_type_setting
from cs.vp.bom.web.bommanager import utils as bommanager_utils
from cs.vp.bom.web.table import VERSION as BOM_TABLE_VERSION
from cs.vp.bom.web.filter import VERSION as BOM_FILTER_VERSION
from cs.vp.bom.web.preview import VERSION as PREVIEW_VERSION

LOG = logging.getLogger(__name__)

COMPONENT_NAME = "cs-vp-bom-web-bommanager"

BOM_TYPE_SETTING_1 = "cs.webcomponents.cs-vp-bom-web-bommanager-active_bomtype"
BOM_TYPE_SETTING_2 = "default"


def include_threed(request):
    try:
        from cs.threed.hoops.web.utils import add_csp_header
    except ImportError:
        return
    else:
        request.after(add_csp_header)


def _get_bom_types():
    return bom.BomType.getActiveBOMTypes()


def _get_feature_infos():
    return {f: fls.is_available(f) for f in BOMMANAGER_FEATURES}


def update_with_common_props(app_setup, request, bom_types=None):
    collection_app = root.get_v1(request).child("collection")
    bom_types_to_use = bom_types if bom_types is not None else _get_bom_types()

    app_setup[COMPONENT_NAME]["xbom_feature"] = XBOM_FEATURE
    app_setup[COMPONENT_NAME]["feature_infos"] = _get_feature_infos()
    app_setup[COMPONENT_NAME]["active_bom_type"] = get_active_bom_type_setting()
    app_setup[COMPONENT_NAME]["bom_types"] = [request.view(t, app=collection_app) for t in bom_types_to_use]

class BommanagerApp(ConfigurableUIApp):
    def update_app_setup(self, app_setup, model, request):
        super(BommanagerApp, self).update_app_setup(app_setup, model, request)

        # BaseErrorModel doesn't have the method update_app_setup
        if hasattr(model, "update_app_setup"):
            model.update_app_setup(app_setup, request)

        setup_worker_url(model, request, app_setup)
        replace_outlets(model, app_setup)


@BommanagerApp.path("{lbom_oid}")
class BommanagerModel(SinglePageModel):
    page_name = "cs-vp-bom-web-bommanager"

    def __init__(self,
        lbom_oid, rbom=None,
        product=None, variant=None,
        signature=None, site=None, site2=None, variability_model=None
    ):
        """
        Important note:
        All objects from url must be loaded and added to the self.rest_objects
        during the initialization! Otherwise there are serious runtime problems in BomManager.

        The problem is a runtime problem. For example, if the 'site' was not present in the rest_objects,
        then the frontend tries to reload it. But this caused a new rendering and then a Javascript exception
        occurred that a generator was already running and the sagas were broken.
        This happens only for objects which are in the URL. So all these must be passed in the app_setup.
        """
        super(BommanagerModel, self).__init__()

        rbom_oid = rbom

        self.classdef = CDBClassDef("part")
        self.rest_objects = set()

        self.bom_types = _get_bom_types()

        self.lbom = items.Item.ByKeys(cdb_object_id=lbom_oid)

        if self.lbom is None:
            raise exc.HTTPNotFound()

        self.rest_objects.add(self.lbom)

        # FIXME: generalize this for other kind of boms
        self.rboms = self.lbom.ManufacturingViews
        self.rest_objects.update(self.rboms)

        self.sites = [
            rbom.ManufacturingSite
            for rbom in self.rboms
            if rbom.ManufacturingSite is not None
        ]
        self.rest_objects.update(self.sites)

        if site is not None:
            site_obj = Organization.ByKeys(cdb_object_id=site)
            if site_obj is not None:
                self.rest_objects.add(site_obj)
            else:
                raise exc.HTTPNotFound()

        if site2 is not None:
            site2_obj = Organization.ByKeys(cdb_object_id=site2)
            if site2_obj is not None:
                self.rest_objects.add(site2_obj)
            else:
                raise exc.HTTPNotFound()

        self.rbom = None
        if rbom_oid is not None:
            self.rbom = rbom = items.Item.ByKeys(cdb_object_id=rbom_oid)
            if rbom is None or rbom not in self.rboms:
                raise exc.HTTPNotFound()


    def get_base_path(self, path):
        return '/'.join(path.split('/')[:3])

    def get_license_error(self):
        mbom_type_id = bom.get_mbom_bom_type().cdb_object_id

        if self.rbom is not None and self.rbom.type_object_id != mbom_type_id:
            # rbom is no mbom, so check for the availability of the xbom license
            # the xbom feature may already have been allocated, this is a noop in that case
            try:
                fls.allocate_license(XBOM_FEATURE)
            except fls.LicenseError as e:
                return e.message
        return None

    def get_no_bom_types_error(self):
        if len(self.bom_types) == 0:
            return util.get_label("web.bommanager.no_bom_type_available")
        return None

    def create_owned_operations_list(self):
        user = auth.persno
        all_roles = util.get_roles('GlobalContext', "", user)
        operations = set(['bommanager_create_rbom', 'bommanager_index_rbom', 'bommanager_replace_position', 'CDB_Index'])

        QUERYSTR = """
            select name from cdb_op_owner 
            where classname='part' and 
            ({role_condition}) and 
            ({operation_names})
            """

        query = QUERYSTR.format(
            role_condition = " OR ".join(["role_id='%s'" % sqlapi.quote(key)
                                       for key in all_roles]),
            operation_names = " OR ".join(["name='%s'" % sqlapi.quote(key)
                                       for key in operations]))

        result = sqlapi.RecordSet2(sql=query)
        queried = set([comp.name for comp in result])

        return operations.intersection(queried)


    @staticmethod
    def get_classnames(classname):
        classdef = CDBClassDef(classname)
        result = [classname]
        result.extend(classdef.getSubClassNames(True))
        return result

    def update_app_setup(self, app_setup, request):
        collection_app = root.get_v1(request).child("collection")

        def link(obj):
            result = request.link(obj, app=collection_app)
            return urllib.parse.unquote(result)

        cmsg = items.Item.MakeCdbcmsg('cdbvp_xbom_manager_show_preview')

        try:
            from cs.threed.hoops import _MODEL_RULE

            rule = Rule.ByKeys(_MODEL_RULE)
            has_geometry = rule.match(self.lbom)
        except ImportError:
            has_geometry = True

        app_setup[COMPONENT_NAME] = {
            "products_catalog": forms.FormInfoBase.get_catalog_config(
                request, "cdbvp_max_bom_products", is_combobox=False, as_objs=True),
            "variants_catalog": forms.FormInfoBase.get_catalog_config(
                request, "cdbvp_variants", is_combobox=False, as_objs=True),
            "xbom_catalog": forms.FormInfoBase.get_catalog_config(
                request, "cdb_mbom_browser2", is_combobox=False, as_objs=True),
            "site_catalog": forms.FormInfoBase.get_catalog_config(
                request, "cdb_manufacturing_site", is_combobox=False, as_objs=True),
            "has_products": bool(self.lbom.Products),
            "lbom_oid": self.lbom.cdb_object_id,
            "rboms": [link(rbom) for rbom in self.rboms],
            "rest_objects": [request.view(obj, app=collection_app) for obj in self.rest_objects],
            "sites": [link(site) for site in self.sites],
            "license_error": self.get_license_error(),
            "available_bomtypes_error": self.get_no_bom_types_error(),
            "preview_url": cmsg.cdbwin_url(),
            "has_geometry": has_geometry,
            "owned_operations": list(self.create_owned_operations_list()),
        }

        update_with_common_props(app_setup, request, self.bom_types)


@root.Root.mount(app=BommanagerApp, path="/bommanager")
def _mount_app():
    return BommanagerApp()


@BommanagerApp.view(model=BommanagerModel, name="base_path", internal=True)
def get_base_path(model, request):
    return model.get_base_path(request.path)


@BommanagerApp.view(model=BommanagerModel, name="document_title", internal=True)
def default_document_title(self, request):
    if len(self.bom_types) == 1:
        t = self.bom_types[0].code
        return util.get_label("web.bommanager.xbom_document_title").format(type=t)
    return util.get_label("web.bommanager.document_title")


@BommanagerApp.view(model=BommanagerModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-web-components-pdf", "15.1.0")
    request.app.include("cs-vp-bom-web-preview", PREVIEW_VERSION)
    request.app.include("cs-vp-items-components", "15.1.0")
    request.app.include("cs-vp-bom-web-table", BOM_TABLE_VERSION)
    request.app.include("cs-vp-bom-web-filter", BOM_FILTER_VERSION)
    include_threed(request)
    request.app.include("cs-vp-bom-web-bommanager", BOM_MANAGER_VERSION)
    return None


# useful for acceptance tests
@BommanagerApp.path("clear_cache")
class ClearCacheModel(object):
    pass


@BommanagerApp.view(model=ClearCacheModel)
def clear_cache(model, request):
    plugin_config.Csweb_plugin.clear_cache()


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-vp-bom-web-bommanager", BOM_MANAGER_VERSION,
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-vp-bom-web-bommanager.js")
    lib.add_file("cs-vp-bom-web-bommanager.js.map")
    static.Registry().add(lib)
