# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Mandatory condition for variants package to be functional with threed:

Class which contains variability
    - has to be retrievable with `cdb.objects.ById`
    - has to have an python relationship `Variants` which has to return object of classes variant
    - has to implement following functions:
        > def multiple_eval(baugruppe, b_index, teilenummer, t_index, variante, position, filters, nconditions=None)
                Apply an arbitrary number of filters to a single BOM position.

                :param filters: A list of BOMFilter objects

                :return: A dictionary which has the object of filters as keys,
                         and values True if the position should be included
                         in the result, according to the filter,
                         and False otherwise.

        > def get_filter_for_signature(signature)
                Retrieve bom filter and hash for signature

                :param signature: variability signature
                :type signature: basestring

                :return: tuple first element is the filter object and second the hash for the signature
                         the filter object needs to have the function:
                            eval(self, baugruppe, b_index, teilenummer, t_index, variante, position, occurrence_id=None, assembly_path=None)
                                    Apply filter to BOM position

                                    :return: True if the position should be included and False otherwise

Class variant
    - has to implement following functions:
        >     def make_variant_filter(self):
                A filter used to filter bom items for specific variant properties
                :return: filter object which needs to have this function:
                        eval(self, baugruppe, b_index, teilenummer, t_index, variante, position, occurrence_id=None, assembly_path=None)
                                Apply filter to BOM position

                                :return: True if the position should be included and False otherwise

        > def get_variability_properties_for_pdf(self, lang=None)
                Provide variability properties for this variant for PDF

                :param lang: Language identifier
                :return: list with tuples each tuple should contain as first entry the name of the property
                         and as second entry the value of the property. These should already be string,
                         For boolean there is a special case look in `helper.py`.

        > def get_variability_properties_info_str(self, lang=None)
                Provide variability properties for threed cockpit of variability object

                :param lang: Language identifier
                :return: list with each entry representing an property/value combination.
                         These have to be merged in a single string.
"""

try:
    from cs.threed.variants import cs_vp_variants_extensions
except ImportError:
    pass

try:
    from cs.threed.variants import cs_variants_extensions
except ImportError:
    pass


def get_variant(variability_model_id, variant_id):
    from cs.vp import variants
    result = variants.Variant.ByKeys(product_object_id=variability_model_id, id=variant_id)

    if result is None:
        from cs.variants import Variant
        result = Variant.ByKeys(variability_model_id=variability_model_id, id=variant_id)

    return result


def get_variant_variability_model(variant):
    try:
        return variant.VariabilityModel
    except AttributeError:
        return variant.Product


def get_variant_variability_model_id(variant):
    try:
        return variant.variability_model_id
    except AttributeError:
        return variant.product_object_id


def get_variant_classes():
    from cs.vp import variants
    classes = (variants.Variant,)
    try:
        from cs.variants import Variant
        classes += (Variant,)
    except ImportError:
        pass
    return classes


def get_variability_properties_for_pdf_by_signature(variability_model_id, signature, lang=None):
    from cs.threed.variants.cs_vp_variants_extensions import get_variability_properties_for_pdf
    return get_variability_properties_for_pdf(variability_model_id, signature, lang)
