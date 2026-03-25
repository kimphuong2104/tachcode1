#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from collections import defaultdict

from webob.exc import HTTPBadRequest

from cdb import misc, tools
from cdb.objects import Object
from cdbwrapc import CDBClassDef
from cs.taskmanager.eval import evaluate
from cs.taskmanager.web.util import get_object_ui_link


class Webdata(object):
    """Class to serve the async data for tasks."""

    def get_object_value(self, obj, request):
        description = obj.GetDescription()

        # kAppl_IIOPServer and cdbpc URLs will be removed in CE 16
        if hasattr(misc, "kAppl_IIOPServer") and misc.CDBApplicationInfo().rootIsa(
            misc.kAppl_IIOPServer
        ):
            object_ui_link = obj.MakeURL("CDB_ShowObject", plain=2)
        else:
            object_ui_link = get_object_ui_link(obj, request)
        result = {
            "link": {
                "to": object_ui_link,
                "title": description,
            },
            "text": description,
            "icon": {
                "src": obj.GetObjectIcon(),
                "size": "sm",
                "title": description,
            },
        }

        return result

    def get_rest_value(self, value, request):
        if isinstance(value, Object):
            return self.get_object_value(value, request)

        return value

    def ensure_existence(self, param, key):
        if key not in param:
            raise HTTPBadRequest
        return param[key]

    def _get_async_data(self, payload, request):
        """
        Computes the async data for tasks.

        :param payload: Payload should contain task object ids
            and propnames for each of the requested task type (system classname).
            An example payload would look like following:
            {
                "cdbpcs_task": {
                    "task_object_ids": [
                        "oid1", "oid2"
                    ],
                    "propnames": ["getCsTasksResponsible", "getCsTasksStatus"]
                },
                ...
            }

        :param request: Request object.

        :raises HTTPBadRequest: When the payload doesn't have the expected keys.
        """

        result = defaultdict(dict)

        for task_class, params in payload.items():
            if not params:
                raise HTTPBadRequest

            task_object_ids = self.ensure_existence(params, "task_object_ids")
            propnames = self.ensure_existence(params, "propnames")

            cldef = CDBClassDef(task_class)
            if not cldef:
                # classname is invalid
                continue

            klass = tools.getObjectByName(cldef.getFullQualifiedPythonName())
            if not klass:
                # No fully qualified python name provided
                continue

            tasks = [
                task
                for task in klass.KeywordQuery(cdb_object_id=task_object_ids)
                if task.CheckAccess("read")
            ]
            for task in tasks:
                result[task_class][task.cdb_object_id] = {}
                for propname in propnames:
                    r = self.get_rest_value(evaluate(task, propname), request)

                    result[task_class][task.cdb_object_id][propname] = r

        return result

    def get_async_data(self, request):
        """
        Gets the async data for tasks.

        :param request: Request object used for retrieving payload
            and computing links.

        :raises HTTPBadRequest: When there is no payload for the given request
            object.
        """

        payload = request.json

        if not payload:
            logging.error("Request doesn't contain json payload.")
            raise HTTPBadRequest

        return self._get_async_data(payload, request)
