#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import print_function
from __future__ import absolute_import

import datetime
import os
import shutil
import tempfile
import time

from cdb import cdbuuid
from cdb.objects.cdb_file import CDB_File, cdb_link_item, cdb_file_record
from cdb.storage import blob

from cs.vp.items import Item
from cs.documents import Document, DocumentReference
from cs.workspaces import Workspace

import six


def create_test_workspace(name, parameters, **kwargs):
    """
    Creates a workspace with a number of assemblies that can be parametrized.
    Using Object Framework instead of operations for speed.
    """
    params = parameters.copy()
    params.update(kwargs)

    print('\nCreating workspace "%s"' % name)
    before = time.time()

    # create workspace
    w_nummer = Workspace.create_workspace_number()
    attrs = Workspace.MakeChangeControlAttributes()
    ws = Workspace.Create(
        z_nummer=w_nummer,
        z_index="",
        titel=name,
        z_art="workspace",
        z_status=0,
        **attrs
    )
    create_workspace_file(ws)

    # create documents
    top_docs = []
    for _ in six.moves.range(params["num_top_docs"]):
        depth = params["depth"]
        top = create_structure(ws, params, depth)
        top_docs.append(top)

    # create parallel index structures
    num_index_per_doc = params["num_index_per_doc"]
    if num_index_per_doc:
        print("\nCreating indexes")
    for _ in six.moves.range(num_index_per_doc):
        top_docs = [index_structure(doc) for doc in top_docs]

    ellapsed = time.time() - before
    print('\nCreating workspace "%s" took %s secs.' % (name, ellapsed))

    return ws


def create_structure(parent, params, depth):
    """
    Recursive function to create a structure of CAD documents.
    """
    print(".", end="")  # progress
    item_attributes = params["item_attributes"]
    item = Item.Create(teilenummer=Item.MakeItemNumber(), t_index="", **item_attributes)
    dummy = Document()
    dummy.teilenummer = item.teilenummer
    z_nummer = Document.makeNumber(dummy)
    doc_attrs = params["document_attributes"].copy()
    doc_attrs.update(Document.MakeChangeControlAttributes())
    doc = Document.Create(
        z_nummer=z_nummer,
        z_index="",
        teilenummer=item.teilenummer,
        t_index=item.t_index,
        titel="Test Document %s" % z_nummer,
        **doc_attrs
    )

    # link to parent
    attrs = cdb_link_item.MakeChangeControlAttributes()
    cdb_link_item.Create(
        cdbf_object_id=parent.cdb_object_id,
        cdb_wspitem_id=cdbuuid.create_uuid(),
        cdb_folder="",
        cdb_link=doc.cdb_object_id,
        **attrs
    )
    attrs = DocumentReference.MakeChangeControlAttributes()
    DocumentReference.Create(
        z_nummer=parent.z_nummer,
        z_index=parent.z_index,
        z_nummer2=doc.z_nummer,
        z_index2=doc.z_index,
        cdb_link="0",
        logischer_name="",
        owner_application="WSM",
        reltype="WSM",
        **attrs
    )

    # create file and child docs
    if depth <= 1:
        create_part_file(doc, params)
    else:
        subdocs = []
        num_children_per_doc = params["num_children_per_doc"]
        for _ in six.moves.range(num_children_per_doc):
            subdoc = create_structure(doc, params, depth - 1)
            subdocs.append(subdoc)
        create_assembly_file(doc, params)

    return doc


def create_workspace_file(doc):
    path_to_metadata = {}
    d = tempfile.mkdtemp()
    try:
        cdb_wspitem_id = cdbuuid.create_uuid()
        cdbf_type = "TXT"
        fn = "README.txt"
        path = os.path.join(d, fn)
        with open(path, "w") as fd:
            fd.writelines(
                "This workspace was automatically generated.\n"
                "The CAD files are fake. They cannot be opened in the CAD system.\n"
                "But the workspace should be ok for WSD tests that do not involve the CAD system.\n"
            )

        path_to_metadata[path] = {
            "cdbf_type": cdbf_type,
            "cdbf_name": fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_wspitem_id": cdb_wspitem_id,
            "cdbf_primary": "1",
        }
        create_files_with_blobs(path_to_metadata)
    finally:
        shutil.rmtree(d)


