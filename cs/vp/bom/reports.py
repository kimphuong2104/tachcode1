#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     Reports.py
# Author:   san
# Creation: 20.10.09
# Purpose:  Custom Reports for the Standard version of CIM Database

# ----------------------- Custom Providers for Reports ------------------------

import collections
from typing import Optional

from cdb import cmsg
from cdb import i18n
from cdb import sqlapi
from cdb import ue
from cdb import util
from cdb.objects import ByID
from cdb.platform import olc
from cdb.platform.mom import fields
from cs.materials import Material
from cs.tools import powerreports

from cs.vp.bom import bomqueries
from cs.vp.bom import is_installed
from cs.vp.bom import enhancement
from cs.vp.items import Item
from cs.vp.items import ItemCategory
from cs.vp.items import PartUnit
from cs.vp.variants.filter import CsVpVariantsFilterPlugin, CsVpVariantsFilterContextPlugin, \
    CsVpVariantsProductContextPlugin
from cs.vp.bom import bomqueries_plugins
from cs.vp.bom.enhancement.plugin import AbstractPlugin
from cs.vp.bom.enhancement import FlatBomEnhancement


def _get_lang_attribute(attr, lang=i18n.default()):
    return attr.lang_adefs[lang].getName()


# ==============================================================================
# Report Strukturstückliste
# ==============================================================================

def bomfilter_function(bomfilter):
    def _bomfilter_function(components):
        result = []
        for comp in components:
            site_object_id = comp.site_object_id
            if (
                not bomfilter.get("site_object_id") or
                not site_object_id or
                bomfilter.get("site_object_id") == site_object_id
            ):
                result.append(comp)
        return result

    return _bomfilter_function


_PLANT_LABEL = None


def get_plant_label():
    global _PLANT_LABEL
    if _PLANT_LABEL is None:
        dd_field = fields.DDField.ByKeys("part", "site_object_id")
        if dd_field:
            _PLANT_LABEL = dd_field.Label['']
    return _PLANT_LABEL


def get_bomfilter_text(bomfilter):
    if bomfilter.get('site_object_id'):
        site = ByID(bomfilter.get("site_object_id"))
        if site:
            return "%s: %s" % (get_plant_label(), site.GetDescription())
    return ""


class StatusNames(powerreports.CustomDataProvider):
    """ Custom provider for status Names. This is needed because apparently
        the Context provider can't visualize joined attributes
    """
    CARD = 1
    CALL_CARD = powerreports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        item = parent_result.getObject()
        result = powerreports.ReportData(self)

        for attr in Item.joined_status_name.adef.getSQLSelectNames():
            result[attr] = getattr(item, attr)
        return result

    def getSchema(self):
        t = powerreports.XSDType(self.CARD)
        for attr in Item.joined_status_name.adef.getSQLSelectNames():
            t.add_attr(attr, sqlapi.SQL_CHAR)
        return t


