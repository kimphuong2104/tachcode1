#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module cs.vp.variants.items

This is the documentation for the cs.vp.variants.items module.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants
from cdb import sig
from cdb import ue
from cdb.classbody import classbody
from cdb.objects import Forward
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import Reference_N
from cdb.objects import operations
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cs.vp.bom import AssemblyComponent
from cs.vp.items import Item
from cs.vp.variants import filter as Filter

fBOMMapping = Forward("cs.vp.variants.bomlinks.BOMMapping")
fBOM_Predicate = Forward("cs.vp.variants.bomlinks.BOM_Predicate")
fBOMTerm = Forward("cs.vp.variants.bomlinks.BOM_Term")
fProduct = Forward("cs.vp.products.Product")
fProductAssemblyLink = Forward("cs.vp.variants.product_extensions.ProductAssemblyLink")
fVariant2Part = Forward("cs.vp.variants.Variant2Part")
fVariant = Forward("cs.vp.variants.Variant")
fItem = Forward("cs.vp.items.Item")


@classbody
class Item(object):

    ProductLinks = Reference_N(
        fProductAssemblyLink,
        fProductAssemblyLink.teilenummer == Item.teilenummer,
        fProductAssemblyLink.t_index == Item.t_index)

    def _get_products(self):
        result = [link.Product for link in self.ProductLinks]
        return result
    Products = ReferenceMethods_N(fProduct, _get_products)

    VariantLinks = Reference_N(fVariant2Part,
                               fVariant2Part.teilenummer == Item.teilenummer,
                               fVariant2Part.t_index == Item.t_index)

    def _getVariant(self):
        var_links = self.VariantLinks
        if var_links:
            return var_links[0].Variant
        return None
    Variant = ReferenceMethods_1(fVariant, _getVariant)

    def _getMaxBOM(self):
        var_links = self.VariantLinks
        if var_links:
            return var_links[0].MaxBOM
        return None
    MaxBOM = ReferenceMethods_1(fItem, _getMaxBOM)

    def _getInstantiationProduct(self):
        if self.Variant:
            return self.Variant.Product
        else:
            return None
    InstantiationProduct = ReferenceMethods_1(fProduct, _getInstantiationProduct)

    def _getInstantiations(self):
        variant_links = fVariant2Part.KeywordQuery(max_bom_teilenummer=self.teilenummer,
                                                   max_bom_t_index=self.t_index)
        return Item.Query(Item.cdb_object_id.one_of(*[
            link.Part.cdb_object_id for link in variant_links if link.Part
        ]))
    Instantiations = ReferenceMethods_N(fItem, _getInstantiations)

    def copy_bom_conditions(self, ctx):
        """ Copy the conditions that belong either to VPMs for which a link has
            just been created, or that belong to "unrelated" VPMs (this happens,
            if the item is part of a "deeply configured" structure).
            This is done here in relship_copy-post, so that the BOM items are
            already in place.
        """
        if (ctx.error
                or ctx.relationship_name != 'CDB::Relationship::STL::part2bom_item'):
            return
        old_item = Item.ByKeys(ctx.cdbtemplate.teilenummer,
                               ctx.cdbtemplate.t_index)
        # Copy BOM conditions only for VPMs the new item ist associated with.
        rating_method = Filter.get_maxbom_rating_method()
        if rating_method == Filter.kMaxBOMRatingMethodSingleProperty:
            bom_ratings = fBOMMapping.KeywordQuery(baugruppe=old_item.teilenummer,
                                                   b_index=old_item.t_index)
            if bom_ratings:
                copy_prod_ids = set(self.ProductLinks.product_object_id)
                if not copy_prod_ids:
                    # configured sub component without own product assignment.
                    copy_prod_ids = set(bom_ratings.vpm_product_object_id)
                for bm in bom_ratings:
                    if bm.vpm_product_object_id in copy_prod_ids:
                        bm.Copy(baugruppe=self.teilenummer,
                                b_index=self.t_index)
        elif rating_method == Filter.kMaxBOMRatingMethodPredicateBased:
            bom_predicates = fBOM_Predicate.KeywordQuery(baugruppe=old_item.teilenummer,
                                                         b_index=old_item.t_index)
            if bom_predicates:
                copy_prod_ids = set(self.ProductLinks.product_object_id)
                if not copy_prod_ids:
                    # configured sub component without own product assignment.
                    copy_prod_ids = set(bom_predicates.product_object_id)
                for pred in bom_predicates:
                    if pred.product_object_id in copy_prod_ids:
                        pred.CopyWithChangeLog(baugruppe=self.teilenummer,
                                               b_index=self.t_index)
                        if hasattr(pred, "Terms"):
                            for term in pred.Terms:
                                term.CopyWithChangeLog(baugruppe=self.teilenummer,
                                                       b_index=self.t_index)
        # Set position types for my BOM positions. These may differ from the
        # template, as not all BOM conditions may have been copied.
        for c in self.Components:
            c.set_position_type()

    @sig.connect(Item, "relship_copy", "post")
    def _vpvariants_relship_copy_post(self, ctx):
        self.copy_bom_conditions(ctx)

    def keep_product_links(self, ctx):
        links = self.ProductLinks.product_object_id
        if links:
            ctx.keep("cdbvp_old_product_ids", '@'.join(links))

    @sig.connect(Item, "delete", "pre")
    def _vpvariants_delete_pre(self, ctx):
        self.keep_product_links(ctx)

    def copy_variant_associations(self, ctx):
        if not ctx.error:
            for var_link in fVariant2Part.KeywordQuery(teilenummer=ctx.cdbtemplate.teilenummer,
                                                       t_index=ctx.cdbtemplate.t_index):
                var_link.Copy(teilenummer=self.teilenummer,
                              t_index=self.t_index)

    @sig.connect(Item, "index", "post")
    def _vpvariants_index_post(self, ctx):
        self.copy_variant_associations(ctx)

    def _is_configurable_item(self, checked_items):
        """ Test if the Item is configurable - meaning the BOM of the item or
            one of its subcomponents has a condition attached.
            checked_items is a cache with (teilenummer, t_index) tuples of
            items that are already known to be not configurable (there is no
            need for a cache of configurable items, as the first one detected
            will directly jump out).
            THINKABOUT: check product associations instead (or additionally)?
                        check "configurable" flag only?
        """
        components = self.Components
        # direct BOM items
        for comp in components:
            if comp.VPMProperties or comp.VPMPredicates:
                return True
        # sub-parts
        for comp in components:
            if (comp.teilenummer, comp.t_index) in checked_items:
                pass  # already seen
            elif comp.Item._is_configurable_item(checked_items):
                return True
        # OK, we are clean
        checked_items.add((self.teilenummer, self.t_index))
        return False

    def has_configurable_parts(self):
        checked_items = set()
        for comp in self.Components:
            if comp.Item._is_configurable_item(checked_items):
                return True
        return False

    def create_variant_association(self, ctx):
        """ If the create operation was a followup operation from
            "cdbvp_instantiate_max_bom", record the variant association, and
            filter the MaxBOM entries and add them to the new part.
        """
        if (ctx.error
            or ("cdbvp_instantiate_variant"
                not in ctx.ue_args.get_attribute_names())):
            return
        max_bom_item = Item.ByKeys(ctx.cdbtemplate.teilenummer,
                                   ctx.cdbtemplate.t_index)
        # record variant-to-part mapping
        from cs.vp.variants import Variant2Part
        Variant2Part.Create(variant_id=ctx.ue_args.variant_id,
                            product_object_id=ctx.ue_args.product_object_id,
                            teilenummer=self.teilenummer,
                            t_index=self.t_index,
                            max_bom_teilenummer=max_bom_item.teilenummer,
                            max_bom_t_index=max_bom_item.t_index)

    @sig.connect(Item, "create", "post")
    def _vpvariants_create_post(self, ctx):
        self.create_variant_association(ctx)

    @sig.connect(Item, "cdbvp_show_bom_item", "now")
    def cdbvp_show_bom_item_now(self, ctx):
        """ Opens the ProductStructure and expands the structure
        to a specified bom item. The bom item to be shown is defined by
        ctx.sys_args.occurence_id  """

        if "occurence_id" not in ctx.sys_args.get_attribute_names():
            raise ue.Exception("cdbvp_occurence_missing")

        occurence_id = ctx.sys_args.occurence_id
        if occurence_id:
            # Get bom item object by occurence_id
            target_object = AssemblyComponent.ByKeys(baugruppe=self.teilenummer,
                                                     b_index=self.t_index,
                                                     occurence_id=occurence_id)
            if target_object:
                target_object_handle = target_object.ToObjectHandle()
                obscure_id_string = target_object_handle.get_object_id()
                kwargs = {
                    "cdb::argument.expanduntilobjectfound": obscure_id_string
                    }
                ctx.url(self.MakeURL("CDB_ProductStructure", **kwargs))
            else:
                raise ue.Exception("cdbvp_occurence_id_does_not_exists", occurence_id)
        else:
            raise ue.Exception("cdbvp_occurence_id_empty")

    @sig.connect(Item, "CDB_ProductStructure", "now")
    def CDB_ProductStructure_now(self, ctx):
        if ctx.action_object_id:
            if "expanduntilobjectfound" in ctx.sys_args.get_attribute_names():
                ctx.expandStructAndSelectObject(ctx.sys_args.expanduntilobjectfound)

    @sig.connect(Item, "cdbvp_filtered_bom", "now")
    def cdbvp_filtered_bom_now(self, ctx):
        """ Assuming this item is an instantiation associated with a variant,
            show the BOM structure filtered by that variant.
        """
        var_links = list(self.VariantLinks)
        if len(var_links) == 0:
            raise ue.Exception("cdbvp_err_no_variant")
        variant = var_links[0].Variant
        max_bom = var_links[0].MaxBOM
        variant.get_filter_variant().show_filtered_bom(max_bom, ctx)

    def delete_bom_links(self, ctx):
        if (not ctx.error
                and "cdbvp_old_product_ids" in ctx.ue_args.get_attribute_names()):
            # extract product ids from string
            product_ids = ctx.ue_args.cdbvp_old_product_ids.split('@')
            for prod_id in product_ids:
                product = fProduct.ByKeys(prod_id)
                if product is not None:
                    product.delete_unreachable_bom_links()

    def delete_variant_associations(self, ctx):
        """ Delete the associations from variants to deleted parts.
        """
        if not ctx.error:
            v2p = fVariant2Part.KeywordQuery(teilenummer=self.teilenummer,
                                             t_index=self.t_index)
            v2p.Delete()

    @sig.connect(Item, "delete", "post")
    def _vpvariants_delete_post(self, ctx):
        self.delete_bom_links(ctx)
        self.delete_variant_associations(ctx)

    def instantiate_bom(self, variant, data=None, instance=None):
        """
        Instantiate the article according to a variant.

        The BOM will be copied. The parameter `data` contains the choices made
        in the instantiation wizard. It tells for each variable subassembly if
        it has to be instantiated or replaced with an already instantiated bom.
        """

        if data is None:
            data = {}

        from cs.vp.variants import filter as bom_filters
        bom_filter = bom_filters.VariantBOMFilter(variant.product_object_id, variant.id)

        def create_instance(item):
            args = {
                "teilenummer": "#",
                "t_index": "",
                "configurable": 0,
                "materialnr_erp": "",  # FIXME: compute it if item is an mbom
            }

            # FIXME: make description configurable
            for fd in Item.i18n_benennung.getLanguageFields().values():
                name = "%s (%s)" % (
                    item[fd.name],
                    variant.name if variant.name else "%d" % variant.id
                )
                # ensure to limit to field length
                args[fd.name] = name[:fd.length]

            instance = operations.operation(constants.kOperationCopy, item, **args)

            # record variant-to-part mapping
            from cs.vp.variants import Variant2Part
            Variant2Part.Create(variant_id=variant.id,
                                product_object_id=variant.product_object_id,
                                teilenummer=instance.teilenummer,
                                t_index=instance.t_index,
                                max_bom_teilenummer=item.teilenummer,
                                max_bom_t_index=item.t_index)
            return instance

        def replace_instance(maxbom, instance):
            # reinstantiate item: we want to replace the instantiated assembly components
            # with copies of the maxbom components, so that instances.Components
            # is a copy of maxbom.Components

            # delete the instantiated assembly components
            for comp in instance.Components:
                if not [
                    maxcomp
                    for maxcomp in maxbom.Components
                    if maxcomp.position == comp.position
                    and maxcomp.teilenummer == comp.teilenummer
                    and maxcomp.t_index == comp.t_index
                    and maxcomp.variante == comp.variante
                ]:
                    operations.operation(constants.kOperationDelete, comp)

            # replace the missing maxbom components
            for comp in maxbom.Components:
                if not [
                    instcomp
                    for instcomp in instance.Components
                    if instcomp.position == comp.position
                    and instcomp.teilenummer == comp.teilenummer
                    and instcomp.t_index == comp.t_index
                    and instcomp.variante == comp.variante
                ]:
                    new_comp = operations.operation(
                        constants.kOperationCopy,
                        comp,
                        baugruppe=instance.teilenummer,
                        b_index=instance.t_index,
                        position=comp.position
                    )
                    assert new_comp.position == comp.position

            chctrl = Item.MakeChangeControlAttributes()
            del chctrl["cdb_cdate"]
            del chctrl["cdb_cpersno"]

            instance.Update(**chctrl)
            instance.Reload()

        def replace(comp, instance, data):
            # preconditions: len(el["path"]) > 0 && el["path"][0] == comp
            # forall el in data

            if instance == "NEW":
                instance = comp.Item.instantiate_bom(variant, [
                    {
                        "instance": el["instance"],
                        "path": el["path"][1:]
                    }
                    for el in data
                ])

            result = operations.operation(
                constants.kOperationCopy, comp,
                teilenummer=instance.teilenummer,
                t_index=instance.t_index
            )
            operations.operation(constants.kOperationDelete, comp)
            return instance

        if instance is None:
            instance = create_instance(self)
        else:
            replace_instance(self, instance)

        for comp in instance.Components:
            # delete bom predicates on instantiated components
            comp.VPMProperties.Delete()
            comp.VPMPredicates.Delete()
            comp.VPMTerms.Delete()

            if bom_filter.eval(
                self.teilenummer, self.t_index, comp.teilenummer,
                comp.t_index, comp.variante, comp.position
            ):
                def _cmp(lhs, rhs):
                    return all((
                        getattr(lhs, attr) == getattr(rhs, attr)
                        for attr in ["teilenummer", "t_index", "position", "variante", "auswahlmenge"]
                    ))

                _data = [x for x in data if len(x.get("path", [])) > 0 and _cmp(x["path"][0], comp)]
                if len(_data) > 0:
                    _instances = [el["instance"] for el in _data if len(el["path"]) == 1]
                    replace(comp, _instances[0] if _instances else "NEW", _data)
            else:
                operations.operation(constants.kOperationDelete, comp)

        instance.Reload()
        return instance

    def on_cdbvp_reinstantiate_part_now(self, ctx):
        if self.MaxBOM is None or self.Variant is None:
            raise ue.Exception("cdbvp_err_no_variant")

        # only allow this operation if the user has enough access rights on the object
        for necessary_right in ["save", "delete_bom", "create_bom"]:
            if not self.CheckAccess(necessary_right):
                raise ue.Exception("cdbvp_no_variant_mgr_inst")

        url = (
            "/byname/instance_wizard/"
            "{product_object_id}/"
            "{variant_id}/"
            "{max_bom_teilenummer}"
        ).format(
            product_object_id=self.Variant.product_object_id,
            variant_id=self.Variant.id,
            max_bom_teilenummer=self.MaxBOM.teilenummer
        )

        if self.MaxBOM.t_index is not None:
            url += '/%s' % self.MaxBOM.t_index

        url += '/instance/%s' % self.cdb_object_id

        return ue.Url4Context(url)


