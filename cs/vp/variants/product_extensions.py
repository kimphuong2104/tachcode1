#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import dberrors
from cdb import sig
from cdb import sqlapi
from cdb import ue
from cdb import util
from cdb.classbody import classbody
from cdb.objects import ByID
from cdb.objects import Forward
from cdb.objects import Object
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import Reference_1
from cdb.objects import Reference_N

from cs.vp.bom import AssemblyComponent
from cs.vp.items import Item
from cs.vp.products import Product
from cs.vp.variants import ProductVariant
from cs.vp.variants import Variant, bomlinks
from cs.vp.variants.bomlinks import BOMMapping
from cs.vp.variants.bomlinks import BOM_Predicate
from cs.vp.variants.bomlinks import BOM_Term
from cs.vp.variants.constraints import Constraint
from cs.vp.variants.filter import get_maxbom_rating_method, kMaxBOMRatingMethodSingleProperty, \
    kMaxBOMRatingMethodPredicateBased, VirtualVariantBOMFilter
from cs.vp.variants.productviews import ProductView
from cs.vp.variants.properties import EnumDefinition
from cs.vp.variants.properties import Property
from cs.vp.variants.properties import Property2SubProductProperty

fProduct2Subproducts = Forward(__name__ + ".Product2Subproducts")
ProductAssemblyLink = Forward(__name__ + ".ProductAssemblyLink")


class Product2Subproducts(Object):
    __maps_to__ = "cdbvp_product2product"
    __classname__ = "cdbvp_product2product"

    SubProduct = Reference_1(Product, fProduct2Subproducts.product_object_id2)

    Product = Reference_1(Product, fProduct2Subproducts.product_object_id)

    def _findParentProductProperty(self, subproduct_prop):
        if subproduct_prop.CatalogueProperty:
            for prop in self.Product.AllProperties:
                if prop.CatalogueProperty and prop.CatalogueProperty == subproduct_prop.CatalogueProperty:
                    return prop
        return None

    def addInterfaceProperties(self, ctx):
        for prop in self.SubProduct.VariantDrivingProperties:
            if prop.interface_property:
                parentproduct_prop = self._findParentProductProperty(prop)
                if parentproduct_prop:
                    # add missing enum values
                    for enum_val in prop.EnumValues:
                        try:
                            enum_val.Copy(product_object_id=self.Product.cdb_object_id,
                                          id=parentproduct_prop.id)
                        except dberrors.DBConstraintViolation:
                            pass
                else:
                    new_prop_id = Property.NewID()
                    parentproduct_prop = prop.Copy(product_object_id=self.Product.cdb_object_id,
                                                   id=new_prop_id)
                    for enum_val in prop.EnumValues:
                        enum_val.Copy(product_object_id=self.Product.cdb_object_id,
                                      id=new_prop_id)
                Property2SubProductProperty.Create(product_object_id=parentproduct_prop.product_object_id,
                                                   property_id=parentproduct_prop.id,
                                                   subproduct_object_id=prop.product_object_id,
                                                   subproduct_property_id=prop.id)

    def acceptSubProduct(self, ctx):
        if self.product_object_id == self.product_object_id2:
            raise ue.Exception("cdbvp_mod_asgn_err")

        if not self.SubProduct.status == 200:
            raise ue.Exception("cdbvp_mod_asgn_status_err")

    event_map = {(('create'), ('pre')): "acceptSubProduct",
                 (('create'), ('post')): "addInterfaceProperties"
                 }


