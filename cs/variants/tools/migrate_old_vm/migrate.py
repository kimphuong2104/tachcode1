#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import json

from cdb import ddl
from cdb.cdbuuid import create_uuid
from cdb.sqlapi import SQLupdate, quote
from cdb.transactions import Transaction
from cs.classification import catalog, classes, constraints
from cs.classification.api import (
    get_classification,
    get_new_classification,
    rebuild_classification,
    update_classification,
)
from cs.classification.catalog import _set_property_values_active_state
from cs.classification.classes import ClassProperty
from cs.classification.util import check_code, isclose
from cs.variants import VariabilityModel, VariabilityModelPart, Variant, VariantPart
from cs.variants.api.constants_api import CLASSIFICATION_FLAG_FOR_INSTANTIATOR
from cs.variants.selection_condition import SelectionCondition, is_expression_long
from cs.variants.tools.migrate_old_vm import LOGGER
from cs.variants.tools.migrate_old_vm.mappings import (
    map_attributes_catalog_property_to_classification_catalog_property,
    map_attributes_product_to_classification_class,
    map_attributes_product_to_variability_model,
    map_attributes_property_to_classification_catalog_property,
    map_attributes_property_to_classification_class_property,
    map_attributes_property_to_classification_class_property_value,
    map_bom_string_predicate_to_selection_condition,
    map_bom_term_predicate_to_selection_condition,
    map_old_constraint_to_classification_constraint,
    map_old_variant_part_ref_to_variant_part,
    map_old_variant_to_variant,
    map_variant_property_value_to_variant_classification_value,
)
from cs.variants.tools.migrate_old_vm.util import (
    get_property_catalog_class,
    get_property_class_class,
    get_property_value_class,
)
from cs.vp.products import ProductPart
from cs.vp.variants.bomlinks import BOM_String_Predicate, BOM_Term_Predicate
from cs.vp.variants.properties import EnumDefinition


class CatalogPropertiesChecker:
    def __init__(self, catalog_properties):
        self.catalog_properties = catalog_properties
        self.used_properties = []

    def __len__(self):
        return len(self.catalog_properties)

    def exists_catalog_property(self, enum_value_attributes):
        # We only have text and float values in old vm (boolean have fixed values that do not need conversion)
        try:
            enum_value = enum_value_attributes["text_value"]

            def compare_func(x):
                return x.value == enum_value

        except KeyError:
            enum_value = enum_value_attributes["float_value"]

            def compare_func(x):
                return isclose(x.value["float_value"], enum_value)

        for each in self.catalog_properties:
            if compare_func(each):
                self.used_properties.append(each)
                return True

        return False

    def get_unused_properties(self):
        return [
            each for each in self.catalog_properties if each not in self.used_properties
        ]


class CdbObjectIdMigrator:
    def __init__(self):
        self.table_name = "CS_VARIANTS_ID_MIGRATION"
        self.data = []

        self.table = self.create_table()

    def create_table(self):
        table = ddl.Table(
            self.table_name,
            [
                ddl.Char("original_cdb_object_id", 40),
                ddl.Char("new_cdb_object_id", 40),
                ddl.Char("classname", 32),
                ddl.PrimaryKey("original_cdb_object_id", "new_cdb_object_id"),
            ],
        )
        if not table.exists():
            table.create()

        return table

    def assign_new_cdb_object_id(self, object_to_assign_new_id):
        original_cdb_object_id = object_to_assign_new_id["cdb_object_id"]
        new_cdb_object_id = create_uuid()
        classname = object_to_assign_new_id.GetClassname()
        object_table_name = object_to_assign_new_id.GetTableName()

        self.table.insert(
            original_cdb_object_id=original_cdb_object_id,
            new_cdb_object_id=new_cdb_object_id,
            classname=classname,
        )

        SQLupdate(
            """{object_table_name} SET cdb_object_id='{new_cdb_object_id}'
            WHERE cdb_object_id='{original_cdb_object_id}'""".format(
                object_table_name=quote(object_table_name),
                original_cdb_object_id=quote(original_cdb_object_id),
                new_cdb_object_id=quote(new_cdb_object_id),
            )
        )

        SQLupdate(
            "cdb_object SET id='{new_cdb_object_id}' WHERE id='{original_cdb_object_id}'".format(
                original_cdb_object_id=quote(original_cdb_object_id),
                new_cdb_object_id=quote(new_cdb_object_id),
            )
        )

        return original_cdb_object_id


