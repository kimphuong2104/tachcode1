#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi, version


class PatchOperationGroup(object):
    def run(self):
        if version.verstring(0) >= "15.5":
            sqlapi.SQLupdate(
                "cdb_op_names "
                "SET menugroup=40, "
                "    ordering=10 "
                "WHERE name='cs_tasks_delegate' "
            )


pre = []
post = [PatchOperationGroup]
