#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

from cdb import sqlapi

from cs.workflow import processes
from cs.workflow import briefcases

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class SetExtendsRights(object):
    """ Update task to set the attribute extends_rights of briefcase links to
        system tasks. This should be always false.
    """
    def run(self):
        condition = briefcases.BriefcaseLink.extends_rights.not_one_of(0, "0")  # @UndefinedVariable
        brlinks = briefcases.BriefcaseLink.Query(condition)

        for brlink in brlinks:
            if brlink.Task and brlink.Task.isSystemTask:
                brlink.extends_rights = 0


class SetStartedBy(object):
    """ Set the attribute started_by, needed for system tasks to start
    """
    def run(self):
        condition = ("status!=%s AND "
                     "(started_by='' OR started_by IS NULL) AND "
                     "subject_type='Person'" % processes.Process.NEW.status)

        rs = sqlapi.RecordSet2(table="cdbwf_process", condition=condition)
        for record in rs:
            record.update(started_by=record.subject_id)


pre = []
post = [SetStartedBy, SetExtendsRights]

# Guard importing as main module
if __name__ == "__main__":
    SetStartedBy().run()
    SetExtendsRights().run()
