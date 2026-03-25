#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb.comparch import protocol
from cs.taskmanager import TaskHeaders


def compile_headers():
    try:
        TaskHeaders.compileToView(fail=True)
    except:  # noqa: E722 # pylint: disable=bare-except
        logging.exception("Failed to compile task headers")
        protocol.logError(
            "Failed to compile task headers. Please run"
            " 'cs.taskmanager.TaskHeaders.compileToView' manually"
        )
