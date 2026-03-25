#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module cs.vp.variants.reports

This is the documentation for the cs.vp.variants.reports module.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sig
from cdb import ue
from cdb import cmsg
from cdb import sqlapi
from cdb import i18n
from cdb.objects import ByID
from cs.tools import powerreports as PowerReports
from cs.vp.variants.filter import VariantBOMFilter
from cs.vp.variants.filter import VirtualVariantBOMFilter
from cs.vp.variants import Variant
from cs.vp.products import Product

from cs.vp.items import Item

from cs.vp.bom.reports import HierarchicalBOM
from cs.vp.bom.reports import _get_lang_attribute

NVARIANTS = 10


def to_char(the_int) -> str:
    """
    Adds `the_int` to 97 ('A') and return it as character

    :parm int the_int
    """
    return chr(ord("A") + the_int)


# ==============================================================================
# Report Variantenstückliste
# ==============================================================================

class VirtualVariantBOM(HierarchicalBOM):
    """ Custom Provider for a hierarchical BOM report.
    """
    CALL_CARD = PowerReports.CARD_0

    def getData(self, parent_result, source_args, **kwargs):
        self.addtl_filter = {}
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang",
                                                  i18n.default())
        if ("max_bom_teilenummer" in source_args and
                "max_bom_t_index" in source_args):
            item = Item.ByKeys(teilenummer=source_args["max_bom_teilenummer"],
                               t_index=source_args["max_bom_t_index"])

            if not item:
                raise RuntimeError("This provider needs an item as parameter")

            product_object_id = source_args["filter_id"].split(";")[0]
            variant_sig = source_args["filter_id"].split(";")[1]

            self.filter = VirtualVariantBOMFilter(product_object_id, variant_sig)
            result = self._getStructure(item)
        else:
            result = super(VirtualVariantBOM, self).getData(parent_result,
                                                            source_args,
                                                            **kwargs)

        return self._process_result(result, self.cdbxml_report_lang)


