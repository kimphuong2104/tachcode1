# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
from cdb import constants
from cdb.objects import operations
from cs.variants import VariantPart, VariantSubPart
from cs.variants.api import helpers
from cs.variants.api.constants_api import (
    IS_INSTANTIATE,
    IS_INSTANTIATE_CREATE_ROOT_PART,
    IS_INSTANTIATE_CREATE_SUB_PART,
)
from cs.variants.api.instantiate_options import InstantiateOptions
from cs.vp import bom, items


def rebuild_instance(root_instance, lookup):
    helpers.copy_variant_classification(lookup.variant, root_instance)
    reinstantiate_recursive(lookup.variant_bom, root_instance, lookup)
    root_instance.Reload()


def reinstantiate_recursive(variant_bom_node, instance, lookup):
    """

    :param variant_bom_node:
    :type variant_bom_node: cs.variants.api.variant_bom_node.VariantBomNode
    :param instance:
    :param lookup:
    :type lookup: cs.variants.api.instantiate_lookup.InstantiateLookup
    :return:
    """
    for each in variant_bom_node.bom_items_to_delete:
        helpers.delete_with_operation(each)

    for each_variant_bom_node in variant_bom_node.children:
        comp = each_variant_bom_node.value

        if each_variant_bom_node.is_no_old_existing:
            # make it new or reuse an existing
            # the old one is from maxbom
            # or added after instantiated (maybe from different rule or manually)
            new_sub_instance = _get_instance_from_reuse_lookup(
                each_variant_bom_node, lookup
            )
            if new_sub_instance is None:
                new_sub_instance = make_sub_instance(
                    comp, each_variant_bom_node, lookup
                )
                instantiate_recursive(each_variant_bom_node, new_sub_instance, lookup)

            new_bom_item = _copy_bom_item(
                each_variant_bom_node, instance, new_sub_instance
            )
            _update_occurrences(each_variant_bom_node, new_bom_item, False)

        elif each_variant_bom_node.is_original_needed:
            # switch back to the original from maxbom
            new_bom_item = _copy_bom_item(each_variant_bom_node, instance, comp)
            _update_occurrences(each_variant_bom_node, new_bom_item, False)

        else:
            # At this point we are sure we only hit bom_items which are unique to this instance
            # this also means we are sure that a `ref_to_bom_items` always exists
            if each_variant_bom_node.is_must_be_instantiated:
                _handle_reinstantiate_node(comp, each_variant_bom_node, lookup)
            # update the current
            _update_old_bom_item_attributes(each_variant_bom_node)

            _update_occurrences(
                each_variant_bom_node, each_variant_bom_node.ref_to_bom_item, True
            )

            if helpers.is_reuse_enabled():
                each_variant_bom_node.update_checksum(
                    lookup.variant.variability_model_id
                )


def _handle_reinstantiate_node(bom_item, variant_bom_node, lookup):
    """handle reinstantiate of a single node

    :param bom_item: the bom_item to operate on
    :param variant_bom_node:
    :type variant_bom_node: cs.variants.api.variant_bom_node.VariantBomNode
    :param lookup:
    :type lookup: cs.variants.api.instantiate_lookup.InstantiateLookup
    :return:
    """
    if not variant_bom_node.ref_to_bom_item.Item.CheckAccess("save"):
        _replace_instance(variant_bom_node, bom_item, lookup)

    elif variant_bom_node.has_somewhere_deep_changed:
        _handle_has_somewhere_deep_changed(variant_bom_node, bom_item, lookup)

    else:
        # update old deep
        reinstantiate_recursive(
            variant_bom_node,
            variant_bom_node.ref_to_bom_item.Item,
            lookup,
        )


