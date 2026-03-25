# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import classbody, ue, util, i18n
from cdb.objects import Reference_N, Forward

from cs.vp.variants import Variant, BasicProblemSolver, Property
from cs.vp.variants.apps import generatorui

from cs.threed.variants.helper import get_pdf_boolean

fMeasurement = Forward("cs.threed.hoops.markup.Measurement")
fViewerSnapshot = Forward("cs.threed.hoops.markup.ViewerSnapshot")
fView = Forward("cs.threed.hoops.markup.View")


def get_value_text(prop, value_id, lang):
    if value_id in [True, False]:
        return get_pdf_boolean(value_id)
    elif prop.EnumByValue[value_id]:
        return prop.EnumByValue[value_id].ValueText[lang]
    else:
        return value_id


def get_variability_properties_for_pdf(variability_model_id, signature, lang=None):
    if lang is None:
        lang = i18n.default()

    result = []
    values = BasicProblemSolver.parseSolutionSignature(signature)
    for prop_id, value_id in values.items():
        prop = Property.ByKeys(product_object_id=variability_model_id, id=prop_id)
        if prop:
            name_text = prop.Name[lang]
            value_text = get_value_text(prop, value_id, lang)
            result.append((name_text, value_text))


@classbody.classbody
class Variant(object):
    ViewerMeasurements = Reference_N(fMeasurement,
                                     fMeasurement.context_object_id == Variant.cdb_object_id)
    ViewerSnapshots = Reference_N(fViewerSnapshot,
                                  fViewerSnapshot.context_object_id == Variant.cdb_object_id)
    ViewerViews = Reference_N(fView,
                              fView.context_object_id == Variant.cdb_object_id)

    def on_threed_cockpit_now(self, ctx):
        maxbom = self._get_max_bom_item(ctx)
        url = "/cs-threed-hoops-web-cockpit/%s/variant/%s" % (maxbom.cdb_object_id, self.cdb_object_id)
        return ue.Url4Context(url)

    def get_variability_properties_for_pdf(self, lang=None):
        """
        Provide variability properties for this variant for PDF

        :param lang: Language identifier
        :return: list with tuples each tuple should contain as first entry the name of the property
                 and as second entry the value of the property. These should already be string,
                 For boolean there is a special case look in `helper.py`.
        """
        if lang is None:
            lang = i18n.default()

        result = []
        for pv in self.PropertyValues:
            if pv.Property:
                name_text = pv.Property.Name[lang]
                value_text = get_value_text(pv.Property, pv.get_value(), lang)
                result.append((name_text, value_text))

        return result

    def get_variability_properties_info_str(self, lang=None):
        """
        Provide variability properties for threed cockpit of variability object

        :param lang: Language identifier
        :return: list with each entry representing an property/value combination.
                 These have to be merged in a single string.
        """
        return [pv.info_str(lang) for pv in self.PropertyValues]

    event_map = {
        ("threed_cockpit", "pre_mask"): "_select_max_bom_dlg",
    }

# -- Plugin for the variant editor ---------------------------------------------
def show_in_cockpit(state_id, selected_row, selected_maxbom_oid=None):
    app = generatorui._getapp()

    state = app.getState(state_id)

    if state:
        generator = state.generator

        pvalues, vinfo = state.grid_data_mapping[int(selected_row)]
        product = generator._product

        # determine max bom
        maxbom = app._get_maxbom(product, selected_maxbom_oid)

        # determine filterable variant and build catia ctrl lines
        variant = app._get_filter_variant(product, vinfo)
        if variant:
            url = variant.MakeURL("threed_cockpit",
                                  **{"cdb::argument.maxbom_oid": maxbom.cdb_object_id})
        else:
            # Try to retrieve the max bom view solution from the solver
            solution = generator.getFilterSolution(pvalues)
            if solution:
                signature = solution.split(";")[1]
                url = "/cs-threed-hoops-web-cockpit/%s/signature/%s/%s" % (
                    maxbom.cdb_object_id, product.cdb_object_id,
                    signature
                    # urllib.quote(signature)
                )
            else:
                raise util.ErrorMessage("cdbvp_err_no_unique_mapping")
        return {"url": url}


generatorui.register_plugin({
    "icon": "threed_viewer_3d",
    "label": "threed_hoops_show_in_viewer",
    "json_name": "show_in_cockpit",
    "json": show_in_cockpit,
    "position": 100,
})
