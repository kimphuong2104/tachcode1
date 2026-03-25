#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines

import json
import logging
from collections import defaultdict

from cdb import auth, sig, sqlapi, transactions
from cdb.constants import kOperationCopy, kOperationDelete, kOperationModify
from cdb.objects.operations import operation
from cs.platform.web.rest.support import rest_key, rest_object
from cs.platform.web.root.main import _get_dummy_request

from cs.pcs.projects import Project
from cs.pcs.projects.project_structure import query_patterns, rest_objects, util
from cs.pcs.projects.tasks import Task

GET_VIEWS = sig.signal()


def _rest_object(obj_class, rest_key):
    obj = rest_object(obj_class, rest_key)
    if obj and obj.CheckAccess("read"):
        return obj
    return None


class ObjectNotFound(ValueError):
    pass


class View:
    """
    Abstract baseclass for project structure views.
    Do not use this class directly!

    ``View`` classes must define the class constant `view_name`.
    Custom views have to be registered.

    .. rubric :: Example: Registering the Custom View "my_view"

    .. code-block :: python

        from cdb import sig
        from cs.pcs.timeschedule.web.views import GET_VIEWS
        from cs.pcs.timeschedule.web.views import View

        class MyView(View):
            view_name = "my_view"

            def resolve_structure(self):
                pass

            def get_full_data(self, first=None):
                pass

            def format_response(self):
                return {s}

        @sig.connect(GET_VIEWS)
        def _register_view(register_callback):
            register_callback(MyView)

    Views can be instantiated with these parameters:

    `root_oid`
        The `cdb_object_id` of the project to resolve.

    `request`
        Optional `morepath.Request` for generating links.
        If `None`, a dummy request is used instead.

        `subprojects`
            Optional boolean;
            If `True`, subprojects are also resolved.
            Defaults to `False`.

    """

    def __init__(self, root_oid, request=None):
        self.root_oid = root_oid

        if request is None:
            self.request = _get_dummy_request()
        else:
            self.request = request
        self.subprojects = self.request.params.get("subprojects", "0") == "1"

    def __repr__(self):
        return f"'{self.view_name}' {super().__repr__()}"

    def resolve(self, first=None):
        """
        Calls the methods `resolve_structure`, `get_full_data` and
        `format_response` of `self`.

        :param first: Fed to `self.get_full_data`, which might handle this
            amount of first visible rows in a special way.
            Defaults to `None`.
        :type first: int

        :returns: The result of `self.format_response`
        """
        self.resolve_structure()
        self.get_full_data(first)
        return self.format_response()

    def resolve_structure(self):
        """
        Resolves the structure of `self.root_oid`
        with or without subprojects (depending on `self.subprojects`).

        Calls
        `cs.pcs.projects.project_structure.util.resolve_project_structure`
        and applies the result to the instance variables
        `self.records`, `self.rows`, `self.flat_nodes` and `self.levels`,
        respectively.
        """
        resolved = util.resolve_project_structure(
            self.root_oid,
            self.subprojects,
            self.get_row_and_node,
            self.request,
        )
        self.records, self.rows, self.flat_nodes, self.levels = resolved

    def get_full_data(self, first=None):
        """
        Retrieves full data of structure objects.

        Should only be called after
        `self.resolve_structure` has been called.

        To be implemented by each view class itself.

        :param first: If not `None`, only retrieve the full data of the first
            visible nodes until this number is reached
            (Children of collapsed nodes are not visible).
            `helpers.get_first_nodes` contains a helper
            to determine the first visible nodes.
        :type first: int
        """
        raise NotImplementedError()

    def format_response(self):
        """
        Returns a JSON-serializable response.

        Should only be called after both
        `self.resolve_structure` and
        `self.get_full_data` have been called.

        To be implemented by each view class itself.
        """
        raise NotImplementedError()

    def resolve_root_object(self, root_rest_key):
        """
        Returns the relevant root object.

        The default implementation tries to return a Project.
        If another kind of object is intended, this method needs
        to be overwritten.
        """
        return _rest_object(Project, root_rest_key)


