# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module db_tools

Useful functionality for databases
"""


from cdb import sqlapi
from cdb import util

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ["OneOfReduced"]


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
            return "(%s)" % ",".join([self.table_info.make_literal(c_name, str(val)) for val in vals])

        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE\
           and len(values) > self.max_inlist_value:
            result = []
            for i in range(0, len(values) // self.max_inlist_value):
                result.append(_convert(column_name,
                                       values[i * self.max_inlist_value: (i + 1) * self.max_inlist_value]))
            result.append(_convert(column_name,
                                   values[(len(values) // self.max_inlist_value) * self.max_inlist_value:]))
        else:
            result = _convert(column_name, values)
        return result

    def get_expression(self, column_name, values=None, table_alias='', exclude_values=False):
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
        column_part = column_name if not table_alias else '{}.{}'.format(table_alias, column_name)
        value_part = self._make_values(column_name, values) if values else "('')"
        operand = "IN" if not exclude_values else "NOT IN"

        if isinstance(value_part, list):
            result = ["(%s %s %s)" %
                      (column_part, operand, single_vp) for single_vp in value_part]
            return "(%s)" % ((" AND " if exclude_values else " OR ").join(result))
        return "(%s %s %s)" % (column_part, operand, value_part)
