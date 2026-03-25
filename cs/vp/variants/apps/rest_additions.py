# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.objects import fields
from cdb.objects import IconCache
from cdb.objects.core import CDBClassDef
from cdb.objects.core import Object
from cdb import sqlapi

from cs.platform.web.permissions import ReadPermission
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.generic.model import Workflow
from cs.platform.web.rest.relship.main import make_relship_target, RelshipTarget, RelshipApp, _render_relship
from cs.platform.web.root import get_v1

from webob.exc import HTTPBadRequest

from cs.vp import bom
from cs.vp.items import Assembly
from cs.vp.variants import Variant
from cs.vp.variants.bomlinks import BOM_Predicate
from cs.vp.variants.filter import VariantBOMFilter
from cs.vp.variants.items import Item, AssemblyComponent
from cs.vp.bom.search import BomItemAttributeAccessor

from .instance_wizard.utils import safe_int


def _fp(value):  # Format a Parameter for an sql query
    if value in [None, sqlapi.NULL]:
        return ''
    return sqlapi.quote(value)


def _add_current_status(_, obj, rendered_obj, additional_objects, *args, **kwargs):
    if obj.GetClassDef().has_workflow():
        work_flow_information = Workflow(obj)
        rendered_obj['system:current_status'] = work_flow_information.current_status
    elif isinstance(obj, AssemblyComponent):
        item = additional_objects.get('item') if 'item' in additional_objects else None
        if item is not None:
            work_flow_information = Workflow(item)
            rendered_obj['system:current_status'] = work_flow_information.current_status


def _add_selection_predicates(request, obj, rendered_obj, additional_objects):
    if isinstance(obj, AssemblyComponent):
        collection_app = get_v1(request).child('collection')
        bom_item_app = collection_app.child(GenericApp, rest_name="bom_item")
        predicates = additional_objects.get('predicates') if 'predicates' in additional_objects else None
        sel_pred_rs = RelshipTarget(obj,
                                    "SelectionPredicates",
                                    PresentRelshipResolver(predicates,
                                                           BOM_Predicate.__classname__)) if predicates is not None else make_relship_target(obj, "SelectionPredicates")
        enriched_sel_pred_rs = request.view(sel_pred_rs, app=bom_item_app, name='complete-target-with-status')
        if 'system:resolved_relships' in rendered_obj:
            rendered_obj['system:resolved_relships'].append(enriched_sel_pred_rs)
        else:
            rendered_obj['system:resolved_relships'] = [enriched_sel_pred_rs]


def _add_item(request, obj, rendered_obj, additional_objects):
    if isinstance(obj, AssemblyComponent):
        collection_app = get_v1(request).child('collection')
        bom_item_app = collection_app.child(GenericApp, rest_name="bom_item")
        item = additional_objects.get('item') if 'item' in additional_objects else None
        has_children = additional_objects.get('has_children') if 'has_children' in additional_objects else None
        item_target = RelshipTarget(obj,
                                    "Item",
                                    PresentRelshipResolver(BackpackObject(item,
                                                                          dict(has_children=has_children)),
                                                           Item.__classname__, True)) if item is not None else make_relship_target(obj, "Item")
        enriched_item_rs = request.view(item_target, app=bom_item_app, name='complete-bom-item-target')
        if 'system:resolved_relships' in rendered_obj:
            rendered_obj['system:resolved_relships'].append(enriched_item_rs)
        else:
            rendered_obj['system:resolved_relships'] = [enriched_item_rs]


def _add_icon(request, obj, rendered_obj, additional_objects):
    if isinstance(obj, AssemblyComponent):
        item = additional_objects.get('item') if 'item' in additional_objects else None
        if item is not None:
            icon = IconCache.getIcon(
                "cdbvp_part",
                t_kategorie=item.t_kategorie,
                cdbvp_positionstyp=obj.cdbvp_positionstyp,
                cdbvp_has_condition=obj.cdbvp_has_condition
            )
            rendered_obj["system:icon_link"] = icon


def _add_has_children(_, obj, rendered_obj, additional_objects):
    if isinstance(obj, Item):
        has_children = additional_objects.get('has_children') if 'has_children' in additional_objects else len(obj.Components) > 0
        rendered_obj['system:has_children'] = has_children


def _add_bom_item_description(request, obj, rendered_obj, additional_objects):
    if isinstance(obj, AssemblyComponent):
        item = additional_objects.get('item') if 'item' in additional_objects else obj.Item
        bom_node_tag = get_bomnode_tag()
        rendered_obj["system:bom_item_description"] = bom_node_tag % BomItemAttributeAccessor(obj, item)


