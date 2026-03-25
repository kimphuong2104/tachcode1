#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import logging
from urllib import parse

from cdb.objects import ByID
from cdb.platform.mom.relships import Relship
from cdb.util import get_label
from cs.platform.web.rest.support import values_from_rest_key
from cs.platform.web.root import get_v1
from cs.platform.web.root.main import _get_dummy_request
from webob.exc import HTTPNotFound

from cs.pcs.checklists import Checklist
from cs.pcs.checklists.web.related import query_objects
from cs.pcs.projects.common.webdata.util import get_rest_key


def _get_rship_label(relship_id):
    relship = Relship.ByKeys(name=relship_id)
    label = get_label(relship.label).rsplit("/")[-1]
    return label


def _get_collection_app(request):
    """identify app to calculate links with"""
    if request is None:
        request = _get_dummy_request()
    return get_v1(request).child("collection")


def get_rest_object(obj, request, collection_app):
    """return the full REST API representation of obj"""
    if not obj:
        return None

    result = request.view(
        obj,
        app=collection_app,
        # use relship-target over default view, because
        # resolving relships is _expensive_
        # this also resolves long texts
        name="relship-target",
    )
    return result


def get_rest_url(url, rest_name, rest_key):
    scheme, netloc, _, _, _ = parse.urlsplit(url)
    return f"{scheme}://{netloc}/api/v1/collection/{rest_name}/{rest_key}"


def get_item_rest_url(item):
    rest_key = get_rest_key(item, ["cdb_project_id", "checklist_id"])
    return get_rest_url(item["@id"], "checklist", rest_key)


def get_rule_rest_url(rule, ref):
    rest_key = get_rest_key(ref, ["cdb_project_id", "checklist_id"])
    return get_rest_url(rule["@id"], "checklist", rest_key)


class RelatedChecklistsStructureModel:
    def __init__(self, object_id):
        """
        raises `HTTPNotFound` if project identified by `cdb_project_id`
        does not exist or is not readable
        """
        obj = ByID(object_id)

        if not obj or not obj.CheckAccess("read"):
            logging.error(
                "project or project task not found or not readable: '%s'",
                object_id,
            )
            raise HTTPNotFound

        self.cdb_object_id = object_id
        self.project_id = obj.cdb_project_id
        self.task_id = getattr(obj, "task_id", None)
        self.checklist_id = getattr(obj, "checklist_id", None)

    def resolve_structure(self, request):
        """
        Retrieves checklists, checklist items and work objects assigned
        to the task identified by `self.project_id` and `self.task_id`.
        Data is fetched with optimized SQL queries, access is not checked.

        "checklists" includes app-specific data for the RelatedChecklists component.
            Represents the structure of a checklist with subelements
        "objects" contains the REST objects
        "labels" contains internationalized labels used as relationship captions in the frontend
        """
        result = resolve_structure(
            self.cdb_object_id,
            self.project_id,
            self.task_id,
            self.checklist_id,
            request,
        )
        return {
            "checklists": result["checklists"],
            "objects": result["objects"],
            "labels": {
                "items": _get_rship_label("cdbpcs_checklist2cl_items"),
                "workobjects": _get_rship_label("cdbpcs_deliv2rule"),
            },
            "tasks_checklists_list": result["tasks_checklists_list"],
        }


def resolve_structure(
    cdb_object_id, cdb_project_id, task_id, checklist_id, request=None
):
    checklists = query_objects.query_checklists(cdb_project_id, task_id, checklist_id)
    return resolve_structure_results(checklists, cdb_object_id, request)


def resolve_structure_results(checklists, cdb_object_id, request):
    response = {
        "checklists": {},
        "objects": [],
        "tasks_checklists_list": {},
    }
    checklist_list = []

    def _add_to_objects(obj):
        response["objects"].append(obj)

    if request is None:
        request = _get_dummy_request()

    app = _get_collection_app(request=request)

    for checklist in checklists:
        rest_cl = get_rest_object(checklist, request, app)
        response["checklists"][rest_cl["@id"]] = {
            "@id": rest_cl["@id"],
            "type": rest_cl["type"],
            "items": [],
            "workobjects": [],
            "content_fetched": False,
        }
        checklist_list.append(rest_cl["@id"])
        _add_to_objects(rest_cl)
    response["tasks_checklists_list"][cdb_object_id] = checklist_list

    return response


class RelatedChecklistsContentModel:
    def __init__(self):
        self.checklist_objs = []

    def resolve(self, request, rest_keys):
        for rest_key in rest_keys:
            keys = values_from_rest_key(rest_key)
            checklist_obj = Checklist.ByKeys(keys[0], keys[1])

            if not checklist_obj or not checklist_obj.CheckAccess("read"):
                logging.error(
                    "no checklist with the following rest_key found: '%s'",
                    rest_key,
                )
                raise HTTPNotFound
            self.checklist_objs.append(checklist_obj)

        result = resolve_content(
            self.checklist_objs,
            request,
        )
        return {
            "checklists": result["checklists"],
            "objects": result["objects"],
        }


def resolve_content(checklist_objs, request=None):
    items = query_objects.query_items(
        checklist_objs[0].cdb_project_id, [cl.checklist_id for cl in checklist_objs]
    )
    rules = query_objects.query_rules(
        checklist_objs[0].cdb_project_id, [cl.checklist_id for cl in checklist_objs]
    )
    return resolve_content_results(checklist_objs, items, rules, request)


