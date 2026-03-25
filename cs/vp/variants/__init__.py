#!/usr/bin/env python
# -*- python; coding: utf-8 -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved

from collections import defaultdict

from cdbwrapc import Operation

from cdb import constants
from cdb import i18n
from cdb import ue
from cdb import util
from cdb.util import check_access, ErrorMessage
from cdb import sqlapi
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Forward
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_N
from cdb.objects import LocalizedField
from cdb.objects import ByID
from cdb.objects import operations
from cs.vp.items import Item
from cdb.platform import mom
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cs.tools.powerreports import WithPowerReports

from cs.vp.variants.properties import EnumDefinition
from cs.vp.variants.properties import Property
from cs.vp.variants.properties import PropertyValue
from cs.vp.variants import constraints as Constraints
from cs.vp.variants.util import VariantInfoTextGenerator

fProduct = Forward("cs.vp.products.Product")
fProductAssemblyLink = Forward("cs.vp.variants.product_extensions.ProductAssemblyLink")
fProductView = Forward("cs.vp.variants.productviews.ProductView")
fProperty = Forward("cs.vp.variants.properties.Property")
fPropertyValue = Forward("cs.vp.variants.properties.PropertyValue")
fVariant = Forward(__name__ + ".Variant")
fVariant2Part = Forward(__name__ + ".Variant2Part")
fVariantMapping = Forward(__name__ + ".VariantMapping")
fConstraint = Forward("cs.vp.variants.constraints.Constraint")
fLinkToViolatedConstraints = Forward(__name__ + ".LinkToViolatedConstraint")

from cs.vp.variants.solvers import BasicProblemSolver

from cs.vp.variants.vptools import WithChangeLog