# Provider for Strukturstückliste
# Note: MS Excel 2007 can not properly handle more than approx 32000 data
# items and crashes in tests run on the RECARO test data. As a result, the
# grouping of elements by hierarchy or the display of hyperlinks fails. The
# grouping still works with up to 45000 elements if all the style elements
# (indenting, hyperlinks) are removed.
class HierarchicalBOM(powerreports.CustomDataProvider):
    """ Data provider for product structure with hierarchy information """
    CARD = powerreports.N
    CALL_CARD = powerreports.CARD_1
    REC_LEVEL = ''
    # Keep a dictionary of XML fields which will be returned in the XSDSchema
    # and their type, for each item of the results list
    XSDSchemaItems = {
        # calculated items
        "cdbxml_level": (sqlapi.SQL_INTEGER, "computed"),
        "nr_hyperlink": (sqlapi.SQL_CHAR, "computed"),
        "pos_hyperlink": (sqlapi.SQL_CHAR, "computed"),
        "status_txt": (sqlapi.SQL_CHAR, "computed"),
        "category": (sqlapi.SQL_CHAR, "computed"),
        "designation": (sqlapi.SQL_CHAR, "computed"),
        "material_hyperlink": (sqlapi.SQL_CHAR, "computed"),
        "mengeneinheit_name": (sqlapi.SQL_CHAR, "computed"),

        # items from tables (attributes)
        "teilenummer": (sqlapi.SQL_CHAR, "einzelteile"),
        "t_index": (sqlapi.SQL_CHAR, "einzelteile"),
        "position": (sqlapi.SQL_INTEGER, "einzelteile"),
        "menge": (sqlapi.SQL_FLOAT, "einzelteile"),

        "t_kategorie": (sqlapi.SQL_CHAR, "teile_stamm"),
        "cdb_objektart": (sqlapi.SQL_CHAR, "teile_stamm"),
        "status": (sqlapi.SQL_INTEGER, "teile_stamm"),
        "benennung": (sqlapi.SQL_CHAR, "teile_stamm"),
        "eng_benennung": (sqlapi.SQL_CHAR, "teile_stamm"),
        "techdaten": (sqlapi.SQL_CHAR, "teile_stamm"),
        "mengeneinheit": (sqlapi.SQL_CHAR, "teile_stamm"),
        "material_object_id": (sqlapi.SQL_CHAR, "teile_stamm"),
        "site": (sqlapi.SQL_CHAR, "teile_stamm"),
        }

    def __init__(self):
        super(HierarchicalBOM, self).__init__()

        self.bom_enhancement = enhancement.FlatBomEnhancement()

    def _get_item_object(self, parent_result, source_args):
        item = None
        variant = None

        # If we have a MaxBOM, let's use it
        from cs.vp.variants import Variant
        if is_installed("cs.vp.variants") and \
                "max_bom_teilenummer" in source_args and\
                "max_bom_t_index" in source_args:
            item = Item.ByKeys(teilenummer=source_args["max_bom_teilenummer"],
                               t_index=source_args["max_bom_t_index"])

            if isinstance(parent_result, powerreports.ReportData):
                obj = parent_result.getObject()
                if isinstance(obj, Variant):
                    variant = obj

        # Otherwise the report should be called in context of an item
        elif isinstance(parent_result, powerreports.ReportData):
            obj = parent_result.getObject()
            if isinstance(obj, Item):
                if obj.Variant and isinstance(obj.Variant, Variant):
                    # cs.vp.variants only, not cs.variants
                    item = obj.MaxBOM
                    variant = obj.Variant
                else:
                    item = obj

        return item, variant

    def getData(self, parent_result, source_args, **kwargs):
        item, variant = self._get_item_object(parent_result, source_args)
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang",
                                                  i18n.default())

        if item is None:
            raise RuntimeError("This provider needs an item as parameter")

        self.REC_LEVEL = kwargs.get("depth", '')

        self.addtl_filter = {}
        for k, v in kwargs.items():
            if k.startswith("filter_") and v:
                self.addtl_filter[k[7:]] = v

        if variant:
            filter_variant = variant.get_filter_variant()
            self.bom_enhancement.add(
                CsVpVariantsFilterPlugin(CsVpVariantsFilterContextPlugin(
                    CsVpVariantsProductContextPlugin(filter_variant.product_object_id),
                    variant_object_id=filter_variant.cdb_object_id)
                                         )
            )

        result = self._getStructure(item)

        return self._process_result(result, lang=self.cdbxml_report_lang)

    @staticmethod
    def _process_result(data, lang):
        tmp_store = set()  # this is to collect some objects to prevent garbage collection and reconstruction from db
        for rd in data:
            # set category
            category = ItemCategory.ByKeys(rd["t_kategorie"])
            if category:
                tmp_store.add(category)
                cat_attr = _get_lang_attribute(ItemCategory.name, lang)
                rd["category"] = getattr(category, cat_attr)

            # set status_txt
            definition = olc.StateDefinition.ByKeys(objektart=rd["cdb_objektart"],
                                                    statusnummer=rd["status"])
            if definition:
                tmp_store.add(definition)
                status_attr = _get_lang_attribute(olc.StateDefinition.statusbez, lang)
                rd["status_txt"] = getattr(definition, status_attr)

            # set mengeneinheit_name
            if rd["mengeneinheit"]:
                unit = PartUnit.ByKeys(rd["mengeneinheit"])
                if unit:
                    tmp_store.add(unit)
                    unit_attr = _get_lang_attribute(PartUnit.name_i18n, lang)
                    rd["mengeneinheit_name"] = getattr(unit, unit_attr)

            # set material link
            if rd["material_object_id"]:
                material = Material.ByKeys(cdb_object_id=rd["material_object_id"])
                if material:
                    rd["material_hyperlink"] = powerreports.MakeReportURL(
                        material,
                        action="CDB_ShowObject",
                        text_to_display=material.GetDescription())

            # set site
            site = ByID(rd["site"])
            if site:
                rd["site"] = site.GetDescription()

        return data

    def getSchema(self):
        t = powerreports.XSDType(self.CARD)
        for attr, (sqlType, _tableName) in self.XSDSchemaItems.items():
            t.add_attr(attr, sqlType)
        return t

    def getArgumentDefinitions(self):
        return {"depth": sqlapi.SQL_INTEGER}

    def _getStructure(self, item):
        part_attributes = [
            attr
            for attr, (_, table) in self.XSDSchemaItems.items()
            if table == "teile_stamm"
        ]
        designation_attr = _get_lang_attribute(
            Item.i18n_benennung, self.cdbxml_report_lang)
        if designation_attr not in part_attributes:
            part_attributes.append(designation_attr)
        part_attributes.append("site_object_id")

        result = powerreports.ReportDataList(self)
        for lev, record in self._getComponents(item, part_attributes=part_attributes):
            d = powerreports.ReportData(self, record)
            d["cdbxml_level"] = lev
            d["nr_hyperlink"] = self \
                .__makeURLWithoutObj("part", "teile_stamm",
                                     "CDB_ShowObject", 0, record.teilenummer,
                                     {"teilenummer": record.teilenummer,
                                      "t_index": record.t_index})
            d["pos_hyperlink"] = self \
                .__makeURLWithoutObj("bom_item", "einzelteile",
                                     "CDB_ShowObject", 0, record.position,
                                     {"cdb_object_id": record.cdb_object_id})

            d["designation"] = getattr(record, designation_attr)
            d["site"] = record.site_object_id

            result.append(d)
        return result

    def _should_recurse_into(self, comp, depth, curr_lev):
        return ((depth != 1)
                and (self.REC_LEVEL == ''
                     or (self.REC_LEVEL != ''
                         and int(self.REC_LEVEL) - 1 > curr_lev)))

    def _getComponents(self, item, depth=0, curr_lev=0, part_attributes=None):
        """ Ermittlung Produktstruktur Hierarchieinformationen """
        if self.addtl_filter:
            self.bom_enhancement.add(
                bomqueries_plugins.FilterFunctionPlugin(
                    bomfilter_function(self.addtl_filter)
                )
            )

        flat_bom = bomqueries.flat_bom_dict(
            item,
            bom_enhancement=self.bom_enhancement,
            part_attributes=part_attributes
        )

        result = []

        def walk(teilenummer, t_index, curr_lev):
            for comp in flat_bom[(teilenummer, t_index)]:
                result.append((curr_lev, comp))
                if self._should_recurse_into(comp, depth, curr_lev):
                    walk(comp.teilenummer, comp.t_index, curr_lev + 1)

        walk(item.teilenummer, item.t_index, 0)

        return result

    def __makeURLWithoutObj(self, class_name, relation, operation, interactive,
                            text_to_display, search_cond):
        """ Create a cdb URL without instantiating the object it refers to """
        url = cmsg.Cdbcmsg(class_name, operation, interactive)
        for key in search_cond.keys():
            url.add_item(key, relation, search_cond[key])
        string = url.cdbwin_url()
        return "%s cdb:texttodisplay:%s" % (string, text_to_display)


