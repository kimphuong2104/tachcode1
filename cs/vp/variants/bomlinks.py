#!/usr/bin/env python
# -*- python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Model classes and user exits for connecting BOMs and VPMs.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ["BOM_Predicate", "BOM_Term"]
import ast
import collections
import numbers

from cdb import misc
from cdb import sqlapi
from cdb import util
from cdb import ue

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import LocalizedField
from cdb.util import ErrorMessage

from cs.vp.variants import properties
from cs.vp.variants.operators import eval_term, sap_operator

from cs.vp.variants.vptools import WithChangeLog
from cs.vp import items

# ## Model entities
fBOMMapping = Forward(__name__ + ".BOMMapping")
fBOM_Predicate = Forward(__name__ + ".BOM_Predicate")
fBOM_Term = Forward(__name__ + ".BOM_Term")
fDD_Helper_EnumOnBOMItem = Forward(__name__ + ".DD_Helper_EnumOnBOMItem")
fProduct = Forward("cs.vp.products.Product")
fProperty = Forward("cs.vp.variants.properties.Property")
fProductAssemblyLink = Forward("cs.vp.variants.product_extensions.ProductAssemblyLink")
fAssemblyComponent = Forward("cs.vp.bom.AssemblyComponent")


class BOMMapping(Object):

    __maps_to__ = "cdbvp_bom_mapping"
    __classname__ = "cdbvp_bom_mapping"

    AssemblyComponent = Reference_1(fAssemblyComponent,
                                    fAssemblyComponent.baugruppe == fBOMMapping.baugruppe,
                                    fAssemblyComponent.b_index == fBOMMapping.b_index,
                                    fAssemblyComponent.teilenummer == fBOMMapping.teilenummer,
                                    fAssemblyComponent.variante == fBOMMapping.variante,
                                    fAssemblyComponent.position == fBOMMapping.position)

    PropertyValue = Reference_1(properties.EnumDefinition,
                                fBOMMapping.property_id,
                                fBOMMapping.vpm_product_object_id,
                                fBOMMapping.property_value)

    Property = Reference_1(fProperty,
                           fBOMMapping.property_id,
                           fBOMMapping.vpm_product_object_id)

    def on_create_pre(self, ctx):
        # Sicherstellen, dass ein Merkmal nur einmal bewertet werden kann
        for prop in self.AssemblyComponent.VPMProperties:
            if (prop.vpm_product_object_id == ctx.dialog.vpm_product_object_id
                    and "%d" % (prop.property_id) == ctx.dialog.property_id):
                raise ue.Exception("cdbvp_property_already_evaluated", self.Property.Name[''])

        ok, exc = self.Property.isMaxBOMRateable()
        if not ok:
            raise exc

        # if (not self.Property.ProductView or not self.Property.ProductView.isMaxBOMView()):
        #     if self.Property.Product.MaxBOMView:
        #         raise ue.Exception(1024,
        #                            "Nur Merkmale aus der Sicht '%s'"
        #                            " können bewertet werden." % self.Property.Product.MaxBOMView.name_de) # FIXME: i18n
        #     else:
        #         # Thinkabout: Sicht als MaxBom Sicht autom. aktivieren
        #         # FIXME
        #         raise ue.Exception(1024,
        #                            "Die MaxBOM kann nur mit den Merkmalen genauer einer Sicht bewertet werden."
        #                            "Die für die Merkmalsberwertung zu verwendende Sicht muss zunächst durch "
        #                            "Setzen der Checkbox 'MaxBOM Bewertung' an der jeweiligen Sicht ausgewählt werden.")

    def adjust_position_type(self, ctx):
        if not ctx.error:
            self.AssemblyComponent.set_position_type()

    event_map = {(("create", "delete"), "post"): "adjust_position_type"
                 }


