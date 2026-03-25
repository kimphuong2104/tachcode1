#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module cs.variants.reports

This is the documentation for the cs.variants.reports module.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from operator import attrgetter

from cdb import cmsg, i18n, sig, sqlapi, ue
from cs.classification.util import isclose
from cs.tools import powerreports
from cs.variants import VariabilityModel, Variant
from cs.variants.api import VariantsClassification
from cs.variants.api.filter import (
    CsVariantsFilterContextPlugin,
    CsVariantsVariabilityModelContextPlugin,
    CsVariantsVariantFilterPlugin,
)
from cs.variants.classification_helper import get_property_entry_value
from cs.vp.bom import AssemblyComponentOccurrence, bomqueries, enhancement
from cs.vp.bom.bomqueries_plugins import ComponentJoinPlugin
from cs.vp.bom.reports import HierarchicalBOM, _get_lang_attribute
from cs.vp.items import Item

NVARIANTS = 10


def get_int_as_variant_char(the_int: int) -> str:
    """
    Adds `the_int` to 97 ('A') and return it as character

    .. code-block:: pycon
         >>> get_int_as_variant_char(1)
         'B'
         >>>
    """
    return chr(ord("A") + the_int)


class HierarchicalBOMCsVariants(HierarchicalBOM):
    def __init__(self):
        super().__init__()

        self.filter = None
        self.addtl_filter = {}
        self.cdbxml_report_lang = None

    def _get_item_object(self, parent_result, source_args):
        item = None
        variant = None

        # If we have a MaxBOM, let's use it
        if "max_bom_id" in source_args:
            item = Item.ByKeys(cdb_object_id=source_args["max_bom_id"])

            if isinstance(parent_result, powerreports.ReportData):
                obj = parent_result.getObject()
                if isinstance(obj, Variant):
                    variant = obj

        # Otherwise the report should be called in context of an item
        elif isinstance(parent_result, powerreports.ReportData):
            obj = parent_result.getObject()
            if isinstance(obj, Item):
                if obj.Variant:
                    item = obj.MaxBOM
                    variant = obj.Variant
                else:
                    item = obj

        return item, variant

    def getData(self, parent_result, source_args, **kwargs):
        item, variant = self._get_item_object(parent_result, source_args)
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang", i18n.default())

        if item is None:
            raise RuntimeError("This provider needs an item as parameter")

        self.REC_LEVEL = kwargs.get("depth", "")

        self.addtl_filter = {}
        for k, v in kwargs.items():
            if k.startswith("filter_") and v:
                self.addtl_filter[k[7:]] = v

        if variant:
            # if the report runs twice the previous added variant plugin is still present
            # the easiest way to solve this issue is to recreate the bom enhancement object
            # not the smartest way but works
            self.bom_enhancement = bomqueries.FlatBomEnhancement()

            var_model_plg = CsVariantsVariabilityModelContextPlugin(
                variability_model_id=variant.variability_model_id
            )
            ctx_plg = CsVariantsFilterContextPlugin(var_model_plg, variant.id)
            var_plg = CsVariantsVariantFilterPlugin(ctx_plg)
            self.bom_enhancement.add(var_plg)
            self.bom_enhancement.add(ComponentJoinPlugin("latest_working"))

        result = self._getStructure(item)

        return self._process_result(result, lang=self.cdbxml_report_lang)


