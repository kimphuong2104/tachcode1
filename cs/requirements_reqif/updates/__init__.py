#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id: __init__.py 134508 2015-11-20 11:51:29Z aki $"

from cdb import sqlapi
from cdb.comparch.pk_upgrade import PKUpgrade


class ReqIFProfileAttributesSchemaPKUpgrade(PKUpgrade):

    def __init__(self):
        super(ReqIFProfileAttributesSchemaPKUpgrade, self).__init__("cs.requirements_reqif",
                                                                    "cdbrqm_reqif_profile_attrs",
                                                                    "cdbrqm_reqif_profile_attrs",
                                                                    ['reqif_profile_id', 'object_type_classname', 'internal_field_name'],
                                                                    ['reqif_profile_id', 'entity_object_id', 'internal_field_name'])
        # fill the entity cache once
        self.entities = {}

    def _fill_entity_cache(self):
        if not self.entities:
            rs = sqlapi.RecordSet2("cdbrqm_reqif_profile_entities")
            for record in rs:
                self.entities[(record['reqif_profile_id'], record['internal_object_type'])] = record['cdb_object_id']

    def change_db_content(self):
        from cdb import ddl
        from cdb.ddl import Char
        t = ddl.Table(self.table_name)
        if not t.hasColumn('entity_object_id'):
            # ensure that the table has the column
            col = Char('entity_object_id', 40)
            t.addAttributes(col)
        self._fill_entity_cache()
        # fill the entity_object_id for each reqif attribute mapping
        for k, v in self.entities.items():
            sqlapi.SQLupdate("cdbrqm_reqif_profile_attrs SET entity_object_id = '%s' WHERE reqif_profile_id='%s' AND object_type_classname='%s'" % (
                sqlapi.quote(v),
                sqlapi.quote(k[0]),
                sqlapi.quote(k[1]))
            )

    def get_new_pk(self, old_pk, data, new_pk, module_id):
        self._fill_entity_cache()
        if new_pk["entity_object_id"] is None:
            new_id = self.entities.get((old_pk.get('reqif_profile_id'), old_pk.get('object_type_classname')))
            new_pk["entity_object_id"] = new_id if new_id else ''
        return new_pk


upgrades = [ReqIFProfileAttributesSchemaPKUpgrade()]
