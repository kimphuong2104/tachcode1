#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import logging

from webob.exc import HTTPNotFound

from cdb import auth, sqlapi
from cs.taskmanager.userdata import ReadStatus, Tags
from cs.taskmanager.web.util import format_in_condition, get_grouped_data


class WriteDataBaseModel(object):
    def check_read(self, *object_ids):
        where_ids = format_in_condition("id", object_ids)
        ids_by_table = get_grouped_data(
            "cdb_object",
            where_ids,
            "relation",
            transform_func=lambda x: x.id,
        )

        found_ids = [oid for oids in ids_by_table.values() for oid in oids]
        missing_ids = set(object_ids).difference(found_ids)
        if missing_ids:
            logging.error("IDs missing in cdb_object: %s", missing_ids)
            raise HTTPNotFound

        for table, uuids in ids_by_table.items():
            where_uuids = format_in_condition("cdb_object_id", uuids)
            rows = sqlapi.RecordSet2(table, where_uuids, access="read")
            missing_ids = set(uuids).difference([row.cdb_object_id for row in rows])
            if missing_ids:
                logging.error("IDs missing in %s: %s", table, missing_ids)
                raise HTTPNotFound


class WriteReadStatus(WriteDataBaseModel):
    def set_read_status(self, read, unread):
        self.check_read(*(read + unread))

        if read:
            ReadStatus.SetTasksRead(*read)
        if unread:
            ReadStatus.SetTasksUnread(*unread)


class WriteTags(WriteDataBaseModel):
    def set_tags(self, tags_by_oid):
        self.check_read(*tags_by_oid.keys())
        result = {}

        for object_id, tags in tags_by_oid.items():
            Tags.SetTaskTags(auth.persno, object_id, tags)
            result[object_id] = Tags.GetTaskTags(auth.persno, object_id)

        return result
