# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

from __future__ import absolute_import
__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os
import itertools

from cdb import rte
from cdb import sig
from cdb import misc
from cdb import tools

from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.web.components.plugin_config import Csweb_plugin

from cs.tools.semanticlinks import SemanticLinkType
from cdb.platform.mom.entities import Class
COMPONENTNAME = "cs-tools-semanticlinks-linkgraph"
THREED_AVAILABLE = None


def _threed_available():
    global THREED_AVAILABLE
    if THREED_AVAILABLE is None:
        try:
            import cs.threed
            THREED_AVAILABLE = True
        except ImportError:
            THREED_AVAILABLE = False
    return THREED_AVAILABLE


class LinkGraphApp(BaseApp):
    client_favicon = "cdb_link_graph"

    def update_app_setup(self, app_setup, model, request):
        super(LinkGraphApp, self).update_app_setup(app_setup, model, request)
        semanticlinktypes = SemanticLinkType.Query("invalid = 0").Execute()
        link_types = ["Contains / Contained in"]
        for slt in semanticlinktypes:
            if slt.gen_mirror_link:
                if "%s / %s" % (slt.name, slt.MirrorLinkType.name) in link_types:
                    continue
                elif "%s / %s" % (slt.MirrorLinkType.name, slt.name) in link_types:
                    continue
                else:
                    link_types.append("%s / %s" % (slt.name, slt.MirrorLinkType.name))
            else:
                if slt.name not in link_types:
                    link_types.append(slt.name)

        clnames = list(set(semanticlinktypes.subject_object_classname + semanticlinktypes.object_object_classname))
        classnames = []
        for classname in clnames:
            c = Class.ByKeys(classname)
            if not c: continue
            classnames.append([c.beschriftung, classname])
        app_setup.merge_in([COMPONENTNAME], {
            "link_types": link_types,
            "classnames": classnames
        })
        plg_config = {}
        plg_libs = []
        plg_setup = []
        cfg_entries = []
        ctx_name = "cs-semanticlinks-linkgraph-desc"
        for entry in Csweb_plugin.get_plugin_config(ctx_name):
            cfg_entries.append({'discriminator': entry.get('discriminator'),
                                'component': entry.get('component')})
            for name, version in entry.get("libraries", []):
                if name.startswith("cs-threed-hoops") and not _threed_available():
                    continue
                plg_libs.append((name, version))
            fqpyname = entry.get("setup")
            if fqpyname is not None:
                try:
                    plg_setup.append(tools.getObjectByName(fqpyname))
                except ImportError as e:
                    misc.log_error("ConfigurableUIModel: Could not import setup"
                                   " function '%s': %s" % (fqpyname, e))
            plg_config[ctx_name] = cfg_entries
            app_setup.update(pluginConfiguration=plg_config)
            for fct in plg_setup:
                fct(model, request, app_setup)
            for name, version in itertools.chain(plg_libs):
                request.app.include(name, version)


@Root.mount(app=LinkGraphApp, path="/cs-tools-semanticlinks-linkgraph")
def _mount_app():
    return LinkGraphApp()


@LinkGraphApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Link Graph"


@LinkGraphApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-activitystream-web", "15.1.0")
    request.app.include("cs-tools-semanticlinks-createLinksApp", "0.0.1")
    request.app.include(COMPONENTNAME, "0.0.1")
    return "cs-tools-semanticlinks-linkgraph-MainComponent"


@LinkGraphApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(COMPONENTNAME, "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-tools-semanticlinks-linkgraph.js")
    lib.add_file("cs-tools-semanticlinks-linkgraph.js.map")
    static.Registry().add(lib)
