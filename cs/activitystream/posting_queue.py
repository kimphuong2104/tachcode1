#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module posting_queue

This is the documentation for the posting_queue module.
"""

from __future__ import absolute_import

import logging
import sys

import six
from cdb import mq
from cdb.objects.operations import system_args

from cs.activitystream.objects import SystemPosting

__docformat__ = "restructuredtext en"

__all__ = ["getQueue"]


class SystemPostingJob(mq.Job):
    def __init__(self, _id, queue):
        mq.Job.__init__(self, _id, queue)

    def run(self):
        self.create_posting()
        self.done()

    def create_posting(self):
        values = {}
        for field_name in SystemPosting.GetFieldNames():
            if field_name not in ("cdb_object_id", "cdb_classname"):
                values[field_name] = self.get(field_name)

        # The queue only contains cdate and cpersno.
        # mdate and mpersno should have the same value
        if "cdb_mdate" not in values and "cdb_cdate" in values:
            values["cdb_mdate"] = values["cdb_cdate"]

        if "cdb_mpersno" not in values and "cdb_cpersno" in values:
            values["cdb_mpersno"] = values["cdb_cpersno"]

        values["is_deleted"] = 0

        # because the creator of the posting is not the queue but
        # the person that has created the job
        sys_args = system_args(keepchangecontrolattrs="1")
        return SystemPosting.do_create(sys_args, **values)


_SYS_POSTING_QUEUE = None


def getQueue():
    global _SYS_POSTING_QUEUE  # pylint: disable=global-statement
    if _SYS_POSTING_QUEUE is None:
        _SYS_POSTING_QUEUE = mq.Queue(
            "system_posting", SystemPostingJob, fieldlist=[]
        )  # db schema is created using the Data Dictionary
    return _SYS_POSTING_QUEUE


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)-8s] [%(name)s] %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    arguments = [six.ensure_str(arg) for arg in sys.argv]
    sys.exit(getQueue().cli(arguments))
