#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module Protocols

This is the documentation for the Protocols module.
"""

import datetime

from cdb import auth, cdbuuid, util
from cdb.objects import Forward, Object, Reference

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ['MSGCANCEL',
           'MSGDONE',
           'MSGINFO',
           'MSGSYSTEM',
           'MSGTASKREADY',
           'MSGUSER',
           'Protocol']

fProcess = Forward("cs.workflow.processes.Process")
fTask = Forward("cs.workflow.tasks.Task")
fUser = Forward("cdb.objects.org.User")

MSGCANCEL = "CANCEL"
MSGDONE = "DONE"
MSGAPPROVED = "APPROVED"
MSGINFO = "INFO"
MSGREFUSE = "REFUSE"
MSGSYSTEM = "SYSTEM"
MSGTASKREADY = "INFO"  # workaround while E026300 is open
MSGUSER = "USER"


class Protocol(Object):
    __maps_to__ = "cdbwf_protocol"
    __classname__ = "cdbwf_protocol"

    Process = Reference(1, fProcess, fProcess.cdb_process_id)
    Task = Reference(1, fTask, fTask.task_id, fTask.cdb_process_id)
    User = Reference(1, fUser, fUser.personalnummer)

    event_map = {
        (("create", "copy"), "pre_mask"): "assert_parent",
    }

    def assert_parent(self, ctx):
        # No creation of tasks out of a process context
        if not ctx.parent.get_attribute_names():
            raise util.ErrorMessage("cdbwf_create_protocol_from_wf")

    def on_create_pre_mask(self, ctx):
        self.timestamp = datetime.datetime.utcnow()
        self.personalnummer = auth.persno
        if self.task_id and self.Task:
            ctx.set('task_title', self.Task.title)

    def on_create_pre(self, ctx):
        self.msgtype = MSGUSER
        self.cdbprot_sortable_id = Protocol.MakeEntryId()

    @classmethod
    def MakeEntryId(cls):
        return cdbuuid.create_sortable_id()
