#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.taskmanager.updates.v15_4_1_1 import revert_deleted_patch


class EnsureMessageUpdate(object):
    __table_name__ = "meldungen"
    __meldung_label__ = "cs_tasks_delegate"

    def run(self):
        revert_deleted_patch(
            "cs.taskmanager",
            "meldungen",
            meldung_label="cs_tasks_delegate",
        )


pre = []
post = [EnsureMessageUpdate]
