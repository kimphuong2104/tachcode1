#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from collections import defaultdict

from cdb import CADDOK, sqlapi
from cdb.platform.olc import StatusInfo
from cdbwrapc import CDBClassDef
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common.rest_objects import get_restlinks_in_batch
from cs.pcs.projects.common.webdata.util import get_rest_key, get_sql_condition
from cs.pcs.projects.project_structure import util
from cs.pcs.timeschedule.web.mapping import ColumnDefinition
from cs.pcs.timeschedule.web.models.base_model import ScheduleBaseModel
from cs.pcs.timeschedule.web.models.helpers import (
    PCS_OID,
    get_node,
    get_oids_by_relation,
    get_pcs_oids,
)
from cs.pcs.timeschedule.web.rest_objects import get_rest_objects

SUBJECT_LINK_PATTERNS = {
    "Person": {
        "uiLink": "/info/person/{}",
        "iconLink": "/resources/icons/byname/cdb_person",
    },
    "Common Role": {
        "uiLink": "",
        "iconLink": "/resources/icons/byname/cdb_role",
    },
    "PCS Role": {
        "uiLink": "",
        "iconLink": "/resources/icons/byname/cdb_role",
    },
}


class StatusInfoDict(dict):
    """deeply-nested alternative to defaultdict"""

    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


