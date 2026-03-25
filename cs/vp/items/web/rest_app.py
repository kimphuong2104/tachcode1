# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Special REST application for items. Implements object versioning and
classifying related logic.
"""

__revision__ = "$Id$"


from webob.exc import HTTPBadRequest, HTTPNotFound

import urllib.parse

from cdbwrapc import CDBClassDef
from cdb.objects import operations
from cdb.objects import Rule
from cdb.constants import kOperationIndex, kOperationModify, kArgumentUsesRestAPI
from cdb.platform.mom import SimpleArgument
from cs.platform.web.license import check_license
from cs.platform.web.permissions import CDB_Permission, ReadPermission
from cs.platform.web.rest import CollectionApp
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.generic import model as generic_model
from cs.platform.web.rest.relship import main as relship
from cs.platform.web.rest.generic.convert import load
from cs.platform.web.rest.support import rest_key
from cs.platform.web.root import get_v1
from cs.platform.web.rest.support import decode_key_component

from cs.vp.items import Item
from cs.vp import items
from cs.vp import bom
from cs.vp.variants.filter import VariantBOMFilter
from cs.vp import variants
from cs.vp.variants.apps.rest_additions import _generic_enrich_renderer, _add_current_status, _add_has_children


class ItemApp(GenericApp):
    def __init__(self):
        super(ItemApp, self).__init__("part")

    def get_object(self, keys):
        key_values = [decode_key_component(k) for k in keys.split('@')]
        try:
            return Item.ItemFromRestKey(key_values)
        except ValueError:
            raise HTTPBadRequest()


@CollectionApp.mount(app=ItemApp, path="part")
def _mount_app():
    return ItemApp()


@GenericApp.defer_links(model=Item)
def _defer_item(app, _item):
    return app.child(ItemApp())


@ItemApp.json(model=Item, permission=ReadPermission)
@check_license
def part_default(item, request):
    result = request.view(item, name="base_data")
    result["relship:versions"] = [request.link(version)
                                  for version in item.Versions]
    return result


@ItemApp.json(model=generic_model.ObjectCollection, request_method='POST', name="instance")
def instantiate_part(self, request):
    for values in request.json:
        product_object_id = values.get("product_object_id")
        instance_object_id = values.get("instance_oid")
        variant_id = values.get("variant_id")
        teilenummer = values.get("teilenummer")
        t_index = values.get("t_index", "")

        variant = variants.Variant.ByKeys(
            product_object_id=product_object_id, id=variant_id)
        item = items.Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
        replace_instance = None
        if instance_object_id is not None:
            replace_instance = Item.ByKeys(cdb_object_id=instance_object_id)

        if not variant or not item:
            raise HTTPBadRequest()

        class_app = get_v1(request).child("class")
        type_urls = {
            clazz: request.link(
                CDBClassDef(clazz),
                app=class_app
            )
            for clazz in ["part", "bom_item"]
        }

        def resolve(obj):
            if obj["@type"] == type_urls["part"]:
                return items.Item.ByKeys(
                    teilenummer=obj["teilenummer"],
                    t_index=obj["t_index"]
                )
            elif obj["@type"] == type_urls["bom_item"]:
                return bom.AssemblyComponent.ByKeys(
                    baugruppe=obj["baugruppe"],
                    b_index=obj["b_index"],
                    teilenummer=obj["teilenummer"],
                    t_index=obj["t_index"],
                    position=obj["position"],
                    variante=obj["variante"],
                    auswahlmenge=obj["auswahlmenge"]
                )

        data = [{
            "instance": resolve(el["obj"]) if el["id"] != "NEW" else "NEW",
            "path": list(map(resolve, el["path"][1:]))
        } for el in values.get("data")]
        instance = item.instantiate_bom(variant, data, instance=replace_instance)

    result = request.view(instance)
    result["system:url"] = instance.MakeURL()
    result["system:structure_url"] = instance.MakeURL('CDB_ProductStructure')

    return [result]


class PartVersions(object):
    def __init__(self, cdb_obj):
        self.cdb_obj = cdb_obj
        self.versions = cdb_obj.Versions

    def versionize(self, json_args):
        json_args.update(load(json_args, self.cdb_obj.GetClassDef()))
        args = operations.prefix_args(None, **json_args)
        args.append(SimpleArgument(kArgumentUsesRestAPI, "1"))
        operations.operation(kOperationIndex, self.cdb_obj, args)


@ItemApp.permission_rule(model=PartVersions,
                         permission=CDB_Permission)
def _check_versions_permission(identity, model, permission):
    # For PartVersions models, check declared permissions on the source part
    return permission.check_permission(identity, model.cdb_obj)


@ItemApp.path(path='{keys}/versions', model=PartVersions)
def _get_versions(keys, app):
    obj = app.get_object(keys)
    if obj is None:
        return None
    return PartVersions(obj)


@ItemApp.json(model=PartVersions, permission=ReadPermission)
def _part_versions(obj, request):
    result = [request.view(v) for v in obj.versions if v.CheckAccess("read")]
    # FIXME: add context
    return result


@ItemApp.json(model=PartVersions, request_method='PUT',
              permission=ReadPermission)
# Check read permission on the parent part, the permission to actually index
# the part are checked by the operations
def _part_new_version(obj, request):
    try:
        obj.versionize(request.json)
    except RuntimeError as x:
        raise HTTPBadRequest(detail=str(x))
    return request.view(obj)


# ----- classification related declarations -----

class PartClass(object):

    def __init__(self, cdb_obj):
        self.cdb_obj = cdb_obj

    def sg(self):
        return self.cdb_obj.sachgruppe

    def propvals(self):
        def propval(pv):
            unit = ""
            tp = "string"
            if pv.is_pq():
                tp = "pq"
                v = pv.value[0]
                unit = pv.value[1]
            else:
                v = pv.value
                if isinstance(v, float):
                    tp = "float"
            return {
                'value': v,
                'unit': unit,
                'type': tp
            }
        props = dict()
        if self.sg() is not None:
            for pk, pv in self.cdb_obj.Properties.items():
                props[pk] = propval(pv)
        return props

    def classify(self, json_args):
        operations.operation(kOperationModify, self.cdb_obj,
                             operations.prefix_args(None, **json_args))


@ItemApp.permission_rule(model=PartClass,
                         permission=CDB_Permission)
def _check_class_permission(identity, model, permission):
    # see comment for PartVersions
    return permission.check_permission(identity, model.cdb_obj)


@ItemApp.path(path='{keys}/class', model=PartClass)
def _get_class(keys, app):
    obj = app.get_object(keys)
    if obj is None:
        return None
    return PartClass(obj)


@ItemApp.json(model=PartClass, permission=ReadPermission)
def _part_class(obj, request):
    result = dict()
    result['class'] = obj.sg()
    result['properties'] = obj.propvals()
    return result


@ItemApp.json(model=PartClass, request_method='PUT', permission=ReadPermission)
# regarding ReadPermission see above
def _part_classify(obj, request):
    try:
        obj.classify(request.json)
    except RuntimeError as x:
        raise HTTPBadRequest(detail=str(x))
    return request.view(obj)


class ItemRelshipApp(relship.RelshipApp):
    pass


@ItemRelshipApp.json(model=relship.RelshipTarget, path="BOM", name="filtered")
def filtered_bom(model, request):
    def safe_int(arg):
        try:
            return int(arg)
        except ValueError:
            return None

    result = relship._render_relship(model, request, request.view)

    product_object_id = request.GET.get("product_object_id")
    variant_id = request.GET.get("variant_id")

    if product_object_id is not None and variant_id is not None:
        variant = variants.Variant.ByKeys(
            product_object_id=product_object_id,
            id=safe_int(variant_id)
        )

        if not variant:
            raise HTTPNotFound()

        vfilter = VariantBOMFilter(product_object_id, variant_id)
        result["targets"] = [
            target for target in result["targets"]
            if vfilter.eval(
                baugruppe=target["baugruppe"],
                b_index=target["b_index"],
                teilenummer=target["teilenummer"],
                t_index=target["t_index"],
                variante=target["variante"],
                position=safe_int(target["position"])
            )
        ]

    return result


@ItemRelshipApp.json(model=relship.RelshipTarget, path="Instantiations", name="variant")
def part_variant(model, request):
    product_object_id = request.GET.get("product_object_id")
    variant_id = request.GET.get("variant_id")

    result = relship._render_relship(model, request,
                                     _generic_enrich_renderer(request,
                                                              [_add_current_status,
                                                               _add_has_children]))
    result["@id"] = urllib.parse.unquote(result["@id"].split('?')[0])
    if product_object_id is not None and variant_id is not None:
        item = model.parent_object
        links = variants.Variant2Part.KeywordQuery(
            product_object_id=product_object_id,
            variant_id=variant_id,
            max_bom_teilenummer=item.teilenummer,
            max_bom_t_index=item.t_index
        )
        targets = [(vl.teilenummer, vl.t_index) for vl in links]
        result["targets"] = [
            target for target in result["targets"]
            if (target["teilenummer"], target["t_index"]) in targets
        ]
    return result


@ItemApp.mount(app=ItemRelshipApp, path="{keys}/relship",
               variables=lambda o: dict(keys=rest_key(o.parent_object)))
def _mount_relships(keys, app):
    model = app.get_object(keys)
    return ItemRelshipApp(model)


@ItemApp.defer_links(model=relship.RelshipCollection)
def _defer_relship_collection(app, model):
    return app.child(ItemRelshipApp(model.parent_object))


@ItemApp.defer_links(model=relship.RelshipTarget)
def _defer_relship_target(app, model):
    return app.child(ItemRelshipApp(model.parent_object))
