#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb.util import get_label

from cs.platform.web import root

THREED_AVAILABLE = None


def _threed_available():
    global THREED_AVAILABLE
    if THREED_AVAILABLE is None:
        try:
            import cs.threed
            THREED_AVAILABLE = True
        except ImportError:
            THREED_AVAILABLE = False
    return THREED_AVAILABLE


def get_available_viewers_for_document(doc, request):
    result = []
    collection_app = root.get_v1(request).child("collection")

    def _add_result(file_list, comp, prev_id="2D", label="cs_vp_preview_twod"):
        for each in file_list:
            result.append({
                "props": {
                    "filename": each.cdbf_name,
                    "url": request.link(each, app=collection_app)
                },
                "label": get_label(label),
                "id": prev_id,
                "component": comp
            })

    _add_result(doc.get_2d_preview_pdfs(), "cs-web-components-pdf-PDFViewer")
    _add_result(doc.get_2d_supported_preview_images(), "cs-web-components-base-ImageViewer")

    if _threed_available() and doc.is_3d_preview_available():
        result.append({
            "props": {
                "model": doc.cdb_object_id
            },
            "label": get_label("cs_vp_preview_threed"),
            "id": "3D",
            "component": "cs-threed-hoops-web-cockpit-Preview"
        })

    return result