class Variant(Object, WithPowerReports, WithChangeLog):
    __maps_to__ = "cdbvp_variant"
    __classname__ = "cdbvp_variant"

    PropertyValues = Reference_N(fPropertyValue,
                                 fPropertyValue.product_object_id == fVariant.product_object_id,
                                 fPropertyValue.variant_id == fVariant.id)

    View = Reference_1(fProductView,
                       fProductView.id == fVariant.view_id,
                       fProductView.product_object_id == fVariant.product_object_id)

    Product = Reference_1(fProduct,
                          fProduct.cdb_object_id == fVariant.product_object_id)

    PartsRefs = Reference_N(fVariant2Part,
                            fVariant2Part.product_object_id == fVariant.product_object_id,
                            fVariant2Part.variant_id == fVariant.id)

    LinksToViolatedConstraints = Reference_N(fLinkToViolatedConstraints,
                                             fLinkToViolatedConstraints.product_object_id == fVariant.product_object_id,
                                             fLinkToViolatedConstraints.variant_id == fVariant.id)

    InfoTxt = LocalizedField("cdbvp_variant_info_txt")

    def _parts(self):
        # [ref.Part for ref in self.PartsRefs] intentionally not
        # used for performance reasons (one additional db select per part)
        return Item.SQL("select a.* from teile_stamm a, cdbvp_variant2part b "
                        "where a.teilenummer=b.teilenummer and a.t_index = b.t_index "
                        "and b.variant_id = '%s' and b.product_object_id = '%s'" %
                        (self.id, self.product_object_id))
    Parts = ReferenceMethods_N(Item, _parts)

    def mapToView(self, target_view_id):
        """ Maps self to the corresponding variant(s) within the specified
            view_id. If target_view_id is None or 0, map to a variant without
            a view (ie. one that is attached directly to the product).
            Returns a (possibly empty) set of all mapped variants.
            Must be overwritten in subclasses.
        """
        raise NotImplementedError()

    def get_max_bom_variants(self):
        """ Return a list of variants, that are mapped to this one, and can be
            used to filter the MaxBOM.
        """
        max_bom_view = self.Product.MaxBOMView
        if max_bom_view is None:
            max_bom_variants = self.mapToView(None)
        else:
            max_bom_variants = self.mapToView(max_bom_view.id)
        return list(max_bom_variants)

    def getInfoText(self, lang):
        return VariantInfoTextGenerator().get_variant_info_string(self, lang)

    def updateInfoText(self, clear_generator_cache=True):
        info_texts = {}
        for lang in self.InfoTxt.keys():
            info_texts[lang] = self.getInfoText(lang)
        info_texts_for_db = {Variant.InfoTxt[lang].name: info_text for lang, info_text in info_texts.items()}
        self.Update(**info_texts_for_db)
        if clear_generator_cache:
            VariantInfoTextGenerator().clear_cache()

    @classmethod
    def NewVariantID(cls, product_object_id):
        new_id = 1
        t = sqlapi.SQLselect("max(id) from cdbvp_variant where product_object_id = '%s'" % product_object_id)
        if sqlapi.SQLstring(t, 0, 0) != "":
            new_id = sqlapi.SQLinteger(t, 0, 0) + 1
        return new_id

    @classmethod
    def CreateVariant(cls, props, product_object_id, clear_generator_cache=True, **kwargs):
        """ Create a variant given its property evaluations

            :param props: A dictionary containing the property evaluations.
                The keys are the ids of the properties. The values can be
                True (option on), False (option off) or the id of a property
                value. The dictionary does not have to contain all of the
                product properties.
            :param product_object_id: The cdb_object_id of the product.
            :param clear_generator_cache: When set to false, the cache that is used
                to construct the info text for the created variant is not emptied.
                When this is the case, `VariantInfoTextGenerator().clear_cache()`
                must be called explicitly to avoid keeping outdated information
                in this cache.
        """
        # check if variant already exists (E045638)
        signature = BasicProblemSolver.getSolutionSignature(list(props.items()))
        if Variant.KeywordQuery(product_object_id=product_object_id, signature=signature):
            raise ErrorMessage("cdbvp_variant_already_exists")

        kwargs["product_object_id"] = product_object_id
        if "id" not in kwargs:
            kwargs["id"] = cls.NewVariantID(product_object_id)
        variant = operations.operation(constants.kOperationNew, cls.__classname__, **kwargs)

        for prop_id, value_id in props.items():
            if value_id is True or value_id is False:
                value = None
                disabled = int(value_id is False)
            else:
                value = value_id
                disabled = 0

            fPropertyValue\
                .CreateWithChangeLog(product_object_id=product_object_id,
                                     variant_id=variant.id,
                                     id=prop_id,
                                     value=value,
                                     disabled=disabled)
        variant.updateInfoText(clear_generator_cache=clear_generator_cache)
        variant.updateSignature()

        # For variants being created in the variant editor the solver status has
        # already been computed. So there's no need to do it again
        if "solver_status" not in kwargs:
            variant.update_solver_status(force=True)

        return variant

    def preset_id(self, ctx):
        self.id = self.NewVariantID(self.product_object_id)

    def updateSignature(self):
        prop_values = (
            (
                pv.id,
                pv.get_value()
            ) for pv in self.PropertyValues
        )
        signature = BasicProblemSolver.getSolutionSignature(prop_values)
        if self.signature != signature:
            self.signature = signature

    @classmethod
    def BySignature(cls, product_object_id, signature):
        variants = cls.KeywordQuery(product_object_id=product_object_id, signature=signature)
        if variants:
            return variants[0]
        else:
            return None

    # --------------- Pager API --------------

    def get_property_values(self):
        return BasicProblemSolver.parseSolutionSignature(self.signature)

    def match(self, presettings):
        result = True
        prop_values = self.get_property_values()
        for prop_id, value in presettings.items():
            if prop_id not in prop_values or value != prop_values[prop_id]:
                result = False
                break
        return result

    # ----------------------------------------

    def _preselect_max_bom_dlg(self, ctx):
        if ("maxbom_oid" in ctx.sys_args.get_attribute_names() or
                len(self.Product.UsableToplevelAssemblies) == 1):
            maxbom = self._get_max_bom_item(ctx)
            ctx.set("max_bom_teilenummer", maxbom.teilenummer)
            ctx.set("max_bom_t_index", maxbom.t_index)

    def _select_max_bom_dlg(self, ctx):
        skipped = False
        if "maxbom_oid" in ctx.sys_args.get_attribute_names():
            skipped = True
            ctx.skip_dialog()
        else:
            cnt = len(self.Product.UsableToplevelAssemblies)
            if cnt == 0:
                raise ue.Exception("cdbvp_err_no_max_bom",
                                   self.Product.code)
            elif cnt == 1:
                skipped = True
                ctx.skip_dialog()
        return skipped

    def _validate_max_bom_dlg(self, ctx):
        maxbom = self._get_max_bom_item(ctx)
        is_valid = any((
            candidate.teilenummer == maxbom.teilenummer and candidate.t_index == maxbom.t_index
            for candidate in self.Product.UsableToplevelAssemblies
        ))

        answer_ok = (
            "question_maxbom_invalid" in ctx.dialog.get_attribute_names() and
            ctx.dialog["question_maxbom_invalid"] == ctx.MessageBox.kMsgBoxResultYes
        )

        if not is_valid and not answer_ok:
            msgbox = ctx.MessageBox(
                "cdbvp_invalid_maxbom_selected", [],
                "question_maxbom_invalid", ctx.MessageBox.kMsgBoxIconQuestion
            )
            msgbox.addYesButton(1)
            msgbox.addCancelButton()
            ctx.show_message(msgbox)

    def _get_max_bom_item(self, ctx):
        maxbom = None

        if "maxbom_oid" in ctx.sys_args.get_attribute_names():
            return ByID(ctx.sys_args.maxbom_oid)
        elif set(["max_bom_teilenummer", "max_bom_t_index"]) <= set(ctx.dialog.get_attribute_names()):
            # It is possible to select an outdated maxbom in the dialog.
            # This is ok if the user does it explicitly,
            # but we shouldn't select them automatically.
            maxbom = Item.ByKeys(
                teilenummer=ctx.dialog.max_bom_teilenummer,
                t_index=ctx.dialog.max_bom_t_index
            )

        if maxbom is not None:  # FIXME: check if maxbom is assigned to the product
            return maxbom
        else:
            candidates = self.Product.UsableToplevelAssemblies
            if not candidates:
                raise ue.Exception("cdbvp_err_no_max_bom", self.Product.code)
            return candidates[0]

    def on_cdbvp_instantiate_max_bom_now(self, ctx):
        """ Create a new item from the MaxBOM item, by filtering the BOM entries
            with this variants property values.
        """
        max_bom_item = self._get_max_bom_item(ctx)

        if getattr(ctx.dialog, "persistent_bom", "0") == "1":
            return self._instantiate_wizard(max_bom_item)
        else:
            return self._instantiate(ctx, max_bom_item)

    def _instantiate(self, ctx, max_bom_item):
        cdef = max_bom_item.GetClassDef()
        ueargs = [("cdbvp_instantiate_variant", "1"),
                  ("variant_id", self.id),
                  ("product_object_id", self.product_object_id)]
        predef = {}
        predef_args = cdef.getPredefinedOpArgs("CDB_Create", True)
        for arg in predef_args:
            predef[arg.name] = arg.value
        dont_copy = set(["teilenummer", "t_index", "cdb_object_id",
                         "cdb_cdate", "cdb_mdate",
                         "cdb_cpersno", "cdb_mpersno",
                         "status", "cdb_status_txt"
                         "materialnr_erp", "benennung", "configurable"])
        predef.update([(k, v) for k, v in max_bom_item.items()
                       if k not in dont_copy and v is not sqlapi.NULL])
        predef["benennung"] = ("%s (%s)"
                               % (max_bom_item.benennung,
                                  self.name if self.name else "%d" % (self.id)))
        predef["configurable"] = "0"

        # op_object must be set to get the correct class for the operation!
        ctx.set_followUpOperation(opname="CDB_Create",
                                  opargs=ueargs,
                                  predefined=list(predef.items()),
                                  op_object=max_bom_item,
                                  tmpl_object=max_bom_item)

    def _instantiate_wizard(self, maxbom):
        url = (
            "/byname/instance_wizard/"
            "{product_object_id}/"
            "{variant_id}/"
            "{max_bom_teilenummer}"
        ).format(
            product_object_id=self.product_object_id,
            variant_id=self.id,
            max_bom_teilenummer=maxbom.teilenummer
        )

        if maxbom.t_index:
            url += '/%s' % maxbom.t_index

        return ue.Url4Context(url)

    def get_filter_variant(self, ctx=None):
        max_bom_variants = self.get_max_bom_variants()
        if len(max_bom_variants) == 0:
            raise ue.Exception("cdbvp_err_no_mapping")
        elif len(max_bom_variants) > 1:
            raise ue.Exception("cdbvp_err_no_unique_mapping")
        else:
            return max_bom_variants[0]

    def show_filtered_bom(self, max_bom, ctx):
        filter_id = "%s:%s" % (self.product_object_id, self.id)
        # see cdb._ctx.cdbstructure.Context.setFilter
        predef = [("cdb::argument.stlactivefilter", filter_id),
                  ("cdb::argument.filter_name", self.product_struct_filter_name),
                  ("cdb::argument.stlactivefiltermodule", "cs.vp.variants.filter.Filter")]
        ctx.set_followUpOperation("CDB_ProductStructure", predefined=predef, op_object=max_bom)

    def on_cdbvp_filtered_bom_now(self, ctx):
        """ Show the BOM structure filtered by this variant.
        """
        filter_variant = self.get_filter_variant(ctx)
        if filter_variant:
            max_bom_item = self._get_max_bom_item(ctx)
            filter_variant.show_filtered_bom(max_bom_item, ctx)

    def getSignature(self):
        solution = sorted(((pv.id, pv.get_value()) for pv in self.PropertyValues),
                          key=lambda t: t[0])
        return ','.join(("%s:%s" % item for item in solution))

    @classmethod
    def getVariantTextFromSignature(cls, product_object_id, signature, lang=None):
        values = BasicProblemSolver.parseSolutionSignature(signature)
        if lang is None:
            lang = i18n.default()

        result = []
        for prop_id, value in values.items():
            prop = Property.ByKeys(product_object_id=product_object_id, id=prop_id)
            result.append(PropertyValue.get_text(prop, value, lang=lang))
        return ", ".join(result)

    def getSAPPropertyValues(self):
        return dict([(str(pv.Property.erp_id()), str(pv.EnumValue.name))
                     for pv in self.PropertyValues])

    def on_query_catalog_pre_mask(self, ctx):
        if ctx.catalog_name == "cdb_bomflt_head" and not ctx.dialog.teilenummer:
            ctx.set("teilenummer", ctx.catalog_invoking_dialog.teilenummer)
            ctx.set("t_index", ctx.catalog_invoking_dialog.t_index)

            # Produktmodell vorbelegen
            vpm_links = fProductAssemblyLink.KeywordQuery(teilenummer=ctx.catalog_invoking_dialog.teilenummer,
                                                          t_index=ctx.catalog_invoking_dialog.t_index)
            if len(vpm_links) == 1:
                product = vpm_links[0].Product
                ctx.set("product_object_id", product.cdb_object_id)
                ctx.set("product_code", product.code)

                # Letzte verwendete Sicht für das Produkt vorbelegen
                view = None
                if product.cdb_object_id in VariantSearchBrowser.DIALOG_PRESETTINGS:
                    view_id = VariantSearchBrowser.DIALOG_PRESETTINGS[product.cdb_object_id].get("view_id")
                    if view_id:
                        view = fProductView.ByKeys(view_id, product.cdb_object_id)
                else:
                    # MaxBom Sicht vorbelegen, wenn definiert
                    if product.MaxBOMView:
                        view = product.MaxBOMView
                if view:
                    ctx.set("view_id", view.id)
                    ctx.set("view_name", view.Name[''])

    def set_report_mask_attributes(self, ctx):
        ctx.set("product_object_id", self.product_object_id)
        if len(self.Product.MaxBoms) == 1:
            maxbom = self.Product.MaxBoms[0]
            ctx.set("max_bom_teilenummer", maxbom.teilenummer)
            ctx.set("max_bom_t_index", maxbom.t_index)

    def getSolver(self):
        from cs.vp.variants.vpmsolvers import BasicVPMSolver

        view_props = list(self.View.VariantDrivingProperties) \
            if self.View else []
        product_props = list(self.Product.VariantDrivingProperties)
        solver = BasicVPMSolver(self.Product,
                                view_props + product_props,
                                view_props)
        return solver

    def update_solver_status(self, solver=None, constraints=None, force=False):

        def _update_status(new_status):
            if self.solver_status != new_status:
                self.solver_status = new_status

        if constraints is None:
            constraints = []

        from cs.vp.variants.varianttableadapters import SyncStatus

        if not solver:
            solver = self.getSolver()

        solution_dict = {pv.id: pv.get_value() for pv in self.PropertyValues}

        if solver.validate(solution_dict):
            if solver.containsAllVariables(solution_dict):
                _update_status(SyncStatus.ok.value)
            else:
                _update_status(SyncStatus.incomplete.value)
            self.LinksToViolatedConstraints.Delete()
        elif self.solver_status != SyncStatus.manual.value or force is True:
            _update_status(SyncStatus.invalid.value)

        if self.solver_status != SyncStatus.ok.value:
            self._generate_links_to_violated_constraints(constraints)

    @classmethod
    def exclude_from_solution_space(cls, variant_dict, product_object_id, view_id=0):
        # FIXME: Adjust for options

        dict_iter = iter(variant_dict.items())
        prop_id, value = next(dict_iter)

        # Create constraint
        args = {"product_object_id": product_object_id,
                "constraint_id": Constraints.Constraint.newID(),
                "view_id": view_id,
                "property_id": prop_id,
                "enum_value": value,
                "operator": "!=",
                "constraint_type": 2,
                "excluding_constraint": 1,
                }

        if check_access("cdbvp_constraint", args, "create"):
            constr = Constraints.Constraint.CreateWithChangeLog(**args)

            # Create predicate
            args = {"product_object_id": product_object_id,
                    "constraint_id": constr.constraint_id,
                    "predicate_id": Constraints.Predicate.newID()
                    }
            pred = Constraints.Predicate.CreateWithChangeLog(**args)

            for prop_id, value in dict_iter:
                args = {"product_object_id": product_object_id,
                        "constraint_id": constr.constraint_id,
                        "predicate_id": pred.predicate_id,
                        "term_id": Constraints.Term.newID(),
                        "property_id": prop_id,
                        "enum_value": value,
                        "operator": "=",
                        }
                Constraints.Term.CreateWithChangeLog(**args)

            pred.Reload()
            pred.update_info_txt()

            constr.Product.Reload()
            constr.update_solver_stati()
            return constr
        else:
            raise ErrorMessage("cdbvp_product_missing_rights")

    def make_invalid(self):
        variant_dict = self.get_property_values()
        return self.exclude_from_solution_space(
            variant_dict, self.product_object_id, self.view_id)

    def get_violated_constraints(self):
        result = []

        ids, values = list(zip(*self.get_property_values().items()))
        for constraint in self.AllConstraints:
            if not constraint.is_mapping_constraint():
                if not constraint.compute(ids)(*values):
                    result.append(constraint)
        return result

    def _generate_links_to_violated_constraints(self, constraints=None):
        if constraints is None:
            constraints = []

        for constraint in constraints:
            args = {"product_object_id": self.product_object_id,
                    "variant_id": self.id,
                    "constraint_id": constraint.constraint_id}

            if not LinkToViolatedConstraint.ByKeys(**args):
                LinkToViolatedConstraint.Create(**args)

    # bom_table / threed support
    def make_variant_filter(self):
        """
        A filter used to filter bom items for specific variant properties
        :return: filter object which needs to have this function:
                eval(self, baugruppe, b_index, teilenummer, t_index, variante, position, occurrence_id=None, assembly_path=None)
                        Apply filter to BOM position

                        :return: True if the position should be included and False otherwise
        """
        from cs.vp.variants.filter import VariantBOMFilter
        return VariantBOMFilter(self.product_object_id, self.id)

    event_map = {
        (('create', 'copy'), 'pre_mask'): ('preset_id'),
        ('cdbvp_instantiate_max_bom', 'pre_mask'): '_preselect_max_bom_dlg',
        ('cdbvp_instantiate_max_bom', 'post_mask'): '_validate_max_bom_dlg',
        ('cdbvp_filtered_bom', 'pre_mask'): '_select_max_bom_dlg',
        ('cdbxml_excel_report', 'pre_mask'): 'set_report_mask_attributes'
    }


