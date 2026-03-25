#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.static import Registry
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK
from cs.web.components.storybook.main import add_stories

from cs.objectdashboard.config import DASHBOARD_LAYOUTS, Widget
from cs.objectdashboard.dashboard.internal import (
    ContextObjectDashboardConfig,
    InternalDashboardApp,
)
from cs.pcs.projects.common.web import get_url_patterns

APP = "cs-objectdashboard-dashboard"
STORIES_APP = f"{APP}-stories"
VERSION = "15.1.0"


def getLogger():
    return logging.getLogger(__name__)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _():
    for component in [APP, STORIES_APP]:
        lib = static.Library(
            component, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
        )
        lib.add_file(f"{component}.js")
        lib.add_file(f"{component}.js.map")
        static.Registry().add(lib)

    add_stories((APP, VERSION), (STORIES_APP, VERSION))


def get_app_url_patterns(request):
    internal_app = InternalDashboardApp.get_app(request)
    models = [
        ("configURL", ContextObjectDashboardConfig, ["context_object_id"]),
    ]
    return get_url_patterns(request, internal_app, models)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def _(app_setup, request):
    app_setup.merge_in([APP], {"layouts": DASHBOARD_LAYOUTS})


def collect_tile_libraries():
    """
    Emit signal ``cs.objectdashboard.dashboard.GET_OBJECT_DASHBOARD_LIBS`` to
    get all registered Javascript libraries for the object dashboard.

    This is only required for libraries providing tiles for widgets in other
    libraries, usually in customer modules.

    Custom libraries can be registered like this:

    .. code-block :: python

        from cdb import sig
        from cs.objectdashboard.dashboard import GET_OBJECT_DASHBOARD_LIBS

        @sig.connect(GET_OBJECT_DASHBOARD_LIBS)
        def register_tile_libraries():
            "Register JS lib (always in newest version available)"
            return ["custom-plm-widgets"]
    """
    from cs.objectdashboard.dashboard import GET_OBJECT_DASHBOARD_LIBS

    result = set(["cs-objectdashboard-widgets"])

    for libs in sig.emit(GET_OBJECT_DASHBOARD_LIBS)():
        try:
            result.update(libs)
        except TypeError:
            getLogger().error(
                "failed to register libraries '%s' (not an iterable)", libs
            )

    return result


def dashboard_outlet_setup(model, request, app_setup):
    reg = Registry()

    # NOTE [via 28-11-2018]: Some plugins require other libraries, since they are only wrappers over
    # some other react component defined elswere. At the moment there is no platform support for
    # library dependencies. This will come in a future release.
    #
    # We add here a hack to load these dependencies before the plugins. The only other solutions are:
    #  - The DependentLibrary from Bor which forcefully loads the dependencies. This has problems if these
    # dependencies are loaded again by a tab definition for example (like for diagram). In particular the
    # Sagas are twice defined and all ajax request are done twice with no way to fix it.
    #  - Dummy dashboard components that only exist to load the dependencies. This require a lot of work to
    # make sure that the user doesn't see them.
    #  - An extra json attribute for Widget which defines dependencies.
    #
    # The last option is the cleanest but since we only need a temporary workaround, we hard-code them here.

    dependencies = collect_tile_libraries()

    for dep in dependencies:
        try:
            request.app.include(dep, reg.getall(dep)[0].version)
        except IndexError:
            pass

    for lib, _ in Widget.get_libraries():
        request.app.include(lib, reg.getall(lib)[0].version)
