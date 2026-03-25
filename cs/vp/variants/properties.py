#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved

from cdb import util
from cdb import ue
from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import LocalizedField
from cdb.objects import ReferenceMapping_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import NULL
from cdb.objects import ByID
from cdb.platform.gui import CDBCatalog
from cdb.platform.mom import getObjectHandleFromObjectID
from cdb.platform.mom import entities

from cs.vp.variants.constraints import eval_term

from cs.vp.variants.propertiescatalogue import CatalogueEnumDefinition
from cs.vp.variants.propertiescatalogue import CatalogueProperty

from cs.vp.variants.varianttableadapters import SyncStatus

from cs.vp.variants.solvers import BasicProblemSolver
from cs.vp.variants.vptools import WithChangeLog

import re

fProperty = Forward(__name__ + ".Property")
fEnumDefinition = Forward(__name__ + ".EnumDefinition")
fPropertyValue = Forward(__name__ + ".PropertyValue")
fPropertyDependency = Forward(__name__ + ".PropertyDependency")
fEnumDefPropertyValue = Forward(__name__ + ".EnumDefPropertyValue")
fProperty2SubProductProperty = Forward(__name__ + ".Property2SubProductProperty")
fVariant = Forward("cs.vp.variants.Variant")
fConstraint = Forward("cs.vp.variants.constraints.Constraint")
fProduct = Forward("cs.vp.products.Product")
fProductView = Forward("cs.vp.variants.productviews.ProductView")
fTerm = Forward("cs.vp.variants.constraints.Term")
fCatalogueProperty = Forward("cs.vp.variants.propertiescatalogue.CatalogueProperty")
fCatalogueEnumDefinition = Forward("cs.vp.variants.propertiescatalogue.CatalogueEnumDefinition")
fBOM_Term = Forward("cs.vp.variants.bomlinks.BOM_Term")


def fill_localized_fields(LField, value=None):
    """ This method is called from objects of the classes
        Property, EnumDefinition, CatalogueProperty, CatalogueEnumDefinition,
        PropertyFolder and ProductView

        - LField    is the LocalizedField corresponding to name,
                    it shouldn't support language fallback (fala = False)
        - value     value in the login language
    """
    if value is None:
        value = LField['de']

    is_generated = re.compile("^\{.+\}$")

    for lang in LField.keys():
        if not LField[lang] or is_generated.match(LField[lang]):
            LField[lang] = "{%s}" % value


def generate_erp_name(input_str, length):
    # this method is called from EnumDefinition objects,
    # as well as from CatalogueEnumDefinition objects.
    """ Short name for SAP """
    short_name = (str(input_str)
                  .replace('ß', 'ss')
                  .upper()
                  .replace(' ', '')
                  .replace('Ä', 'AE')
                  .replace('Ö', 'OE')
                  .replace('Ü', 'UE'))
    return short_name[:length]


def set_erp_code(obj, attr):
    """ This method is called from objects of the classes
        Property and CatalogueProperty

        - obj     The object whose ERP-code has to be set
        - attr    The name of the attribute that contains
                  the ERP-code
    """
    if getattr(obj, attr) == "-- auto --":
        for lang in 'en', 'de':
            if obj.Name[lang] and not obj.Name[lang].startswith('{'):
                setattr(obj, attr,
                        generate_erp_name(obj.Name[lang],
                                          getattr(obj.__class__, attr).length))
                break


