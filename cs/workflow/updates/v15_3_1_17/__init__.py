# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This update script adds a Sequential Taskgroup as a parent to all parallel tasks
if desired.

This update script does not use "iterate(big)", because the function SchemaComponent.Query()
in connection with "iterate(big)", unfortunately processes objects several times, so that it
comes to incorrect updates. For this reason it is assumed that a 64-bit architecture
is available or that there are not so many workflow tasks.
"""

from cdb import sqlapi
from cdb import transaction
from cdb import util
from cdb.comparch import protocol
from cs.workflow import taskgroups
from cs.workflow import tasks
from cs.workflow.taskgroups import TaskGroup
from cs.workflow.taskgroups import SequentialTaskGroup
from cs.workflow.schemacomponents import SchemaComponent

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


class OptionalMigrateParallelTasksToSequentialTasks(object):
    def run(self):
        query = """
            SELECT * FROM cdbwf_task AS task WHERE parent_id IN
            (SELECT task_id FROM cdbwf_task AS parent WHERE parent.cdb_process_id = task.cdb_process_id
            AND cdb_classname = 'cdbwf_aggregate_parallel')
            AND NOT cdb_classname = 'cdbwf_aggregate_sequential'
        """

        # This SQL command returns all tasks which have a parallel task group as parent.
        tasks_in_parallel_squence = SchemaComponent.SQL(query)

        # For every task a seqential task group will be created.
        for task in tasks_in_parallel_squence:
            with transaction.Transaction():
                new_sequential_taskgroup = SchemaComponent.Create(
                                                    task_id=TaskGroup.new_aggregate_number(),
                                                    cdb_process_id=task.cdb_process_id,
                                                    parent_id=task.parent_id,
                                                    position=task.position,
                                                    title="Sequential task group",
                                                    status=0,
                                                    cdb_status_txt="New",
                                                    cdb_objektart="cdbwf_aggregate",
                                                    cdb_classname="cdbwf_aggregate_sequential",
                                                    process_is_onhold=int(0))

                task.Update(parent_id=new_sequential_taskgroup.task_id, position=10)

            protocol.logMessage(
                "Sequential task group successfully created for task {} in process {}".format(task.task_id, task.cdb_process_id)
            )

pre = []
post = []

if __name__ == '__main__':
    update = OptionalMigrateParallelTasksToSequentialTasks()
    update.run()
