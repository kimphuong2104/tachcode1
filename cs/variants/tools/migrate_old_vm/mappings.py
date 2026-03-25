#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import ast

from cs.classification import classes
from cs.classification.util import create_code
from cs.variants.tools.migrate_old_vm import LOGGER
from cs.variants.tools.migrate_old_vm.util import (
    is_old_property_alphanumeric,
    is_old_property_boolean,
    is_old_property_numeric,
    map_multilingual_attribute,
)
from cs.vp.bom import AssemblyComponent
from cs.vp.variants.bomlinks import Predicate_Expression_Solver


def map_old_variant_part_ref_to_variant_part(each_variant_part, **kwargs):
    result = {
        "maxbom_teilenummer": each_variant_part.max_bom_teilenummer,
        "maxbom_t_index": each_variant_part.max_bom_t_index,
        "teilenummer": each_variant_part.teilenummer,
        "t_index": each_variant_part.t_index,
    }

    result.update(**kwargs)
    return result


def map_variant_property_value_to_variant_classification_value(
    old_property_enum_definition, new_classification_property_entry
):
    property_type = new_classification_property_entry["property_type"]
    old_property_value = old_property_enum_definition.value_txt_de

    if property_type == "text":
        return old_property_value
    elif property_type == "float":
        return dict(
            new_classification_property_entry["value"],
            float_value=float(old_property_value),
        )
    elif property_type == "boolean":
        return old_property_value == "1"
    else:
        raise TypeError("Not supported property type '{0}'".format(property_type))


def map_old_variant_to_variant(variant, **kwargs):
    name = variant.name
    if variant.solver_status == 0:
        name += " [manual]"

    result = {
        "id": variant.id,
        "name": name,
        "cdb_cdate": variant.cdb_cdate,
        "cdb_cpersno": variant.cdb_cpersno,
        "cdb_mdate": variant.cdb_mdate,
        "cdb_mpersno": variant.cdb_mpersno,
    }

    result.update(**kwargs)
    return result


def map_bom_predicate_to_selection_condition(bom_predicate, **kwargs):
    result = {
        "cdb_cdate": bom_predicate.cdb_cdate,
        "cdb_cpersno": bom_predicate.cdb_cpersno,
        "cdb_mdate": bom_predicate.cdb_mdate,
        "cdb_mpersno": bom_predicate.cdb_mpersno,
    }

    result.update(**kwargs)

    assembly_components = AssemblyComponent.KeywordQuery(
        baugruppe=bom_predicate.baugruppe,
        b_index=bom_predicate.b_index,
        teilenummer=bom_predicate.teilenummer,
        variante=bom_predicate.variante,
        position=bom_predicate.position,
    ).Execute()

    if len(assembly_components) > 1:
        LOGGER.warning(
            "Bom predicate maps to more than one assembly component. Please review. Bom predicate: %s",
            bom_predicate.DBInfo(),
        )

    if not assembly_components:
        LOGGER.warning(
            "Bom predicate maps to no assembly component. "
            "Selection condition cannot be created. Bom predicate: %s",
            bom_predicate.DBInfo(),
        )

    for each in assembly_components:
        result.update(ref_object_id=each.cdb_object_id)
        yield result


class PredicateStringExpressionToSelectionConditionExpression(ast.NodeVisitor):
    def __init__(self):
        self.erp_codes = []

    @staticmethod
    def is_number(n):
        try:
            float(n)
            return True
        except (ValueError, TypeError):
            return False

    def visit_Name(self, node):
        if (
            node.id not in Predicate_Expression_Solver.reserved
            and not PredicateStringExpressionToSelectionConditionExpression.is_number(
                node.id
            )
        ):
            self.erp_codes.append(node.id)


def map_bom_string_predicate_to_selection_condition(
    bom_predicate, old_property_to_class_property_lookup, **kwargs
):
    visitor = PredicateStringExpressionToSelectionConditionExpression()
    bom_predicate_expression = bom_predicate.expression

    try:
        node = ast.parse(bom_predicate_expression, mode="eval")
    except SyntaxError as e:
        LOGGER.warning(
            "Bom string predicate has syntax error '%s'. Bom predicate: %s",
            str(e),
            bom_predicate.DBInfo(),
        )
        return
    visitor.visit(node)

    # Sort the erp codes reverse so that we do not replace erp codes which contain parts of others
    erp_codes = sorted(visitor.erp_codes, key=len, reverse=True)
    classification_expression = bom_predicate_expression

    # Need to do an two stage replace process.
    # Because the new classification code could also contain a part of the erp code

    # First stage: Replace erp codes with ids of the classification property
    for erp_code in erp_codes:
        try:
            classification_property = old_property_to_class_property_lookup[erp_code]
        except KeyError:
            LOGGER.warning(
                "Bom string predicate contains a non found erp code '%s' of a property. "
                "Bom predicate: %s",
                erp_code,
                bom_predicate.DBInfo(),
            )
            return

        classification_expression = classification_expression.replace(
            erp_code, classification_property.cdb_object_id
        )

    # Second stage: Replace ids of the classification properties with correct code
    for erp_code in erp_codes:
        classification_property = old_property_to_class_property_lookup[erp_code]

        classification_expression = classification_expression.replace(
            classification_property.cdb_object_id, classification_property.code
        )

    for each in map_bom_predicate_to_selection_condition(
        bom_predicate, expression=classification_expression, **kwargs
    ):
        yield each


