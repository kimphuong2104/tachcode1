#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi


class CheckIssueIdColumn:
    """
    Checks if the `issue_id` column is not of type char
    in any table after the update process is completed.
    The result is printed to the console.
    """

    def run(self):
        broken = sqlapi.RecordSet2(
            "cdb_columns",
            "column_name = 'issue_id' AND type != 'char'",
        )

        if broken:
            tables_message = "\n".join([f"{col.table_name}" for col in broken])
            print(
                """The issue_id column is not of type character in the following tables:\n"""
                f"{tables_message}"
            )


if __name__ == "__main__":
    CheckIssueIdColumn().run()
