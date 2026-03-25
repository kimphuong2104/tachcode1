#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from webob import exc
from webob.exc import HTTPNotFound

from cdb.objects import ByID
from cdb.objects import Rule
from cdb.util import get_label, get_prop

from cs.documents import Document
from cs.platform.web import JsonAPI
from cs.platform.web import root
from cs.platform.web.rest import get_collection_app
from cs.vp.cad import FILE_TYPE_PDF
from cs.vp.cad.file_type_list import FileTypeList
from cs.vp.items import Item

__revision__ = "$Id$"

_ALLOWED_2D_FILE_TYPE_PROP = "p2df"

_DOCUMENTS_FOR_2D_PREVIEW_RULE = "Part Preview: 2D Documents"


def _get_allowed_filetypes_for_2d_preview():
    filetype_prop = get_prop(_ALLOWED_2D_FILE_TYPE_PROP)
    if not filetype_prop:
        # Allow only PDFs by default if not configured otherwise.
        return FileTypeList(FILE_TYPE_PDF)

    return FileTypeList.from_string(filetype_prop)


class ImagePreview(object):
    def __init__(self, object_id):
        self.requested_object_id = object_id

        obj = ByID(object_id)
        if obj is None:
            raise exc.HTTPNotFound()

        self.image_preview_file = None
        if isinstance(obj, Item):
            self.image_preview_file = obj.get_image_preview_file()
        elif isinstance(obj, Document):
            # cs.threed's PreviewDisplayer fetches an image preview for the hybrid client via a single
            # document, so we use that as a single preview doc instead.
            preview_images = obj.get_2d_supported_preview_images()
            self.image_preview_file = preview_images[0] if preview_images else None
        else:
            # Passed object ID is neither item nor model/document.
            raise exc.HTTPBadRequest()

    def convert_to_json(self, request):
        collection_app = get_collection_app(request)

        image = None
        model_object_id = None

        if self.image_preview_file is not None:
            model_object_id = self.image_preview_file.cdbf_object_id
            image = {
                "src": request.link(self.image_preview_file, app=collection_app),
                "tooltip": get_label("cs_threed_hoops_click_to_launch_viewer")
            }

        if model_object_id is None:
            model_object_id = self.requested_object_id

        return {
            "requestedObjectId": self.requested_object_id,
            "image": image,
            "viewer": {
                "model": model_object_id
            }
        }


class AvailableViewers(object):
    def __init__(self, item_or_object_id, document_selection_rule=None, allowed_file_types=None):
        self.document_selection_rule = document_selection_rule
        self.allowed_file_types = allowed_file_types

        if isinstance(item_or_object_id, Item):
            self.item = item_or_object_id
        else:
            self.item = Item.ByKeys(cdb_object_id=item_or_object_id)

    def get_2d_preview_files(self):
        documents = self.item.get_preview_documents(self.document_selection_rule)

        preview_pdfs = []
        preview_images = []
        for doc in documents:
            if self.allowed_file_types is None or self.allowed_file_types.contains(FILE_TYPE_PDF):
                preview_pdfs += doc.get_2d_preview_pdfs()

            supported_images = doc.get_2d_supported_preview_images()
            if self.allowed_file_types is not None:
                preview_images += [img for img in supported_images if self.allowed_file_types.contains(img.cdbf_type)]
            else:
                preview_images += supported_images

        return preview_pdfs, preview_images

    def get_available_viewers(self, request):
        if self.item is None:
            raise HTTPNotFound()

        collection_app = root.get_v1(request).child("collection")

        def _create_viewer_props(file_list, comp):
            viewer_props = []
            for file_to_preview in file_list:
                viewer_props.append({
                    "label": get_label("cs_vp_preview_twod"),
                    "id": "2D",
                    "component": comp,
                    "props": {
                        "filename": file_to_preview.cdbf_name,
                        "url": request.link(file_to_preview, app=collection_app)
                    },
                })
            return viewer_props

        pdfs, images = self.get_2d_preview_files()

        result = []
        result += _create_viewer_props(pdfs, "cs-web-components-pdf-PDFViewer")
        result += _create_viewer_props(images, "cs-web-components-base-ImageViewer")
        return result


class PreviewInternal(JsonAPI):
    pass


# HINT: this internal api is also used by the preview in cs.threed (cs.threed.hoops.web.preview). Do not delete/modify the url
# THINKABOUT: the url /internal/preview/... is very generic. Maybe make the python module part of the url?
@root.Internal.mount(app=PreviewInternal, path="preview")
def _mount_threed():
    return PreviewInternal()


@PreviewInternal.path(path="image_preview/{object_id}", model=ImagePreview)
def _get_image_preview(object_id):
    return ImagePreview(object_id)


@PreviewInternal.json(model=ImagePreview)
def _get_result(result, request):
    return result.convert_to_json(request)


@PreviewInternal.path(path="preview_viewers")
class PreviewViewersInternal(object):
    pass


@PreviewInternal.json(model=PreviewViewersInternal, request_method="POST")
def preview_viewers(model, request):
    payload = request.json
    result = {}
    if "objectIds" in payload:

        document_selection_rule = Rule.ByKeys(_DOCUMENTS_FOR_2D_PREVIEW_RULE)
        allowed_file_types = _get_allowed_filetypes_for_2d_preview()

        for item in Item.KeywordQuery(cdb_object_id=payload["objectIds"]):
            av = AvailableViewers(item, document_selection_rule, allowed_file_types)
            result[item.cdb_object_id] = av.get_available_viewers(request)

    return result