class Property(Object, WithChangeLog):
    """ Merkmale """

    __classname__ = "cdbvp_property"
    __maps_to__ = "cdbvp_property"

    COMPARE_WITH_CATALOG = {"name_de": "name_de",
                            "name_en": "name_en",
                            "erp_code": "sap_property",
                            "data_type": "data_type"}

    EnumValues = Reference_N(fEnumDefinition,
                             fEnumDefinition.product_object_id == fProperty.product_object_id,
                             fEnumDefinition.id == fProperty.id)

    # Liefert die für den Variantengenerator relevanten Merkmalswerte.
    # Das sind alle manuell angelegten Merkmalswerte und alle generierten
    # Merkmalswerte, die valide sind (cdbvp_enum_def.solver_status != SyncStatus.invalid.value)

    GeneratorRelevantEnumValues = Reference_N(fEnumDefinition,
                                              fEnumDefinition.product_object_id == fProperty.product_object_id,
                                              fEnumDefinition.id == fProperty.id,
                                              ((fEnumDefinition.solver_status == SyncStatus.manual.value) |
                                               (fEnumDefinition.solver_status == SyncStatus.ok.value) |
                                               (fEnumDefinition.solver_status == NULL))
                                              )
    GeneratedValidEnumValues = Reference_N(fEnumDefinition,
                                           fEnumDefinition.product_object_id == fProperty.product_object_id,
                                           fEnumDefinition.id == fProperty.id,
                                           fEnumDefinition.solver_status == SyncStatus.ok.value)

    EnumByValue = ReferenceMapping_1(fEnumDefinition,
                                     fEnumDefinition.product_object_id == fProperty.product_object_id,
                                     fEnumDefinition.id == fProperty.id,
                                     indexed_by=fEnumDefinition.value)

    Constraints = Reference_N(fConstraint,
                              fConstraint.product_object_id == fProperty.product_object_id,
                              fConstraint.property_id == fProperty.id)

    Terms = Reference_N(fTerm,
                        fTerm.product_object_id == fProperty.product_object_id,
                        fTerm.property_id == fProperty.id)

    Product = Reference_1(fProduct, fProperty.product_object_id)

    ProductView = Reference_1(fProductView,
                              fProperty.view_id, fProperty.product_object_id)

    SubProductPropertyMappings = Reference_N(fProperty2SubProductProperty,
                                             fProperty2SubProductProperty.product_object_id == fProperty.product_object_id,
                                             fProperty2SubProductProperty.property_id == fProperty.id)

    PropertyDependencies = Reference_N(fPropertyDependency,
                                       fPropertyDependency.product_object_id == fProperty.product_object_id,
                                       fPropertyDependency.property_id == fProperty.id)

    PropertyDependencyUsages = Reference_N(fPropertyDependency,
                                           fPropertyDependency.product_object_id == fProperty.product_object_id,
                                           fPropertyDependency.property_id2 == fProperty.id)

    CatalogueProperty = Reference_1(fCatalogueProperty, fProperty.catalogue_property_object_id)

    PropertyValues = Reference_N(fPropertyValue,
                                 fPropertyValue.product_object_id == fProperty.product_object_id,
                                 fPropertyValue.id == fProperty.id)

    SubProperties = Reference_N(
        fProperty,
        (fProperty.product_object_id == fProperty.product_object_id) &
        (fProperty.parent_id == fProperty.id)
    )

    Name = LocalizedField("property_name", de="name_de", en="name_en", fala=True)
    NameNoFala = LocalizedField("property_name", de="name_de", en="name_en")

    def _getConstraintUsages(self):
        return fConstraint.SQL("""
            SELECT *
            FROM cdbvp_constraint
            WHERE EXISTS (
                SELECT *
                FROM cdbvp_term
                WHERE property_id=%s AND product_object_id='%s'
                    AND cdbvp_term.constraint_id=cdbvp_constraint.constraint_id
                    AND cdbvp_term.product_object_id=cdbvp_constraint.product_object_id
            )
            """ % (self.id, self.product_object_id))

    ConstraintUsages = ReferenceMethods_N(fConstraint, _getConstraintUsages)

    def isSubProperty(self):
        return len(self.PropertyDependencyUsages) > 0

    def _getAttachedProperties(self):
        return [d.ReferencedProperty for d in self.PropertyDependencies
                if d.ReferencedProperty
                and len(d.ReferencedProperty.GeneratorRelevantEnumValues) > 0]
    AttachedProperties = ReferenceMethods_N(fProperty, _getAttachedProperties)

    def setup_generator_register(self, ctx):
        if ctx.action in ("create", "query") or not self.PropertyDependencies:
            ctx.disable_registers(["cdbvp_enum_def_generator"])

    def getVariantTableAdapter(self, **kwargs):
        from cs.vp.variants.varianttableadapters import PropertyAdapter
        return PropertyAdapter(self)

    def keep_name(self, ctx):
        for lang in self.Name.keys():
            ctx.keep(Property.Name[lang].name, self.Name[lang])

    def update_constraint_texts(self, ctx):
        for lang in self.Name.keys():
            if Property.Name[lang].name in ctx.ue_args.get_attribute_names() and \
                    getattr(ctx.ue_args, Property.Name[lang].name) != self.Name[lang]:
                # Constraints, in denen das Merkmal als Term verwendet wird
                for c in self.ConstraintUsages:
                    # update predicate infos
                    for p in c.Predicates:
                        p.update_info_txt()
                    # update constraint infos
                    c.update_info_txt()
                # Direkt zugeordnete Constraints (Merkmal ist Output Merkmal)
                for c in self.Constraints:
                    c.update_info_txt()
                for t in self.Terms:
                    t.update_predicate_txt()
                break

    def update_variant_texts(self, ctx):
        for lang in self.Name.keys():
            attr_name = Property.Name[lang].name
            if attr_name in ctx.ue_args.get_attribute_names() and ctx.ue_args[attr_name] != self.Name[lang]:
                if self.ProductView:
                    self.ProductView.update_variant_texts()
                else:
                    self.Product.update_variant_texts()
                break

    def copy_values(self, ctx=None):
        """ If the property comes from the catalogue, copy the values from the catalogue
        """
        if self.data_type == 'boolean':
            return
        if self.CatalogueProperty and not self.CatalogueProperty.ValueFolders:
            for cvalue in self.CatalogueProperty.Values:
                args = {"product_object_id": self.product_object_id,
                        "id": self.id,
                        "name": cvalue.name,
                        "catalogue_property_object_id": self.CatalogueProperty.cdb_object_id,
                        "catalog_enum_value": cvalue.value,
                        "solver_status": SyncStatus.manual.value,
                        "value": cvalue.value
                        }

                for lang in cvalue.ValueTxt.keys():
                    name = CatalogueEnumDefinition.ValueTxt[lang].name
                    args[name] = cvalue[name]

                EnumDefinition.CreateGenerated(**args)
            self.dirty = 0

    def set_dirty(self, ctx):
        if self.CatalogueProperty:
            for lang in self.Name.keys():
                if Property.Name[lang].name in ctx.ue_args.get_attribute_names() and \
                        getattr(ctx.ue_args, Property.Name[lang].name) != self.Name[lang]:
                    if ctx.mode == "post":
                        self.getPersistentObject().dirty = 1
                    else:
                        self.dirty = 1
                    break

    def check_catalogue_property_status(self, ctx):
        if "cdb_object_id" in ctx.dragged_obj.get_attribute_names():
            clsname = getObjectHandleFromObjectID(ctx.dragged_obj.cdb_object_id).getClassDef().getClassname()

            if clsname == "cdbvp_catalogue_property":
                catalogue_property = ByID(ctx.dragged_obj.cdb_object_id)

                if catalogue_property.status != CatalogueProperty.VALID.status:
                    raise ue.Exception(9833)

    def fill_names(self, ctx):
        if "cdb_object_id" in ctx.dragged_obj.get_attribute_names():
            clsname = getObjectHandleFromObjectID(ctx.dragged_obj.cdb_object_id).getClassDef().getClassname()

            if clsname == "cdbvp_catalogue_property":
                catalogue_property = ByID(ctx.dragged_obj.cdb_object_id)

                for lang in Property.Name.keys():
                    if lang in CatalogueProperty.Name.keys():
                        ctx.set(Property.Name[lang].name, catalogue_property.Name[lang])
                ctx.skip_dialog()

    def set_fields(self, ctx):
        if ctx.relationship_name != "cdbvp_catalogue_property2property":
            ctx.set_writeable("catalogue_property_object_id")

    def fill_localized_fields(self, ctx):
        fill_localized_fields(self.NameNoFala, value=self.property_name)

    def preset_erp_code(self, ctx=None):
        if not ctx or ctx.dragged_obj_relationship_name != "cdbvp_catalogue_folder2property":
            self.erp_code = "-- auto --"

    def set_erp_code(self, ctx):
        set_erp_code(self, "erp_code")

    def erp_id(self):
        return self.erp_code

    def isMaxBOMRateable(self):
        ok = True
        exc = None

        # Nur Merkmale direkt am Produkt oder die Merkmale der markierten MaxBOM Sicht dürfen
        # bewertet werden. Wenn eine Sicht zur Bewertung der MaxBOM markiert ist, dürfen die
        # Merkmale direkt am Produkt nicht verwendet werden.
        max_bom_view = self.Product.MaxBOMView
        if self.ProductView != max_bom_view:
            ok = False
            if max_bom_view:
                if self.ProductView:
                    exc = ue.Exception("cdbvp_property_not_from_maxbom_view",
                                       max_bom_view.name_de, self.ProductView.name_de)
                else:
                    exc = ue.Exception("cdbvp_property_not_from_maxbom_view2",
                                       max_bom_view.name_de)
            else:
                exc = ue.Exception("cdbvp_property_not_from_maxbom_view3")
        return ok, exc

    @classmethod
    def NewID(cls):
        return util.nextval("cdbvp_property")

    def set_position(self, ctx=None):
        self.position = util.nextval("cdbvp_property_position", 1)

    def on_cdbvp_property_move_up_now(self, ctx):
        expr = ((Property.product_object_id == self.product_object_id)
                & (Property.view_id == self.view_id)
                & (Property.position < self.position))
        pres = Property.Query(expr)
        if not pres:
            raise ue.Exception("cdbvp_err_property_top_position")

        pre = max(pres, key=lambda x: x.position)
        tmp = pre.position
        pre.position = self.position
        self.position = tmp

    def on_cdbvp_property_move_down_now(self, ctx):
        expr = ((Property.product_object_id == self.product_object_id)
                & (Property.view_id == self.view_id)
                & (Property.position > self.position))
        pres = Property.Query(expr)
        if not pres:
            raise ue.Exception("cdbvp_err_property_bottom_position")

        succ = min(pres, key=lambda x: x.position)
        tmp = succ.position
        succ.position = self.position
        self.position = tmp

    def checkInterfaceFlag(self, ctx):
        if self.interface_property and not self.CatalogueProperty:
            raise ue.Exception("cdbvp_interface_prop_err")

    def allowDelete(self, ctx):
        if len(self.SubProductPropertyMappings):
            raise ue.Exception("cdbvp_del_prop_err")

    def dialog_item_change(self, ctx):
        if ctx.changed_item == 'catalogue_property_object_id' and \
                self.erp_code == "":
            self.preset_erp_code()

    def get_differences_from_catalogue(self):
        cdbvp_property = entities.Entity.ByKeys(classname="cdbvp_property")

        if self.CatalogueProperty:
            propdiff = []
            values = {}

            for attr in self.COMPARE_WITH_CATALOG.keys():
                catattr = self.COMPARE_WITH_CATALOG[attr]
                if getattr(self, attr) != getattr(self.CatalogueProperty, catattr):
                    field_label = cdbvp_property.DDFieldsByName[attr].Label['']
                    propdiff.append((field_label,
                                               getattr(self, attr),
                                               getattr(self.CatalogueProperty, catattr)))

            for value in self.EnumValues:
                diffs = value.get_differences_from_catalogue()
                if diffs:
                    values[value.value] = diffs

            new_values = [val for val in self.EnumValues if not val.CatalogueEnumValue]

            return propdiff, values, new_values

    def update_value_stati(self, solver=None):
        generated_values = ((fEnumDefinition.solver_status == SyncStatus.ok.value) |
                            (fEnumDefinition.solver_status == SyncStatus.manual.value) |
                            (fEnumDefinition.solver_status == SyncStatus.invalid.value))

        if self.AttachedProperties:
            if not solver:
                from cs.vp.variants.vpmsolvers import BasicVPMSolver
                solver = BasicVPMSolver(self.Product, self.AttachedProperties)

            for value in self.EnumValues.Query(generated_values):
                value.update_solver_status(solver)
        else:
            # All the generated values become invalid
            self.EnumValues.Query(generated_values).Update(solver_status=SyncStatus.invalid.value)

    def create_bool_prop_values(self, ctx):
        """
        Creates two property values if selected data_type is 'boolean'
        """
        if self.data_type == 'boolean':
            BOOL_VALUES = [0, 1]
            for value in BOOL_VALUES:
                args = dict(value=value, id=self.id,
                            name=value, product_object_id=self.product_object_id,
                            catalogue_property_object_id='')

                for lang in EnumDefinition.ValueText.keys():
                    attrname = EnumDefinition.ValueText[lang].name
                    args[attrname] = value

                EnumDefinition.CreateWithChangeLog(**args)

    def check_data_type(self, ctx):
        """
        Check switch of data types.
        Not allowed:
        alphanumeric -> numeric,
        alphanumeric -> boolean,
        numeric -> boolean
        """
        if (ctx.object.data_type == "alphanumeric" and self.data_type == "numeric") or \
               (ctx.object.data_type == "alphanumeric" and self.data_type == "boolean") or \
               (ctx.object.data_type == "numeric" and self.data_type == "boolean"):
            raise ue.Exception("cdbvp_data_type_modify", ctx.object.data_type, self.data_type)

    def update_solver_stati(self, ctx=None):
        if self.Product:
            self.Product.update_solver_stati()

    @staticmethod
    def get_typed_value_for_type(prop_type, value):
        if prop_type == "boolean":
            if value == "0":
                return False
            elif value == "1":
                return True
            else:
                return value
        elif prop_type == "numeric":
            return float(value)
        else:
            return value

    def get_typed_value(self, value):
        """
        Returns the typed value. I.e. True or False if the property is boolean,
        a float value if the property is numeric and a unicode string if the property
        is alphanumeric

        :param value: A property value, as stored in the database. For float values the decimal
            separator should be a point. This is always the case if you use the attribute
            cdbvp_enum_def.name.
        """
        return self.get_typed_value_for_type(self.data_type, value)

    event_map = {(("create", "copy", "modify", "info", "query"), "pre_mask"): "setup_generator_register",
                 (("modify"), "pre_mask"): ("keep_name"),
                 (("modify"), "post"): ("update_constraint_texts", "update_variant_texts", "set_dirty", "update_solver_stati"),
                 ("modify", ("post_mask", "pre")): "check_data_type",
                 ("create", "pre"): "set_position",
                 (("create"), ("post")): ("copy_values", "create_bool_prop_values", "update_solver_stati"),
                 (("create"), ("pre_mask")): ("check_catalogue_property_status", "fill_names", "set_fields"),
                 (("create", "modify", "copy"), "post_mask"): ("checkInterfaceFlag", "fill_localized_fields"),
                 (("create", "copy"), "post_mask"): "set_erp_code",
                 (("create", "copy"), "pre_mask"): "preset_erp_code",
                 (('create', 'copy'), 'dialogitem_change'): "dialog_item_change",
                 ("delete", "pre"): "allowDelete",
                 (("copy", "delete"), "post"): "update_solver_stati"
                 }


class PropertyTypeCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        return ["alphanumeric", "numeric", "boolean"]


class EnumDefinition(Object, WithChangeLog):
    """ Merkmalswert am Merkmal vom Typ Enum """

    __classname__ = "cdbvp_enum_def"
    __maps_to__ = "cdbvp_enum_def"

    COMPARE_WITH_CATALOG = {"value_txt_de": "value_txt_de",
                            "value_txt_en": "value_txt_en",
                            "name": "name"}

    ValueText = LocalizedField("value_txt", fala=True)
    ValueTextNoFala = LocalizedField("value_txt")

    Property = Reference_1(fProperty, fEnumDefinition.id, fEnumDefinition.product_object_id)

    PropertyValues = Reference_N(fEnumDefPropertyValue,
                                 fEnumDefPropertyValue.product_object_id == fEnumDefinition.product_object_id,
                                 fEnumDefPropertyValue.property_id == fEnumDefinition.id,
                                 fEnumDefPropertyValue.property_value == fEnumDefinition.value)

    CatalogueEnumValue = Reference_1(fCatalogueEnumDefinition,
                                     fCatalogueEnumDefinition.catalogue_property_object_id == fEnumDefinition.catalogue_property_object_id,
                                     fCatalogueEnumDefinition.value == fEnumDefinition.catalog_enum_value)

    Constraints = Reference_N(fConstraint,
                              fConstraint.product_object_id == fEnumDefinition.product_object_id,
                              fConstraint.property_id == fEnumDefinition.id,
                              fConstraint.enum_value == fEnumDefinition.value
                              )

    Terms = Reference_N(fTerm,
                        fTerm.product_object_id == fEnumDefinition.product_object_id,
                        fTerm.property_id == fEnumDefinition.id,
                        fTerm.enum_value == fEnumDefinition.value)

    BOM_Terms = Reference_N(fBOM_Term,
                            fBOM_Term.product_object_id == fEnumDefinition.product_object_id,
                            fBOM_Term.property_id == fEnumDefinition.id,
                            fBOM_Term.enum_value == fEnumDefinition.value)

    def _getConstraintUsages(self):
        return fConstraint.SQL("""
            SELECT *
            FROM cdbvp_constraint
            WHERE EXISTS (
                SELECT *
                FROM cdbvp_term
                WHERE product_object_id='%s' AND property_id=%s AND enum_value=%s
                    AND cdbvp_term.constraint_id=cdbvp_constraint.constraint_id
                    AND cdbvp_term.product_object_id=cdbvp_constraint.product_object_id
            )
            """ % (self.product_object_id, self.id, self.value))

    ConstraintUsages = ReferenceMethods_N(fConstraint, _getConstraintUsages)

    @classmethod
    def NewID(cls):
        return util.nextval("cdbvp_enum_def")

    @classmethod
    def CreateGenerated(cls, **kwargs):
        if "value" not in kwargs:  # this is the key
            kwargs["value"] = cls.NewID()
        if "solver_status" not in kwargs:
            kwargs["solver_status"] = SyncStatus.ok.value
        return cls.CreateWithChangeLog(**kwargs)

    def updateSignature(self):
        prop_values = ((pv.rated_property_id, pv.rated_property_value) for pv in self.PropertyValues)
        signature = BasicProblemSolver.getSolutionSignature(prop_values)
        if self.signature != signature:
            self.signature = signature

    # --------------- Pager API --------------

    def get_property_values(self):
        return BasicProblemSolver.parseSolutionSignature(self.signature)

    def match(self, presettings):
        result = True
        if presettings:
            for prop_id, value in self.get_property_values().items():
                if prop_id in presettings and value != presettings[prop_id]:
                    result = False
                    break
        return result

    # ----------------------------------------

    def generate_erp_name(self, input_str=None):
        """ Short name for SAP """
        if not input_str:
            if self.value_txt_en:
                input_str = self.value_txt_en
            elif self.value_txt_de:
                input_str = self.value_txt_de
            else:
                input_str = self.generate_name()

        return generate_erp_name(input_str, EnumDefinition.name.length)

    def generate_name(self, lang=None):
        return ", ".join([pv.info_str(lang) for pv in self.PropertyValues])

    def set_name(self, ctx):
        if self.Property.data_type == 'alphanumeric' and self.name == "-- auto --":
            self.name = self.generate_erp_name(self.value_txt_de)

    def preset_name(self, ctx):
        if set(["value", "catalogue_property_object_id"]) <= set(ctx.dragged_obj.get_attribute_names()):
            ctx.skip_dialog()
        elif self.Property.data_type == "alphanumeric":
            self.name = "-- auto --"

    def compute_constraint(self, property_ids, satisfying_input_property_values):
        def eval_input_property_value(x, prop_value):
            return eval_term(x[prop_value.Property.id], prop_value.value, "=")

        def the_compute_function(*args):
            x = dict(zip(property_ids, args))
            wenn = any(eval_input_property_value(x, p)
                       for p in satisfying_input_property_values)
            dann = False
            if wenn:
                dann = eval_term(x[self.Property.id], self.value, "=")
            return not wenn or dann
        return the_compute_function

    def keep_name(self, ctx):
        for lang in EnumDefinition.ValueText.keys():
            ctx.keep(EnumDefinition.ValueText[lang].name, self.ValueText[lang])

    def update_constraint_texts(self, ctx):
        for lang in self.ValueText.keys():
            saved_name = EnumDefinition.ValueText[lang].name
            if saved_name in ctx.ue_args.get_attribute_names() and \
                   getattr(ctx.ue_args, saved_name) != self.ValueText[lang]:
                # Constraints, in denen der Merkmalswert als Term verwendet wird
                for c in self.ConstraintUsages:
                    # update predicate infos
                    for p in c.Predicates:
                        p.update_info_txt()
                    # update constraint infos
                    c.update_info_txt()
                # Direkt zugeordnete Constraints (Merkmalswert ist Output Merkmalswert)
                for c in self.Constraints:
                    c.update_info_txt()
                for t in self.Terms:
                    t.update_predicate_txt()
                break

    def update_variant_texts(self, ctx):
        for lang in self.ValueText.keys():
            attr_name = EnumDefinition.ValueText[lang].name
            if attr_name in ctx.ue_args.get_attribute_names() and ctx.ue_args[attr_name] != self.ValueText[lang]:
                if self.Property.ProductView:
                    self.Property.ProductView.update_variant_texts()
                else:
                    self.Property.Product.update_variant_texts()
                break

    def setup_value_register(self, ctx):
        if self.Property:
            if self.Property.data_type == 'alphanumeric':
                ctx.disable_registers(["cdbvp_number_def"])
                ctx.disable_registers(["cdbvp_boolean_def"])
            elif self.Property.data_type == 'numeric':
                ctx.disable_registers(["cdbvp_enum_def_reg"])
                ctx.disable_registers(["cdbvp_boolean_def"])
            else:
                ctx.disable_registers(["cdbvp_enum_def_reg"])
                ctx.disable_registers(["cdbvp_number_def"])

    def handle_number_value(self, ctx):
        if self.Property.data_type == 'numeric' or \
                self.Property.data_type == 'boolean':
            for lang in self.ValueText.keys():
                self.ValueText[lang] = self.name

    def check_numeric_value(self, ctx):
        # if self is a numeric value, checks that self.name
        # has only one decimal delimiter (see E023748)
        if self.Property and self.Property.data_type == "numeric" and \
                not re.match("[+-]?\d*(?:[,\.]\d+)?$", self.name):
            raise ue.Exception("cdbvp_invalid_numeric_value")

    def set_dirty(self, ctx):
        if ctx.action == "create":
            self.Property.dirty = 1

        if ctx.action == "modify":
            for lang in EnumDefinition.ValueText.keys():
                saved_name = EnumDefinition.ValueText[lang].name
                if saved_name in ctx.ue_args.get_attribute_names() and\
                 ctx.ue_args[saved_name] != getattr(self, saved_name):
                    self.Property.dirty = 1
                    break

    def fill_localized_fields(self, ctx):
        if self.Property.data_type == 'alphanumeric':
            fill_localized_fields(self.ValueTextNoFala, value=self.value_txt)

    def check_context_for_create(self, ctx):
        # Bei kontextloser Neuanlage, bspw. im Katalog bei der Formulierung von
        # Constraints und Termen ist self.Property None.
        # Das Merkmal wird benötigt, um den Typ (numerisch/alphanumerisch)
        # zu bestimmen und das entsprechende Maskenregister anzuzeigen.
        # In solchen Fällen die Neuanlage abweisen.
        if not self.Property:
            # Meldung: Die Neuanlage von Merkmalswerten ist in diesem Kontext nicht erlaubt.
            raise ue.Exception("cdbvp_err_create_propvalue")

    def check_drag_and_drop(self, ctx):
        if set(["value", "catalogue_property_object_id"]) <= set(ctx.dragged_obj.get_attribute_names()):
            if ctx.dragged_obj.catalogue_property_object_id != self.Property.catalogue_property_object_id:
                raise ue.Exception("cdbvp_err_dd_enum")

            c_value = CatalogueEnumDefinition.ByKeys(catalogue_property_object_id=ctx.dragged_obj.catalogue_property_object_id,
                                                     value=ctx.dragged_obj.value)
            if c_value and self.Property.data_type == "numeric" and c_value.CatalogueProperty.data_type == "alphanumeric":
                raise ue.Exception("cdbvp_data_type_modify")

        if ctx.dragged_obj_relationship_name == "cdbvp_property2cdbvp_enum_def":
            if self.Property.data_type == "boolean":
                raise ue.Exception("cdbvp_data_type_modify_bool")
            prop = Property.ByKeys(id=ctx.dragged_obj.id,
                                      product_object_id=ctx.dragged_obj.product_object_id)
            if prop and self.Property.data_type == "numeric" and prop.data_type == "alphanumeric":
                raise ue.Exception("cdbvp_data_type_modify", self.Property.data_type, prop.data_type)

    def update_bom_predicates(self, ctx):
        for lang in EnumDefinition.ValueText.keys():
            saved_name = EnumDefinition.ValueText[lang].name
            if saved_name in ctx.ue_args.get_attribute_names() and \
               ctx.ue_args[saved_name] != getattr(self, saved_name):
                for bt in self.BOM_Terms:
                    bt.update_predicate_txt()
                break

    def get_differences_from_catalogue(self):
        if self.CatalogueEnumValue:
            cdbvp_enum_def = entities.Entity.ByKeys(classname="cdbvp_enum_def")

            result = []
            for attr in self.COMPARE_WITH_CATALOG.keys():
                cat_attr = self.COMPARE_WITH_CATALOG[attr]
                if getattr(self, attr) != getattr(self.CatalogueEnumValue, cat_attr):
                    field_label = cdbvp_enum_def.DDFieldsByName[attr].Label['']
                    result.append((field_label,
                                   getattr(self, attr),
                                   getattr(self.CatalogueEnumValue, cat_attr)))
            return result

    def update_solver_status(self, solver):
        if solver.validate(self.get_property_values()):
            self.solver_status = SyncStatus.ok.value
        elif self.solver_status != SyncStatus.manual.value:
            self.solver_status = SyncStatus.invalid.value

    def update_variant_stati(self, ctx=None):
        if self.Property:
            self.Property.update_solver_stati()

    event_map = {(("create", "copy"), ("post_mask")): "set_name",
                 (("create", "copy"), ("pre_mask")): ("preset_name"),
                 (("modify"), "pre_mask"): ("keep_name"),
                 (("modify"), "post"): ("update_bom_predicates", "update_constraint_texts", "update_variant_texts"),
                 (("create"), "pre_mask"): ["check_context_for_create", "setup_value_register", "check_drag_and_drop"],
                 (("copy", "modify", "info", "query"), "pre_mask"): "setup_value_register",
                 (("create", "copy", "modify"), ("pre")): ("handle_number_value", "check_numeric_value"),
                 (("create", "modify"), "post"): "set_dirty",
                 (("create", "modify", "copy"), "post_mask"): "fill_localized_fields",
                 (("create", "copy", "modify", "delete"), "post"): "update_variant_stati"
                 }


