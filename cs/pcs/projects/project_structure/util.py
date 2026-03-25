#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import logging
import re
from collections import namedtuple
from itertools import groupby
from operator import itemgetter
from urllib.parse import quote, unquote, urlencode

from cdb import ddl, sig, sqlapi, util
from cdb.lru_cache import lru_cache
from cdb.platform import gui
from cdb.platform.olc import StatusInfo
from cdbwrapc import CDBClassDef
from cs.platform.web.rest.support import rest_key, rest_name_for_class_name

from cs.pcs.projects.common import format_in_condition
from cs.pcs.projects.common.rest_objects import get_oid_from_node_id
from cs.pcs.projects.project_structure import query_patterns

DTAG_PREFIX = "project_structure_dtag."
DTAG_PATTERN = re.compile(r"[{](.+?)[}]")

LEVEL = namedtuple(
    "pcs_level", ["cdb_object_id", "table_name", "level", "additional_data"]
)
PCS_RECORD = namedtuple("pcs_record", ["table_name", "record"])


def PCS_LEVEL(cdb_object_id, table_name, level, additional_data=None):
    return LEVEL(cdb_object_id, table_name, level, additional_data)


ELLIPSIS = "..."


def url_unquote(text):
    return unquote(text)


def _get_icon_url(icon_id, query):
    icon_url = f"/resources/icons/byname/{quote(icon_id)}"

    if query:
        query_str = urlencode(query)
        return f"{icon_url}?{query_str}"
    else:
        return icon_url


def get_object_icon(icon_id, record=None, *attrs):
    """
    :param icon_id: Name of a configured icon to get the URL for.
    :type icon_id: str

    :param record: Record representing an object. Defaults to `None`.
    :type record: cdb.sqlapi.Record

    :param attrs: Key names in `record` to construct
        query parameters from.
    :type attrs: tuple

    :returns: URL of the icon identified by `icon_id`.
        If both `record` and `attrs` are given,
        the URL includes matching query parameters.
    :rtype: str
    """
    query = [(attr, record[attr]) for attr in attrs] if attrs else None
    return _get_icon_url(icon_id, query)


def _get_status_label(kind, status):
    try:
        info = StatusInfo(kind, status)
    except (TypeError, ValueError):
        logging.exception("invalid status: '%s', %s", kind, status)
        return None

    return info.getLabel()


def get_status(kind, status):
    """
    :param kind: Name of a configured Object Lifecycle (OLC).
    :type kind: str

    :param attrs: ID of a configured status in OLC `kind`.
    :type attrs: int

    :returns: Status icon URL and status label in user's language.
    :rtype: dict
    """
    query = [("sys::workflow", kind), ("sys::status", status)]

    return {
        "url": _get_icon_url("State Color/0", query),
        "title": _get_status_label(kind, status),
    }


def get_object_description(description_pattern, record=None, *attrs):
    """
    :param description_pattern: Object description pattern.
        May contain placeholders for `format` keyword arguments: "{key}".
    :type description_pattern: str

    :param record: Record representing an object. Defaults to `None`.
    :type record: cdb.sqlapi.Record

    :param attrs: Key names in `record` to format pattern with.
    :type attrs: tuple

    :returns: Resolved object description pattern.
    :rtype: str
    """
    kwargs = {attr: "" if record[attr] is None else record[attr] for attr in attrs}
    return description_pattern.format(**kwargs)