@classbody
class AssemblyComponent(object):

    VPMProperties = Reference_N(fBOMMapping,
                                fBOMMapping.baugruppe == AssemblyComponent.baugruppe,
                                fBOMMapping.b_index == AssemblyComponent.b_index,
                                fBOMMapping.teilenummer == AssemblyComponent.teilenummer,
                                fBOMMapping.variante == AssemblyComponent.variante,
                                fBOMMapping.position == AssemblyComponent.position)

    VPMPredicates = Reference_N(fBOM_Predicate,
                                fBOM_Predicate.baugruppe == AssemblyComponent.baugruppe,
                                fBOM_Predicate.b_index == AssemblyComponent.b_index,
                                fBOM_Predicate.teilenummer == AssemblyComponent.teilenummer,
                                fBOM_Predicate.variante == AssemblyComponent.variante,
                                fBOM_Predicate.position == AssemblyComponent.position)

    VPMTerms = Reference_N(
        fBOMTerm,
        fBOMTerm.baugruppe == AssemblyComponent.baugruppe,
        fBOMTerm.b_index == AssemblyComponent.b_index,
        fBOMTerm.teilenummer == AssemblyComponent.teilenummer,
        fBOMTerm.variante == AssemblyComponent.variante,
        fBOMTerm.position == AssemblyComponent.position
    )

    def find_possible_alternatives(self):
        """ Return BOM postions with the same position number as this one, that
            are to be treated as alternative positions.
        """
        return AssemblyComponent.KeywordQuery(baugruppe=self.baugruppe,
                                              b_index=self.b_index,
                                              position=self.position)

    def set_position_type(self, ctx=None):
        def _set_pos_type(pos, postype, has_condition):
            if ((pos.cdbvp_positionstyp != postype)
                    or (pos.cdbvp_has_condition != has_condition)):
                pos.Update(cdbvp_positionstyp=postype,
                           cdbvp_has_condition=has_condition)
        # ---
        if ctx is None or not ctx.error:
            alternatives = [a for a in self.find_possible_alternatives()]
            if len(alternatives) == 1:
                a = alternatives[0]
                if a.VPMProperties or a.VPMPredicates:
                    _set_pos_type(a, 'option', 1)
                else:
                    _set_pos_type(a, 'position', 0)
            else:
                for a in alternatives:
                    cond = 1 if (a.VPMProperties or a.VPMPredicates) else 0
                    _set_pos_type(a, 'alternative', cond)

    @sig.connect(AssemblyComponent, "create", "post")
    @sig.connect(AssemblyComponent, "delete", "post")
    def _vpvariants_set_position_type(self, ctx=None):
        self.set_position_type(ctx)

    def set_sap_condition_text(self, ctx):
        ctx.set("sap_condition_text",
                fBOM_Predicate.combined_sap_condition(self.VPMPredicates))
        ctx.disable_cancel()
        ctx.set_button_label(ctx.kButtonLabelOK, "ok")

    @sig.connect(AssemblyComponent, "cdbvp_show_sap_condition", "pre_mask")
    def _vpvariants_show_sap_condition(self, ctx):
        self.set_sap_condition_text(ctx)


class ProductBrowser(CDBCatalog):

    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        if self.getInvokingField():
            self.teilenummer = self.getInvokingDlgValue("teilenummer")
            self.t_index = self.getInvokingDlgValue("t_index")
            self.browserdata = ProductBrowserData(self, self.teilenummer, self.t_index)
            self.setResultData(self.browserdata)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            sel_item = self.browserdata.products[selected_rows[0]]
            self.setValue("product_object_id", sel_item.cdb_object_id)


class ProductBrowserData(CDBCatalogContent):

    def __init__(self, catalog, teilenummer, t_index):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.products = Item.ByKeys(teilenummer, t_index).Products

    def getNumberOfRows(self):
        return len(self.products)

    def getRowObject(self, row):
        return self.products[row].ToObjectHandle()