def map_bom_term_predicate_to_selection_condition(
    bom_predicate, old_property_to_class_property_lookup, **kwargs
):
    term_parts = []
    terms = bom_predicate.Terms.Execute()

    if not terms:
        LOGGER.warning(
            'Predicate does not contain "Terms". '
            "No selection condition will be created. Predicate: %s",
            bom_predicate.DBInfo(),
        )
        return

    for each_term in terms:
        expression_class_property = old_property_to_class_property_lookup[
            each_term.Property.erp_code
        ]

        expression = map_property_enum_definition_to_classification_expression(
            each_term.PropertyValue,
            each_term.operator,
            expression_class_property,
        )

        term_parts.append(expression)

    for each in map_bom_predicate_to_selection_condition(
        bom_predicate, expression=" and ".join(term_parts), **kwargs
    ):
        yield each


def map_old_constraint_to_classification_constraint(
    old_constraint, old_property_to_class_property_lookup, **kwargs
):
    expression_class_property = old_property_to_class_property_lookup[
        old_constraint.OutputProperty.erp_code
    ]

    expression = map_property_enum_definition_to_classification_expression(
        old_constraint.OutputPropertyValue,
        old_constraint.operator,
        expression_class_property,
        old_constraint=old_constraint,
    )

    predicate_expression_parts = []
    for predicate in old_constraint.Predicates:
        term_expression_parts = []

        for term in predicate.Terms:
            term_class_property = old_property_to_class_property_lookup[
                term.Property.erp_code
            ]

            term_expression = map_property_enum_definition_to_classification_expression(
                term.PropertyValue,
                term.operator,
                term_class_property,
                old_constraint=old_constraint,
            )

            term_expression_parts.append(term_expression)

        predicate_expression_parts.append(
            "({0})".format(" and ".join(term_expression_parts))
        )

    when_condition = " or ".join(predicate_expression_parts)

    result = {
        "when_condition": when_condition,
        "expression": expression,
        # constraint_type
        # 1	Äquivalenz
        # 2	Implikation
        "equivalent": old_constraint.constraint_type == 1,
    }

    result.update(**kwargs)
    return result


def map_property_enum_definition_to_classification_expression(
    old_property_enum_definition,
    old_property_operator,
    class_property,
    old_constraint=None,
):
    if old_property_operator == "\N{BALLOT BOX WITH CHECK}":
        if old_constraint is not None and not isinstance(
            class_property, classes.BooleanClassProperty
        ):
            LOGGER.warning(
                'Constraint contains an expression which has a "BALLOT BOX WITH CHECK" '
                "but is not of boolean type. Please review. Constraint: %s",
                old_constraint.DBInfo(),
            )

        old_property_operator = "is not"
        old_property_value = False
    elif old_property_operator == "\N{BALLOT BOX}":
        if old_constraint is not None and not isinstance(
            class_property, classes.BooleanClassProperty
        ):
            LOGGER.warning(
                'Constraint contains an expression which has a "BALLOT BOX" '
                "but is not of boolean type. Please review. Constraint: %s",
                old_constraint.DBInfo(),
            )

        old_property_operator = "is"
        old_property_value = False
    else:
        old_property_value = old_property_enum_definition.value_txt_de

        if isinstance(class_property, classes.TextClassProperty):
            old_property_value = '"{0}"'.format(old_property_value)
        elif isinstance(class_property, classes.BooleanClassProperty):
            old_property_value = old_property_value == "1"

        if old_property_operator == "=":
            old_property_operator = "=="

    return "{0} {1} {2}".format(
        class_property.code, old_property_operator, old_property_value
    )


def map_attributes_product_to_variability_model(product, **kwargs):
    result = {
        "cdb_cdate": product.cdb_cdate,
        "cdb_cpersno": product.cdb_cpersno,
        "cdb_mdate": product.cdb_mdate,
        "cdb_mpersno": product.cdb_mpersno,
    }

    result.update(**kwargs)
    return result


def map_attributes_product_to_classification_class(product, **kwargs):
    result = {
        "code": create_code(product.code),
        "name": product.code,
        "external_code": product.erp_code,
        "is_abstract": 0,
        "is_exclusive": 0,
        "cdb_objektart": "cs_classification_class",
        "cdb_status_txt": "Released",
        "status": 200,
    }

    result.update(
        map_multilingual_attribute("name", product, "name", fallback_value=product.code)
    )

    result.update(**kwargs)
    return result


