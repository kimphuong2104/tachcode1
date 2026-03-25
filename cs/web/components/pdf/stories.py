#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
This module setups the stories for storybook.
"""
from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import os
from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.platform.web.rest.app import get_collection_app
from cs.web.components.storybook.main import add_stories
from cs.web.components.storybook.main import STORYBOOK_APP_SETUP_HOOK
from cs.web.components.storybook.main import STORYBOOK_APP_SETUP_PATH
from . import setup_worker_url


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    stories = static.Library("cs-web-components-pdf-stories", "15.1.0",
                             os.path.join(os.path.dirname(__file__), "js", "build"))
    stories.add_file('cs-web-components-pdf-stories.js')
    stories.add_file('cs-web-components-pdf-stories.js.map')
    static.Registry().add(stories)
    add_stories(
        ("cs-web-components-pdf", "15.1.0"),
        ("cs-web-components-pdf-stories", "15.1.0"))


@sig.connect(STORYBOOK_APP_SETUP_HOOK)
def _story_setup(app_setup, model, request):
    app_setup.merge_in(STORYBOOK_APP_SETUP_PATH, {
        "cs-web-components-pdf": {
            "singlepage": {
                "path": "/static/powerscript/cs.web.components.pdf/storybook_test.pdf",
                "name": "model.pdf"
            },
            "multipage": {
                "path": "/static/powerscript/cs.web.components.pdf/multipage_story_test.pdf",
                "name": "specification.pdf"
            }
        }
    })
    setup_worker_url(model, request, app_setup)