class BOM_Predicate(Object, WithChangeLog):
    __maps_to__ = "cdbvp_bom_predicate"
    __classname__ = "cdbvp_bom_predicate"

    AssemblyComponent = Reference_1(fAssemblyComponent,
                                    fAssemblyComponent.baugruppe == fBOM_Predicate.baugruppe,
                                    fAssemblyComponent.b_index == fBOM_Predicate.b_index,
                                    fAssemblyComponent.teilenummer == fBOM_Predicate.teilenummer,
                                    fAssemblyComponent.variante == fBOM_Predicate.variante,
                                    fAssemblyComponent.position == fBOM_Predicate.position)

    Product = Reference_1(fProduct, fBOM_Predicate.product_object_id)

    PredicateText = LocalizedField("predicate_text", fala=True)

    Assembly = Reference_1(
        items.Item,
        items.Item.teilenummer == fBOM_Predicate.baugruppe,
        items.Item.t_index == fBOM_Predicate.b_index,
    )

    Parts = Reference_N(
        items.Item,
        items.Item.teilenummer == fBOM_Predicate.teilenummer
    )

    def get_signature(self):
        return ""

    @staticmethod
    def newID():
        return util.nextval("cdbvp_bom_predicate")

    def update_info_txt(self, ctx=None):
        desc = self.Product.GetDescription()
        for lang in self.PredicateText.keys():
            self.PredicateText[lang] = "[%s] %s" % (desc, self.info_str(lang))

    def info_str(self, lang="de"):
        return "*** empty expression ***"

    @classmethod
    def combined_sap_condition(cls, predicates):
        preds = list(predicates)
        if len(preds) == 1:
            return preds[0].sap_condition_str()
        else:
            return "\nOR ".join(["(%s)" % p.sap_condition_str()
                                 for p in predicates])

    def eval(self, x, **kwargs):
        return True

    def adjust_position_type(self, ctx):
        if not ctx.error and self.AssemblyComponent:
            self.AssemblyComponent.set_position_type()

    def skip_dialog_if_dd(self, ctx):
        if ctx.dragged_obj_relationship_name == "cdbvp_bom_item2cdbvp_predicate":
            ctx.skip_dialog()

    def update_predicate(self):
        """ Used after the creation of a predicate with the object framework.
            It produces the same result, as if the predicate was created
            with an operation (i.e. text are updated, etc..).
        """
        self.update_info_txt()
        self.AssemblyComponent.set_position_type()

    def create_predicate_id(self, ctx):
        self.predicate_id = BOM_Predicate.newID()

    event_map = {(("create", "delete"), "post"): "adjust_position_type",
                 (("create"), "pre_mask"): ("skip_dialog_if_dd", "create_predicate_id")}


class BOM_Term_Predicate(BOM_Predicate):
    __classname__ = "cdbvp_bom_predicate_term"
    __match__ = fBOM_Predicate.cdb_classname >= __classname__

    Terms = Reference_N(fBOM_Term,
                        fBOM_Term.baugruppe == fBOM_Predicate.baugruppe,
                        fBOM_Term.b_index == fBOM_Predicate.b_index,
                        fBOM_Term.teilenummer == fBOM_Predicate.teilenummer,
                        fBOM_Term.variante == fBOM_Predicate.variante,
                        fBOM_Term.position == fBOM_Predicate.position,
                        fBOM_Term.product_object_id == fBOM_Predicate.product_object_id,
                        fBOM_Term.predicate_id == fBOM_Predicate.predicate_id,
                        order_by="property_id")

    def info_str(self, lang="de"):
        if self.Terms:
            return " AND ".join([t.info_str(lang) for t in self.Terms])
        else:
            return "*** empty expression ***"

    def handle_dd(self, ctx):
        if ctx.dragged_obj_relationship_name == "cdbvp_bom_item2cdbvp_predicate":
            attrs = ["baugruppe", "b_index", "teilenummer", "variante",
                     "position", "product_object_id", "predicate_id"]
            args = {attr: ctx.dragged_obj[attr] for attr in attrs}
            bom_terms = BOM_Term.KeywordQuery(**args)

            for bom_term in bom_terms:
                bom_term.CopyWithChangeLog(baugruppe=self.baugruppe,
                                           b_index=self.b_index,
                                           teilenummer=self.teilenummer,
                                           variante=self.variante,
                                           predicate_id=self.predicate_id,
                                           position=self.position)

            self.getPersistentObject().update_info_txt()

    def eval(self, x, **kwargs):
        return all(term.eval(x) for term in self.Terms)

    def sap_condition_str(self):
        terms = list(self.Terms)
        if len(terms) == 1:
            return terms[0].sap_condition_str()
        else:
            return " AND ".join(["(%s)" % t.sap_condition_str()
                                 for t in self.Terms])

    def get_signature(self):
        return ";".join(sorted([
            "%s:%s" % (t.property_id, t.enum_value)
            for t in self.Terms
        ]))

    event_map = {(("create", "delete"), "post"): "adjust_position_type",
                 (("create"), "pre_mask"): "skip_dialog_if_dd",
                 (("create"), "post"): "handle_dd",
                 }


