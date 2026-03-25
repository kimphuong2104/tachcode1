#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module Filter

Filter BOM structures according to conditions from VPMs.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
import logging

from collections import namedtuple
from typing import Optional, Any, Self

from cdb import cad, kernel, sqlapi, util
from cdb.objects import Forward
from cdb.sqlapi import Record

from cs.vp.bom.enhancement.plugin import Dependencies, AbstractPlugin, AbstractRestPlugin
from cs.vp.utils import parse_url_query_args
from cs.vp.variants import Variant, bomlinks, properties, solvers
from cs.vp.products import Product

fProduct = Forward("cs.vp.products.Product")

kMaxBOMRatingMethodPredicateBased = 1
kMaxBOMRatingMethodSingleProperty = 2

_MAXBOM_RATING_METHOD = None

LOG = logging.getLogger(__name__)

def get_maxbom_rating_method():
    global _MAXBOM_RATING_METHOD
    if _MAXBOM_RATING_METHOD is None:
        # property vprm is for dev only!!
        vprm = util.get_prop('vprm')
        if vprm:
            _MAXBOM_RATING_METHOD = int(vprm)
            return _MAXBOM_RATING_METHOD

        if len(bomlinks.BOMMapping.Query()):
            # Rating by single properties attached to BOM positions
            _MAXBOM_RATING_METHOD = kMaxBOMRatingMethodSingleProperty
        if len(bomlinks.BOM_Predicate.Query()) and _MAXBOM_RATING_METHOD is not None:
            raise RuntimeError("CDBVP Variant Management: Error: "
                               "Cannot determine max bom rating method (predicate based or single property). "
                               "Found ratings in both tables (cdbvp_bom_predicate, cdbvp_bom_mapping). "
                               "Different rating methods cannot be used together.")

        if _MAXBOM_RATING_METHOD is None:
            # Rating by complex conditions using a list of predicates
            # attached to a BOM position
            _MAXBOM_RATING_METHOD = kMaxBOMRatingMethodPredicateBased
    return _MAXBOM_RATING_METHOD


