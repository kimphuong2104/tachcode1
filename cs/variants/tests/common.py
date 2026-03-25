# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import collections
import time
from decimal import Decimal

import mock
from requests.exceptions import ConnectionError as RequestsConnectionError

from cdb import constants, testcase, validationkit
from cdb.objects import ByID, core, operations
from cdb.testcase import without_error_logging
from cdb.validationkit import operation
from cs.classification import api as classification_api
from cs.classification import catalog, classes, constraints, units, util
from cs.classification.solr import SolrCommandException
from cs.classification.validation import ClassificationValidator
from cs.variants import (
    VariabilityModel,
    VariabilityModelPart,
    VariantPart,
    VariantsView,
)
from cs.variants import api as variants_api
from cs.variants.items import AssemblyComponent
from cs.variants.selection_condition import (
    SelectionCondition,
    map_expression_to_correct_attribute,
)
from cs.vp import items
from cs.vp.products import Product

ITEM_CATEGORY = "Baukasten"


def generate_product(preset=None, user_input=None):
    if preset is None:
        preset = {}
    if user_input is None:
        user_input = {}
    preset_default = {
        "code": "Test product",
        "objektart": "cdbvp_product",
        "cdb_status_txt": "Draft",
        "status": 0,
    }
    preset_default.update(preset)
    user_input_default = {}
    user_input_default.update(user_input)
    return operation(
        constants.kOperationNew,
        Product,
        preset=preset_default,
        user_input=user_input_default,
    )


def generate_part(presets_custom=None, user_input_custom=None, use_subclass=False):
    if presets_custom is None:
        presets_custom = {}
    if user_input_custom is None:
        user_input_custom = {}

    preset = {
        "benennung": "TEST ITEM",
        "teilenummer": "#CON-VP-",
        "t_kategorie": ITEM_CATEGORY,
        "t_bereich": "Engineering",
        "mengeneinheit": "qm",
        "is_imprecise": 0,
    }
    preset.update(presets_custom)
    user_input = {}
    user_input.update(user_input_custom)
    handle = operation(
        constants.kOperationNew,
        "part" if not use_subclass else "part_subclass",
        preset=preset,
        user_input=user_input,
    )
    return core.object_from_handle(handle)


def generate_assembly_component(
    assembly, item=None, presets_custom=None, user_input_custom=None
):
    if presets_custom is None:
        presets_custom = {}
    if user_input_custom is None:
        user_input_custom = {}
    if item is None:
        item = generate_part()

    preset = {
        "teilenummer": item.teilenummer,
        "t_index": item.t_index,
        "baugruppe": assembly.teilenummer,
        "b_index": assembly.t_index,
        "is_imprecise": 0,
    }
    preset.update(presets_custom)
    user_input = {}
    user_input.update(user_input_custom)
    return operation(
        constants.kOperationNew, AssemblyComponent, preset=preset, user_input=user_input
    )


def generate_assembly_component_occurrence(assembly_component, **kwargs):
    from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence

    args = {
        "bompos_object_id": assembly_component.cdb_object_id,
        "occurrence_id": "some assembly component occurrence",
        "reference_path": "reference_path.prt",
        "assembly_path": "assembly_path.asm",
    }

    args.update(kwargs)

    return operations.operation(
        constants.kOperationNew, AssemblyComponentOccurrence, **args
    )


def ensure_running_classification_core(timeout=120):
    testcase.require_service(
        "cdb.uberserver.services.index.IndexService", timeout=timeout
    )

    from cs.classification import solr

    # noinspection PyProtectedMember
    # pylint: disable=protected-access
    solr_connection = solr._get_solr_connection()
    t = time.time()
    while t + timeout > time.time():
        try:
            without_error_logging(solr_connection.get_fields)()
            break
        except (RequestsConnectionError, SolrCommandException):
            time.sleep(1)
    else:
        raise IOError("Solr did not start up within %d seconds" % timeout)


def generate_classification_class(**args):
    default_args = {
        "code": "CS_VARIANTS_TEST_CLASS",
        "name_de": "CS_VARIANTS_TEST_CLASS",
        "name_en": "CS_VARIANTS_TEST_CLASS",
    }
    default_args.update(args)

    return operations.operation(
        constants.kOperationNew, classes.ClassificationClass, **default_args
    )


