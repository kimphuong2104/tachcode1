#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Special REST application for documents. Implements object versioning related
logic.
"""


from webob.exc import HTTPBadRequest

from cdb import objects
from cdb.constants import kArgumentUsesRestAPI, kOperationIndex
from cdb.objects import operations
from cdb.platform.mom import SimpleArgument
from cs.documents import Document
from cs.platform.web.license import check_license
from cs.platform.web.permissions import CDB_Permission, ReadPermission
from cs.platform.web.rest import CollectionApp
from cs.platform.web.rest.generic.convert import load
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.generic.model import ObjectCollection
from cs.platform.web.rest.support import decode_key_component


class DocumentApp(GenericApp):
    def __init__(self):
        super(DocumentApp, self).__init__("document")

    def get_object(self, keys):  # pylint: disable=no-self-use
        key_values = [decode_key_component(k) for k in keys.split("@")]
        try:
            return Document.DocumentFromRestKey(key_values)
        except ValueError:
            raise HTTPBadRequest()


@CollectionApp.mount(app=DocumentApp, path="document")
def _mount_app():
    return DocumentApp()


@GenericApp.defer_links(model=Document)
def _defer_document(app, _doc):
    return app.child(DocumentApp())


class DocumentCollection(ObjectCollection):
    """
    A collection of document objects. Derived from `ObjectCollection` to
    provide a mechanism that reduces the result to one single version for
    each document number found.
    """

    def __init__(self, extra_parameters, rule, one_version_method, withFiles):
        """
        Initialization of a document collection. All parameter except
        `one_version_method` are inherited from
        `cs.platform.web.rest.generic.modelObjectCollection`.
        """
        super(DocumentCollection, self).__init__(
            "document", extra_parameters, rule, withFiles
        )
        self.one_version_method = one_version_method

    def query(self):
        """
        A query on a DocumentCollection filters the list of results, so that
        only a single version of each document is returned. The version to
        be returned is selected by calling the GetSpecificVersion() method.
        If `self.one_version_method` is empty all versions found are
        returned.
        """
        query_result = super(DocumentCollection, self).query()
        if not self.one_version_method:
            return query_result

        # We filter the queried objects, but have to make sure that the kernel's
        # result_complete is kept intact, if it is present. See the ObjectCollection
        # view implementation.
        if isinstance(query_result, objects.ObjectCollection):
            all_docs = query_result
            result_complete = not all_docs.IsRestricted()
        elif isinstance(query_result, tuple):
            all_docs, result_complete = query_result
        else:
            all_docs = query_result
            result_complete = True

        # The all_docs collection contains all possible candidates, already
        # filtered by the search condition and access rights. For each distinct
        # z_nummer in this list, select the single return value, but keep the
        # order from the original list.
        docs_by_znum = {}
        znum_order = []
        for doc_version in all_docs:
            if doc_version.z_nummer in docs_by_znum:
                docs_by_znum[doc_version.z_nummer].append(doc_version)
            else:
                znum_order.append(doc_version.z_nummer)
                docs_by_znum[doc_version.z_nummer] = [doc_version]
        result = []
        for znum in znum_order:
            docs = docs_by_znum[znum]
            # Call GetLatestObjectVersion on a concrete instance, so that
            # subclasses can override the behaviour.
            latest = docs[0].GetSpecificVersion(docs, self.one_version_method)
            if latest is not None:
                result.append(latest)
        return (result, result_complete)

    @classmethod
    def _path_vars(cls, obj):
        result = {
            "extra_parameters": obj.extra_parameters,
            "rule": obj.rule_name,
            "withFiles": obj.withFiles,
        }
        if obj.one_version_method:
            result["one_version_method"] = obj.one_version_method
        return result


@DocumentApp.path(
    path="",
    model=DocumentCollection,
    variables=DocumentCollection._path_vars,  # pylint: disable=protected-access
)
def _get_document_collection(extra_parameters, rule="", withFiles="complete"):
    # Pop legacy parameter all_versions
    all_versions = extra_parameters.pop("all_versions", None)
    version_method = extra_parameters.pop("one_version_method", None)
    if not version_method and all_versions is not None and all_versions == "0":
        version_method = "GetLatestObjectVersion"
    return DocumentCollection(extra_parameters, rule, version_method, withFiles)


@DocumentApp.json(model=Document, permission=ReadPermission, name="extended")
@check_license
def _document_default(doc, request):
    result = request.view(doc, name="base_data")
    result["relship:versions"] = [request.link(version) for version in doc.Versions]
    result["relship:uifiles"] = [
        request.view(f, name="file_meta") for f in doc.WebUIFiles
    ]
    return result


@DocumentApp.json(model=Document, permission=ReadPermission, name="file")
def _object_file_view(model, request):
    """This is a temporary fix, that returns the class icon if no actual
    thumbnail can  be found. Reason is, that the OLE icons have not yet
    been converted to SVG, and the PNG icons look terrible when scaled up.
    """
    from cs.platform.web.rest.generic.view import _object_file_view

    result = _object_file_view(model, request)
    if result is None and request.params.get("kind") == "thumbnail":
        result = {"url": None, "iconURL": model.GetClassIcon()}
    return result


class DocumentVersions(object):
    def __init__(self, cdb_obj):
        self.cdb_obj = cdb_obj
        self.versions = cdb_obj.Versions

    def versionize(self, json_args):
        json_args.update(load(json_args, self.cdb_obj.GetClassDef()))
        args = operations.prefix_args(None, **json_args)
        args.append(SimpleArgument(kArgumentUsesRestAPI, "1"))
        operations.operation(kOperationIndex, self.cdb_obj, args)


@DocumentApp.permission_rule(model=DocumentVersions, permission=CDB_Permission)
def _check_versions_permission(identity, model, permission):
    # For DocumentVersions models, check declared permissions on the source doc
    return permission.check_permission(identity, model.cdb_obj)


@DocumentApp.path(path="{keys}/versions", model=DocumentVersions)
def _get_versions(keys, app):
    obj = app.get_object(keys)
    if obj is None:
        return None
    return DocumentVersions(obj)


@DocumentApp.json(model=DocumentVersions, permission=ReadPermission)
def _document_versions(model, request):
    result = [request.view(v) for v in model.versions if v.CheckAccess("read")]
    # FIXME: add context
    return result


@DocumentApp.json(
    model=DocumentVersions, request_method="PUT", permission=ReadPermission
)
# Check read permission on the parent doc, the permission to actually index
# the document are checked by the operations
def _document_new_version(obj, request):
    try:
        obj.versionize(request.json)
    except RuntimeError as x:
        raise HTTPBadRequest(detail=str(x))
    return request.view(obj)
