# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module items

This is the documentation for the items module.
"""
from __future__ import absolute_import

import json
import logging
from collections import defaultdict

from cdb import sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.objects import Reference_N, ReferenceMethods_1, ReferenceMethods_N
from cs.classification.computations import PropertyValueNotFoundException
from cs.classification.util import isclose
from cs.variants import (
    VariabilityModel,
    VariabilityModelPart,
    Variant,
    VariantPart,
    VariantSubPart,
)
from cs.variants.api import (
    VariantsClassification,
    instantiate_part,
    reinstantiate_parts,
)
from cs.variants.api.constants_api import (
    CLASSIFICATION_FLAG_FOR_INSTANTIATOR,
    IS_INSTANTIATE,
)
from cs.variants.classification_checks import (
    UeExceptionChangedPropertiesNotAllowedOnItem,
    check_for_not_allowed_variability_classification_class_deletion,
    get_all_variant_driving_properties_from_classification_diff_data,
    is_variability_classification_class_affected,
)
from cs.variants.exceptions import (
    MultiplePartsReinstantiateWithFailedPartsError,
    NotAllowedToReinstantiateError,
    NotAnInstanceException,
    SelectionConditionEvaluationError,
    VariantIncompleteError,
)
from cs.variants.selection_condition import SelectionCondition
from cs.vp.bom import AssemblyComponent
from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence
from cs.vp.items import Item
from cs.vp.items.mbom import DERIVED_BOM_CREATED

# noinspection PyProtectedMember
from cs.vp.products import ProductPart

# Have to make sure that the classbody of old VM is loaded prior to our adaptions so we force this import here
# noinspection PyUnresolvedReferences
# pylint: disable=unused-import
from cs.vp.variants.items import Item as VpVariantsItemClassbody  # noqa: F401

LOG = logging.getLogger(__name__)


def disconnect_signal_function(signal, func_name):
    slots = sig.find_slots(*signal)
    for x in slots:
        if x.__name__ == func_name:
            sig.disconnect(x)


# Disconnect signals from cs.vp.variants
disconnect_signal_function(
    (AssemblyComponent, "create", "post"), "_vpvariants_set_position_type"
)
disconnect_signal_function(
    (AssemblyComponent, "delete", "post"), "_vpvariants_set_position_type"
)

SELECTION_CONDITION_CHILD_BOM_ITEM_MAPPING_WHITELIST = [
    "teilenummer",
    "t_index",
    "variante",
    "position",
    "menge",
    "component_unit_name_en",
    "mbom_mapping_tag",
    "stlbemerkung",
    "position_el",
    "ap_bemerkung",
    "st_fertart",
    "ap_fertart",
    "auftr_z_index",
    "strukturzaehler",
    "cadsource",
    "occurence_id",
    "variant_id",
    "stlbemerkung",
]


def _is_db_attribute_equal(left_attribute, right_attribute):
    if isinstance(left_attribute, float) and isinstance(right_attribute, float):
        return isclose(left_attribute, right_attribute)
    else:
        left_attribute = left_attribute if left_attribute is not None else ""
        right_attribute = right_attribute if right_attribute is not None else ""

        return left_attribute == right_attribute


def _is_copied_bom_item_by_mapping_whitelist(source_bom_item, copied_bom_item):
    for each in SELECTION_CONDITION_CHILD_BOM_ITEM_MAPPING_WHITELIST:
        if not _is_db_attribute_equal(source_bom_item[each], copied_bom_item[each]):
            return False

    return True


@classbody
class AssemblyComponent:
    SelectionConditions = Reference_N(
        SelectionCondition,
        SelectionCondition.ref_object_id == AssemblyComponent.cdb_object_id,
    )


@classbody
class Item:
    VariantLinks = Reference_N(
        VariantPart,
        VariantPart.teilenummer == Item.teilenummer,
        VariantPart.t_index == Item.t_index,
    )

    def _get_variant(self):
        var_links = self.VariantLinks
        if var_links:
            return var_links[0].Variant
        return None

    Variant = ReferenceMethods_1(Variant, _get_variant)

    VariabilityModelLinks = Reference_N(
        VariabilityModelPart,
        VariabilityModelPart.teilenummer == Item.teilenummer,
        VariabilityModelPart.t_index == Item.t_index,
    )

    def _get_variability_models(self):
        result = [link.VariabilityModel for link in self.VariabilityModelLinks]
        return result

    VariabilityModels = ReferenceMethods_N(VariabilityModel, _get_variability_models)
    Products = VariabilityModels

    def _copy_selection_conditions(self, ctx):
        if ctx.relationship_name != "CDB::Relationship::STL::part2bom_item":
            return

        source_object = ctx.cdbtemplate
        copied_object = ctx.object

        bom_items = AssemblyComponent.SQL(
            """
            SELECT e.* FROM einzelteile e
            WHERE (e.baugruppe='{baugruppe1}' AND e.b_index='{b_index1}')
            OR (e.baugruppe='{baugruppe2}' AND e.b_index='{b_index2}')
            """.format(
                baugruppe1=source_object.teilenummer,
                b_index1=source_object.t_index,
                baugruppe2=copied_object.teilenummer,
                b_index2=copied_object.t_index,
            )
        )

        source_bom_items = []
        copied_bom_items = []
        for each in bom_items:
            if (
                each.baugruppe == source_object.teilenummer
                and each.b_index == source_object.t_index
            ):
                source_bom_items.append(each)
            elif (
                each.baugruppe == copied_object.teilenummer
                and each.b_index == copied_object.t_index
            ):
                copied_bom_items.append(each)
            else:
                raise ValueError("Not recognized bom_item result!")

        selection_conditions_lookup = defaultdict(list)
        selection_conditions = SelectionCondition.KeywordQuery(
            ref_object_id=[each.cdb_object_id for each in source_bom_items]
        )
        for each in selection_conditions:
            selection_conditions_lookup[each.ref_object_id].append(each)

        for each in source_bom_items:
            copied_bom_item_oid = None

            for copied in copied_bom_items:
                if _is_copied_bom_item_by_mapping_whitelist(each, copied):
                    copied_bom_item_oid = copied.cdb_object_id

            if copied_bom_item_oid is None:
                raise ue.Exception("No corresponding copied bom_item found!")

            for sc in selection_conditions_lookup[each.cdb_object_id]:
                sc.Copy(
                    ref_object_id=copied_bom_item_oid,
                    **SelectionCondition.MakeChangeControlAttributes()
                )

    def _keep_selection_conditions_bom_item_ref_object_ids(self, ctx):
        bom_item_ref_object_ids = AssemblyComponent.KeywordQuery(
            baugruppe=self.teilenummer, b_index=self.t_index
        ).cdb_object_id
        ctx.keep("bom_item_ref_object_ids", json.dumps(bom_item_ref_object_ids))

    def _delete_selection_conditions(self, ctx):
        bom_item_ref_object_ids = json.loads(ctx.ue_args["bom_item_ref_object_ids"])
        SelectionCondition.KeywordQuery(ref_object_id=bom_item_ref_object_ids).Delete()

    def update_variant_part_name(self, variant):
        """
        Changes the name of the variant part

        This function is called during instantiate on the newly created
        part or during reinstantiate on newly created (indexed) part
        """

        # Note: variant name and benennung2 are both not multilanguage attributes
        if variant.name is not None or variant.name != "":
            self.benennung2 = variant.name[: Item.benennung2.length]

        descriptions = self.GetLocalizedValues("i18n_benennung")

        for lang_key, each_value in descriptions.items():
            if each_value == "":
                continue

            new_name = "Var{0}-{1}".format(variant.id, each_value)
            self.SetLocalizedValue(
                "i18n_benennung", lang_key, new_name[: Item.benennung.length]
            )

    def handle_instantiate_copy_pre(self, ctx, instance_type_flag=None):
        """called during operation 'cs_variant_instantiate' at 'pre' time

        instance_type_flag indicate if it is called for root part or sub part

        instance_type_flag can either be:
            * cs.variants.api.constants_api.IS_INSTANTIATE_CREATE_ROOT_PART (for root part)
            * cs.variants.api.constants_api.IS_INSTANTIATE_CREATE_SUB_PART (for sub part)

        """
        self.materialnr_erp = self.teilenummer

    def handle_instantiate_copy_relships(self, ctx, instance_type_flag=None):
        """called during operation 'cs_variant_instantiate' at 'relship_copy' time

        instance_type_flag indicate if it is called for root part or sub part

        instance_type_flag can either be:
            * cs.variants.api.constants_api.IS_INSTANTIATE_CREATE_ROOT_PART (for root part)
            * cs.variants.api.constants_api.IS_INSTANTIATE_CREATE_SUB_PART (for sub part)

        """
        ctx.skip_relationship_copy()

    def has_instanced_parts(self):
        instanced_parts = VariantPart.KeywordQuery(
            maxbom_teilenummer=self.teilenummer, maxbom_t_index=self.t_index
        )

        return len(instanced_parts) > 0

    def _allow_max_bom_delete(self, _):
        if self.has_instanced_parts():
            raise ue.Exception("cs_variants_delete_max_bom_with_instanced_parts")

    event_map = {
        ("relship_copy", "post"): "_copy_selection_conditions",
        ("delete", "pre"): (
            "_keep_selection_conditions_bom_item_ref_object_ids",
            "_allow_max_bom_delete",
        ),
        ("delete", "post"): "_delete_selection_conditions",
    }


@sig.connect(Item, "copy", "pre")
def _handle_instantiate_copy_pre(item, ctx):
    if IS_INSTANTIATE in ctx.sys_args.get_attribute_names():
        ctx.keep(IS_INSTANTIATE, ctx.sys_args[IS_INSTANTIATE])
        item.handle_instantiate_copy_pre(ctx, ctx.sys_args[IS_INSTANTIATE])


@sig.connect(Item, "relship_copy", "pre")
def _handle_instantiate_copy_relships(item, ctx):
    if IS_INSTANTIATE in ctx.ue_args.get_attribute_names():
        item.handle_instantiate_copy_relships(ctx, ctx.ue_args[IS_INSTANTIATE])


@sig.connect(DERIVED_BOM_CREATED)
def _derived_mbom_created(item, rbom, ctx):
    # adds the new bom as maxbom to all variability models of the original item
    if ctx is not None and ctx.action == "bommanager_create_rbom":
        sqlapi.SQLinsert(
            "INTO cs_variability_model_part (teilenummer, t_index, variability_model_object_id) "
            "SELECT '%s', '%s', variability_model_object_id FROM cs_variability_model_part "
            "WHERE teilenummer='%s' and t_index='%s'"
            % (rbom.teilenummer, rbom.t_index, item.teilenummer, item.t_index)
        )


@sig.connect(Item, "classification_update", "pre_commit")
def _check_item_classification(item, _, classification_diff_data):
    # TODO: think about another way to provide information to classification signal that this should not check
    if classification_diff_data.get(CLASSIFICATION_FLAG_FOR_INSTANTIATOR, False):
        return

    variant = item.Variant

    if variant is None:
        return

    classification_class = variant.get_classification_class()
    check_for_not_allowed_variability_classification_class_deletion(
        classification_class, classification_diff_data
    )

    if not is_variability_classification_class_affected(
        classification_class, classification_diff_data
    ):
        return

    variants_classification = VariantsClassification([classification_class.code])
    not_allowed_changed_properties = []
    for (
        property_definition,
        diff_property_entry,
    ) in get_all_variant_driving_properties_from_classification_diff_data(
        variants_classification, classification_diff_data
    ):
        if "old_value" in diff_property_entry:
            not_allowed_changed_properties.append(
                "{name} ({code})".format(**property_definition)
            )

    if not_allowed_changed_properties:
        raise UeExceptionChangedPropertiesNotAllowedOnItem(
            not_allowed_changed_properties
        )


@sig.connect(Item, list, "cs_variant_reinstantiate_part", "pre_mask")
def _reinstantiate_part_pre_mask(all_parts, ctx):
    variant_parts = VariantPart.get_all_belonging_to_parts(all_parts)
    if len(variant_parts) != len(all_parts):
        raise ue.Exception("cs_variants_only_variant_parts")

    denied_parts = []
    for each_part in all_parts:
        if not each_part.CheckAccess("save") and not each_part.CheckAccess("index"):
            denied_parts.append(each_part)

    if denied_parts:
        raise ue.Exception(
            "cs_variants_not_allowed_to_reinstantiate",
            "\n".join([x.GetDescription() for x in denied_parts]),
        )

    parts_unique_max_bom_part_numbers = set(variant_parts.maxbom_teilenummer)
    if len(parts_unique_max_bom_part_numbers) != 1:
        raise ue.Exception("cs_variants_only_unique_max_bom")

    unique_max_bom_part_number = parts_unique_max_bom_part_numbers.pop()
    ctx.set("teilenummer", unique_max_bom_part_number)

    max_boms = Item.KeywordQuery(teilenummer=unique_max_bom_part_number).Execute()
    if len(max_boms) == 1:
        ctx.set("max_bom_id", max_boms[0].cdb_object_id)


@sig.connect(Item, list, "cs_variant_reinstantiate_part", "now")
def _reinstantiate_part_now(all_parts, ctx):
    max_bom_id = getattr(ctx.dialog, "max_bom_id", None)

    if max_bom_id is None:
        raise ue.Exception("cs_variants_select_maxbom")

    max_bom = Item.ByKeys(cdb_object_id=max_bom_id)

    if max_bom is None:
        raise ue.Exception("cs_variants_select_maxbom")

    try:
        reinstantiate_parts(all_parts, maxbom=max_bom)
    except NotAnInstanceException as ex:
        LOG.exception(ex)
        raise ue.Exception("cs_variant_part_missing_maxbom")
    except NotAllowedToReinstantiateError as ex:
        LOG.exception(ex)
        raise ue.Exception(
            "cs_variants_not_allowed_to_reinstantiate",
            ex.part.GetDescription(),
        )
    except MultiplePartsReinstantiateWithFailedPartsError as ex:
        LOG.exception(ex)
        raise ue.Exception(
            "cs_variants_error_part_reinstantiation",
            len(ex.failed_parts_exceptions),
            len(ex.all_parts_lookup),
            "\n".join(
                [
                    ex.all_parts_lookup[x].GetDescription()
                    for x in ex.failed_parts_exceptions
                ]
            ),
        )
    except SelectionConditionEvaluationError as ex:
        LOG.error(ex.build_message(), exc_info=True)
        if isinstance(ex.__cause__, PropertyValueNotFoundException):
            raise ue.Exception(
                "cs_variants_property_value_not_found", ex.__cause__.property_code
            )
        raise ue.Exception("cs_variants_selection_condition_expression_exception")
    except VariantIncompleteError as ex:
        LOG.exception(ex)
        raise ue.Exception("cs_variants_assigned_characteristics")
    except Exception as ex:
        LOG.exception(ex)
        raise ue.Exception("just_a_replacement", str(ex))


@sig.connect(Item, "delete", "post")
def _remove_item_from_sub_part(part, ctx):
    all_sub_parts = VariantSubPart.KeywordQuery(part_object_id=part.cdb_object_id)
    all_sub_parts.Delete()


@sig.connect(Variant, list, "cs_variant_instantiate", "pre_mask")
def _instantiate_part_pre_mask(objs, ctx):
    var_model_ids = {x.variability_model_id for x in objs}
    if len(var_model_ids) != 1:
        raise ue.Exception("cs_variants_only_unique_variability_model")
    ctx.set("variability_model_id", var_model_ids.pop())

    max_bom_id = getattr(ctx.dialog, "max_bom_id", None)
    if max_bom_id is not None and max_bom_id != "":
        ctx.skip_dialog()
    else:
        ctx.set_readonly("variability_model_id")


@sig.connect(Variant, list, "cs_variant_instantiate", "now")
def _instantiate_part_now(all_variants, ctx):
    max_bom_id = getattr(ctx.dialog, "max_bom_id", None)

    if max_bom_id is None:
        raise ue.Exception("cs_variants_select_maxbom")

    max_bom = Item.ByKeys(cdb_object_id=max_bom_id)

    if max_bom is None:
        raise ue.Exception("cs_variants_select_maxbom")

    failed_variants = []

    for variant in all_variants:
        try:
            try:
                instantiate_part(variant, max_bom)
            except SelectionConditionEvaluationError as ex:
                LOG.error(ex.build_message(), exc_info=True)
                if isinstance(ex.__cause__, PropertyValueNotFoundException):
                    raise ue.Exception(
                        "cs_variants_property_value_not_found",
                        ex.__cause__.property_code,
                    )
                raise ue.Exception(
                    "cs_variants_selection_condition_expression_exception"
                )
            except VariantIncompleteError as ex:
                LOG.exception(ex)
                raise ue.Exception("cs_variants_assigned_characteristics")
            except Exception as ex:
                LOG.exception(ex)
                raise ue.Exception("just_a_replacement", str(ex))
        except ue.Exception:
            if len(all_variants) == 1:
                raise

            failed_variants.append(variant)

    if failed_variants:
        raise ue.Exception(
            "cs_variants_error_part_instantiation",
            len(failed_variants),
            len(all_variants),
            "\n".join([x.GetDescription() for x in failed_variants]),
        )


@sig.connect(VariantPart, "create", "post")
def _instantiate_part_post(variant_part, _ctx):
    ProductPart.CreateIfNoConflict(
        product_object_id=variant_part.VariabilityModel.product_object_id,
        teilenummer=variant_part.teilenummer,
        t_index=variant_part.t_index,
    )


@classbody
class AssemblyComponentOccurrence:
    SelectionConditions = Reference_N(
        SelectionCondition,
        SelectionCondition.ref_object_id == AssemblyComponentOccurrence.cdb_object_id,
    )
