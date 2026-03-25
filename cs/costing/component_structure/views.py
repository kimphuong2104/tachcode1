# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import logging
import six
from webob.exc import HTTPBadRequest
from cdb import auth, sig, transactions
from cdb import util as cdbutil
from cdb.constants import kOperationModify
from cdb.lru_cache import lru_cache
from cdb.objects import ByID
from cdb.objects.operations import operation

from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects.common.webdata.util import get_classinfo_REST
from cs.pcs.projects.project_structure.views import GET_VIEWS, ObjectNotFound
from cs.pcs.projects.project_structure.util import get_object_description
from cs.pcs.projects.project_structure.util import get_object_icon
from cs.pcs.projects.project_structure.util import get_table_for_oids
from cs.pcs.projects.project_structure.rest_objects import rest_objects_by_oid
from cs.pcs.projects.project_structure import TreeView

from cs.costing.calculations import Calculation
from cs.costing.component_structure import util

DTAG_PREFIX = "costing_structure_dtag."


def _split_rest_id(rest_id):
    url_parts = rest_id.split("/")
    rest_name = url_parts[-2]
    rest_key = url_parts[-1]
    return rest_name, rest_key


def _get_oid_from_url(object_url):
    # it is assumed, that object url matche the pattern
    # https://hostname:port/api/v1/collection/class_rest_name/rest_key
    # where rest_key are the primary_keys joined by '@'
    class_rest_name, rest_key = _split_rest_id(object_url)
    classDef, _ = get_classinfo_REST(class_rest_name)
    class_name = classDef.getClassname()
    if (class_name == "cdbpco_comp2component"):
        # cdb_object_id is the only primary key, therefore rest_key == oid
        return rest_key
    else:
        raise ValueError("Invalid class for object: %s", class_name)


def _get_and_check_access_by_oid(oid, access_right):
    obj = ByID(oid)
    if not(obj and obj.CheckAccess(access_right)):
        logging.error(
            "User '%s' has '%s' access on object with cdb_object_id: '%s'",
            auth.persno, access_right, oid
        )
        raise HTTPBadRequest
    return obj


@lru_cache()
def get_costing_structure_dtag(classname):
    """
    resolve project structure description tag for given table
    """
    label = cdbutil.get_label("{}{}".format(DTAG_PREFIX, classname))
    [label, fields] = util.validate_dtag(classname, label)

    return label, fields