def _get_instance_from_reuse_lookup(variant_bom_node, lookup):
    if not helpers.is_reuse_enabled():
        return None

    pk_value = variant_bom_node.get_identification_key_values()
    if pk_value in variant_bom_node.parent.reuse_children_lookup:
        return variant_bom_node.parent.reuse_children_lookup[pk_value]

    pkey_tuple = (variant_bom_node.value.teilenummer, variant_bom_node.value.t_index)
    return lookup.reinstantiate_lookup.get(pkey_tuple, None)


def _handle_has_somewhere_deep_changed(each_variant_bom_node, comp, lookup):
    new_sub_instance = _get_instance_from_reuse_lookup(each_variant_bom_node, lookup)
    if new_sub_instance is not None:
        _replace_ref_to_bom_item(each_variant_bom_node, new_sub_instance)

    else:
        number_usage = helpers.count_part_used_in_bom_items(
            each_variant_bom_node.ref_to_bom_item.teilenummer,
            each_variant_bom_node.ref_to_bom_item.t_index,
        )

        if number_usage == 1:
            # inplace update old deep
            reinstantiate_recursive(
                each_variant_bom_node,
                each_variant_bom_node.ref_to_bom_item.Item,
                lookup,
            )
        else:
            # this is the most top level point we are detect there is a another usage
            # of this part somewhere.
            _replace_instance(each_variant_bom_node, comp, lookup)


def build_instance(root_instance, lookup):
    instantiate_recursive(lookup.variant_bom, root_instance, lookup)
    root_instance.Reload()


def instantiate_recursive(variant_bom_node, instance, lookup):
    all_children_nodes = [(x, instance) for x in variant_bom_node.children]
    while all_children_nodes:
        current_children_node, current_children_instance = all_children_nodes.pop()
        if current_children_node.is_must_be_instantiated:
            new_sub_instance = _get_instance_from_reuse_lookup(
                current_children_node, lookup
            )
            if new_sub_instance is None:
                new_sub_instance = make_sub_instance(
                    current_children_node.value, current_children_node, lookup
                )
                all_children_nodes.extend(
                    [(x, new_sub_instance) for x in current_children_node.children]
                )
        else:
            new_sub_instance = current_children_node.value
        new_bom_item = _copy_bom_item(
            current_children_node, current_children_instance, new_sub_instance
        )
        _update_occurrences(current_children_node, new_bom_item, False)


def get_instantiated_of(variability_model_id, part_object_id):
    """
    Returns the object_id of the part from which the `part_object_id` was created.

    :param variability_model_id: variability model object id
    :type variability_model_id: str
    :param part_object_id: part object id
    :type part_object_id: str
    :return: part object id or None
    """
    obj = VariantSubPart.ByKeys(
        variability_model_id=variability_model_id, part_object_id=part_object_id
    )

    if obj:
        return obj.instantiated_of_part_object_id
    return None


def make_root_instance(maxbom, variant):
    """
    create a new root instance from given maxbom

    register the created instance as `VariantPart` and
    the classification of the `variant` is copied to the new instance.

    raises an TypeError if source_object is not a Item.

    :param maxbom: the maxbom
    :type maxbom: cs.vp.items.Item
    :param variant: the variant
    :type variant: cs.variants.Variant
    :return: the new instance (Item)
    :rtype: cs.vp.items.Item
    """
    if not isinstance(maxbom, items.Item):
        raise TypeError("'source_object' needs to be of type 'Item'")

    instance = _create_instance(maxbom, instance_type=IS_INSTANTIATE_CREATE_ROOT_PART)
    instance.update_variant_part_name(variant)

    helpers.copy_variant_classification(variant, instance)
    operations.operation(
        constants.kOperationNew,
        VariantPart,
        variability_model_id=variant.variability_model_id,
        variant_id=variant.id,
        teilenummer=instance.teilenummer,
        t_index=instance.t_index,
        maxbom_teilenummer=maxbom.teilenummer,
        maxbom_t_index=maxbom.t_index,
    )

    return instance