class ProductAssemblyLink(Object):
    __maps_to__ = "cdbvp_product_bom"
    __classname__ = "cdbvp_product_bom"

    Item = Reference_1(Item,
                       ProductAssemblyLink.teilenummer,
                       ProductAssemblyLink.t_index)

    Product = Reference_1(Product, ProductAssemblyLink.product_object_id)

    MSG_RESULT_BOM_COPY = "1"
    MSG_RESULT_BOM_MOVE = "2"

    def checkUniqueness(self, ctx):
        t = sqlapi.SQLselect(("product_object_id from cdbvp_product_bom "
                              "where product_object_id != '%s' and "
                              "teilenummer = '%s' and t_index = '%s'") %
                             (self.product_object_id, self.teilenummer,
                              self.t_index))
        if sqlapi.SQLrows(t) > 0:
            vpm = Product.ByKeys(sqlapi.SQLstring(t, 0, 0))
            raise ue.Exception("cdbvp_maxbom_already_configured", vpm.code)

    @classmethod
    def askCopyOrMove(cls, ctx):
        """ Ask the user whether the BOM association should be copied or moved
        """
        mb = ctx.MessageBox("cdbvp_bom_copy_move_dlg", [],
                            "cdb::argument.cdbvp_bom_copy_move",
                            ctx.MessageBox.kMsgBoxIconQuestion)
        btn = ctx.MessageBoxButton("cdbvp_btn_bom_copy",
                                   cls.MSG_RESULT_BOM_COPY,
                                   ctx.MessageBoxButton.kButtonActionCallServer,
                                   is_dflt=1)
        mb.addButton(btn)
        btn = ctx.MessageBoxButton("cdbvp_btn_bom_move",
                                   cls.MSG_RESULT_BOM_MOVE,
                                   ctx.MessageBoxButton.kButtonActionCallServer,
                                   is_dflt=0)
        mb.addButton(btn)
        mb.addCancelButton(btn)
        ctx.show_message(mb)

    def check_drag_drop_action(self, ctx):
        """ If we are in a D&D of a BOM association from one product to
            another: check that the BOM conditions are valid for the new
            product, and decide whether to move or copy the association.
        """
        if ctx.dragged_obj_relationship_name == 'cdbvp_product2bom':
            old_product_id = ctx.dragged_obj_parent.cdb_object_id
            new_product_id = self.product_object_id
            # Check for invalid BOM conditions (ie. ones that reference invalid
            # properties or property values).
            invalid = Product.invalid_bom_links(old_product_id,
                                                new_product_id,
                                                self.teilenummer,
                                                self.t_index)
            if invalid:
                msg = ", ".join("(%s/%s)" % (_id, val)
                                for (_id, val) in invalid)
                raise ue.Exception("cdbvp_invalid_bom_links", msg)
            # Determine whether to copy or to move. If we could not delete,
            # then it is copy, otherwise ask the user.
            orig = ProductAssemblyLink.ByKeys(old_product_id,
                                              self.teilenummer,
                                              self.t_index)
            if orig.is_delete_allowed():
                if ("cdbvp_bom_copy_move" not in ctx.sys_args.get_attribute_names()
                        or ctx.sys_args.cdbvp_bom_copy_move == ""):
                    self.askCopyOrMove(ctx)
                elif ctx.sys_args.cdbvp_bom_copy_move == self.MSG_RESULT_BOM_COPY:
                    ctx.keep("cdbvp_copy_bom_link", "1")
                else:
                    ctx.keep("cdbvp_copy_bom_link", "0")
            else:
                ctx.keep("cdbvp_copy_bom_link", "1")

    def adjust_asm_link(self, ctx):
        """ If we just did a D&D of a BOM association from one product to
            another: either move the association, incl. BOM conditions, or
            copy it. Which one depends on the decision made in
            check_drag_drop_action.
        """
        if ctx.dragged_obj_relationship_name == 'cdbvp_product2bom':
            old_product_id = ctx.dragged_obj_parent.cdb_object_id
            new_product_id = self.product_object_id
            if ('cdbvp_copy_bom_link' in ctx.ue_args.get_attribute_names()
                    and ctx.ue_args.cdbvp_copy_bom_link == "1"):
                Product.copy_bom_links(old_product_id, new_product_id,
                                       [(self.teilenummer, self.t_index)])
            else:
                Product.move_max_bom(old_product_id, new_product_id,
                                     self.teilenummer, self.t_index,
                                     delete_old_link=True,
                                     delete_invalid_bom_links=False)
            ctx.refresh_tables([BOMMapping.__maps_to__,
                                BOM_Predicate.__maps_to__,
                                BOM_Term.__maps_to__])

    def set_item_configurable(self, ctx):
        if not ctx.error:
            item = self.Item
            if not item.configurable:
                item.configurable = 1

    def reset_item_configurable(self, ctx):
        if not ctx.error:
            item = self.Item
            if item.configurable and not item.ProductLinks:
                item.configurable = 0

    def is_delete_allowed(self):
        return (self.Product.CheckAccess('CHANGE')
                or self.Item.CheckAccess('CHANGE'))

    def check_delete_allowed(self, ctx):
        """ The association between a product and a MaxBOM may only be removed
            if at least one of the objects may be changed by the user.
        """
        if not self.is_delete_allowed():
            raise ue.Exception("cdbvp_err_detach_max_bom")

    def delete_unused_bom_links(self, ctx):
        if not ctx.error:
            Product.ByKeys(self.product_object_id).delete_unreachable_bom_links()

    # Remove check for uniqueness, because a MaxBOM can be assiciated with
    # several indexes of a product!
    event_map = {
        # (('create', 'copy'), ('pre')): ("checkUniqueness"),
        ('create', 'post_mask'): "check_drag_drop_action",
        ('create', 'post'): "adjust_asm_link",
        (('create', 'copy'), 'post'): "set_item_configurable",
        ('delete', 'pre'): "check_delete_allowed",
        ('delete', 'post'): ("delete_unused_bom_links",
                             "reset_item_configurable")
        }


