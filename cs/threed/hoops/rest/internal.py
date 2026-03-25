# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


from operator import itemgetter
from itertools import groupby

from webob.exc import HTTPNotFound, HTTPBadRequest

from cs.platform.web import root
from cs.platform.web import JsonAPI
from cs.platform.web.rest.app import get_collection_app
from cs.platform.web.rest.support import values_from_rest_key, rest_key

from cs.documents import Document

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent
from cs.vp.bom import bomqueries

from cs.threed.hoops.mapping import DocumentFileMapper, PartDocumentMapper
from cs.threed.hoops.utils import get_occurrences_for_bom_item_ids

from cdb import sqlapi
from cdbwrapc import SQL_INTEGER, SQL_FLOAT

class HoopsInternal(JsonAPI):
    pass


@root.Internal.mount(app=HoopsInternal, path="cs.threed.hoops")
def _mount_internal():
    return HoopsInternal()


@HoopsInternal.path(path="mapping/document/{cdb_object_id}", model=DocumentFileMapper)
def _get__document_mapping_model(cdb_object_id):
    doc = Document.ByKeys(cdb_object_id=cdb_object_id)
    if not doc:
        raise HTTPNotFound

    return DocumentFileMapper(doc)


@HoopsInternal.path(path="mapping/bom_item/{cdb_object_id}", model=PartDocumentMapper)
def _get_item_mapping_model(cdb_object_id):
    item = Item.ByKeys(cdb_object_id=cdb_object_id)
    if not item:
        raise HTTPNotFound

    return PartDocumentMapper(item)


def _get_obj_paths_for_rest_url_paths(cls, url_paths):
    flat_urls = set([url for path in url_paths for url in path])
    table_pks = [{"name": fd.name, "type": fd.type} for fd in cls.GetTablePKeys()]

    split_values = []
    key_urls = {}
    for url in flat_urls:
        rk = url.replace("%40", "@").split("/")[-1]
        split_values.append(values_from_rest_key(rk))
        key_urls[rk] = url

    def _quote(pk_type, val):
        if pk_type not in [SQL_INTEGER, SQL_FLOAT]:
            return "'%s'" % val
        return val

    def _make_sub_condition(table_pks, values):
        return " AND ".join(["%s=%s" % (pk["name"], _quote(pk["type"], values[idx])) for idx, pk in enumerate(table_pks)])

    condition = " OR ".join(["%s" % _make_sub_condition(table_pks, values) for values in split_values])

    result = sqlapi.RecordSet2(
            table=cls.GetTableName(),
            condition=condition
        )
    objs = cls.FromRecords(result)

    objs_for_rest_urls = {key_urls[rest_key(o)]: o for o in objs}

    return [[objs_for_rest_urls[url] for url in path] for path in url_paths]


def _get_transformations_by_bom_item_id(ids):
    all_occurrences = get_occurrences_for_bom_item_ids(ids)
    all_occurrences.sort(key=itemgetter('bompos_object_id'))
    trafos_by_bompos_id = {}

    for bom_item_id, occs in groupby(all_occurrences, key=itemgetter('bompos_object_id')):
        trafos_by_bompos_id[bom_item_id] = [o.relative_transformation for o in occs]

    return trafos_by_bompos_id


@HoopsInternal.json(model=DocumentFileMapper, name="for_document_paths", request_method="POST")
def _return_documents_mapping(mapper, request):
    if "document_url_paths" not in request.json:
        raise HTTPBadRequest
    document_url_paths = request.json["document_url_paths"]
    document_paths = _get_obj_paths_for_rest_url_paths(Document, document_url_paths)

    for idx, doc_path in enumerate(document_paths):
        if len(doc_path) != len(document_url_paths[idx]):
            raise HTTPBadRequest

    filename_paths = mapper.get_filename_paths_for_document_paths(document_paths)

    return [{"path": fpath, "transforms": []} for fpath in filename_paths]


@HoopsInternal.json(model=DocumentFileMapper, name="for_filenames", request_method="POST")
def _return_document_filenames_mapping(mapper, request):
    if "filenames" not in request.json:
        raise HTTPBadRequest
    filenames = request.json["filenames"]
    docs = mapper.get_document_path_for_filenames(filenames)
    return [request.view(d, app=get_collection_app(request)) for d in docs]


@HoopsInternal.json(model=PartDocumentMapper, name="for_bom_item_oid_paths", request_method="POST")
def _return_bom_item_oid_paths_mapping(mapper, request):
    if "bom_item_oid_paths" not in request.json:
        raise HTTPBadRequest

    bom_item_oid_paths = request.json["bom_item_oid_paths"]
    all_bom_item_oids = list(set([oid for path in bom_item_oid_paths for oid in path]))

    # omit bom enhancement to get the filename mapping 'as saved'
    bom_item_recs = bomqueries.bom_item_records(*all_bom_item_oids)

    objs_by_oid = {o.cdb_object_id: o for o in AssemblyComponent.FromRecords(bom_item_recs)}
    bom_item_paths = [[objs_by_oid[oid] for oid in path] for path in bom_item_oid_paths]

    filename_paths = mapper.get_filename_paths_for_bom_item_paths(bom_item_paths)
    transformations_by_bom_item_id = _get_transformations_by_bom_item_id(all_bom_item_oids)

    result = []
    for idx, path in enumerate(bom_item_paths):
        filename_path = filename_paths[idx]
        transforms = [transformations_by_bom_item_id.get(b.cdb_object_id, []) for b in path]
        result.append({"path": filename_path, "transforms": transforms})

    return result


@HoopsInternal.json(model=DocumentFileMapper, name="get_mapping_file_link", request_method="GET")
def _return_mapping_file_link(mapper, request):
    collection_app = get_collection_app(request)
    return request.link(mapper.context_document.get_json_mapping_file(), app=collection_app)


@HoopsInternal.json(model=PartDocumentMapper, name="for_filenames", request_method="POST")
def _return_bom_item_filenames_mapping(mapper, request):
    if "filenames" not in request.json:
        raise HTTPBadRequest
    filenames = request.json["filenames"]
    transformation_matrix = request.json["tMatrix"] if "tMatrix" in request.json.keys() else None
    bom_items = mapper.get_bom_item_path_for_filenames(filenames, transformation_matrix)

    return [request.view(b, app=get_collection_app(request)) for b in bom_items]
