#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import sys
import traceback

from cdb import transactions
from cdb.comparch import protocol

from cs.pcs.projects import Project, tasks_efforts


class UpdatePercentComplete:
    """
    E068238: Percentage of completion isn't aggregated correctly
    E067223: Partially discarded task groups and projects cannot be 100% completed
    (undocumented internal API changed; see Release Notes)

    This update script checks the internal aggregation for all projects, that are not
    yet in a final status.
    It especially fixes the value for percentage of completion for all those projects.
    The script utilizes the same code used by the usual work processes and just
    enforces the checks.
    """

    def run(self):
        success = 0
        failed = 0
        for p in Project.Query("status NOT IN (180, 200)"):
            try:
                with transactions.Transaction():
                    tasks_efforts.aggregate_changes(p)
                protocol.logMessage(
                    "Adjusted percentage of completion for"
                    f" project {p.cdb_project_id} - {p.project_name}"
                )
                success += 1
            except Exception:
                protocol.logError(
                    f"Error while adjusting project {p.cdb_project_id} - {p.project_name}",
                    details_longtext="".join(
                        traceback.format_exception(*sys.exc_info())
                    ),
                )
                failed += 1
        protocol.logMessage(
            f"{success} projects successfully adjusted.\n"
            f"{failed} projects failed to be adjusted.\n"
        )


upd_classes = [UpdatePercentComplete]


def main():
    for cls in upd_classes:
        name = cls().__class__.__name__
        protocol.logMessage(f"Update task {name} running...\n")
        cls().run()
        protocol.logMessage(f"Update {name} has been executed.\n")


# Guard importing as main module
if __name__ == "__main__":
    main()