class PropertyValue(Object, WithChangeLog):
    """ Merkmalsbewertung an Varianten"""

    __classname__ = "cdbvp_property_value"
    __maps_to__ = "cdbvp_property_value"

    Property = Reference_1(fProperty,
                           fPropertyValue.id,
                           fPropertyValue.product_object_id)

    EnumValue = Reference_1(fEnumDefinition,
                            fPropertyValue.id,
                            fPropertyValue.product_object_id,
                            fPropertyValue.value)

    Variant = Reference_1(fVariant,
                          fPropertyValue.variant_id,
                          fPropertyValue.product_object_id)

    def on_create_pre_mask(self, ctx):
        if ctx.dialog.product_object_id and ctx.dialog.variant_id and ctx.dialog.id and ctx.dialog.value:
            # Skip Dialog, if everything is already defined
            # Drag & Drop of Enum Value on Variant
            ctx.skip_dialog()

    @staticmethod
    def get_text(prop, value, lang="de", enum_definition=None):
        if value in [True, False]:
            return prop.Name[lang] + " " + ("\N{BALLOT BOX WITH CHECK}" if value else "\N{BALLOT BOX}")

        enum_definition = enum_definition if enum_definition is not None else prop.EnumByValue[value]
        if enum_definition is not None:
            return "%s=%s" % (prop.Name[lang], enum_definition.ValueText[lang])

        # this should not happen but this way the changes from E050619 are not changing the
        # behavior of this function
        return None

    def info_str(self, lang="de", prop=None, enum_definition=None):
        prop = prop if prop is not None else self.Property
        value = self.get_value()
        return self.get_text(prop, value, lang, enum_definition)

    def get_value(self):
        if self.disabled:
            return False
        elif self.value is not None:
            return self.value
        else:
            return True

    def updateVariantInfo(self, ctx):
        self.Variant.updateInfoText()

    def updateVariantSignature(self, ctx):
        self.Variant.updateSignature()

    def update_solver_status(self, ctx):
        self.Variant.update_solver_status()

    event_map = {
        (('create', 'copy', 'modify', 'delete'), 'post'): ('updateVariantInfo', 'updateVariantSignature', 'update_solver_status')
        }


