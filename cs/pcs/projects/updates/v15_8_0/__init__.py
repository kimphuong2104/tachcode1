#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import sys

from cdb import progress, sqlapi
from cdb.comparch import protocol, updutils
from cs.baselining.support import BaselineTools

from cs.pcs.projects import Project


class MigrateEarlyFlags:
    def run(self):
        sqlapi.SQLupdate(
            """
            cdbpcs_task SET
                start_is_early = 1,
                end_is_early = 0,
                milestone = 0
            WHERE
                milestone IS NULL
                OR milestone = 0
        """
        )
        sqlapi.SQLupdate(
            """
            cdbpcs_task SET
                start_is_early = early_position,
                end_is_early = early_position
            WHERE milestone != 0
        """
        )


class CreateProjectBaselines:
    """
    This release includes changes to the task scheduling algorithm.
    To communicate changes to project managers,
    baselines are created for all new and active projects.

    NOTE: You have to run this update manually.
    """

    __baseline_name__ = "Scheduled before cs.pcs 15.8.0"
    __baseline_comment__ = (
        "This baseline contains the schedule computed"
        " before the update to cs.pcs 15.8.0."
        " Use it to discover scheduling changes."
    )
    __active_statuses__ = [
        Project.NEW.status,
        Project.EXECUTION.status,
        Project.FROZEN.status,
    ]

    def __init__(self, baseline_name=None, baseline_comment=None):
        self.baseline_name = baseline_name or self.__baseline_name__
        self.baseline_comment = baseline_comment or self.__baseline_comment__

    def run(self):
        active_projects = Project.SQL(
            f"""
            SELECT proj.*
            FROM (
                SELECT * FROM cdbpcs_project
                WHERE ce_baseline_id = ''
                    AND status IN
                    ({', '.join([str(status) for status in self.__active_statuses__])})
            ) proj
            LEFT JOIN ce_baseline bl
                ON proj.cdb_object_id = bl.ce_baselined_object_id
                AND bl.ce_baseline_name = '{self.baseline_name}'
            WHERE bl.cdb_object_id IS NULL
            """
        )
        if not active_projects:
            sys.stderr.write("no new or active projects without 15.8 baseline found\n")
            sys.exit(1)

        pbar = progress.ProgressBar(
            maxval=len(active_projects),
            prefix="create baselines",
        )
        pbar.show()

        for project in active_projects:
            BaselineTools.create_baseline(
                obj=project,
                name=self.baseline_name,
                comment=self.baseline_comment,
            )
            project.recalculate()
            pbar += 1
            pbar.show()

        print(
            f"created baselines for {len(active_projects)} new/active"
            " projects and rescheduled them"
        )


class CreateProjectBaselinesNotification:
    def run(self):
        protocol.logWarning(
            "Please run cs.pcs.projects.updates.v15_8_1 manually"
            " to create baselines for active projects"
            " as described in the release notes."
        )


class EnsureSharingGroups:
    "E070274; moved configuration from cs.sharing to cs.pcs.projects"

    def run(self):
        updutils.install_objects(
            module_id="cs.pcs.projects",
            objects=[
                ("cdb_pyrule", {"name": "cs.sharing: Project Roles"}),
                (
                    "cdb_sharing_group",
                    {"cdb_object_id": "7c7bb300-99b5-11e5-89b1-00aa004d0001"},
                ),
                (
                    "cdb_sharing_group",
                    {"cdb_object_id": "989c2b4f-99b5-11e5-8904-00aa004d0001"},
                ),
            ],
        )


pre = []
post = [MigrateEarlyFlags, CreateProjectBaselinesNotification, EnsureSharingGroups]


if __name__ == "__main__":
    CreateProjectBaselines().run()
