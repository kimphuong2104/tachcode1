#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import logging
import sys

from cdb import CADDOK, sqlapi
from cdb.platform.mom.relations import DDUserDefinedView
from cs.pcs.resources.schedule import SCHEDULE_CALCULATOR


class CompileWorkdaysView(object):
    def run(self):
        print("\ncompiling cdb_workdays_v...")
        workdays_v = DDUserDefinedView.ByKeys("cdb_workdays_v")
        workdays_v.rebuild(force=True)
        print("compiling cdb_workdays_v SUCCEEDED")


class UpdateSchedules(object):
    """recreate demand/allocation schedules for projects with demands"""

    __log_prefix__ = "UpdateSchedules"

    def run(self):
        print("\nupdating schedules...")
        query = """SELECT cdb_object_id
            FROM cdbpcs_task
            WHERE ce_baseline_id = ''
            AND (cdb_project_id, task_id) IN (
                SELECT cdb_project_id, task_id
                FROM cdbpcs_prj_demand
            )
        """
        tasks = sqlapi.RecordSet2(sql=query)
        task_uuids = [x.cdb_object_id for x in tasks]
        SCHEDULE_CALCULATOR.createSchedules_many(task_uuids)

        logging.info("%s project schedules updated", self.__log_prefix__)

        print("updating schedules FINISHED")


def main():
    CompileWorkdaysView().run()
    UpdateSchedules().run()


if __name__ == "__main__":
    print("Connected to database %s\n" % CADDOK.DBMODE)
    confirmation = input(
        "This script will update your resource schedules. Depending on how "
        "many schedules exist in your system, this may take a while.\n\n"
        "Continue (y/n)?\n"
    )
    if confirmation and confirmation in "yY":
        main()
    else:
        sys.stderr.write("user canceled\n")
        sys.exit(1)