class PropertyDependency(Object):
    """
    Zuordnung von Merkmalen zu Merkmalen. Aus den zugeordneten Merkmalen
    und deren möglichen Merkmalswerten werden durch einen Generatorlauf
    die möglichen Merkmalswerte des übergeordneten Merkmals berechnet.
    """

    __classname__ = "cdbvp_property_dependency"
    __maps_to__ = "cdbvp_property_dependency"

    ReferencingProperty = Reference_1(fProperty,
                                      fPropertyDependency.property_id,
                                      fPropertyDependency.product_object_id)

    ReferencedProperty = Reference_1(fProperty,
                                     fPropertyDependency.property_id2,
                                     fPropertyDependency.product_object_id)

    def check_self_reference(self, ctx):
        if self.ReferencedProperty == self.ReferencingProperty:
            raise ue.Exception("cdbvp_property_self_reference")

    def update_value_stati(self, ctx):
        if self.ReferencingProperty:
            self.ReferencingProperty.update_value_stati()

    def check_drag_and_drop(self, ctx):
        if ctx.dragged_obj_relationship_name == "cdbvp_product2properties":
            if self.ReferencingProperty.data_type == "boolean":
                raise ue.Exception("cdbvp_data_type_modify_bool")
            if self.ReferencingProperty.data_type == "numeric" and self.ReferencedProperty.data_type == "alphanumeric":
                raise ue.Exception("cdbvp_data_type_modify", self.ReferencingProperty.data_type, self.ReferencedProperty.data_type)

    event_map = {('create', 'pre'): 'check_self_reference',
                 ('create', 'pre_mask'): 'check_drag_and_drop',
                 (('create', 'copy', 'delete', 'modify'), 'post'): 'update_value_stati'}


