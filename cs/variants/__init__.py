# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import json

from cdb import classbody, constants, sig, sqlapi, transactions, ue
from cdb.objects import ReferenceMethods_1, core, expressions, operations, references
from cs.classification import api as classification_api
from cs.classification import classes
from cs.tools.powerreports import WithPowerReports
from cs.variants.classification_checks import (
    VariantVariabilityClassificationClassChecker,
    check_for_not_allowed_variability_classification_class_deletion,
    get_all_variant_driving_properties_from_classification_diff_data,
    is_variability_classification_class_affected,
)
from cs.variants.classification_helper import calculate_classification_value_checksum
from cs.vp import items

# noinspection PyProtectedMember
from cs.vp.products import Product, ProductPart

fSelectionCondition = expressions.Forward(
    "cs.variants.selection_condition.SelectionCondition"
)
fVariabilityModel = expressions.Forward("cs.variants.VariabilityModel")
fVariant = expressions.Forward("cs.variants.Variant")
fVariantPart = expressions.Forward("cs.variants.VariantPart")
fVariantsView = expressions.Forward("cs.variants.VariantsView")
fVariabilityModelPart = expressions.Forward("cs.variants.VariabilityModelPart")

VARIANT_STATUS_OK = "ok"
VARIANT_STATUS_INVALID = "invalid"

VARIANT_DRIVING_FLAG_INDEX = 9
NO_VARIANT_ID = -1
COCKPIT_ROOT_URL = "/cs-threed-hoops-web-cockpit-part"


