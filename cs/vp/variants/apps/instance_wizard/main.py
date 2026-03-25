# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import json

from cdb import rte
from cdb import sig
from cdb import util
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.platform.web.base import byname_app
from cs.web.components.base.main import LAYOUT
from cs.platform.web.util import render_file_template

from cs.vp import variants

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class InstanceWizardApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(InstanceWizardApp, self).update_app_setup(app_setup, model, request)

        from cs.vp.variants.apps.instance_wizard.view import _setup
        app_setup["cs-vp-instance-wizard"] = _setup(model, request)

        self.include("jquery", "2.1.0")
        self.include("cs-vp-utils", "15.5.0")
        self.include("cs-vp-tree-component", "15.5.0")
        self.include("cs-vp-rest-tree-component", "15.5.0")
        self.include("cs-vp-list-component", "15.5.0")
        self.include("cs-vp-table-component", "15.5.0")
        self.include("cs-vp-variants-apps-instance_wizard", "15.5.0")


@byname_app.BynameApp.mount(app=InstanceWizardApp, path="instance_wizard")
def _mount_items_app():
    return InstanceWizardApp()


@InstanceWizardApp.path(path='/{product_object_id}/{variant_id}/{teilenummer}')
class InstanceWizardModel(BaseModel):
    """ Web UI model """

    # Labels used in the web app
    LABELS = [
        "cs_items_bom",
        "cdbvp_variants_articles",
        "cdbvp_variants_properties",
        "cdbvp_variants_todo",
        "cdbvp_variants_web_filter",
        "cdbvp_variants_web_filter_placeholder",
        "cdbvp_variants_web_hide_variant_details",
        "cdbvp_variants_web_search",
        "cdbvp_variants_web_search_placeholder",
        "cdbvp_variants_web_show_variant_details",
        "baugruppe",
        "cdbvp_state",
        "cdbvp_variants_assigned_part",
        "cdbvp_variants_open",
        "cdbvp_variants_edited",
        "cdbvp_variants_new_article",
        "cdbvp_variants_variant",
        "cdbvp_instance_created",
        "cdbvp_instantiate_max_bom",
        "cdbvp_variants_shape_now",
        "cdbvp_variants_web_close",
        "cdbvp_variants_web_ajax_err",
        "cdbvp_variants_web_ajax_0",
        "cdbvp_variants_web_error"
    ]

    def __init__(
        self, absorb, product_object_id, variant_id,
        teilenummer, t_index="", instance_oid=""
    ):
        super(InstanceWizardModel, self).__init__()
        self.absorb = absorb

        self.product_object_id = product_object_id
        self.variant_id = variant_id
        self.variant = variants.Variant.ByKeys(product_object_id=product_object_id, id=variant_id)

        self.teilenummer = teilenummer
        self.t_index = t_index

        self.instance_oid = instance_oid

    @property
    def labels(self):
        """ Returns a dict (label id, localized string) containing all the
            labels that are used in the search app.
        """
        result = {lbl: util.Labels()[lbl] for lbl in self.LABELS}
        return result

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]

    @property
    def class_labels(self):
        from cdbwrapc import CDBClassDef
        cdef = CDBClassDef("part")
        return {cd.getClassname(): cd.getDesignation()
                for cd in (cdef,) + cdef.getSubClasses(True)}


@InstanceWizardApp.path(path='/{product_object_id}/{variant_id}/{teilenummer}/{t_index}')
class InstanceWizardModelWithIndex(InstanceWizardModel):
    pass


@InstanceWizardApp.path(path='/{product_object_id}/{variant_id}/{teilenummer}/instance/{instance_oid}')
class InstanceWizardModelWithInstance(InstanceWizardModel):
    pass


@InstanceWizardApp.path(path='/{product_object_id}/{variant_id}/{teilenummer}/{t_index}/instance/{instance_oid}')
class InstanceWizardModelWithIndexAndInstance(InstanceWizardModel):
    pass


@InstanceWizardApp.view(model=InstanceWizardModel, name="app_component", internal=True)
def _setup(self, request):
    return "cs.vp.variants.apps.instance_wizard.index_component"


@InstanceWizardApp.view(model=InstanceWizardModel, name="base_path", internal=True)
def get_base_path(self, request):
    return "/byname/instance_wizard"