_OPCONTEXT = "VariantMatrix"


def _make_operations_dict(_, obj, rendered_obj, *args, **kwargs):
    result = []
    oh = obj.ToObjectHandle()
    for oi in sorted(oh.getOperationInfos(context_name=_OPCONTEXT),
                     key=lambda oi: oi.get_opname()):
        urls = oi.get_icon_urls()
        result.append({"name": oi.get_opname(),
                       "href": obj.MakeURL(oi.get_opname()),
                       "tooltip": oi.get_tooltip(),
                       "iconUrl": ("/" + urls[0]) if urls else "",
                       "label": "/".join(oi.get_label_path()),
                       })
    rendered_obj["system:variant_matrix_operations"] = result


def _make_variant_operations_dict(_, obj, rendered_obj, *args, **kwargs):
    result = []
    oh = obj.ToObjectHandle()
    for oi in sorted(oh.getOperationInfos(True, "VariantMatrixVariant"),
                     key=lambda oi: oi.get_opname()):
        urls = oi.get_icon_urls()
        result.append({"name": oi.get_opname(),
                       "href": obj.MakeURL(oi.get_opname()),
                       "tooltip": oi.get_tooltip(),
                       "iconUrl": ("/" + urls[0]) if urls else "",
                       "label": "/".join(oi.get_label_path()),
                       })
    rendered_obj["system:variant_matrix_operations"] = result


BOM_NODE_TAG = None


def get_bomnode_tag():
    global BOM_NODE_TAG
    if BOM_NODE_TAG is None:
        from cdb.platform.gui import Message
        from cdb.objects.core import parse_raw
        msg = Message.ByKeys('bom_node_tag')
        if msg:
            dtag = msg.Text['']
        else:
            dtag = ""
            cldef = None
            try:
                cldef = CDBClassDef('bom_item')
                dtag = cldef.getObjDescriptionPattern()
            except RuntimeError:
                pass
        if not dtag:
            dtag = 'position + ": " + menge + "x " + teilenummer + "/" + t_index'
        BOM_NODE_TAG = parse_raw(dtag)
    return BOM_NODE_TAG


def _generic_enrich_renderer(request, list_of_additions):
    def enrichRenderer(obj, **kwargs):
        obj_to_render = obj.obj if isinstance(obj, BackpackObject) else obj
        additional_objects = obj.additional_objects if isinstance(obj, BackpackObject) else {}
        rendered_obj = request.view(obj_to_render, **kwargs)
        for addition in list_of_additions:
            addition(request, obj_to_render, rendered_obj, additional_objects)
        return rendered_obj
    return enrichRenderer


def _enrich_bom_item_target_renderer(request):
    return _generic_enrich_renderer(request,
                                    [_add_has_children,
                                     _add_current_status,
                                     _add_item,
                                     _add_icon,
                                     _add_selection_predicates,
                                     _add_bom_item_description])


def _enrich_status_renderer(request):
    return _generic_enrich_renderer(request,
                                    [_add_current_status])


def _enrich_status_and_operations_renderer(request):
    return _generic_enrich_renderer(request,
                                    [_add_current_status, _make_operations_dict])


def _enrich_variant_operations_renderer(request):
    return _generic_enrich_renderer(request, [_make_variant_operations_dict])


class PresentRelshipResolver(object):
    def __init__(self, content, target_classname, is_unary=False):
        self.content = content
        self.is_unary = is_unary
        self.target_classname = target_classname

    def resolve(self):
        return self.content

    def get_additional_data(self):
        """
        If your resolver wants additional data to be sent as a request
        result you can overwrite this function and return a dictionary
        with the data.
        """
        return {}


class BackpackObject(object):
    def __init__(self, obj, additional_objects):
        self.obj = obj
        self.additional_objects = additional_objects