def generate_property(values, **args):
    # pylint: disable=too-many-branches
    if all((isinstance(value, bool) for value in values)):
        prop_type = "boolean"
    elif all((isinstance(value, float) for value in values)):
        prop_type = "float_without_unit"
    elif all((isinstance(value, tuple) for value in values)):
        prop_type = "float"
    elif all((isinstance(value, int) for value in values)):
        prop_type = "integer"
    else:
        prop_type = "text"
    prop_code = "CS_VARIANTS_TEST_%s_PROPERTY" % prop_type.upper()

    unit_object_id = None
    default_args = {
        "code": prop_code,
        "name_de": prop_code,
    }

    if prop_type == "float":
        unit_object_id = units.Unit.ByKeys(symbol="m").cdb_object_id
        default_args.update({"unit_object_id": unit_object_id})

    if prop_type in ("float", "float_without_unit"):
        # Find the most decimal places
        longest_decimal_places = 0
        for each_value in values:
            if isinstance(each_value, float):
                float_value = each_value
            else:
                float_value = each_value[0]

            decimal_places = abs(Decimal(str(float_value)).as_tuple().exponent)
            longest_decimal_places = max(decimal_places, longest_decimal_places)

        default_args.update({"no_decimal_positions": longest_decimal_places})

    default_args.update(args)

    if prop_type == "float_without_unit":
        prop = operations.operation(
            constants.kOperationNew, catalog.type_map["float"], **default_args
        )
    else:
        prop = operations.operation(
            constants.kOperationNew, catalog.type_map[prop_type], **default_args
        )

    if prop_type == "text":
        for value in values:
            additional_args = {
                "property_object_id": prop.cdb_object_id,
                "text_value": value,
                "is_active": 1,
            }

            if value is not None:
                additional_args["label_de"] = "LABEL_" + value

            operations.operation(
                constants.kOperationNew,
                catalog.value_type_map[prop_type],
                **additional_args
            )
    if prop_type == "float":
        for value in values:
            if isinstance(value, float):
                float_value = value
                unit_oid = unit_object_id
            else:
                float_value = value[0]
                unit_oid = units.Unit.ByKeys(symbol=value[1]).cdb_object_id

            operations.operation(
                constants.kOperationNew,
                catalog.value_type_map[prop_type],
                property_object_id=prop.cdb_object_id,
                float_value=float_value,
                is_active=1,
                unit_object_id=unit_oid,
            )
    if prop_type == "float_without_unit":
        for value in values:
            operations.operation(
                constants.kOperationNew,
                catalog.value_type_map["float"],
                property_object_id=prop.cdb_object_id,
                float_value=value,
                is_active=1,
            )
    if prop_type == "integer":
        for value in values:
            operations.operation(
                constants.kOperationNew,
                catalog.value_type_map[prop_type],
                property_object_id=prop.cdb_object_id,
                integer_value=value,
                is_active=1,
            )

    return prop


def generate_float_property(values, **args):
    unit_object_id = units.Unit.ByKeys(symbol="m").cdb_object_id

    default_args = {
        "code": "CS_VARIANTS_TEST_FLOAT_PROPERTY",
        "name_de": "CS_VARIANTS_TEST_FLOAT_PROPERTY",
        "unit_object_id": unit_object_id,
    }
    default_args.update(args)

    prop = operations.operation(
        constants.kOperationNew, catalog.FloatProperty, **default_args
    )

    for value in values:
        operations.operation(
            constants.kOperationNew,
            catalog.FloatPropertyValue,
            property_object_id=prop.cdb_object_id,
            float_value=value,
            is_active=1,
            unit_object_id=unit_object_id,
        )

    return prop


def create_variability_model(
    product,
    props,
    views=None,
    class_code="CS_VARIANTS_TEST",
    is_enum_only=False,
    with_props_on_parent_class=False,
):
    if views is None:
        views = []

    clazz = generate_class_with_props(
        props,
        code="{0}_CLASS".format(class_code),
        name_de=class_code,
        name_en=class_code,
        is_enum_only=is_enum_only,
    )

    if with_props_on_parent_class:
        parent_clazz = clazz
        clazz = generate_classification_class(
            code="{0}_CHILD_CLASS".format(class_code),
            parent_class_id=parent_clazz.cdb_object_id,
        )
        clazz.ChangeState(classes.ClassificationClass.RELEASED.status)

    # generate a variability model
    variability_model = operations.operation(
        constants.kOperationNew,
        VariabilityModel,
        product_object_id=product.cdb_object_id,
        class_object_id=clazz.cdb_object_id,
    )

    for view_props, counter in zip(views, range(len(views))):
        generate_variants_view(
            variability_model, view_props, "{0}_VIEW_{1}".format(class_code, counter)
        )
    return variability_model


