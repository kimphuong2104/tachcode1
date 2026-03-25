# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Internal app for the threed cockpit
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import json
from webob.exc import (
    HTTPForbidden,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPNoContent
)

import morepath
import urllib

from cdb import fls
from cdb import util
from cdb import i18n
from cdb import sqlapi

from cdb.objects import Object
from cdb.objects import ByID
from cdb.objects import Rule

from cs import documents
from cs.platform.web import JsonAPI
from cs.platform.web import root
from cs.platform.web.uisupport import get_ui_link
from cs.platform.web.rest.app import get_collection_app, CollectionApp

from cs.documents import Document

from cs.vp import items
from cs.vp import cad
from cs.vp import products
from cs.vp import bom
from cs.vp.bom import bomqueries

from cs.threed.hoops import bcf
from cs.threed.hoops import _MODEL_RULE
from cs.threed.hoops import markup
from cs.threed.hoops import markup_elink
from cs.threed.variants import get_variant


CAD_RULE_2D = "mBOM Manager: 2D documents"


@CollectionApp.view(model=markup.View, name="ui_link", internal=True)
def _get_handle_ui_link(model, request):
    return model.get_view_url()


class CockpitInternal(JsonAPI):
    pass


@root.Internal.mount(app=CockpitInternal, path="threed")
def _mount_internal():
    return CockpitInternal()


@CockpitInternal.path(path="{cdb_object_id}", model=Object)
def _structure_path(cdb_object_id):
    return ByID(cdb_object_id)

@CockpitInternal.path(path="find")
class Find(object):
    pass

class ObjURLModel(object):
    def __init__(self):
        pass


@CockpitInternal.path(path="obj_from_cmsg", model=ObjURLModel)
def _obj_from_cmsg_path():
    return ObjURLModel()


@CockpitInternal.json(model=Object, name="rest_object")
def rest_object(model, request):
    collection_app = root.get_v1(request).child("collection")
    return urllib.parse.unquote(request.link(model, app=collection_app))


@CockpitInternal.json(model=Object, name="mapping_file")
def _redirect_to_mapping_file(model, request):
    if isinstance(model, Document):
        mapping_file = model.get_json_mapping_file()
    elif isinstance(model, items.Item):
        doc = model.get_3d_model_document()
        if doc is None:
            raise HTTPNotFound()
        mapping_file = doc.get_json_mapping_file()

    return morepath.redirect(request.link(mapping_file, app=get_collection_app(request)))


def _get_obj_from_cmsg(msg):
    # get an object from a `cdb.cmsg.Cdbcmsg` link.

    # Searches for parameters
    urlparts = msg.split("?")
    if len(urlparts) != 2:
        return None

    paramstr = urlparts[1]
    import cgi
    key_dict = cgi.parse_qs(paramstr, True)

    # Gets relation
    relation = key_dict.keys()[0].split('.')[0]

    # Finds out object class
    from cdb.objects import ClassRegistry
    objcls = ClassRegistry().find(relation)
    if not objcls:
        return None

    querydict = {}
    knames = objcls.KeyNames()

    # Removes relation prefix by attribute names
    # (relation name + ".")
    kidx = len(relation) + 1
    for k, v in key_dict.items():
        # Queries objects only with keys
        attr = k[kidx:]
        if attr in knames:
            querydict[attr] = v
    if not querydict:
        return None

    objs = objcls.KeywordQuery(**querydict)

    # Distinct check
    if len(objs) != 1:
        return None

    obj = objs[0]
    return obj


@CockpitInternal.json(model=ObjURLModel, request_method="POST")
def get_obj_id_from_cmsg(model, request):
    data = request.json
    cmsg = data["url"]
    obj = _get_obj_from_cmsg(cmsg)
    if obj:
        oid = obj.GetObjectID()

        result = {
            "cdb_object_id": oid,
            "icon": obj.GetObjectIcon(),
            "description": obj.GetDescription(),
        }

        return result


@CockpitInternal.json(model=Object, name="save_view", request_method="POST")
def save_view(object, request):
    fls.allocate_license("3DSC_005")  # 3DC: View
    data = request.json
    base64snapshot = data.pop('base64snapshot', None)
    unique_id = data.get('uniqueId')
    view = markup.View.ByKeys(cdb_object_id=unique_id)

    if not util.check_access(
            markup.View.__maps_to__, {'cdb_object_id': unique_id}, 'save'):
        raise HTTPForbidden('Not allowed to save views')

    if view is not None:
        markup_elink.update_view(data, view)
    else:
        markup_elink.create_view(data)

    view = markup.View.ByKeys(unique_id)
    if view is None:
        raise HTTPInternalServerError("view was not created")
    view.save_snapshot(base64snapshot)

    return view.get_elink_data(request)