def create_class_property_values(
    cdb_object_id_migrator, class_property, old_property, options
):
    property_catalog_value_class = get_property_value_class(old_property)
    if property_catalog_value_class is not None:
        catalog_properties_checker = CatalogPropertiesChecker(
            class_property.Property.PropertyValues.Execute()
        )

        for enum_index, enum_value in enumerate(old_property.EnumValues):
            enum_value_attributes = (
                map_attributes_property_to_classification_class_property_value(
                    enum_value,
                    old_property,
                    property_object_id=class_property.cdb_object_id,
                    pos=10 * (enum_index + 1 + len(catalog_properties_checker)),
                )
            )

            if catalog_properties_checker.exists_catalog_property(
                enum_value_attributes
            ):
                continue

            if options.keep_cdb_object_id_of_enum_def:
                cdb_object_id = cdb_object_id_migrator.assign_new_cdb_object_id(
                    enum_value
                )
                enum_value_attributes["cdb_object_id"] = cdb_object_id

            LOGGER.debug(
                "\tGenerating catalog property value with attributes %s",
                enum_value_attributes,
            )
            property_catalog_value_class.CreateNoResult(**enum_value_attributes)

        property_values = catalog_properties_checker.get_unused_properties()
        _set_property_values_active_state(class_property, property_values, 0)


def create_class_property(
    cdb_object_id_migrator,
    catalog_property,
    classification_class,
    old_property,
    options,
):
    if not old_property.EnumValues:
        LOGGER.warning(
            "Property with no enum values found will not create an class property for it. %s",
            old_property.DBInfo(),
        )
        return None

    property_class_class = get_property_class_class(old_property)
    class_property_attributes = (
        map_attributes_property_to_classification_class_property(old_property)
    )

    if options.keep_cdb_object_id_of_property:
        cdb_object_id = cdb_object_id_migrator.assign_new_cdb_object_id(old_property)
        class_property_attributes["cdb_object_id"] = cdb_object_id

    if not check_code(class_property_attributes["code"]):
        raise ValueError(
            "Code of class property is not a valid: {0}".format(
                class_property_attributes["code"]
            )
        )

    existing_class_properties_with_same_code = ClassProperty.KeywordQuery(
        code=class_property_attributes["code"]
    )
    if existing_class_properties_with_same_code:
        for each in existing_class_properties_with_same_code:
            if not isinstance(each, property_class_class):
                if options.postfix_class_prop_code_with_different_type:
                    class_property_attributes["code"] = "{0}_{1}".format(
                        class_property_attributes["code"], old_property.data_type
                    )
                else:
                    raise ValueError(
                        "Code of class property is already in use with a different datatype. "
                        "code: '{0}' wanted datatype: {1} already existing datatype: {2}".format(
                            class_property_attributes["code"],
                            property_class_class,
                            type(each),
                        )
                    )

    LOGGER.debug(
        "\tGenerating class property of type %s with attributes %s",
        property_class_class,
        class_property_attributes,
    )
    class_property = property_class_class.NewPropertyFromCatalog(
        catalog_property,
        classification_class.cdb_object_id,
        **class_property_attributes
    )

    create_class_property_values(
        cdb_object_id_migrator, class_property, old_property, options
    )

    return class_property


def create_catalog_property_values(catalog_property, old_property):
    property_catalog_value_class = get_property_value_class(old_property)
    if property_catalog_value_class is not None:
        for enum_index, enum_value in enumerate(old_property.Values):
            enum_value_attributes = (
                map_attributes_property_to_classification_class_property_value(
                    enum_value,
                    old_property,
                    property_object_id=catalog_property.cdb_object_id,
                    pos=10 * (enum_index + 1),
                )
            )
            LOGGER.debug(
                "\tGenerating catalog property value with attributes %s",
                enum_value_attributes,
            )
            property_catalog_value_class.CreateNoResult(**enum_value_attributes)


