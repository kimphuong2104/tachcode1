# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Module files

This is the documentation for the files module.
"""

from cdb.objects import ByID
from cdb.objects.cdb_file import CDB_File
from cdb.sig import connect, emit

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = [
    'check_file_modification_post',
    'check_file_modification_pre',
    'watch_content_change',
]


@connect("wf_briefcase_content_change")
def watch_content_change(self, ctx, briefcase=None):
    """
    If the object (self) itself and/or its parent (in case self is a file
    object) is contained in a briefcase of a running task, then an entry
    in the process's protocol is made and notifications are send. If a
    briefcase isn't given, then all processes are iterated for matching
    briefcases.
    If objects of other modules are used as briefcase content and are
    considered worth being watched via protocol and notification, then
    modifications of these objects should be made public by emitting the
    signal 'wf_briefcase_content_change'.
    """
    from cs.workflow.briefcases import Briefcase
    from cs.workflow.tasks import InteractiveTask

    if briefcase:
        briefcases = [briefcase]
    else:
        briefcases = Briefcase.ByContent(self.cdb_object_id)

        # If a file has been modified, find also the briefcases
        # of its referring object
        if hasattr(self, "cdbf_object_id"):
            briefcases.extend(Briefcase.ByContent(self.cdbf_object_id))

    running_tasks = []
    for x in briefcases:
        x.notify_content_change()
        running_tasks.extend(
            InteractiveTask.get_running_tasks_by_briefcase(x))

    for task in list(set(running_tasks)):
        if not hasattr(self, "cdbf_object_id"):
            setattr(ctx, 'content_change_bobject', self)
        else:
            setattr(ctx, 'content_change_file', self)
            setattr(ctx, 'content_change_bobject', ByID(self.cdbf_object_id))
        task.sendNotification(ctx)


@connect(CDB_File, "modify", "pre")
def check_file_modification_pre(self, ctx):
    # we get here whenever a file gets uploaded via web gui or wsm
    # (actually whenever any file gets modified in cdb)
    # HACK: wsm modifies files 3 times. 2 times without changing the
    # 'cdb_mdate', but we don't want 3 protocol entries
    ctx.keep('cdb_mdate_old', ctx.object.cdb_mdate)


@connect(CDB_File, "modify", "post")
def check_file_modification_post(self, ctx):
    from cs.workflow.misc import is_auxiliary_file, is_converted_file
    # HACK: see 'check_file_modification_pre' above
    if ctx.ue_args['cdb_mdate_old'] == ctx.object.cdb_mdate:
        return
    # skip 'unimportant' files
    if is_converted_file(self) or is_auxiliary_file(self):
        return
    emit("wf_briefcase_content_change")(self, ctx)