@CockpitInternal.json(model=Object, name="delete_view", request_method="POST")
def delete_view(object, request):
    fls.allocate_license("3DSC_005")  # 3DC: View
    data = request.json
    view = markup.View.ByKeys(cdb_object_id=data.get('uniqueId'))

    if view is not None:
        view.delete_all()


@CockpitInternal.json(model=Object, name="save_bcf_topic", request_method="POST")
def save_bcf_topic(obj, request):
    fls.allocate_license("3DSC_020")  # 3DC: Write BCF
    bcf.save_topic(obj, request)

@CockpitInternal.json(model=Object, name="add_bcf_viewpoint", request_method="POST")
def add_bcf_viewpoint(obj, request):
    fls.allocate_license("3DSC_020")  # 3DC: Write BCF
    bcf.add_viewpoint(obj, request)

@CockpitInternal.json(model=Object, name="add_bcf_comment", request_method="POST")
def add_bcf_comment(obj, request):
    fls.allocate_license("3DSC_020")  # 3DC: Write BCF
    bcf.add_comment(obj, request)


def get_bom_node_description(comp):
    from cs.vp.bom.diffutil import pages
    bom_node_tag = pages.get_bomnode_tag()
    description = bom_node_tag % pages._BomItemAttributeAccessor(
        comp, comp.Item)
    return description


def _get_bom_icon(category, position_type, has_condition):
    from cdb.objects import IconCache
    kwargs = {"t_kategorie": category,
              "cdbvp_positionstyp": position_type,
              "cdbvp_has_condition": has_condition}
    return IconCache.getIcon("cdbvp_part", **kwargs)


def select_flat_drawings(item, level=None):
    drawings_rule = Rule.ByKeys(name=CAD_RULE_2D)
    if drawings_rule:
        keys = ", ".join([
            "{table}" + fd.name
            for fd in bom.AssemblyComponent.GetTableKeys()
        ])

        level_condition = \
            "flat_bom.bom_level <= %s" % level if level is not None else "1=1"
        QUERY = """
            WITH flat_bom ({keys}, bom_level)
            AS (
                SELECT {einzelteile_keys}, 1 bom_level
                FROM einzelteile
                WHERE {root_condition}
                UNION ALL
                SELECT {einzelteile_keys}, flat_bom.bom_level + 1
                FROM einzelteile
                INNER JOIN flat_bom
                ON flat_bom.teilenummer=einzelteile.baugruppe AND
                    flat_bom.t_index=einzelteile.b_index
            )
            SELECT *
            FROM zeichnung WHERE EXISTS (
                SELECT 42
                FROM flat_bom
                WHERE (
                    zeichnung.teilenummer = flat_bom.teilenummer AND
                    zeichnung.t_index = flat_bom.t_index
                    AND {level_condition}
                )
            ) OR (
                zeichnung.teilenummer='{teilenummer}' AND
                zeichnung.t_index='{t_index}'
            )
        """.format(
            root_condition=bomqueries.make_root_condition(item),
            keys=keys.format(table=""),
            einzelteile_keys=keys.format(table="einzelteile."),
            level_condition=level_condition,
            teilenummer=item.teilenummer,
            t_index=item.t_index
        )

        docs = documents.Document.SQL(QUERY)
        drawings = [doc for doc in docs if drawings_rule.match(doc)]
        return drawings


@CockpitInternal.json(model=items.Item, name="drawings")
def part_drawings(item, request):
    collection_app = root.get_v1(request).child("collection")
    drawings_rule = Rule.ByKeys(name=CAD_RULE_2D)

    try:
        depth = int(request.GET.get("depth", ""))
    except ValueError:
        depth = None

    def view(doc):
        result = {
            '@id': urllib.parse.unquote(request.link(doc, app=collection_app)),
            'system:description': doc.GetDescription(),
            'system:icon_link': doc.GetObjectIcon(),
            'cdb_object_id': doc.cdb_object_id
        }
        ui_link = get_ui_link(request, doc)
        if ui_link:
            result['system:ui_link'] = ui_link
        return result

    if drawings_rule:
        return {
            "objects": [
                view(doc)
                for doc in select_flat_drawings(item, depth)
            ],
            "depth": depth
        }


@CockpitInternal.json(model=items.Item, name="structure")
def bom_node_structure(item, request):
    collection_app = root.get_v1(request).child("collection")
    result = []

    # FIXME: do everything with only one sql query
    for comp in item.Components:
        if comp.Item is not None:
            view = request.view(comp.Item, app=collection_app)
            view.update({
                "description": get_bom_node_description(comp),
                "has_children": bool(comp.Item.Components),
                "system:icon_link": _get_bom_icon(
                    comp.Item.t_kategorie,
                    comp.cdbvp_positionstyp,
                    comp.cdbvp_has_condition
                )
            })
            result.append(view)
    return result