class EnumDefPropertyValue(Object, WithChangeLog):
    """
    Merkmalsbewertungen für generierte Merkmalswerte aus zugeordneten Merkmalen
    """

    __classname__ = "cdbvp_enum_def_prop_value"
    __maps_to__ = "cdbvp_enum_def_prop_value"

    Property = Reference_1(fProperty,
                           fEnumDefPropertyValue.rated_property_id,
                           fEnumDefPropertyValue.product_object_id)

    def info_str(self, lang=None):
        if not lang:
            lang = 'de'
        return self.Property.EnumByValue[self.rated_property_value].ValueText[lang]


class PropertyFolder(Object, WithChangeLog):
    __classname__ = "cdbvp_property_folder"
    __maps_to__ = "cdbvp_property_folder"

    Name = LocalizedField("folder_name", fala=True)
    NameNoFala = LocalizedField("folder_name", fala=False)

    @classmethod
    def newID(cls):
        return util.nextval("cdbvp_folder_id")

    def handleDragDrop(self, ctx):
        """ Drag&Drop handler to move folders by drag & drop. """

        relships = ['cdbvp_property_folder2property_folder', 'cdbvp_product_view2folder']
        if ctx.dragged_obj_relationship_name in relships and ctx.relationship_name in relships:

            if (ctx.dragged_obj.product_object_id == self.product_object_id and
                    ctx.dragged_obj.view_id == ctx.dialog.view_id):

                if ctx.mode == "pre_mask":
                    if (ctx.relationship_name == 'cdbvp_property_folder2property_folder'
                            and ctx.dragged_obj.id == ctx.parent.id):
                        # Bei D&D auf sich selbst keine Aktion durchführen
                        ctx.keep("do_nothing", "1")

                    # Set dummy id for the new folder, which will be created by the drag & drop action.
                    # Created folder will be deleted in post mode.
                    ctx.set("id", "-1")
                    ctx.skip_dialog()

                elif ctx.mode == "pre":
                    # ensure, that object creation cannot fail due to unique constraint violation
                    pobj = self.getPersistentObject()
                    if pobj:
                        pobj.Delete()
                elif ctx.mode == "post":
                    # Set new parent_id for dragged folder and delete newly created one.
                    if "do_nothing" not in ctx.ue_args.get_attribute_names():
                        dragged_folder = PropertyFolder.ByKeys(int(ctx.dragged_obj.id),
                                                               ctx.dragged_obj.product_object_id)
                        if ctx.relationship_name == 'cdbvp_property_folder2property_folder':
                            parent_id = ctx.parent.id
                        elif ctx.relationship_name == 'cdbvp_product_view2folder':
                            parent_id = NULL
                        dragged_folder.parent_id = parent_id
                    self.getPersistentObject().Delete()
            else:
                raise ue.Exception("cdbvp_folders_views_error")

    def fill_localized_fields(self, ctx):
        fill_localized_fields(self.NameNoFala, value=self.folder_name)

    event_map = {("create", ("pre_mask", "pre", "post")): "handleDragDrop",
                 (("create", "modify", "copy"), "post_mask"): "fill_localized_fields",
                 }


