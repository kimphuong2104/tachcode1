#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Service for running system tasks

- Whenever a system task's status is changed to EXECUTION, a job is enqueued in the message queue
- When the queue runs a job, it will do so in a subprocess
  (that impersonates the workflow starter for checking access rights correctly)
- The subprocess (implemented in task_external_process.py)
  then runs the system task implementation (see systemtasks.py)
"""

import logging
import pathlib
import sys
import cdbwrapc

from cdb import CADDOK
from cdb import dberrors
from cdb import dbutil
from cdb import ddl
from cdb import misc
from cdb import mq
from cdb import rte
from cdb import util
from cdb.objects import org
from cdb.objects.operations import operation
from cdb.plattools import killableprocess

from cs.workflow import processes
from cs.workflow import protocols
from cs.workflow import tasks
from cs.workflow.systemtasks import InfoMessage

__all__ = [
    'WFQueue',
    'SystemTaskJob',
    'wfqueue',
]

PROGRAM = "WFQUEUE"
SCRIPT = pathlib.Path(__file__, "..", "task_external_process.py").resolve()


def getLogger():
    return logging.getLogger(PROGRAM)


class WFQueue(mq.Queue):

    @dbutil.with_reconnect()
    def cli(self, argv):
        self.language = CADDOK.ISOLANG
        logging.info("WFServer starting with language '%s'", self.language)
        super().cli(argv)


class SystemTaskJob(mq.Job):
    def fail(self, process, exception):
        logging.exception("wfqueue")
        title = str(util.ErrorMessage("cdbwf_system_task_failed"))
        exception_text = str(exception)
        # pause wf and notify wf owners
        process.setOnhold()
        process.addProtocol(f"{title}\n\n{exception_text}", protocols.MSGREFUSE)
        self.notify_subjects(
            title,
            exception_text,
            (process.started_by, "Person"),
            (process.subject_id, process.subject_type),
        )
        super().fail(1, exception_text)

    def owner_inactive(self, process):
        # pause wf and notify wf admins
        process.setOnhold()
        self.notify_subjects(
            str(
                util.ErrorMessage(
                    "cdbwf_workflow_paused_admin",
                    process.started_by,
                )
            ),
            str(
                util.ErrorMessage("cdbwf_workflow_paused_admin_desc")
            ),
            ("cdbwf: Process Administrator", "Common Role"),
        )

    def get_user_to_impersonate(self, user_id):
        user = org.User.ByKeys(user_id)

        if not user:
            logging.error("user '%s' does not exist", user_id)
            return None

        is_active, reason = cdbwrapc.check_account(user.login, CADDOK.ISOLANG)

        if is_active:
            return user

        logging.error("user '%s' is invalid: '%s'", user_id, reason)
        return None

    def notify_subjects(self, title, description, *subjects):
        kwargs = {
            "is_active": 1,
            "cdb_process_id": self.cdb_process_id,
            "task_id": self.task_id,
            "title": title,
            "description": description,
        }

        handled = set()

        for subject in subjects:
            if subject in handled:
                continue

            kwargs["subject_id"], kwargs["subject_type"] = subject
            operation("CDB_Create", InfoMessage, **kwargs)
            handled.add(subject)

    def run(self):
        cdbwrapc.clearUserSubstituteCache()
        process = processes.Process.ByKeys(cdb_process_id=self.cdb_process_id)

        if process and process.status == processes.Process.EXECUTION.status:
            user = self.get_user_to_impersonate(process.started_by)

            if user:
                args = [
                    rte.runtime_tool("powerscript"),
                    "--program-name", PROGRAM,
                    "--user", user.login,
                    "--language", self.queue.language,
                    str(SCRIPT),
                    self.cdb_process_id,
                    self.task_id,
                ]
                logging.debug("wfqueue args: %s", args)
                try:
                    killableprocess.check_output(args)
                except killableprocess.CalledProcessError as exc:
                    self.fail(process, exc.output.decode('utf-8'))

            else:
                self.owner_inactive(process)
        else:
            logging.error(
                "process '%s' does not exist or is not running",
                self.cdb_process_id,
            )

        self.done()


wfqueue = WFQueue(
    "wfqueue",
    SystemTaskJob,
    fieldlist=[
        ddl.Char(
            "cdb_process_id",
            processes.Process.cdb_process_id.length),  # @UndefinedVariable
        ddl.Char(
            "task_id",
            tasks.SystemTask.task_id.length)])  # @UndefinedVariable


def initialize_tool():
    rte.environ["CADDOK_TOOL"] = PROGRAM.lower()
    config = pathlib.Path(
        rte.environ["CADDOK_BASE"],
        "etc",
        f"{rte.environ['CADDOK_TOOL']}.conf",
    )

    try:
        config = config.resolve()
        rte.exec_config_script(str(config))
    except pathlib.os.error:
        pass  # configuration does not exist

    misc.cdblog_exit("")
    misc.cdblog_init(rte.environ["CADDOK_TOOL"], "", "")


def main(argv):
    initialize_tool()

    while 1:
        try:
            sys.exit(wfqueue.cli(argv))
        except dberrors.DBConnectionLost:
            logging.warning("database connection lost")
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main(sys.argv)