def get_flat_structure(
    pcs_levels, pcs_records, get_row_and_node, request, collapsed=None
):
    """
    :param pcs_levels: cdb_object_id, table name and level of objects.
    :type pcs_levels: list of
        `cs.pcs.projects.project_structure.util.PCS_LEVEL`

    :param pcs_records: database table name and record of resolved
        content objects.
    :type pcs_records: list of
        `cs.pcs.projects.project_structure.util.PCS_RECORD`

    :param get_row_and_node: The function to construct a single row and
        node entry for parameters
        `(row_number, pcs_level, rest_link, expanded)`.
    :type get_row_and_node: function

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :param collapsed: Expansion states indexed by row IDs (rest links).
        If a row ID is not present, it is considered expanded,
        otherwise the boolean value determines if it is collapsed.
        Defaults to an empty dict (everything expanded).
    :type collapsed: dict

    :returns: JSON-serializable rows, (flat) tree nodes, levels.
    :rtype: tuple of (list of dict, list of dict, list of int)

    :raises KeyError: if rest link cannot be generated for any object.

    .. warning ::

        See
        ``cs.pcs.projects.common.rest_objects.get_restlinks_in_batch``
        for other possible exceptions.

    """
    from cs.pcs.projects.common.rest_objects import (
        get_restkeys_in_batch,
        get_restlinks_in_batch,
    )

    if collapsed is None:
        collapsed = {}

    rest_links = get_restlinks_in_batch(pcs_records, request)
    rest_keys = get_restkeys_in_batch(pcs_records)
    readable = get_readable_oids(pcs_levels, rest_links)

    rows = []
    flat_nodes = []
    levels = []
    for row_number, pcs_level in enumerate(readable):
        oid = pcs_level.cdb_object_id

        row, node = get_row_and_node(
            row_number,
            pcs_level,
            rest_links[oid],
            rest_keys[oid],
            not collapsed.get(str(row_number), False),
        )

        rows.append(row)
        flat_nodes.append(node)
        levels.append(int(pcs_level.level))

    return rows, flat_nodes, levels


def resolve_project_structure(root_oid, subprojects, get_row_and_node, request):
    """
    :param root_oid: The `cdb_object_id` of the root project to resolve.
    :type root_oid: str

    :param subprojects: If ``True``, the project structure is resolved
        recursively including all subrojects.
        If not, subprojects are not part of the resolved structure.
    :type subprojects: bool

    :param get_row_and_node: The function to construct a single row and
        node entry for parameters
        `(row_number, oid, rest_link, collapsed)`.
    :type get_row_and_node: function

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: 4-tuple of pcs records, rows, flat tree nodes and levels.
    :rtype: tuple
    """
    pcs_levels = resolve_structure(root_oid, "cdbpcs_project", subprojects)
    pcs_records = resolve_records(pcs_levels)

    rows, flat_nodes, levels = get_flat_structure(
        pcs_levels,
        pcs_records,
        get_row_and_node,
        request,
    )
    return pcs_records, rows, flat_nodes, levels


def resolve_structure(root_oid, root_table_name, subprojects, offset=0):
    """
    :param root_oid: `cdb_object_id` of the root object to resolve.
    :type root_oid: str

    :param root_table_name: Database table name of the root object.
    :type root_table_name: str

    :param subprojects: If ``True`` (and ``root_table_name`` is
        "cdbpcs_project"), subproject headers will also be resolved.
        Else, subprojects are not part of the result at all.
    :type subprojects: bool

    :returns: Resolved structure nodes.
        If no structure could be resolved,
        returns a list with just the root node.
    :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`

    .. note ::

        Please note that tasks with position ``NULL`` are unsupported and
        considered corrupted data.
        Their existence will break the expected sorting order.

    """
    if root_table_name == "cdbpcs_project" and subprojects:
        pattern = "subprojects"
    else:
        pattern = "structure"

    query_pattern = query_patterns.get_query_pattern(pattern)

    if query_pattern:
        query_str = query_pattern.format(oid=root_oid)
        return resolve_query(query_str)
    else:
        return [PCS_LEVEL(root_oid, root_table_name, 0)]


def resolve_query(query_str):
    """
    :param query_str: SQL query to resolve a structure.
        Must select at least `cdb_object_id`, `table_name` and `llevel`.
    :type query_str: str

    :returns: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`
    """
    rset = sqlapi.RecordSet2(sql=query_str)
    return [
        PCS_LEVEL(
            record.cdb_object_id,  # child oid
            record.table_name,
            int(record.llevel),
        )
        for record in rset
    ]


