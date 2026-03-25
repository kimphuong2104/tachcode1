#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from cs.web.components.library_config import Libraries

OPTIONAL_PLUGINS = ["cs-tasks-documents-plugin"]


def add_optional_libraries(model, request, app_setup):
    for plugin in OPTIONAL_PLUGINS:
        lib = Libraries.ByKeys(plugin)
        if lib:
            request.app.include(lib.library_name, lib.library_version)
            logging.info("added optional plugin '%s'", plugin)
        else:
            logging.info("skipping optional plugin '%s' (not found)", plugin)
