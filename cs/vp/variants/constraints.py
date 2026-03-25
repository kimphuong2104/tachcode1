#!/usr/bin/env python
# -*- Python; coding: utf-8 -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved

from cdb import util
from cdb import i18n
from cdb import ue
from cdb.objects import Object
from cdb.objects import LocalizedField
from cdb.objects import Reference_N
from cdb.objects import Reference_1
from cdb.objects import Forward
from cs.vp.variants.operators import eval_term, inverse_operator

from cs.vp.variants.vptools import WithChangeLog

fConstraint = Forward(__name__ + ".Constraint")
fPredicate = Forward(__name__ + ".Predicate")
fTerm = Forward(__name__ + ".Term")
fDragDropHelperPropOnConstraint = Forward(__name__ + ".DragDropHelperPropOnConstraint")

fProperty = Forward("cs.vp.variants.properties.Property")
fEnumDefinition = Forward("cs.vp.variants.properties.EnumDefinition")

fProductView = Forward("cs.vp.variants.productviews.ProductView")

fProduct = Forward("cs.vp.products.Product")

IF = "IF"
ONLYIF = "IF AND ONLY IF"
AND = "AND"
OR = "OR"

# Defines the default language of the generated info expression
# for constraints and predicates
info_lang = "de"


class Constraint(Object, WithChangeLog):
    __maps_to__ = "cdbvp_constraint"
    __classname__ = "cdbvp_constraint"

    OutputProperty = Reference_1(fProperty,
                                 fConstraint.property_id,
                                 fConstraint.product_object_id)

    OutputPropertyValue = Reference_1(fEnumDefinition,
                                      fConstraint.property_id,
                                      fConstraint.product_object_id,
                                      fConstraint.enum_value)

    Predicates = Reference_N(fPredicate,
                             fPredicate.product_object_id == fConstraint.product_object_id,
                             fPredicate.constraint_id == fConstraint.constraint_id)

    ProductView = Reference_1(fProductView, fProductView.product_object_id == fConstraint.product_object_id,
                              fProductView.id == fConstraint.view_id)

    Product = Reference_1(fProduct, fConstraint.product_object_id)

    ConstraintTxt = LocalizedField("constraint_text", fala=True)

    def update_info_txt(self, ctx=None):
        # set longtext
        for lang in self.ConstraintTxt.keys():
            info_txt = self.info_str(lang)
            txt_attr = "cdbvp_constraint_info_txt_" + lang

            if txt_attr in self.GetClassDef().getTextFieldNames():
                self.SetText(txt_attr, info_txt)

            # set additional text field with first 256 chars for hitlist usage
            self.ConstraintTxt[lang] = info_txt[:256]

    def info_str(self, lang=info_lang):
        then_part = self.output_info_str(lang)
        if_part = self.predicate_info_str(lang)
        operator = IF if self.constraint_type == 2 else ONLYIF

        result = "%s %s \n%s" % (then_part, operator, if_part) if if_part else then_part
        return result

    def predicate_info_str(self, lang=info_lang):
        return (" \n%s " % OR).join(["(%s)" % p.info_str(lang) for p in self.Predicates if p.Terms])

    def output_info_str(self, lang="de"):
        lhs = self.OutputProperty.Name[lang]
        if not self.OutputPropertyValue:
            return "%s %s" % (
                lhs,
                self.operator
            )
        else:
            return "%s %s %s" % (
                lhs,
                self.operator,
                self.OutputPropertyValue.ValueText[lang]
            )

    def preset_property_name(self, ctx):
        from cs.vp.variants.properties import Property

        if ctx.dialog.property_id and self.OutputProperty and i18n.default() in self.OutputProperty.Name.keys():
            property_name_attr = Property.Name[''].name
            if property_name_attr in ctx.dialog.get_attribute_names():
                ctx.set(property_name_attr, self.OutputProperty.Name[''])

    def compute(self, property_ids):
        def implication_function(*args):
            """ Implication """
            x = dict(list(zip(property_ids, args)))
            wenn = any(pred.eval(x) for pred in self.Predicates)
            if wenn:
                val = x.get(self.OutputProperty.id, False)
                dann = eval_term(
                    val,
                    self.OutputPropertyValue.value if self.OutputPropertyValue else None,
                    self.operator
                )
            return not wenn or dann

        def equivalence_function(*args):
            """ Equivalence """
            x = dict(list(zip(property_ids, args)))
            wenn = any(pred.eval(x) for pred in self.Predicates)

            val = x.get(self.OutputProperty.id, False)
            dann = eval_term(
                val,
                self.OutputPropertyValue.value if self.OutputPropertyValue else None,
                self.operator
            )
            return wenn == dann

        return equivalence_function if self.constraint_type == 1 else implication_function

    def properties_used(self):
        result = set((self.OutputProperty,))
        result.update(*(pred.properties_used() for pred in self.Predicates))
        return result

    def set_update_info_txt_flag(self, ctx):
        if ctx.action == "create":
            ctx.keep("update_info_txt", "1")
        else:
            attr_names = ["operator", "enum_value", "property_id"]
            for attr in attr_names:
                if ctx.object[attr] != self[attr]:
                    ctx.keep("update_info_txt", "1")
                    break

    def set_operator(self, ctx):
        if self.OutputPropertyValue:
            self.operator = "="
        else:
            self.operator = '\N{BALLOT BOX WITH CHECK}'

    def check_update_info_txt(self, ctx):
        if "update_info_txt" in ctx.ue_args.get_attribute_names():
            obj = self.getPersistentObject()
            obj.update_info_txt()

    def dragdrop_handler(self, ctx):
        if ctx.dragged_obj:
            ctx.skip_dialog()

    def on_cdbvp_toggle_constraint_operator_now(self, ctx):
        if self.CheckAccess("save"):
            self.operator = inverse_operator(self.operator)
            self.update_info_txt()
        else:
            raise ue.Exception("cdbvp_automatic_constraint")

    def update_solver_stati(self, ctx=None):
        self.Product.update_solver_stati(constraints=[self])

    @classmethod
    def newID(cls):
        return util.nextval("cdbvp_constraint")

    def is_mapping_constraint(self):
        for pred in self.Predicates:
            for term in pred.Terms:
                if term.Property.view_id != self.OutputProperty.view_id:
                    return True
        return False

    event_map = {(("create"), "pre_mask"): ("preset_property_name", "dragdrop_handler"),
                 (("modify"), "post_mask"): ("set_update_info_txt_flag"),
                 (("create"), "pre"): ("set_update_info_txt_flag", "set_operator"),
                 (("create", "modify"), "post"): "check_update_info_txt",
                 # Thinkabout: maybe create not needed?
                 (("create", "copy", "modify", "delete",
                   "cdbvp_toggle_constraint_operator"), "post"): "update_solver_stati",
                 }


