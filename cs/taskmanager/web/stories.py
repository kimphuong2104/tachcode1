#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
React storybook
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.taskmanager.web.main import APPNAME, APPVERSION
from cs.web.components.storybook.main import add_stories

STORIES_APP = "{}-stories".format(APPNAME)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    stories = static.Library(
        STORIES_APP, APPVERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )

    stories.add_file("{}.js".format(STORIES_APP))
    stories.add_file("{}.js.map".format(STORIES_APP))

    static.Registry().add(stories)
    add_stories(
        (APPNAME, APPVERSION),
        (STORIES_APP, APPVERSION),
    )
