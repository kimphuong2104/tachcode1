# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

import os

import hashlib
import morepath
from webob.exc import HTTPNotFound

from cdb import fls
from cdb import rte
from cdb import sig
from cdb import util as cdb_util
from cdb.objects import ByID

from cs.documents import Document
from cs.platform.web import root
from cs.platform.web import static
from cs.vp.items import Item
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK
from cs.web.components.configurable_ui import ConfigurableUIApp
from cs.web.components.configurable_ui import ConfigurableUIModel
from cs.web.components.configurable_ui import SinglePageModel

from cs.threed.hoops import markup
from cs.threed.hoops.utils import MONOLITHIC_FILETYPES
from cs.threed.hoops.web.utils import add_csp_header


__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


COMPONENT_NAME = "cs-threed-hoops-web-cockpit"


# FRONTEND_LICENSES lists all the licenses the frontend uses. They are allocated when
# the user opens the cockpit and added to appSetup with a boolean flag indicating
# if the license could be allocated or not
FRONTEND_LICENSES = [
    "3DSC_003",  # 3DC: Redlining
    "3DSC_004",  # 3DC: Measurements
    "3DSC_005",  # 3DC: View
    "3DSC_006",  # 3DC: Snapshots
    "3DSC_019",  # 3DC: Read BCF
    "3DSC_020",  # 3DC: Write BCF
]

def md5_hash(message):
    h = hashlib.md5()
    h.update(message)
    return h.hexdigest()


class CockpitApp(ConfigurableUIApp):
    def __init__(self, document_id, part_id):
        super(CockpitApp, self).__init__()
        self.document = Document.ByKeys(cdb_object_id=document_id)
        self.part = None

        # if a shared link of a cs.threed version < 15.7.0 is opened,
        # the context object which is now always a document could still
        # be the id of a part. If no document is found with the given id,
        # we try the id for a part instead.
        if self.document is None:
            self.part = Item.ByKeys(cdb_object_id=document_id)
            if self.part:
                self.document = self.part.get_3d_model_document()
        
        if self.document is None:
            raise HTTPNotFound

        if self.part is None:
            self.part = Item.ByKeys(cdb_object_id=part_id)

    def get_title(self):
        if self.part is not None:
            return self.part.GetDescription()
        return self.document.GetDescription()

class CockpitAppPart(CockpitApp):
    pass

class ConfigurableModel(SinglePageModel):
    page_name = "cs-threed-cockpit"

    def __init__(self):
        super(ConfigurableModel, self).__init__()
        self.variant = None
        self.variability_model_id = None
        self.signature = None
        self.add_plugin_context("cs-threed-cockpit-bom-filter")


class VariantModel(ConfigurableModel):
    def __init__(self, variant):
        super(VariantModel, self).__init__()
        self.variant = variant

        if self.variant is None:
            raise HTTPNotFound("Variant not found")


class SignatureModel(ConfigurableModel):
    def __init__(self, variability_model_id, signature):
        super(SignatureModel, self).__init__()

        # Old variant management:
        #     variability_model_id -> Product.cdb_object_id
        #     signature -> signature
        # New variant management:
        #     variability_model_id -> VariabilityModel.cdb_object_id
        #     signature -> classification_data_signature
        self.variability_model_id = variability_model_id
        self.signature = signature


class VariabilityModelModel(ConfigurableModel):
    def __init__(self, variability_model_id):
        super(VariabilityModelModel, self).__init__()
        self.variability_model_id = variability_model_id


class ProductModel(object):
    def __init__(self, product_object_id):
        self.product_object_id = product_object_id


@root.Root.mount(app=CockpitApp, path="/cs-threed-hoops-web-cockpit/{document_id}")
def _mount_app(document_id, part=None):
    return CockpitApp(document_id, part_id=part)


@root.Root.mount(app=CockpitAppPart, path="/cs-threed-hoops-web-cockpit-part/{part_object_id}")
def _mount_app_part(part_object_id):
    item = Item.ByKeys(cdb_object_id=part_object_id);
    if item is None:
        raise HTTPNotFound("Part not found")
    doc = item.get_3d_model_document()
    if doc is None:
        raise HTTPNotFound("Document not found")
    return CockpitAppPart(doc.cdb_object_id, part_id=part_object_id)


@CockpitAppPart.path(path="", model=ConfigurableModel)
def _get_model():
    return ConfigurableModel()


