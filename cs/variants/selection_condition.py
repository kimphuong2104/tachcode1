# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
from cdb import ue, util
from cdb.objects import Forward, Reference_1, core
from cdbwrapc import CDBClassDef
from cs.classification.computations import property_codes_used_in_expression
from cs.variants import VariabilityModel

fSelectionCondition = Forward("cs.variants.selection_condition.SelectionCondition")


def get_expression_dd_field_length():
    expression_def = CDBClassDef("cs_selection_condition").getAttributeDefinition(
        "expression"
    )
    return expression_def.getColumnInfo().length()


def is_expression_long(expression):
    expression_dd_field_length = get_expression_dd_field_length()
    return len(expression) > expression_dd_field_length


def map_expression_to_correct_attribute(expression):
    if is_expression_long(expression):
        return {"expression": None, "cs_sc_expression_long": expression}

    return {"expression": expression, "cs_sc_expression_long": None}


def get_expression_from_record(selection_condition_record):
    result = selection_condition_record.expression
    if result == "" or result is None:
        return get_expression_long(selection_condition_record.cdb_object_id)
    else:
        return result


def get_expression_long(cdb_object_id):
    return util.text_read(
        "cs_sc_expression_long",
        ["cdb_object_id"],
        [cdb_object_id],
    )


class SelectionCondition(core.Object):
    __maps_to__ = "cs_selection_condition"
    __classname__ = "cs_selection_condition"

    VariabilityModel = Reference_1(
        VariabilityModel,
        VariabilityModel.cdb_object_id == fSelectionCondition.variability_model_id,
    )

    def get_expression(self):
        return get_expression_from_record(self)

    @classmethod
    def new_id(cls):
        return util.nextval("cs_selection_condition")

    def check_expression(self, ctx):
        from cs.variants.api import VariantsClassification

        expression = getattr(ctx.dialog, "expression", None)
        if expression == "" or expression is None:
            expression = getattr(ctx.dialog, "cs_sc_expression_long")

        try:
            used_property_codes = property_codes_used_in_expression(expression)
        except SyntaxError as ex:
            raise ue.Exception("cs_variants_sc_expression_syntax_error", str(ex))

        # For modify variability_model_id is not needed in dialog then its only in "self"
        variability_model_id = getattr(
            ctx.dialog, "variability_model_id", self.variability_model_id
        )
        variability_model_class_code = VariabilityModel.ByKeys(
            cdb_object_id=variability_model_id
        ).class_code
        variants_classification = VariantsClassification(
            class_codes=[variability_model_class_code]
        )
        variant_driving_properties = (
            variants_classification.get_variant_driving_properties()
        )

        not_variant_driving_properties = set()
        for each in used_property_codes:
            if each not in variant_driving_properties:
                not_variant_driving_properties.add(each)

        if not_variant_driving_properties:
            raise ue.Exception(
                "cs_variants_sc_expression_non_variant_driving_properties",
                " - {0}".format("\n - ".join(not_variant_driving_properties)),
            )

    event_map = {
        (("create", "copy", "modify"), "pre"): "check_expression",
    }
