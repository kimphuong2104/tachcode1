#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import ddl, sqlapi


class teilenummer2PartObjectID:
    """
    Update the new attribute field part_object_id in class cdb_action
    based on the already existing values of teilenummer and t_index
    """

    def run(self):
        t = ddl.Table("part_v")
        if t.exists():
            sqlapi.SQLupdate(
                "cdb_action SET part_object_id="
                "(select cdb_object_id from part_v where "
                "part_v.teilenummer=cdb_action.teilenummer and "
                "part_v.t_index=cdb_action.t_index)"
            )


pre = []
post = [teilenummer2PartObjectID]