# ==============================================================================
# Report Stücklistenvergleich
# ==============================================================================

def always_true(*args, **kwargs):
    return True

class TNode:
    def __init__(self, value=None):
        self.value = value
        self.parent = None
        self.children = []

def _build_tree(root, flatbom, max_depth):

    def _build(node, depth=0):
        depth += 1
        if max_depth and depth > max_depth:
            return
        for c in children[(node.value.teilenummer, node.value.t_index)]:
            # For debugging:
            #space = depth * 3 * ' '
            #txt = "%s%s/%s %s/%s POS:%s MENGE:%s" % (space, c.baugruppe, c.b_index, c.teilenummer, c.t_index, c.position, c.menge)
            #from cdb import misc
            #misc.cdblogv(misc.kLogErr, 0, txt)

            cnode = TNode(c)
            cnode.parent = node
            node.children.append(cnode)
            all_parts[c.teilenummer].add(c)
            _build(cnode, depth)

    all_parts = collections.defaultdict(set)
    children = collections.defaultdict(set)
    for r in flatbom:
        children[(r.baugruppe, r.b_index)].add(r)

    root.menge = 1.0
    rootNode = TNode(root)
    _build(rootNode)

    return rootNode, all_parts


def _calculate_quantities(root_node):
    # teilenummer : ({indexes}, int)
    result = dict()

    def _map(tnode, depth):
        for child in tnode.children:
            _map(child, depth+1)
        _op(tnode)

    def _op(tnode):
        teilenummer = tnode.value.teilenummer
        if teilenummer not in result:
            result[teilenummer] = [{tnode.value.t_index}, 0]
        else:
            result[teilenummer][0].add(tnode.value.t_index)

        menge = tnode.value.menge
        current_parent = tnode.parent
        while current_parent is not None:
            menge *= current_parent.value.menge
            current_parent = current_parent.parent
        result[teilenummer][1] += menge

    _map(root_node, 0)

    return result


class BOMComparisonSitePlugin(AbstractPlugin):

    def __init__(self, site_object_id: str | None = None):
        self.site_object_id = site_object_id

    def get_bom_item_where_stmt_extension(self) -> Optional[str]:
        if self.site_object_id is None:
            return "1=1"

        # Note:
        # Do not use the 'bom_item_table_alias'. It won't work (query error).
        # The original code also has no alias
        return f"(site_object_id='{self.site_object_id}' or site_object_id='' or site_object_id is null)"


class BOMComparison(powerreports.CustomDataProvider):
    CARD = powerreports.N
    CALL_CARD = powerreports.CARD_N

    def __init__(self):
        self.addtl_filter = dict()

    @staticmethod
    def _validate_depth_arg(kwargs_depth):
        try:
            depth = int(kwargs_depth)
        except Exception:
            depth = 0
        if depth < 0:
            depth = 0
        return depth

    def _set_filters_if_present(self, kwargs):
        for k, v in kwargs.items():
            if k.startswith("filter_") and v:
                filter_name = k[7:]
                self.addtl_filter[filter_name] = v

    def _get_and_filter_flat_bom_if_present(self, item1, item2):
        site_object_id = self.addtl_filter.get("site_object_id")
        enhancement = FlatBomEnhancement()
        enhancement.add(BOMComparisonSitePlugin(site_object_id))

        def sort_func(bom_item):
            return bom_item.baugruppe, bom_item.b_index, bom_item.position

        item1_fb = bomqueries.flat_bom(item1, part_attributes=['t_kategorie', 'benennung'],
                                       bom_enhancement=enhancement, sort_func=sort_func)
        item2_fb = bomqueries.flat_bom(item2, part_attributes=['t_kategorie', 'benennung'],
                                       bom_enhancement=enhancement, sort_func=sort_func)
        return item1_fb, item2_fb

    def _set_category(self, report_data, t_kategorie):
        category = ItemCategory.ByKeys(t_kategorie)
        if category:
            category_attr = _get_lang_attribute(ItemCategory.name, self.cdbxml_report_lang)
            report_data["category"] = getattr(category, category_attr)

    @staticmethod
    def _get_beautified_indexes(indexes):
        indexes_str = ', '.join(indexes)
        if indexes_str.startswith(","):
            return indexes_str.replace(",", "' ',", 1)
        else:
            return indexes_str

    @classmethod
    def _add_quantity_and_indexes(cls, teilenummer, quantities, report_data, attr_suffix):
        report_data["t_index_%s" % attr_suffix] = cls._get_beautified_indexes(quantities[teilenummer][0])
        report_data["menge_%s" % attr_suffix] = quantities[teilenummer][1]

    @staticmethod
    def _set_item_hyperlink(report_data, t_index):
        urlmsg = cmsg.Cdbcmsg("part", "CDB_ShowObject", 0)
        urlmsg.add_item("teilenummer", "teile_stamm", report_data["teilenummer"])
        urlmsg.add_item("t_index", "teile_stamm", t_index)
        report_data["item_hyperlink"] = "%s cdb:texttodisplay:%s" % (
            urlmsg.cdbwin_url(), report_data["teilenummer"])

    def getData(self, parent_result, source_args, **kwargs):
        result = powerreports.ReportDataList(self)

        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang", i18n.default())

        item1 = None
        item2 = None
        parent_result_is_valid = isinstance(parent_result, powerreports.ReportDataList) and len(parent_result) > 1
        if parent_result_is_valid:
            item1 = parent_result[0].getObject()
            item2 = parent_result[1].getObject()
        else:
            return result

        depth_limit = self._validate_depth_arg(kwargs.get("depth", 0))

        # todo: to be tested
        self._set_filters_if_present(kwargs)

        if item1 is not None and item2 is not None:
            item1_fb, item2_fb = self._get_and_filter_flat_bom_if_present(item1, item2)
            item1_tree, item1_parts = _build_tree(item1, item1_fb, depth_limit)
            item2_tree, item2_parts = _build_tree(item2, item2_fb, depth_limit)
            item1_quantities = _calculate_quantities(item1_tree)
            item2_quantities = _calculate_quantities(item2_tree)

            for teilenummer in sorted(set(item1_parts.keys()).union(set(item2_parts.keys()))):

                item1 = item1_parts.get(teilenummer) # returns a set of occurences
                item2 = item2_parts.get(teilenummer)
                item = list(item1)[0] if item1 else list(item2)[0] # Note: use random occurence for part name and category

                report_data = powerreports.ReportData(self)
                report_data['teilenummer'] = teilenummer
                t_index = item.t_index # Note that this is a random index, if the part is contained in bom with different index
                report_data['benennung'] = item.benennung
                self._set_category(report_data, item.t_kategorie)
                self._set_item_hyperlink(report_data, t_index)

                msg2 = None
                if item1:
                    self._add_quantity_and_indexes(teilenummer, item1_quantities, report_data, 'a')
                if item2:
                    self._add_quantity_and_indexes(teilenummer, item2_quantities, report_data, 'b')

                if not item1 or not item2:
                    msg = util.CDBMsg(util.CDBMsg.kOk, "cdbvp_bom_report_occurrence")
                else:
                    item1_indexes = item1_quantities[teilenummer][0]
                    item1_quantity = item1_quantities[teilenummer][1]
                    item2_indexes = item2_quantities[teilenummer][0]
                    item2_quantity = item2_quantities[teilenummer][1]

                    quantity_different = item1_quantity != item2_quantity
                    version_different = item1_indexes != item2_indexes
                    if quantity_different and version_different:
                        msg = util.CDBMsg(util.CDBMsg.kOk, "cdbvp_bom_report_version")
                        msg2 = util.CDBMsg(util.CDBMsg.kOk, "cdbvp_bom_report_quantity")
                    elif version_different:
                        msg = util.CDBMsg(util.CDBMsg.kOk, "cdbvp_bom_report_version")
                    elif quantity_different:
                        msg = util.CDBMsg(util.CDBMsg.kOk, "cdbvp_bom_report_quantity")
                    else:
                        msg = util.CDBMsg(util.CDBMsg.kOk, "cdbvp_bom_report_none")
                if msg2 is not None:
                    report_data["diff"] = '{}/{}'.format(
                        msg.getText(self.cdbxml_report_lang, False), msg2.getText(self.cdbxml_report_lang, False)
                    )
                else:
                    report_data["diff"] = msg.getText(self.cdbxml_report_lang, False)
                result.append(report_data)
            return result

    def getArgumentDefinitions(self):
        return {"depth": sqlapi.SQL_INTEGER}

    def getSchema(self):
        t = powerreports.XSDType(powerreports.N)
        t.add_attr("teilenummer", sqlapi.SQL_CHAR)
        t.add_attr("benennung", sqlapi.SQL_CHAR)
        t.add_attr("category", sqlapi.SQL_CHAR)
        t.add_attr("t_index_a", sqlapi.SQL_CHAR)
        t.add_attr("menge_a", sqlapi.SQL_FLOAT)
        t.add_attr("t_index_b", sqlapi.SQL_CHAR)
        t.add_attr("menge_b", sqlapi.SQL_FLOAT)
        t.add_attr("diff", sqlapi.SQL_CHAR)
        t.add_attr("item_hyperlink", sqlapi.SQL_CHAR)
        return t


