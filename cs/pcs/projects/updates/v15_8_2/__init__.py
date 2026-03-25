#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi


class FixContextRelationship:
    def run(self):
        sqlapi.SQLupdate(
            """
            cs_tasks_context_tree_relships SET
                parent_relship_name = 'cdbwf_info_message2process',
                source_classname = 'cdbwf_info_message'
            WHERE
                parent_relship_name = 'cdbwf_task2process'
                AND source_classname = 'cdbwf_task'
                AND context_tree_name = 'cdbwf_info_message_to_project'
        """
        )


pre = [FixContextRelationship]
post = []

if __name__ == "__main__":
    FixContextRelationship().run()