def resolve_content_results(checklist_objs, items, rules, request):
    response = {
        "checklists": {},
        "objects": [],
    }
    if request is None:
        request = _get_dummy_request()

    app = _get_collection_app(request=request)
    rest_cls = [
        get_rest_object(checklist_obj, request, app) for checklist_obj in checklist_objs
    ]
    for rest_cl in rest_cls:
        response["checklists"][rest_cl["@id"]] = {
            "@id": rest_cl["@id"],
            "type": rest_cl["type"],
            "items": [],
            "workobjects": [],
            "content_fetched": True,
        }

    def _add_to_checklist(restkey, object_type, obj):
        response["checklists"][restkey][object_type].append(obj["@id"])

    for item in items:
        cl_id = [x for x in rest_cls if x["checklist_id"] == item["checklist_id"]][0][
            "@id"
        ]
        rest_item = get_rest_object(item, request, app)
        _add_to_checklist(
            cl_id,
            "items",
            rest_item,
        )
        response["objects"].append(rest_item)

    if rules:
        for rule in rules["rules"]:
            rest_rule = get_rest_object(rule, request, app)

            for ref in rules["refs"].get(rule.name, []):
                cl_id = [
                    x for x in rest_cls if x["checklist_id"] == ref["checklist_id"]
                ][0]["@id"]
                _add_to_checklist(
                    cl_id,
                    "workobjects",
                    rest_rule,
                )
            response["objects"].append(rest_rule)

    return response


class RelatedChecklistsRefreshModel:
    def __init__(self, object_id):
        """
        raises `HTTPNotFound` if project identified by `object_id`
        does not exist or is not readable. The object can only be either
        project, project_task, checklist
        """
        obj = ByID(object_id)

        if not obj or not obj.CheckAccess("read"):
            logging.error(
                "project, project task or checklist not found or not readable: '%s'",
                object_id,
            )
            raise HTTPNotFound

        self.cdb_object_id = object_id
        self.project_id = obj.cdb_project_id
        self.task_id = getattr(obj, "task_id", None)
        self.checklist_id = getattr(obj, "checklist_id", None)

    def resolve(self, request, expanded_checklists=None):
        result = resolve_refresh(
            self.cdb_object_id,
            self.project_id,
            self.task_id,
            self.checklist_id,
            expanded_checklists,
            request,
        )
        return {
            "checklists": result["checklists"],
            "objects": result["objects"],
            "labels": {
                "items": _get_rship_label("cdbpcs_checklist2cl_items"),
                "workobjects": _get_rship_label("cdbpcs_deliv2rule"),
            },
            "tasks_checklists_list": result["tasks_checklists_list"],
        }


def resolve_refresh(
    cdb_object_id,
    cdb_project_id,
    task_id,
    checklist_id,
    expanded_checklists,
    request=None,
):
    checklists = query_objects.query_checklists(cdb_project_id, task_id, checklist_id)
    items = query_objects.query_items(cdb_project_id, expanded_checklists)
    rules = query_objects.query_rules(cdb_project_id, expanded_checklists)
    return resolve_refresh_results(
        checklists, items, rules, task_id, cdb_object_id, request
    )


def resolve_refresh_results(checklists, items, rules, task_id, cdb_object_id, request):

    if request is None:
        request = _get_dummy_request()

    app = _get_collection_app(request=request)

    response = {
        "checklists": {},
        "objects": [],
        "tasks_checklists_list": {},
    }
    checklist_list = []

    def _add_to_checklist(object_type, checklist_url, obj):
        response["checklists"][checklist_url][object_type].append(obj["@id"])
        response["checklists"][checklist_url]["content_fetched"] = True

    def _add_to_objects(obj):
        response["objects"].append(obj)

    for checklist in checklists:
        rest_cl = get_rest_object(checklist, request, app)
        response["checklists"][rest_cl["@id"]] = {
            "@id": rest_cl["@id"],
            "type": rest_cl["type"],
            "items": [],
            "workobjects": [],
            "content_fetched": False,
        }
        checklist_list.append(rest_cl["@id"])
        _add_to_objects(rest_cl)

    if task_id:
        response["tasks_checklists_list"][cdb_object_id] = checklist_list

    for item in items:
        rest_item = get_rest_object(item, request, app)
        _add_to_checklist(
            "items",
            get_item_rest_url(rest_item),
            rest_item,
        )
        _add_to_objects(rest_item)

    if rules:
        for rule in rules["rules"]:
            rest_rule = get_rest_object(rule, request, app)
            for ref in rules["refs"].get(rule.name, []):
                _add_to_checklist(
                    "workobjects",
                    get_rule_rest_url(rest_rule, ref),
                    rest_rule,
                )
            response["objects"].append(rest_rule)

    return response


def get_item_rest_url(item):
    rest_key = get_rest_key(item, ["cdb_project_id", "checklist_id"])
    return get_rest_url(item["@id"], "checklist", rest_key)


def get_rule_rest_url(rule, ref):
    rest_key = get_rest_key(ref, ["cdb_project_id", "checklist_id"])
    return get_rest_url(rule["@id"], "checklist", rest_key)
