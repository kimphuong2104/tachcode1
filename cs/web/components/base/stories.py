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
from cdb.objects.org import Person
from cs.web.components.storybook.main import add_stories
from cs.web.components.storybook.main import STORYBOOK_APP_SETUP_HOOK
from cs.web.components.storybook.main import STORYBOOK_APP_SETUP_PATH


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    stories = static.Library("cs-web-components-base-stories", "15.1.0",
                             os.path.join(os.path.dirname(__file__), "js", "build"))
    stories.add_file('cs-web-components-base-stories.js')
    stories.add_file('cs-web-components-base-stories.js.map')
    static.Registry().add(stories)
    add_stories(
        ("cs-web-components-base", "15.1.0"),
        ("cs-web-components-base-stories", "15.1.0"))


@sig.connect(STORYBOOK_APP_SETUP_HOOK)
def _story_setup(app_setup, model, request):
    app_setup.merge_in(STORYBOOK_APP_SETUP_PATH, {
        "cs-web-components-base": {
            "person": request.class_link(
                Person,
                {"keys": "caddok"},
                app=get_collection_app(request))
        }
    })
