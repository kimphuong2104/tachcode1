#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import logging

from cdb import sig
from cdb.lru_cache import lru_cache
from cs.platform.web.root.main import _get_dummy_request
from cs.web.components import outlet_config

from cs.pcs.helpers import is_feature_licensed
from cs.pcs.projects.project_structure.views import GET_VIEWS, TreeView, View


def _ensure_request(request):
    if request is None:
        return _get_dummy_request()
    else:
        return request


@lru_cache(maxsize=1)
def get_view_class(view_name):
    return ProjectStructureViews.GetViewClass(view_name)


def resolve_root_object(request, view_name, root_rest_key):
    """
    Resolves the root object for the given view name.
    """
    view_class = get_view_class(view_name)
    view = view_class(root_rest_key, request)
    return view.resolve_root_object(root_rest_key)


def resolve(root_oid, view_name, request=None, first=None):
    """
    :param root_oid: The `cdb_object_id` of the root project to resolve.
    :type root_oid: str

    :param view_name: Name of a registered project structure view.
    :type view_name: str

    :param request: The request sent from the frontend.
        Defaults to a dummy request.
    :type request: morepath.Request

    :param first: Number of nodes to include full data for.
        If less than `first` nodes are found, include data for all of them.
        Defaults to `None`, which includes data of all nodes.
    :type first: int

    :returns: The JSON-serializable resolved structure.
    :rtype: dict (usually, but depends on the specific view)

    :raises KeyError: if `view_name` is not the name of a registered view.
    :raises AttributeError: if resolved view class
        is missing the method `resolve`.

    .. warning ::

        Since views may be implemented anywhere,
        they can be slow, insecure and raise any exception.

        Be sure to know which views are registered in your system
        and that they do not leak secret data.
    """
    request = _ensure_request(request)
    view_class = get_view_class(view_name)
    view = view_class(root_oid, request)
    return view.resolve(first)


def get_full_data(object_ids, view_name, request=None):
    """
    :param object_ids: The ``cdb_object_id`` values to get the full data of.
    :type object_ids: list of str

    :param view_name: Name of a registered project structure view.
    :type view_name: str

    :param request: The request sent from the frontend.
        Defaults to a dummy request.
    :type request: morepath.Request

    :returns: The JSON-serializable full data.
    :rtype: dict (usually, but depends on the specific view)

    :raises KeyError: if ``view_name`` is not the name of a registered view.
    :raises AttributeError: if resolved view class
        is missing the method ``get_full_data_of``.
    """
    request = _ensure_request(request)
    view_class = get_view_class(view_name)
    return view_class.get_full_data_of(object_ids, request)


def persist_drop(target, parent, children, predecessor, view_name, is_move=True):
    """
    :param target: ``@id`` of object to move in structure
    :type target: str

    :param parent: ``@id`` of new parent object of target
    :type parent: str

    :param children: ordered list of ``@id`` of parent's children
        containing ``target`` in the intended position.
    :type children: list of str

    :param predecessor: ``@id`` of target's new predecessor.
            Used as a fallback if ``children`` is ``None``
        :type predecessor: str

    :param view_name: Name of a registered project structure view.
    :type view_name: str

    :param is_move: If ``True``, this is a "move" operation, otherwise "copy".
    :type is_move: bool

    :raises KeyError: if ``view_name`` is not the name of a registered view.
    """
    view_class = get_view_class(view_name)
    return view_class.persist_drop(target, parent, children, predecessor, is_move)


def delete_copy(copy_id, view_name):
    """
    :param copy_id: ``@id`` of copyied object to delete
    :type copy_id: str

    :param view_name: Name of a registered project structure view.
    :type view_name: str

    :raises KeyError: if `view_name` is not the name of a registered view.
    """
    view_class = get_view_class(view_name)
    return view_class.delete_copy(copy_id)


class ProjectStructureViews:
    def __init__(self):
        self.collect()

    @classmethod
    def GetViewClass(cls, view_name):
        """
        :param view_name: Name of the view to get the class for.
        :type view_name: str

        :returns: Class of the view named `view_name`
        :rtype: class
        """
        views = cls()
        return views.views[view_name]

    def _register_view(self, view):
        # may raise AttributeError or ValueError
        view_name = view.view_name

        if issubclass(view, View):
            already_registered = self.views.get(view_name, None)

            if already_registered:
                logging.error(
                    "ignoring duplicate view '%s': %s",
                    view_name,
                    view,
                )
            else:
                self.views[view_name] = view
        else:
            raise TypeError(f"not a view: {view}")

    def collect(self):
        """
        Emit ``cs.pcs.projects.project_structure.views.GET_VIEWS``.
        Functions connected to the signal will be called to register
        themselves.

        .. note ::

            Only the first view to register itself
            for any given view name is used.
            To avoid ambiguity, only one view should be registered
            for each name.

        """
        self.views = {"project_structure": TreeView}
        sig.emit(GET_VIEWS)(self._register_view)


class ProjectStructureOutletCallback(outlet_config.OutletPositionCallbackBase):
    """
    If the project nor task feature is not licensed in the system, this callback
    will not show the tab of the ProjectStructure (e.g. return an empty list).
    """

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        if not is_feature_licensed(["TASKS_001"]):
            # do not show tab if project nor tasks are not licensed
            return []
        return [pos_config]
