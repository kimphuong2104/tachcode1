#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import ElementsError, sig, sqlapi, tools, transaction
from cdb.constants import kOperationDelete, kOperationNew
from cdb.objects.operations import operation
from cdbwrapc import CDBClassDef
from webob.exc import HTTPBadRequest, HTTPForbidden, HTTPNotFound

from cs.pcs.projects.common.rest_objects import (
    get_project_id_in_batch,
    get_restlinks_in_batch,
)
from cs.pcs.timeschedule.web.models.data_model import DataModel


class ElementsModel(DataModel):
    def __init__(self, context_object_id):
        super().__init__(context_object_id)
        fqpyname = CDBClassDef(self.content_classname).getFullQualifiedPythonName()
        self.content_cls = tools.getObjectByName(fqpyname)

    def _get_schedule_elements(self, request):
        """
        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: REST links of time schedule elements ordered by their
            position.
        :rtype: list of str
        """
        pinned_oids = self._get_pinned_oids()
        pinned_records = self._get_record_tuples(pinned_oids)
        links_by_oid = get_restlinks_in_batch(pinned_records, request)
        readable = self._get_readable(pinned_oids, links_by_oid)

        return [links_by_oid[ts_oid.cdb_object_id] for ts_oid in readable]

    def _run_op(self, opname, element, **kwargs):
        try:
            operation(opname, element, **kwargs)
        except ElementsError as error:
            logging.exception("operation on time schedule element failed")
            raise HTTPForbidden(str(error)) from error

    def _get_tables_by_oid(self, content_oids):
        """
        :param content_oids: cdb_object_ids to get information for
        :type content_oids: list of str

        :returns: database table names indexed by cdb_object_ids
        :rtype: dict
        """
        formatted_in_values = "', '".join(content_oids)
        return {
            x.id: x.relation
            for x in sqlapi.RecordSet2("cdb_object", f"id IN ('{formatted_in_values}')")
        }

    def _clear_elements(self):
        elements = self.content_cls.KeywordQuery(
            view_oid=self.context_object_id,
        )
        if elements:
            self._run_op(kOperationDelete, elements)

    def get_schedule_elements(self, request):
        return self._get_schedule_elements(request)

    def get_schedule_project_ids(self, request):
        pinned_oids = self._get_pinned_oids()
        pinned_records = self._get_record_tuples(pinned_oids)
        return get_project_id_in_batch(pinned_records, request)

    def persist_elements(self, request):
        """
        Set time schedule's elements.

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :raises HTTPBadRequest: if the json payload is missing the attribute
            ``elementOIDs``.

        :raises HTTPNotFound: if any object ID is unknown or no plugin can be
            found for it.

        :raises HTTPForbidden: if the create operation of the content object
            fails or pinning the object is not allowed.
        """
        try:
            content_oids = request.json["elementOIDs"]
        except KeyError as exc:
            logging.error("request is missing 'elementOIDs'")
            raise HTTPBadRequest from exc

        sig.emit("plugins.validate_schedule")(self.context_object_id)

        tables_by_oid = self._get_tables_by_oid(content_oids)

        try:
            with transaction.Transaction():
                self._clear_elements()

                for content_oid in content_oids:
                    table = tables_by_oid[content_oid]
                    plugin = self.plugins[table]
                    if not getattr(plugin, "allow_pinning", False):
                        logging.exception(
                            "Pinning not allowed for this plugin - Table: '%s'", table
                        )
                        raise HTTPForbidden()

                    self._run_op(
                        kOperationNew,
                        self.content_cls,
                        view_oid=self.context_object_id,
                        content_oid=content_oid,
                        cdb_content_classname=plugin.classname,
                        unremovable=0,
                    )
        except KeyError as exc:
            logging.exception("adding time schedule element failed")
            raise HTTPNotFound from exc

    def get_manage_elements_data(self, request):
        """
        Get data for standalone `Manage Elements` operation:

        1. Query content object IDs for context time schedule ordered by
           position. Keep list of oid and database table name tuples.
        2. For each content object, resolve its structure using the matching
           plugin. Missing plugins will raise exceptions.
        3. Query database to get records for all resolved object IDs where
           "read" access is granted.

        .. warning ::

            Because ``sqlapi.Record`` objects are used instead of higher-level
            APIs like ``cdb.objects``, make sure to provide plugins for all
            object classes usable as time schedule contents.

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: data for frontend needed to run the ManageElements operation.
        :rtype: dict

        """
        pinned_oids = self._get_pinned_oids()
        ts_records = self._get_record_tuples(pinned_oids)
        result = self._get_rest_objects(None, ts_records, request)

        result.update(
            {
                "elements": self.get_schedule_elements(request),
                "project_ids_by_elements": self.get_schedule_project_ids(request),
                "plugins": self._get_plugins(request),
            }
        )
        return result