class Variant(core.Object, WithPowerReports):
    __maps_to__ = "cs_variant"
    __classname__ = "cs_variant"

    def _get_instanced_items(self):
        return items.Item.SQL(
            "SELECT DISTINCT teile_stamm.* "
            "FROM teile_stamm INNER JOIN cs_variant_part "
            "ON teile_stamm.teilenummer=cs_variant_part.teilenummer "
            "AND teile_stamm.t_index=cs_variant_part.t_index "
            "WHERE cs_variant_part.variability_model_id='{modelid}' "
            "AND cs_variant_part.variant_id={id}".format(
                modelid=self.variability_model_id, id=self.id
            )
        )

    Instances = references.ReferenceMethods_N(items.Item, _get_instanced_items)
    VariantParts = references.Reference_N(
        fVariantPart,
        fVariantPart.variability_model_id == fVariant.variability_model_id,
        fVariantPart.variant_id == fVariant.id,
    )
    VariabilityModel = references.Reference_1(
        fVariabilityModel,
        fVariabilityModel.cdb_object_id == fVariant.variability_model_id,
    )

    def _get_product(self):
        return self.VariabilityModel.Product

    Product = ReferenceMethods_1(Product, _get_product)

    @classmethod
    def new_id(cls, variability_model_id):
        new_id = 1
        t = sqlapi.SQLselect(
            "max(id) from cs_variant where variability_model_id = '%s'"
            % variability_model_id
        )
        if sqlapi.SQLstring(t, 0, 0) != "":
            new_id = sqlapi.SQLinteger(t, 0, 0) + 1
        return new_id

    def get_classification_checksum(self):
        variant_driving_properties = self.get_variant_driving_properties_with_values()[
            "properties"
        ]
        return calculate_classification_value_checksum(variant_driving_properties)

    def update_classification_checksum(self):
        classification_checksum = self.get_classification_checksum()
        self.Update(classification_checksum=classification_checksum)

    def get_variant_driving_properties_with_values(self):
        from cs.variants.api import VariantsClassification

        variability_class_code = self.VariabilityModel.ClassificationClass.code
        variants_classification = VariantsClassification([variability_class_code])
        variant_driving_properties = (
            variants_classification.get_variant_driving_properties()
        )
        variant_classification_properties = classification_api.get_classification(
            self, narrowed=False
        )["properties"]

        filtered_classification_properties = {}
        for each in variant_driving_properties:
            filtered_classification_properties[
                each
            ] = variant_classification_properties[each]

        return {
            "metadata": variant_driving_properties,
            "properties": filtered_classification_properties,
        }

    @classmethod
    def on_cs_variant_save_variants_now(cls, ctx):
        from cs.variants.api import save_variant

        variability_model_id = ctx.dialog["variability_model_id"]
        variability_model = VariabilityModel.ByKeys(variability_model_id)

        params_list_string = ctx.dialog["params_list"]
        params_list = json.loads(params_list_string)

        with transactions.Transaction():
            for params in params_list:
                save_variant(variability_model, params)

    @classmethod
    def on_cs_variant_exclude_variants_now(cls, ctx):
        from cs.variants.api import exclude_variant

        variability_model_id = ctx.dialog["variability_model_id"]
        variability_model = VariabilityModel.ByKeys(variability_model_id)

        params_list_string = ctx.dialog["params_list"]
        params_list = json.loads(params_list_string)

        with transactions.Transaction():
            for params in params_list:
                exclude_variant(variability_model, params)

    def has_instances(self):
        sql_stmt = """
            SELECT * FROM cs_variant_part
            WHERE variability_model_id='{model_id}' AND variant_id='{variant_id}'
        """.format(
            model_id=self.variability_model_id, variant_id=self.id
        )
        from_str = "FROM dual" if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE else ""
        exists_qry = "SELECT 1 AS cnt {from_str} WHERE EXISTS ({sql_stmt})".format(
            from_str=from_str, sql_stmt=sql_stmt
        )
        return len(sqlapi.RecordSet2(sql=exists_qry)) > 0

    # bom_table / threed support
    def make_variant_filter(self):
        """
        A filter used to filter bom items for specific variant properties
        :return: filter object which needs to have this function:
                eval(self, baugruppe, b_index, teilenummer, t_index, variante,
                     position, occurrence_id=None, assembly_path=None)
                        Apply filter to BOM position

                        :return: True if the position should be included and False otherwise
        """
        from cs.variants.api.filter import VariantFilter

        return VariantFilter(self, ignore_not_set_properties=True)

    def _allow_delete(self, ctx):
        if self.has_instances():
            raise ue.Exception("cs_variants_delete_variant_with_instances")

    def get_newest_instanced_item(self):
        try:
            return items.Item.SQL(
                "SELECT DISTINCT teile_stamm.* "
                "FROM teile_stamm INNER JOIN cs_variant_part "
                "ON teile_stamm.teilenummer=cs_variant_part.teilenummer "
                "AND teile_stamm.t_index=cs_variant_part.t_index "
                "WHERE cs_variant_part.variability_model_id='{modelid}' "
                "AND cs_variant_part.variant_id={id} "
                "ORDER BY teile_stamm.cdb_cdate DESC".format(
                    modelid=self.variability_model_id, id=self.id
                ),
                max_rows=1,
            )[0]
        except IndexError:
            return None

    def get_classification_class(self):
        return self.VariabilityModel.ClassificationClass

    def open_threed_cockpit_pre_mask(self, ctx):
        max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
        is_max_bom_id_defined = max_bom_id is not None and max_bom_id != ""
        if (
            is_max_bom_id_defined
            or self.VariabilityModel.preselect_ctx_max_bom_id_if_possible(ctx)
            is not None
        ):
            ctx.skip_dialog()
        else:
            # dialog needs to be shown but through variant variability model is already fixed
            ctx.set_readonly("variability_model_id")

    def open_threed_cockpit(self, ctx):
        max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
        if max_bom_id is None or max_bom_id == "":
            raise ue.Exception("cs_variants_select_maxbom")

        url = (
            f"{COCKPIT_ROOT_URL}/{max_bom_id}?variantId={self.id}"
            f"&variabilityModel={self.variability_model_id}"
        )
        return ue.Url4Context(url)

    def _select_max_bom_dlg(self, ctx):
        # needed for cs.viewstation
        skipped = False
        max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
        is_max_bom_id_defined = max_bom_id is not None and max_bom_id != ""
        if is_max_bom_id_defined:
            skipped = True
            ctx.skip_dialog()

        return skipped

    @staticmethod
    def _get_max_bom_item(ctx) -> items.Item | None:
        # needed for cs.viewstation / cs.workspace (E069806)
        max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
        is_max_bom_id_defined = max_bom_id is not None and max_bom_id != ""
        if is_max_bom_id_defined:
            return items.Item.ByKeys(cdb_object_id=max_bom_id)
        return None

    @classmethod
    def on_cs_variants_open_in_cad_unsaved_pre_mask(cls, ctx):
        """
        pre_mask hook for open unsaved variant in CAD system
        :param ctx:
        :return:
        """
        # local import to avoid circular imports
        from cs.variants.cad_integration import CAD_PLUGINS, find_plugins_for_maxbom

        if not CAD_PLUGINS:
            raise ue.Exception("cs_variants_cad_plugin_no_plugin_registered")

        # maxbom always set for unsaved variants
        maxbom = cls._get_max_bom_item(ctx)
        plugins = find_plugins_for_maxbom(maxbom)

        if not plugins:
            raise ue.Exception("cs_variants_cad_plugin_no_plugin_for_maxbom")

        if len(plugins) == 1:
            plugin = plugins[0]
            ctx.set("plugin_selected_erzeug_system", plugin.erzeug_system)
            ctx.set("plugin_selection", plugin.title)
            ctx.skip_dialog()

        # more than one plugin -> user have to select one
        else:
            # variability model and max bom for unsaved variants can not be empty
            ctx.set_readonly("variability_model_id")
            ctx.set_readonly("max_bom_id")

    @classmethod
    def on_cs_variants_open_in_cad_unsaved_now(cls, ctx):
        """
        now hook for open unsaved variant in CAD system
        :param ctx:
        :return:
        """

        # local import to avoid circular imports
        from cs.variants.api.filter import (
            CsVariantsFilterContextPlugin,
            CsVariantsVariabilityModelContextPlugin,
        )
        from cs.variants.cad_integration import get_plugin

        selected_erzeug_system = ctx.dialog["plugin_selected_erzeug_system"]
        plugin = get_plugin(selected_erzeug_system)

        if plugin is None:
            raise ue.Exception(
                "cs_variant_cad_plugin_not_found", selected_erzeug_system
            )

        variability_model_id = ctx.dialog["variability_model_id"]

        params_list_string = ctx.dialog["params_list"]
        params_list = json.loads(params_list_string)

        var_model_context = CsVariantsVariabilityModelContextPlugin(
            variability_model_id
        )
        variant_filter_plugin = CsVariantsFilterContextPlugin(
            var_model_context, classification_properties=params_list[0]
        )

        maxbom = cls._get_max_bom_item(ctx)

        from cs.variants.api.occurrence_walk_generator import OccurrenceWalkGenerator

        walk_generator = OccurrenceWalkGenerator(maxbom, variant_filter_plugin)
        plugin.callback(plugin.erzeug_system, walk_generator, ctx)

    def on_cs_variants_open_in_cad_pre_mask(self, ctx):
        """
        pre_mask hook for open variant in CAD system
        :param ctx:
        :return:
        """
        # local import to avoid circular imports
        from cs.variants.cad_integration import CAD_PLUGINS, find_plugins_for_maxbom

        if not CAD_PLUGINS:
            raise ue.Exception("cs_variants_cad_plugin_no_plugin_registered")
        maxbom = self._get_max_bom_item(ctx)

        if maxbom is not None:
            plugins = find_plugins_for_maxbom(maxbom)
            if not plugins:
                raise ue.Exception(
                    "cs_variants_cad_plugin_no_plugin_for_maxbom",
                    maxbom.teilenummer,
                    maxbom.t_index,
                )

            if len(plugins) == 1:
                plugin = plugins[0]
                ctx.set("plugin_selected_erzeug_system", plugin.erzeug_system)
                ctx.set("plugin_selection", plugin.title)
                ctx.skip_dialog()

        else:
            # dialog needs to be shown but through variant the variability model is already fixed
            ctx.set_readonly("variability_model_id")

    def on_cs_variants_open_in_cad_now(self, ctx):
        """
        now hook for open variant in CAD system
        :param ctx:
        :return:
        """
        # local import to avoid circular imports
        from cs.variants.api.filter import (
            CsVariantsFilterContextPlugin,
            CsVariantsVariabilityModelContextPlugin,
        )
        from cs.variants.cad_integration import get_plugin

        maxbom = self._get_max_bom_item(ctx)
        if maxbom is None:
            raise ue.Exception("cs_variants_select_maxbom")

        # check if plugin is present (based on "erzeug_system" attribute)
        selected_erzeug_system = ctx.dialog["plugin_selected_erzeug_system"]
        plugin = get_plugin(selected_erzeug_system)

        if plugin is None:
            raise ue.Exception(
                "cs_variant_cad_plugin_not_found", selected_erzeug_system
            )
        var_model_context = CsVariantsVariabilityModelContextPlugin(
            self.variability_model_id
        )
        variant_filter_plugin = CsVariantsFilterContextPlugin(
            var_model_context, self.id
        )

        from cs.variants.api.occurrence_walk_generator import OccurrenceWalkGenerator

        walk_generator = OccurrenceWalkGenerator(maxbom, variant_filter_plugin)
        plugin.callback(plugin.erzeug_system, walk_generator, ctx)

    event_map = {
        ("delete", "pre"): "_allow_delete",
        ("threed_cockpit_cs_variants", "pre_mask"): "open_threed_cockpit_pre_mask",
        ("threed_cockpit_cs_variants", "now"): "open_threed_cockpit",
    }