def generate_class_with_props(
    props, is_enum_only=False, for_variants=True, **class_args
):
    # generate a classification class
    clazz = generate_classification_class(**class_args)
    clazz.ChangeState(classes.ClassificationClass.RELEASED.status)

    create_and_add_props_to_class(
        props, clazz, is_enum_only=is_enum_only, for_variants=for_variants
    )
    return clazz


def create_and_add_props_to_class(props, clazz, is_enum_only=False, for_variants=True):
    catalog_props = []
    for code, values in props.items():
        catalog_prop = generate_property(
            values, code=code, name_de=code, is_enum_only=is_enum_only
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)
        catalog_props.append(catalog_prop)

    # assign properties to the classification class
    for catalog_prop, _ in zip(catalog_props, range(len(catalog_props))):
        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, clazz.cdb_object_id, for_variants=for_variants
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status


def generate_variants_view(
    variability_model, view_props, class_code="CS_VARIANTS_TEST_VIEW"
):
    code_with_class_postfix = "{0}_CLASS".format(class_code)
    view_clazz = generate_class_with_props(
        view_props,
        code=code_with_class_postfix,
        name_de=code_with_class_postfix,
        name_en=code_with_class_postfix,
    )

    return operations.operation(
        constants.kOperationNew,
        VariantsView,
        variability_model_id=variability_model.cdb_object_id,
        class_object_id=view_clazz.cdb_object_id,
        name_de=code_with_class_postfix,
    )


@validationkit.run_with_roles(["public", "Engineering"])
def generate_selection_condition(variability_model, reference_object, expression):
    result = operations.operation(
        constants.kOperationNew,
        SelectionCondition,
        variability_model_id=variability_model["cdb_object_id"],
        ref_object_id=reference_object["cdb_object_id"],
        **map_expression_to_correct_attribute(expression)
    )
    reference_object.Reload()
    return result


def generate_variant(variability_model, values, **args):
    default_args = {"name": "TEST_VARIANT"}
    default_args.update(args)

    class_code = variability_model.class_code
    classification_values = {}
    for property_code, property_value in values.items():
        new_key = "{0}_{1}".format(class_code, property_code)

        if isinstance(property_value, (dict, float)):
            new_value = get_float_property_entry(
                property_code, property_value, unit_label=None
            )
        elif isinstance(property_value, int):
            new_value = get_int_property_entry(property_code, property_value)
        elif isinstance(property_value, bool):
            new_value = get_bool_property_entry(property_code, property_value)
        else:
            new_value = get_text_property_entry(property_code, property_value)

        classification_values[new_key] = new_value

    return variants_api.save_variant(
        variability_model, classification_values, **default_args
    )


def generate_variant_part(variant, item, **args):
    default_args = {
        "variability_model_id": variant.variability_model_id,
        "variant_id": variant.id,
        "teilenummer": item.teilenummer,
        "t_index": item.t_index,
    }
    default_args.update(args)
    return operations.operation(constants.kOperationNew, VariantPart, **default_args)


def generate_constraint(classification_class, when_condition, expression, **args):
    return operations.operation(
        constants.kOperationNew,
        constraints.Constraint,
        classification_class_id=classification_class.cdb_object_id,
        when_condition=when_condition,
        expression=expression,
        **args
    )


def generate_product_bom(item, variability_model):
    return operations.operation(
        constants.kOperationNew,
        VariabilityModelPart,
        teilenummer=item.teilenummer,
        t_index=item.t_index,
        variability_model_object_id=variability_model.cdb_object_id,
    )


def get_classification(obj):
    classification = classification_api.get_classification(obj)
    return classification["properties"]


def check_classification(obj, expected):
    classification = classification_api.get_classification(obj)
    property_values = classification["properties"]

    assert is_classification_data_equal(
        expected, property_values
    ), "Classification is not equal!"


def set_prop_enum_only(prop_code):
    prop = catalog.Property.ByKeys(code=prop_code)
    prop.is_enum_only = 1

    for each_class_prop in prop.DependentClassProperties:
        each_class_prop.is_enum_only = 1


