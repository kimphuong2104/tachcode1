#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from contextlib import contextmanager

from cdb import cdbuuid, ddl, sqlapi, transactions, util
from cdb.objects import Object

from cs.pcs.projects.common import partition


def get_table_columns(table_name, filter_func):
    """
    :param table_name: Table name to get columns for
    :type table_name: str

    :param filter_func: Function to run for each column name.
        If the result is ``True``,
        the column name is included in the return value.
    :type filter_func: function

    :returns: Column names matching the filter
    :rtype: list
    """
    table = ddl.Table(table_name)
    if not table.exists():
        return []
    columns = table.reflect()
    return [
        column.colname
        for column in columns
        if (isinstance(column, ddl.ColumnBase) and filter_func(column.colname))
    ]


def _make_row_literals(table_info, rows):
    """
    :param table_info: Table info from ``cdb.util.tables``
    :type table_info: cdbwrapc.TableInfo

    :param rows: Key/value tuples for each row to generate literal for
    :type rows: list

    :returns: Comma-separated SQL literals for use
        with an identically ordered column list
    :rtype: str
    """
    row_literals = [
        sqlapi.make_literal(table_info, column, value) for column, value in rows
    ]
    return ", ".join(row_literals)


def sql_mass_insert(table, columns, rows, batchsize=500):
    """
    Insert multiple rows in batches into given table.

    :param table: Name of the table to insert into
    :type table: str

    :param columns: Column names to insert.
        Must be ordered exactly like values in each entry of ``rows``.
    :type columns: list

    :param rows: Value tuples for each row to insert.
        Rows must contain values in the exact same order as ``columns``.
        Values will be converted to SQL literals.
    :type rows: list

    :param batchsize: Rows to insert with a single statement. Defaults to 500.
        Some databases may be able to use higher values.
        Limiting factors include the max. length of statements
        and max. number of UNION clauses.
    :type batchsize: int

    .. rubric :: Example Usage

    .. code-block :: python

        from cs.pcs.projects.baselining import sql_mass_insert

        sql_mass_insert(
            "cdbpcs_issue",
            ("cdb_project_id", "issue_id", "issue_name", "cdb_object_id"),
            (
                ("P001", "ISS-001", "1st issue", "i1"),
                ("P001", "ISS-002", "2nd issue", "i2"),
                ("P001", "ISS-003", "3rd issue", "i3"),
            ),
        )
    """
    table_info = util.tables[table]
    stmts_rows = [_make_row_literals(table_info, zip(columns, row)) for row in rows]

    stmt_into = f"INTO {table} ({', '.join(columns)})"
    pattern_row = "SELECT {}"

    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        pattern_into = f"{stmt_into} WITH x AS ({{}}) SELECT * FROM x"
        pattern_row = f"{pattern_row} FROM dual"
    else:
        pattern_into = f"{stmt_into} {{}}"

    with transactions.Transaction():
        for chunk in partition(stmts_rows, batchsize):
            stmt_rows = " UNION ALL ".join(
                [pattern_row.format(stmt_row) for stmt_row in chunk]
            )
            stmt = pattern_into.format(stmt_rows)
            sqlapi.SQLinsert(stmt)


