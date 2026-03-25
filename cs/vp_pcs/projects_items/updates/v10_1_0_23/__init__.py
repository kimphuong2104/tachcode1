#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class DataMigrations(object):
    def run(self):
        self.upd_kosmodrom_missing_rules()

    def upd_kosmodrom_missing_rules(self):
        # items
        module_id = "cs.vp_pcs.projects_items"
        # terms
        sqlstr = (
            "into cdb_pyterm "
            + "(name, fqpyname, predicate_name, attribute, operator, expression, filter_rule, id, cdb_module_id) "  # noqa: E501
            + "values('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"
        )

        name = "cdbpcs: Kosmodrom: Released Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pyterm where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: Released Items",
                    "status",
                    "IN",
                    "200,300,400",
                    "",
                    "1",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Active Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pyterm where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: Active Items",
                    "status",
                    "!=",
                    "180",
                    "",
                    "1",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Objects Recently Created"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pyterm where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: Recently Created Items",
                    "cdb_cdate",
                    ">=",
                    "$(start_date)",
                    "",
                    "1",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: My Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pyterm where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: My Items",
                    "cdb_cpersno",
                    "=",
                    "$(persno)",
                    "",
                    "1",
                    module_id,
                )
            )

        # predicates
        sqlstr = (
            "into cdb_pypredicate (name, fqpyname, predicate_name, description, cdb_module_id) "
            + "values('%s', '%s', '%s', '%s', '%s')"
        )

        name = "cdbpcs: Kosmodrom: Objects Recently Created"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pypredicate where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: Recently Created Items",
                    "",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: My Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pypredicate where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: My Items",
                    "",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Released Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pypredicate where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: Released Items",
                    "",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Active Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                "* from cdb_pypredicate where name='%s' and cdb_module_id='%s'"
                % (name, module_id)
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.vp.items.Item",
                    "cdbpcs: Kosmodrom: Active Items",
                    "",
                    module_id,
                )
            )

    # ----------------------------------------------------------


pre = []
post = [DataMigrations]
