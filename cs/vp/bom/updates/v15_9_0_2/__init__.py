# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


class RemoveUnusedObjectRule(object):

    def run(self):
        """
        Removes the unused object rule "mBOM Manager: 3D documents", including its associated predicates and
        terms.
        """

        from cdb import sqlapi

        rule_to_delete = "mBOM Manager: 3D documents"

        # Delete terms, predicates then rule itself.
        tables = ["cdb_pyterm", "cdb_pypredicate", "cdb_pyrule"]
        for table in tables:
            records = sqlapi.RecordSet2(table, "name='{}'".format(rule_to_delete))
            for record in records:
                record.delete()


pre = []
post = [RemoveUnusedObjectRule]


if __name__ == "__main__":
    RemoveUnusedObjectRule().run()