def get_tree_nodes(flat_nodes, levels):
    """
    :param flat_nodes: List of node dicts with numerical level information.
    :type flat_nodes: list of dict

    :param levels: List of levels matching ``flat_nodes`` (have to be of same
        length and in same order).
    :type levels: list of int

    :returns: Nested node structure based on ``flat_nodes``.
        Only includes root nodes (e.g. level == 0) at the top level,
        others nested under each node's "children" key.
    :rtype: list of dict

    :raises KeyError: if any node is missing the key "children",
    :raises TypeError: if any node is not a dict or `levels` is not iterable.
    :raises IndexError: if `levels` contains less elements than `flat_nodes`
        or does not contain gapless values starting from 0.
    """
    if not flat_nodes:
        return []

    nodes_by_level = []
    current_level = -1

    def _wrap_up_levels(nodes_by_level, from_level, to_level):
        "internal helper, mutates ``nodes_by_level``"
        for wrap_level in range(from_level, to_level, -1):
            parent = nodes_by_level[wrap_level - 1][-1]
            parent["children"] += nodes_by_level[wrap_level]
            del nodes_by_level[wrap_level]

    for index, node in enumerate(flat_nodes):
        level = levels[index]

        if level == current_level:
            # same level: add to nodes_by_level
            nodes_by_level[level].append(node)
        elif level > current_level:
            # move deeper: add to next level in nodes_by_level
            nodes_by_level.append([node])
        else:
            # move up: wrap up nodes_by_level up to level
            _wrap_up_levels(nodes_by_level, current_level, level)
            nodes_by_level[level].append(node)

        current_level = level

    _wrap_up_levels(nodes_by_level, current_level, 0)
    return nodes_by_level[0]


def get_first_nodes(tree_nodes, first):
    """
    :param tree_nodes: The (nested) nodes to process.
    :type tree_nodes: list of nested tree nodes.

    :param first: The amount of visible nodes to return.
    :type first: int

    :returns: Flattened list of node IDs representing the first n visible
        rows (where n = `first`).
        Children of expanded rows are visible,
        children of collapsed rows are not.
        The returned list's length is at least 1, at most `first`.
    :rtype: list

    :raises KeyError: if any node does not contain any of the keys
        "id" or "children".
        The value of key "expanded" defaults to `False` if missing.

    :raises TypeError: if `first` is not numerical.
    """
    result = []

    for node in tree_nodes:
        result.append(get_oid_from_node_id(node["id"]))

        if len(result) >= first:
            return result

        if node.get("expanded", False):
            result += get_first_nodes(
                node["children"],
                first - len(result),
            )
            if len(result) >= first:
                return result

    return result


def resolve_records(pcs_levels):
    """
    :param pcs_levels: cdb_object_ids and database table names of
        objects to query database for.
    :type pcs_levels: list of
        `cs.pcs.projects.project_structure.util.PCS_LEVE`

    :returns: table names and records for objects identified by `pcs_levels`.
        **Only includes records the current user has read access for**
    :rtype: list of `cs.pcs.projects.project_structure.util.PCS_RECORD`

    :raises ValueError: if
        - any value contains a non-string value in first position,
        - `pcs_levels` or one of its values is not iterable or
        - any value contains less than 2 value.
    :raises cdb.dberrors.DBConstraintViolation: if any table name is
        invalid or does not exist.
    """
    oids_by_relation = _get_oids_by_relation(pcs_levels)

    result = []

    for relation, oids in oids_by_relation:
        try:
            query_str = _get_oid_query_str(oids)
        except TypeError as exc:
            raise ValueError(f"non-string oid value: '{oids}'") from exc
        result += [
            PCS_RECORD(relation, rec)
            for rec in sqlapi.RecordSet2(relation, query_str, access="read")
        ]

    return result


def get_readable_oids(ordered_oids, readable_oids):
    """
    :param ordered_oids: tuples in expected order where the first entry is
        a cdb_object_id (e.g. "resolved" oids).
    :type ordered_oids: list of
        `cs.pcs.projects.project_structure.util.PCS_LEVEL`

    :param readable_oids: cdb_object_ids the current user has read access
        for
    :type readable_oids: list of str

    :returns: Filtered ``ordered_oids`` - only entries found in
        ``readable_oids``. Subtrees of non-readable entries are also
        filtered out.
    :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`

    :raises AttributeError: if any element in `ordered_oids` is missing
        either attribute "level" or "cdb_object_id".
    """
    result = []
    skip_level = None

    for oid in ordered_oids:
        if skip_level is None or skip_level >= oid.level:
            if oid.cdb_object_id in readable_oids:
                result.append(oid)
                skip_level = None
            else:
                # if an oid is not readable, also filter out its subtree,
                # e.g. continue with the next entry of same or lower level
                skip_level = oid.level

    return result