def create_part_file(doc, params):
    path_to_metadata = {}
    d = tempfile.mkdtemp()
    try:
        # write "CAD" file, containing random bytes
        cdb_wspitem_id = cdbuuid.create_uuid()
        cdbf_type = params["part_file_type"]
        fn = create_filename("part.ipt", cdbf_type, doc)
        path = os.path.join(d, fn)
        file_size = params["file_size"]
        with open(path, "wb") as fd:
            fbytes = os.urandom(file_size)
            fd.write(fbytes)
        path_to_metadata[path] = {
            "cdbf_type": cdbf_type,
            "cdbf_name": fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_wspitem_id": cdb_wspitem_id,
            "cdbf_primary": "1",
        }

        # write "preview" file, 1/10 of the size
        preview_fn = fn + ".png"
        preview_path = os.path.join(d, preview_fn)
        with open(preview_path, "wb") as fd:
            fbytes = os.urandom(min(file_size / 10, 1))
            fd.write(fbytes)
        path_to_metadata[preview_path] = {
            "cdbf_type": "PNG",
            "cdbf_name": preview_fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_belongsto": cdb_wspitem_id,
            "cdbf_primary": "0",
            "cdb_wspitem_id": cdbuuid.create_uuid(),
        }

        # write appinfo
        appinfo_fn = fn + ".appinfo"
        appinfo_path = os.path.join(d, appinfo_fn)
        with open(appinfo_path, "w") as fd:
            fd.write(
                '<appinfo integration-version="Dummy data by cs.workspaces.create_test_workspace">\n'
                "  <properties>\n"
                '    <property id="ProjectInformation-Document Number" type="string" value="%s"/>\n'
                "  </properties>\n"
                "</appinfo>\n" % doc.z_nummer
            )
        path_to_metadata[appinfo_path] = {
            "cdbf_type": "Appinfo",
            "cdbf_name": appinfo_fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_belongsto": cdb_wspitem_id,
            "cdbf_primary": "0",
            "cdb_wspitem_id": cdbuuid.create_uuid(),
        }

        create_files_with_blobs(path_to_metadata)
    finally:
        shutil.rmtree(d)


def create_filename(original_name, cdbf_type, doc):
    fr = cdb_file_record.Create(cdbf_object_id=doc.cdb_object_id, cdbf_type=cdbf_type)
    fn = fr.generate_name(original_name)
    fr.Delete()
    return fn


def create_assembly_file(doc, params):
    path_to_metadata = {}
    d = tempfile.mkdtemp()
    try:
        # write "CAD" file, containing random bytes
        cdb_wspitem_id = cdbuuid.create_uuid()
        cdbf_type = params["assembly_file_type"]
        fn = create_filename("assembly.iam", cdbf_type, doc)
        path = os.path.join(d, fn)
        file_size = params["file_size"]
        with open(path, "wb") as fd:
            fbytes = os.urandom(file_size)
            fd.write(fbytes)
        path_to_metadata[path] = {
            "cdbf_type": cdbf_type,
            "cdbf_name": fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_wspitem_id": cdb_wspitem_id,
            "cdbf_primary": "1",
        }

        # write "preview" file, 1/10 of the size
        preview_fn = fn + ".png"
        preview_path = os.path.join(d, preview_fn)
        with open(preview_path, "wb") as fd:
            fbytes = os.urandom(min(file_size / 10, 1))
            fd.write(fbytes)
        path_to_metadata[preview_path] = {
            "cdbf_type": "PNG",
            "cdbf_name": preview_fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_belongsto": cdb_wspitem_id,
            "cdbf_primary": "0",
            "cdb_wspitem_id": cdbuuid.create_uuid(),
        }

        # write appinfo
        appinfo_fn = fn + ".appinfo"
        appinfo_path = os.path.join(d, appinfo_fn)
        occs = create_appinfo_occurrences(doc)
        with open(appinfo_path, "w") as fd:
            fd.write(
                '<appinfo integration-version="Dummy data by cs.workspaces.create_test_workspace">\n'
                "  <properties>\n"
                '    <property id="ProjectInformation-Document Number" type="string" value="%s"/>\n'
                "  </properties>\n"
                "%s\n"
                "</appinfo>\n" % (doc.z_nummer, occs)
            )
        path_to_metadata[appinfo_path] = {
            "cdbf_type": "Appinfo",
            "cdbf_name": appinfo_fn,
            "cdbf_object_id": doc.cdb_object_id,
            "persno": "caddok",
            "cdb_belongsto": cdb_wspitem_id,
            "cdbf_primary": "0",
            "cdb_wspitem_id": cdbuuid.create_uuid(),
        }

        create_files_with_blobs(path_to_metadata)
    finally:
        shutil.rmtree(d)


