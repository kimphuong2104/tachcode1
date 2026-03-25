# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import collections
import json

from cs.vp.bom.enhancement import FlatBomEnhancement
from webob import exc

from cs.platform.web import JsonAPI, root
from cs.platform.web.rest import get_collection_app
from cs.vp.bom import AssemblyComponent
from cs.vp.bom.bomqueries import flat_bom
from cs.vp.items import Item
from cs.documents import Document
from cs.web.components.ui_support import forms
from cdb.objects import Rule
from cs.threed.hoops import _MODEL_RULE


def is_cs_variants_installed():
    try:
        from cs.variants import Variant

        return True
    except ImportError:
        return False


class PreviewInternal(JsonAPI):
    pass


class PreviewModel(object):
    pass


@root.Internal.mount(app=PreviewInternal, path="threed_preview")
def _mount_preview_internal():
    return PreviewInternal()


@PreviewInternal.path(path="", model=PreviewModel)
def _main():
    return PreviewModel()


def _assembly_component_to_keys(item):
    if hasattr(item, "baugruppe"):
        return {
            "teilenummer": item.teilenummer,
            "t_index": item.t_index,
            "baugruppe": item.baugruppe,
            "b_index": item.b_index,
            "position": str(item.position),
            "variante": item.variante,
            "auswahlmenge": item.auswahlmenge,
            "cdb_object_id": item.cdb_object_id,
        }

    return {
        "teilenummer": item.teilenummer,
        "t_index": item.t_index,
    }


def _build_tnode_path(tnode, path):
    path.append(_assembly_component_to_keys(tnode.value))

    if tnode.parent is None:
        return

    _build_tnode_path(tnode.parent, path)


class TNode(object):
    def __init__(self, value=None):
        self.value = value
        self.parent = None
        self.children = []


def _build_tree(root, flatbom, max_depth):
    def _build(node, depth=0):
        depth += 1
        if max_depth and depth > max_depth:
            return
        for c in children[(node.value.teilenummer, node.value.t_index)]:
            cnode = TNode(c)
            cnode.parent = node
            node.children.append(cnode)
            all_parts[(c.teilenummer, c.t_index)].append(cnode)
            _build(cnode, depth)

    all_parts = collections.defaultdict(list)
    children = collections.defaultdict(set)
    for r in flatbom:
        children[(r.baugruppe, r.b_index)].add(r)

    root.menge = 1.0
    rootNode = TNode(root)
    _build(rootNode)

    return all_parts


def _get_variant_filter(variant_object_id, variability_model_id=None):
    try:
        from cs.variants import Variant
        from cs.variants.api.filter import VariantFilter

        variant = Variant.KeywordQuery(cdb_object_id=variant_object_id)
        variant_filter = VariantFilter(variant[0])
        return variant_filter
    except ImportError:
        from cs.vp.variants import filter as variant_filters, Variant

        variant = Variant.KeywordQuery(cdb_object_id=variant_object_id)
        return variant_filters.VariantBOMFilter(variability_model_id, variant[0].id)


def _get_variant_filter_for_signature(variability_model_id, signature):
    try:
        from cs.variants.api.filter import PropertiesBasedVariantFilter

        classification_attributes = json.loads(signature)
        variant_filter = PropertiesBasedVariantFilter(
            variability_model_id, classification_attributes
        )
        return variant_filter
    except ImportError:
        from cs.vp.variants import filter as variant_filters, Variant

        variant_filter = variant_filters.VirtualVariantBOMFilter(
            variability_model_id, signature
        )
        return variant_filter


@PreviewInternal.json(
    model=PreviewModel, name="filtered_pathes_by_variant_filter", request_method="POST"
)
def _filtered_pathes_by_variantfilter(model, request):

    data = request.json
    root_item = None
    try:
        root_item = Document.ByKeys(cdb_object_id=data.get("document_object_id")).Item
    except AttributeError:
        raise exc.HTTPNotFound()

    if root_item is None:
        raise exc.HTTPNotFound()

    variant_filter = None

    variant_object_id = data.get("variant", None)
    variability_model_id = data.get("variability_model_id", None)
    signature = data.get("signature", None)

    if variant_object_id is not None:
        variant_filter = _get_variant_filter(variant_object_id, variability_model_id)

    elif variability_model_id is not None and signature is not None:
        variant_filter = _get_variant_filter_for_signature(
            variability_model_id, signature
        )
    else:
        raise exc.HTTPUnprocessableEntity()

    # we do not need call flat_bom if we know we have nothing to filter
    if variant_filter is None:
        return []

    records = _get_flat_bom_records_with_occurrences(root_item)
    all_parts = _build_tree(root_item, records, False)
    all_pathes = list()

    for comp in records:
        if not variant_filter.eval_bom_item(comp):
            tnode_list = all_parts[(comp.teilenummer, comp.t_index)]
            for each_tnode in tnode_list:
                node_path = []
                _build_tnode_path(each_tnode, node_path)
                node_path.reverse()
                all_pathes.append(node_path)

        elif comp["has_sc_on_oc"] == 1:
            bom_items = AssemblyComponent.FromRecords([comp])
            bom_item_occurrences = bom_items[0].Occurrences.Execute()
            for occurrence in bom_item_occurrences:
                if not variant_filter.eval_bom_item(occurrence):
                    tnode_list = all_parts[(comp.teilenummer, comp.t_index)]
                    for each_tnode in tnode_list:
                        node_path = []
                        _build_tnode_path(each_tnode, node_path)
                        node_path.reverse()
                        node_path[-1]["relative_transformation"] = occurrence.relative_transformation
                        all_pathes.append(node_path)
    return all_pathes


def _get_flat_bom_records_with_occurrences(root_item):
    params = {}

    if is_cs_variants_installed():
        from cs.variants.api.filter import BomPredicatesAttrFlatBomPlugin

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(BomPredicatesAttrFlatBomPlugin())

        params["bom_enhancement"] = bom_enhancement

    return flat_bom(root_item, **params)


@PreviewInternal.json(model=PreviewModel, name="get_document", request_method="POST")
def _get_document(model, request):
    data = request.json
    cdb_object_id = data.get("cdb_object_id", None)

    if cdb_object_id == None:
        raise exc.HTTPBadRequest()

    item = Item.ByKeys(cdb_object_id=cdb_object_id)
    if not item:
        return None

    doc = item.get_3d_model_document()
    if not doc:
        return None

    return doc.cdb_object_id

@PreviewInternal.json(model=PreviewModel, name="get_root_has_model", request_method="POST")
def _get_root_has_model(model, request):
    data = request.json
    context_object_id = data.get("context_object_id", None)

    if context_object_id is None:
        raise exc.HTTPBadRequest()

    context_object = Item.ByKeys(cdb_object_id=context_object_id)
    if context_object is None:
        return True

    rule = Rule.ByKeys(_MODEL_RULE)
    return rule.match(context_object)