@RelshipApp.json(model=RelshipTarget, name="complete-bom-item-target")
def _reference_complete_bom_item_target(model, request):
    product_object_id = request.GET.get("product_object_id")
    variant_id = request.GET.get("variant_id")
    submodel = model
    if isinstance(model.parent_object, Assembly) and model.relship_name == 'Components':
        # get bom once and filter for variant bom here to prevent not needed sub renderings
        all_boms = model.parent_object.Components.Query(condition="1=1", access="read")
        if product_object_id is not None and variant_id is not None:
            variant = Variant.ByKeys(
                product_object_id=product_object_id,
                id=safe_int(variant_id)
            )
            if variant is None:
                raise HTTPBadRequest()
            vfilter = VariantBOMFilter(product_object_id, variant_id)
            filtered_boms = [
                bom for bom in all_boms if vfilter.eval(
                    baugruppe=bom.baugruppe,
                    b_index=bom.b_index,
                    teilenummer=bom.teilenummer,
                    t_index=bom.t_index,
                    variante=bom.variante,
                    position=safe_int(bom.position)
                )
            ]

            items = []
            items_with_children = []
            selectionPredicates = []
            # Optimization: fetch items in chunks - to ensure also small enough conditions
            from cs.vp.bom import _chunked
            for boms in _chunked(filtered_boms, 300):
                items_condition = " OR ".join(["(teilenummer='{teilenummer}' AND "
                                       "t_index='{t_index}')"
                                       .format(teilenummer=_fp(bom_item.teilenummer),
                                               t_index=_fp(bom_item.t_index))
                                       for bom_item in boms])
                items += Item.Query(items_condition, access="read")
                items_with_children += [
                    x.get('cdb_object_id')
                    for x in sqlapi.RecordSet2(
                        'teile_stamm',
                        condition="""
                            ({items_condition}) AND
                            EXISTS(
                                SELECT 42
                                FROM einzelteile e
                                WHERE e.baugruppe=teile_stamm.teilenummer
                                AND e.b_index=teile_stamm.t_index
                            )
                        """.format(items_condition=items_condition),
                        columns=['cdb_object_id']
                    )
                ]

                selectionPredicates += BOM_Predicate.SQL(
                    """
                        SELECT p.*
                        FROM einzelteile e INNER JOIN cdbvp_bom_predicate p
                        ON e.baugruppe=p.baugruppe
                            AND e.b_index=p.b_index
                            AND e.teilenummer=p.teilenummer
                            AND e.variante=p.variante
                            AND e.position=p.position
                        WHERE {bom_condition}
                            AND product_object_id='{product_object_id}'
                    """.format(
                        bom_condition=items_condition
                        .replace("teilenummer", "e.teilenummer")
                        .replace("t_index", "e.t_index"),
                        product_object_id=product_object_id
                    )
                )

            items_with_children = set(items_with_children)
            itemsdict = {}
            for item in items:
                itemsdict["%s;%s" % (item.teilenummer, item.t_index)] = item
            predicatedict = {}
            get_mapping_key = lambda x: "{baugruppe};{b_index};{teilenummer};{variante};{position}".format(baugruppe=x.baugruppe,
                                                                                          b_index=x.b_index,
                                                                                          teilenummer=x.teilenummer,
                                                                                          variante=x.variante,
                                                                                          position=x.position)
            for p in selectionPredicates:
                pkey = get_mapping_key(p)
                if pkey in predicatedict:
                    predicatedict[pkey].append(p)
                else:
                    predicatedict[pkey] = [p]
            content = [BackpackObject(bom, dict(
                                                item=itemsdict["%s;%s" % (bom.teilenummer, bom.t_index)],
                                                has_children=itemsdict["%s;%s" % (bom.teilenummer, bom.t_index)].cdb_object_id in items_with_children,
                                                predicates=predicatedict[get_mapping_key(bom)] if get_mapping_key(bom) in predicatedict else []
                                                )
                                      ) for bom in filtered_boms]
            submodel = RelshipTarget(model.parent_object, model.relship_name, PresentRelshipResolver(content=content,
                                                                                                     target_classname=model.target_classname,
                                                                                                     is_unary=model.is_unary))
    result = _render_relship(submodel, request, _enrich_bom_item_target_renderer(request))
    return result


@RelshipApp.json(model=RelshipTarget, name="complete-target-with-status")
def _reference_target_complete_with_status(model, request):
    return _render_relship(model, request, _enrich_status_renderer(request))


@GenericApp.json(model=Object, permission=ReadPermission, name="with-status")
def _default_view_with_status(model, request):
    return _enrich_status_renderer(request)(model)


@GenericApp.json(model=Object, permission=ReadPermission, name="with-status-and-operations")
def _default_view_with_status_and_operations(model, request):
    return _enrich_status_and_operations_renderer(request)(model)


@RelshipApp.json(model=RelshipTarget, name="complete-target-with-status-and-operations")
def _reference_target_complete_with_status_and_operations(model, request):
    return _render_relship(model, request, _enrich_status_and_operations_renderer(request))


@GenericApp.json(model=Object, permission=ReadPermission, name="with-variant-operations")
def _default_view_with_variant_operations(model, request):
    return _enrich_variant_operations_renderer(request)(model)