class BOMComparisonHeader(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_1
    CALL_CARD = powerreports.CARD_N

    def getSchema(self):
        t = powerreports.XSDType(1)
        t.add_attr("hyperlink1", sqlapi.SQL_CHAR)
        t.add_attr("hyperlink2", sqlapi.SQL_CHAR)
        t.add_attr("product1", sqlapi.SQL_CHAR)
        t.add_attr("product2", sqlapi.SQL_CHAR)
        t.add_attr("variant1", sqlapi.SQL_CHAR)
        t.add_attr("variant2", sqlapi.SQL_CHAR)
        t.add_attr("maxbom1", sqlapi.SQL_CHAR)
        t.add_attr("maxbom2", sqlapi.SQL_CHAR)
        t.add_attr("category1", sqlapi.SQL_CHAR)
        t.add_attr("category2", sqlapi.SQL_CHAR)
        t.add_attr("filter", sqlapi.SQL_CHAR)
        return t

    def getData(self, parent_result, source_args, **kwargs):
        result = powerreports.ReportData(self)
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang", i18n.default())
        cat_attr = _get_lang_attribute(ItemCategory.name, self.cdbxml_report_lang)
        item1 = item2 = None
        if isinstance(parent_result, powerreports.ReportDataList) and len(parent_result) > 1:
            item1 = parent_result[0].getObject()
            # ALT: result["hyperlink1"] = powerreports.MakeReportURL(item1)
            result["hyperlink1"] = powerreports.MakeReportURL(item1, None, item1.teilenummer)
            category1 = ItemCategory.ByKeys(kategorie=item1.t_kategorie)
            result["category1"] = getattr(category1, cat_attr)
            if is_installed("cs.vp.variants"):
                if item1.Variant:
                    result["product1"] = powerreports.MakeReportURL(item1.Variant.Product)
                    result["variant1"] = powerreports.MakeReportURL(item1.Variant)
                if item1.MaxBOM:
                    result["maxbom1"] = powerreports.MakeReportURL(item1.MaxBOM)
            item2 = parent_result[1].getObject()
            result["hyperlink2"] = powerreports.MakeReportURL(item2, None, item2.teilenummer)
            category2 = ItemCategory.ByKeys(kategorie=item2.t_kategorie)
            result["category2"] = getattr(category2, cat_attr)
            if is_installed("cs.vp.variants"):
                if item2.Variant:
                    result["product2"] = powerreports.MakeReportURL(item2.Variant.Product)
                    result["variant2"] = powerreports.MakeReportURL(item2.Variant)
                if item2.MaxBOM:
                    result["maxbom2"] = powerreports.MakeReportURL(item2.MaxBOM)

            bomfilter = {}
            for k, v in kwargs.items():
                if k.startswith("filter_"):
                    bomfilter[k[7:]] = v

            result["filter"] = get_bomfilter_text(bomfilter)

        return result


# ==============================================================================
# Report Verwendungsnachweis
# ==============================================================================

class PartUsage(powerreports.CustomDataProvider):
    """ Custom data provider for product usage structure """
    CARD = powerreports.N
    CALL_CARD = powerreports.CARD_1
    REC_LEVEL = -1
    TOP_ONLY = 0

    # Keep a dictionary of XML fields which will be returned in the XSDSchema
    # and their type, for each item of the results list
    XSDSchemaItems = {
        # calculated items
        "usage_lev": (sqlapi.SQL_INTEGER, "computed"),
        "baugr_hyperlink": (sqlapi.SQL_CHAR, "computed"),
        "pos_hyperlink": (sqlapi.SQL_CHAR, "computed"),
        "variant_article": (sqlapi.SQL_INTEGER, "computed"),
        "status_txt": (sqlapi.SQL_CHAR, "computed"),
        "category": (sqlapi.SQL_CHAR, "computed"),
        "designation": (sqlapi.SQL_CHAR, "computed"),
        "material_hyperlink": (sqlapi.SQL_CHAR, "computed"),
        "mengeneinheit_name": (sqlapi.SQL_CHAR, "computed"),

        # attributes of the item as a component
        "baugruppe": (sqlapi.SQL_CHAR, "component"),
        "b_index": (sqlapi.SQL_CHAR, "component"),
        "position": (sqlapi.SQL_INTEGER, "component"),
        "menge": (sqlapi.SQL_FLOAT, "component"),

        # attributes of the item
        "mengeneinheit": (sqlapi.SQL_CHAR, "item"),

        # attributes of the assembly the component is part of
        "status": (sqlapi.SQL_INTEGER, "assembly"),
        "t_kategorie": (sqlapi.SQL_CHAR, "assembly"),
        "cdb_objektart": (sqlapi.SQL_CHAR, "assembly"),
        "benennung": (sqlapi.SQL_CHAR, "assembly"),
        "techdaten": (sqlapi.SQL_CHAR, "assembly"),
        "material_object_id": (sqlapi.SQL_CHAR, "assembly"),
        }

    def getData(self, parent_result, source_args, **kwargs):
        self.cdbxml_report_lang = source_args.get("cdbxml_report_lang",
                                                  i18n.default())

        # The context (parent_result) is an article (type Item)
        self.item = None
        if isinstance(parent_result, powerreports.ReportData):
            self.item = parent_result.getObject()
        if self.item is None:
            raise RuntimeError("This provider needs an item as parameter")

        DBDependentScript = {sqlapi.DBMS_ORACLE: self.__getUsageORACLE,
                             sqlapi.DBMS_MSSQL: self.__getUsageMSSQL,
                             sqlapi.DBMS_SQLITE: self.__getUsageOtherDB}

        self.TOP_ONLY = int(kwargs.get("toplevel", 0))
        if kwargs["depth"] != "":
            self.REC_LEVEL = int(kwargs.get("depth", 0))

        # First we find all Usages of the part in the database
        # This step is optimized for some DMBS (Oracle, MSSQL)
        DBType = sqlapi.SQLdbms()  # get DB type

        # When a DB dependent script has been defined, run that;
        # in case DBType is not defined, run the default __getUsageOtherDB
        results = DBDependentScript.get(DBType, self.__getUsageOtherDB)(self.item)

        if is_installed("cs.vp.variants"):
            # Then we find out, which usages are maxboxs
            MaxBOMKeys = set([(rd["baugruppe"], rd["b_index"])
                              for rd in results
                              if int(rd["configurable"])])
            MaxBOMs = [Item.ByKeys(baugruppe, b_index)
                       for baugruppe, b_index in MaxBOMKeys]

            # Number of conditions which hang on the bom_item
            # Used to optimize the algorithm
            self.nconditions = {(rd["baugruppe"], rd["b_index"],
                                 rd["teilenummer"], rd["t_index"],
                                 rd["variante"], rd["position"]):
                                 (int(rd["n_conditions"]), int(rd["sum_conditions"]))
                                for rd in results}

            # Now we find out, for each MaxBOM, which variant articles
            # use the item
            variant_usages = powerreports.ReportDataList(self)
            for maxBOM in MaxBOMs:
                variant_usages += self.getVariantUsages(maxBOM)

            if kwargs.get("only_variants", "0") == "1":
                return variant_usages
            else:
                if self.TOP_ONLY:
                    filtered_results = [dict(rd) for rd in results
                                        if int(rd["top_level"])]
                else:
                    filtered_results = results
                return self._process_result(variant_usages + filtered_results,
                                            self.cdbxml_report_lang)
        else:
            return self._process_result(results, self.cdbxml_report_lang)

    @staticmethod
    def _process_result(data, lang):
        tmp_store = set() # this is to collect some objects to prevent garbage collection and reconstruction from db
        for rd in data:
            # set category
            category = ItemCategory.ByKeys(rd["t_kategorie"])
            if category:
                tmp_store.add(category)
                cat_attr = _get_lang_attribute(ItemCategory.name, lang)
                rd["category"] = getattr(category, cat_attr)

            # set status_txt
            definition = olc.StateDefinition.ByKeys(objektart=rd["cdb_objektart"],
                                                    statusnummer=rd["status"])
            if definition:
                tmp_store.add(definition)
                attr = _get_lang_attribute(olc.StateDefinition.statusbez, lang)
                rd["status_txt"] = getattr(definition, attr)

            # set mengeneinheit_name
            if rd["mengeneinheit"]:
                unit = PartUnit.ByKeys(rd["mengeneinheit"])
                if unit:
                    tmp_store.add(unit)
                    unit_attr = _get_lang_attribute(PartUnit.name_i18n, lang)
                    rd["mengeneinheit_name"] = getattr(unit, unit_attr)

            # set material link
            if rd["material_object_id"]:
                material = Material.ByKeys(cdb_object_id=rd["material_object_id"])
                if material:
                    rd["material_hyperlink"] = powerreports.MakeReportURL(
                        material,
                        action="CDB_ShowObject",
                        text_to_display=material.GetDescription())

        return data

    def getSchema(self):
        t = powerreports.XSDType(self.CARD)
        for attr, (sqlType, _itemType) in self.XSDSchemaItems.items():
            t.add_attr(attr, sqlType)
        return t

    def getArgumentDefinitions(self):
        return {"depth": sqlapi.SQL_INTEGER}

    def getVariantUsages(self, maxBOM):
        from cs.vp.variants import Variant2Part
        from cs.vp.variants import Variant
        from cs.vp.variants.filter import VariantBOMFilter

        result = powerreports.ReportDataList(self)

        filters = {}
        for vl in Variant2Part.KeywordQuery(max_bom_teilenummer=maxBOM.teilenummer,
                                            max_bom_t_index=maxBOM.t_index):
            variant = Variant.ByKeys(product_object_id=vl.product_object_id,
                                     id=vl.variant_id)
            try:
                fvariant = variant.get_filter_variant()
            except ue.Exception as ex:
                from cdb.platform.gui import Message
                msg = Message.ByKeys(meldung_nr=ex.nr)
                if msg and msg.meldung_label == "cdbvp_err_no_mapping":
                    raise ue.Exception("lk_err_no_mapping",
                                       "%s" % variant.GetDescription())
                elif msg and msg.meldung_label == "cdbvp_err_no_unique_mapping":
                    raise ue.Exception("lk_err_no_unique_mapping",
                                       "%s" % variant.GetDescription())
                else:
                    raise ex

            if vl.Part:
                filters[vl.Part] = VariantBOMFilter(fvariant.product_object_id,
                                                    fvariant.id)

        if filters:
            # For each instantiation of the maxBOM we generate a list
            # of the components on a path between the maxBOM and the item
            components = {instantiation: [] for instantiation in filters}
            self.visit_bom(maxbom=maxBOM,
                           bom=maxBOM,
                           filters=filters,
                           result=components,
                           depth=self.REC_LEVEL)

            for instantiation in components:
                occurrences = [x for x in components[instantiation] if x[1].Item == self.item]
                for level, comp in occurrences:
                    rd = powerreports.ReportData(self, instantiation)
                    rd["variant_article"] = 1

                    rd["menge"] = comp.menge
                    rd["position"] = comp.position
                    rd["usage_lev"] = level
                    rd["baugr_hyperlink"] = powerreports.MakeReportURL(
                        instantiation,
                        action="CDB_ShowObject",
                        text_to_display=instantiation.teilenummer)
                    rd["pos_hyperlink"] = powerreports.MakeReportURL(
                        comp,
                        action="CDB_ShowObject",
                        text_to_display=comp.position)
                    rd["category"] = comp.Item.t_kategorie_name
                    designation_attr = _get_lang_attribute(Item.i18n_benennung,
                                                           self.cdbxml_report_lang)
                    rd["designation"] = getattr(comp.Assembly, designation_attr)
                    rd["material_object_id"] = comp.Item.material_object_id

                    result.append(rd)
        return result

    def visit_bom(self, maxbom, bom, filters, result, depth, level=1):

        for comp in bom.Components:
            pkeys = (comp.baugruppe, comp.b_index, comp.teilenummer,
                     comp.t_index, comp.variante, comp.position)

            # If the component doesn't use the item we don't
            # consider it
            if pkeys in self.nconditions:
                item = comp.Item

                # If on the path to the maxbom there are no conditions
                # we don't need to check anything
                if self.nconditions[pkeys][1] == 0:
                    for instantiation in filters:
                        result[instantiation].append((level, comp))
                    drin = {fltr: True for fltr in filters.values()}
                else:
                    drin = {}
                    for f in filters.values():
                        drin[f] = f.eval(comp.baugruppe,
                                         comp.b_index,
                                         comp.teilenummer,
                                         comp.t_index,
                                         comp.variante,
                                         comp.position)

                    for instantiation in filters:
                        if drin[filters[instantiation]]:
                            result[instantiation].append((level, comp))

                if depth != 0 and item.isAssembly():
                    # Optimierungsmöglichkeit:
                    # nur die Varianten berücksichtigen, die item enthalten
                    self.visit_bom(maxbom, item,
                                   {inst: filters[inst]
                                    for inst in filters
                                    if self.nconditions[pkeys][1] == 0 or
                                    drin[filters[inst]]},
                                   result,
                                   depth - 1, level + 1)

    def __getUsageORACLE(self, item):
        """ ORACLE specific Hierarchical Query, customized for this report """
        lev_clause = ""
        order_clause = ""
        if self.TOP_ONLY:
            order_clause = " ORDER BY baugruppe, b_index, position, stufe DESC "
        else:
            order_clause = " ORDER BY rownr, baugruppe, b_index, position ASC "
        if self.REC_LEVEL != -1:
            lev_clause = " AND LEVEL <= %d " % int(self.REC_LEVEL)

        from cs.vp.variants import filter
        rating_method = filter.get_maxbom_rating_method()
        if rating_method == filter.kMaxBOMRatingMethodPredicateBased:
            rating_relation = "cdbvp_bom_predicate"
        else:
            rating_relation = "cdbvp_bom_mapping"

        BOMItems = """
        SELECT et.*, nvl(bp.n,0) AS n_conditions
        FROM einzelteile et
             LEFT OUTER JOIN (
                 SELECT
                     count(*) n, baugruppe, b_index, teilenummer, variante, position
                 FROM {rating_relation}
                 GROUP BY baugruppe, b_index, teilenummer, variante, position) bp
            ON bp.baugruppe=et.baugruppe
               AND bp.b_index=et.b_index
               AND bp.teilenummer=et.teilenummer
               AND bp.variante=et.variante
               AND bp.position=et.position
        """.format(rating_relation=rating_relation)

        HierarchicalQuery = """
        SELECT
                e.rownr, e.stufe usage_lev, e.teilenummer, e.position,
                e.menge, e.t_index, e.b_index, e.baugruppe, e.variante,
                e.auswahlmenge, e.path_conditions, e.n_conditions,
                ts.cdb_status_txt, ts.t_kategorie, ts.{designation} designation,
                ts.material_object_id, ts.cdb_objektart,
                ts.techdaten, ts.status, ts.t_bereich, ts.configurable,
                a.mengeneinheit,
                (SELECT CASE WHEN COUNT(*)=0 THEN 1 ELSE 0 END
                 FROM einzelteile e2
                 WHERE e2.teilenummer = e.baugruppe
                 AND e2.t_index = e.b_index) AS top_level
        FROM (SELECT ROWNUM rownr, CAST(LEVEL AS INTEGER) AS stufe, e.baugruppe, e.b_index, e.menge,
                        e.teilenummer, e.t_index, e.position, e.auswahlmenge, e.variante,
                        e.n_conditions, e.is_imprecise,
                        SYS_CONNECT_BY_PATH(e.n_conditions, '/') as path_conditions
             FROM ({BOMItems}) e
             WHERE 1>0 {lev_clause}
             START WITH e.teilenummer = '{teilenummer}' AND (e.t_index = '{t_index}' OR e.is_imprecise = 1)
             CONNECT BY NOCYCLE e.teilenummer = PRIOR e.baugruppe
             AND (e.t_index = PRIOR e.b_index OR e.is_imprecise = 1)
             ORDER SIBLINGS BY e.baugruppe, e.b_index) e,
            teile_stamm ts, teile_stamm a
        WHERE
                a.teilenummer = e.teilenummer
                AND a.t_index = e.t_index
                AND ts.teilenummer = e.baugruppe
                AND ts.t_index = e.b_index
                {order_clause}
        """.format(BOMItems=BOMItems,
                   lev_clause=lev_clause,
                   teilenummer=item.teilenummer,
                   t_index=item.t_index,
                   order_clause=order_clause,
                   designation=_get_lang_attribute(Item.i18n_benennung,
                                                   self.cdbxml_report_lang))

        recordSet = sqlapi.RecordSet2(sql=HierarchicalQuery)

        results = powerreports.ReportDataList(self)
        for record in recordSet:
            rd = powerreports.ReportData(self, record)

            # Compute hyperlinks manually, without instantiating the object
            rd["variant_article"] = 0
            rd["sum_conditions"] = sum([int(p)
                                        for p in rd["path_conditions"].split("/")
                                        if p != ""])
            rd["baugr_hyperlink"] = self \
                .__makeURLWithoutObj("bom_item", "einzelteile",
                                     "CDB_ShowObject", 0, record.baugruppe,
                                     {"cdb_object_id": record.cdb_object_id})
            rd["pos_hyperlink"] = self \
                .__makeURLWithoutObj("bom_item", "einzelteile",
                                     "CDB_ShowObject", 0, record.position,
                                     {"cdb_object_id": record.cdb_object_id})

            results.append(rd)
        return results

    def __getUsageMSSQL(self, item):
        """
        MSSQL specific recursive Common Table expression, customized for
        this report
        """
        # Clauses for the WHERE statement in SQL
        lev_clause = ""
        # End filter in case only the top level needs to be displayed
        end_filter = ""
        order_clause = ""
        if self.TOP_ONLY:
            order_clause = (" ORDER BY h.baugruppe, h.b_index, h.position, "
                            "          h.usage_lev DESC ")
        if self.REC_LEVEL != -1:
            lev_clause = " AND usage_lev < %d" % (int(self.REC_LEVEL) - 1)

        from cs.vp.variants import filter

        rating_method = filter.get_maxbom_rating_method()
        if rating_method == filter.kMaxBOMRatingMethodPredicateBased:
            rating_relation = "cdbvp_bom_predicate"
        else:
            rating_relation = "cdbvp_bom_mapping"

        # Recursive CTE. The sortorder attribute is built along the way in
        # order to deliver the results in the right hierarchical order by
        # baugruppe and index
        RecursiveCTEQuery = """
        WITH
        BOMItem AS (
            SELECT e.*, ISNULL(bp.n, 0) AS n_conditions,
            (SELECT CASE WHEN COUNT(*)=0 THEN 1 ELSE 0 END
                         FROM einzelteile e2
                         WHERE e2.teilenummer = e.baugruppe
                         AND e2.t_index = e.b_index) AS top_level
            FROM einzelteile AS e
            LEFT OUTER JOIN (
                 SELECT
                     count(*) n, baugruppe, b_index, teilenummer, variante, position
                 FROM {rating_relation}
                 GROUP BY baugruppe, b_index, teilenummer, variante, position
            ) AS bp ON
                bp.baugruppe=e.baugruppe
                AND bp.b_index=e.b_index
                AND bp.teilenummer=e.teilenummer
                AND bp.variante=e.variante
                AND bp.position=e.position
        ),
        Hierarchical (baugruppe, b_index, teilenummer, t_index,
                      position, menge, variante, auswahlmenge,
                      designation, t_kategorie, cdb_status_txt,
                      material_object_id, cdb_objektart, techdaten, mengeneinheit,
                      status, t_bereich, usage_lev, sortorder, top_level,
                      n_conditions, sum_conditions, configurable)
        AS (SELECT et.baugruppe, et.b_index, et.teilenummer, et.t_index,
                   et.position, et.menge, et.variante, et.auswahlmenge,
                   ts.{designation}, ts.t_kategorie, ts.cdb_status_txt,
                   ts.material_object_id, ts.cdb_objektart, ts.techdaten, a.mengeneinheit,
                   ts.status, ts.t_bereich, 1 as usage_lev,
                   cast(row_number() over(partition by et.teilenummer
                       order by et.baugruppe, et.b_index) as varchar(max)) as sortorder,
                   et.top_level,
                   et.n_conditions as n_conditions,
                   et.n_conditions as sum_conditions,
                   ts.configurable
            FROM   BOMItem AS et
            INNER JOIN teile_stamm AS ts ON et.baugruppe = ts.teilenummer AND
                                            et.b_index = ts.t_index
            INNER JOIN teile_stamm AS a ON et.teilenummer = a.teilenummer AND
                                            et.t_index = a.t_index
            WHERE  et.teilenummer = '{teilenummer}' AND (et.t_index = '{t_index}' OR et.is_imprecise = 1)
            UNION ALL
            SELECT et.baugruppe, et.b_index, et.teilenummer, et.t_index,
                   et.position, et.menge, et.variante, et.auswahlmenge,
                   ts.{designation}, ts.t_kategorie, ts.cdb_status_txt,
                   ts.material_object_id, ts.cdb_objektart, ts.techdaten, a.mengeneinheit,
                   ts.status, ts.t_bereich, usage_lev + 1,
                   h.sortorder + cast('/' as varchar(max)) +
                       cast(row_number() over(partition by et.teilenummer
                           order by et.baugruppe, et.b_index) as varchar(max)),
                   et.top_level,
                   h.sum_conditions + et.n_conditions AS sum_conditions,
                   et.n_conditions AS n_conditions,
                   ts.configurable
            FROM   BOMItem AS et
            INNER JOIN teile_stamm AS ts ON et.baugruppe = ts.teilenummer AND
                                            et.b_index = ts.t_index
            INNER JOIN teile_stamm AS a ON et.teilenummer = a.teilenummer AND
                                            et.t_index = a.t_index
            INNER JOIN Hierarchical AS h ON et.teilenummer = h.baugruppe AND
                                            (et.t_index = h.b_index OR et.is_imprecise = 1)
            WHERE 1>0 {lev_clause}
           )
        SELECT * FROM Hierarchical as h {end_filter} {order_clause}
        """.format(rating_relation=rating_relation,
                   teilenummer=item.teilenummer,
                   t_index=item.t_index,
                   lev_clause=lev_clause,
                   end_filter=end_filter,
                   order_clause=order_clause,
                   designation=_get_lang_attribute(Item.i18n_benennung,
                                                   self.cdbxml_report_lang))

        recordSet = sqlapi.RecordSet2(sql=RecursiveCTEQuery)
        if not order_clause:
            # sort records according to sortorder
            def key(record):
                return list(map(int, record.sortorder.split("/")))
            recordSet = sorted(recordSet, key=key)

        results = powerreports.ReportDataList(self)
        for record in recordSet:
            rd = powerreports.ReportData(self, record)
            # Compute hyperlinks manually
            rd["variant_article"] = 0
            rd["baugr_hyperlink"] = self \
                .__makeURLWithoutObj("bom_item", "einzelteile",
                                     "CDB_ShowObject", 0, record.baugruppe,
                                     {"cdb_object_id": record.cdb_object_id})
            rd["pos_hyperlink"] = self \
                .__makeURLWithoutObj("bom_item", "einzelteile",
                                     "CDB_ShowObject", 0, record.position,
                                     {"cdb_object_id": record.cdb_object_id})

            results.append(rd)
        return results

    def __getUsageOtherDB(self, item):
        """ Return the hierarchical usage structure by iterating through the
        items as instantiated objects in the Object Framework"""
        result = powerreports.ReportDataList(self)
        lev_comp_list = self.__getUsage(item)

        for component, level, n_conditions, sum_conditions in lev_comp_list:
            d = powerreports.ReportData(self, component)
            d["usage_lev"] = level
            d["top_level"] = int(len(component.Assembly.Usage) == 0)
            d["baugr_hyperlink"] = powerreports\
                .MakeReportURL(component, text_to_display="baugruppe")
            d["pos_hyperlink"] = powerreports\
                .MakeReportURL(component, text_to_display="position")

            # Number of conditions which hang on the component
            d["n_conditions"] = n_conditions
            d["sum_conditions"] = sum_conditions

            d["configurable"] = component.Assembly.configurable

            # Add attributes to the result depending on the object they describe
            for attr, (_sqlT, itemType) in self.XSDSchemaItems.items():
                if itemType == "component" and component.HasField(attr):
                    d[attr] = component[attr]
                elif itemType == "assembly" and component.Assembly.HasField(attr):
                    d[attr] = component.Assembly[attr]
                elif itemType == "item" and component.Item.HasField(attr):
                    d[attr] = component.Item[attr]

            designation_attr = _get_lang_attribute(Item.i18n_benennung,
                                                   self.cdbxml_report_lang)
            d["designation"] = getattr(component.Assembly, designation_attr)

            result.append(d)
        return result

    def __getUsage(self, item, curr_lev=1, n_parent_conditions=0):
        """ Computing the Part Usage recursively """
        result = []

        from cs.vp.variants import filter
        rating_method = filter.get_maxbom_rating_method()

        components = sorted(item.Usage, key=lambda x: (x.baugruppe, x.b_index))
        for component in components:
            if rating_method == filter.kMaxBOMRatingMethodSingleProperty:
                n_conditions = len(component.VPMProperties)
            else:
                n_conditions = len(component.VPMPredicates)
            sum_conditions = n_parent_conditions + n_conditions

            result.append((component,
                           curr_lev,
                           n_conditions,
                           sum_conditions))
            if self.REC_LEVEL == -1 or self.REC_LEVEL > curr_lev:
                result += self.__getUsage(component.Assembly,
                                          curr_lev + 1,
                                          sum_conditions)
        return result

    def __makeURLWithoutObj(self, class_name, relation, operation,
                            interactive, text_to_display, search_cond):
        """ Create a cdb URL without instantiating the object it refers to """
        url = cmsg.Cdbcmsg(class_name, operation, interactive)
        for key, val in search_cond.items():
            url.add_item(key, relation, val)
        string = url.cdbwin_url()
        return "%s cdb:texttodisplay:%s" % (string, text_to_display)