class VariantsTestCase(testcase.RollbackTestCase):
    # pylint: disable=too-many-instance-attributes
    @classmethod
    def setUpClass(cls):
        super(VariantsTestCase, cls).setUpClass()

        ensure_running_classification_core()

    @staticmethod
    def get_prop_with_class_prefix(prop_code):
        return "CS_VARIANTS_TEST_CLASS_{0}".format(prop_code)

    def setUp(self, with_occurrences=False):
        super().setUp()

        self.product = generate_product()

        # the prop codes need to be unique.
        # otherwise you will get on second run an error from the index server,
        # since there's not rollback on the index server.
        self.timestamp = ("%s" % time.time()).replace(".", "")
        self.prop1 = "PROP1_%s" % self.timestamp
        self.prop2 = "PROP2_%s" % self.timestamp
        self.class_prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        self.class_prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        props = collections.OrderedDict(
            [
                (self.prop1, ["VALUE1", "VALUE2"]),
                (self.prop2, ["VALUE1", "VALUE2"]),
            ]
        )

        self.view_prop1 = "VIEW_PROP1_%s" % self.timestamp
        self.view_prop2 = "VIEW_PROP2_%s" % self.timestamp
        view_props = collections.OrderedDict(
            [
                (self.view_prop1, ["VALUE1", "VALUE2"]),
                (self.view_prop2, ["VALUE1", "VALUE2"]),
            ]
        )
        self.variability_model = create_variability_model(
            self.product, props, views=[view_props]
        )
        self.view = self.variability_model.Views[0]

        # PROP1 == 'VALUE1' => PROP2 == 'VALUE1'
        self.expression = (
            "CS_VARIANTS_TEST_CLASS_%s != 'VALUE1' or CS_VARIANTS_TEST_CLASS_%s == 'VALUE1'"
            % (self.prop1, self.prop2)
        )

        self.maxbom = generate_part()
        generate_product_bom(self.maxbom, self.variability_model)
        self.subassembly = generate_part()
        self.subassembly_comp = generate_assembly_component(
            self.maxbom, self.subassembly
        )

        self.comp = generate_assembly_component(
            self.subassembly, user_input_custom={"menge": 2}
        )
        self.selection_condition = generate_selection_condition(
            self.variability_model, self.comp, self.expression
        )

        if with_occurrences:
            self.occurrence1 = generate_assembly_component_occurrence(
                self.comp,
                occurrence_id="occurrence1",
                relative_transformation="occurrence1",
            )
            self.occurrence2 = generate_assembly_component_occurrence(
                self.comp,
                occurrence_id="occurrence2",
                relative_transformation="occurrence1",
            )
            self.selection_condition_occurrence1 = generate_selection_condition(
                self.variability_model, self.occurrence1, self.expression
            )

        self.constraint = None

        # Reset caches in cs.classification
        ClassificationValidator.reload_all()

    def generate_constraint(self):
        self.constraint = generate_constraint(
            self.variability_model.ClassificationClass,
            "CS_VARIANTS_TEST_CLASS_{0} != 'VALUE1'".format(self.prop1),
            "CS_VARIANTS_TEST_CLASS_{0} != 'VALUE1'".format(self.prop2),
        )

        # Reset caches in cs.classification
        ClassificationValidator.reload_all()

        return self.constraint


class VariantsTestCaseWithFloat(testcase.RollbackTestCase):
    # pylint: disable=too-many-instance-attributes
    @classmethod
    def setUpClass(cls):
        super(VariantsTestCaseWithFloat, cls).setUpClass()

        ensure_running_classification_core()

    def setUp(self):
        super().setUp()

        self.product = generate_product()

        # the prop codes need to be unique.
        # otherwise you will get on second run an error from the index server,
        # since there's not rollback on the index server.
        self.timestamp = ("%s" % time.time()).replace(".", "")
        self.prop1 = "PROP1_%s" % self.timestamp
        self.prop2 = "PROP2_%s" % self.timestamp
        self.prop_float = "PROP_FLOAT_%s" % self.timestamp
        props = collections.OrderedDict(
            [
                (self.prop1, ["VALUE1", "VALUE2"]),
                (self.prop2, ["VALUE1", "VALUE2"]),
                (self.prop_float, [(100, "cm"), (1, "m"), (200, "mm")]),
            ]
        )

        self.view_prop1 = "VIEW_PROP1_%s" % self.timestamp
        self.view_prop2 = "VIEW_PROP2_%s" % self.timestamp
        view_props = collections.OrderedDict(
            [
                (self.view_prop1, ["VALUE1", "VALUE2"]),
                (self.view_prop2, ["VALUE1", "VALUE2"]),
            ]
        )
        self.variability_model = create_variability_model(
            self.product, props, views=[view_props]
        )
        self.view = self.variability_model.Views[0]

        # PROP1 == 'VALUE1' => PROP2 == 'VALUE1'
        expression = (
            "CS_VARIANTS_TEST_CLASS_%s != 'VALUE1' or CS_VARIANTS_TEST_CLASS_%s == 'VALUE1'"
            % (self.prop1, self.prop2)
        )

        self.maxbom = generate_part()
        generate_product_bom(self.maxbom, self.variability_model)
        self.subassembly = generate_part()
        self.subassembly_comp = generate_assembly_component(
            self.maxbom, self.subassembly
        )

        self.comp = generate_assembly_component(
            self.subassembly, user_input_custom={"menge": 2}
        )
        self.selection_condition = generate_selection_condition(
            self.variability_model, self.comp, expression
        )

        # Reset caches in cs.classification
        ClassificationValidator.reload_all()