class ProductVariant(Variant):
    __classname__ = "cdbvp_product_variant"
    __match__ = Variant.cdb_classname >= __classname__

    VariantMappings = Reference_N(fVariantMapping,
                                  fVariantMapping.product_object_id == fVariant.product_object_id,
                                  fVariantMapping.variant_id == fVariant.id)

    AllConstraints = Reference_N(fConstraint,
                                 fConstraint.product_object_id == fVariant.product_object_id,
                                 fConstraint.view_id == 0)

    def mapToView(self, target_view_id):
        """ See Variant.mapToView """
        if target_view_id is None or target_view_id == 0:
            return set([self])
        mappings = self.VariantMappings.KeywordQuery(view_id=target_view_id)
        return set([m.ViewVariant for m in mappings if m.ViewVariant])

    def _skip_max_bom_dialog(self, ctx):
        if "maxbom_oid" in ctx.sys_args.get_attribute_names():
            ctx.skip_dialog()
        else:
            max_boms = self.Product.UsableToplevelAssemblies
            cnt = len(max_boms)
            if cnt == 0:
                raise ue.Exception("cdbvp_err_no_max_bom",
                                   self.Product.code)
            elif cnt == 1:
                ctx.skip_dialog()
            elif cnt == 2:
                if (max_boms[0].IsDerived() and max_boms[1].IsDerived() and
                    max_boms[0].cdb_depends_on == max_boms[1].cdb_object_id) or \
                    (max_boms[0].IsDerived() is False and max_boms[1].IsDerived() and
                     max_boms[1].cdb_depends_on == max_boms[0].cdb_object_id):
                    ctx.set("max_bom_teilenummer", max_boms[0].teilenummer)
                    ctx.set("max_bom_t_index", max_boms[0].t_index)
                    ctx.skip_dialog()


