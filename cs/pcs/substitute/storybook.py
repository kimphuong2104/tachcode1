# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.web.components.storybook.main import add_stories

from cs.pcs.substitute.main import APP, VERSION

STORIES_APP = f"{APP}-stories"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    stories = static.Library(
        STORIES_APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    stories.add_file(f"{STORIES_APP}.js")
    stories.add_file(f"{STORIES_APP}.js.map")
    static.Registry().add(stories)
    add_stories((APP, VERSION), (STORIES_APP, VERSION))
