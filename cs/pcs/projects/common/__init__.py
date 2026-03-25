#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import abc

from cdb import sqlapi, ue
from cdb.lru_cache import lru_cache
from cdb.platform.mom.entities import CDBClassDef


def partition(values, chunksize):
    values = list(values) if isinstance(values, abc.KeysView) else values
    if not (isinstance(chunksize, int) and chunksize > 1):
        raise ValueError("chunksize must be a positive integer")

    for index in range(0, len(values), chunksize):
        yield values[index : index + chunksize]


# copied from cs.classification 15.2.0.36
def format_in_condition(col_name, values, max_inlist_value=1000):
    """
    :param col_name: Name of the column to generate an "in" clause for
    :type col_name: string

    :param values: Values to use in "in" clause
    :type values: list - will break if a set is used

    :returns: "or"-joined SQL "in" clauses including ``values`` in batches of
        up to 1000 each to respect DBMS-specific limits (ORA: 1K, MS SQL 10K).
        NOTE: If values is empty "1=0" is returned, so no value should be
              returned for the SQL statement.
    :rtype: string
    """

    def _convert(values):
        return f"{col_name} IN ({','.join([sqlapi.make_literals(v) for v in values])})"

    if len(values) == 0:
        return "1=0"

    conditions = [_convert(chunk) for chunk in partition(values, max_inlist_value)]
    return " OR ".join(conditions)


def is_valid_resp(cdb_project_id, subject_id, subject_type):
    team_data = sqlapi.RecordSet2(
        "cdbpcs_resp_brows",
        f"cdb_project_id = '{sqlapi.quote(cdb_project_id)}' "
        f"AND subject_id = '{sqlapi.quote(subject_id)}' "
        f"AND subject_type = '{sqlapi.quote(subject_type)}'",
    )

    return bool(team_data)


@lru_cache(maxsize=1, clear_after_ue=True)
def assert_team_member(ctx, cdb_project_id):
    # Check the user is a member of the project
    subject_type = ctx.dialog.subject_type
    subject_id = ctx.dialog.subject_id

    valid_resp = is_valid_resp(cdb_project_id, subject_id, subject_type)

    if valid_resp:
        return

    raise ue.Exception("cdbpcs_check_team_member_assigned", subject_id, cdb_project_id)


def assert_valid_project_resp(ctx):
    cdb_project_id = ctx.dialog.cdb_project_id
    subject_id = ctx.dialog.subject_id if hasattr(ctx.dialog, "subject_id") else None
    subject_type = (
        ctx.dialog.subject_type if hasattr(ctx.dialog, "subject_type") else None
    )

    # Note: if no responsible is given skip check about team membership
    if subject_id and not is_valid_resp(cdb_project_id, subject_id, subject_type):
        raise ue.Exception("cdbpcs_invalid_resp")


@lru_cache(maxsize=None)
def get_restname(classname):
    """
    Returns restname for a given data dictionary class.

    :param classname: data dictionary classname.
    :type: str

    :returns: restname if data dictionary class exists.
        Otherwise returns None.
    :rtype: str
    """
    cdef = CDBClassDef(classname)
    return cdef.getRESTName() if cdef else None
