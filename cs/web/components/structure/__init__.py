# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Support to access the UI-Structures of the kernel via REST
"""

from __future__ import absolute_import
import json
from collections import deque, defaultdict
import logging

import six

from cdbwrapc import RestStructure, kNodeTypeObject, RelationshipDefinition, CDBClassDef
from cdb import misc, auth
from cdb import ElementsError
from cdb.platform.mom import CDBObjectHandle
from cs.platform.web import JsonAPI
from cs.platform.web.rest import support
from cs.platform.web.rest.generic.main import App
from webob.exc import HTTPForbidden
from cdb.platform._structureinfo import StructureInformation

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ["StructureCache", "StructureApp", "StructureModel"]


@six.add_metaclass(misc.Singleton)
class StructureCache(object):
    """
    A cache for structures.
    """

    def __init__(self):
        self.structures = deque()
        self.structure_cache_limit = 5  # the number of structures to be cached

    def clear(self):
        """
        Clears the cached structure objects. At this time this is a
        feature for tests that checks if a node can be expanded when
        the structure ist not there.
        """
        self.structures = deque()

    def _add_rest_node_id(self, node, structure):
        """
        We have to build an id that allow us to navigate stateless.
        This call adds this id to the node if we are able to build such an id.
        """
        snode_id = node.get("id", "")
        persistent_id = structure.get_persistent_id(snode_id)
        if persistent_id:
            node["rest_node_id"] = json.dumps(persistent_id)

    def _adjust_node(self, node, structure):
        """
        Prepares the node for REST. Remove the fields
        we do not need and add further fields if necessary.
        """
        self._add_rest_node_id(node, structure)
        no_of_subitems = node.pop("no_of_subitems", -1)
        if no_of_subitems == 0:
            node["subnodes"] = []
        elif ("rest_node_id" not in node) or (node["action_flag"] & 1):
            # No persistency - or autoexpand-flag set
            # we have to retrieve the subnodes immediately
            node["subnodes"] = self._get_nodes(structure, node["id"])
        else:
            node["subnodes"] = None

        # No one needs the internal id
        node.pop("id")

    def get_structure(self, structure_name, root_obj, from_cache=True):
        """
        Checks if the cache provides a structure with
        the given `structure_name` and the root `root_obj`.
        If not the structure will be created automatically.
        Returns the `cdbwrapc.RestStructure` or raises an
        `cdb.ElementsError` if the structure is not
        available.
        """
        result = None
        oid = root_obj.ToObjectHandle().get_object_id()
        pos = 0
        structure = None
        for structure in self.structures:
            if (structure.get_id() == structure_name) and \
               (structure.get_root_node().get_object_id() == oid):
                result = structure
                break
            pos += 1

        if result:
            if pos > 0 or not from_cache:
                self.structures.remove(structure)
            if from_cache:
                # Sort to access the recently used elements at the beginning
                self.structures.appendleft(structure)
            else:
                result = None

        if not result:
            result = RestStructure(structure_name, root_obj.ToObjectHandle())
            self.structures.appendleft(result)
            if len(self.structures) > self.structure_cache_limit:
                self.structures.pop()

        return result

    def get_root(self, structure_name, root_obj):
        """
        Returns the root node of the given structure.
        Raises an `cdb.ElementsError` if the structure is not
        available.
        """
        # If someone asks for the root node we have to create a new
        # structure (E044613)
        structure = self.get_structure(structure_name, root_obj, False)
        result = structure.get_root()
        self._adjust_node(result, structure)
        return result

    def _get_nodes(self, structure, parent_node_id, refresh_parent_node=False):
        """
        Retrieve the subnodes of `parent_node_id` that
        is part of the `cdbwrac.RestStructure` structure.
        """
        nodes = structure.get_nodes(parent_node_id, refresh_parent_node)
        for node in nodes:
            self._adjust_node(node, structure)
        return nodes

    def get_nodes(self, structure_name, root_obj, parent_node_id, refresh_parent_node=False):
        """
        Return a list of subnodes of the node with the id `parent_node_id`.
        Raises a `cdb.ElementsError` if the structure is not
        available.
        """
        structure = self.get_structure(structure_name, root_obj)
        try:
            parent_node_info = json.loads(parent_node_id)
            if isinstance(parent_node_info, list) and len(parent_node_info) == 2:
                if structure.contains_node(parent_node_info[0]):
                    return self._get_nodes(structure, parent_node_info[0], refresh_parent_node)
                else:
                    obj = CDBObjectHandle(parent_node_info[1])
                    node_id = structure.add_node(obj)
                    return self._get_nodes(structure, node_id, refresh_parent_node)
            elif isinstance(parent_node_info, six.string_types):
                # A persistent ID
                return self._get_nodes(structure, parent_node_info, refresh_parent_node)
            else:
                raise ValueError("We expect a JSON coded list of 2 elements "
                                 "or a persistent id for parent_node_id.")
        except ElementsError as e:
            logging.getLogger(__name__).warning(
                "Failed to retrieve subnodes of '%s': %s", parent_node_id,
                str(e))
            raise e
        except Exception as e:
            logging.getLogger(__name__).exception("Failed to receive subnodes "
                                                  "of %s", parent_node_id)
            raise ValueError("%s is not a valid parent_node_id in this "
                             "structure." % parent_node_id)


class StructureApp(JsonAPI):
    """
    The morepath app that provides the structures
    configured in the kernel in the REST API.
    """
    def __init__(self, parent_object):
        """
        Initializes the app with the object that
        is the root object of the structure.
        """
        super(StructureApp, self).__init__()
        self.parent_object = parent_object


class StructureModel(object):
    """
    Morepath model for a structure.
    """
    def __init__(self, root_object, structure_name, extra_parameters=None):
        """
        Initializes the structure `structure_name`
        that starts with the given `root_object`.
        `extra_parameters` is a dictionary that where
        ``parent_node_id`` is the parent node for retrieving
        more nodes.
        """
        self.root_object = root_object
        self.structure_name = structure_name
        self.extra_parameters = extra_parameters

    def get_relationships(self):
        def has_add_operations(rs):
            try:
                # RelshipOperationInfo.getOperationInfo was introduced with CE 15.6.8
                ropinfo = rs.getOperationInfo()
            except AttributeError:
                return True
            ref_ops = ropinfo.get_reference_op_info().get_opinfo_list()
            link_ops = ropinfo.get_link_op_info().get_opinfo_list()
            return len([
                op for op in ref_ops + link_ops if
                             (op.creates_object() and not op.is_object_operation()) or
                             op.get_opname() == 'CDB_SelectAndAssign'
            ]) > 0

        structure = StructureCache().get_structure(self.structure_name, self.root_object)
        structure_info = StructureInformation(structure)
        clsdefs = [CDBClassDef(name) for name in
                   structure_info.get_involved_classes(visible=True)]
        result = {}
        for clsdef in clsdefs:
            cls_relship_defs = {
                rs.get_name(): rs
                for rs in [RelationshipDefinition(name) for name in clsdef.getRelationshipNames()]
                if rs.is_valid() and rs.get_rolename() and rs.get_reference_cldef().getRESTName()
                   and has_add_operations(rs)
            }
            relships = [cls_relship_defs[relship_name].get_rolename()
                        for relship_name in structure.get_relationship_names()
                        if cls_relship_defs.get(relship_name) is not None]
            result[clsdef.getClassname()] = relships
        return result

    def get_struct_info(self):
        """
        Returns a dictionary about further information about
        the structure. The dictionary is only filled if no
        `parent_node_id` is given in the `extra_parameters`.
        """
        result = {}
        if not self.extra_parameters or not self.extra_parameters.get("parent_node_id"):
            s = StructureCache().get_structure(self.structure_name, self.root_object)
            if s:
                result["title"] = s.get_op_title()
                result["obj_title"] = s.get_title()
                expand_level = s.get_initial_expand_level()
                result["initial_expand_level"] = expand_level if expand_level > 0 else 2
                result["relships_with_add_menu"] = self.get_relationships()
        return result

    def get_nodes(self):
        """Returns a list of dictionaries where every dictionary represents a
        node.

        If you provide a ``parent_node_id`` in `__init__` the nodes returned
        are the subnodes of this node. The root-nodes are returned otherwiese.
        Raises a `cdb.ElementsError` if the structure is not available.

        """
        result = []
        refresh_parent_node = False
        if self.extra_parameters:
            parent_node_id = self.extra_parameters.get("parent_node_id")
            refresh_parent_node = self.extra_parameters.get("refresh") == "true"
        else:
            parent_node_id = ""
        if not parent_node_id:
            # Get the root
            root_node = StructureCache().get_root(self.structure_name, self.root_object)
            result.append(root_node)
        else:
            result = StructureCache().get_nodes(self.structure_name,
                                                self.root_object,
                                                parent_node_id,
                                                refresh_parent_node)
        return result


@StructureApp.path(model=StructureModel, path='{structure_name}')
def _get_structure_model(structure_name, app, extra_parameters):
    if not app.parent_object.CheckAccess('read'):
        # no read access to the source object means no access to the structure
        raise HTTPForbidden()
    try:
        return StructureModel(app.parent_object, structure_name, extra_parameters)
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))


@App.mount(app=StructureApp, path="{keys}/structure",
           variables=lambda o: dict(keys=support.rest_key(o.parent_object)))
def _mount_structure(keys, app):
    model = app.get_object(keys)
    return StructureApp(model)


@App.defer_links(model=StructureModel)
def _defer_structure_target(app, model):
    return app.child(StructureApp(model.parent_object))