def sql_mass_copy(table, where, changes):
    """
    Insert multiple rows in batches into given table
    as a copy of the rows identified by ``where``.

    If the table contains the field ``cdb_object_id``,
    new UUIDs are generated automatically.
    Other individual changes to the copied rows are unsupported.

    :param table: Name of the table to read from and insert into
    :type table: str

    :param where: SQL WHERE condition (without "WHERE" keyword)
    :type where: str

    :param changes: Value changes to apply to all copied rows
    :type changes: dict

    .. rubric :: Example Usage

    .. code-block :: python

        from cs.pcs.projects.baselining import sql_mass_copy

        sql_mass_copy(
            "cdbpcs_issue",
            "cdb_project_id = 'old project'",
            {"cdb_project_id": "new project"},
        )
    """
    table_info = util.tables[table]
    changed_values = _make_row_literals(table_info, list(changes.items()))
    unchanged_columns = get_table_columns(table, lambda x: x not in changes)
    changed_columns = list(changes.keys())
    has_uuid = "cdb_object_id" in unchanged_columns

    if has_uuid:
        unchanged_columns.remove("cdb_object_id")
        changed_columns.append("cdb_object_id")
        changed_values = f"{changed_values}, cdbpcs_new_uuids.new_uuid"

    unchanged_col_str = ", ".join(unchanged_columns)

    pattern = (
        "INTO {table} ({all_columns}) "
        "SELECT {all_selects} "
        "FROM {table} "
        "{{}} "
        "WHERE {where}".format(
            table=table,
            all_columns=", ".join([unchanged_col_str] + changed_columns),
            all_selects=", ".join([unchanged_col_str, changed_values]),
            where=where,
        )
    )

    if has_uuid:
        old_data = sqlapi.RecordSet2(table, where, columns=["cdb_object_id"])

        with NewUUIDs.generate([x.cdb_object_id for x in old_data]) as opid:
            join = (
                f"JOIN {NewUUIDs.__maps_to__} "
                f"ON {NewUUIDs.__maps_to__}.opid = '{opid}' "
                f"AND {NewUUIDs.__maps_to__}.old_uuid = cdb_object_id"
            )
            stmt = pattern.format(join)
            sqlapi.SQLinsert(stmt)
            NewUUIDs.register_new_uuids(opid, table)
    else:
        stmt = pattern.format("")
        sqlapi.SQLinsert(stmt)


class NewUUIDs(Object):
    """
    Helper DB table to insert batch-generated UUIDs
    for SQL mass insert/copy.
    Generated UUIDs are inserted along with existing ones.
    This allows SQL-based copy operations to join ``cdbpcs_new_uuids``.

    All data in this table should be considered runtime data and
    must be deleted as soon as the operation is completed.

    The table is persistent instead of temporary to save on
    extra SQL statements and DBMS-specific logic.
    """

    __maps_to__ = "cdbpcs_new_uuids"
    __classname__ = "cdbpcs_new_uuids"

    @classmethod
    def register_new_uuids(cls, opid, relation):
        """
        Create records in ``cdb_object`` for given values.

        :param opid: Operation ID to retrieve new UUIDs to register
        :type opid: str

        :param relation: Name of the database table to register UUIDs for
        :type relation: str
        """
        stmt = (
            "INTO cdb_object (id, relation) "
            f"SELECT new_uuid, '{relation}' "
            f"FROM {cls.__maps_to__} "
            f"WHERE opid = '{opid}'"
        )
        sqlapi.SQLinsert(stmt)

    @classmethod
    @contextmanager
    def generate(cls, old_uuids):
        """
        Generates an ``opid`` and one new UUID for each ``old_uuid``.
        Data for this ``opid`` is deleted on context exit.

        Temporary UUIDs can be used to efficiently copy objects in SQL
        by joining with the rows to copy.
        The following example copies all issues of a project into another one.
        Please note that for brevity, not all columns are included.

        :param old_uuids: UUIDs to generate new ones for
        :type old_uuids: list
        """
        # 1. generate opid and UUIDs
        opid = cdbuuid.create_uuid()
        uuids = [(old_uuid, cdbuuid.create_uuid()) for old_uuid in old_uuids]

        # 2. insert temporary data for new opid
        sql_mass_insert(
            cls.__maps_to__,
            ("opid", "old_uuid", "new_uuid"),
            [(opid, old_uuid, new_uuid) for old_uuid, new_uuid in uuids],
        )

        # 3. give opid to the context block and run it
        yield opid

        # 4. clean up temporary data (also if context block raises)
        sqlapi.SQLdelete(f"FROM {cls.__maps_to__} WHERE opid = '{opid}'")
