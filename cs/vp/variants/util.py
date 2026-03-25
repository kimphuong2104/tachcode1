#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import misc


class VariantInfoTextGenerator(object, metaclass=misc.Singleton):
    def __init__(self):
        self.cache_filled = {}

        self.properties_by_id = {}
        self.enum_definitions_by_key = {}

    def _set_cache_default(self, variant, clear_all):
        if clear_all is True:
            self.properties_by_id = {}
            self.enum_definitions_by_key = {}
            self.cache_filled = {}
        elif variant is not None:
            product_id = variant.product_object_id
            try:
                del self.properties_by_id[product_id]
                del self.enum_definitions_by_key[product_id]
                del self.cache_filled[product_id]
            except KeyError:
                # when they are not cached, do nothing
                pass

    @staticmethod
    def _get_pv_cache_key(pv, lang):
        return pv.product_object_id, pv.variant_id, pv.id, lang

    def _get_enum_def_for_prop_value(self, prop_value, product_id):
        if (prop_value.id, prop_value.value) in self.enum_definitions_by_key.get(product_id, []):
            return self.enum_definitions_by_key[product_id][prop_value.id, prop_value.value]
        return None

    def _get_property_for_prop_value(self, prop_value, product_id):
        if prop_value.id in self.properties_by_id.get(product_id, []):
            return self.properties_by_id[product_id][prop_value.id]
        return None

    def _get_info_string(self, prop_value, lang, product_id):
        prop = self._get_property_for_prop_value(prop_value, product_id)
        enum_def = self._get_enum_def_for_prop_value(prop_value, product_id)
        return prop_value.info_str(lang, prop, enum_def)

    def _fill_cache(self, product_object_id):
        from cs.vp.variants import Property, EnumDefinition
        properties = Property.KeywordQuery(product_object_id=product_object_id)
        self.properties_by_id[product_object_id] = {p.id: p for p in properties}
        enum_definitions = EnumDefinition.KeywordQuery(product_object_id=product_object_id)
        self.enum_definitions_by_key[product_object_id] = {(e.id, e.value): e for e in enum_definitions}
        self.cache_filled[product_object_id] = True

    def get_variant_info_string(self, variant, lang):
        product_id = variant.product_object_id
        if not self.cache_filled.get(product_id, False):
            self._fill_cache(product_id)
        return ", ".join([
            self._get_info_string(pv, lang, product_id) for pv in variant.PropertyValues
        ])[:256]

    def clear_cache(self, variant=None, clear_all=False):
        self._set_cache_default(variant, clear_all)
