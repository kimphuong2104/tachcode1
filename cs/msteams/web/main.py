# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import urllib

from cdb import rte, sig
from cs.msteams.objects import MSTeamsASAssignment, MSTeamsChannel
from cs.platform.web import static
from cs.platform.web.root import get_v1
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK

COMPONENTNAME = "cs-msteams-web"


def _get_collection_app(request):
    return get_v1(request).child("collection")


@sig.connect(GLOBAL_APPSETUP_HOOK)
def update_app_setup(app_setup, request):
    app_setup.merge_in(
        [COMPONENTNAME],
        {
            "msteamsASAssignURL": urllib.parse.unquote(
                request.class_link(
                    MSTeamsASAssignment,
                    {
                        "keys": "",
                        "extra_parameters": {"_as_table": "ce_msteams_as_assign"},
                    },
                    app=_get_collection_app(request),
                )
                + "&$filter=as_channel_id eq '${topic_id}'"
            ),
            "teamsChannelURL": urllib.parse.unquote(
                request.class_link(
                    MSTeamsChannel,
                    {"keys": "${channel_id}"},
                    app=_get_collection_app(request),
                )
            ),
        },
    )


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-msteams-web",
        "15.8.0",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-msteams-web.js")
    lib.add_file("cs-msteams-web.js.map")
    static.Registry().add(lib)
