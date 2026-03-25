# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z kbu $"

import os

from cdb import rte
from cdb import sig
from cdb.comparch import tools
from cdb.comparch.modules import Module
from cdb.comparch.patches import ModulePatch
from cdb.comparch.protocol import ModuleConflict
from cdb.util import get_label

from cs.platform.web import static
from cs.platform.web.root import Internal

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

COMPARCH_APP_PATH = "cs-admin/comparch"
COMPARCH_API_PATH = "%s-api" % COMPARCH_APP_PATH
COMPARCH_APP_FULLPATH = "/internal/%s" % COMPARCH_APP_PATH
COMPARCH_API_FULLPATH = "/internal/%s" % COMPARCH_API_PATH
COMPARCH_APP_NAMESPACE = "cs-admin-comparch_app"
COMPARCH_APP_VERSION = "15.8.0"

COMPARCH_UNASSIGNED_OBJECTS = "unassigned_objects"
COMPARCH_UNASSIGNED_OBJECTS_DETAIL = "unassigned_objects_detail"
COMPARCH_MODULE_CONTENT = "module_content"
COMPARCH_MODULE_CONTENT_DETAIL = "module_content_detail"


class ComparchApp(BaseApp):

    def update_app_setup(self, app_setup, model, request):
        super(ComparchApp, self).update_app_setup(app_setup, model, request)
        app_setup.merge_in(["links", "cs-admin"], {
            "comparch_api": COMPARCH_API_FULLPATH
        })


class ComparchModel(BaseModel):

    def __init__(self, extra_parameters):
        super(ComparchModel, self).__init__()
        self.extra_parameters = extra_parameters
        self.mode = self.extra_parameters.get("mode")


@ComparchApp.path(path='/', model=ComparchModel)
def get_model(extra_parameters):
    return ComparchModel(extra_parameters)


@Internal.mount(app=ComparchApp, path="/%s" % COMPARCH_APP_PATH)
def _mount_app():
    return ComparchApp()


@ComparchApp.view(model=ComparchModel, name="document_title", internal=True)
def default_document_title(self, request):
    title = "Component Architecture"
    if self.mode in [COMPARCH_UNASSIGNED_OBJECTS, COMPARCH_UNASSIGNED_OBJECTS_DETAIL]:
        title = get_label("ce_module_show_unassigned_objs")
    elif self.mode in [COMPARCH_MODULE_CONTENT, COMPARCH_MODULE_CONTENT_DETAIL]:
        title = get_label("cdb_module_content")
        module_id = self.extra_parameters.get("module_id", "")
        if module_id:
            from cdb.comparch.content import ModuleContent
            from cdb.comparch.modules import Module
            title += " %s" % module_id
            module = Module.ByKeys(module_id)
            contents = ((module.app_conf_exp_dir, "Dev"),
                        (module.app_conf_master_exp_dir, "Master"),
                        (module.std_conf_exp_dir, "Distribution"))
            for confdir, content_from in contents:
                if os.path.isdir(confdir):
                    mc = ModuleContent(module.module_id, confdir)
                    if mc.getItemTypes():
                        title += " (%s)" % content_from
                        break
    return title


@ComparchApp.view(model=ComparchModel, name="application_title", internal=True)
def get_application_title(self, request):
    return default_document_title(self, request)


@ComparchApp.view(model=ComparchModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(COMPARCH_APP_NAMESPACE, COMPARCH_APP_VERSION)
    return "cs-admin-comparch_app-MainComponent"


@ComparchApp.view(model=ComparchModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(COMPARCH_APP_NAMESPACE, COMPARCH_APP_VERSION,
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("%s.js" % COMPARCH_APP_NAMESPACE)
    lib.add_file("%s.js.map" % COMPARCH_APP_NAMESPACE)
    static.Registry().add(lib)


@sig.connect(Module, "ce_module_view_complete_content", "now")
def _module_view_complete_content(self, ctx):
    tools.assert_cdbpkg_host()
    ctx.url("%s?mode=%s&module_id=%s" %
            (COMPARCH_APP_FULLPATH, COMPARCH_MODULE_CONTENT, self.module_id))


@sig.connect(ModulePatch, "ce_show_module_patch", "now")
def _module_show_patch(self, ctx):
    tools.assert_cdbpkg_host()
    ctx.url("/powerscript/cdb.comparch.elink_apps.comparch/module_patch?"
            "module_id=%s&customized_module_id=%s&patch_type=%s" %
            (self.module_id, self.customized_module_id, self.patch_type),
            icon="cdb_module_patch")


def _get_module_conflict_url(self):
    return "powerscript/cdb.comparch.elink_apps.comparch/conflict_details?" \
        "module_id=%s&protocol_id=%s&entry_id=%s" % \
        (self.module_id, self.protocol_id, self.entry_id)


@sig.connect(ModuleConflict, "info", "pre_mask")
def _patch_module_conflict_mask(self, ctx):
    ctx.set_elink_url("conflict_details", _get_module_conflict_url(self))


@sig.connect(ModuleConflict, "preview", "now")
def _patch_module_conflict_preview(self, ctx):
    ctx.setPreviewURL(_get_module_conflict_url(self))