class ViewVariant(Variant):
    __classname__ = "cdbvp_view_variant"
    __match__ = Variant.cdb_classname >= __classname__

    VariantMappings = Reference_N(fVariantMapping,
                                  fVariantMapping.product_object_id == fVariant.product_object_id,
                                  fVariantMapping.view_variant_id == fVariant.id,
                                  fVariantMapping.view_id == fVariant.view_id)

    AllConstraints = Reference_N(fConstraint,
                                 fConstraint.product_object_id == fVariant.product_object_id,
                                 fConstraint.view_id == fVariant.view_id)

    def mapToView(self, target_view_id):
        """ See Variant.mapToView """
        if self.view_id == target_view_id:
            return set([self])
        result = set()
        for mapping in self.VariantMappings:
            product_variant = mapping.ProductVariant
            if product_variant:
                result.update(product_variant.mapToView(target_view_id))
        return result


class VariantMapping(Object):
    __maps_to__ = "cdbvp_variant_mapping"
    __classname__ = "cdbvp_variant_mapping"

    View = Reference_1(fProductView,
                       fVariantMapping.view_id,
                       fVariantMapping.product_object_id)

    ViewVariant = Reference_1(ViewVariant,
                              fVariantMapping.view_variant_id,
                              fVariantMapping.product_object_id)

    ProductVariant = Reference_1(ProductVariant,
                                 fVariantMapping.variant_id,
                                 fVariantMapping.product_object_id)