@sig.connect(Variant, "classification_update", "pre_commit")
def _check_variant_classification(variant, _, classification_diff_data):
    from cs.variants.api import VariantsClassification

    classification_class = variant.get_classification_class()
    check_for_not_allowed_variability_classification_class_deletion(
        classification_class, classification_diff_data
    )

    if not is_variability_classification_class_affected(
        classification_class, classification_diff_data
    ):
        return

    variants_classification = VariantsClassification([classification_class.code])
    classification_class_checker = VariantVariabilityClassificationClassChecker(
        variant, variants_classification
    )
    for (
        property_definition,
        diff_property_entry,
    ) in get_all_variant_driving_properties_from_classification_diff_data(
        variants_classification, classification_diff_data
    ):
        classification_class_checker.check(property_definition, diff_property_entry)

    classification_class_checker.raise_ue_exception_if_checks_failed()


@sig.connect(Variant, "classification_update", "post")
def _update_variant_classification_checksum(variant, _):
    variant.update_classification_checksum()


class VariabilityModel(core.Object):
    __maps_to__ = "cs_variability_model"
    __classname__ = "cs_variability_model"

    ClassificationClass = references.Reference_1(
        classes.ClassificationClass,
        classes.ClassificationClass.cdb_object_id == fVariabilityModel.class_object_id,
    )

    Product = references.Reference_1(
        Product, Product.cdb_object_id == fVariabilityModel.product_object_id
    )

    SelectionConditions = references.Reference_N(
        fSelectionCondition,
        fSelectionCondition.variability_model_id == fVariabilityModel.cdb_object_id,
    )

    ToplevelAssemblyLinks = references.Reference_N(
        fVariabilityModelPart,
        fVariabilityModelPart.variability_model_object_id
        == fVariabilityModel.cdb_object_id,
    )

    def _getMaxBoms(self):
        result = []
        for each in self.ToplevelAssemblyLinks:
            if each.Item:
                result.append(each.Item)
        return result

    MaxBOMs = references.ReferenceMethods_N(items.Item, _getMaxBoms)

    # threed support
    Variants = references.Reference_N(
        fVariant, fVariant.variability_model_id == fVariabilityModel.cdb_object_id
    )

    Views = references.Reference_N(
        fVariantsView,
        fVariantsView.variability_model_id == fVariabilityModel.cdb_object_id,
    )

    def generate_class_applicability(self, ctx=None):
        from cs.classification import applicability

        clazz = self.ClassificationClass
        for classname in ["cs_variant", "part"]:
            applicabilities = clazz.Applicabilities.KeywordQuery(dd_classname=classname)

            if not applicabilities:
                operations.operation(
                    constants.kOperationNew,
                    applicability.ClassificationApplicability,
                    classification_class_id=clazz.cdb_object_id,
                    dd_classname=classname,
                    is_active=1,
                    write_access_obj="save",
                )

    # threed support
    # pylint: disable=too-many-arguments
    @staticmethod
    def multiple_eval(
        baugruppe,
        b_index,
        teilenummer,
        t_index,
        variante,
        position,
        filters,
        nconditions=None,
    ):
        """
        Apply an arbitrary number of filters to a single BOM position.

        :param filters: A list of BOMFilter objects

        :return: A dictionary which has the object of filters as keys,
                 and values True if the position should be included
                 in the result, according to the filter,
                 and False otherwise.
        """
        return {
            variant_filter: variant_filter.eval(
                baugruppe, b_index, teilenummer, t_index, variante, position
            )
            for variant_filter in filters
        }

    # threed support
    def get_filter_for_signature(self, signature):
        """
        Retrieve bom filter and hash for signature

        :param signature: variability signature
        :type signature: basestring

        :return: tuple first element is the filter object and second the hash for the signature
                 the filter object needs to have the function:
                    eval(self, baugruppe, b_index, teilenummer, t_index, variante,
                         position, occurrence_id=None, assembly_path=None)
                            Apply filter to BOM position

                            :return: True if the position should be included and False otherwise
        """
        from cs.variants.api.filter import PropertiesBasedVariantFilter

        classification_data = json.loads(signature)
        return (
            PropertiesBasedVariantFilter(self.cdb_object_id, classification_data),
            calculate_classification_value_checksum(classification_data),
        )

    def preselect_ctx_max_bom_id_if_possible(self, ctx):
        # Only possible to auto select max bom if only one exists
        if len(self.MaxBOMs) == 1:
            max_bom = self.MaxBOMs[0]
            ctx.set("max_bom_id", max_bom.cdb_object_id)
            ctx.set(".max_bom_id", max_bom.cdb_object_id)
            return max_bom

        return None

    def open_threed_cockpit_pre_mask(self, ctx):
        ctx.set("variability_model_id", self.cdb_object_id)
        if self.preselect_ctx_max_bom_id_if_possible(ctx) is None:
            ctx.set_readonly("variability_model_id")
        else:
            ctx.skip_dialog()

    @staticmethod
    def open_threed_cockpit(ctx):
        variability_model_id = getattr(ctx.dialog, "variability_model_id", None)
        if variability_model_id is None or variability_model_id == "":
            raise ue.Exception("cs_variants_select_variability_model")

        max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
        if max_bom_id is None or max_bom_id == "":
            raise ue.Exception("cs_variants_select_maxbom")

        url = f"{COCKPIT_ROOT_URL}/{max_bom_id}?variabilityModel={variability_model_id}"
        return ue.Url4Context(url)

    @staticmethod
    def set_fields_readonly(ctx):
        ctx.set_readonly("class_object_id")

    event_map = {
        (("create", "copy", "modify"), "post"): "generate_class_applicability",
        ("modify", "pre_mask"): "set_fields_readonly",
        ("threed_cockpit_cs_variants", "pre_mask"): "open_threed_cockpit_pre_mask",
        ("threed_cockpit_cs_variants", "now"): "open_threed_cockpit",
    }