class BOMFilter(object):
    """ Filter BOM positions according to the given property values
    """

    def __init__(self, product_object_id, property_values):
        self.product_object_id = product_object_id
        self.product = fProduct.ByKeys(product_object_id)
        self.property_values = property_values
        self.prop_dict = dict(self.property_values)
        self.product_object_ids = [product_object_id]
        self.init_module_mapping(self.product)
        self.rating_method = get_maxbom_rating_method()

        self.predicates = bomlinks.get_predicates(product_object_id)
        self.terms = bomlinks.get_terms(product_object_id)

        solver = bomlinks.Predicate_Expression_Solver(product_object_id, {})
        self.properties = solver.get_properties()
        self.values = solver.get_values()

    def init_module_mapping(self, product, parent_mapping_dict=None):
        """
        Loads the complete sub module structure with property
        mapping between parent and sub modules.
        """
        for ref in product.SubproductReferences:
            sub_product = ref.SubProduct
            if sub_product:
                self.product_object_ids.append(sub_product.cdb_object_id)
                prop_mappings = properties.Property2SubProductProperty.KeywordQuery(
                    product_object_id=product.cdb_object_id,
                    subproduct_object_id=sub_product.cdb_object_id
                )
                mapping_dict = dict([(m.property_id, m.subproduct_property_id) for m in prop_mappings])
                if mapping_dict:
                    for k, v in mapping_dict.items():
                        if k in self.prop_dict:
                            self.prop_dict[v] = self.prop_dict[k]
                self.init_module_mapping(sub_product, mapping_dict)

    def eval_bom_item(self, bom_item):
        """
        Appl filter to bom item. This is an compatibility eval for new and old variantmanagement
        """
        if hasattr(bom_item, "has_predicates") and not bom_item.has_predicates:
            return True

        return self.eval(
            bom_item.baugruppe,
            bom_item.b_index,
            bom_item.teilenummer,
            bom_item.t_index,
            bom_item.variante,
            bom_item.position
        )

    def eval(self, baugruppe, b_index, teilenummer, t_index, variante, position):
        """
        Apply filter to BOM position

        :return: True if the position should be included and False otherwise
        """

        def eval_predicate_based():
            bom_predicates = self.predicates[(
                baugruppe, b_index, teilenummer, variante, position
            )]

            if bom_predicates:
                result = False
                for predicate in bom_predicates:
                    # this is not very nice, but we want to avoid constructing the cdb object
                    # for performance reasons
                    if predicate.cdb_classname == "cdbvp_bom_string_predicate":
                        return bomlinks.BOM_String_Predicate.compute(
                            self.product_object_id, predicate.expression, self.prop_dict,
                            product_properties=self.properties,
                            product_values=self.values
                        )
                    elif predicate.cdb_classname == "cdbvp_bom_predicate_term":
                        terms = self.terms[(
                            baugruppe, b_index, teilenummer, variante, position, predicate.predicate_id
                        )]
                        if all(bomlinks.BOM_Term.eval_term(term, self.prop_dict) for term in terms):
                            result = True
                            break
            else:
                result = True
            return result

        def eval_single_property_based():
            bom_properties = bomlinks.BOMMapping.Query(
                (bomlinks.BOMMapping.baugruppe == baugruppe) &
                (bomlinks.BOMMapping.b_index == b_index) &
                (bomlinks.BOMMapping.teilenummer == teilenummer) &
                (bomlinks.BOMMapping.variante == variante) &
                (bomlinks.BOMMapping.position == position) &
                (bomlinks.BOMMapping.vpm_product_object_id.one_of(*self.product_object_ids))
            )
            if bom_properties:
                for prop in bom_properties:
                    if self.prop_dict.get(int(prop.property_id), None) != int(prop.property_value):
                        return False
            return True

        if self.rating_method == kMaxBOMRatingMethodSingleProperty:
            return eval_single_property_based()
        elif self.rating_method == kMaxBOMRatingMethodPredicateBased:
            return eval_predicate_based()
        else:
            raise RuntimeError("'%s' is not a valid max bom rating method." % self.rating_method)


class VariantBOMFilter(BOMFilter):
    """ Encapsulates the logic for evaluating the conditions attached to BOM
        positions in the context of a variant.
    """

    def __init__(self, product_object_id, variant_number):
        variant = Variant.ByKeys(variant_number, product_object_id)
        BOMFilter.__init__(self, product_object_id,
                           list(zip(variant.PropertyValues.id,
                                    [pv.get_value() for pv in variant.PropertyValues])))


class VirtualVariantBOMFilter(BOMFilter):
    """ Encapsulates the logic for evaluating the conditions attached to BOM
        positions in the context of a not-saved variant.
    """

    def __init__(self, product_object_id, signature):
        BOMFilter.__init__(self, product_object_id,
                           solvers.BasicProblemSolver.parseSolutionSignature(signature))


def filter(bom_filter, data):
    colindex = {}
    for col in range(sqlapi.SQLcols(data)):
        name = sqlapi.SQLname(data, col)
        colindex[name] = col

    def get(name, row, sqltype=None):
        if sqltype is None:
            sqltype = sqlapi.SQLstring
        return sqltype(data, colindex[name], row)

    deletions = []
    for row in range(sqlapi.SQLrows(data)):
        filter_result = bom_filter.eval(baugruppe=get("baugruppe", row),
                                        b_index=get("b_index", row),
                                        teilenummer=get("teilenummer", row),
                                        t_index=get("t_index", row),
                                        variante=get("variante", row),
                                        position=get("position", row, sqlapi.SQLinteger))
        if not filter_result:
            deletions.append(row)

    deletions.reverse()
    for x in deletions:
        ref = data.rowof(x)
        data.remove(ref)