# shared DataModel for time and resource schedules
class DataModel(ScheduleBaseModel):
    def __init__(self, context_object_id):
        ScheduleBaseModel.__init__(self, context_object_id)
        self.columns = ColumnDefinition.ByGroup(self.column_group)

    def _get_value_from_payload(self, payload, key):
        """
        :param payload: json payload to retrieve value from
        :type payload: dict

        :param key: key, the value is stored under in the payload
        :type key: string

        :raises: HTTPBadRequest if payload or key do not match their expected
                 types or key is not in payload

        :returns: retrieved value from the payload
        :rtype: any
        """

        def raise_bad_request(key, payload):
            logging.error(
                "invalid key '%s' in request payload: %s",
                key,
                payload,
            )
            raise HTTPBadRequest

        if not (isinstance(payload, dict) and isinstance(key, str)):
            raise_bad_request(key, payload)
        try:
            value = payload[key]
        except KeyError:
            raise_bad_request(key, payload)
        return value

    def _get_plugins(self, request):
        """
        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Plugin information for the frontend.
        :rtype: list of dict
        """
        result = []

        for plugin in self.plugins.values():
            classdef = CDBClassDef(plugin.classname)
            result.append(
                {
                    "classname": plugin.classname,
                    "allow_pinning": getattr(plugin, "allow_pinning", False),
                    "icon": classdef.getIconId(),
                    "title": classdef.getTitle(),
                    "catalog": plugin.GetCatalogConfig(
                        self.context_object,
                        request,
                    ),
                }
            )

        return result

    def get_plugins(self, request):
        """
        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: REST links of time schedule elements and plugin information
            for the frontend.
        :rtype: dict
        """
        return {
            "plugins": self._get_plugins(request),
        }

    def _get_pinned_oids(self):
        """
        :returns: cdb_object_id and database table name of all content objects
            of ``self.context_object``.
        :rtype: list of `helpers.PCS_OID`

        :raises AttributeError: if records are missing either the ``id`` or
            ``relation`` field.
        """
        alias = "" if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE else "AS"
        query = f"""
            SELECT o.id, o.relation
                FROM cdb_object {alias} o
            LEFT OUTER JOIN {self.content_table} {alias} c
                ON o.id = c.content_oid
            WHERE c.view_oid='{self.context_object_id}'
            ORDER BY c.position
            """
        return [
            PCS_OID(record.id, record.relation)
            for record in sqlapi.RecordSet2(sql=query)
        ]

    def get_row(self, row_number, oid, rest_link, pinned_oid, parent_oid):
        """
        :param row_number: Row number in the parent table.
        :type row_number: int

        :param oid: cdb_object_id of the objects this row represents.
        :type oid: str

        :param rest_link: REST URL of the object this row represents.
        :type rest_link: str

        :param pinned_oid: cdb_object_id of the top most pinned parent object of this row.
        :type oid: str

        :param parent_oid: cdb_object_id of the direct parent object of this row.
            Only needed for resource schedule
        :type oid: str

        :returns: Row data to be JSON-serialized.
        :rtype: dict
        """
        return {
            "id": oid + "@" + pinned_oid
            if not parent_oid
            else oid + "@" + parent_oid + "@" + pinned_oid,  # row node id
            "rowNumber": row_number,
            "columns": [],
            # restLink is required for loading objects, operations, selection
            "restLink": rest_link,
        }

    def _resolve_structure(self, pinned_oids, request):
        """
        For each content object in ``pinned_oids``, use the matching plugin to
        resolve the content object's structure.

        :param pinned_oids: cdb_object_id and database table name of content
            objects to resolve.
        :type pinned_oids: list of `helpers.PCS_OID`

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: cdb_object_id, table name and level in structure of each
            resolved content object (in order of appearance).
        :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :raises TypeError: if ``pinned_oids`` is not iterable or plugin does
            not return only iterable values.
        :raises ValueError: if any value in ``pinned_oids`` does not contain
            exactly 2 values or plugin does not return exactly 2 values.
        """
        resolved_levels = []

        for pinned_oid, relation in pinned_oids:
            plugin = self.plugins.get(relation, None)

            if plugin:
                ts_levels = plugin.ResolveStructure(pinned_oid, request)
                resolved_levels += ts_levels
            else:
                logging.warning("no plugin found for relation '%s'", relation)

        return resolved_levels

    def _get_record_tuples(self, resolved_oids):
        """
        :param resolved_oids: cdb_object_ids and database table names of
            objects to query database for.
        :type resolved_oids: list of `helpers.PCS_OID`

        :returns: table names and records for objects identified by
            ``resolved_oids``.
            **Only includes records the current user has read access for**
        :rtype: list of `cs.pcs.projects.project_structure.util.PCS_RECORD`
        """
        oids_by_relation = get_oids_by_relation(resolved_oids)

        result = []

        for relation, oids in oids_by_relation:
            result.extend(self.plugins[relation].ResolveRecords(oids))

        return result

    def _get_readable(self, ordered_oids, readable_oids):
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

                    # ignore if `oid` is not a `PCS_LEVEL` but `PCS_OID` object
                    # which happens in flat structures like "get_schedule_elements"
                    skip_level = getattr(oid, "level", None)

        return result

    # pylint: disable=too-many-locals
    def _get_data(self, resolved, ts_records, request):
        """
        :param resolved: cdb_object_id, table name and level of objects.
        :type resolved: list of
            `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :param ts_records: database table name and record of resolved
            content objects.
        :type ts_records: list of
            `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: JSON-serializable rows and tree nodes and
            a dictionary for the mapping of content objects with
            baseline objects.
        :rtype: tuple of (list of dict, list of dict, dict)

        :raises KeyError: if rest link cannot be generated for any object.

        .. warning ::

            See
            ``cs.pcs.timeschedule.web.rest_objects.get_restlinks_in_batch``
            for other possible exceptions.

        """
        rest_links = get_restlinks_in_batch(ts_records, request)
        collapsed = self.get_user_settings(
            self.context_object_id,
        ).get("collapsedRows", {})
        readable = self._get_readable(resolved, rest_links)

        rows = []
        flat_nodes = []
        levels = []
        relevant_baselines = {}
        pinned_oid = ""
        node_ids_expansion = {}
        if "elements" in request.path:
            treeview_state = request.json["treeViewState"]
            for row_number in treeview_state:
                node_id = treeview_state[row_number]["id"]
                node_ids_expansion[node_id] = treeview_state[row_number]["expanded"]

        last_demand_alloc_parent_oid = (
            readable[0].cdb_object_id if len(readable) > 0 else None
        )
        for row_number, ts_level in enumerate(readable):
            oid = ts_level.cdb_object_id
            level = int(ts_level.level)
            if level == 0:
                pinned_oid = oid
            parent_oid = None
            if (
                ts_level.table_name in ["cdbpcs_prj_alloc", "cdbpcs_prj_demand"]
                and ts_level.level > 0
            ):
                if ts_level.level > levels[-1]:
                    last_demand_alloc_parent_oid = readable[
                        row_number - 1
                    ].cdb_object_id
                parent_oid = last_demand_alloc_parent_oid
            row = self.get_row(row_number, oid, rest_links[oid], pinned_oid, parent_oid)
            node_id = row.get("id")
            node = get_node(
                row_number,
                self._get_is_expanded(node_id, node_ids_expansion, collapsed),
                node_id,  # row node_id
            )
            rows.append(row)
            flat_nodes.append(node)
            levels.append(level)
            if (
                self.with_baselines
                and hasattr(ts_level, "additional_data")
                and ts_level.additional_data
            ):
                relevant_baselines[oid] = (
                    ts_level.table_name,
                    ts_level.additional_data,
                )

        tree_nodes = util.get_tree_nodes(flat_nodes, levels)
        return rows, tree_nodes, relevant_baselines

    def _get_baseline_data(self, relevant_baselines, request):
        """
        Resolves baseline data objects and creates a mapping of content
        objects with their baseline counterparts.

        :param relevant_baselines: key value pair where key is the object ID of
            the content and value is the object ID of its baseline counterpart.
            Not all content objects will have a baseline.
        :type relevant_baselines: dict

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: resolved records of the baseline objects and key value mapping of
            content objects with baseline objects.
        :rtype: tuple
        """
        rec_oids = [
            (oid, table_name) for table_name, oid in relevant_baselines.values()
        ]
        baseline_records = self._get_record_tuples(rec_oids)

        rest_links = get_restlinks_in_batch(baseline_records, request)
        baseline_mapping = {k: rest_links[v[1]] for k, v in relevant_baselines.items()}
        return baseline_records, baseline_mapping

    def _get_is_expanded(self, node_id, node_ids_expansion, collapsed):

        if node_id in collapsed:
            return not collapsed.get(node_id)

        if len(node_ids_expansion) != 0:
            if node_id not in node_ids_expansion:
                return False
            else:
                return (node_ids_expansion[node_id],)
        return True

    def get_data(self, request):
        """
        Get application data:

        1. Query content object IDs for context time schedule ordered by
           position. Keep list of oid and database table name tuples.
        2. For each content object, resolve its structure using the matching
           plugin. Missing plugins will raise exceptions.
           Also keep dict of parent object IDs by child object ID.
        3. Query database to get records for all resolved object IDs where
           "read" access is granted.
        4. Map object IDs to flat rows and calculate tree nodes as a nested
           structure.
        5. Include full data of the first ``self.first_page_size``
           visible objects.

        .. warning ::

            Because ``sqlapi.Record`` objects are used instead of higher-level
            APIs like ``cdb.objects``, make sure to provide plugins for all
            object classes usable as time schedule contents.

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: data for frontend including flat rows, nested tree nodes,
            flat relship data and full objects for some or all rows.
        :rtype: dict

        :raises ValueError: if either ``_resolve_structure`` or ``_get_data``
            do not return exactly 2 values.
        :raises TypeError: if ``_get_full_data_first_page`` does not return an
            iterable.

        .. warning ::

            For other possible exceptions, also see

            - ``_get_pinned_oids``,
            - ``_resolve_structure``,
            - ``_get_record_tuples``,
            - ``_get_data``,
            - ``_get_baseline_data`` and
            - ``_get_full_data_first_page``.

        """

        pinned_oids = self._get_pinned_oids()
        ts_levels = self._resolve_structure(pinned_oids, request)
        ts_records = self._get_record_tuples(ts_levels)
        rows, tree_nodes, relevant_baselines = self._get_data(
            ts_levels, ts_records, request
        )

        result = {
            "error": False,
            "rows": rows,
            "treeNodes": tree_nodes,
            "plugins": self._get_plugins(request),
        }

        if self.with_baselines:
            bl_records, bl_mapping = self._get_baseline_data(
                relevant_baselines, request
            )
            result["baselineMapping"] = bl_mapping
        else:
            bl_records = []

        result.update(
            self._get_full_data_first_page(
                tree_nodes, ts_records, bl_records, relevant_baselines, request
            )
        )

        extension = getattr(self.context_object, "schedule_get_data", None)
        if extension:
            result.update(extension(result, request))

        return result

    def _get_full_data_first_page(
        self, tree_nodes, ts_records, bl_records, relevant_baselines, request
    ):
        """
        :param tree_nodes: Nodes to process
        :type tree_nodes: list of dict

        :param ts_records: database table name and record of resolved
            content objects.
        :type ts_records: tuple of
            `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :param bl_records: database table name and record of resolved
            baseline objects.
        :type bl_records: tuple of
            `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :param relevant_baselines: key value pair where key is the object ID of
            the content and value is the object ID of its baseline counterpart.
            Not all content objects will have a baseline.
        :type relevant_baselines: dict

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Full data of initially visible objects.
        :rtype: dict

        :raises TypeError: if ``ts_records`` is not iterable.
        :raises ValueError: if ``ts_records`` values do not contain exactly
            2 values each.
        :raises AttributeError: if second value of any record tuple is missing
            the attribute "cdb_object_id".

        .. warning ::

            For other possible exceptions, also see

            - ``util.get_first_nodes`` and
            - ``get_full_data``.

        """
        records_by_oid = {ts_rec.record.cdb_object_id: ts_rec for ts_rec in ts_records}

        initially_visible_oids = (
            util.get_first_nodes(
                tree_nodes,
                self.first_page_size,
            )
            if self.first_page_size
            else records_by_oid.keys()
        )

        bl_records_by_oid = {
            bl_rec.record.cdb_object_id: bl_rec for bl_rec in bl_records
        }

        initially_visible_objs = [
            records_by_oid[oid]
            for oid in list(records_by_oid)
            if oid in initially_visible_oids
        ]

        initially_visible_bl_objs = [
            bl_records_by_oid[relevant_baselines[oid][1]]
            for oid in relevant_baselines.keys()
            if oid in initially_visible_oids
        ]

        return self.get_full_data(
            initially_visible_oids,
            None,
            initially_visible_objs,
            initially_visible_bl_objs,
            request,
        )

    def _get_rest_objects(self, resolved, ts_records, request):
        """
        :param resolved: cdb_object_id, table name and level of objects.
        :type resolved: list of
            `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :param ts_records: database table name and record of resolved
            content objects. If ``None``, tuples are loaded from database
            using ``resolved_oids`` first.
        :type ts_records: tuple of
            `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Rest objects and status information.
        :rtype: dict

        :raises KeyError: if plugin for any record's relation is missing.
        :raises TypeError: if ``ts_records`` is not ``None`` and not
            iterable.
        :raises ValueError: if any record tuple does not contain exactly 2
            values.

        .. warning ::

            For other possible exceptions, also see

            - ``_get_record_tuples``,
            - ``add_status_info`` and
            - ``get_rest_objects``.

        """
        if ts_records is None:
            ts_records = self._get_record_tuples(resolved)

        status_info = StatusInfoDict()
        project_pkeys = set()

        for relation, record in ts_records:
            self.add_status_info(
                status_info,
                self.plugins[relation],
                record,
            )
            pid = record.get("cdb_project_id", None)
            if pid:
                bid = record.get("ce_baseline_id", "")
                # projectNames contains projects of pinned elements
                # only include non-baseline projects
                if bid == "":
                    project_pkeys.add((pid, bid))

        return {
            "objects": get_rest_objects(
                self.plugins, self.column_group, ts_records, request
            ),
            "status": status_info,
            "projectNames": self._get_project_names(project_pkeys),
        }

    def get_full_data(self, oids, resolved, ts_records, bl_records, request):
        """
        :param oids: cdb_object_ids to get data for.
        :type oids: list of str

        :param resolved: cdb_object_id, table name and level of objects.
            If falsy and ``ts_records`` is ``None``,
            these will be calculated based on ``oids``.
        :type resolved: list of
            `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :param ts_records: database table name and record of resolved
            content objects. If ``None``, records will be loaded before
            generating result.
        :type ts_records: tuple of
            `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :param bl_records: database table name and record of resolved
            baseline objects.
        :type bl_records: tuple of
            `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: JSON-serializable data for the frontend.
        :rtype: dict
        """
        from cs.pcs.timeschedule.web.models.elements_model import ElementsModel

        if ts_records is None and not resolved:
            resolved = get_pcs_oids(oids)

        result = self._get_rest_objects(resolved, ts_records, request)

        if self.with_baselines:
            result.update(
                {
                    "bl_objects": get_rest_objects(
                        self.plugins, self.column_group, bl_records, request
                    ),
                    "status": self._add_status_info(bl_records, result["status"]),
                }
            )

        EM = ElementsModel(self.context_object_id)
        result.update(
            {
                "subjects": self._get_subjects(result["objects"]),
                "elements": ElementsModel.get_schedule_elements(EM, request),
                "project_ids_by_elements": ElementsModel.get_schedule_project_ids(
                    EM, request
                ),
            }
        )

        extension = getattr(self.context_object, "schedule_get_full_data", None)
        if extension:
            result.update(extension(oids, request))

        return result

    def _add_status_info(self, bl_records, status_info):
        """
        Resolves JSON-serializable status information for given ``baseline record``
        and adds it to ``status_info``.

        :param status_info: aggregated status info indexed by classname,
            and status ID.
            Will be mutated with resolved status info for given input.
        :type status_info: dict

        :param bl_record: record of the baseline object to get information for.
        :type record: cdb.sqlapi.Record
        """
        if bl_records:
            for relation, record in bl_records:
                self.add_status_info(
                    status_info,
                    self.plugins[relation],
                    record,
                )
        return status_info

    @staticmethod
    def add_status_info(status_info, plugin, record):
        """
        Resolves JSON-serializable status information for given ``record``
        and adds it to ``status_info``.

        :param status_info: aggregated status info indexed by classname,
            and status ID.
            Will be mutated with resolved status info for given input.
        :type status_info: dict

        :param plugin: plugin to resolve information for record.
        :type plugin: subclass of
            ``cs.pcs.timeschedule.web.plugins.TimeschedulePlugin``

        :param record: record of the object to get information for.
        :type record: cdb.sqlapi.Record

        :raises RuntimeError: if plugin is invalid.
        """
        if not plugin.has_olc:
            return True

        try:
            kind = plugin.GetObjectKind(record)
        except (AttributeError, TypeError) as exc:
            msg = f"invalid plugin: {plugin}"
            logging.exception(msg)
            raise RuntimeError(msg) from exc

        status = getattr(record, plugin.status_attr, None)

        if status is None:
            return None

        try:
            info = StatusInfo(kind, status)
        except (TypeError, ValueError, AttributeError):
            msg = f"invalid status: {kind}, {record}"
            logging.exception(msg)
            info = None

        if info:
            status_info[kind][status] = {
                "label": info.getLabel(),
                "color": info.getCSSColor(),
            }

    def _get_project_names(self, project_pkeys):
        """
        :param project_pkeys: project primary key tuples to resolve names for
        :type project_pkeys: set of tuple

        :returns: Names of projects indexed by their cdb_project_id
        :rtype: dict
        """

        KEY_NAMES = ["cdb_project_id", "ce_baseline_id"]
        pkeys = list(project_pkeys.difference([None]))
        return {
            get_rest_key(x, KEY_NAMES): x.project_name
            for x in sqlapi.RecordSet2(
                "cdbpcs_project",
                get_sql_condition("cdbpcs_project", KEY_NAMES, pkeys),
                access="read",
            )
        }

    def _get_subjects(self, rest_objs):
        """
        :param rest_objs: rest objects to read subject_id and subject_type
            values from.
        :type rest_objs: list of dict

        :returns: mapped subjects indexed by subject_id and subject_type for
            all value combinations in ``rest_objs``. A mapped subject consists
            of a "title" (subject's mapped name in current session language),
            a "uiLink" and an "iconLink" (both taken from
            ``SUBJECT_LINK_PATTERNS``).
        :rtype: dict of dict

        .. rubric :: Example return value for language "en"

        .. code-block :: python

            {
                "Person": {
                    "caddok": {
                        "uiLink": "/info/person/caddok",
                        "iconLink": "/resources/icons/byname/cdb_person",
                        "title": "Administrator",
                    },
                },
                "Common Role": {
                    "vip": {
                        "uiLink": "",
                        "iconLink": "/resources/icons/byname/cdb_role",
                        "title": "Very Important People",
                    },
                },
                "PCS Role": {
                    "Projektleiter": {
                        "uiLink": "",
                        "iconLink": "/resources/icons/byname/cdb_role",
                        "title": "Project Manager",
                    },
                },
            }

        :raises TypeError: if ``rest_objs`` is not iterable.
        """
        if not rest_objs:
            return {}

        result = defaultdict(dict)
        query = " OR ".join(
            f"(subject_id = '{sid}' AND subject_type = '{stype}')"
            for sid, stype in set(
                (obj.get("subject_id", ""), obj.get("subject_type", ""))
                for obj in rest_objs
            )
        )
        rset = sqlapi.RecordSet2(
            sql="SELECT DISTINCT "
            f"subject_id, subject_type, subject_name_{CADDOK.ISOLANG} AS subject_name "
            "FROM pcs_sharing_subjects_all "
            f"WHERE {query} "
        )

        for rec in rset:
            subject = {"title": rec.subject_name}
            patterns = SUBJECT_LINK_PATTERNS.get(rec.subject_type, None)
            if patterns:
                subject.update(
                    {
                        key: value.format(rec.subject_id)
                        for key, value in patterns.items()
                    }
                )
            result[rec.subject_type][rec.subject_id] = subject

        return result

    def schedule_get_related_names(self, request):
        # timeschedule-specific
        # raise Error, when called with other context
        if self.context_object.GetClassname() != "cdbpcs_time_schedule":
            raise HTTPBadRequest
        project_pid = self._get_value_from_payload(request.json, "projectID")
        project_bid = ""
        task_oid = self._get_value_from_payload(request.json, "taskOID")
        project_name_dict = self._get_project_names(set([(project_pid, project_bid)]))
        task_dict = get_rest_objects(
            self.plugins,
            self.column_group,
            self._get_record_tuples(get_pcs_oids([task_oid])),
            request,
        )
        return {"projectName": project_name_dict, "task": task_dict}