class CostTreeView(TreeView):
    """
    View for use with frontend component
    `cs-costing-web-StructureTree`.
    """
    view_name = "costing_structure"

    LICENSE_FEATURE_ID = "COSTING_006"

    ### Developer's Note:
    # Resolving the costing structure is done slightly different as in pcs.
    # When resolving the structure, attributes for displaying are also resolved
    # for all entries. Due to the nature of the component structure,
    # we need attributes from different tables as well as a special rest key
    # identifying the entires (cdb_object_id--<number of occurence>)
    # These attributes are only kept for the first 100 records, which
    # are augmented with additional data.
    # For the remaining ones only the 'oid with occurence' is kept.
    # On the second request for resolving the remaining entries, for each
    # distinct oid among the 'oid with occurence' the attributes are re-resolved;
    # meaning the attributes are fetched by oid from db and
    # then remapped to the corresponding 'oids with occurence'.
    # Afterwards these records are augmented with additional data.
    #
    # Initial data resolving is therefore slower as in pcs, but payload size
    # and second request handling is about the same.
    ###

    @classmethod
    def get_additional_data(cls, pcs_record, request):
        desc_pattern, desc_attrs = get_costing_structure_dtag(
            pcs_record.record["cdb_classname"] if pcs_record.record["cdb_classname"] else "cdbpco_calculation")

        icon_pattern = "cdbpco_comp_object"
        icon_attrs = [
            "cdb_classname"
        ]

        cloned_icon_link = "/resources/icons/byname/cdbpco_cloned"
        component_link = "{}/api/v1/collection/cdbpco_component/{}"

        return {
            "system:description": get_object_description(
                desc_pattern,
                pcs_record.record,
                *desc_attrs
            ),
            "system:icon_link": get_object_icon(
                icon_pattern,
                pcs_record.record,
                *icon_attrs
            ),
            "cloned": pcs_record.record["cloned"],
            "cloned_icon_link": {"url": cloned_icon_link if pcs_record.record["cloned"] == 1 else ""},
            "comp_object_id": pcs_record.record["comp_object_id"] if "comp_object_id" in pcs_record.record else "",
            "component_id": six.moves.urllib.parse.unquote(
                component_link.format(request.application_url, pcs_record.record['comp_object_id'])
            ) if "comp_object_id" in pcs_record.record else ""
        }

    @classmethod
    def get_tree_object(cls, rest_object):
        """
        :param rest_object: Metadata of an object.
        :type rest_object: dict or ``None``

        :returns: Minimal object data for simple tree
        :rtype: dict

        :raises KeyError: if ``rest_object`` is not ``None`` but missing one
            of these keys:
                - "system:description",
                - "system:navigation_id",
                - "system:icon_link",
                - "status",
                - 'comp_object_id',
                - 'component_id',
                - 'cloned' and
                - 'cloned_icon_link'
        """
        # kind, status
        if rest_object:
            return {
                "@id": rest_object["@id"].split('--')[0],
                "@type": rest_object["@type"],
                "system:classname": rest_object["system:classname"],
                "system:navigation_id": rest_object["system:navigation_id"],  # cdb_oid--occurence_id
                "system:description": rest_object["system:description"],
                "comp_object_id": rest_object["comp_object_id"],
                "rest_key": rest_object["@id"],  # cdb_oid--occurence_id
                "component_id": rest_object['component_id'],
                "label": rest_object["system:description"],
                "cloned": rest_object["cloned"],
                "icons": [
                    {"url": rest_object["system:icon_link"]},
                    rest_object["cloned_icon_link"]
                ],
            }

        return {}

    def resolve_structure(self):
        """
        Resolves the structure of `self.root_oid`.

        Calls
        `cs.costing.component_structure.util.resolve_component_structure`
        and applies the result to the instance variables
        `self.records`, `self.rows`, `self.flat_nodes` and `self.levels`,
        respectively.
        """
        resolved = util.resolve_component_structure(
            self.root_oid,
            self.get_row_and_node,
            self.request,
        )
        self.records, self.rows, self.flat_nodes, self.levels = resolved

    @staticmethod
    def get_full_data_of(object_ids_with_occurence, request):
        """
        Retrieves full data for given `object_ids_with_occurence`.

        :param object_ids_with_occurence: `cdb_object_id` values with occurence
                                           suffix to retrieve data for.
        :type object_ids_with_occurence: list of str

        :returns: Full data indexed by each object's rest key
            (`object_ids_with_occurence`).
            Only objects readable by the user are included.
        :rtype: dict
        """
        object_ids = []
        mapping_oids = {}
        for oid_occ in object_ids_with_occurence:
            oid = oid_occ.split('--')[0]
            object_ids.append(oid)
            if oid not in mapping_oids:
                mapping_oids[oid] = []
            mapping_oids[oid].append(oid_occ)
        # Check read access for all oids
        object_id_with_read_access = util.filter_oid_with_read_access(object_ids)
        pcs_levels = get_table_for_oids(object_id_with_read_access)
        records = util.resolve_records(pcs_levels)
        # resolve additional data and re-map rest object to oids_with_occurence (rest_key)
        rest_objs = util.rest_objects_by_restkey(
            records,
            mapping_oids,
            request,
            CostTreeView.get_additional_data,
        )
        return {
            rest_key: CostTreeView.get_tree_object(rest_obj)
            for rest_key, rest_obj in rest_objs.items()
        }

    def get_full_data(self, first=None):
        """
        Retrieves full data of structure objects.
        Sets the instance variables
        `self.full_nodes`, `self.remaining` and `self.adjacency_list`.

        :param first: (Maximum) Number of nodes to retrieve full data of.
            Full data of all nodes is retrieved if `first` is either
                - `None` or
                - not larger than 0 or
                - larger than the length of `self.flat_nodes`.
            The adjacency list always contains all nodes,
            regardless of `first`.
            Defaults to `None`.
        :type first: int
        """
        # runs `get_additional_data` for all nodes
        # which is approximately as fast for large projects as filtering
        # `self.records` beforehand
        rest_objs = rest_objects_by_oid(
            self.records,
            self.request,
            self.get_additional_data,
        )

        self.adjacency_list = CostTreeView.get_adjacency_list(self.flat_nodes)
        first_nodes, remaining = self._get_first_nodes(first)
        self.full_nodes = {
            node["rest_key"]: self.get_tree_object(
                rest_objs.get(node["id"], None))
            for node in first_nodes
        }
        self.remaining = [node["id"] for node in remaining]

    def resolve_root_object(self, root_rest_key):
        kwargs = {'cdb_object_id': root_rest_key}
        return get_and_check_object(Calculation, "read", **kwargs)

    @staticmethod
    def determine_sort_order(idx, object_id):
        """
        Returns new value for sort_order for node in structure tree.

        :param index: index of node object among its siblings
        :type index: number

        :param object_id: object id of node object to change sort_order for
        :type object_url: str

        :returns: new sort_order value for node object
        :rtype: int

        Note: Overwrite this method in order to set sort_order as desired.
                You may use existing helper methods:
                `ById`:: oid => object of oid
        Example:
        `
        obj = ByID(oid)
        comp_class_name = obj.Component.GetClassname()
        cloned = obj.cloned
        pos = idx * 10
        prefix = 0
        if (comp_class_name == "cdbpcs_part_component"):
            prefix = 10
        elif (comp_class_name == "cdbpcs_step_component"):
            prefix = 20
        else:
            return pos

        return int("{prefix}{pos}".format(prefix=prefix, pos=pos))
        `
        """
        return (idx + 1) * 10

    @classmethod
    def _resolve_object(cls, keys, objs, rest_id, uuids=None):
        """
        Resolves the object identified by ``rest_id``
        and mutates ``keys`` and ``objs`` to include resolved information.

        :param keys: REST keys indexed by REST IDs to add resolved object to
        :type keys: dict of str

        :param objs: Objects indexed by REST IDs to add resolved object to
        :type objs: dict of cdb.objects.Object

        :param rest_id: REST ID of the object to resolve
        :type rest_id: str

        :param uuids: UUIDs indexed by REST IDs to add resolved IDs to.
            Defaults to ``None`` because base implementation in ``cs.pcs``
            does not use it.
        :type objs: dict of str

        :raises ObjectNotFound: if no object exists for given ``rest_id``
            or read access is denied
        """
        uuid = _get_oid_from_url(rest_id)

        if uuids is not None:
            # is None in base class's _get_target_children call (revert move)
            uuids[rest_id] = uuid

        obj = _get_and_check_access_by_oid(uuid, "read")

        if not obj:
            raise ObjectNotFound(rest_id)

        _, rest_key = _split_rest_id(rest_id)
        keys[rest_id] = rest_key
        objs[rest_id] = obj

    @classmethod
    def _get_child_objects(cls, parent_obj):
        # obj is Component2Component
        return parent_obj.Children

    @classmethod
    def _get_objs_and_position(cls, target, parent, children,
                               target_in_children):
        """
        :param target: REST ID of project or task
        :type target: str

        :param parent: REST ID of parent project or task
        :type parent: str

        :param children: REST IDs of all children of ``parent`` and
            ``target_in_children``.
        :type children: list of str

        :param target_in_children: Mandatory member of ``children``.
        :type target_in_children: str

        :returns: Two dictionaries containing
            1. the cdb.objects.Object entries and
            2. the new position numbers

            for ``children``, respectively.
            Each dictionary is indexed by the child's REST ID.
        :rtype: tuple of dict

        :raises ValueError: if ``target_in_children``
            is not part of ``children``
        """
        uuids = {}
        keys = {}
        objs = {}
        new_positions = {}

        if target_in_children not in children:
            raise ValueError(
                "target '{}' is missing in children: {}".format(
                    target_in_children, children))

        cls._resolve_object(keys, objs, target, uuids)
        cls._resolve_object(keys, objs, parent, uuids)

        for index, child_rest_id in enumerate(children):
            cls._resolve_object(keys, objs, child_rest_id, uuids)
            new_positions[child_rest_id] = CostTreeView.determine_sort_order(
                index, uuids[child_rest_id])

        cls._missing_children(
            objs[parent],
            [keys[child] for child in children],
        )

        return objs, new_positions

    @classmethod
    def persist_drop(cls, target, parent, children, predecessor, is_move):
        """
        Persists a drag & drop action in the project structure.
        Basically moves or copies a target project or task.

        If ``is_move`` is ``True``, ``target`` is changed
        so it becomes a child of ``parent`` at the position
        specified by its appearance in ``children``.

        If ``is_move`` is ``False``, ``target`` is copied
        as a new child of ``parent``.
        Its position among the children is determined by the position of
        ``target`` appended with ``self.COPY_POSTFIX`` in ``children``
        (because the list may include both the original and the copy).

        In either case, the position of ``children`` may be changed
        to match the desired order as given in ``children``.

        :param target: REST ID of project or task to move or copy
        :type target: str

        :param parent: REST ID of new parent project or task of ``target``
        :type parent: str

        :param children: Ordered REST IDs of parent's child tasks and/or
            projects containing target in the intended position
            (e.g. the target state).
        :type children: list of str

        :param predecessor: ``@id`` of target's new predecessor.
            Used as a fallback if ``children`` is ``None``
        :type predecessor: str

        :param is_move: If ``True``, ``target`` is moved, else copied.
        :type is_move: bool

        :raises ObjectNotFound: if read access is denied for any object
        :raises ValueError: if ``children`` does not contain
            the target and all of parent's current children
        :raises ElementsError: if any modify operation fails
        """
        if not is_move:
            raise NotImplementedError

        if children is None:
            children = cls._get_target_children(
                target, target, parent, predecessor)

        objs, new_positions = cls._get_objs_and_position(
            target, parent, children, target)

        # update target: parent reference and position
        parent_comp = _get_and_check_access_by_oid(
            objs[parent].comp_object_id, "read")
        target_comp = _get_and_check_access_by_oid(
            objs[target].comp_object_id, "read")
        target_cloned = (
            1 if bool(objs[parent].cloned) else bool(target_comp.cloned))
        target_changes = {
            "sort_order": six.text_type(new_positions[target]),
            # Note: comp2component's parent_object_id is the cdb_object_id of
            #       the corresponding parent's component
            "parent_object_id": parent_comp.cdb_object_id,
            # mark target node as cloned if parent is a clone
            "cloned": target_cloned,
        }

        with transactions.Transaction():
            operation(kOperationModify, objs[target], **target_changes)

            if target_cloned != target_comp.cloned:
                operation(kOperationModify, target_comp, cloned=target_cloned)

            for child in children:  # update child positions
                operation(
                    kOperationModify,
                    objs[child],
                    sort_order=six.text_type(new_positions[child]),
                )

    @classmethod
    def delete_copy(cls, copy_id):
        raise NotImplementedError


@sig.connect(GET_VIEWS)
def _register_view(register_callback):
    register_callback(CostTreeView)
