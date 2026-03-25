# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import logging
import os
from collections import defaultdict

from cdb import i18n, rte, sig, util
from cdbwrapc import CDBClassDef
from cs.materials import Material
from cs.materials.curve import Curve
from cs.materials.diagram import Diagram
from cs.materials.web.curves.main import LIB_NAME as CURVES_LIB_NAME
from cs.materials.web.curves.main import LIB_VERSION as CURVES_LIB_VERSION
from cs.platform.web import JsonAPI, root, static
from cs.platform.web.base import byname_app
from cs.platform.web.rest import get_collection_app
from cs.platform.web.uisupport import get_ui_link
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel
from cs.web.components.ui_support import forms

COMPONENT_NAME = "cs-materials-web-diff"
LIB_NAME = "cs-materials-web-diff"
LIB_VERSION = "15.1.1"
LOG = logging.getLogger(__name__)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        LIB_NAME, LIB_VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(LIB_NAME + ".js")
    lib.add_file(LIB_NAME + ".js.map")
    static.Registry().add(lib)


class DiffModel(SinglePageModel):
    page_name = "csmat-diff"


class DiffApp(ConfigurableUIApp):
    def update_app_setup(self, app_setup, model, request):
        super(DiffApp, self).update_app_setup(app_setup, model, request)

        self.include(CURVES_LIB_NAME, CURVES_LIB_VERSION)
        self.include(LIB_NAME, LIB_VERSION)

        material_catalog = forms.FormInfoBase.get_catalog_config(
            request, "csmat_material_catalog", is_combobox=False, as_objs=False
        )
        material_catalog["directCreate"] = False
        app_setup[COMPONENT_NAME] = {"material_catalog": material_catalog}


