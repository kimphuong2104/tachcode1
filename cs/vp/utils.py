# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import datetime
from typing import Any
from urllib.parse import urlparse, parse_qs

from cdb import sqlapi
from cdb.objects.core import parse_raw


DESCRIPTION_TAGS = dict()
NEVER_VALID_DATE = datetime.datetime(9999, 12, 31).replace(microsecond=0)


def get_description_tag(message):
    global DESCRIPTION_TAGS
    if message not in DESCRIPTION_TAGS:
        from cdb.platform.gui import Message
        msg = Message.ByKeys(message)
        if msg:
            dtag = msg.Text['']
            DESCRIPTION_TAGS[message] = parse_raw(dtag)
        else:
            raise RuntimeError("Message with id '%s' not found" % message)
    return DESCRIPTION_TAGS[message]


def parse_url_query_args(url: str, single_value_mode: bool=True) -> dict[str, Any]:
    """
    Parse the query args of an url

    :param url: url which should be parsed
    :param single_value_mode: flag which shows if only single values should be extracted (index 0).
                              Default: True

    :return: dict with query args
    """
    url_parse_result = urlparse(url)
    result = parse_qs(url_parse_result.query)

    if single_value_mode:
        result = {each_key: each_value[0] for each_key, each_value in result.items()}

    return result


def chunk(all_elements, number_of_elements):
    for i in range(0, len(all_elements), number_of_elements):
        yield all_elements[i:i + number_of_elements]


def get_sql_row_limit(rows=1):
    select_limit = ""
    where_limit = ""
    match sqlapi.SQLdbms():
        case sqlapi.DBMS_ORACLE:
            where_limit = f"AND ROWNUM <= {rows}"
        case sqlapi.DBMS_MSSQL:
            select_limit = f"TOP {rows}"
        case sqlapi.DBMS_SQLITE | sqlapi.DBMS_POSTGRES:
            where_limit = f"LIMIT {rows}"
    return select_limit, where_limit


def add_bom_mode(app_setup):
    from cs.vp.bom import AssemblyComponent
    app_setup.merge_in(["cs.vp.bom"], {
        'bom_mode': AssemblyComponent.get_bom_mode()
    })


def sql_recursive():
    return "RECURSIVE" if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES else ""
