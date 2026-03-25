#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi


class UpdateTaskAttributes:
    def run(self):
        # update all tasks, that have not ended yet:
        # auto_update_time_may not be True if automatic flag is not set
        sqlapi.SQLupdate(
            "cdbpcs_task SET auto_update_time = 0 WHERE automatic = 0"
            " AND auto_update_time = 1 AND status NOT IN (180, 200, 250)"
        )


pre = []
post = [UpdateTaskAttributes]