class Predicate(Object, WithChangeLog):
    __maps_to__ = "cdbvp_predicate"
    __classname__ = "cdbvp_predicate"

    Terms = Reference_N(fTerm,
                        fTerm.product_object_id == fPredicate.product_object_id,
                        fTerm.constraint_id == fPredicate.constraint_id,
                        fTerm.predicate_id == fPredicate.predicate_id)

    Constraint = Reference_1(fConstraint,
                             fPredicate.product_object_id,
                             fPredicate.constraint_id)

    PredicateText = LocalizedField("predicate_text", fala=True)

    def update_info_txt(self, ctx=None):
        for lang in self.PredicateText.keys():
            self.PredicateText[lang] = self.info_str(lang)
        if self.Constraint:
            self.Constraint.update_info_txt()

    def info_str(self, lang=info_lang):
        if self.Terms:
            return (" %s " % AND).join([t.info_str(lang) for t in self.Terms])
        else:
            return "*** empty expression ***"

    def skip_dialog(self, ctx):
        ctx.skip_dialog()

    def eval(self, x):
        return all(term.eval(x) for term in self.Terms)

    def properties_used(self):
        return set(term.Property for term in self.Terms)

    @classmethod
    def newID(cls):
        return util.nextval("cdbvp_predicate")

    def update_solver_stati(self, ctx=None):
        if self.Constraint:
            self.Constraint.update_solver_stati()

    event_map = {
        ("create", "pre_mask"): "skip_dialog",
        ("delete", "post"): ("update_info_txt", "update_solver_stati")
    }


