# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


"""
Module update_comments

Comments of issues will be migrated and moved to its activitysteam.
"""

from cdb.comparch import protocol

from cs.pcs.projects.updates.v15_5_0 import MigrateIssueComments

upd_classes = [MigrateIssueComments]


def main():
    for cls in upd_classes:
        printable_name = cls().__class__.__name__
        start_message = f"\nUpdate task {printable_name} running..."
        end_message = f"Update {printable_name} has been executed."
        protocol.logMessage(start_message)
        print(start_message)
        cls().run()
        protocol.logMessage(end_message)
        print(end_message)


# Guard importing as main module
if __name__ == "__main__":
    main()
