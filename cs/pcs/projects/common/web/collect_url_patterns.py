#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Run `powerscript -m cs.pcs.projects.common.web.collect_url_patterns`
to update `url_patterns.json` (URL patterns available in the frontend).

Note: There is an integration test that will run this and update
`url_patterns.json`.
This means if everyone runs the tests before committing, the file will always
be up to date (if new modules have been added here, that is).
"""

import json
import logging
import os
from urllib.parse import urlsplit

from cdb.tools import getModuleHandle
from cs.platform.web.root.main import _get_dummy_request

APPS = [
    # cs.pcs.msp.web.imports.main is used in isolation, so excluded here
    # so are "new from template" operations
    "cs.objectdashboard.dashboard.webapp",
    "cs.objectdashboard.widgets.widget_rest_app",
    "cs.pcs.checklists.web",
    "cs.pcs.efforts.web.rest_app",
    "cs.pcs.projects.common.web",
    "cs.pcs.projects.common.webdata",
    "cs.pcs.projects.web.rest_app.project_structure",
    "cs.pcs.projects.web",
    "cs.pcs.substitute.main",
    "cs.pcs.timeschedule.web.main",
    "cs.pcs.widgets.widget_rest_app",
    "cs.pcs.projects.common.indicators",
    "cs.pcs.projects_documents.web.rest_app",
]


def make_links(apps):
    request = _get_dummy_request("/")
    result = {}

    for fqpyname in apps:
        module = getModuleHandle(fqpyname)
        try:
            app, links = module.APP, module.get_app_url_patterns(request)
        except AttributeError:
            logging.exception("[ ERROR ] %s", module)

        for label in links:
            result[f"{app}@{label}"] = links[label]

    return result


def make_relative_links(apps):
    links = make_links(apps)

    for label, url in links.items():
        try:
            parts = urlsplit(url)
        except (TypeError, ValueError):
            logging.exception(
                "[ ERROR ] unexpected value for '%s': %s",
                label,
                url,
            )
            raise
        links[label] = parts.path

    return links


def write_url_patterns():
    filepath = os.path.join(
        os.path.dirname(__file__),
        "js",
        "src",
        "url_patterns.json",
    )
    links = make_relative_links(APPS)

    with open(filepath, "w", encoding="utf8") as fileobj:
        json.dump(links, fileobj, indent=4, sort_keys=True)
        fileobj.write("\n")


if __name__ == "__main__":
    write_url_patterns()