def map_attributes_property_to_classification_catalog_property(
    old_property, options, **kwargs
):
    is_boolean = is_old_property_boolean(old_property)

    result = {
        "code": "{0}{1}".format(
            old_property.erp_code,
            "_" + old_property.data_type
            if options.postfix_catalog_prop_code_with_data_type
            else "",
        ),
        "external_code": old_property.erp_code,
        "has_enum_values": 1 if not is_boolean else 0,
        "is_enum_only": 1 if not is_boolean else 0,
        "is_multivalued": 0,
        "is_unit_changeable": 0,
        "multiline": 0,
        "cdb_objektart": "cs_property",
        "cdb_status_txt": "Released",
        "status": 200,
    }
    result.update(map_multilingual_attribute("label", old_property, "property_name"))
    result.update(map_multilingual_attribute("name", old_property, "property_name"))

    cdbvp_property_txt = old_property.GetText("cdbvp_property_txt")
    if len(cdbvp_property_txt) > 250:
        LOGGER.warning(
            "Description text is too long und is truncated to 250 chars for property '%s'",
            old_property.DBInfo(),
        )
        cdbvp_property_txt = cdbvp_property_txt[:250]

    result.update(
        map_multilingual_attribute(
            "prop_description",
            old_property,
            "cdbvp_property_txt",
            fallback_value=cdbvp_property_txt,
        )
    )

    result.update(**kwargs)
    return result


def map_attributes_catalog_property_to_classification_catalog_property(
    old_catalog_property, **kwargs
):
    is_boolean = is_old_property_boolean(old_catalog_property)

    result = {
        "code": old_catalog_property.sap_property,
        "external_code": old_catalog_property.sap_property,
        "has_enum_values": 1 if not is_boolean else 0,
        "is_enum_only": 1 if not is_boolean else 0,
        "is_multivalued": 0,
        "is_unit_changeable": 0,
        "multiline": 0,
        "cdb_objektart": "cs_property",
        "cdb_status_txt": "Released",
        "status": 200,
    }
    result.update(map_multilingual_attribute("label", old_catalog_property, "name"))
    result.update(map_multilingual_attribute("name", old_catalog_property, "name"))

    cdbvp_catalogue_property_txt = old_catalog_property.GetText(
        "cdbvp_catalogue_property_txt"
    )
    if len(cdbvp_catalogue_property_txt) > 250:
        LOGGER.warning(
            "Description text is too long und is truncated to 250 chars for catalog property '%s'",
            old_catalog_property.DBInfo(),
        )
        cdbvp_catalogue_property_txt = cdbvp_catalogue_property_txt[:250]

    result.update(
        map_multilingual_attribute(
            "prop_description",
            old_catalog_property,
            "cdbvp_catalogue_property_txt",
            fallback_value=cdbvp_catalogue_property_txt,
        )
    )

    result.update(**kwargs)
    return result


def map_attributes_property_to_classification_class_property_value(
    enum_value, old_property, **kwargs
):
    result = {
        "is_active": 1,
    }

    if is_old_property_alphanumeric(old_property):
        result["text_value"] = enum_value.value_txt_de
        result.update(map_multilingual_attribute("label", enum_value, "value_txt"))
    elif is_old_property_numeric(old_property):
        result["float_value"] = float(enum_value.value_txt_de)
    else:
        raise ValueError(
            "Not supported property data_type: {0}".format(old_property.data_type)
        )

    result.update(**kwargs)
    return result


def map_attributes_property_to_classification_class_property(old_property, **kwargs):
    is_boolean = is_old_property_boolean(old_property)

    result = {
        "code": old_property.erp_code,
        "external_code": old_property.erp_code,
        "for_variants": old_property.variant_relevant,
        "has_enum_values": 1 if not is_boolean else 0,
        "is_editable": 1,
        "is_enum_only": 1 if not is_boolean else 0,
        "is_mandatory": 0,
        "is_visible": 1,
        "multiline": 0,
    }
    result.update(map_multilingual_attribute("name", old_property, "property_name"))

    cdbvp_property_txt = old_property.GetText("cdbvp_property_txt")
    if len(cdbvp_property_txt) > 250:
        LOGGER.warning(
            "Description text is too long und is truncated to 250 chars for property '%s'",
            old_property.DBInfo(),
        )
        cdbvp_property_txt = cdbvp_property_txt[:250]

    result.update(
        map_multilingual_attribute(
            "prop_description",
            old_property,
            "cdbvp_property_txt",
            fallback_value=cdbvp_property_txt,
        )
    )

    result.update(**kwargs)
    return result
