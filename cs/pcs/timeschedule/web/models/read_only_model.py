#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import sqlapi
from webob.exc import HTTPBadRequest

from cs.pcs.timeschedule.web.models.base_model import ScheduleBaseModel
from cs.pcs.timeschedule.web.models.helpers import (
    get_oid_query_str,
    get_oids_by_relation,
    get_pcs_oids,
)
from cs.pcs.timeschedule.web.plugins import WithTimeSchedulePlugin


class ReadOnlyModel(ScheduleBaseModel, WithTimeSchedulePlugin):
    def get_read_only_data(self, oids):
        # resolve oids, i.e. get for each oid the table name
        ts_oids = get_pcs_oids(oids)
        # group the resolved oids by table name
        oids_by_tablename = get_oids_by_relation(ts_oids)
        # determine all oids without save access (so read only)
        read_only_oids = []
        # and determine all oids with save access
        oids_with_save_access_by_tablename = {}
        # check the access right on oids
        for tablename, oids_to_check in oids_by_tablename:
            query_str = get_oid_query_str(oids_to_check)
            oids_with_save_access = [
                record.cdb_object_id
                for record in sqlapi.RecordSet2(tablename, query_str, access="save")
            ]

            # add only oids for which no save access is granted
            oids_without_save_access = set(oids_to_check) - set(oids_with_save_access)
            read_only_oids += list(oids_without_save_access)
            # add only oids for which save access is granted
            oids_with_save_access_by_tablename.update(
                {
                    tablename: oids_with_save_access,
                }
            )

        # determine class specific read only fields and object specific
        # read only fields for each class a plugin exists for
        class_specific_read_only_attributes_per_class = {}
        object_specific_read_only_attributes_per_oid = {}
        for plugin in self.plugins.values():
            # by class
            read_only_fields_by_class = plugin.GetClassReadOnlyFields()
            class_specific_read_only_attributes_per_class.update(
                {plugin.classname: read_only_fields_by_class}
            )
            # by object
            read_only_fields_by_object = plugin.GetObjectReadOnlyFields(
                oids_with_save_access_by_tablename.get(plugin.table_name, []),
            )
            object_specific_read_only_attributes_per_oid.update(
                read_only_fields_by_object
            )

        return {
            "OIDs": read_only_oids,
            "byClass": class_specific_read_only_attributes_per_class,
            "byObject": object_specific_read_only_attributes_per_oid,
        }

    def get_read_only(self, request):
        # request contains lists of oids to check save access right for
        try:
            oids = request.json["oids"]
        except KeyError as exc:
            logging.error("request is missing 'oids'")
            raise HTTPBadRequest from exc

        return self.get_read_only_data(oids)