def make_sub_instance(source_object, variant_bom_node, lookup):
    """
    create a new sub instance from given `source_object`

    register the created instance as `VariantSubPart`

    raises an TypeError if source_object is neither a Item or AssemblyComponent.

    :param variant_bom_node: the variant bom node
    :type variant_bom_node: cs.variants.api.variant_bom_node.VariantBomNode
    :param source_object: source_object can be `Item` or `AssemblyComponent`
    :type source_object: Item or AssemblyComponent
    :param lookup: the lookup
    :type lookup: cs.variants.api.instantiate_lookup.InstantiateLookup
    :return: the new instance
    :rtype: cs.vp.items.Item
    """
    if isinstance(source_object, items.Item):
        item = source_object
    elif isinstance(source_object, bom.AssemblyComponent):
        item = source_object.Item
    else:
        raise TypeError(
            "'source_object' needs to be of type 'Item' or 'AssemblyComponent'"
        )

    instance = _create_instance(item, instance_type=IS_INSTANTIATE_CREATE_SUB_PART)
    VariantSubPart.Create(
        variability_model_id=lookup.variant.variability_model_id,
        instantiated_of_part_object_id=item.cdb_object_id,
        part_object_id=instance.cdb_object_id,
        structure_checksum=variant_bom_node.checksum,
    )
    lookup.reinstantiate_lookup[(item.teilenummer, item.t_index)] = instance
    return instance


def make_indexed_instance(variant_part):
    """
    create and return a new index of the given `variant_part`

    the index is created with the operation `CDB_Index`
    this will also write the newly created part into the `VariantPart` table

    Note:
    The relationship `cdbvp_aggregation_1_N_only_index` is used to manage the link to `VariantPart`

    :param variant_part: the part to index
    :type variant_part: cs.vp.items.Item
    :return: the new indexed part
    :rtype: cs.vp.items.Item
    """
    indexed_part = operations.operation("CDB_Index", variant_part)
    return indexed_part


def _create_instance(source_item, instance_type=""):
    """
    create a new instance from given `item`

    :param source_item: the source object
    :type source_item: cs.vp.items.Item
    :param instance_type: type which should be emitted to adapt attributes
    :type instance_type: str
    :return: the new instance
    :rtype: cs.vp.items.Item
    """
    instance = operations.operation(
        constants.kOperationCopy,
        source_item,
        operations.system_args(**{IS_INSTANTIATE: instance_type}),
        teilenummer="#",
        t_index="",
    )

    return instance


def _replace_instance(each_variant_bom_node, comp, lookup):
    """
    make a new instance and replace `each_variant_bom_node.ref_to_bom_item` with the new one

    Note:
    we change the primary keys of the bom_item (teilenummer, t_index)

    :param each_variant_bom_node:
    :param comp:
    :param lookup:
    :return:
    """
    new_sub_instance = make_sub_instance(comp, each_variant_bom_node, lookup)
    instantiate_recursive(each_variant_bom_node, new_sub_instance, lookup)
    _replace_ref_to_bom_item(each_variant_bom_node, new_sub_instance)


def _replace_ref_to_bom_item(each_variant_bom_node, new_sub_instance):
    """
    replace the teilenummer and t_index of a the bom_item ref

    Note:
        The decision was to go with this solution for now until there are problems with it.
        The thing is that we are *updating primary keys* here!
        This means that objects related to this bom_item are lost (occurrences also!)

    :param each_variant_bom_node:
    :param new_sub_instance:
    :return:
    """
    each_variant_bom_node.ref_to_bom_item = operations.operation(
        constants.kOperationModify,
        each_variant_bom_node.ref_to_bom_item,
        teilenummer=new_sub_instance.teilenummer,
        t_index=new_sub_instance.t_index,
    )


