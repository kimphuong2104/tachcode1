#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved

from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_N
from cdb.objects import Forward
from cdb.objects import LocalizedField
from cdb import sqlapi
from cdb import util

from cs.vp.variants.vptools import WithChangeLog

fProductView = Forward(__name__ + ".ProductView")
fVariant = Forward("cs.vp.variants.Variant")
fProduct = Forward("cs.vp.products.Product")
fProperty = Forward("cs.vp.variants.properties.Property")
fPropertyValue = Forward("cs.vp.variants.properties.PropertyValue")
fConstraint = Forward("cs.vp.variants.constraints.Constraint")


class ProductView(Object, WithChangeLog):
    __maps_to__ = "cdbvp_product_view"
    __classname__ = "cdbvp_product_view"

    Variants = Reference_N(fVariant,
                           fVariant.product_object_id == fProductView.product_object_id,
                           fVariant.view_id == fProductView.id)

    Properties = Reference_N(fProperty,
                             fProperty.product_object_id == fProductView.product_object_id,
                             fProperty.view_id == fProductView.id)

    _VariantDrivingProperties = Reference_N(fProperty,
                                            fProperty.product_object_id == fProductView.product_object_id,
                                            fProperty.view_id == fProductView.id,
                                            fProperty.variant_relevant > 0,
                                            order_by=fProperty.position)

    def _get_variant_driving_properties(self):
        return [prop for prop in self._VariantDrivingProperties
                if len(prop.GeneratorRelevantEnumValues) > 0]
    VariantDrivingProperties = ReferenceMethods_N(fProperty, _get_variant_driving_properties)

    Constraints = Reference_N(fConstraint,
                              fConstraint.product_object_id == fProductView.product_object_id,
                              fConstraint.view_id == fProductView.id)

    Product = Reference_1(fProduct,
                          fProduct.cdb_object_id == fProductView.product_object_id)

    Name = LocalizedField("name", fala=True)
    NameNoFala = LocalizedField("name", fala=False)

    def isMaxBOMView(self):
        return self.max_bom_evaluation == 1

    def getVariantTableAdapter(self, **kwargs):
        from cs.vp.variants.varianttableadapters import ViewAdapter
        return ViewAdapter(self.Product, self)

    @classmethod
    def newViewID(cls):
        return util.nextval("cdbvp_view_id")

    def setMaxBOMCheckboxReadonly(self, ctx):
        if not self.Product or (self.Product.MaxBOMView and self.id != self.Product.MaxBOMView.id):
            ctx.set_readonly("max_bom_evaluation")
        else:
            # Wenn irgendwelche Merkmale bewertet sind (vom Produkt oder einer Sicht), kann die
            # Einstellung nicht mehr geändert werden.
            t = sqlapi.SQLselect("count(*) from cdbvp_property where product_object_id = '%s' "
                                 "and id in (select property_id from cdbvp_bom_term where product_object_id = '%s' "
                                 "union select property_id from cdbvp_bom_mapping where vpm_product_object_id = '%s')"
                                 % (self.product_object_id, self.product_object_id, self.product_object_id))
            if sqlapi.SQLinteger(t, 0, 0) > 0:
                ctx.set_readonly("max_bom_evaluation")

    def fill_localized_fields(self, ctx):
        from cs.vp.variants.properties import fill_localized_fields
        fill_localized_fields(self.NameNoFala)

    def update_variant_texts(self):
        for v in self.Variants:
            v.updateInfoText()

    def check_view_id(self, ctx):
        """ If the id is 0, increase it by 1. Properties with view_id=0
            are those without views.
        """
        if self.id == 0:
            self.id = self.newViewID()

    event_map = {('create', 'post_mask'): "check_view_id",
                 (('create', 'copy', 'modify'), ('pre_mask')): "setMaxBOMCheckboxReadonly",
                 (("create", "modify", "copy"), "post_mask"): "fill_localized_fields",
                }