class BOM_String_Predicate(BOM_Predicate):
    __classname__ = "cdbvp_bom_string_predicate"
    __match__ = fBOM_Predicate.cdb_classname >= __classname__

    def get_signature(self):
        return self.expression

    def info_str(self, lang="de"):
        return self.expression

    @staticmethod
    def compute(product_object_id, expr, props, **kwargs):
        transformer = Predicate_Expression_Solver(product_object_id, props, **kwargs)
        try:
            node = ast.parse(expr, mode="eval")
            new_node = transformer.visit(node)
            code = compile(new_node, "<string>", "eval")
            result = eval(code)
            return result
        except Exception as ex:
            misc.log(9, "Expression evaluation for Predicate calculation failed %s" % ex)
            raise

    def eval(self, x, **kwargs):
        """
        Method to compute
        :param: x Dictionary that holds the filter parameters. Keys are the id of the property and values the vlaue of the enum_def
        :return: The computed value
        """
        return BOM_String_Predicate.compute(self.product_object_id, self.expression, x, **kwargs)


class Predicate_Expression_Solver(ast.NodeTransformer):
    reserved = ["int", "float", "bool", "True", "False"]

    def __init__(self, product_object_id, x, product_properties=None, product_values=None):
        """
        Class to Resolve the erp-codes to the IDs of the Property
        :param prop: The given predicate.
        :param x: x Dictionary that holds the filter parameters.
                    Keys are the id of the property and values the value of the enum_def
        :param product_properties: A dictionary that can be optionally speficied
                                   to optimize performance.
                                   It should be the same as given from
                                   `self.get_properties(True)`.
        :param product_values: A dictionary that can be optionally speficied
                               to optimize performance.
                               It should be the same as given from
                               `self.get_value(True)`.
        :return:
        """
        self.propertydict = x
        self.product_object_id = product_object_id
        self.properties = None
        self.values = None

        if product_properties is not None:
            self.properties = product_properties
        else:
            self.get_properties(True)

        if product_values is not None:
            self.values = product_values
        else:
            self.get_values(True)

    def get_properties(self, force=False):
        if self.properties is None or force is True:
            self.properties = {}
            for prop in properties.Property.KeywordQuery(product_object_id=self.product_object_id):
                self.properties[prop.erp_code] = {
                    "id": prop.id,
                    "data_type": prop.data_type
                }

        return self.properties

    def get_values(self, force=False):
        if self.values is None or force is True:
            self.values = {}
            for value in properties.EnumDefinition.KeywordQuery(product_object_id=self.product_object_id):
                self.values[(value.id, value.value)] = {
                    "name": value.name
                }

        return self.values

    def __isnumber(self, n):
        try:
            float(n)
            return True
        except (ValueError, TypeError):
            return False

    def _get_value(self, name):
        # get the value of the property name in the current variant
        prop = self.properties.get(name)
        if prop is not None:
            prop_id = prop.get("id")
            if prop_id in self.propertydict:
                value = self.propertydict[prop_id]

                if value is True or value is False:
                    return value

                value_dict = self.values.get((prop_id, value))
                if value_dict is None or "name" not in value_dict:
                    raise ErrorMessage("cdbvp_string_predicate_notfound", name)
                return properties.Property.get_typed_value_for_type(
                    prop.get("data_type"), value_dict.get("name"))
        else:
            raise ErrorMessage("cdbvp_string_predicate_notfound", name)

    def visit_Name(self, node):
        literals = [True, False, None]
        if node.id not in self.reserved and not self.__isnumber(node.id):
            value = self._get_value(node.id)
            if any(value is literal for literal in literals):
                new_node = ast.Constant(value=value, ctx=node.ctx)
            elif isinstance(value, numbers.Number):
                new_node = ast.Num(n=value)
            else:
                new_node = ast.Str(s="%s" % value)
            new_node = ast.copy_location(new_node, node)
            return ast.fix_missing_locations(new_node)
        return node