def _get_oid_query_str(oids, attr=None):
    """
    :param oids: List of cdb_object_id values.
    :type oids: list

    :param attr: Attribute name to use (defaults to "cdb_object_id").
    :type attr: str

    :returns: SQL WHERE clause for given values, e.g.
        ``"cdb_object_id IN ('a', 'b', 'c')"``.
    :rtype: str

    :raises TypeError: if ``oids`` is not iterable or any cdb_object_id is
        neither ``None`` nor a ``str``.
    """
    if attr is None:
        attr = "cdb_object_id"

    return format_in_condition(attr, oids)


def _get_oids_by_relation(pcs_levels):
    """
    :param pcs_levels: cdb_object_ids and database table names of objects.
    :type pcs_levels: list of
        `cs.pcs.projects.project_structure.util.PCS_LEVEL`

    :returns: list of cdb_object_ids grouped by database table names
    :rtype: list of tuple(str, list)

    :raises ValueError: if
        - `pcs_levels` or one of its values is not iterable,
        - any value contains less than 2 value.
    """
    oids_by_relation = []
    try:
        sorted_oids = sorted(pcs_levels, key=itemgetter(1))
    except TypeError as exc:
        raise ValueError(
            f"value (or one of its values) is not iterable: '{pcs_levels}'"
        ) from exc
    except IndexError as exc:
        raise ValueError(
            f"each value must contain at least 2 values: '{pcs_levels}'"
        ) from exc

    for relation, oids in groupby(sorted_oids, itemgetter(1)):
        oids_by_relation.append((relation, [o[0] for o in oids]))

    return oids_by_relation


def get_table_for_oids(object_ids):
    """
    :param object_ids: List of `cdb_object_id` values to get table names for.
    :type object_ids: list of str

    :returns: List of tuples containing `cdb_object_id` values
        and their respective database table names.
    :rtype: list of `PCS_LEVEL`

    .. note ::
       Read access is not checked, only for internal use.
    """
    if not object_ids:
        return []
    query_str = f"SELECT * FROM cdb_object WHERE {_get_oid_query_str(object_ids, 'id')}"
    rset = sqlapi.RecordSet2(sql=query_str)
    return [PCS_LEVEL(record.id, record.relation, 0) for record in rset]


def validate_dtag(classname, label, failsafe=True):
    """
    validate fields in description tag labels

    :param classname: Name of the class.
    :type classname: str

    :param label: label to get the fields from.
    :type label: str

    :param failsafe: if True invalid field placeholders will be replaced
        with "<field_name>", else an error is raised
    :type failsafe: bool

    :returns: the label in the current language and the fields required for placeholders.
        If failsafe is True, placeholders for invalid fields are replaced with
        static strings "<field_name>".
    :rtype: tuple of (label, fields)

    :raises ErrorMessage: if failsafe is False and the label contains
        any placeholders for invalid fields.
    """
    cdef = CDBClassDef(classname)
    table = ddl.Table(cdef.getPrimaryTable())
    fields = DTAG_PATTERN.findall(label)
    missing = [field for field in fields if not table.hasColumn(field)]
    if missing:
        if failsafe:
            new_label = None
            for m in missing:
                new_label = (
                    label.replace("{" + m + "}", "<" + m + ">")
                    if new_label is None
                    else new_label.replace("{" + m + "}", "<" + m + ">")
                )
                fields.remove(m)
            return new_label, fields
        else:
            raise util.ErrorMessage(
                "cdbpcs_project_structure_dtag_invalid", ", ".join(missing)
            )
    return label, fields


