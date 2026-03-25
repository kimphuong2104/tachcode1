#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class DataMigrations:
    def run(self):
        self.upd_kosmodrom_missing_rules()

    def upd_kosmodrom_missing_rules(self):

        # docs
        module_id = "cs.pcs.projects_documents"
        # terms
        sqlstr = (
            "into cdb_pyterm (name, fqpyname, predicate_name, attribute, "
            + "operator, expression, filter_rule, id, cdb_module_id) "
            + "values('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"
        )

        name = "cdbpcs: Kosmodrom: Released Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pyterm where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: Released Documents",
                    "z_status",
                    "=",
                    "200",
                    "",
                    "1",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: My Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pyterm where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: My Documents",
                    "autoren",
                    "=",
                    "$(persno)",
                    "",
                    "1",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Active Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pyterm where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: Active Documents",
                    "z_status",
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
                f"* from cdb_pyterm where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: Recently Created Documents",
                    "cdb_cdate",
                    ">=",
                    "$(start_date)",
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

        name = "cdbpcs: Kosmodrom: Active Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pypredicate where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: Active Documents",
                    "",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: My Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pypredicate where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: My Documents",
                    "",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Objects Recently Created"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pypredicate where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: Recently Created Documents",
                    "",
                    module_id,
                )
            )

        name = "cdbpcs: Kosmodrom: Released Objects"
        if not sqlapi.SQLrows(
            sqlapi.SQLselect(
                f"* from cdb_pypredicate where name='{name}' and cdb_module_id='{module_id}'"
            )
        ):
            sqlapi.SQLinsert(
                sqlstr
                % (
                    name,
                    "cs.documents.Document",
                    "cdbpcs: Kosmodrom: Released Documents",
                    "",
                    module_id,
                )
            )

    # ----------------------------------------------------------


pre = []
post = [DataMigrations]
