#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
CONTACT Elements Update-Task
"""

from __future__ import absolute_import

import logging


class RebuildPostingIndex(object):
    """Rebuild index of postings due to changing indexed date"""

    def run(self):
        log = logging.getLogger(__name__)

        from cdb.platform.mom.entities import Class

        log.info("Creating index jobs for postings")
        Class.updateSearchIndexByClassname("cdbblog_user_posting", low_priority=True)


pre = []
post = [RebuildPostingIndex]


if __name__ == "__main__":
    RebuildPostingIndex().run()
