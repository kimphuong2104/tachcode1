#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi

from cs.pcs.projects.updates.v15_8_0 import CreateProjectBaselines


class AddDaytime:
    def run(self):
        # Set daytime=NULL
        sqlapi.SQLupdate(
            """
            cdbpcs_task SET
                daytime = NULL
            WHERE
                milestone IS NULL
                OR milestone = 0
                OR automatic = 1
        """
        )
        # Set daytime=Morning
        sqlapi.SQLupdate(
            """
            cdbpcs_task SET
                daytime = 0
            WHERE
                milestone = 1
                AND automatic = 0
                AND start_is_early = 1
        """
        )
        # Set daytime=Evening
        sqlapi.SQLupdate(
            """
            cdbpcs_task SET
                daytime = 1
            WHERE
                milestone = 1
                AND automatic = 0
                AND start_is_early = 0
        """
        )


pre = []
post = [AddDaytime]

if __name__ == "__main__":
    CreateProjectBaselines(
        baseline_name="Scheduled before cs.pcs 15.8.1",
        baseline_comment=(
            "This baseline contains the schedule computed"
            " before the update to cs.pcs 15.8.1."
            " Use it to discover scheduling changes."
        ),
    ).run()