class Term(Object, WithChangeLog):
    __maps_to__ = "cdbvp_term"
    __classname__ = "cdbvp_term"

    Predicate = Reference_1(Predicate,
                            fTerm.product_object_id,
                            fTerm.constraint_id,
                            fTerm.predicate_id)

    Property = Reference_1(fProperty,
                           fTerm.property_id,
                           fTerm.product_object_id)

    PropertyValue = Reference_1(fEnumDefinition,
                                fTerm.property_id,
                                fTerm.product_object_id,
                                fTerm.enum_value)

    Constraint = Reference_1(fConstraint, fConstraint.product_object_id == fTerm.product_object_id,
                             fConstraint.constraint_id == fTerm.constraint_id)

    def update_predicate_txt(self, ctx=None):
        if self.Predicate:
            self.Predicate.update_info_txt()

    def info_str(self, lang="de"):
        if self.PropertyValue:
            return "%s %s %s" % (self.Property.Name[lang], self.operator, self.PropertyValue.ValueText[lang])
        else:
            return "%s %s" % (self.Property.Name[lang], self.operator)

    def eval(self, x):
        val = x.get(self.Property.id, False)
        return eval_term(
            val,
            self.PropertyValue.value if self.PropertyValue else None,
            self.operator
        )

    def on_cdbvp_toggle_term_operator_now(self, ctx):
        self.operator = inverse_operator(self.operator)
        self.update_predicate_txt()

    def on_create_pre_mask(self, ctx):
        if ctx.dragged_obj:
            ctx.skip_dialog()

    @classmethod
    def newID(cls):
        return util.nextval("cdbvp_term")

    def check_mapping_consistency(self, ctx):
        if self.PropertyValue and self.PropertyValue.Property.ProductView:
            if not self.Constraint.ProductView:
                raise ue.Exception("cdbvp_mapping_constraint_on_views")
            elif self.Constraint.ProductView != self.PropertyValue.Property.ProductView:
                raise ue.Exception("cdbvp_mapping_constraints_between_views")

    def check_product(self, ctx):
        if self.PropertyValue and self.PropertyValue.product_object_id != self.product_object_id:
            raise ue.Exception("cdbvp_different_product")

    def check_constraint_type(self, ctx=None):
        # Constraint Typ bei Mapping-Constraints autom. auf Äquivalenz ändern bei
        # Zuordnung des ersten Terms.
        if self.PropertyValue and self.PropertyValue.Property.ProductView != self.Constraint.ProductView:
            brothers = fTerm.Query((fTerm.product_object_id == self.product_object_id) &
                                   (fTerm.constraint_id == self.constraint_id))
            if len(brothers) == 1:
                # constraint type 'equivalence' has id 1
                self.Constraint.constraint_type = 1
                self.Constraint.update_info_txt()

    def update_solver_stati(self, ctx=None):
        if self.Constraint:
            self.Constraint.update_solver_stati()

    event_map = {("create", "pre"): ("check_mapping_consistency", "check_product"),
                 ("create", "post"): "check_constraint_type",
                 (("create", "copy", "modify", "delete"), ("post")): ("update_predicate_txt", "update_solver_stati")
                 }


class DragDropHelperPropOnConstraint(Object):
    __maps_to__ = "cdbvp_ddhelper_prop_on_constr"
    __classname__ = "cdbvp_ddhelper_prop_on_constr"

    Constraint = Reference_1(fConstraint,
                             fConstraint.product_object_id == fDragDropHelperPropOnConstraint.product_object_id,
                             fConstraint.constraint_id == fDragDropHelperPropOnConstraint.constraint_id)

    def on_create_pre_mask(self, ctx):
        ctx.skip_dialog()

    def on_create_pre(self, ctx):
        if not self.Constraint.CheckAccess("save"):
            raise ue.Exception("cdbvp_automatic_constraint")

        obj = self.getPersistentObject()
        if obj:
            obj.Delete()

        if self.property_value is None:
            self.property_value = -1
            self.cdbvp_operator = '\N{BALLOT BOX WITH CHECK}'
        else:
            self.cdbvp_operator = "="

    def on_create_post(self, ctx):
        # Create Predicate
        p = Predicate\
            .CreateWithChangeLog(product_object_id=self.product_object_id,
                                 constraint_id=self.constraint_id,
                                 predicate_id=Predicate.newID())

        # Create Term
        property_value = self.property_value if self.property_value >= 0 else None
        t = Term.CreateWithChangeLog(product_object_id=self.product_object_id,
                                     constraint_id=self.constraint_id,
                                     predicate_id=p.predicate_id,
                                     term_id=Term.newID(),
                                     property_id=self.property_id,
                                     enum_value=property_value,
                                     operator=self.cdbvp_operator)
        t.check_constraint_type()
        t.update_solver_stati()

        # Set predicate text
        p.update_info_txt()

        # Everything is set up, now we can drop the relship object
        obj = self.getPersistentObject()
        if obj:
            obj.Delete()

    def check_mapping_consistency(self, ctx):
        enum_def = fEnumDefinition.ByKeys(ctx.dragged_obj.id,
                                          ctx.dragged_obj.product_object_id,
                                          getattr(ctx.dragged_obj, "value", -1))
        constraint = fConstraint.ByKeys(self.product_object_id, self.constraint_id)
        if enum_def and enum_def.Property.ProductView:
            if not constraint.ProductView:
                # raises "Mapping-Constraints können nur als Constraints in der
                # jeweiligen Sicht definiert werden."
                raise ue.Exception(9845)
            elif constraint.ProductView != enum_def.Property.ProductView:
                # raises "Mapping-Constraints können nur zwischen den Merkmalen
                # am Produkt und den Merkmalen einer Sicht definiert werden."
                raise ue.Exception(9846)

    def check_product(self, ctx):
        if ctx.dragged_obj.product_object_id != self.product_object_id:
            # raises "Constraints dürfen nur Merkmale aus demselben Produkt verwenden."
            raise ue.Exception(9847)

    event_map = {("create", "pre"): ("check_mapping_consistency", "check_product"),
                 }


class ConstraintType(Object):
    __classname__ = "cdbvp_constraint_type"
    __maps_to__ = "cdbvp_constraint_type"