def create_appinfo_occurrences(doc):
    # assumption:no subfolders
    occs = []
    for ref in doc.DocumentReferences:
        dst = ref.ReferencedDocument
        anchor = dst.PrimaryFiles[0]
        occs.append(anchor.cdbf_name)
    occs = [
        '    <occurrence id="%s" bom-relevant="yes" name="%s" quantity="1" sortval="%s">\n'
        '      <cadreference path="%s" variantid=""/>\n'
        "    </occurrence>\n" % (i, p, i, p)
        for i, p in enumerate(occs)
    ]
    ret = "  <occurrences>\n%s  </occurrences>" % ("".join(occs))
    return ret


def index_structure(doc):
    """
    Recursively index a document and the structure below.
    Avoids operations for performance.
    File names stay the same.
    """
    print(".", end="")  # progress
    doc2 = doc.Copy(z_index=next_index(doc.z_index))
    for f in doc.Files:
        f.Copy(cdbf_object_id=doc2.cdb_object_id)
    child_to_index_child = {}
    for ref in doc.DocumentReferences:
        dst = ref.ReferencedDocument
        dst2 = index_structure(dst)
        ref.Copy(
            z_nummer=doc2.z_nummer,
            z_index=doc2.z_index,
            z_nummer2=dst2.z_nummer,
            z_index2=dst2.z_index,
        )
        child_to_index_child[dst.cdb_object_id] = dst2.cdb_object_id
    for item in doc.WorkspaceItems:
        if item.cdb_classname == "cdb_link_item":
            item.Copy(
                cdbf_object_id=doc2.cdb_object_id,
                cdb_link=child_to_index_child[item.cdb_link],
            )
    return doc2


def next_index(z_index):
    if not z_index:
        return "a"
    elif z_index == "z":
        raise ValueError("Out of indexes")
    else:
        n = six.int2byte(ord(z_index) + 1)
        return n


def delete_workspace_with_referenced_documents(doc, is_workspace=True):
    """
    DANGEROUS! Really deletes all the PDM documents with indexe and parts, circumventing operations.
    """
    # files and links
    print(".", end="")  # progress
    for f in doc.WorkspaceItems:
        f.Delete()
    # recursively delete subdocs
    for ref in doc.DocumentReferences:
        dst = ref.ReferencedDocument
        subdocs = [dst]
        if is_workspace:
            # if at toplevel: delete parallel structures, too
            subdocs = Document.KeywordQuery(z_nummer=dst.z_nummer)
        for subdoc in subdocs:
            if subdoc is not None:
                delete_workspace_with_referenced_documents(subdoc, is_workspace=False)
    # delete refs
    for ref in doc.DocumentReferences:
        ref.Delete()
    if doc.Item:
        doc.Item.Delete()
    doc.Delete()


def create_files_with_blobs(path_to_metadata):
    """
    Creates blobs and matching CDB_File objects.
    """
    BLOCKSIZE = 1024 * 1024

    bs = blob.getBlobStore("main")
    attrs = Workspace.MakeChangeControlAttributes()
    attrs["cdbf_fdate"] = datetime.datetime.utcnow()
    for path, metadata in list(six.iteritems(path_to_metadata)):
        ul = bs.Upload(meta=metadata)
        with open(path, "rb") as blobfd:
            while True:
                block = blobfd.read(BLOCKSIZE)
                if not block:
                    break
                ul.write(block)
        blob_id = ul.close()
        metadata["cdbf_blob_id"] = blob_id
        metadata.update(attrs)
        CDB_File.Create(**metadata)
