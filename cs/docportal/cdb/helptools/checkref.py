# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Module checkref

Check help_id references for existence.

You can run this file to get some info about used HelpIDs:

    powerscript -m cs.docportal.cs.docportal.cdb.helptools.checkref

"""
from cdb import sqlapi
from cdb.platform.mom.fields import DDField

# hard-coded HelpIDs that must exist
CONSTANT_HELP_IDS = (
    'cdb_help_index',  # misc/constants.hh
    'cdb_mask_dlgsaveascii',  # wincdb/DlgSaveTableToASCII.cpp
    'cdb_mask_dlgverteiler',  # wincdb/dlgVerteiler.cpp
    'cdb_mask_dlgwsprops',  # wincdb/DlgWorkspaceProperties.cpp
)


class HelpIDChecker:
    """
    Check usage of help_id fields

    This checks all the classes with predefined fields based on cdb_help.help_id for
    issues with undefined or unused help references.
    """

    def __init__(self):
        self.usages = self.find_help_id_users()

    @staticmethod
    def find_help_id_users() -> list[tuple]:
        help_id_field = DDField.ByKeys(classname='cdb_help', field_name='help_id')
        usages = help_id_field.UsagesAsPredefinedField
        pairs = [(usage.Entity.relation, usage.field_name) for usage in usages]
        return pairs

    def find_undefined_help_ids(self) -> list[tuple[str, str]]:
        """
        Find all HelpIDs referenced but not defined in cdb_help

        :returns: List of tuples with relation/help_id pairs
        """

        usage_cond = '\nUNION ALL SELECT '.join(
            [
                f" '{relation}' relation, {field} help_id FROM {relation} "
                for relation, field in self.usages
            ]
        )

        sql = (
            """
            SELECT x.relation relation, x.help_id help_id
            FROM
                (SELECT %s) x
            WHERE
                x.help_id IS NOT NULL
            AND
                x.help_id IS NOT ""
            AND
                NOT EXISTS
                    (SELECT 1
                     FROM cdb_help
                     WHERE help_id=x.help_id)
              """
            % usage_cond
        )
        rs = sqlapi.RecordSet2(sql=sql)
        return [(row['relation'], row['help_id']) for row in rs]

    def find_unused_help_ids(self) -> list[str]:
        """
        Find all HelpIDs not referenced but defined in cdb_help

        :returns: List of unused help_ids
        """

        usage_cond = '\nUNION SELECT '.join(
            [f' {field} help_id FROM {table} ' for table, field in self.usages]
        )

        sql = (
            """
            SELECT help_id help_id
            FROM
                cdb_help
            WHERE
                help_id NOT IN (SELECT %s)
              """
            % usage_cond
        )

        rs = sqlapi.RecordSet2(sql=sql)
        return [(row['help_id']) for row in rs]

    def used_help_ids(self) -> list[str]:
        """
        Find all HelpIDs referenced anywhere

        :returns: List of referenced HelpIDs
        """

        usage_cond = '\nUNION SELECT '.join(
            [
                f' {field} help_id FROM {table} WHERE {field} '
                f"IS NOT NULL AND {field} <> ''"
                for table, field in self.usages
            ]
        )

        sql = """SELECT %s ORDER BY help_id""" % usage_cond

        rs = sqlapi.RecordSet2(sql=sql)
        return [(row['help_id']) for row in rs]


if __name__ == '__main__':
    checker = HelpIDChecker()
