# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Module utils

This is the documentation for the utils module.
"""

import collections
import datetime
import json
import urllib.parse

from webob.exc import HTTPBadRequest


from cdb import misc
from cdb import sqlapi
import collections
from cs.platform.web import PlatformApp
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.relship.main import make_relship_target
from cs.platform.web.root import get_v1
from cs.platform.web.root.main import Internal

from cs.vp.bom.usages import get_usages
from cs.vp.variants import Variant
from cs.vp.variants.items import Item, AssemblyComponent


def _fp(value):  # Format a Parameter for an sql query
    if value in [None, sqlapi.NULL]:
        return ''
    return sqlapi.quote(value)


def log(msg):
    misc.log(9, msg)


def bom_tree_walk(cb, node, parents, mapping=None, processedItemIds=None, level=0):
    log('bom_tree_walk on %s ' % ("  " * level + node.GetDescription()))
    children = []
    processedItemIds = processedItemIds if processedItemIds is not None else []
    processedNode = node
    if isinstance(processedNode, Item):
        processedItemIds = processedItemIds + [processedNode.cdb_object_id]
        if mapping is not None and ",".join(processedItemIds) in mapping:
            processedNode = Item.ByKeys(cdb_object_id=mapping.get(",".join(processedItemIds)))
        children = lambda: processedNode.Components
    elif isinstance(processedNode, AssemblyComponent):
        children = lambda: [processedNode.Item]
    else:
        raise ValueError()
    # stop if cb indicates to break the walk
    stop_walk, cb_children = cb(processedNode, parents)
    if not stop_walk:
        # evaluate children only if needed
        children = cb_children() if cb_children is not None else children()
        parents = parents + [processedNode]
        for child in children:
            bom_tree_walk(cb, child, parents, mapping, processedItemIds, level + 1)


# ---------- Application ----------
APP_ID = "cs.vp.variants.apps.instance_wizard"


def safe_int(arg):
    try:
        return int(arg)
    except ValueError:
        return None


class UtilsBaseApp(PlatformApp):
    pass


@Internal.mount(app=UtilsBaseApp, path=APP_ID)
def _mount():
    return UtilsBaseApp()


class BOMTextSearchModel(object):
    def __init__(self, *args, **kwargs):
        pass


class BOMPredicateSearchModel(object):
    def __init__(self, *args, **kwargs):
        self.product_object_id = kwargs.get('product_object_id', '')
        self.variant_id = kwargs.get('variant_id', '')
        self.teilenummer = kwargs.get('teilenummer', '')
        self.t_index = kwargs.get('t_index', '')


@UtilsBaseApp.path(model=BOMTextSearchModel, path='utils/bom_text_search')
def get_bom_text_search_model():
    return BOMTextSearchModel()


@UtilsBaseApp.path(model=BOMPredicateSearchModel, path='utils/bom_predicate_search')
def get_bom_predicate_search_model():
    return BOMPredicateSearchModel()


def _get_bom_predicates_usages(product_object_id, maxbom):
    stmt = """
        SELECT * from teile_stamm ts
        WHERE EXISTS (
          SELECT 42
          FROM einzelteile e INNER JOIN cdbvp_bom_predicate p
          ON e.baugruppe=p.baugruppe
            AND e.b_index=p.b_index
            AND e.teilenummer=p.teilenummer
            AND e.variante=p.variante
            AND e.position=p.position
          WHERE e.teilenummer=ts.teilenummer AND e.t_index=ts.t_index
            AND product_object_id='%s'
        )
    """ % product_object_id
    _items = set(Item.SQL(stmt))
    items_condition = " OR ".join(["(teilenummer='{teilenummer}' AND "
                                   "t_index='{t_index}')"
                                   .format(teilenummer=_fp(item.teilenummer),
                                           t_index=_fp(item.t_index))
                                   for item in _items])
    usages = set(get_usages(_items, maxbom))
    usageItems = Item.Query(Item.cdb_object_id.one_of(*usages))
    usages_condition = " OR ".join(["(teilenummer='{teilenummer}' AND "
                                   "t_index='{t_index}')".format(teilenummer=_fp(item.teilenummer),
                                                                 t_index=_fp(item.t_index))
                                    for item in usageItems])

    return items_condition, usages_condition, set(usages)


def _generateExpandedRelships(request, part_app, expanded_relships):
    for k in list(expanded_relships):
        bom_rs = make_relship_target(expanded_relships[k], "Components")
        expanded_relships[k] = request.view(bom_rs, app=part_app, name='complete-bom-item-target')


@UtilsBaseApp.json(model=BOMPredicateSearchModel)
def bom_predicate_search(model, request):
    product_object_id = request.GET.get('product_object_id')
    variant_id = request.GET.get('variant_id')
    variant = None
    if product_object_id is not None and variant_id is not None:
        variant = Variant.ByKeys(product_object_id=product_object_id,
                                 id=safe_int(variant_id))
    if variant is None:
        raise HTTPBadRequest()

    teilenummer = request.GET.get('teilenummer', model.teilenummer)
    t_index = request.GET.get('t_index', model.t_index)
    maxbom = Item.ByKeys(teilenummer=teilenummer, t_index=t_index)

    if maxbom is not None:
        start = datetime.datetime.utcnow()
        log('bom_predicate_search started on poid %s, %s, %s, %s' % (
            product_object_id, variant_id, teilenummer, t_index))

        collection_app = get_v1(request).child('collection')
        part_app = collection_app.child(GenericApp, rest_name="part")

        matched_items = set()
        search_result_item_condition, search_result_usages_condition, search_result_usages = \
            _get_bom_predicates_usages(product_object_id, maxbom)

        sql_preparation_time = datetime.datetime.utcnow()
        log('bom_predicate_search sql preparation done %s;;;%s;;;%s within %f' % (
            search_result_item_condition, search_result_usages_condition, search_result_usages,
            (sql_preparation_time - start).total_seconds()
        ))

        expanded_relships = collections.OrderedDict()

        def assembly_predicate_matcher(node, parents):
            if isinstance(node, Item) and node.cdb_object_id in search_result_usages:
                # only follow boms for items which are in usages or contain predicates
                return False, lambda: node.Components.Query("""
                    ( {cond1} ) OR ( {cond2} )
                """.format(cond1=search_result_usages_condition, cond2=search_result_item_condition))
            elif isinstance(node, Item) and node.cdb_object_id not in search_result_usages:
                return True, None
            elif isinstance(node, AssemblyComponent) and len(node.VPMPredicates) > 0:
                url = ""
                if len(parents) > 0:
                    assembly = parents[-1]
                    if assembly.cdb_object_id not in matched_items:
                        log('bom_predicate_search found %s' % assembly.GetDescription())
                    matched_items.add(assembly.cdb_object_id)
                    for parent in parents[0:-1]:
                        if url:
                            url += ";%s" % (request.link(parent, app=collection_app))
                        else:
                            url += request.link(parent, app=collection_app)
                        unescaped_url = urllib.parse.unquote(url)
                        if isinstance(parent, Item) and unescaped_url not in expanded_relships:
                            expanded_relships[unescaped_url] = parent
                return False, None
            return False, None
        bom_tree_walk(assembly_predicate_matcher, maxbom, [])

        search_time = datetime.datetime.utcnow()
        log('bom_predicate_search tree search done within %f' % ((search_time - sql_preparation_time).total_seconds()))
        _generateExpandedRelships(request, part_app, expanded_relships)
        log('bom_predicate_search relship generation done within %f' % (datetime.datetime.utcnow() - search_time).total_seconds())
        log('bom_predicate_search total time %f' % (datetime.datetime.utcnow() - start).total_seconds())
        return {"matched": list(matched_items.difference([maxbom.cdb_object_id])),
                "expanded": dict(relships=list(expanded_relships.values()),
                                  ids=list(expanded_relships))}
    else:
        return {"matched": [],
                "expanded": dict(relships=[],
                                  ids=[])}


@UtilsBaseApp.json(model=BOMTextSearchModel)
def bom_text_search(_, request):
    teilenummer = request.GET.get('teilenummer')
    t_index = request.GET.get('t_index', '')
    search_text = request.GET.get('text')
    part_mapping = json.loads(request.GET.get('mapping', '{}'))
    if search_text:
        maxbom = Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
        collection_app = get_v1(request).child('collection')
        part_app = collection_app.child(GenericApp, rest_name="part")
        matched_items = []
        expanded_relships = collections.OrderedDict()

        # return true if search position reached
        def item_description_matcher(node, parents):
            if isinstance(node, Item) and search_text in node.GetDescription():
                matched_items.append(node.cdb_object_id)
                url = ""
                for parent in parents:
                    if url:
                        url += ";%s" % (request.link(parent, app=collection_app))
                    else:
                        url += request.link(parent, app=collection_app)
                    if isinstance(parent, Item):
                        unescaped_url = urllib.parse.unquote(url)
                        bom_rs = make_relship_target(parent, "Components")
                        if unescaped_url not in expanded_relships:
                            expanded_relships[unescaped_url] = request.view(
                                bom_rs,
                                app=part_app,
                                name='complete-bom-item-target'
                            )
            return False, None
        if maxbom is not None:
            bom_tree_walk(item_description_matcher, maxbom, [], part_mapping)
        return {"matched": matched_items,
                "expanded": dict(relships=list(expanded_relships.values()),
                                  ids=list(expanded_relships))}
    else:
        return {"matched": [],
                "expanded": dict(relships=[],
                                  ids=[])}