class MaxBOM(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_0

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD, Item)
        schema.add_attr("maxbom_hyperlink", sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        maxbom = None
        if set(["max_bom_teilenummer", "max_bom_t_index"]) <= set(source_args.keys()):
            maxbom = Item.ByKeys(teilenummer=source_args["max_bom_teilenummer"],
                               t_index=source_args["max_bom_t_index"])

        if not maxbom:
            raise RuntimeError("Cannot find MaxBOM")

        data = PowerReports.ReportData(self, maxbom)
        data["maxbom_hyperlink"] = PowerReports.MakeReportURL(maxbom,
                                                              "CDB_ShowObject",
                                                              maxbom.teilenummer)

        return data


# ==============================================================================
# Report Variantenvergleich
# ==============================================================================

class VariantBOMComparison(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_N

    def _makeURL(self, tnumber, tidx):
        urlmsg = cmsg.Cdbcmsg("part", "CDB_ShowObject", 0)
        urlmsg.add_item("teilenummer", "teile_stamm", tnumber)
        urlmsg.add_item("t_index", "teile_stamm", tidx)
        return "%s cdb:texttodisplay:%s" % (urlmsg.cdbwin_url(), tnumber)

    def _getStructure(self, component, level=1):
        result = PowerReports.ReportDataList(self)

        args = {"baugruppe": component.baugruppe,
                "b_index": component.b_index,
                "teilenummer": component.teilenummer,
                "t_index": component.t_index,
                "position": component.position,
                "variante": component.variante
                }
        in_variants = [fltr.eval(**args) for fltr in self.filters]

        item_result = PowerReports.ReportData(self, component.Item)
        item_result["item_hyperlink"] = self._makeURL(component.teilenummer, component.t_index)
        item_result["position"] = component.position
        item_result["menge"] = int(component.menge)
        item_result["difference"] = "keine" if len(set(in_variants)) == 1 else "Vorkommen"
        item_result["difference_en"] = "none" if len(set(in_variants)) == 1 else "found"
        item_result["cdbxml_level"] = level

        category_attr = _get_lang_attribute(Item.t_kategorie_name,
                                            self.cdbxml_report_lang)
        item_result["category"] = getattr(component.Item, category_attr)

        designation_attr = _get_lang_attribute(Item.i18n_benennung,
                                               self.cdbxml_report_lang)
        item_result["designation"] = getattr(component.Item, designation_attr)

        for letter, in_var in zip([to_char(i) for i in range(NVARIANTS)], in_variants):
            item_result["variante%s" % letter] = int(in_var) * int(component.menge)
        result.append(item_result)
        for comp in component.Item.Components:
            result += self._getStructure(comp, level + 1)
        return result

    def getData(self, parent_result, source_args, **kwargs):
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang",
                                                  i18n.default())

        # Fetch the MaxBOM-Object
        item = Item.ByKeys(teilenummer=source_args["max_bom_teilenummer"],
                           t_index=source_args["max_bom_t_index"])
        if item is None:
            raise RuntimeError("This provider needs a valid maxbom as paramter")

        variants = [pr.getObject() for pr in parent_result]
        if len(variants) < 2 or len(variants) > NVARIANTS:
            raise RuntimeError("This provider requires between 2 and "
                               "%s variants" % NVARIANTS)

        if len(set([v.Product for v in variants])) != 1:
            raise RuntimeError("Please select only variants from the same product")

        # this throws an exception if no unique mapping
        mbvariants = [variant.get_filter_variant() for variant in variants]
        self.filters = [VariantBOMFilter(mbvar.product_object_id, mbvar.id) for mbvar in mbvariants]

        result = PowerReports.ReportDataList(self)
        for comp in item.Components:
            result += self._getStructure(comp)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(PowerReports.N)
        t.add_attr("position", sqlapi.SQL_CHAR)
        t.add_attr("menge", sqlapi.SQL_INTEGER)
        t.add_attr("teilenummer", sqlapi.SQL_CHAR)
        t.add_attr("designation", sqlapi.SQL_CHAR)
        t.add_attr("category", sqlapi.SQL_CHAR)
        t.add_attr("t_index", sqlapi.SQL_CHAR)
        t.add_attr("difference", sqlapi.SQL_CHAR)
        t.add_attr("difference_en", sqlapi.SQL_CHAR)

        for i in range(NVARIANTS):
            t.add_attr("variante%s" % to_char(i), sqlapi.SQL_INTEGER)

        t.add_attr("cdbxml_level", sqlapi.SQL_INTEGER)
        t.add_attr("item_hyperlink", sqlapi.SQL_CHAR)
        return t


class VirtualVariantBOMComparison(VariantBOMComparison):
    CALL_CARD = PowerReports.CARD_0

    def getData(self, parent_result, source_args, **kwargs):
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang",
                                                  i18n.default())

        # Fetch the MaxBOM-Object
        item = Item.ByKeys(teilenummer=source_args["max_bom_teilenummer"],
                           t_index=source_args["max_bom_t_index"])
        if not item:
            raise RuntimeError("This provider needs an item as parameter")

        product_object_id = source_args["filter_id"].split(";")[0]
        variant_signatures = source_args["filter_id"].split(";")[1:]

        self.filters = [VirtualVariantBOMFilter(product_object_id, variant_sig) for variant_sig in variant_signatures]

        result = PowerReports.ReportDataList(self)
        for comp in item.Components:
            result += self._getStructure(comp)
        return result


class VariantProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD, Variant)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        product_object_id, variant_number = source_args["filter_id"].split(":")
        variant = Variant.ByKeys(variant_number, product_object_id)
        data = PowerReports.ReportData(self, variant)
        return data


class VirtualVariantProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_0

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        schema.add_attr("variant_text", sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportData(self)

        product_object_id, variant_signature = source_args["filter_id"].split(";")
        result["variant_text"] = Variant.getVariantTextFromSignature(product_object_id, variant_signature)
        return result


class VariantMaxBOMProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_0

    def getData(self, parent_result, source_args, **kwargs):
        # Fetch the MaxBOM-Object
        item = Item.ByKeys(teilenummer=source_args["max_bom_teilenummer"],
                           t_index=source_args["max_bom_t_index"])
        if item is None:
            raise RuntimeError("This provider needs a valid maxbom as paramter")

        result = PowerReports.ReportData(self, item)
        result["cdbxml_hyperlink"] = PowerReports.MakeReportURL(
                item, text_to_display="teilenummer")
        if hasattr(item, "Project") and item.Project:
            result["project_hyperlink"] = PowerReports.MakeReportURL(item.Project)
        return result

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD, Item)
        schema.add_attr("cdbxml_hyperlink", sqlapi.SQL_CHAR)
        schema.add_attr("project_hyperlink", sqlapi.SQL_CHAR)
        return schema


class VariantComparisonProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_N

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        schema.add_attr("name", sqlapi.SQL_CHAR)
        schema.add_attr("cdbxml_level", sqlapi.SQL_INTEGER)
        for i in range(NVARIANTS):
            schema.add_attr("variant%s" % to_char(i), sqlapi.SQL_INTEGER)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        variants = [pr.getObject() for pr in parent_result]
        if len(variants) < 2 or len(variants) > NVARIANTS:
            raise RuntimeError("This provider requires between 2 and "
                               "%s variants" % NVARIANTS)

        if len(set([v.Product for v in variants])) != 1 or\
                len(set([v.View for v in variants])) != 1:
            raise RuntimeError("Please select only variants "
                               "from the same product "
                               "and from the same view")

        view = variants[0].View
        product = variants[0].Product
        properties = view.Properties if view else product.VariantDrivingProperties
        result = PowerReports.ReportDataList(self)

        for prop in properties:
            data = PowerReports.ReportData(self)
            data["name"] = prop.Name['']
            data["cdbxml_level"] = 0
            result.append(data)

            for value in prop.EnumValues:
                data = PowerReports.ReportData(self)
                data["name"] = value.ValueText['']
                for letter, variant in zip([to_char(i) for i in range(NVARIANTS)], variants):
                    data["variant%s" % letter] = 1 if variant.PropertyValues.KeywordQuery(value=value.value) else 0
                    data["cdbxml_level"] = 1
                result.append(data)
        return result


class VirtualVariantComparisonProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_0

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        schema.add_attr("name", sqlapi.SQL_CHAR)
        schema.add_attr("cdbxml_level", sqlapi.SQL_INTEGER)
        for i in range(NVARIANTS):
            schema.add_attr("variant%s" % (to_char(i)), sqlapi.SQL_INTEGER)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        product_object_id = source_args["filter_id"].split(";")[0]
        variant_signatures = source_args["filter_id"].split(";")[1:]

        product = Product.ByKeys(product_object_id)
        properties = product.MaxBOMView.Properties if product.MaxBOMView else product.VariantDrivingProperties

        result = PowerReports.ReportDataList(self)
        for prop in properties:
            data = PowerReports.ReportData(self)
            data["name"] = prop.Name['']
            data["cdbxml_level"] = 0
            result.append(data)

            for value in prop.EnumValues:
                data = PowerReports.ReportData(self)
                data["name"] = value.ValueText['']
                for letter, vsig in zip([to_char(i) for i in range(NVARIANTS)], variant_signatures):
                    data["variant%s" % letter] = 1 if "%s:%s" % (prop.id, value.value) in vsig else 0
                    data["cdbxml_level"] = 1
                result.append(data)
        return result


class VirtualVariantsProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_0

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        schema.add_attr("id", sqlapi.SQL_INTEGER)
        schema.add_attr("name", sqlapi.SQL_CHAR)
        schema.add_attr("variant_text", sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang",
                                                  i18n.default())

        info_field = _get_lang_attribute(
            Variant.cdbvp_variant_info_txt,
            self.cdbxml_report_lang
        )

        product_object_id = source_args["filter_id"].split(";")[0]
        variant_signatures = source_args["filter_id"].split(";")[1:]

        result = PowerReports.ReportDataList(self)
        for signature in variant_signatures:
            variant = Variant.ByKeys(product_object_id=product_object_id, signature=signature)
            data = PowerReports.ReportData(self)
            if variant is not None:
                data["id"] = variant.id
                data["name"] = variant.name
                data["variant_text"] = getattr(variant, info_field)
            else:
                data["variant_text"] = Variant.getVariantTextFromSignature(
                    product_object_id, signature, lang=self.cdbxml_report_lang)
            result.append(data)
        return result


# ==============================================================================
# Hilfmethode
# ==============================================================================

@sig.connect(Product, "cdbvp_variant_bom_report", "pre_mask")
def keep_attributes(product, ctx):
    if "filter_id" in ctx.dialog.get_attribute_names():
        ctx.keep("filter_id", ctx.dialog.filter_id)


@sig.connect(Product, "cdbvp_bom_comparison", "pre_mask")
@sig.connect(Product, "cdbvp_variant_bom_report", "pre_mask")
def skip_select_max_bom_dlg_prod(product, ctx):
    if "maxbom_oid" in ctx.sys_args.get_attribute_names():
        ctx.skip_dialog()
    else:
        l = len(product.ToplevelAssemblyLinks)
        if l == 0:
            raise ue.Exception("cdbvp_err_no_max_bom",
                               product.code)
        elif l == 1:
            ctx.skip_dialog()