@sig.connect(gui.Label, "create", "pre")
@sig.connect(gui.Label, "copy", "pre")
@sig.connect(gui.Label, "modify", "pre")
def check_project_structure_dtag(self, ctx):
    if self.ausgabe_label.startswith(DTAG_PREFIX):
        classname = self.ausgabe_label.split(DTAG_PREFIX)[-1]
        for label in self.GetLocalizedValues("txt").values():
            validate_dtag(classname, label, False)


@lru_cache()
def get_project_structure_dtag(table_name):
    """
    resolve project structure description tag for given table
    """
    label = util.get_label(f"{DTAG_PREFIX}{table_name}")
    [label, fields] = validate_dtag(table_name, label)

    return label, fields


def rest_id2rest_key(rest_id):
    """
    :param rest_id: Absolute or relative REST ID of a project or task
    :type rest_id: str

    :returns: The REST key of ``rest_id``
        and a flag indicating whether its REST name is "project_task".
    :rtype: tuple of str, bool
    """
    url_parts = rest_id.split("/")
    rest_key = url_parts.pop()
    rest_name = url_parts.pop()
    is_task = rest_name == "project_task"
    return rest_key, is_task


def obj2rest_id(base_url, obj):
    rest_name = rest_name_for_class_name(obj.GetClassname())
    return f"{base_url}/{rest_name}/{rest_key(obj)}"


def fit_text(text, postfix, max_length):
    """
    :type text: str
    :type postfix: str
    :type max_length: int

    :returns: ``text`` and ``postfix`` concatenated.
        If the resulting string would be longer than ``max_length``,
        ``text`` is shortened accordingly and an ellipsis ("...")
        is added in between shortened ``text`` and ``postfix`` so
        ``max_length`` is filled.
    :rtype: str

    :raises ValueError: if resulting text does not fit
        into ``max_length`` characters
    """
    postfix_length = len(postfix)

    if (len(text) + postfix_length) <= max_length:
        pattern = "{}{}"
    else:
        text_length = max_length - postfix_length - len(ELLIPSIS)
        if text_length < 0:
            raise ValueError(
                f"cannot fit text into {max_length} chars: '{text}{postfix}'"
            )
        pattern = f"{{}}{ELLIPSIS}{{}}"
        text = text[:text_length]

    return pattern.format(text, postfix)


def get_copy_name(original_name, existing_names, max_length):
    """
    :type original_name: str
    :type existing_names: list of str

    :type max_length: Return value can have at most this many chars
    :type max_length: int

    :returns: New name based on ``original_name`` with next copy postfix
        unique among ``existing names``.
        Copy postfixes are numbered, counting up for every existing name
        starting with the same characters
        (trailing ellipsis matches any number of characters).
    :rtype: str
    """
    postfix_i18n = util.get_label("cdbpcs_copy_postfix")

    # simple pattern is used to separate the name from any copy postfix
    simple_pattern = f" ({postfix_i18n}"

    # pattern finds existing names with copy postfixes:
    # "foo (Copy)", "foo (Copy 2)" and so on
    # (the first copy is not numbered)
    pattern = re.compile(
        # pylint: disable-next=consider-using-f-string
        r"(?P<text>.*?)({})? \({}(?P<counter>\s\d+)\)$".format(
            re.escape(ELLIPSIS), re.escape(postfix_i18n)
        )
    )

    parts = original_name.rsplit(simple_pattern, 1)

    max_counter = -1  # -1 = no postfix needed

    for name in existing_names:
        existing_parts = name.rsplit(simple_pattern, 1)

        if len(existing_parts) != 2:
            if original_name.startswith(name):
                max_counter = max(0, max_counter)
            continue

        match = pattern.search(name)
        if match:
            values = match.groupdict()
            text = values["text"]

            if original_name.startswith(text):
                max_counter = max(max_counter, int(values["counter"]))
        else:  # first copy postfix without a counter
            max_counter = max(1, max_counter)

    if max_counter == -1:
        return fit_text(parts[0], "", max_length)

    next_counter = f" {max_counter + 1}" if max_counter > 0 else ""
    new_postfix = f" ({postfix_i18n}{next_counter})"

    return fit_text(parts[0], new_postfix, max_length)
