#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module db_tools

Useful functionality for databases
"""

import pathlib

from cdb import misc, sqlapi, util


def load_pattern(pattern_name):
    """
    :param pattern_name: Base name of a file containing an SQL pattern.
        The pattern may include keyword placeholders to fill via `format`.
    :type pattern_name: str

    :returns: Contents of the SQL file located in `sql/{pattern_name}.sql`.
    :rtype: str

    :raises RuntimeError: if `pattern_name` tries to escape this file's path.
    :raises: if file does not exist or is not readable.
    """
    base = (pathlib.Path(__file__).parent / "sql").resolve()
    sanitized_path = misc.jail_filename(str(base), f"{pattern_name}.sql")

    with open(sanitized_path, "r", encoding="utf-8") as pattern_file:
        return pattern_file.read()


class OneOfReduced(object):
    """
    The PowerScript Objects framework is not used for more complex calculations in Project Office.
    This class creates SQL conditions using the operators IN or NOT IN. Additional features are:
    - The data type of the column is taken into account.
    - Alias names for tables can be used
    - Oracle-specific limitation to a maximum of 1000 items in the list is taken into account

    Samples:
        oor = OneOfReduced(table_name='cdbpcs_task')
            print oor.get_expression(column_name='task_id',
                                     values=['T001', 'T002', 'T003', 'T004', 'T005'],
                                     table_alias='x')
            # Output:
            # (x.task_id IN ('T001','T002','T003','T004','T005'))

            print oor.get_expression(column_name='task_id',
                                     values=['T001', 'T002', 'T003', 'T004', 'T005'],
                                     exclude_values=True)
            # Output:
            # (task_id NOT IN ('T001','T002','T003','T004','T005'))

            print oor.get_expression(column_name='status',
                         values=[50, 100, 200])
            # Output:
            # (status IN (50,100,200))

            oor.max_inlist_value = 3  # for demo purposes,
                                      # the maximum number of entries in a list is reduced to 3
            print oor.get_expression(column_name='task_id',
                                     values=['T001', 'T002', 'T003', 'T004', 'T005'],
                                     table_alias='x')
            # Output:
            # ((x.task_id IN ('T001','T002','T003')) OR (x.task_id IN ('T004','T005')))
    """

    max_inlist_value = 1000

    def __init__(self, table_name):
        """
        :param table_name: table name in order to determine the data type of column_name
        """
        self.table_info = util.TableInfo(table_name)

    def _make_values(self, column_name, values):
        def _convert(c_name, vals):
            return "(%s)" % ",".join(
                [self.table_info.make_literal(c_name, str(val)) for val in vals]
            )

        if is_oracle() and len(values) > self.max_inlist_value:
            result = []
            for i in range(0, len(values) // self.max_inlist_value):
                result.append(
                    _convert(
                        column_name,
                        values[
                            i * self.max_inlist_value : (i + 1) * self.max_inlist_value
                        ],
                    )
                )

            remaining = values[
                (len(values) // self.max_inlist_value) * self.max_inlist_value :
            ]
            if remaining:
                result.append(_convert(column_name, remaining))
        else:
            result = _convert(column_name, values)
        return result

    def get_expression(
        self, column_name, values=None, table_alias="", exclude_values=False
    ):
        """
        Get the expression for use in SQL statements
        :param column_name: column name used to search for values.
        :param values: list of values to be searched for
        :param table_alias: A table alias that is set before the column name when the condition is used
                            in SQL join statements. The table alias does not have to refer to the table name.
        :param exclude_values: False (Default): values are searched for using an IN expression
                              True: values are excluded with an NOT-IN expression
        :return: SQL expression for use in WHERE conditions
        """
        column_part = (
            column_name if not table_alias else "{}.{}".format(table_alias, column_name)
        )
        value_part = self._make_values(column_name, values) if values else "('')"
        operand = "IN" if not exclude_values else "NOT IN"

        if isinstance(value_part, list):
            result = [
                "(%s %s %s)" % (column_part, operand, single_vp)
                for single_vp in value_part
            ]
            return "(%s)" % ((" AND " if exclude_values else " OR ").join(result))
        return "(%s %s %s)" % (column_part, operand, value_part)


SQL_IN_MULTI_VALUES = """WITH q (cdb_project_id, task_id) AS (
        SELECT {}
    )
    SELECT cdb_object_id
    FROM cdbpcs_task
    INNER JOIN q
        ON q.cdb_project_id = cdbpcs_task.cdb_project_id
        AND q.task_id = cdbpcs_task.task_id
    WHERE cdbpcs_task.ce_baseline_id = ''
"""


def is_oracle():
    return sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE


def is_postgres():
    return sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES


def get_task_uuids(objs):
    """
    :param objs: Objects with ``cdb_project_id`` and ``task_id`` attributes
    :type objs: list or cdb.objects.ObjectCollection

    :returns: UUIDs of tasks referenced by ``objs``
    :rtype: list
    """
    if not objs:
        return []

    task_key_pattern = (
        "'{0.cdb_project_id}' AS cdb_project_id, '{0.task_id}' AS task_id"
    )

    if is_oracle():
        task_key_pattern += " FROM dual"

    task_keys = " UNION SELECT ALL ".join([task_key_pattern.format(x) for x in objs])
    tasks = sqlapi.RecordSet2(sql=SQL_IN_MULTI_VALUES.format(task_keys))
    return [x.cdb_object_id for x in tasks]


def get_res_sched_condition(prefix, task_uuids, filter_condition=None):
    oor = OneOfReduced(table_name="cdbpcs_task")
    query = "{} AND {}".format(
        oor.get_expression(
            table_alias="cdbpcs_task",
            column_name="cdb_object_id",
            values=task_uuids,
        ),
        filter_condition or "1=1",
    )
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        # MS SQL does not support tuples and IN clauses
        return """EXISTS (
            SELECT 1
            FROM cdbpcs_task
            WHERE cdbpcs_task.cdb_project_id = {0}.cdb_project_id
                AND cdbpcs_task.task_id = {0}.task_id
                AND {1}
        )""".format(
            prefix, query
        )
    else:
        return """({0}.cdb_project_id, {0}.task_id) IN (
            SELECT cdb_project_id, task_id
            FROM cdbpcs_task
            WHERE {1}
        )""".format(
            prefix, query
        )


def get_time_frame_overlap_condition(start_field, end_field, start_date, end_date):
    """
    :param start_field: Name of the DB field containing lower-bound date values
    :type start_field: str

    :param end_field: Name of the DB field containing upper-bound date values
    :type end_field: str

    :param start_date: Lower-bound date value
    :type start_date: datetime.date

    :param end_date: Uppoer-bound date value
    :type end_date: datetime.date

    :returns: SQL WHERE condition (without "WHERE" keyword)
        to retrieve rows with some overlap of given time frame.
    :rtype: str
    """
    start = sqlapi.SQLdate_literal(start_date)
    end = sqlapi.SQLdate_literal(end_date)
    return f"""COALESCE({start_field}, {start}) <= {end}
        AND COALESCE({end_field}, {end}) >= {start}"""