class BOM_Term(Object, WithChangeLog):
    __maps_to__ = "cdbvp_bom_term"
    __classname__ = "cdbvp_bom_term"

    Predicate = Reference_1(fBOM_Predicate,
                            fBOM_Term.baugruppe,
                            fBOM_Term.b_index,
                            fBOM_Term.teilenummer,
                            fBOM_Term.variante,
                            fBOM_Term.position,
                            fBOM_Term.product_object_id,
                            fBOM_Term.predicate_id)

    Property = Reference_1(fProperty,
                           fBOM_Term.property_id,
                           fBOM_Term.product_object_id)

    PropertyValue = Reference_1(properties.EnumDefinition,
                                fBOM_Term.property_id,
                                fBOM_Term.product_object_id,
                                fBOM_Term.enum_value)

    @staticmethod
    def newID():
        return util.nextval("cdbvp_bom_term")

    def on_create_pre(self, ctx):
        if self.enum_value is None:
            self.enum_value = -1
            self.operator = '\N{BALLOT BOX WITH CHECK}'
        else:
            self.operator = "="

    def update_predicate_txt(self, ctx=None):
        if self.Predicate:
            self.Predicate.update_info_txt()

    def info_str(self, lang):
        lhs = self.Property.Name[lang]
        if not self.PropertyValue:
            return "%s %s" % (lhs, self.operator)
        else:
            return "%s %s %s" % (
                lhs,
                self.operator,
                self.PropertyValue.ValueText[lang]
            )

    def sap_condition_str(self):
        return "$parent.%s %s '%s'" % (self.Property.erp_id(),
                                       sap_operator(self.operator),
                                       self.PropertyValue.name)

    def eval(self, x):
        return BOM_Term.eval_term(self, x)

    @staticmethod
    def eval_term(term, x):
        prop_val = x.get(term.property_id, False)
        return eval_term(
            prop_val,
            term.enum_value,
            term.operator
        )

    def on_create_pre_mask(self, ctx):
        if ctx.dragged_obj:
            ctx.skip_dialog()

    event_map = {
        (("create", "copy", "modify", "delete"), ("post")): "update_predicate_txt"
        }


