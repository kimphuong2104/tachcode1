#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.taskmanager.updates import compile_headers


class CompileHeaders(object):
    """
    obsolete join on read_status has been removed;
    compile cs_tasks_headers_v to speed up taskmanager
    """

    def run(self):
        compile_headers()


pre = []
post = [CompileHeaders]