class Variant2Part(Object):
    __maps_to__ = "cdbvp_variant2part"
    __classname__ = "cdbvp_variant2part"

    Variant = Reference_1(fVariant,
                          fVariant.product_object_id == fVariant2Part.product_object_id,
                          fVariant.id == fVariant2Part.variant_id)

    Part = Reference_1(Item,
                       Item.teilenummer == fVariant2Part.teilenummer,
                       Item.t_index == fVariant2Part.t_index)

    MaxBOM = Reference_1(Item,
                         Item.teilenummer == fVariant2Part.max_bom_teilenummer,
                         Item.t_index == fVariant2Part.max_bom_t_index)


class LinkToViolatedConstraint(Object):
    __maps_to__ = "cdbvp_violated_constraints"
    __classname__ = "cdbvp_violated_constraints"


class VariantBrowser(CDBCatalog):
    """
    Product configuration catalog within product structure
    """

    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        self.browserdata = VariantBrowserData(self)
        self.setResultData(self.browserdata)

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            selected_variant = self.browserdata.variants[selected_rows[0]]
            # Determine the MaxBOM variant to use for actual filtering.
            # The code below in VariantBrowserData.__init__ guarantees that
            # there is exactly one result.
            (filter_variant,) = selected_variant.get_max_bom_variants()
            self.setValue("filter_id", "%s:%s" %
                          (filter_variant.product_object_id,
                           filter_variant.id))


