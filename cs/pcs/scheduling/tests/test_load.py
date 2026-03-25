#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date, datetime

import mock
from cdb import sqlapi, testcase

from cs.pcs.scheduling import load


@mock.patch.object(load.sqlapi, "SQLdate", return_value=None)
def test_SQLdate_null(SQLdate):
    assert load.SQLdate("T", "C", "R") == ""


@mock.patch.object(load.sqlapi, "SQLdate", return_value="02.05.2023")
def test_SQLdate(SQLdate):
    assert load.SQLdate("T", "C", "R") == date(2023, 5, 2)


@testcase.rollback
def test_load():
    sqlapi.Record(
        "cdbpcs_prj_prot",
        cdbprot_sortable_id="test-0",
        cdbprot_zeit=datetime(2023, 5, 1, 10, 11, 12),
        cdbprot_neustat="NEW",
        cdbprot_newstate=200,
    ).insert()
    sqlapi.Record(
        "cdbpcs_prj_prot",
        cdbprot_sortable_id="test-1",
    ).insert()

    result = load.load(
        "cdbprot_sortable_id, cdbprot_zeit, cdbprot_neustat, cdbprot_newstate"
        " FROM cdbpcs_prj_prot"
        " WHERE cdbprot_sortable_id LIKE 'test-%'",
        [
            ("cdbprot_sortable_id", sqlapi.SQLstring),
            ("cdbprot_zeit", load.SQLdate),
            ("cdbprot_neustat", sqlapi.SQLstring),
            ("cdbprot_newstate", sqlapi.SQLinteger),
        ],
    )
    assert result == [
        {
            "cdbprot_sortable_id": "test-0",
            "cdbprot_zeit": date(2023, 5, 1),
            "cdbprot_neustat": "NEW",
            "cdbprot_newstate": 200,
        },
        {
            "cdbprot_sortable_id": "test-1",
            "cdbprot_zeit": "",
            "cdbprot_neustat": "",
            "cdbprot_newstate": 0,
        },
    ]