class Filter(kernel.TableFilter):
    def execute(self, data, filter_info=None):
        if (filter_info and filter_info.getClassname() == "bom_item") or not filter_info:
            product_object_id, variant_number = self.get_filter_id().split(":")
            v_filter = VariantBOMFilter(product_object_id, int(variant_number))
            filter(v_filter, data)


class VirtualVariantFilter(kernel.TableFilter):
    def execute(self, data, filter_info=None):
        if (filter_info and filter_info.getClassname() == "bom_item") or not filter_info:
            product_object_id, pvalues = self.get_filter_id().split(";")
            vv_filter = VirtualVariantBOMFilter(product_object_id, pvalues)
            filter(vv_filter, data)


FilterResult = namedtuple("FilterResult", "path active")


class ProductStructureFilter(object):
    def __init__(self, product_object_id, properties, bom_item_callback=None, item_callback=None):
        self.filter = BOMFilter(product_object_id, properties)
        self.bom_item_callback = bom_item_callback
        self.item_callback = item_callback

    def walk(self, bom, path=()):

        if self.item_callback and not self.item_callback(bom):
            return

        for component in bom.Components:
            if self.bom_item_callback and not self.bom_item_callback(component):
                continue

            drin = self.filter.eval(baugruppe=component.baugruppe,
                                    b_index=component.b_index,
                                    teilenummer=component.teilenummer,
                                    t_index=component.t_index,
                                    variante=component.variante,
                                    position=component.position)
            result_item = FilterResult(path=(component,) + path, active=drin)
            yield result_item
            if component.Item:
                new_path = (component,) + path
                for result in self.walk(component.Item, new_path):
                    yield result


class CatiaRemoteControl(object):
    SEPARATOR = "|@|"

    def __init__(self, maxbom):
        self.maxbom = maxbom
        self.stl_mode_condition_value = cad.getCADConfValue('STL Mode condition value', "CatiaV5")
        self.stl_mode_condition_attr = cad.getCADConfValue('STL Mode condition attribute', "CatiaV5")

    def get_ctrl_lines(self, product_object_id, props):
        ctrl_lines = ["Instanz ID;Instanz aktiv"]
        properties = list(props.items())
        filter_ = ProductStructureFilter(product_object_id,
                                         properties,
                                         self.filter_bom_item_callback,
                                         self.filter_item_callback)

        for node in filter_.walk(self.maxbom):
            occurence_id_path = []
            for bom_item in reversed(node.path):
                if not bom_item.occurence_id:
                    rating_method = get_maxbom_rating_method()
                    ratings = 0
                    if rating_method == kMaxBOMRatingMethodPredicateBased:
                        ratings = len(bom_item.VPMPredicates)
                    elif rating_method == kMaxBOMRatingMethodSingleProperty:
                        ratings = len(bom_item.VPMProperties)
                    if ratings:
                        self.handle_missing_occurence_id(node)
                    else:
                        occurence_id_path = []
                        break
                occurence_id_path.append(bom_item.occurence_id)
            if occurence_id_path:
                instance_id = CatiaRemoteControl.SEPARATOR.join(occurence_id_path)
                ctrl_lines.append("{0};{1}".format(instance_id, "1" if node.active else "0"))
        return ctrl_lines

    def get_variant_ctrl_lines(self, variant_obj):
        return self.get_ctrl_lines(variant_obj.product_object_id,
                                   variant_obj.get_property_values())

    def filter_bom_item_callback(self, bom_item):
        return bom_item.cadsource == "catia"

    def filter_item_callback(self, item):
        if self.stl_mode_condition_attr:
            return "%s" % (item[self.stl_mode_condition_attr]) == self.stl_mode_condition_value
        else:
            return True

    def handle_missing_occurence_id(self, node):
        """ Builds a message as follows and raises it as util.ErrorMessage Exception:

        Fehlende CATIA Vorkommensinformation (occurence_id)
        an folgender Stücklistenposition (Pfad ausgehend von der Top Level Baugruppe):
        Position 10: 1272782/a --> Position 40: 2333443/b -> ...

        Description of path elements (bom items) can be configured by
        cdbvp_cadctrl_err_bomitem_dtag Message.
        Leading text can be configured by cdbvp_cadctrl_err_occurence_id
        Message.
        """

        pattern = None
        from cdb.platform import gui
        m = gui.Message.ByName("cdbvp_cadctrl_err_bomitem_dtag")
        if m:
            pattern = m.Text['']

        path = []
        for bom_item in reversed(node.path):
            if pattern:
                path.append(bom_item.ApplyDescriptionPattern(pattern))
            else:
                path.append(bom_item.GetDescription())

        raise util.ErrorMessage("cdbvp_cadctrl_err_occurence_id", " --> ".join(path))


class CsVpVariantsProductContextPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.vp.variantFilterProductContext"

    def __init__(self, product_object_id) -> None:
        if product_object_id is None:
            raise ValueError("Need a product_object_id")

        self.product_object_id = product_object_id

    @classmethod
    def create_from_rest_data(cls, rest_data: Optional[Any], dependencies: Dependencies) -> Optional[Self]:
        if rest_data is None:
            return None

        product_object_id = rest_data["product_object_id"]
        return cls(product_object_id)

    @classmethod
    def create_for_default_data(cls, dependencies: Dependencies, **kwargs: Any) -> Optional[Self]:
        bom_table_url = kwargs.get("bom_table_url")
        url_query_args = parse_url_query_args(bom_table_url)

        product_id = url_query_args.get("product", None)
        if product_id is None:
            return None

        return cls(product_id)

    def get_default_data(self) -> tuple[Any, Any]:
        if self.product_object_id is None:
            return None, None

        product = Product.ByKeys(cdb_object_id=self.product_object_id)
        if product is None:
            # todo: remove query parameter from url?
            LOG.info("%s: the url query parameter 'product' (value: '%s') refer to a non-existing object",
                     self.__class__.__name__, self.product_object_id)
            return None, None

        return ({
            "product_object_id": self.product_object_id,
            "system:description": product.GetDescription()
        }, None)


class CsVpVariantsFilterContextPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.vp.variantFilterContext"
    DEPENDENCIES = (CsVpVariantsProductContextPlugin,)

    def __init__(self, context_plugin: CsVpVariantsProductContextPlugin,
                 variant_object_id: Optional[str] = None,
                 signature: Optional[str] = None) -> None:

        if variant_object_id is None and signature is None:
            raise ValueError("variant_id **or** signature is needed")

        if variant_object_id is not None and signature is not None:
            raise ValueError("Only variant_id **or** signature is supported")

        self.product_context_plugin: CsVpVariantsProductContextPlugin = context_plugin
        self.variant_object_id = variant_object_id
        self.signature = signature
        self._variant_filter = None

    @classmethod
    def create_from_rest_data(cls, rest_data: Optional[Any], dependencies: Dependencies) -> Optional[
        AbstractPlugin]:
        variant_filter_context_plugin = dependencies[CsVpVariantsProductContextPlugin]

        if variant_filter_context_plugin is None:
            return None

        if rest_data is None:
            return None

        variant_id = rest_data.get("variant_id", None)
        signature = rest_data.get("signature", None)

        try:
            return cls(variant_filter_context_plugin, variant_id, signature)
        except ValueError:
            return None

    @property
    def variant_filter(self):
        if self._variant_filter is None:
            if self.signature is None:

                variant = Variant.ByKeys(cdb_object_id=self.variant_object_id)
                self._variant_filter = VariantBOMFilter(
                    self.product_context_plugin.product_object_id, variant.id
                )
            else:
                self._variant_filter = VirtualVariantBOMFilter(
                    self.product_context_plugin.product_object_id, self.signature
                )

        return self._variant_filter

    @classmethod
    def create_for_default_data(cls, dependencies: Dependencies, **kwargs: Any) -> Optional[Self]:
        variant_filter_context_plugin = dependencies[CsVpVariantsProductContextPlugin]
        if variant_filter_context_plugin is None:
            return None

        bom_table_url = kwargs.get("bom_table_url")
        url_query_args = parse_url_query_args(bom_table_url)

        variant_object_id = url_query_args.get("variant", None)
        signature = url_query_args.get("signature", None)
        if variant_object_id is None and signature is None:
            return None

        return cls(variant_filter_context_plugin, variant_object_id=variant_object_id, signature=signature)

    def get_default_data(self) -> tuple[Any, Any]:
        if self.variant_object_id is None and self.signature is None:
            return None, None

        data = {
            "signature": self.signature,
        }

        # check if given cdb_object_id result in an existing variant
        if self.variant_object_id is not None:
            var = Variant.ByKeys(cdb_object_id=self.variant_object_id)
            if var is None:
                # todo: remove query parameter from url?
                LOG.info("%s: the url query parameter 'variant' (value: '%s') refer to a non-existing object",
                             self.__class__.__name__, self.variant_object_id)
                return None, None  # note: if variant given then there can not be a signature

            data.update({
                "variant_id": self.variant_object_id,
                "system:description": var.GetDescription(),
                "name": var.name
            })

        return data, None


class CsVpVariantsFilterPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.vp.variantFilter"
    DEPENDENCIES = (CsVpVariantsFilterContextPlugin,)

    def __init__(self, filter_context_plugin: CsVpVariantsFilterContextPlugin) -> None:
        if filter_context_plugin is None:
            raise ValueError("filter_context_plugin can not be None")

        self.variant_filter_context_plugin: CsVpVariantsFilterContextPlugin = filter_context_plugin

    @classmethod
    def create_from_rest_data(cls, rest_data: Optional[Any], dependencies: Dependencies) -> Optional[Self]:
        variant_filter_context_plugin = dependencies[CsVpVariantsFilterContextPlugin]

        if variant_filter_context_plugin is None:
            return None

        return cls(variant_filter_context_plugin)

    def filter_bom_item_records(self, bom_item_records):
        return [
            each
            for each in bom_item_records
            if self.variant_filter_context_plugin.variant_filter.eval_bom_item(each)
        ]


class CsVpVariantsAttributePlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.vp.variantAttribute"
    DEPENDENCIES = (CsVpVariantsFilterContextPlugin,)

    def __init__(self, filter_context_plugin: CsVpVariantsFilterContextPlugin = None) -> None:
        self.variant_filter_context_plugin: CsVpVariantsFilterContextPlugin = filter_context_plugin

    @classmethod
    def create_from_rest_data(cls, rest_data: Optional[Any], dependencies: Dependencies) -> Optional[
        AbstractPlugin]:
        variant_filter_context_plugin = dependencies[CsVpVariantsFilterContextPlugin]

        return cls(variant_filter_context_plugin)

    def get_bom_item_select_stmt_extension(self) -> Optional[str]:
        return """,
                CASE
                    WHEN EXISTS (
                        SELECT 42
                        FROM cdbvp_bom_predicate p
                        WHERE {0}.baugruppe=p.baugruppe
                            AND {0}.b_index=p.b_index
                            AND {0}.teilenummer=p.teilenummer
                            AND {0}.variante=p.variante
                            AND {0}.position=p.position
                    ) THEN 1
                    ELSE 0
                END has_predicates
            """.format(
            self.BOM_ITEM_TABLE_ALIAS
        )

    def get_additional_bom_item_attributes(
            self, bom_item_record: Record
    ) -> Optional[dict]:
        return {
            "has_predicates": getattr(bom_item_record, "has_predicates", 0),
            "in_variant": True
            if self.variant_filter_context_plugin is None
            else self.variant_filter_context_plugin.variant_filter.eval_bom_item(
                bom_item_record
            ),
        }