class VariantBrowserData(CDBCatalogContent):

    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.catalog = catalog
        self.reset()

    def reset(self):
        self.variants = []
        self.product_object_id = None
        self.view_id = None
        self.variant_presettings = {}
        self.variant_search_cond = None

    def load(self):
        self.variants = []

        product = fProduct.ByKeys(self.product_object_id)
        if not product:
            return

        selected_view = None
        if self.view_id:
            selected_view = fProductView.ByKeys(self.view_id, self.product_object_id)

        variant_source = selected_view if selected_view else product
        max_bom_view_id = product.MaxBOMView.id if product.MaxBOMView else None
        self.variants = [variant
                         for variant in variant_source.Variants
                         if len(variant.mapToView(max_bom_view_id)) == 1
                         and variant.match(self.variant_presettings)]
        if self.variant_search_cond:
            res = fVariant.Query(self.variant_search_cond)
            self.variants = [v for v in self.variants if v in res]

    def onSearchChanged(self):
        self.reset()
        prop_search = defaultdict(dict)
        variant_attr_names = fVariant.GetFieldNames()

        for arg in self.getSearchArgs():
            if arg.name == "product_object_id":
                self.product_object_id = arg.value
            elif arg.name == "view_id":
                self.view_id = arg.value
            elif (arg.name.startswith("prop_search_id_") or arg.name.startswith("prop_search_value_id_")) and arg.value:
                # Collect property search values
                prop_search[arg.name[-2:]][arg.name[:-2]] = arg.value
            elif arg.name in variant_attr_names:
                self.variant_search_cond = self.getSQLCondition()

        VariantSearchBrowser.DIALOG_PRESETTINGS[self.product_object_id]["view_id"] = self.view_id

        # build dict with prop_id/value_id from collected property search values
        for d in prop_search.values():
            try:
                self.variant_presettings[int(d["prop_search_id_"])] = int(d["prop_search_value_id_"])
            except ValueError:
                pass
            except KeyError:
                pass
        self.load()

    def getNumberOfRows(self):
        return len(self.variants)

    def getRowObject(self, row):
        return self.variants[row].ToObjectHandle()


class VariantSearchBrowser(object):

    MAX_PROP_SEARCH_FIELDS = 20

    DIALOG_PRESETTINGS = defaultdict(dict)

    def invoked(self):
        return self.getInvokingField()

    def clear_view_search_conditions(self):
        self.setValue("view_id", "")
        self.setValue("view_name", "")
        self.clear_prop_search_conditions()

    def clear_product_search_conditions(self):
        self.setValue("product_object_id", "")
        self.setValue("product_code", "")
        self.clear_view_search_conditions()

    def _clear_prop_fields(self, search_field_id, field_names):
        for field_name in field_names:
            name = "%s_%s" % (field_name, str(search_field_id).zfill(2))
            # existence test - raises KeyError
            self.getInvokingDlgValue(name)
            # clear value
            self.setValue(name, "")

    def clear_prop_value_search_condition(self, search_field_id):
        self._clear_prop_fields(search_field_id,
                                ["prop_search_value", "prop_search_value_id"])

    def clear_prop_search_condition(self, search_field_id):
        self._clear_prop_fields(search_field_id,
                                ["prop_search_name", "prop_search_id"])
        self.clear_prop_value_search_condition(search_field_id)

    def clear_prop_search_conditions(self):
        try:
            for search_field_id in range(self.MAX_PROP_SEARCH_FIELDS):
                self.clear_prop_search_condition(search_field_id + 1)
        except KeyError:
            pass