def get_text_property_entry(property_code, property_value, use_mock_any_for_id=False):
    entry = {
        "value_path": property_code,
        "property_type": "text",
        "id": mock.ANY if use_mock_any_for_id else None,
        "value": property_value,
    }
    if property_value is not None:
        entry["addtl_value"] = {"label": "LABEL_{0}".format(property_value)}

    return [entry]


def get_float_property_entry(
    property_code, property_value, unit_label="m", float_value_normalized=None
):
    return [
        {
            "value_path": property_code,
            "property_type": "float",
            "id": None,
            "value": get_float_value(
                property_value,
                unit_label=unit_label,
                float_value_normalized=float_value_normalized,
            )
            if not isinstance(property_value, dict)
            else property_value,
        }
    ]


def get_float_value(float_value, unit_label="m", float_value_normalized=None):
    result = {
        "float_value_normalized": float_value
        if float_value_normalized is None
        else float_value_normalized,
        "float_value": float_value,
    }
    if unit_label is not None:
        result["unit_label"] = unit_label
        result["unit_object_id"] = units.Unit.ByKeys(symbol=unit_label).cdb_object_id

    return result


def get_bool_property_entry(property_code, property_value):
    return [
        {
            "value_path": property_code,
            "property_type": "boolean",
            "id": None,
            "value": property_value,
        }
    ]


def get_int_property_entry(property_code, property_value):
    return [
        {
            "value_path": property_code,
            "property_type": "integer",
            "id": None,
            "value": property_value,
        }
    ]


def is_classification_data_equal(data_left, data_right):
    try:
        for property_code, property_left_entries in data_left.items():
            # No multiple allowed so hard code to index 0
            property_left_entry = property_left_entries[0]
            property_right_entry = data_right[property_code][0]

            if not util.are_property_values_equal(
                property_left_entry["property_type"],
                property_left_entry["value"],
                property_right_entry["value"],
            ):
                return False
    except KeyError:
        return False

    return True


class VariantsNoSubComponentCase(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(VariantsNoSubComponentCase, cls).setUpClass()

        ensure_running_classification_core()

    def setUp(self):
        super().setUp()

        self.product = generate_product()

        # the prop codes need to be unique.
        # otherwise you will get on second run an error from the index server,
        # since there's not rollback on the index server.
        self.timestamp = ("%s" % time.time()).replace(".", "")
        self.prop1 = "PROP1_%s" % self.timestamp
        self.prop2 = "PROP2_%s" % self.timestamp
        props = collections.OrderedDict(
            [
                (self.prop1, ["VALUE1", "VALUE2"]),
                (self.prop2, ["VALUE1", "VALUE2"]),
            ]
        )

        self.view_prop1 = "VIEW_PROP1_%s" % self.timestamp
        self.view_prop2 = "VIEW_PROP2_%s" % self.timestamp
        view_props = collections.OrderedDict(
            [
                (self.view_prop1, ["VALUE1", "VALUE2"]),
                (self.view_prop2, ["VALUE1", "VALUE2"]),
            ]
        )
        self.variability_model = create_variability_model(
            self.product, props, views=[view_props]
        )
        self.view = self.variability_model.Views[0]

        self.maxbom = generate_part()
        generate_product_bom(self.maxbom, self.variability_model)

        # Reset caches in cs.classification
        ClassificationValidator.reload_all()


class ReinstantiateCase(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(ReinstantiateCase, cls).setUpClass()

        cls.product = Product.ByKeys(code="VAR_TEST_REINSTANTIA")
        cls.variability_model = ByID("39a54ecc-2401-11eb-9218-24418cdf379c")
        cls.maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")
        cls.part1 = items.Item.ByKeys(teilenummer="9508576", t_index="")
        cls.var_part1 = items.Item.ByKeys(teilenummer="9508578", t_index="")
        cls.var_part2 = items.Item.ByKeys(teilenummer="9508577", t_index="")