class VariantsView(core.Object):
    __maps_to__ = "cs_variants_view"
    __classname__ = "cs_variants_view"

    ClassificationClass = references.Reference_1(
        classes.ClassificationClass,
        classes.ClassificationClass.cdb_object_id == fVariantsView.class_object_id,
    )

    VariabilityModel = references.Reference_1(
        fVariabilityModel,
        fVariabilityModel.cdb_object_id == fVariantsView.variability_model_id,
    )


class VariantPart(core.Object):
    __maps_to__ = "cs_variant_part"
    __classname__ = "cs_variant_part"

    Variant = references.Reference_1(
        fVariant,
        fVariant.variability_model_id == fVariantPart.variability_model_id,
        fVariant.id == fVariantPart.variant_id,
    )

    Item = references.Reference_1(
        items.Item,
        items.Item.teilenummer == fVariantPart.teilenummer,
        items.Item.t_index == fVariantPart.t_index,
    )

    MaxBOM = references.Reference_1(
        items.Item,
        items.Item.teilenummer == fVariantPart.maxbom_teilenummer,
        items.Item.t_index == fVariantPart.maxbom_t_index,
    )

    VariabilityModel = references.Reference_1(
        fVariabilityModel,
        fVariabilityModel.cdb_object_id == fVariantPart.variability_model_id,
    )

    @staticmethod
    def get_all_belonging_to_parts(parts):
        condition_parts = []
        for each in parts:
            condition_parts.append(
                "teilenummer='{0}' AND t_index='{1}'".format(
                    each.teilenummer, each.t_index
                )
            )

        condition = " OR ".join(condition_parts)
        return VariantPart.Query(condition=condition).Execute()


