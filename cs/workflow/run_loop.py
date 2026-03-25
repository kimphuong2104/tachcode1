#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
"Run Loop" system task implementation
"""

from cdb import cdbuuid
from cdb import constants
from cdb import sqlapi
from cdb import util
from cdb.objects import operations
from cs.activitystream.objects import Topic2Posting
from cs.workflow.misc import sync_global_briefcases
from cs.workflow.processes import Process
from cs.workflow.systemtasks import CloseTaskAsynchronously
from cs.workflow.systemtasks import TaskCancelledException
from cs.workflow.tasks import Task


def get_prefixed_log_msg(cycle, msg):
    """
    :param cycle: The cycle the log message is referring to.
    :type cycle: cs.workflow.processes.Process

    :param msg: The raw log message.
    :type msg: basestring

    :returns: Log message ``msg`` with prefix identifying ``cycle``.
    :rtype: basestring
    """
    label = util.get_label("cdbwf_aggregate_protocol")
    return label.format(
        cycle.current_cycle,
        cycle.cdb_process_id,
        msg
    )


def get_briefcases_by_name(briefcases):
    """
    :param briefcases: Briefcases to index by name for quick access inside a
        code loop.
    :type briefcases: cdb.objects.ObjectCollection of
        cs.workflow.briefcases.Briefcase

    :returns: dict containing ``briefcases`` indexed by their name (which has
        to be unique among ``briefcases``).
    """
    return {
        briefcase.name: briefcase
        for briefcase in briefcases
    }


def add_activity_topic(source, target):
    """
    adds ``target`` as topic to all postings of ``source`` (if necessary)

    also see `GetActivityStreamTopics` of classes `cs.workflow.tasks.Task` and
    `cs.workflow.processes.Process`, which make sure asynchronously-generated
    AS postings are synced upstream
    """
    for t in Topic2Posting.KeywordQuery(topic_id=source.cdb_object_id):
        vals = {
            "posting_id": t.posting_id,
            "topic_id": target.cdb_object_id,
        }
        if not Topic2Posting.KeywordQuery(**vals):
            t.Copy(topic_id=target.cdb_object_id)


def copy_briefcase_content(task, source_briefcase, target_briefcase):
    """
    Make sure ``target_briefcase`` contains at least all contents of
    ``source_briefcase``.

    :param task: Parent task. Only used for error logging.
    :type task: cs.workflow.tasks.SystemTask

    :param source_briefcase: Briefcase to copy contents from.
    :type source_briefcase: cs.workflow.briefcases.Briefcase

    :param target_briefcase: Briefcase to copy contents into.
    :type target_briefcase: cs.workflow.briefcases.Briefcase
    """
    if target_briefcase:
        existing_content = [
            c.cdb_object_id
            for c in target_briefcase.Content
        ]

        for source_content in source_briefcase.FolderContents:
            if source_content.cdb_content_id not in existing_content:
                source_content.Copy(
                    cdb_folder_id=target_briefcase.cdb_object_id
                )
    else:
        msg = util.get_label("cdbwf_parent_briefcase_missing") % (
            source_briefcase.name
        )
        task.addProtocol(msg)


def syncBriefcasesToCycle(parent, cycle):
    """
    Copy briefcases from ``parent`` to ``cycle``, including contents.

    .. note ::

        By default, only local briefcases are synced between workflows.
        Set the environment variable :envvar:`CADDOK_WORKFLOW_SYNC_GLOBALS`
        to "True" to also sync global briefcases.

    :param parent: Run loop task.
    :type parent: cs.workflow.tasks.systemtask

    :param cycle: One of the run loop task's cycles.
    :type cycle: cs.workflow.processes.Process
    """
    msg = util.get_label("cdbwf_syncing_briefcases") % (
        parent.GetDescription(),
        cycle.GetDescription(),
    )
    parent.addProtocol(get_prefixed_log_msg(cycle, msg))

    cycle_briefcases = get_briefcases_by_name(cycle.AllBriefcases)
    cycle_bc_names = set(cycle_briefcases.keys())

    briefcases_to_sync = parent.BriefcaseLinks  # parent's local briefcases

    if sync_global_briefcases():
        # also sync global briefcases in parent's workflow
        briefcases_to_sync += parent.Process.BriefcaseLinks

    for parent_link in briefcases_to_sync:
        target_briefcase = None

        if parent_link.Briefcase.name not in cycle_bc_names:
            # copy missing briefcases and links
            target_briefcase = parent_link.Briefcase.Copy(
                cdb_process_id=cycle.cdb_process_id
            )
            parent_link.Copy(
                cdb_process_id=cycle.cdb_process_id,
                task_id=''
            )
        else:
            target_briefcase = cycle_briefcases.get(
                parent_link.Briefcase.name,
                None
            )

        copy_briefcase_content(
            parent,
            parent_link.Briefcase,
            target_briefcase
        )

    cycle.Reload()


def aggregateProtocol(cycle, parent):
    """
    Copy log entries of (previous) cycle to parent loop task.

    :param cycle: One of the run loop task's cycles.
    :type cycle: cs.workflow.processes.Process

    :param parent: Run loop task.
    :type parent: cs.workflow.tasks.systemtask
    """
    for protocol in cycle.Protocols:
        msg = get_prefixed_log_msg(
            cycle,
            protocol.description
        )
        protocol.Copy(
            cdb_process_id=parent.cdb_process_id,
            cdbprot_sortable_id=cdbuuid.create_sortable_id(),
            task_id=parent.task_id,
            description=msg
        )


def syncBriefcasesFromCycle(cycle, parent):
    """
    Copy the contents of all briefcases of ``cycle`` with briefcase_id other
    than ``0`` (reserved for "Attachments") to local briefcases of ``parent``
    of the same name. Briefcases themselves are not copied.

    .. note ::

        If the environment variable :envvar:`CADDOK_WORKFLOW_SYNC_GLOBALS`
        is set to "True", global briefcases (including "Attachments")
        are also synchronized.

    :param parent: Run loop task.
    :type parent: cs.workflow.tasks.systemtask

    :param cycle: One of the run loop task's cycles.
    :type cycle: cs.workflow.processes.Process
    """
    include_globals = sync_global_briefcases()

    msg = util.get_label("cdbwf_syncing_briefcases") % (
        cycle.GetDescription(),
        parent.GetDescription(),
    )
    parent.addProtocol(get_prefixed_log_msg(cycle, msg))

    if include_globals:
        source_briefcases = cycle.AllBriefcases
        parent_briefcases = get_briefcases_by_name(
            parent.Process.AllBriefcases
        )
    else:
        source_briefcases = cycle.AllBriefcases.Query("briefcase_id != 0")
        parent_briefcases = get_briefcases_by_name(parent.Briefcases)

    for source_briefcase in source_briefcases:
        target_briefcase = parent_briefcases.get(
            source_briefcase.name,
            None
        )
        copy_briefcase_content(
            parent,
            source_briefcase,
            target_briefcase
        )

    parent.Reload()


class RunLoopSystemTaskImplementation(object):
    def __init__(self, task, current_cycle, max_cycles):
        """
        Subworkflow/loop system task implementation. The ``current_cycle``
        number has already been increased at this time.

        :param task: The task object to handle.
        :type task: cs.workflow.tasks.SystemTask

        :param current_cycle: Current cycle's number (already increased,
            allowed range is 1..(max_cycles + 1)).
        :type current_cycle: int (or castable to int)

        :param max_cycles: Maximum number of cycles allowed for this task.
        :type max_cycles: int (or castable to int)

        :raises RuntimeError: If no cycle exists.

        :raises util.ErrorMessage: If either task or its process is not in
            status ``EXECUTION``.
        """
        self.task = task
        self.current_cycle = int(current_cycle)
        self.max_cycles = int(max_cycles)
        self.cycle = self.task.CurrentCycle

    def run(self):
        if self.task.status != Task.EXECUTION.status:
            raise util.ErrorMessage("cdbwf_task_not_ready")

        if self.task.Process.status != Process.EXECUTION.status:
            raise util.ErrorMessage("cdbwf_process_not_execution")

        if self.current_cycle == 1:  # first cycle, just start it
            if self.cycle:
                self.startCurrentCycle()
            else:
                raise RuntimeError(
                    util.get_label("cdbwf_no_sub_workflow")
                )
        else:  # subsequent cycles
            syncBriefcasesFromCycle(self.cycle, self.task)
            add_activity_topic(
                self.cycle,
                self.task
            )
            aggregateProtocol(self.cycle, self.task)
            if not self.checkSuccessConditions():
                self.checkFailureConditions()
                self.checkMaxCycles()
                self.createNewCycle()

    def checkMaxCycles(self):
        """
        Cancel ``self.task`` if ``self.current_cycle`` is greater than
        ``self.max_cycles``. Since ``current_cycle`` has already been
        increased, this means we just completed the last allowed cycle.
        """
        if self.current_cycle > self.max_cycles:
            raise TaskCancelledException(
                util.get_label("cdbwf_max_cycles_reached")
            )

    def startCurrentCycle(self):
        syncBriefcasesToCycle(self.task, self.cycle)

        try:
            self.cycle.activate_process()
        except Exception as ex:
            raise TaskCancelledException(
                get_prefixed_log_msg(self.cycle, str(ex))
            )
        else:
            msg = util.get_label("cdbwf_starting_cycle") % (
                self.current_cycle,
                self.cycle.GetDescription()
            )
            raise CloseTaskAsynchronously(
                get_prefixed_log_msg(self.cycle, msg)
            )

    def createNewCycle(self):
        def _copy_activities(source, target):
            # Copy Actitvity Stream Topics
            query = """
                SELECT
                    a.cdb_object_id AS old_object_id,
                    b.cdb_object_id AS new_object_id
                FROM cdbwf_task a
                INNER JOIN cdbwf_task b
                    ON a.task_id = b.task_id
                    AND a.cdb_process_id = '{source.cdb_process_id}'
                    AND b.cdb_process_id = '{target.cdb_process_id}'
            """.format(
                source=source,
                target=target
            )
            records = sqlapi.RecordSet2(sql=query)

            mapping = {
                record.old_object_id: record.new_object_id
                for record in records
            }
            mapping[source.cdb_object_id] = target.cdb_object_id

            msg = util.get_label("cdbwf_updating_activity_stream")
            self.task.addProtocol(get_prefixed_log_msg(source, msg))

            for t in Topic2Posting.KeywordQuery(topic_id=list(mapping)):
                t.Copy(topic_id=mapping[t.topic_id])

        if self.current_cycle in self.task.Cycles.current_cycle:
            msg = util.get_label("cdbwf_cycle_already_exists") % (
                self.current_cycle
            )
            raise TaskCancelledException(
                get_prefixed_log_msg(self.cycle, msg)
            )

        new_cycle = operations.operation(
            constants.kOperationCopy,
            self.cycle,
            operations.form_input(
                self.cycle,
                current_cycle=self.current_cycle,
            ),
        )

        _copy_activities(self.cycle, new_cycle)

        try:
            new_cycle.activate_process()
        except Exception as ex:
            raise TaskCancelledException(
                get_prefixed_log_msg(new_cycle, str(ex))
            )
        else:
            msg = util.get_label("cdbwf_starting_cycle") % (
                self.current_cycle,
                new_cycle.GetDescription()
            )
            raise CloseTaskAsynchronously(
                get_prefixed_log_msg(new_cycle, msg)
            )

    def _getConditions(self, name):
        return self.task.AllParameters.KeywordQuery(
            name=name,
            order_by="value ASC"  # contains position
        )

    def checkSuccessConditions(self):
        """
        Cancels ``self.task`` if it has no success condition.

        :returns: ``True`` if ``self.cycle`` matches at least one success
            condition, else ``False``.
        """
        self.task.addProtocol(
            get_prefixed_log_msg(
                self.cycle,
                util.get_label("cdbwf_checking_success_conditions")
            )
        )
        conditions = self._getConditions("success_condition")

        if not conditions:
            msg = util.get_label("cdbwf_no_success_condition")
            raise TaskCancelledException(
                get_prefixed_log_msg(self.cycle, msg)
            )

        for success_condition in conditions:
            if success_condition.Rule.match(self.cycle):
                msg = util.get_label("cdbwf_matches_success_condition") % (
                    success_condition.getRuleName()
                )
                self.task.addProtocol(
                    get_prefixed_log_msg(
                        self.cycle,
                        msg
                    )
                )
                return True

        return False

    def checkFailureConditions(self):
        """
        Cancels ``self.task`` if at least one failure condition matches
        ``self.cycle``.
        """
        self.task.addProtocol(
            get_prefixed_log_msg(
                self.cycle,
                util.get_label("cdbwf_checking_failure_conditions")
            )
        )
        conditions = self._getConditions("failure_condition")

        for failure_condition in conditions:
            if failure_condition.Rule.match(self.cycle):
                msg = util.get_label("cdbwf_matches_failure_condition") % (
                    failure_condition.getRuleName()
                )
                raise TaskCancelledException(
                    get_prefixed_log_msg(self.cycle, msg)
                )
