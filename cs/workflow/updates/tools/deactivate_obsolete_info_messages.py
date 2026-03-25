# coding: utf-8
"""
Migration script to deactivate info messages belonging to canceled or failed
workflows that are not part of the workflow's completion task.

Corresponds to what the cdb_setting "cs.workflow", "cancel_info_on_failure"
does if set to "1".
"""
from cdb import progress
from cdb import sqlapi
from cdb.objects import paginated

from cs.workflow.processes import Process

PAGESIZE = 20


def update_info_messages():
    processes = Process.KeywordQuery(status=[Process.CANCELLED.status,
                                             Process.DISMISSED.status])
    stmt = "SELECT COUNT(*) amount FROM {} WHERE {}".format(
        processes._table, processes._condition)

    amount = 0

    for x in sqlapi.RecordSet2(sql=stmt):
        amount = x.amount

    pbar = progress.ProgressBar(maxval=amount)
    pbar.show()

    for page in paginated(processes, pagesize=PAGESIZE):
        for process in page:
            process._cancel_info_messages()
            pbar += 1

        pbar.show()


if __name__ == "__main__":
    update_info_messages()