class TreeView(View):
    """
    View for use with frontend component
    `cs-pcs-projects-web-StructureTree`.
    """

    view_name = "project_structure"

    LICENSE_FEATURE_ID = "PROJECTS_001"
    COPY_POSTFIX = "#COPY"

    @staticmethod
    def get_row_and_node(row_number, pcs_level, rest_link, rest_keys, expanded):
        """
        Satisfies `get_row_and_node` interface of
        `cs.pcs.projects.project_structure.util.resolve_project_structure`.

        :param row_number: Unused

        :param pcs_level: Provides `cdb_object_id` and `level`.
        :type pcs_level: `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :param rest_link: REST link of the node's object.
        :type rest_link: str

        :param rest_keys: REST keys of the node's object.
        :type rest_keys: str

        :param expanded: Unused

        :returns: Minimal node data for simple tree
            (which does not use rows at all).
        :rtype: tuple (None, dict)
        """
        return None, {
            "id": pcs_level.cdb_object_id,
            "level": pcs_level.level,
            "rest_key": rest_link.rsplit("/")[-1],
            "system:navigation_id": rest_keys,
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
                - "system:ui_link",
                - "system:description",
                - "system:navigation_id",
                - "system:icon_link",
                - "status" and
                - "cdb_objektart".
        """

        def set_value_if_true(attr, obj):
            if rest_object[attr]:
                obj[attr] = rest_object[attr]

        if rest_object:
            obj = {
                "@id": rest_object["@id"],
                "system:classname": rest_object["system:classname"],
                "system:navigation_id": rest_object["system:navigation_id"],
                "label": rest_object["system:description"],
                "icons": [
                    {"url": rest_object["system:icon_link"]},
                    rest_object.get("status_icon", None),
                ],
                "status_code": rest_object["status_code"],
            }

            set_value_if_true("is_milestone", obj)
            set_value_if_true("msp_active", obj)

            return obj

        return {}

    @staticmethod
    def get_adjacency_list(nodes):
        """
        :param nodes: Node information (requires keys "level" and "rest_key").
        :type nodes: list of dict

        :returns: Lists of children keys indexed by parent keys.
        :rtype: dict
        """
        if not nodes:
            return {}

        result = defaultdict(list)
        parents_by_level = [nodes[0]["rest_key"]]
        current_level = 0

        def set_parent(result, parents_by_level, level, node_id):
            if level > -1:
                # some usecases outside pcs (e.g. cs.costing) support showing
                # the same substructure more than once
                children = result[parents_by_level[level]]
                if node_id not in children:
                    children.append(node_id)

        def remember_parent(parents_by_level, level, node_id):
            # assert len(parents_by_level) >= level
            # clear parents of higher levels - they're complete
            parents_by_level = parents_by_level[:level]
            # make node this level's parent
            parents_by_level.append(node_id)
            # length of parents_by_level should always be level + 1
            return parents_by_level

        for node in nodes[1:]:
            level = node["level"]
            node_id = node["rest_key"]

            if level == current_level:
                if current_level > 0:
                    set_parent(result, parents_by_level, level - 1, node_id)
            else:
                set_parent(result, parents_by_level, level - 1, node_id)

            parents_by_level = remember_parent(parents_by_level, level, node_id)
            current_level = level

        return result

    @classmethod
    def get_additional_data(cls, pcs_record, request):
        desc_pattern, desc_attrs = util.get_project_structure_dtag(
            pcs_record.table_name
        )

        if pcs_record.table_name == "cdbpcs_task":
            icon_pattern = "cdbpcs_task_object"
            icon_attrs = [
                "is_group",
                "milestone",
            ]

        else:  # cdbpcs_project
            icon_pattern = "cdbpcs_project_obj"
            icon_attrs = [
                "parent_project",
                "template",
            ]

        is_milestone = pcs_record.record.get("milestone", 0) or 0
        msp_active = pcs_record.record.get("msp_active", 0)

        return {
            "system:description": util.get_object_description(
                desc_pattern, pcs_record.record, *desc_attrs
            ),
            "system:icon_link": util.get_object_icon(
                icon_pattern, pcs_record.record, *icon_attrs
            ),
            "status_icon": util.get_status(
                pcs_record.record["cdb_objektart"],
                pcs_record.record["status"],
            ),
            "status_code": pcs_record.record["status"],
            "is_milestone": is_milestone,
            "msp_active": msp_active,
        }

    def _traverse_flat_nodes(
        self, start_index, direction, max_length, selected_rest_key, expanded_rest_keys
    ):
        """
        Collecting nodes' rest_keys by traversing flat_nodes list,
        starting at 'start_index', going in given 'direction' until
        'max_length' nodes are found.
        Hereby only nodes, that are selected, the root node or have an
        expanded parent are collected.

        :param start_index: index of node to start traversing at
        :type start_index: int

        :param direction: direction to traverse through the flat nodes
                          (+1 for goind down, -1 for going up)
        :type direction: int

        :param max_length: maximal amount of keys to collect
        :type max_length: int

        :param selected_rest_key: key of selected node
        :type selected_rest_key: string

        :param expanded_rest_keys: list of expanded rest_keys
        :type expanded_rest_keys: list of strings

        :returns: list of collected rest keys
        :rtype: list of strings
        """
        top_level_keys = []
        i = start_index
        while (  # pylint: disable=chained-comparison
            i >= 0
            and i < len(self.flat_nodes)  # constraints set by flat_nodes
            and len(top_level_keys) < max_length  # constraint set by user input
        ):
            # get next rest key
            next_rest_key = self.flat_nodes[i]["rest_key"]
            # NOTE: Root (index 0) has no parent
            parent_rest_key = self.child_to_parent[next_rest_key] if i != 0 else ""
            # add to top_level_keys, if is root, selected or parent is expanded
            if (
                i == 0
                or next_rest_key == selected_rest_key
                or parent_rest_key in expanded_rest_keys
            ):
                top_level_keys.append(next_rest_key)
            i = i + direction
        return top_level_keys

    def _traverse_downwards(
        self, start_index, max_length, selected_rest_key, expanded_rest_keys
    ):
        # direction is down (+1)
        return self._traverse_flat_nodes(
            start_index, 1, max_length, selected_rest_key, expanded_rest_keys
        )

    def _traverse_upwards(
        self, start_index, max_length, selected_rest_key, expanded_rest_keys
    ):
        # direction is up (-1)
        return self._traverse_flat_nodes(
            start_index, -1, max_length, selected_rest_key, expanded_rest_keys
        )

    def _traverse_flat_nodes_BFS(self, start_key, max_length, encountered_keys):
        """
        Collecting nodes' rest_keys via Breadth-First-Search through the
        tree structure starting at 'start_key', ignoring all encountered
        keys and stop searching if 'max_length' keys are found.

        :param start_key: key to start BFS from
        :type start_key: string

        :param max_length: maximal amount of keys to collect
        :type max_length: int

        :param encountered_keys: list of keys to skip during BFS
        :type encountered_keys: list of strings

        :returns: list of collected rest keys
        :rtype: list of strings
        """

        # NOTE: Our Queue is implemented as list.
        #       The first element of the Queue is the last element of our list
        #       (accessed with pop). Therefore adding elements to the end of
        #       our Queue means adding them to the beginning of our list.
        queue = [start_key] if start_key else []
        top_level_keys = []
        while queue and len(top_level_keys) < max_length:
            next_rest_key = queue.pop()
            # if the key was not encountered before
            # add it to the top_level_keys
            if next_rest_key not in encountered_keys:
                top_level_keys.append(next_rest_key)
            if next_rest_key in self.adjacency_list:
                # create a new list with the children in reverse
                children_rest_keys = [] + self.adjacency_list[next_rest_key]
                children_rest_keys.reverse()
                # append children rest keys to the end of the queue
                queue = children_rest_keys + queue
        return top_level_keys

    def _reverse_adjacency_list(self):
        """
        Construct reverse of adjacency list to look up parent by child.
        """
        self.child_to_parent = {}
        for parent in self.adjacency_list:
            children = self.adjacency_list[parent]
            for child in children:
                self.child_to_parent.update({child: parent})

    def _get_first_and_remaining_nodes(self, rest_keys):
        first_nodes = []
        remaining_nodes = []
        for node in self.flat_nodes:
            if node["rest_key"] in rest_keys:
                first_nodes.append(node)
            else:
                remaining_nodes.append(node)
        return first_nodes, remaining_nodes

    def _get_and_parse_snapshot(self):
        """
        Access persisted UI-Settings and parse stored snapshot to
        retrieve selection as well as expansion state of nodes.

        :returns: rest key of selected node (default: root rest key),
                  index of selected node in flat nodes list
                  and list of rest keys of expanded nodes
        :rtype: tuple of string, int and list of strings
        """

        # init with default values
        start_index = 0
        selected_rest_key = None
        # list of all expanded node's rest_keys
        expanded_rest_keys = []
        # value of ui-settings
        snapshot = None

        # project_rest_key is the rest key of the root node
        project_rest_key = self.flat_nodes[0]["rest_key"]
        component = f"{project_rest_key}-cs-pcs-projects-web-StructureTree"
        sql_template = f"""SELECT * from {{table}}
                WHERE persno = '{auth.persno}'
                AND component = '{component}'
                AND property = 'snapshot'
            """
        sql = sql_template.format(table="csweb_ui_settings")
        records = sqlapi.RecordSet2(sql=sql)

        if records:
            try:
                snapshot = json.loads(records[0]["json_value"])
            except ValueError:
                # no JSON Value to decode in csweb_ui_settings
                # snapshot could be long text, therefore try csweb_ui_settings_txt
                sql_long = sql_template.format(table="csweb_ui_settings_txt")
                records = sqlapi.RecordSet2(sql=sql_long)
                if records:
                    try:
                        # long text values are stored line by line in table
                        snapshot = json.loads("".join([r["text"] for r in records]))
                    except ValueError:
                        # no JSON Value to decode in csweb_ui_settings_txt either
                        # therefore no snapshot
                        pass

            if snapshot:
                # if there's a selected node
                if "selectedRestKey" in snapshot:
                    # If selectedRestKey in snapshot is not None...
                    if snapshot["selectedRestKey"]:
                        selected_rest_key = snapshot["selectedRestKey"]
                        # find the index of this key in the flat nodes list

                        # Note: since flat_nodes only contains the currently loaded nodes
                        #       it may be, that the stored selected node is not
                        #       loaded yet. Return default value in that case.
                        selected_node = None
                        for node in self.flat_nodes:
                            if node["rest_key"] == selected_rest_key:
                                selected_node = node
                                break
                        if selected_node:
                            start_index = self.flat_nodes.index(selected_node)

                # determine all expanded node's rest_keys
                for key in snapshot.keys():
                    # only consider snapshot entries representing nodes
                    if type(snapshot[key]) is dict and "expanded" in snapshot[key]:
                        # only add expanded node's restkeys
                        if snapshot[key]["expanded"]:
                            expanded_rest_keys.append(key)

        return selected_rest_key, start_index, expanded_rest_keys

    def _get_first_nodes(self, first):
        """
        :param first: amount of nodes to be loaded
        :type first: int

        :returns: Up to `first` nodes from `self.flat_nodes` and IDs of
                  remaining nodes.
        :rtype: Tuple of two lists

        Which nodes are included in the first list of the return value?
        (in all cases, the algorithm will stop as soon as the first list
        includes `first` nodes)

        0. If `self.flat_nodes` contains only up to `first` nodes, simply
            return all of them

        1. If the user already has UI settings for the project structure
            (which include the selected node, falling back to the root node,
            and the expanded/collapsed state for nodes)
            1.1 Traverse `self.flat_nodes` from the selected node downwards to
                collect visible nodes (considering expansion state)
            1.2 Traverse from the selected node upwards to collect visible nodes
            1.3 Do a BFS ("breadth-first search") starting at the root node to
                collect nodes regardless of expansion state/visibility

        2. Else (the user does not have UI settings, so node visibility depends
            on the default expansion state in the frontend, which is assumed
            to be "collapsed")
            2.1 Do a BFS starting at the root node to collect nodes
        """

        # 0) Are there more than [first] nodes?
        if 0 < first < len(self.flat_nodes):
            # list to store [first] nodes
            top_level_rest_keys = []

            # 1) Access persisted UI-Settings (snapshot) and parse it to get
            (
                selected_rest_key,
                start_index,
                expanded_rest_keys,
            ) = self._get_and_parse_snapshot()

            # if snapshot was present, proceed with 1.1 and 1.2
            if selected_rest_key or expanded_rest_keys:
                # create mapping from child to parent (stored on self)
                self._reverse_adjacency_list()

                # 1.1) Gather all nodes following the start_index going down
                top_level_rest_keys += self._traverse_downwards(
                    start_index,
                    first - len(top_level_rest_keys),  # max_length
                    selected_rest_key,
                    expanded_rest_keys,
                )

                if len(top_level_rest_keys) < first:
                    # 1.2) Gather all nodes following the start_index going up
                    top_level_rest_keys += self._traverse_upwards(
                        start_index - 1,
                        first - len(top_level_rest_keys),  # max_length
                        selected_rest_key,
                        expanded_rest_keys,
                    )
            # if top_level_rest_keys are not full yet, proceed with 1.3)
            # or if no snaphot was present proceed with 2.1
            if len(top_level_rest_keys) < first:
                # 1.3/2.1) Breadth-First-Search to fill top_level_rest_keys
                #    starting from root and ignoring already encountered nodes

                root_rest_key = self.flat_nodes[0]["rest_key"]
                top_level_rest_keys += self._traverse_flat_nodes_BFS(
                    root_rest_key, first - len(top_level_rest_keys), top_level_rest_keys
                )

            # Return nodes with keys in top_level_rest_keys as to be loaded first
            # and rest as remaining nodes
            return self._get_first_and_remaining_nodes(top_level_rest_keys)
        # return all nodes as to be loaded first
        else:
            return self.flat_nodes, []

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
        rest_objs = rest_objects.rest_objects_by_oid(
            self.records,
            self.request,
            self.get_additional_data,
        )

        self.adjacency_list = TreeView.get_adjacency_list(self.flat_nodes)
        first_nodes, remaining = self._get_first_nodes(first)
        self.full_nodes = {
            node["rest_key"]: self.get_tree_object(rest_objs.get(node["id"], None))
            for node in first_nodes
        }
        self.remaining = [node["id"] for node in remaining]

    @staticmethod
    def get_full_data_of(object_ids, request):
        """
        Retrieves full data for given `object_ids`.

        :param object_ids: `cdb_object_id` values to retrieve data for.
        :type object_ids: list of str

        :returns: Full data indexed by each object's rest key
            (`system:navigation_id`).
            Only objects readable by the user are included.
        :rtype: dict
        """
        pcs_levels = util.get_table_for_oids(object_ids)
        records = util.resolve_records(pcs_levels)
        rest_objs = rest_objects.rest_objects_by_restkey(
            records,
            request,
            TreeView.get_additional_data,
        )
        return {
            rest_key: TreeView.get_tree_object(rest_obj)
            for rest_key, rest_obj in rest_objs.items()
        }

    def format_response(self):
        """
        :returns: JSON-serializable response with keys
            "nodes", "objects" and "remaining", containing
            full node data, an adjacency list and `cdb_object_id` values
            still missing in "objects", respectively.
        :rtype: dict
        """
        return {
            "nodes": self.adjacency_list,
            "objects": self.full_nodes,
            "remaining": self.remaining,
        }

    @classmethod
    def _resolve_object(cls, keys, objs, rest_id):
        """
        Resolves the object identified by ``rest_id``
        and mutates ``keys`` and ``objs`` to include resolved information.

        :param keys: REST keys indexed by REST IDs to add resolved object to
        :type keys: dict of str

        :param objs: Objects indexed by REST IDs to add resolved object to
        :type objs: dict of cdb.objects.Object

        :param rest_id: REST ID of the object to resolve
        :type rest_id: str

        :raises ObjectNotFound: if no object exists for given ``rest_id``
            or read access is denied
        """
        rest_key, is_task = util.rest_id2rest_key(rest_id.rstrip(cls.COPY_POSTFIX))
        obj_class = Task if is_task else Project
        obj = _rest_object(obj_class, rest_key)
        if not obj:
            raise ObjectNotFound(rest_id)

        keys[rest_id] = rest_key
        objs[rest_id] = obj

    @classmethod
    def _get_child_objects(cls, parent_obj):
        if isinstance(parent_obj, Task):
            return parent_obj.Subtasks
        else:  # assume parent_obj is a Project
            return parent_obj.TopTasks + parent_obj.OrderedSubProjects

    @classmethod
    def _missing_children(cls, parent_obj, children_rest_keys):
        """
        :param parent_obj: A parent task or project
        :type parent_obj: cs.pcs.projects.tasks.Task or cs.pcs.projects.Project

        :param children_rest_keys: Sorted REST keys of parent's children
        :type children_rest_keys: list of str

        :raises ValueError: if ``children_rest_keys`` is missing
            any of ``parent_obj's`` children
        """
        child_objects = cls._get_child_objects(parent_obj)

        expected = {rest_key(c) for c in child_objects}
        missing_children = expected.difference(set(children_rest_keys))

        if missing_children:
            logging.error(
                "missing children of '%s': %s",
                parent_obj.cdb_object_id,
                missing_children,
            )
            raise ValueError(
                "Objects were changed in the backend by another user. "
                "Please refresh."
            )

    @classmethod
    def _get_objs_and_position(cls, target, parent, children, target_in_children):
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
        keys = {}
        objs = {}
        new_positions = {}

        if target_in_children not in children:
            raise ValueError(
                f"target '{target_in_children}' is missing in children: {children}"
            )

        cls._resolve_object(keys, objs, target)
        cls._resolve_object(keys, objs, parent)

        for index, child_rest_id in enumerate(children):
            cls._resolve_object(keys, objs, child_rest_id)
            new_positions[child_rest_id] = 10 * (index + 1)

        cls._missing_children(
            objs[parent],
            [keys[child] for child in children],
        )

        return objs, new_positions

    @classmethod
    def _get_target_children(cls, target, target_in_children, parent, predecessor):
        objs = {}
        cls._resolve_object({}, objs, parent)
        child_objects = cls._get_child_objects(objs[parent])

        base_url = parent.rsplit("/", 2)[0]
        children = [util.obj2rest_id(base_url, c) for c in child_objects]

        if target == target_in_children:
            children = [c for c in children if c != target]

        if predecessor is None:
            children.insert(0, target_in_children)
        else:
            # may raise ValueError:
            predecessor_index = children.index(predecessor)
            children.insert(predecessor_index + 1, target_in_children)

        return children

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
        if is_move:
            target_in_children = target
            target_operation = kOperationModify
        else:
            target_in_children = f"{target}{cls.COPY_POSTFIX}"
            target_operation = kOperationCopy

        if children is None:
            children = cls._get_target_children(
                target, target_in_children, parent, predecessor
            )

        objs, new_positions = cls._get_objs_and_position(
            target, parent, children, target_in_children
        )

        # update target: parent reference and position
        target_changes = {"position": new_positions[target_in_children]}
        parent_obj = objs[parent]
        target_obj = objs[target]
        target_is_task = isinstance(target_obj, Task)

        def get_name(task_or_project):
            if isinstance(task_or_project, Task):
                return task_or_project.task_name
            return task_or_project.project_name

        if not is_move:  # adapt copy's name
            name_field = "task_name" if target_is_task else "project_name"
            max_length = getattr(
                Task if target_is_task else Project,
                name_field,
            ).length
            target_changes[name_field] = util.get_copy_name(
                target_obj[name_field],
                [get_name(objs[child]) for child in children],
                max_length,
            )

            if not target_is_task:
                target_changes["cdb_project_id"] = "#"
                target_changes["parent_project"] = parent_obj.cdb_project_id

        if target_is_task:
            target_changes["parent_task"] = (
                parent_obj.task_id if isinstance(parent_obj, Task) else ""
            )

        with transactions.Transaction():
            result = operation(target_operation, target_obj, **target_changes)

            for child in children:  # update child positions
                if not child.endswith(cls.COPY_POSTFIX):
                    objs[child].Update(position=new_positions[child])

        if not is_move:
            # return new rest key
            return rest_key(result)

    @classmethod
    def delete_copy(cls, copy_id):
        """
        Deleted an object to revert a drag & drop "copy" action
        in the project structure.

        :param copy_id: REST ID of the project or task to delete
        :type copy_id: str

        :raises ObjectNotFound: if read access is denied for the object
        :raises ElementsError: if delete operation fails
        """
        rest_key, is_task = util.rest_id2rest_key(copy_id)
        obj_class = Task if is_task else Project
        obj = _rest_object(obj_class, rest_key)
        if not obj:
            raise ObjectNotFound(copy_id)

        operation(kOperationDelete, obj)


class TreeTableView(View):
    """
    View for use with frontend component
    `cs-pcs-timeschedule-web-TreeTable`.
    """

    view_name = "tree_table"

    LICENSE_FEATURE_ID = "PROJECTS_001"

    @staticmethod
    def get_row_and_node(row_number, pcs_level, rest_link, rest_keys, expanded):
        """
        Satisfies `get_row_and_node` interface of
        `cs.pcs.projects.project_structure.util.resolve_project_structure`.

        :param row_number: 0-based row number.
        :type row_number: int

        :param pcs_level: `cdb_object_id` and `level`.
        :type pcs_level: `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :param rest_link: URL of the full REST object.
        :type rest_link: str

        :param rest_keys: REST keys of the node's object.
        :type rest_keys: str

        :param expanded: Expansion state
        :type expanded: bool

        :returns: Row and node representation, respectively,
            for use in the tree table component.
        :rtype: tuple(dict, dict)
        """
        oid = pcs_level.cdb_object_id
        row = {
            "id": oid,
            "rowNumber": row_number,
            "columns": [],
            "restLink": rest_link,
        }
        node = {
            "id": oid,
            "rowNumber": row_number,
            "expanded": expanded,
            "children": [],
            "system:navigation_id": rest_keys,
        }
        return row, node

    def get_full_data(self, first=None):
        """
        Generates nested node structure required by `TreeTable` component
        and stores it in `self.full_nodes`.

        Also fill `self.visible_nodes` with the first n visible rows
        where n = `first`.
        If `first` is `None`, `self.visible_nodes` will also be.

        See `cs.pcs.projects.project_structure.util.get_tree_nodes`
        for details.

        :param first: If not `None`, only retrieve the full data of the first
            visible nodes until this number is reached
            (Children of collapsed nodes are not visible).
        :type first: int
        """
        self.full_nodes = util.get_tree_nodes(self.flat_nodes, self.levels)
        if first is None:
            self.visible_nodes = None
        else:
            self.visible_nodes = util.get_first_nodes(self.full_nodes, first)

    def format_response(self):
        """
        :returns: Keys "rows" and "nodes" containing flat rows
            and nested nodes, respectively.
        :rtype: dict
        """
        return {
            "rows": self.rows,
            "nodes": self.full_nodes,
        }


def get_task_structure(task_uuid, baseline_id):
    """
    :param task_uuid: UUID of the task to get the substructure of
    :type task_uuid: str

    :param baseline_id: The ``ce_baseline_id`` of the root task
    :type baseline_id: str

    :returns: The substructure of the task identified by ``task_uuid``,
        not including the task itself. Order is unspecified.
    :rtype: cdb.objects.ObjectCollection
    """
    query_pattern = query_patterns.get_query_pattern("task_structure")
    query_str = query_pattern.format(
        oid=sqlapi.quote(task_uuid),
        blid=sqlapi.quote(baseline_id),
    )
    pcs_levels = util.resolve_query(query_str)
    pcs_records = util.resolve_records(pcs_levels)
    uuids = {x.cdb_object_id for _, x in pcs_records}.difference([task_uuid])
    return Task.KeywordQuery(cdb_object_id=uuids)
