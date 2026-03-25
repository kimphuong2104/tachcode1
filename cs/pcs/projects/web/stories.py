#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This module setups the stories for storybook.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.rest.app import get_collection_app
from cs.web.components.storybook.main import (
    STORYBOOK_APP_SETUP_HOOK,
    STORYBOOK_APP_SETUP_PATH,
    add_stories,
)

from cs.pcs.projects import Project
from cs.pcs.projects.web import APP, VERSION
from cs.pcs.projects.web.rest_app.project_structure import get_app_url_patterns

STORY = f"{APP}-stories"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    stories = static.Library(
        STORY, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    stories.add_file(f"{STORY}.js")
    stories.add_file(f"{STORY}.js.map")
    static.Registry().add(stories)
    add_stories((APP, VERSION), (STORY, VERSION))


@sig.connect(STORYBOOK_APP_SETUP_HOOK)
def _story_setup(app_setup, model, request):
    # explicitely call setup function for webdata
    # setting the url for the project structure tree backend
    links = get_app_url_patterns(request)
    app_setup.merge_in(["links"], links)
    app_setup.merge_in(
        STORYBOOK_APP_SETUP_PATH,
        {
            APP: {
                "project": request.class_link(
                    Project,
                    {"keys": "Ptest.msp.small@"},
                    app=get_collection_app(request),
                )
            }
        },
    )