@sig.connect(Variant, "cdbvp_variant_bom_report", "pre_mask")
def skip_select_max_bom_dlg(variant, ctx):
    skip_select_max_bom_dlg_prod(variant.Product, ctx)


def _get_maxbom(ctx, product=None, variant=None, args={}):
    if not product:
        if variant:
            product = variant.Product
        else:
            raise RuntimeError("please provide either a product or a variant")

    if set(["max_bom_teilenummer", "max_bom_t_index"]) <= \
            set(ctx.dialog.get_attribute_names()):
        args.update({"max_bom_teilenummer": ctx.dialog.max_bom_teilenummer,
                     "max_bom_t_index": ctx.dialog.max_bom_t_index})
    elif "maxbom_oid" in ctx.sys_args.get_attribute_names():
        maxbom = ByID(ctx.sys_args.maxbom_oid)
        if maxbom:
            args.update({"max_bom_teilenummer": maxbom.teilenummer,
                         "max_bom_t_index": maxbom.t_index})
    elif len(product.ToplevelAssemblyLinks) == 1:
        maxbom = product.ToplevelAssemblyLinks[0]
        args.update({"max_bom_teilenummer": maxbom.teilenummer,
                     "max_bom_t_index": maxbom.t_index})
    else:
        raise ue.Exception("cdbvp_err_no_max_bom", product.code)
    return args


@sig.connect(Variant, "cdbvp_variant_bom_report", "now")
def show_cdbvp_variant_bom_report(variant, ctx):
    args = _get_maxbom(ctx, variant=variant)
    Variant.generate_report({"name": "VPMHierarchicalBOM",
                             "report_title": "VarStrukturStueckliste",
                             "iso_code": i18n.default()},
                            ctx, [variant], view=True, dlg_args=args)


@sig.connect(Product, "cdbvp_variant_bom_report", "now")
def show_cdbvp_product_bom_report(product, ctx):
    args = _get_maxbom(ctx,
                       product=product,
                       args={"filter_id": ctx.sys_args["filter_id"]})

    Product.generate_report({"name": "VPMVirtualHierarchicalBOM",
                             "report_title": "VirtVarStrukturStueckliste",
                             "iso_code": i18n.default()},
                            ctx, [], view=True, dlg_args=args)


@sig.connect(Variant, list, "cdbvp_bom_comparison", "pre_mask")
def variant_comparison_skip_select_max_bom(cls, ctx):
    product_object_id = ctx.objects[0].product_object_id
    ctx.set("product_object_id", product_object_id)
    product = Product.ByKeys(product_object_id)
    skip_select_max_bom_dlg_prod(product, ctx)


def _show_bom_comparison(product, variants, ctx):
    if any((variant.View != variants[0].View for variant in variants)):
        # FIXME: proper message
        raise ue.Exception("cdbvp_variants_from_same_view")

    args = _get_maxbom(ctx, variant=variants[0])
    Variant.generate_report({"name": "VPMBomComparison",
                             "report_title": "VarStücklistenvergleich",
                             "iso_code": i18n.default()},
                             ctx, variants, view=True, dlg_args=args)


@sig.connect(Variant, list, "cdbvp_bom_comparison", "now")
def show_cdbvp_bom_comparison(cls, ctx):
    if (len(ctx.objects) < 2 or len(ctx.objects) > 10 or
            any((obj.product_object_id != ctx.objects[0].product_object_id for obj in ctx.objects))):
        # FIXME: proper message
        raise ue.Exception("cdbvp_2_to_10_variants")

    variants = [Variant.ByKeys(product_object_id=obj.product_object_id, id=obj.id) for obj in ctx.objects]
    product = variants[0].Product
    _show_bom_comparison(product, variants, ctx)


@sig.connect(Product, "cdbvp_bom_comparison", "now")
def show_virtual_cdbvp_bom_comparison(product, ctx):
    args = _get_maxbom(ctx,
                       product=product,
                       args={"filter_id": ctx.sys_args["filter_id"]})

    Product.generate_report({"name": "VirtualVPMBomComparison",
                             "report_title": "VirtualVPMBomComparison",
                             "iso_code": i18n.default()},
                            ctx, [], view=True, dlg_args=args)
