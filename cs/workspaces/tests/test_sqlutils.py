#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from cdb import cdbuuid
from cdb.testcase import RollbackTestCase

from cs.workspaces.sqlutils import partionedSqlQuery, MAX_IN_ELEMENTS


class Test_SqlUtils(RollbackTestCase):
    def test_partitionedSqlQuery_emptyValues(self):
        # check that empty input values does not cause an error
        query = "SELECT * FROM zeichnung WHERE"
        records = partionedSqlQuery(query, "cdb_object_id", [], withAnd=False)
        assert not records

    def test_partitionedSqlQuery_manyValues(self):
        # check that there is no SQL error when using many input values
        query = "SELECT * FROM zeichnung WHERE"
        values = [cdbuuid.create_uuid() for _ in range(MAX_IN_ELEMENTS + 2)]
        partionedSqlQuery(query, "cdb_object_id", values, withAnd=False)


if __name__ == "__main__":
    import nose
    import sys

    nose.runmodule(argv=sys.argv[:1])