@classbody.classbody
class Product:
    VariabilityModels = references.Reference_N(
        fVariabilityModel, fVariabilityModel.product_object_id == Product.cdb_object_id
    )

    def preselect_ctx_variability_model_id_if_possible(self, ctx):
        # Only possible to auto select variability model if only one exists
        if len(self.VariabilityModels) == 1:
            variability_model = self.VariabilityModels[0]
            ctx.set("variability_model_id", variability_model.cdb_object_id)
            return variability_model

        return None

    def open_threed_cockpit_pre_mask(self, ctx):
        variability_model = self.preselect_ctx_variability_model_id_if_possible(ctx)

        if variability_model is None:
            # So the catalog shows only variability models valid for this product
            ctx.set("product_object_id", self.cdb_object_id)
        else:
            if variability_model.preselect_ctx_max_bom_id_if_possible(ctx) is None:
                ctx.set_readonly("variability_model_id")
            else:
                ctx.skip_dialog()

    @staticmethod
    def open_threed_cockpit(ctx):
        variability_model_id = getattr(ctx.dialog, "variability_model_id", None)
        if variability_model_id is None or variability_model_id == "":
            raise ue.Exception("cs_variants_select_variability_model")

        max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
        if max_bom_id is None or max_bom_id == "":
            raise ue.Exception("cs_variants_select_maxbom")

        url = f"{COCKPIT_ROOT_URL}/{max_bom_id}?variabilityModel={variability_model_id}"
        return ue.Url4Context(url)

    event_map = {
        ("threed_cockpit_cs_variants", "pre_mask"): "open_threed_cockpit_pre_mask",
        ("threed_cockpit_cs_variants", "now"): "open_threed_cockpit",
    }