class PropertyBrowser(CDBCatalog, VariantSearchBrowser):
    def __init__(self):
        CDBCatalog.__init__(self)
        self.product_object_id = None
        self.view_id = None

    def init(self):
        if self.invoked():
            try:
                self.product_object_id = self.getInvokingDlgValue("product_object_id")
                self.view_id = self.getInvokingDlgValue("view_id")
            except KeyError:
                pass
            if hasattr(self, "product_object_id") and self.product_object_id is not None \
                    and hasattr(self, "view_id") and self.view_id is not None:
                self.browserdata = PropertyBrowserData(self)
                self.setResultData(self.browserdata)

    def handleResultDataSelection(self, selected_rows):
        search_field_id = self.getInvokingField()[-2:]
        if len(selected_rows) == 1:
            selected_property = self.browserdata.properties[selected_rows[0]]
            self.setValue("prop_search_id_%s" % search_field_id, str(selected_property.id))
            self.setValue("prop_search_name_%s" % search_field_id, selected_property.Name[''])
            self.clear_prop_value_search_condition(search_field_id)
        elif len(selected_rows) == 0:
            self.clear_prop_search_condition(search_field_id)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection


class PropertyBrowserData(CDBCatalogContent):

    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)

        self.properties = []
        if catalog.view_id:
            obj = fProductView.ByKeys(catalog.view_id, catalog.product_object_id)
        else:
            obj = fProduct.ByKeys(catalog.product_object_id)
        if obj:
            self.properties = list(obj.VariantDrivingProperties)

            # reduce selectable properties by those, which are
            # already selected in another search field.
            search_field_id = catalog.getInvokingField()[-2:]
            already_selected = []
            for i in range(VariantSearchBrowser.MAX_PROP_SEARCH_FIELDS):
                current_search_field_id = str(i).zfill(2)
                if current_search_field_id != search_field_id:
                    try:
                        already_selected.append(int(catalog.getInvokingDlgValue("prop_search_id_%s" % current_search_field_id)))
                    except KeyError:
                        pass
                    except ValueError:
                        pass
            self.properties = [p for p in self.properties if p.id not in already_selected]

    def getNumberOfRows(self):
        return len(self.properties)

    def getRowObject(self, row):
        return self.properties[row].ToObjectHandle()


class PropertyValueBrowser(CDBCatalog, VariantSearchBrowser):
    def __init__(self):
        CDBCatalog.__init__(self)
        self.prop_id = None
        self.product_object_id = None

    def init(self):
        if self.invoked():
            try:
                search_field_id = self.getInvokingField()[-2:]
                self.prop_id = self.getInvokingDlgValue("prop_search_id_%s" % search_field_id)
                self.product_object_id = self.getInvokingDlgValue("product_object_id")
            except KeyError:
                pass
            if hasattr(self, "product_object_id") and self.product_object_id is not None \
                    and hasattr(self, "prop_id") and self.prop_id is not None:
                self.browserdata = PropertyValueBrowserData(self)
                self.setResultData(self.browserdata)

    def handleResultDataSelection(self, selected_rows):
        search_field_id = self.getInvokingField()[-2:]
        if len(selected_rows) == 1:
            selected_prop_value = self.browserdata.prop_values[selected_rows[0]]
            self.setValue("prop_search_value_id_%s" % search_field_id, str(selected_prop_value.value))
            self.setValue("prop_search_value_%s" % search_field_id, selected_prop_value.ValueText[''])
        elif len(selected_rows) == 0:
            self.clear_prop_value_search_condition(search_field_id)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection


class PropertyValueBrowserData(CDBCatalogContent):
    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)

        self.prop_values = []
        prop = fProperty.ByKeys(catalog.prop_id, catalog.product_object_id)
        if prop:
            self.prop_values = prop.EnumValues

    def getNumberOfRows(self):
        return len(self.prop_values)

    def getRowObject(self, row):
        return self.prop_values[row].ToObjectHandle()