def create_catalog_property(old_property, options):
    old_catalog_property = old_property.CatalogueProperty

    is_difference_in_data_type = (
        old_catalog_property is not None
        and old_catalog_property.data_type != old_property.data_type
    )

    if is_difference_in_data_type:
        LOGGER.warning(
            (
                "Property and catalog property differ in type. "
                "The catalog property will not be used and a new property gets created. "
                "property: %s catalog property: %s"
            ),
            old_property.DBInfo(),
            old_catalog_property.DBInfo(),
        )

    if old_catalog_property is None or is_difference_in_data_type:
        catalog_property_attributes = (
            map_attributes_property_to_classification_catalog_property(
                old_property, options
            )
        )
    else:
        catalog_property_attributes = (
            map_attributes_catalog_property_to_classification_catalog_property(
                old_catalog_property
            )
        )

    catalog_property_class = get_property_catalog_class(old_property)
    catalog_property = catalog_property_class.ByKeys(
        code=catalog_property_attributes["code"]
    )

    if catalog_property is not None:
        LOGGER.debug("\tReuse catalog property %s", catalog_property)
        return catalog_property

    if not check_code(catalog_property_attributes["code"]):
        raise ValueError(
            "Code of class property is not a valid: {0}".format(
                catalog_property_attributes["code"]
            )
        )

    catalog_property_class = get_property_catalog_class(old_property)
    LOGGER.debug(
        "\tGenerating catalog property of type %s with attributes %s",
        catalog_property_class,
        catalog_property_attributes,
    )
    catalog_property = catalog_property_class.Create(**catalog_property_attributes)
    args = {
        "folder_id": catalog.PropertyFolder.ALL_PROPERTIES_FOLDER,
        "property_id": catalog_property.cdb_object_id,
    }
    catalog.PropertyFolderAssignment.Create(**args)

    if old_catalog_property is not None and not is_difference_in_data_type:
        create_catalog_property_values(catalog_property, old_catalog_property)

    return catalog_property


def create_classification_definition(cdb_object_id_migrator, product, options):
    attributes_classification_class = map_attributes_product_to_classification_class(
        product
    )

    if not check_code(attributes_classification_class["code"]):
        raise ValueError(
            "Code of classification class is not a valid: {0}".format(
                attributes_classification_class["code"]
            )
        )

    LOGGER.debug(
        "\tGenerating classification class with attributes %s",
        attributes_classification_class,
    )
    classification_class = classes.ClassificationClass.Create(
        **attributes_classification_class
    )

    old_property_to_class_property_lookup = {}

    for old_property in product.AllProperties:
        catalog_property = create_catalog_property(old_property, options)
        class_property = create_class_property(
            cdb_object_id_migrator,
            catalog_property,
            classification_class,
            old_property,
            options,
        )

        old_property_to_class_property_lookup[old_property.erp_code] = class_property

    return classification_class, old_property_to_class_property_lookup


def create_variability_model(
    product,
    classification_class,
):
    attributes_variability_model = map_attributes_product_to_variability_model(
        product,
        product_object_id=product.cdb_object_id,
        class_object_id=classification_class.cdb_object_id,
    )

    LOGGER.debug(
        "\tGenerating variability model with attributes %s",
        attributes_variability_model,
    )
    variability_model = VariabilityModel.Create(**attributes_variability_model)
    variability_model.generate_class_applicability()

    for max_bom in product.MaxBoms:
        if max_bom["configurable"] == 1:
            LOGGER.debug(
                "\tGenerating MaxBOM teilenummer: %s t_index: %s for variability model %s",
                max_bom.teilenummer,
                max_bom.t_index,
                variability_model.DBInfo(),
            )

            VariabilityModelPart.CreateNoResult(
                variability_model_object_id=variability_model.cdb_object_id,
                teilenummer=max_bom.teilenummer,
                t_index=max_bom.t_index,
            )
        else:
            LOGGER.debug(
                "\tGenerating product part teilenummer: %s t_index: %s",
                max_bom.teilenummer,
                max_bom.t_index,
            )

            ProductPart.CreateNoResult(
                product_object_id=product.cdb_object_id,
                teilenummer=max_bom.teilenummer,
                t_index=max_bom.t_index,
            )

    return variability_model


