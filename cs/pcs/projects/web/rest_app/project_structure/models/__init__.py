#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import logging

from cdb.fls import get_license
from cs.platform.web.rest.support import values_from_rest_key
from webob.exc import HTTPForbidden, HTTPNotFound

from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects.project_structure import (
    delete_copy,
    get_full_data,
    get_view_class,
    persist_drop,
    resolve,
    resolve_root_object,
)
from cs.pcs.projects.tasks import Task


class StructureModel:
    __first_page_size__ = 100

    def __init__(self, request, view_name, root_rest_key):
        """
        raises `HTTPNotFound` if project identified by `cdb_project_id`
        does not exist or is not readable.
        raises `HTTPForbidden` if the license could not be allocated
        for the given view.
        """
        self.object = resolve_root_object(request, view_name, root_rest_key)
        if not self.object:
            logging.error(
                "object not found or not readable: %s",
                root_rest_key,
            )
            raise HTTPNotFound

        view_class = get_view_class(view_name)
        if not get_license(view_class.LICENSE_FEATURE_ID):
            logging.error(
                "View %s failed to allocate license %s.",
                view_name,
                view_class.LICENSE_FEATURE_ID,
            )
            raise HTTPForbidden

        self.view = view_name

    def resolve(self, request):
        """
        Resolves the structure of `self.project` formatted for `view`.

        :param view: Name of the view to use for resolution.
        :type view: str

        :param subprojects: If ``True``, the project structure is resolved
            recursively including all subrojects.
            If not, subprojects are not part of the resolved structure.
        :type subprojects: bool

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Dict with keys
            - "nodes" containing an adjacency list and
            - "objects" containing full data of the first n nodes
              (where n is `self.__first_page_size__`).
            Full data of the remaining nodes is usually resolved
            in a followup request responded to by `self.resolve_full_data`.
        :rtype: dict
        """
        return resolve(
            self.object.cdb_object_id,
            self.view,
            request,
            self.__first_page_size__,
        )

    def get_full_data(self, object_ids, request):
        """
        :param view: Name of the view to use for resolution.
        :type view: str

        :param object_ids: `cdb_object_id` values to get full data for.
        :type object_ids: list of str

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Full object data indexed by `cdb_object_id`.
        :rtype: dict
        """
        return get_full_data(
            object_ids,
            self.view,
            request,
        )

    def persist_drop(self, target, parent, children, predecessor, is_move):
        """
        :param target: ``@id`` of object to move or copy in structure
        :type target: str

        :param parent: ``@id`` of target's new parent object
        :type parent: str

        :param children: Sorted list of ``@id`` of parent's children
            containing ``target`` in the intended position.
            If ``is_move`` is ``False`` (e.g. the drop intends to copy),
            the copied target is postfixed with
            ``cs.pcs.projects.project_structure.views.TreeView.COPY_POSTFIX``
            to distinguish it from the original.
        :type children: list of str

        :param predecessor: ``@id`` of target's new predecessor.
            Used as a fallback if ``children`` is ``None``
        :type predecessor: str

        :param is_move: ``True`` means the drop is moving the target,
            ``False`` means it's copying the target.
        :type is_move: bool
        """
        return persist_drop(
            target,
            parent,
            children,
            predecessor,
            self.view,
            is_move,
        )

    def delete_copy(self, copy_id):
        """
        :param copy_id: `@id` of copied object to delete
        :type copy_id: str
        """
        return delete_copy(copy_id, self.view)


class StructureURLModel:
    def __init__(self, request, rest_key):
        object_keys = values_from_rest_key(rest_key)
        kwargs = {
            "cdb_project_id": object_keys[0],
            "task_id": object_keys[1],
            "ce_baseline_id": object_keys[2],
        }

        task = get_and_check_object(Task, "read", **kwargs)
        if not task:
            raise HTTPNotFound()
        self.task = task
        self.rest_key = rest_key

    def generate_URL(self, request):
        return Task.generate_project_structure_URL(self.task, request, self.rest_key)
