# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Support to access the UI-Structures of the kernel via REST
"""

from __future__ import absolute_import

import six
import urllib

from cdbwrapc import kNodeTypeObject
from cdb import ElementsError
from cdb.objects.core import class_from_handle
from cdb.platform.mom import CDBObjectHandle
try:
    from cdb.platform.mom import increase_eviction_queue_limit
except ImportError:
    # CE 16 has no eviction queue any more - remove this code if and when cs.web
    # is branched for CE 16
    from contextlib import nullcontext as increase_eviction_queue_limit
from cs.platform.web.rest import get_collection_app
from cs.platform.web.uisupport import get_ui_link
from webob.exc import HTTPForbidden
from cs.web.components.structure import StructureApp, StructureModel
from .refresh.model import StructureRefreshModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = []


def _obj_from_handle(oh):
    """
    An implementation that is usually able to create an cdb.objects.Object
    without doing a select as object_from_handle does.
    """
    cls = class_from_handle(oh)
    return cls._FromObjectHandle(oh)


@StructureApp.json(model=StructureModel)
def _structure_model_json(model, request):
    def _adjust_node(node, request, collection_app):
        """
        Helper that removes useless variables and adds
        some links
        """
        rest_node_id = node.get("rest_node_id")
        if rest_node_id:
            extra = {"parent_node_id": rest_node_id}
            expand_model = StructureModel(model.root_object,
                                          model.structure_name,
                                          extra)
            node["expand_url"] = request.link(expand_model)

        # Add the UI-Link to the object
        if node.get("node_type") == kNodeTypeObject:
            oid = node.pop("oid", "")
            full_oid = node.pop("full_oid", None)
            if oid:
                obj = CDBObjectHandle(full_oid if full_oid else oid)
                if obj.is_valid():
                    node["ui_link"] = get_ui_link(request, obj)
                    if obj.getClassDef().getRESTName():
                        objects_obj = _obj_from_handle(obj)
                        if objects_obj:
                            node["object_url"] = urllib.parse.unquote(request.link(objects_obj, app=collection_app))
        # No one need the node type
        node.pop("node_type")

        if node["subnodes"]:
            for subnode in node["subnodes"]:
                _adjust_node(subnode, request, collection_app)

    try:
        with increase_eviction_queue_limit(10000):
            nodes = model.get_nodes()
            if nodes:
                collection_app = get_collection_app(request)
                for node in nodes:
                    _adjust_node(node, request, collection_app)
            result = model.get_struct_info()
            refresh_model = StructureRefreshModel(model.root_object,
                                                  model.structure_name)
            result["refresh_url"] = request.link(refresh_model)
            result["nodes"] = nodes
            return result
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))