class DD_Helper_EnumOnBOMItem(Object):
    __maps_to__ = "cdbvp_ddh_enum_on_bom_item"
    __classname__ = "cdbvp_ddh_enum_on_bom_item"

    Property = Reference_1(fProperty,
                           fDD_Helper_EnumOnBOMItem.property_id,
                           fDD_Helper_EnumOnBOMItem.product_object_id)

    def _delete_persistent_object(self):
        obj = self.getPersistentObject()
        if obj:
            obj.Delete()

    def _check_preconditions(self):
        ok, exc = self.Property.isMaxBOMRateable()
        if not ok:
            raise exc

        # Prüfung zunächst auskommentiert, da für ENE tiefe Konfiguration
        # der MAX-BOM gezeigt werden muss. Annahme dabei: keine Wiederverwendung
        # der Unterbaugruppen.
        # Das Merkmal muss zum selben Produkt gehören, das die Baugruppe
        # konfiguriert
        # link = fProductAssemblyLink.ByKeys(self.product_object_id,
        #                                    self.baugruppe,
        #                                    self.b_index)
        # if not link:
        #     raise ue.Exception(1024,
        #                        "Die Stückliste kann nicht durch Merkmale"
        #                        " dieses Produkts bewertet werden.")

    def on_create_pre(self, ctx):
        """ If for some reason a relship object is left over, delete it before
            starting the DB INSERT, to avoid duplicate key errors.
        """
        if self.property_value is None:
            self.property_value = -1
            self.cdbvp_operator = '\N{BALLOT BOX WITH CHECK}'
        else:
            self.cdbvp_operator = "="

        self._check_preconditions()
        self._delete_persistent_object()

    def on_create_post(self, ctx):
        """ Create a new predicate and term with the enum value as condition.
            The DD_Helper_EnumOnBOMItem record itself will be deleted from the
            DB, because the actual relationship is
            bom_item -> predicate -> term -> enum value.
            This whole construction is only needed because CDB requires the
            class to be there for D&D configuration.
        """
        p = BOM_Term_Predicate\
                .CreateWithChangeLog(baugruppe=self.baugruppe,
                                     b_index=self.b_index,
                                     teilenummer=self.teilenummer,
                                     variante=self.variante,
                                     position=self.position,
                                     product_object_id=self.product_object_id,
                                     predicate_id=BOM_Predicate.newID())

        property_value = self.property_value if self.property_value >= 0 else None
        BOM_Term.CreateWithChangeLog(baugruppe=self.baugruppe,
                                     b_index=self.b_index,
                                     teilenummer=self.teilenummer,
                                     variante=self.variante,
                                     position=self.position,
                                     product_object_id=self.product_object_id,
                                     predicate_id=p.predicate_id,
                                     term_id=BOM_Term.newID(),
                                     property_id=self.property_id,
                                     enum_value=property_value,
                                     operator=self.cdbvp_operator)

        # Set predicate text
        p.update_info_txt()
        # Everything is set up, now we can drop the relship object
        self._delete_persistent_object()
        # set position type of BOM position
        p.AssemblyComponent.set_position_type()

    def on_create_pre_mask(self, ctx):
        if ctx.dragged_obj:
            ctx.skip_dialog()


# -----------------------------------------------------------------------------

def get_predicates(product_object_id):
    """
    Retrieve all the bom predicates for a product with a single query.
    This is useful to avoid performance problems using object frameworks references.

    :return: A dictionary. The keys are tuples of the form
        ``(baugruppe, b_index, teilenummer, variante, position)`` and the values
        are lists of ``cdb.sqlapi.Record``.
    """
    result = collections.defaultdict(list)
    rs = sqlapi.RecordSet2(
        table="cdbvp_bom_predicate",
        condition="product_object_id='%s'" % sqlapi.quote(product_object_id)
    )

    for r in rs:
        result[(r.baugruppe, r.b_index, r.teilenummer, r.variante, r.position)].append(r)

    return result


def get_terms(product_object_id):
    """
    Retrieve all the bom terms for a product with a single query
    This is useful to avoid performance problems using object frameworks references-

    :return: A dictionary. The keys are tuples of the form
        ``(baugruppe, b_index, teilenummer, variante, position, predicate_id)`` and the values
        are lists of ``cdb.sqlapi.Record``.
    """
    result = collections.defaultdict(list)
    rs = sqlapi.RecordSet2(
        table="cdbvp_bom_term",
        condition="product_object_id='%s'" % sqlapi.quote(product_object_id)
    )

    for r in rs:
        result[(r.baugruppe, r.b_index, r.teilenummer, r.variante, r.position, r.predicate_id)].append(r)

    return result