@CockpitAppPart.path(path="variability_model/{variability_model_id}", model=VariabilityModelModel)
def _get_variability_model_model(variability_model_id):
    # Everything is called variability_model nowadays but for old variant management this is a product oid
    return VariabilityModelModel(variability_model_id)


@CockpitAppPart.path(path="variant/{v_oid}", model=VariantModel)
def _get_variant_model(v_oid):
    variant = ByID(v_oid)
    return VariantModel(variant=variant)


@CockpitApp.path(path="", model=ConfigurableModel)
def _get_model():
    return ConfigurableModel()


@CockpitApp.path(path="variant/{v_oid}", model=VariantModel)
def _get_variant_model(v_oid):
    variant = ByID(v_oid)
    return VariantModel(variant=variant)


# For legacy support we redirect the product url to the new variability url
@CockpitApp.view(model=ProductModel)
def _redirect_product_model(model, request):
    return morepath.redirect(request.link(VariabilityModelModel(model.product_object_id)))


@CockpitApp.view(model=ConfigurableModel, name="document_title", internal=True)
def default_document_title(model, request):
    return request.app.get_title()


@sig.connect(ConfigurableModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    request.after(add_csp_header)

    doc = request.app.document
    part = request.app.part

    context = part if part else doc

    views = markup.View.KeywordQuery(context_object_id=context.cdb_object_id)
    collection_app = root.get_v1(request).child("collection")

    from cs.threedlibs.web.communicator.main import VERSION
    communicator_lib = static.Registry().get("cs-threedlibs-communicator", VERSION)

    from cs.threed.hoops.web.tree.main import COMPONENT_NAME as TREE_COMPONENT_NAME
    from cs.threed.hoops.web.tree.main import COMPONENT_VERSION as TREE_COMPONENT_VERSION
    tree_lib = static.Registry().get(TREE_COMPONENT_NAME, TREE_COMPONENT_VERSION)
    tree_fname = tree_lib.find_hashed_filepath(TREE_COMPONENT_NAME + ".js")

    from cs.vp.bom.web.table import VERSION as BOM_TABLE_VERSION
    request.app.include("cs-vp-bom-web-table", BOM_TABLE_VERSION)

    from cs.vp.bom.web.filter import COMPONENT_NAME as FILTER_COMP_NAME, VERSION as FILTER_VERSION
    request.app.include(FILTER_COMP_NAME, FILTER_VERSION)

    from cs.vp.bom.web.product_structure import VERSION as PRODUCT_STRUCTURE_VERSION
    request.app.include("cs-vp-bom-web-product_structure", PRODUCT_STRUCTURE_VERSION)

    app_setup.update({
        COMPONENT_NAME: {
            "document": request.view(doc, app=collection_app),
            "enginePath": communicator_lib.url(),
            "customViews": [view.get_elink_data(request) for view in views],
            "licenses": {l: fls.get_license(l) for l in FRONTEND_LICENSES},
            "health_checker": cdb_util.get_prop("3dhc") == "true",
            "measurements": [m.get_elink_data() for m in
                             markup.Measurement.KeywordQuery(context_object_id=doc.cdb_object_id)],
            "tree_lib_url": "%s/%s" % (tree_lib.url(), os.path.basename(tree_fname)),
            # The monolithic file types will always fall back to the 3D structure tree
            "fallback_tree_filetypes": MONOLITHIC_FILETYPES,
            # TODO: add a customizable display name as dict value
            "cad_variants": {cv.cdb_object_id: {"name": cv.variant_name, "label": cv.variant_name} for cv in
                             doc.CADVariants}
        }
    })

    if part is not None:
        app_setup[COMPONENT_NAME].update({
            "part": request.view(part, app=collection_app)
        })


@CockpitApp.view(model=ConfigurableModel, name="application_id", internal=True)
def get_application_id(self, request):
    return "cs-threed-cockpit"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-threed-hoops-web-cockpit", "15.5.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-threed-hoops-web-cockpit.js")
    lib.add_file("cs-threed-hoops-web-cockpit.js.map")
    static.Registry().add(lib)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def update_app_setup(app_setup, request):
    from cs.threed import services
    broker_ep = services.get_broker_endpoint()
    if broker_ep:
        app_setup.merge_in([COMPONENT_NAME], {
            "broker_url": broker_ep["url"]
        })