@DiffApp.view(model=DiffModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("csmat_diff")


@byname_app.BynameApp.mount(app=DiffApp, path="csmat_diff")
def _mount_diff_app():
    return DiffApp()


@DiffApp.path(path="", model=DiffModel, absorb=True)
def _get_diff_model(absorb):
    return DiffModel()


@DiffApp.view(model=DiffModel, name="base_path", internal=True)
def _get_diff_base_path(model, request):
    return request.path


class MaterialsInternalApp(JsonAPI):
    def __init__(self, *args, **kwargs):
        super(MaterialsInternalApp, self).__init__(*args, **kwargs)


@root.Internal.mount(app=MaterialsInternalApp, path="cs_materials_diff")
def _mount_internal_app():
    return MaterialsInternalApp()


class MaterialsModel(object):  # just to make morepath happy
    def __init__(self, material_key):
        self.material = None
        try:
            material_id, material_index = material_key.split("@")
            material = Material.ByKeys(
                material_id=material_id, material_index=material_index
            )
            if material.CheckAccess("read"):
                self.material = material
        except Exception:  # pylint: disable=W0703
            pass


@MaterialsInternalApp.path(path="material/{material_key}", model=MaterialsModel)
def get_materials_model(app, material_key):
    return MaterialsModel(material_key)


@MaterialsInternalApp.json(model=MaterialsModel)
def get_material_with_curves(model, request):
    def get_diagrams(material):
        for diagram in Diagram.KeywordQuery(
            material_id=material.material_id,
            material_index=material.material_index,
        ):
            if diagram.diagram_type not in diagram_types:
                diagram_types.add(diagram.diagram_type)
                diagram_ids.add(diagram.cdb_object_id)
                diagrams[diagram.diagram_type] = request.view(
                    diagram, app=collection_app
                )
                diagrams[diagram.diagram_type][
                    "system:parent_material_description"
                ] = material.GetDescription()
                diagrams[diagram.diagram_type][
                    "system:parent_material_link"
                ] = get_ui_link(request, material)
        parent_variant = parent_variants.get(material.variant_of_oid)
        if parent_variant:
            get_diagrams(parent_variant)

    if model.material:
        collection_app = get_collection_app(request)

        parent_variants = {}
        for variant in model.material.get_parent_variants():
            parent_variants[variant.cdb_object_id] = variant

        diagrams = {}
        diagram_ids = set()
        diagram_types = set()
        get_diagrams(model.material)

        curves = defaultdict(list)
        for curve in Curve.Query(Curve.diagram_id.one_of(*diagram_ids)):
            curves[curve.diagram_id].append(request.view(curve, app=collection_app))

        return {
            "material": request.view(model.material, app=collection_app),
            "diagrams": diagrams,
            "curves": curves,
        }
    else:
        return {}


class MaterialsMetadataDiffModel(object):  # just to make morepath happy
    def __init__(self, material0_key, material1_key):
        self.material0 = None
        self.material1 = None

        try:
            material0 = Material.ByKeys(cdb_object_id=material0_key)
            material1 = Material.ByKeys(cdb_object_id=material1_key)
            if material0.CheckAccess("read") and material1.CheckAccess("read"):
                self.material0 = material0
                self.material1 = material1
        except Exception:  # pylint: disable=W0703
            pass

    @staticmethod
    def black_list(key):
        if key in [
            "cdb_objektart",
            "cdb_object_id",
            "cdb_cpersno",
            "cdb_cdate",
            "cdb_mpersno",
            "cdb_mdate",
            "role_id",
            "status",
            "variant_type",
        ]:
            return False
        return True

    def diff(self):
        languages = i18n.getActiveGUILanguages()

        cdef = CDBClassDef(self.material0.GetClassname())

        attribute_data = {}

        fields_to_compare = filter(
            MaterialsMetadataDiffModel.black_list,
            Material.GetFieldNames(addtl_field_type=any),
        )
        for field_name in fields_to_compare:
            # Get the label for the attribute
            attribute_definition = cdef.getAttributeDefinition(field_name)
            if attribute_definition is None:
                raise ValueError(
                    "Missing attribute definition of {}".format(field_name)
                )

            attr_lang = attribute_definition.getIsoLang()
            if (
                not attribute_definition.is_multilang()
                and (  # Do not show multi language base fields
                    not attr_lang
                    or attr_lang in languages  # Only show the active languages
                )
            ):
                label = attribute_definition.getLabel()

                # Check if the value has been changed and set the change flag
                left_value = self.material0[field_name]
                if left_value is None:
                    left_value = ""
                right_value = self.material1[field_name]
                if right_value is None:
                    right_value = ""
                is_changed = False
                if left_value != right_value:
                    is_changed = True

                # Handle the parent material reference separately
                if field_name == "variant_of_oid":
                    variant_of_oid0 = self.material0["variant_of_oid"]
                    variant_of_oid1 = self.material1["variant_of_oid"]
                    if variant_of_oid0:
                        baseMaterial = Material.ByKeys(
                            cdb_object_id=self.material0["variant_of_oid"]
                        )
                        left_value = baseMaterial.GetDescription()
                    if variant_of_oid1:
                        baseMaterial = Material.ByKeys(
                            cdb_object_id=self.material1["variant_of_oid"]
                        )
                        right_value = baseMaterial.GetDescription()
                    field_name = "derived_from"

                # Add the attribute data to the result
                attribute_data[field_name] = dict(
                    changed=is_changed, left=left_value, right=right_value, label=label
                )

        return dict(
            left_title=self.material0.GetDescription(),
            right_title=self.material1.GetDescription(),
            attribute_diff=attribute_data,
        )


@MaterialsInternalApp.path(
    path="metadata/{material0_key}/{material1_key}", model=MaterialsMetadataDiffModel
)
def get_materials_metadata_diff_model(app, material0_key, material1_key):
    return MaterialsMetadataDiffModel(material0_key, material1_key)


@MaterialsInternalApp.json(model=MaterialsMetadataDiffModel)
def get_materials_metadata_diff(model, request):
    return model.diff()
