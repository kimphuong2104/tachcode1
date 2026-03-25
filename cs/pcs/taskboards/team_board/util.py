# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module util

Auxiliary functions of the team interval board
"""

from cdb import sig, sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


def get_valid_boards_sql_condition(**kwargs):
    """
    :return: Returns a sql condition containing the IDs of all valid boards
    :rtype: basestring
    """
    sql_args = {"table_alias": "c"}
    sql_args.update(**kwargs)

    valid_oid_statements = sig.emit("get_valid_board_object_ids")()
    if not valid_oid_statements:
        return "1=1"
    # pylint: disable-next=consider-using-f-string
    cond = ["{table_alias}.board_object_id IS NULL".format(**sql_args)]
    for valid_stmt in valid_oid_statements:
        sql_args.update(valid_stmt=valid_stmt)
        cond.append(
            # pylint: disable-next=consider-using-f-string
            "{table_alias}.board_object_id IN ({valid_stmt})".format(**sql_args)
        )
    return " OR ".join(cond)


def get_available_subjects_sql_condition(board_adapter, **kwargs):
    """
    :param board: instance of cs.taskboard.objects.Board
    :param kwargs:
        - subject_id: field containing the ID of the responsible (Default: subject_id)
        - subject_type: field containing the type of the responsible (Default: subject_type)
        - table_alias: field used as alias of the business objects table name (Default: t)
    :return: Returns a sql condition containing the IDs of all board members grouped by type
    :rtype: basestring
    """

    def make_sql(replacements):
        return (
            # pylint: disable-next=consider-using-f-string
            "({table_alias}.{subject_id} IN ({__subjects}) "
            "AND {table_alias}.{subject_type} = '{__type}')".format(**replacements)
        )

    sql_args = {
        "subject_id": "subject_id",
        "subject_type": "subject_type",
        "table_alias": "t",
    }
    sql_args.update(**kwargs)

    persons, common_roles, project_roles = board_adapter.get_subjects()
    statements = []

    if persons:
        sql_args["__subjects"] = ", ".join([f"'{sqlapi.quote(t)}'" for t in persons])
        sql_args["__type"] = "Person"
        statements.append(make_sql(sql_args))
    if common_roles:
        sql_args["__subjects"] = ", ".join(
            [f"'{sqlapi.quote(t)}'" for t in common_roles]
        )
        sql_args["__type"] = "Common Role"
        statements.append(make_sql(sql_args))
    if project_roles:
        sql_args["__subjects"] = ", ".join(
            [f"'{sqlapi.quote(t)}'" for t in project_roles]
        )
        sql_args["__type"] = "PCS Role"
        statements.append(make_sql(sql_args))

    available_subjects_sql_condition = " OR ".join(statements) if statements else ""
    return available_subjects_sql_condition