def _copy_bom_item(variant_bom_node, instance, subinstance):
    """
    copies the bom_item

    :param variant_bom_node:
    :type variant_bom_node: cs.variants.api.variant_bom_node.VariantBomNode
    :param instance: the target instance (baugruppe)
    :param subinstance: the target subinstance (teilenummer)
    :return:
    """
    attrs = {
        "baugruppe": instance.teilenummer,
        "b_index": instance.t_index,
        "teilenummer": subinstance.teilenummer,
        "t_index": subinstance.t_index,
    }

    if variant_bom_node.has_occurrences:
        attrs["menge"] = len(variant_bom_node.occurrences)

    # don't use cdb.operations here, because that would copy the bom_item_occurrences
    # and the selection conditions
    new_bom_item = variant_bom_node.value.Copy(**attrs)
    return new_bom_item


def _update_occurrences(source, target, update_attributes):
    """
    updates the occurrences on the given `target`

    the following steps are made:
        * if occ exists on `target` the attributes will be updated
        * if occ does not exist on `target` it will be copied from `source`
        * if occ exists on `target` but not on `source` it will be deleted

    if `update_attributes` is True then the attributes of existing occurrences
    in the target are updated.

    :param source: the source VariantBomNode
    :type source: cs.variants.api.variant_bom_node.VariantBomNode
    :param target: the target
    :type target: cs.vp.bom.AssemblyComponent
    :param update_attributes: flag if existing should be updated
    :type update_attributes: bool

    :return:
    """
    old_instantiated_bom_item_occurrences_lookup = {
        _make_bom_item_occurrence_only_specific_keys(each): each
        for each in target.Occurrences
    }

    bom_item_of_maxbom_occurrences = source.occurrences
    if bom_item_of_maxbom_occurrences:
        amount_occurrences = 0
        for each in bom_item_of_maxbom_occurrences:
            each_keys = _make_bom_item_occurrence_only_specific_keys(each)
            # Pop here important otherwise it would get deleted
            old_instantiated_bom_item_occurrences = (
                old_instantiated_bom_item_occurrences_lookup.pop(each_keys, None)
            )
            amount_occurrences += 1

            if old_instantiated_bom_item_occurrences is None:
                # Not found means we have to copy it
                # do not use cdb.operations here, because that would copy the bom_item_occurrences
                # and the selection conditions
                each.Copy(
                    bompos_object_id=target.cdb_object_id,
                )

            elif update_attributes:
                # If we find an old we have to update attributes
                attributes = (
                    InstantiateOptions.get_bom_item_occurrences_attributes_to_update(
                        each
                    )
                )
                old_instantiated_bom_item_occurrences.Update(**attributes)

        # the 'if' is a small optimisation to reduce the number of sql queries
        if target.menge != amount_occurrences:
            target.menge = amount_occurrences

    # Every value which still exists in lookup is too much and has to be deleted
    for each in old_instantiated_bom_item_occurrences_lookup.values():
        helpers.delete_with_operation(each)

    # if we are working without occurrences we need to update the
    # menge attribute with the value from the original bom_item
    if not source.has_occurrences and target.menge != source.value.menge:
        target.menge = source.value.menge


def _make_bom_item_occurrence_only_specific_keys(bom_item_occurrence):
    """
    return a string with all values only specific keys
    :param bom_item_occurrence: AssemblyComponentOccurrence
    :return:
    :rtype: str
    """
    from cs.variants.api.constants_api import SEPARATOR
    from cs.variants.api.variant_bom_node import VariantBomNode

    return SEPARATOR.join(
        ["%s" % bom_item_occurrence[key] for key in VariantBomNode.occurrence_keys]
    )


def _update_old_bom_item_attributes(variant_bom_node):
    """update the bom item attributes only if changes"""
    comp_attributes = InstantiateOptions.get_bom_item_attributes_to_update(
        variant_bom_node.value
    )
    ref_attributes = InstantiateOptions.get_bom_item_attributes_to_update(
        variant_bom_node.ref_to_bom_item
    )

    if comp_attributes == ref_attributes:
        return
    variant_bom_node.ref_to_bom_item.Update(**comp_attributes)