class SelectionConditionCreator:
    def __init__(self):
        self.data = {}

    def create_selection_condition(
        self, attributes_selection_condition, variability_model
    ):
        selection_condition_keys = (
            variability_model.cdb_object_id,
            attributes_selection_condition["ref_object_id"],
        )
        if selection_condition_keys in self.data:
            self.data[selection_condition_keys]["expression"].append(
                attributes_selection_condition["expression"]
            )
        else:
            self.data[selection_condition_keys] = attributes_selection_condition
            self.data[selection_condition_keys]["expression"] = [
                self.data[selection_condition_keys]["expression"]
            ]

    def commit(self):
        for each in self.data.values():
            expression_parts = each["expression"]
            if len(expression_parts) == 1:
                expression = expression_parts[0]
            else:
                expression = "({0})".format(") or\n(".join(expression_parts))

            is_expression_long_result = is_expression_long(expression)
            if is_expression_long_result:
                each["expression"] = None
            else:
                each["expression"] = expression

            LOGGER.info(
                "\tGenerating selection condition with attributes %s",
                each,
            )
            new_selection_condition = SelectionCondition.Create(**each)
            if is_expression_long_result:
                new_selection_condition.SetText("cs_sc_expression_long", expression)


def create_selection_condition(attributes_selection_condition, variability_model):
    selection_condition = SelectionCondition.ByKeys(
        variability_model_id=variability_model.cdb_object_id,
        ref_object_id=attributes_selection_condition["ref_object_id"],
    )
    if selection_condition is None:
        LOGGER.info(
            "\tGenerating selection condition with attributes %s",
            attributes_selection_condition,
        )
        SelectionCondition.Create(**attributes_selection_condition)
    else:
        updated_expression = "({0}) or ({1})".format(
            selection_condition.expression,
            attributes_selection_condition["expression"],
        )
        LOGGER.info(
            "\tUpdating selection condition expression %s",
            updated_expression,
        )
        selection_condition.Update(expression=updated_expression)


def create_selection_conditions(
    product, variability_model, old_property_to_class_property_lookup
):
    selection_condition_creator = SelectionConditionCreator()
    for bom_predicate in product.BOM_Predicates:
        if isinstance(bom_predicate, BOM_Term_Predicate):
            attributes_selection_condition_iter = (
                map_bom_term_predicate_to_selection_condition(
                    bom_predicate,
                    old_property_to_class_property_lookup,
                    variability_model_id=variability_model.cdb_object_id,
                )
            )
        elif isinstance(bom_predicate, BOM_String_Predicate):
            attributes_selection_condition_iter = (
                map_bom_string_predicate_to_selection_condition(
                    bom_predicate,
                    old_property_to_class_property_lookup,
                    variability_model_id=variability_model.cdb_object_id,
                )
            )
        else:
            raise TypeError(
                "Bom predicate of type '{0}' is not supported".format(
                    type(bom_predicate)
                )
            )

        for attributes_selection_condition in attributes_selection_condition_iter:
            # None can be returned if an error occurs
            if attributes_selection_condition is not None:
                selection_condition_creator.create_selection_condition(
                    attributes_selection_condition, variability_model
                )

    selection_condition_creator.commit()