@classbody
class Product(object):

    def _getMaxBoms(self):
        result = []
        for l in self.ToplevelAssemblyLinks:
            if l.Item:
                result.append(l.Item)
        return result
    MaxBoms = ReferenceMethods_N(Item, _getMaxBoms)

    ToplevelAssemblyLinks = Reference_N(
        ProductAssemblyLink,
        ProductAssemblyLink.product_object_id == Product.cdb_object_id)

    Views = Reference_N(ProductView,
                        ProductView.product_object_id == Product.cdb_object_id)

    AllConstraints = Reference_N(Constraint,
                                 Constraint.product_object_id == Product.cdb_object_id)

    AllProperties = Reference_N(Property,
                                Property.product_object_id == Product.cdb_object_id)

    AllVariants = Reference_N(Variant,
                              Variant.product_object_id == Product.cdb_object_id)

    Properties = Reference_N(
        Property,
        (Property.product_object_id == Product.cdb_object_id) &
        (Property.view_id == 0)
    )

    # threed support
    Variants = Reference_N(ProductVariant,
                           ProductVariant.product_object_id == Product.cdb_object_id)

    BOM_Predicates = Reference_N(BOM_Predicate,
                                 BOM_Predicate.product_object_id == Product.cdb_object_id)

    BOM_Terms = Reference_N(BOM_Term,
                            BOM_Term.product_object_id == Product.cdb_object_id)

    BOMMappings = Reference_N(BOMMapping,
                              BOMMapping.vpm_product_object_id == Product.cdb_object_id)

    SubproductReferences = Reference_N(Product2Subproducts,
                                       Product2Subproducts.product_object_id == Product.cdb_object_id)

    _VariantDrivingProperties = Reference_N(Property,
                                            Property.product_object_id == Product.cdb_object_id,
                                            Property.view_id == 0,
                                            Property.variant_relevant > 0,
                                            order_by=Property.position)
    TopLevelProperties = Reference_N(
        Property,
        (Property.product_object_id == Product.cdb_object_id) &
        (Property.parent_id == None)
    )

    def _get_variant_driving_properties(self):
        return [prop for prop in self._VariantDrivingProperties
                if len(prop.GeneratorRelevantEnumValues) > 0]
    VariantDrivingProperties = ReferenceMethods_N(Property, _get_variant_driving_properties)

    def _getMaxBOMView(self):
        result = self.Views.KeywordQuery(max_bom_evaluation=1)
        return result[0] if result else None
    MaxBOMView = ReferenceMethods_1(ProductView, _getMaxBOMView)

    def _get_toplevel_assemblies(self):
        result = [link.Item for link in self.ToplevelAssemblyLinks if link.Item]
        return result
    ToplevelAssemblies = ReferenceMethods_N(Item, _get_toplevel_assemblies)

    def _get_usable_toplevel_assemblies(self):
        result = [link.Item
                  for link in self.ToplevelAssemblyLinks
                  if link.Item and link.Item.cdb_obsolete != 1]
        return result
    UsableToplevelAssemblies = ReferenceMethods_N(Item,
                                                  _get_usable_toplevel_assemblies)

    def find_component_pathes(self, bom_item):
        """Walk the "usage" relationship from `bom_item` to `top_level_assemblies`
        and return all pathes leading from `bom_item` to one of the
        `top_level_assemblies`."""

        top_level_assemblies = self.ToplevelAssemblies
        pathes = []

        def recursive_walk_up(path):
            here = path[-1]
            if here.Assembly in top_level_assemblies:
                # Abbruch: Pfad eintragen
                path.reverse()
                pathes.append(path)
            else:
                for used in here.Assembly.Usage:
                    new_path = list(path)
                    new_path.append(used)
                    recursive_walk_up(new_path)

        recursive_walk_up([bom_item])
        return pathes

    def getVariantTableAdapter(self, **kwargs):
        from cs.vp.variants.varianttableadapters import ProductAdapter
        from cs.vp.variants.varianttableadapters import CombinedViewAdapter
        from cs.vp.variants.varianttableadapters import CombinedFilteredAdapter
        adapter = None

        view_ids = kwargs.get("views", [])
        hidden_props = kwargs.get("hidden_props", [])

        if view_ids:
            views = []
            for view_id in view_ids:
                views.append(ProductView.ByKeys(view_id, self.cdb_object_id))

            if hidden_props:
                adapter = CombinedFilteredAdapter(self, views, hidden_props)
            else:
                adapter = CombinedViewAdapter(self, views)

        else:
            adapter = ProductAdapter(self)
        return adapter

    def copy_max_boms_from(self, old_prod):
        """ A copy / index of a VP will have no reference to the MaxBOMs of
            the original (see relship definition), so we have to copy the
            associations to valid BOMs here.
        """
        max_boms = []
        for item in old_prod.UsableToplevelAssemblies:
            ProductAssemblyLink.Create(product_object_id=self.cdb_object_id,
                                       teilenummer=item.teilenummer,
                                       t_index=item.t_index)
            max_boms.append((item.teilenummer, item.t_index))
        self.copy_bom_links(old_prod.cdb_object_id,
                            self.cdb_object_id,
                            max_boms)

    @classmethod
    def copy_bom_links(cls, old_id, new_id, max_boms):
        """ After a deep copy of the product, copy the predicates / direct
            enum value associations with BOM positions.
            Attention: the code assumes, that a copy of a product leaves all
            ids as they are, and only changes the object ID for the product!
        """
        asm_keys = cls._contained_assemblies(max_boms)
        for (teilenummer, t_index) in asm_keys:
            for bm in BOMMapping.KeywordQuery(vpm_product_object_id=old_id,
                                              baugruppe=teilenummer,
                                              b_index=t_index):
                bm.Copy(vpm_product_object_id=new_id)
            for pred in BOM_Predicate.KeywordQuery(product_object_id=old_id,
                                                   baugruppe=teilenummer,
                                                   b_index=t_index):
                pred.Copy(product_object_id=new_id)
                if hasattr(pred, "Terms"):
                    for term in pred.Terms:
                        term.Copy(product_object_id=new_id)

    @classmethod
    def _contained_assemblies(cls, max_boms):
        """ Returns a set of all assemblies, that are referenced recursively
            from one of the given MaxBOMs. The result includes the input.
        """
        candidates = max_boms[:]
        already_seen = set()
        result = set()
        while candidates:
            tnr, tidx = candidates.pop()
            if (tnr, tidx) not in already_seen:
                already_seen.add((tnr, tidx))
                parts = list(AssemblyComponent.KeywordQuery(baugruppe=tnr,
                                                            b_index=tidx))
                if parts:
                    result.add((tnr, tidx))
                    for part in parts:
                        candidates.append((part.teilenummer, part.t_index))
        return result

    def delete_unreachable_bom_links(self):
        """ Delete any BOM conditions that reference this product, but are not
            reachable through an MaxBOM associated with the product.
        """
        max_boms = [(link.teilenummer, link.t_index)
                    for link in self.ToplevelAssemblyLinks]
        valid_items = self._contained_assemblies(max_boms)
        for bm in self.BOMMappings:
            if (bm.baugruppe, bm.b_index) not in valid_items:
                bm.Delete()
        for bt in self.BOM_Terms:
            if (bt.baugruppe, bt.b_index) not in valid_items:
                bt.Delete()
        for bp in self.BOM_Predicates:
            if (bp.baugruppe, bp.b_index) not in valid_items:
                bp.Delete()

    @classmethod
    def invalid_bom_links(cls, old_id, new_id, teilenummer, t_index):
        """ Determine which BOM links (via direct property value mappings or
            via predicates / terms) would be invalid, if the MaxBOM
            (teilenummer, t_index) would be linked to the VP with prop_id 'new_id'
            instead of 'old_id'.
            Returns a set of (property prop_id, property value) pairs, for which no
            corresponding definition could be found in the new VP.
        """
        used = set()
        for bm in BOMMapping.KeywordQuery(vpm_product_object_id=old_id,
                                          baugruppe=teilenummer,
                                          b_index=t_index):
            used.add((bm.property_id, bm.property_value))
        for bt in BOM_Term.KeywordQuery(product_object_id=old_id,
                                        baugruppe=teilenummer,
                                        b_index=t_index):
            used.add((bt.property_id, bt.enum_value))
        not_found = set()
        for prop_id, value in used:
            if not EnumDefinition.KeywordQuery(product_object_id=new_id,
                                               id=prop_id, value=value):
                not_found.add((prop_id, value))
        return not_found

    @classmethod
    def move_max_bom(cls, old_id, new_id, teilenummer, t_index,
                     delete_old_link, delete_invalid_bom_links):
        """ Move the association from a VP to a MaxBOM to another VP (index),
            incl. all the MaxBOM related stuff.
            If 'delete_old_link' is set, a new ProductAssemblyLink has already
            been created, and the old one can be deleted. Otherwise, the link
            is changed to point to the new product ID.
        """
        old = ProductAssemblyLink.ByKeys(old_id, teilenummer, t_index)
        if delete_old_link:
            old.Delete()
        else:
            old.Update(product_object_id=new_id)
        # keep BOM conditions in sync
        invalid = Product.invalid_bom_links(old_id, new_id,
                                            teilenummer, t_index)
        if invalid:
            # There are BOM links that are not valid for the new VP. Either
            # delete them, or throw an exception.
            if delete_invalid_bom_links:
                for (prop_id, value) in invalid:
                    BOMMapping.KeywordQuery(vpm_product_object_id=old_id,
                                            baugruppe=teilenummer,
                                            b_index=t_index,
                                            property_id=prop_id,
                                            property_value=value).Delete()
                    BOM_Term.KeywordQuery(product_object_id=old_id,
                                          baugruppe=teilenummer,
                                          b_index=t_index,
                                          property_id=prop_id,
                                          enum_value=value).Delete()
            else:
                raise Exception("Die Merkmale/Werte %s fehlen im Ziel"
                                % ", ".join("(%s/%s)" % (prop_id, value)
                                            for (prop_id, value) in invalid))
        # Move the valid BOM links over.
        for bm in BOMMapping.KeywordQuery(vpm_product_object_id=old_id,
                                          baugruppe=teilenummer,
                                          b_index=t_index):
            bm.Update(vpm_product_object_id=new_id)
        for pred in BOM_Predicate.KeywordQuery(product_object_id=old_id,
                                               baugruppe=teilenummer,
                                               b_index=t_index):
            if hasattr(pred, "Terms"):
                for term in pred.Terms:
                    term.Update(product_object_id=new_id)
            pred.Update(product_object_id=new_id)
            pred.update_info_txt()

    @classmethod
    def attach_bom_links(cls, from_product_id, from_teilenummer, from_t_index,
                         to_product_id, to_teilenummer, to_t_index):
        """ Take the BOM links that are defined for the combination
            (from_product_id / from_teilenummer, from_t_index), and copy
            them to (to_product_id / to_teilenummer, to_t_index).
            It is assumed that BOM position correspond based on their
            teilenummer, t_index and position.
            If a component is missing in the target part, its conditions are
            silently discarded.
        """
        # check for missing properties / values in target product
        if from_product_id != to_product_id:
            invalid = cls.invalid_bom_links(from_product_id, to_product_id,
                                            from_teilenummer, from_t_index)
            if invalid:
                raise Exception("Die Merkmale/Werte %s fehlen im Ziel"
                                % ", ".join("(%s/%s)" % (_id, value)
                                            for (_id, value) in invalid))
        # TODO: add an option to raise an error if we have missing positions?
        components = AssemblyComponent.KeywordQuery(baugruppe=to_teilenummer,
                                                    b_index=to_t_index)
        valid_positions = set([(c.teilenummer, c.t_index, c.position)
                               for c in components])
        for bm in BOMMapping.KeywordQuery(vpm_product_object_id=from_product_id,
                                          baugruppe=from_teilenummer,
                                          b_index=from_t_index):
            if (bm.teilenummer, bm.t_index, bm.position) in valid_positions:
                bm.Copy(vpm_product_object_id=to_product_id,
                        baugruppe=to_teilenummer,
                        b_index=to_t_index)
        for pred in BOM_Predicate.KeywordQuery(product_object_id=from_product_id,
                                               baugruppe=from_teilenummer,
                                               b_index=from_t_index):
            if (pred.teilenummer, pred.t_index, pred.position) in valid_positions:
                new_pred = pred.Copy(product_object_id=to_product_id,
                                     baugruppe=to_teilenummer,
                                     b_index=to_t_index)
                if hasattr(pred, "Terms"):
                    for term in pred.Terms:
                        term.Copy(product_object_id=to_product_id,
                                  baugruppe=to_teilenummer,
                                  b_index=to_t_index)
                new_pred.update_info_txt()

    def _get_max_bom_item(self, ctx):
        if "maxbom_oid" in ctx.sys_args.get_attribute_names():
            return ByID(ctx.sys_args.maxbom_oid)
        else:
            items = self.ToplevelAssemblies
            if not items:
                raise ue.Exception("cdbvp_err_no_max_bom",
                                   self.code)
            elif len(items) > 1:
                (item,) = [i for i in items
                           if i.teilenummer == ctx.dialog.max_bom_teilenummer
                           and i.t_index == ctx.dialog.max_bom_t_index]
                return item
            else:
                return items[0]

    def update_variant_texts(self):
        for v in self.Variants:
            v.updateInfoText()

    def keep_attributes(self, ctx):
        ctx.keep("filter_id", ctx.dialog.filter_id)

    def set_max_bom(self, ctx):
        skipped = False
        if "maxbom_oid" in ctx.sys_args.get_attribute_names():
            skipped = True
            ctx.skip_dialog()
        else:
            l = len(self.ToplevelAssemblyLinks)
            if l == 0:
                raise ue.Exception("cdbvp_err_no_max_bom",
                                   self.code)
            elif l == 1:
                skipped = True
                ctx.skip_dialog()
        return skipped

    @sig.connect(Product, "cdbvp_filtered_bom", "pre_mask")
    def cdbvp_filtered_bom_pre_mask(self, ctx):
        self.set_max_bom(ctx)
        self.keep_attributes(ctx)

    def filter_bom(self, ctx):
        """ Show the BOM structure filtered by a virtual variant.
        """
        max_bom_item = self._get_max_bom_item(ctx)
        # see cdb._ctx.cdbstructure.Context.setFilter
        predef = [("cdb::argument.stlactivefilter", ctx.ue_args.filter_id),
                  ("cdb::argument.stlactivefiltermodule", "cs.vp.variants.filter.VirtualVariantFilter")]

        filter_name = str(util.ErrorMessage("cdbvp_product_struct_filter_name", self.code))
        predef.append(("cdb::argument.filter_name", filter_name))

        ctx.set_followUpOperation("CDB_ProductStructure",
                                  predefined=predef,
                                  op_object=max_bom_item)

    # threed support
    @staticmethod
    def multiple_eval(baugruppe, b_index, teilenummer, t_index, variante,
                      position, filters, nconditions=None):
        """
        Apply an arbitrary number of filters to a single BOM position.
        More efficient than a sequence of calls to BOMFilter.eval

        :param filters: A list of BOMFilter objects

        :return: A dictionary which has the object of filters as keys,
                 and values True if the position should be included
                 in the result, according to the filter,
                 and False otherwise.
        """
        result = {fltr: True for fltr in filters}

        def eval_single_property_based():
            bom_properties = bomlinks.BOMMapping.KeywordQuery(baugruppe=baugruppe,
                                                     b_index=b_index,
                                                     teilenummer=teilenummer,
                                                     variante=variante,
                                                     position=position)
            if bom_properties:
                for fltr in filters:
                    for prop in bom_properties:
                        if prop.vpm_product_object_id in fltr.product_object_ids:
                            test = (int(prop.property_id), int(prop.property_value))
                            if test not in fltr.prop_dict.items():
                                result[fltr] = False
                                break

        def eval_predicate_based():
            bom_predicates = bomlinks.BOM_Predicate.KeywordQuery(
                baugruppe=baugruppe,
                b_index=b_index,
                teilenummer=teilenummer,
                variante=variante,
                position=position
            )
            if bom_predicates:
                for fltr in filters:
                    if not any(pred.eval(fltr.prop_dict)
                               for pred in bom_predicates
                               if pred.product_object_id in fltr.product_object_ids):
                        result[fltr] = False

        # If there are no condition on the node, we don't need to check
        # anything
        if not nconditions or nconditions[(baugruppe, b_index, teilenummer,
                                           t_index, variante, position)][0] > 0:
            if get_maxbom_rating_method() == kMaxBOMRatingMethodSingleProperty:
                eval_single_property_based()
            elif get_maxbom_rating_method() == kMaxBOMRatingMethodPredicateBased:
                eval_predicate_based()
        return result

    # threed support
    def get_filter_for_signature(self, signature):
        """
        Retrieve bom filter and hash for signature

        :param signature: variability signature
        :type signature: basestring

        :return: tuple first element is the filter object and second the hash for the signature
                 the filter object needs to have the function:
                    eval(self, baugruppe, b_index, teilenummer, t_index, variante, position, occurrence_id=None, assembly_path=None)
                            Apply filter to BOM position

                            :return: True if the position should be included and False otherwise
        """
        return VirtualVariantBOMFilter(self.cdb_object_id, signature), signature

    @sig.connect(Product, "cdbvp_filtered_bom", "now")
    def cdbvp_filtered_bom_now(self, ctx):
        self.filter_bom(ctx)

    def update_bom_predicate_texts(self):
        for pred in self.BOM_Predicates:
            pred.update_info_txt()

    @sig.connect(Product, "relship_copy", "post")
    def _vpvariants_relship_copy_post(self, ctx):
        if ctx.relationship_name == "cdbvp_product2all_properties":
            self.update_bom_predicate_texts()

    @sig.connect(Product, "modify", "post")
    def _vpvariants_modify_post(self, ctx):
        if "code" in ctx.ue_args.get_attribute_names() and ctx.ue_args.code != self.code:
            self.update_bom_predicate_texts()

    @sig.connect(Product, "copy", "post")
    def _vpvariants_copy_post(self, ctx):
        if not ctx.error:
            old = Product.ByKeys(ctx.cdbtemplate.cdb_object_id)
            self.copy_max_boms_from(old)

    def update_solver_stati(self, constraints=[]):
        from cs.vp.variants.vpmsolvers import BasicVPMSolver

        # Update product variants
        solver = BasicVPMSolver(self, self.VariantDrivingProperties)

        for variant in self.Variants:
            variant.update_solver_status(solver, constraints)

        # Update view variants
        for view in self.Views:
            view_props = list(view.VariantDrivingProperties)
            solver = BasicVPMSolver(self,
                                    view_props + list(self.VariantDrivingProperties),
                                    view_props)
            for variant in view.Variants:
                variant.update_solver_status(solver, constraints)

        # Update properties
        for prop in self.AllProperties:
            if prop.PropertyDependencies:
                prop.update_value_stati()

    def on_cdbvp_variant_matrix_now(self, ctx):
        url = "/byname/variant_matrix/{product_object_id}/"\
            .format(product_object_id=self.cdb_object_id)
        return ue.Url4Context(url)