class VariantMaxBOMProvider(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_1
    CALL_CARD = powerreports.CARD_0

    def getData(self, parent_result, source_args, **kwargs):
        # Fetch the MaxBOM-Object
        item = Item.ByKeys(cdb_object_id=source_args["max_bom_id"])
        if item is None:
            raise RuntimeError("This provider needs a valid MaxBOM as parameter")

        result = powerreports.ReportData(self, item)
        result["cdbxml_hyperlink"] = powerreports.MakeReportURL(
            item, text_to_display="teilenummer"
        )
        if hasattr(item, "Project") and item.Project:
            result["project_hyperlink"] = powerreports.MakeReportURL(item.Project)

        result["macro_guard"] = "1"
        return result

    def getSchema(self):
        schema = powerreports.XSDType(self.CARD, Item)
        schema.add_attr("cdbxml_hyperlink", sqlapi.SQL_CHAR)
        schema.add_attr("project_hyperlink", sqlapi.SQL_CHAR)
        # macro_guard is needed to guard the vba script to run only once
        # see: https://code.contact.de/plm/cs.variants/-/merge_requests/399#vba-skripte
        schema.add_attr("macro_guard", sqlapi.SQL_CHAR)
        return schema


def get_report_variant_properties_hyperlink(variant):
    variant_driving_properties = variant.get_variant_driving_properties_with_values()[
        "properties"
    ]

    variant_properties_text_parts = []
    for (
        property_code,
        property_entry,
    ) in variant_driving_properties.items():
        variant_properties_text_parts.append(
            "{0}={1}".format(
                property_code,
                get_property_entry_value(
                    # cs.variants only support single value classification so hardcode index 0
                    property_entry[0]
                ),
            )
        )

    variant_properties_text = ", ".join(variant_properties_text_parts)
    return powerreports.MakeReportURL(variant, text_to_display=variant_properties_text)


class VariantPropertiesProvider(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_1
    CALL_CARD = powerreports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        variant = parent_result.getObject()

        if variant is None or not isinstance(variant, Variant):
            raise RuntimeError("This provider needs an variant object as parent_result")

        result = powerreports.ReportData(self)
        result[
            "variant_properties_hyperlink"
        ] = get_report_variant_properties_hyperlink(variant)
        return result

    def getSchema(self):
        schema = powerreports.XSDType(self.CARD)
        schema.add_attr("variant_properties_hyperlink", sqlapi.SQL_CHAR)
        return schema


class VariantsPropertiesProvider(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_N
    CALL_CARD = powerreports.CARD_N

    def getData(self, parent_result, source_args, **kwargs):
        result = powerreports.ReportDataList(self)

        for each_idx, each in enumerate(parent_result):
            variant = each.getObject()

            if variant is None or not isinstance(variant, Variant):
                raise RuntimeError(
                    "This provider needs an variant object as parent_result"
                )

            data = powerreports.ReportData(self, variant)
            data[
                "variant_properties_hyperlink"
            ] = get_report_variant_properties_hyperlink(variant)
            data["count"] = each_idx + 1
            result.append(data)

        return result

    def getSchema(self):
        schema = powerreports.XSDType(self.CARD, Variant)
        schema.add_attr("variant_properties_hyperlink", sqlapi.SQL_CHAR)
        schema.add_attr("count", sqlapi.SQL_INTEGER)
        return schema


class VariantBOMComparison(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_N
    CALL_CARD = powerreports.CARD_N

    def __init__(self):
        super().__init__()

        self.filters = []
        self.cdbxml_report_lang = None

    def _makeURL(self, tnumber, tidx):
        urlmsg = cmsg.Cdbcmsg("part", "CDB_ShowObject", 0)
        urlmsg.add_item("teilenummer", "teile_stamm", tnumber)
        urlmsg.add_item("t_index", "teile_stamm", tidx)
        return "%s cdb:texttodisplay:%s" % (urlmsg.cdbwin_url(), tnumber)

    def _getStructure(self, component, flat_bom_dict, level=1):
        result = powerreports.ReportDataList(self)

        in_variants = [fltr.eval_bom_item(component) for fltr in self.filters]

        item = Item.ByKeys(cdb_object_id=component.item_object_id)

        item_result = powerreports.ReportData(self, item)
        item_result["item_hyperlink"] = self._makeURL(
            component.teilenummer, component.t_index
        )
        item_result["position"] = component.position

        maxbom_occ = AssemblyComponentOccurrence.KeywordQuery(
            bompos_object_id=component.cdb_object_id
        )

        def count_filtered_occurrences(variant_filter, list_of_occ, component):
            if list_of_occ:
                return len(
                    [occ for occ in list_of_occ if variant_filter.eval_bom_item(occ)]
                )

            return int(component.menge)

        _filtered_menge = [
            count_filtered_occurrences(fltr, maxbom_occ, component)
            for fltr in self.filters
        ]

        # menge are the unfiltered count of occurrences in MaxBOM (not variant!)
        # It seems safe to use the amount of attribute from the component here
        # we except the 'menge' is the same as the count of occurrences
        item_result["menge"] = int(component.menge)

        _has_no_diff = len(set(_filtered_menge)) == 1 and len(set(in_variants)) == 1
        item_result["difference"] = "keine" if _has_no_diff else "Vorkommen"
        item_result["difference_en"] = "none" if _has_no_diff else "found"

        for n_var, in_var, var_menge in zip(
            range(NVARIANTS),
            in_variants,
            _filtered_menge,
        ):
            item_result[f"variante{get_int_as_variant_char(n_var)}"] = (
                int(var_menge) if in_var else 0
            )

        item_result["cdbxml_level"] = level

        category_attr = _get_lang_attribute(
            Item.t_kategorie_name, self.cdbxml_report_lang
        )
        item_result["category"] = getattr(item, category_attr)

        designation_attr = _get_lang_attribute(
            Item.i18n_benennung, self.cdbxml_report_lang
        )
        item_result["designation"] = getattr(item, designation_attr)

        result.append(item_result)
        for comp in flat_bom_dict[(component.teilenummer, component.t_index)]:
            result += self._getStructure(comp, flat_bom_dict, level=level + 1)
        return result

    def getData(self, parent_result, source_args, **kwargs):
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang", i18n.default())

        # Fetch the MaxBOM-Object
        item = Item.ByKeys(cdb_object_id=source_args["max_bom_id"])
        if item is None:
            raise RuntimeError("This provider needs a valid MaxBOM as parameter")

        bom_enhancement = enhancement.FlatBomEnhancement()
        bom_enhancement.add(ComponentJoinPlugin("latest_working"))
        flat_bom_dict = bomqueries.flat_bom_dict(
            item,
            bom_enhancement=bom_enhancement,
            sort_func=attrgetter(*["baugruppe", "b_index", "teilenummer", "t_index"]),
        )

        variants = [pr.getObject() for pr in parent_result]
        if len(variants) < 2 or len(variants) > NVARIANTS:
            raise RuntimeError(
                "This provider requires between 2 and %s variants" % NVARIANTS
            )

        if len({v.Product for v in variants}) != 1:
            raise RuntimeError("Please select only variants from the same product")

        # this throws an exception if no unique mapping
        self.filters = [variant.make_variant_filter() for variant in variants]

        result = powerreports.ReportDataList(self)
        for comp in flat_bom_dict[(item.teilenummer, item.t_index)]:
            result += self._getStructure(comp, flat_bom_dict)
        return result

    def getSchema(self):
        t = powerreports.XSDType(powerreports.N)
        t.add_attr("position", sqlapi.SQL_CHAR)
        t.add_attr("menge", sqlapi.SQL_INTEGER)
        t.add_attr("teilenummer", sqlapi.SQL_CHAR)
        t.add_attr("designation", sqlapi.SQL_CHAR)
        t.add_attr("category", sqlapi.SQL_CHAR)
        t.add_attr("t_index", sqlapi.SQL_CHAR)
        t.add_attr("difference", sqlapi.SQL_CHAR)
        t.add_attr("difference_en", sqlapi.SQL_CHAR)

        for i in range(NVARIANTS):
            t.add_attr(f"variante{get_int_as_variant_char(i)}", sqlapi.SQL_INTEGER)

        t.add_attr("cdbxml_level", sqlapi.SQL_INTEGER)
        t.add_attr("item_hyperlink", sqlapi.SQL_CHAR)
        return t


class VariantComparisonProvider(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_N
    CALL_CARD = powerreports.CARD_N

    def getSchema(self):
        schema = powerreports.XSDType(self.CARD)
        schema.add_attr("name", sqlapi.SQL_CHAR)
        schema.add_attr("cdbxml_level", sqlapi.SQL_INTEGER)
        for i in range(NVARIANTS):
            schema.add_attr("variant%s" % chr(ord("A") + i), sqlapi.SQL_INTEGER)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        # pylint: disable=too-many-locals

        variants = [pr.getObject() for pr in parent_result]
        if len(variants) < 2 or len(variants) > NVARIANTS:
            raise RuntimeError(
                "This provider requires between 2 and " "%s variants" % NVARIANTS
            )

        if len({v.VariabilityModel for v in variants}) != 1:
            raise RuntimeError(
                "Please select only variants from the same variability model"
            )
        variability_model = variants[0].VariabilityModel

        result = powerreports.ReportDataList(self)
        variants_classification = VariantsClassification([variability_model.class_code])
        variants_classification_catalog_values = (
            variants_classification.get_catalog_values()
        )

        variants_classification_variant_properties = {}
        for each in variants_classification.get_variants_classification(
            variability_model, evaluate_status=False
        ):
            current_variant_classification = each["classification"]
            variants_classification_variant_properties[
                each["variant"]
            ] = current_variant_classification

            for each_code in variants_classification.get_variant_driving_properties():
                # Properties with no values do not have an entry in catalog values lookup
                variants_classification_catalog_values_current = {
                    get_property_entry_value(each_entry, entry_type_key="type")
                    for each_entry in variants_classification_catalog_values.get(
                        each_code, []
                    )
                }

                # cs.variants only support single value classification so hardcode index 0
                variant_entry_for_current_property = current_variant_classification[
                    each_code
                ][0]

                variant_value_for_current_property = get_property_entry_value(
                    variant_entry_for_current_property
                )

                if variant_value_for_current_property is not None and (
                    variants_classification_catalog_values_current is None
                    or variant_value_for_current_property
                    not in variants_classification_catalog_values_current
                ):
                    if each_code not in variants_classification_catalog_values:
                        variants_classification_catalog_values[each_code] = []

                    variants_classification_catalog_values[each_code].append(
                        dict(
                            variant_entry_for_current_property,
                            type=variant_entry_for_current_property["property_type"],
                        )
                    )

        for (
            each_code,
            each_entry,
        ) in variants_classification.get_variant_driving_properties().items():
            data_property = powerreports.ReportData(self)
            data_property["name"] = "{0}".format(each_code)
            data_property["cdbxml_level"] = 0
            result.append(data_property)

            if each_entry["type"] == "boolean":
                variants_classification_catalog_values_current = [
                    {"type": each_entry["type"], "value": True},
                    {"type": each_entry["type"], "value": False},
                ]
            else:
                # Properties with no values do not have an entry in catalog values lookup
                variants_classification_catalog_values_current = (
                    variants_classification_catalog_values.get(each_code, [])
                )

            for (
                each_catalog_value_entry
            ) in variants_classification_catalog_values_current:
                catalog_value_value = get_property_entry_value(
                    each_catalog_value_entry, entry_type_key="type"
                )
                data_property_catalog_value = powerreports.ReportData(self)
                data_property_catalog_value["name"] = "{0}".format(catalog_value_value)

                for letter, variant in zip(
                    [get_int_as_variant_char(i) for i in range(NVARIANTS)], variants
                ):
                    # cs.variants only support single value classification so hardcode index 0
                    variant_value_for_current_property = get_property_entry_value(
                        variants_classification_variant_properties[variant][each_code][
                            0
                        ]
                    )

                    if each_entry["type"] == "float":
                        is_variant_using_catalog_value = isclose(
                            variant_value_for_current_property, catalog_value_value
                        )
                    else:
                        # cs.variants only support single value classification so hardcode index 0
                        is_variant_using_catalog_value = (
                            variant_value_for_current_property == catalog_value_value
                        )

                    data_property_catalog_value["variant%s" % letter] = (
                        1 if is_variant_using_catalog_value else 0
                    )
                    data_property_catalog_value["cdbxml_level"] = 1
                result.append(data_property_catalog_value)

        return result


@sig.connect(Variant, list, "cdbxml_excel_report", "pre_mask")
def variant_comparison_skip_select_max_bom(_, ctx):
    variability_model_id = ctx.objects[0].variability_model_id
    for each in ctx.objects:
        if each.variability_model_id != variability_model_id:
            raise ue.Exception("cs_variants_only_unique_variability_model")

    ctx.set("variability_model_id", variability_model_id)

    variability_model = VariabilityModel.ByKeys(cdb_object_id=variability_model_id)
    variability_model.preselect_ctx_max_bom_id_if_possible(ctx)