def create_variants(
    cdb_object_id_migrator,
    product,
    variability_model,
    old_property_to_class_property_lookup,
    options,
):
    # pylint: disable=too-many-locals
    new_classification_structure = get_new_classification(
        [variability_model.ClassificationClass.code]
    )

    for variant in product.Variants:
        if variant.solver_status == 0:
            LOGGER.warning(
                "Manual created variant detected. Will be probably flagged invalid after migration. "
                "Please review. Variant: %s",
                variant.DBInfo(),
            )

        attributes_variant = map_old_variant_to_variant(
            variant,
            variability_model_id=variability_model.cdb_object_id,
        )

        if options.keep_cdb_object_id_of_variant:
            cdb_object_id = cdb_object_id_migrator.assign_new_cdb_object_id(variant)
            attributes_variant["cdb_object_id"] = cdb_object_id

        LOGGER.debug(
            "\tGenerating variant with attributes %s",
            attributes_variant,
        )
        migrated_variant = Variant.Create(**attributes_variant)
        variant_classification_structure = dict(new_classification_structure)

        for each_property_value in variant.PropertyValues:
            each_property = each_property_value.Property
            each_enum_definition = EnumDefinition.ByKeys(
                id=each_property.id,
                product_object_id=product.cdb_object_id,
                value=each_property_value.value,
            )

            new_classification_code = old_property_to_class_property_lookup[
                each_property.erp_code
            ].code

            new_classification_property_entry = variant_classification_structure[
                "properties"
            ][new_classification_code][0]

            new_classification_value = (
                map_variant_property_value_to_variant_classification_value(
                    each_enum_definition,
                    new_classification_property_entry,
                )
            )

            new_classification_property_entry["value"] = new_classification_value

        LOGGER.debug(
            "\tSetting variant classification %s",
            variant_classification_structure,
        )
        update_classification(migrated_variant, variant_classification_structure)

        for each_variant_part in variant.PartsRefs:
            attributes_variant_part = map_old_variant_part_ref_to_variant_part(
                each_variant_part,
                variability_model_id=variability_model.cdb_object_id,
                variant_id=variant.id,
            )
            LOGGER.debug(
                "\tGenerating variant part with attributes %s",
                attributes_variant_part,
            )
            VariantPart.CreateNoResult(**attributes_variant_part)

            existing_classification = get_classification(each_variant_part.Part)
            extended_classification = rebuild_classification(
                existing_classification,
                new_classes=[variability_model.ClassificationClass.code],
            )

            for property_key, property_entries in variant_classification_structure[
                "properties"
            ].items():
                extended_classification["properties"][property_key] = property_entries

            # TODO: think about another way to provide information to classification signal
            # that this should not check
            extended_classification[CLASSIFICATION_FLAG_FOR_INSTANTIATOR] = True

            LOGGER.debug(
                "\tUpdate classification of variant part: %s",
                extended_classification,
            )
            update_classification(each_variant_part.Part, extended_classification)


def create_classification_constraints(
    product,
    classification_class,
    old_property_to_class_property_lookup,
):
    for old_constraint in product.AllConstraints:
        attributes_classification_constraint = (
            map_old_constraint_to_classification_constraint(
                old_constraint,
                old_property_to_class_property_lookup,
                classification_class_id=classification_class.cdb_object_id,
            )
        )

        LOGGER.debug(
            "\tGenerating classification constraint with attributes %s",
            attributes_classification_constraint,
        )
        constraints.Constraint.CreateNoResult(**attributes_classification_constraint)


def save_migrated_product_codes(product_code):
    try:
        with open("migrated_products.json", "r", encoding="utf-8") as file_handle:
            migrated_products = json.load(file_handle)
    except IOError:
        migrated_products = []

    migrated_products.append(product_code)

    with open("migrated_products.json", "w", encoding="utf-8") as file_handle:
        json.dump(migrated_products, file_handle, indent=4)


def migrate_product(product, options):
    if not product.VariantDrivingProperties:
        LOGGER.info(
            "Product '%s' does not contain variant driving properties -> no migration",
            product.code,
        )
        return

    with Transaction():
        LOGGER.info(
            "Migrating Product '%s'",
            product.code,
        )

        cdb_object_id_migrator = CdbObjectIdMigrator()

        (
            classification_class,
            old_property_to_class_property_lookup,
        ) = create_classification_definition(cdb_object_id_migrator, product, options)
        variability_model = create_variability_model(
            product,
            classification_class,
        )
        create_selection_conditions(
            product, variability_model, old_property_to_class_property_lookup
        )
        create_variants(
            cdb_object_id_migrator,
            product,
            variability_model,
            old_property_to_class_property_lookup,
            options,
        )
        create_classification_constraints(
            product, classification_class, old_property_to_class_property_lookup
        )

        save_migrated_product_codes(product.code)
        LOGGER.info(
            "Migrating Product '%s' finished",
            product.code,
        )


def migrate_old_vm(
    products,
    options,
):
    try:
        LOGGER.info("Migration started")

        if options.transaction_over_all_products:
            with Transaction():
                for each in products:
                    migrate_product(
                        each,
                        options,
                    )
        else:
            for each in products:
                migrate_product(
                    each,
                    options,
                )

        LOGGER.info("Migration finished")
    except Exception as ex:
        LOGGER.exception(ex)
        raise ex


def reset_all_bom_item_old_vm_attributes():
    SQLupdate("einzelteile SET cdbvp_positionstyp=NULL, cdbvp_has_condition=NULL")