class VariabilityModelPart(core.Object):
    __maps_to__ = "cs_variability_model_part"
    __classname__ = "cs_variability_model_part"

    Item = references.Reference_1(
        items.Item,
        items.Item.teilenummer == fVariabilityModelPart.teilenummer,
        items.Item.t_index == fVariabilityModelPart.t_index,
    )

    VariabilityModel = references.Reference_1(
        fVariabilityModel,
        fVariabilityModel.cdb_object_id
        == fVariabilityModelPart.variability_model_object_id,
    )

    def _create_product_relation(self, _):
        ProductPart.CreateIfNoConflict(
            product_object_id=self.VariabilityModel.product_object_id,
            teilenummer=self.teilenummer,
            t_index=self.t_index,
        )

    def _set_configurable_attribute_create(self, _):
        items.Item.KeywordQuery(
            teilenummer=self.teilenummer, t_index=self.t_index
        ).Update(configurable=1)

    def _set_configurable_attribute_delete(self, _):
        items.Item.KeywordQuery(
            teilenummer=self.teilenummer, t_index=self.t_index
        ).Update(
            configurable=1
            if VariabilityModelPart.KeywordQuery(
                teilenummer=self.teilenummer, t_index=self.t_index
            )
            else 0
        )

    event_map = {
        ("create", "post"): "_create_product_relation",
        (("create", "copy"), "post"): "_set_configurable_attribute_create",
        ("delete", "post"): "_set_configurable_attribute_delete",
    }


class VariantSubPart(core.Object):
    __maps_to__ = "cs_variant_sub_part"
    __classname__ = "cs_variant_sub_part"