def small_view(obj, request):
    return {
        '@id': urllib.parse.unquote(request.link(obj, app=get_collection_app(request))),
        'system:description': obj.GetDescription(),
        'system:icon_link': obj.GetObjectIcon(),
        'cdb_object_id': obj.cdb_object_id
    }


@CockpitInternal.json(model=documents.Document, name="structure_heads")
def doc_structure_heads(doc, request):
    return {
        "@id": urllib.parse.unquote(request.link(doc)),
        "objects": [small_view(doc, request)]
    }


@CockpitInternal.json(model=items.Item, name="structure_heads")
def part_structure_heads(item, request):
    result = [small_view(item, request)]

    docs = cad.Model.KeywordQuery(
        teilenummer=item.teilenummer, t_index=item.t_index)
    for doc in docs:
        result.append(small_view(doc, request))

    return {
        "@id": urllib.parse.unquote(request.link(item)),
        "objects": result
    }


@CockpitInternal.json(model=products.Product, name="structure_heads")
def product_structure_heads(product, request):
    result = []

    for item in product.MaxBoms:
        result.extend(small_view(item, request))

    return {
        "@id": urllib.parse.unquote(request.link(product)),
        "objects": result
    }


@CockpitInternal.json(model=Object, name="variant")
def product_variant(model, request):
    id = request.GET["id"]
    lang = request.GET.get("lang", i18n.default())
    variant = get_variant(model.cdb_object_id, id)
    result = variant.get_variability_properties_info_str(lang=lang)

    return result


@CockpitInternal.json(model=Object, name="measurement", request_method="POST")
def create_measurement(obj, request):
    # Allocate license corresponding to feature "3DSC: Measurements"
    fls.allocate_license("3DSC_004")

    data = request.json
    kwargs = {
        'context_object_id': obj.cdb_object_id,
        'name': data.get('name')
    }
    kwargs.update(markup.Measurement.MakeChangeControlAttributes())

    if util.check_access('threed_hoops_measurement', kwargs, 'create'):
        measurement = markup.Measurement.Create(**kwargs)
        measurement.SetText('threed_hoops_measurement_txt', json.dumps(data.get('measurements')))
        return measurement.get_elink_data()
    raise HTTPForbidden


@CockpitInternal.json(model=Object, name="measurement", request_method="DELETE")
def delete_measurement(measurement, request):
    # Allocate license corresponding to feature "3DSC: Measurements"
    fls.allocate_license("3DSC_004")

    if measurement is not None and measurement.CheckAccess('delete'):
        measurement.DeleteText('threed_hoops_measurement_txt')
        measurement.Delete()
        raise HTTPNoContent
    raise HTTPNotFound


class CockpitAuthInternal(JsonAPI):
    pass


class AuthenticationModel(object):
    """Authorization Server for generating
    a JWT to be used as a bearer token for accessing Broker Service
    interfaces."""

    def __init__(self):
        super(AuthenticationModel, self).__init__()

    def build_response(self, issuer_url, req_scope):
        from cs.threed.services.auth import WebKey
        scope = "threed/broker/%s" % (req_scope,)
        return WebKey.gen_bearer_token(issuer_url, scope)


@CockpitInternal.path(path="token", model=AuthenticationModel)
def _get_auth_model():
    return AuthenticationModel()


def load_json(request):
    return request.json_body


@CockpitInternal.json(model=AuthenticationModel, request_method="POST",
                      load=load_json)
def view_auth_response(model, request, req_json):
    if not req_json or not req_json.get("response_type") == "token":
        raise HTTPForbidden()
    res = model.build_response(request.link(model), req_json.get("scope"))
    return res


@CockpitInternal.json(model=Find, name="get_top_most_model", request_method="POST")
def _get_top_model_with_geometry(product, request):
    data = request.json
    path = data.get("path", [])
    rule = Rule.ByKeys(_MODEL_RULE)
    last_valid_index = -1
    last_valid_obj_id = ""

    if path:
        item_pkeys = [
            (x["teilenummer"], x["t_index"]) for x in path
        ]
        items_condition = " OR ".join(["(teilenummer='%s' AND t_index='%s')" % (sqlapi.quote(key[0]), sqlapi.quote(key[1]))
            for key in item_pkeys])

        item_list = items.Item.Query(items_condition)
        sorted_item_list = []

        for p in path:
            for comp in item_list:
                if comp.teilenummer == p["teilenummer"]:
                    if comp.t_index == p["t_index"]:
                        sorted_item_list.append(comp)

        for index, comp in reversed(list(enumerate(sorted_item_list))):
            if rule.match(comp):
                last_valid_index = index
                last_valid_obj_id = comp.cdb_object_id
            else:
                break
    return last_valid_index, last_valid_obj_id