class ProductBrowser(CDBCatalog, VariantSearchBrowser):
    """
    Product catalog within product structure
    """

    def __init__(self):
        CDBCatalog.__init__(self)
        self.teilenummer = None
        self.t_index = None

    def init(self):
        if self.invoked():
            try:
                self.teilenummer = self.getInvokingDlgValue("teilenummer")
                self.t_index = self.getInvokingDlgValue("t_index")
            except KeyError:
                pass
            if hasattr(self, "teilenummer") and self.teilenummer is not None and \
                    hasattr(self, "t_index") and self.t_index is not None:
                self.browserdata = ProductBrowserData(self)
                self.setResultData(self.browserdata)

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            selected_product = self.browserdata.products[selected_rows[0]]
            self.setValue("product_object_id", selected_product.cdb_object_id)
            self.setValue("product_code", selected_product.code)
            self.clear_view_search_conditions()
        elif len(selected_rows) == 0:
            self.clear_product_search_conditions()

    def allowMultiSelection(self):
        return self.kDisableMultiSelection


class ProductBrowserData(CDBCatalogContent):
    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)

        vpm_links = fProductAssemblyLink.KeywordQuery(teilenummer=catalog.teilenummer,
                                                      t_index=catalog.t_index)
        self.products = []
        for l in vpm_links:
            self.products.append(l.Product)

    def getNumberOfRows(self):
        return len(self.products)

    def getRowObject(self, row):
        return self.products[row].ToObjectHandle()


class ViewBrowser(CDBCatalog, VariantSearchBrowser):
    def __init__(self):
        CDBCatalog.__init__(self)
        self.product_object_id = None

    def init(self):
        if self.invoked():
            try:
                self.product_object_id = self.getInvokingDlgValue("product_object_id")
            except KeyError:
                pass
            if hasattr(self, "product_object_id") and self.product_object_id is not None:
                self.browserdata = ViewBrowserData(self)
                self.setResultData(self.browserdata)

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            selected_view = self.browserdata.views[selected_rows[0]]
            self.setValue("view_name", selected_view.Name[''])
            self.setValue("view_id", str(selected_view.id))
            self.clear_prop_search_conditions()
        elif len(selected_rows) == 0:
            self.clear_view_search_conditions()

    def allowMultiSelection(self):
        return self.kDisableMultiSelection


class ViewBrowserData(CDBCatalogContent):
    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)

        product = fProduct.ByKeys(catalog.product_object_id)
        if product:
            self.views = product.Views
        else:
            self.views = []

    def getNumberOfRows(self):
        return len(self.views)

    def getRowObject(self, row):
        return self.views[row].ToObjectHandle()


class MaxBOM_Browser(CDBCatalog):

    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        if self.getInvokingField():
            try:
                self.product_object_id = self.getInvokingDlgValue("product_object_id")
            except KeyError:
                pass
            if hasattr(self, "product_object_id") and self.product_object_id:
                self.browserdata = MaxBOM_BrowserData(self, self.product_object_id)
                self.setResultData(self.browserdata)

    def allowMultiSelection(self):
        return self.kDisableMultiSelection

    def handleResultDataSelection(self, selected_rows):
        if len(selected_rows) == 1:
            sel_item = self.browserdata.items[selected_rows[0]]
            self.setValue("max_bom_teilenummer", sel_item.teilenummer)
            self.setValue("max_bom_t_index", sel_item.t_index)


class MaxBOM_BrowserData(CDBCatalogContent):

    def __init__(self, catalog, product_object_id):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.items = fProduct.ByKeys(product_object_id).ToplevelAssemblies

    def getNumberOfRows(self):
        return len(self.items)

    def getRowObject(self, row):
        return self.items[row].ToObjectHandle()


class FilterVariantsBrowser(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        try:
            self.product_object_id = self.getInvokingDlgValue("product_object_id")
            self.id = self.getInvokingDlgValue("id")
            self.max_bom_view_id = self.getInvokingDlgValue("max_bom_view_id")
        except KeyError:
            pass
        if hasattr(self, "product_object_id") and self.product_object_id is not None \
                and hasattr(self, "id") and self.id is not None and hasattr(self, "max_bom_view_id") \
                and self.max_bom_view_id is not None:
            self.browserdata = FilterVariantsBrowserData(self)
            self.setResultData(self.browserdata)


class FilterVariantsBrowserData(CDBCatalogContent):
    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        mappings = VariantMapping.KeywordQuery(product_object_id=catalog.product_object_id,
                                               variant_id=catalog.id,
                                               view_id=catalog.max_bom_view_id)
        self.variants = [Variant.ByKeys(product_object_id=mapping.product_object_id,
                                        id=mapping.view_variant_id)
                         for mapping in mappings]

    def getNumberOfRows(self):
        return len(self.variants)

    def getRowObject(self, row):
        return self.variants[row].ToObjectHandle()
