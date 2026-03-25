# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import classbody
from cdb.objects import Reference_N, Forward

from cs.classification.units import UnitCache

from cs.threed.variants.helper import get_pdf_boolean

from cs.variants import Variant, VariabilityModel

fMeasurement = Forward("cs.threed.hoops.markup.Measurement")
fViewerSnapshot = Forward("cs.threed.hoops.markup.ViewerSnapshot")
fView = Forward("cs.threed.hoops.markup.View")


@classbody.classbody
class Variant(object):
    ViewerMeasurements = Reference_N(fMeasurement,
                                     fMeasurement.context_object_id == Variant.cdb_object_id)
    ViewerSnapshots = Reference_N(fViewerSnapshot,
                                  fViewerSnapshot.context_object_id == Variant.cdb_object_id)
    ViewerViews = Reference_N(fView,
                              fView.context_object_id == Variant.cdb_object_id)

    def yield_variability_properties(self, lang=None):
        variant_driving_properties_with_values = self.get_variant_driving_properties_with_values()
        metadata = variant_driving_properties_with_values["metadata"]
        properties = variant_driving_properties_with_values["properties"]
        for property_code in metadata:
            property_name = metadata[property_code]["name"]
            # Hardcode Index 0 because variant driving
            try:
                property_value = properties[property_code][0]["value"]
            except (KeyError, IndexError):
                property_value = None

            if isinstance(property_value, dict):
                property_float_text = "{0}".format(property_value["float_value"])
                unit_object_id = property_value.get("unit_object_id", None)
                if unit_object_id is not None:
                    unit_label = UnitCache.get_unit_label(unit_object_id)
                    property_float_text += " {0}".format(unit_label)

                property_value = property_float_text

            yield property_name, property_value

    def get_variability_properties_for_pdf(self, lang=None):
        """
        Provide variability properties for this variant for PDF

        :param lang: Language identifier
        :return: list with tuples each tuple should contain as first entry the name of the property
                 and as second entry the value of the property. These should already be string,
                 For boolean there is a special case look in `helper.py`.
        """
        result = []
        for property_name, property_value in self.yield_variability_properties(lang=lang):
            if isinstance(property_value, bool):
                property_value = get_pdf_boolean(property_value)
            elif property_value is None:
                property_value = str(property_value)

            result.append((property_name, property_value))

        return result

    def get_variability_properties_info_str(self, lang=None):
        """
        Provide variability properties for threed cockpit of variability object

        :param lang: Language identifier
        :return: list with each entry representing an property/value combination.
                 These have to be merged in a single string.
        """
        result = []
        for property_name, property_value in self.yield_variability_properties(lang=lang):
            result.append("{0}={1}".format(property_name, property_value))

        return result


@classbody.classbody
class VariabilityModel(object):
    pass
