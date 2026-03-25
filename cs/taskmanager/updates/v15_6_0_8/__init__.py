#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cdb.comparch import protocol


class ResponsibleCell:
    COLUMN = "cs_tasks_col_responsible"
    COMPONENT_OLD = "cs-tasks-cells-ObjectCell"
    COMPONENT_NEW = "cs-tasks-cells-ResponsibleCell"

    def run(self):
        vals = {
            "col": self.COLUMN,
            "old": self.COMPONENT_OLD,
            "new": self.COMPONENT_NEW,
        }
        updated = sqlapi.SQLupdate(
            """cs_tasks_column
            SET plugin_component = '{new}'
            WHERE name = '{col}'
                AND plugin_component = '{old}'
        """.format(
                **vals
            )
        )

        if not updated:
            protocol.logWarning(
                "Please consider using the new component '{new}' "
                "for the column '{col}'".format(**vals)
            )


pre = []
post = [ResponsibleCell]