class Property2Folder(Object):
    __classname__ = "cdbvp_property_folder2property"
    __maps_to__ = "cdbvp_property_folder2property"

    def checkDragDrop(self, ctx):
        relships = ['cdbvp_product_view2properties', 'cdbvp_folder2property', 'cdbvp_product2properties']
        if (ctx.dragged_obj_relationship_name in relships and ctx.relationship_name in relships and
            (ctx.dragged_obj.product_object_id != self.product_object_id or
             ctx.dragged_obj.view_id != ctx.dialog.view_id)):
            raise ue.Exception("cdbvp_properties_views_error")

    def handleDragDrop(self, ctx):
        # Merkmal von Ordner zu Ordner verschieben
        if ctx.dragged_obj_relationship_name == 'cdbvp_folder2property':
            source_folder = Property2Folder.ByKeys(self.product_object_id,
                                                   ctx.dragged_obj_parent.id,  # this is the folder id
                                                   self.property_id)
            source_folder.Delete()

    event_map = {("create", ("post")): "handleDragDrop",
                 ("create", ("pre_mask")): "checkDragDrop"
                 }


class Property2SubProductProperty(Object):
    __maps_to__ = "cdbvp_prop2subproduct_prop"
    __classname__ = "cdbvp_prop2subproduct_prop"
