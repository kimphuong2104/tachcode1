# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$
import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.root import Root, get_internal
from cs.platform.web.uisupport.tabledef import TableDefApp, TableDefBaseModel
from cs.requirements import RQMSpecification, RQMSpecObject, rqm_utils
from cs.requirements.web.rest.diff.diff_indicator_model import \
    DiffCriterionRegistry
from cs.web.components.base.main import BaseApp, BaseModel
from cs.web.components.ui_support import forms

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"


MOUNT_PATH = "/cs-requirements-web-diff"


class DiffApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(DiffApp, self).update_app_setup(app_setup, model, request)
        app_setup["cs-requirements-web-diff"] = model.get_app_setup(request) if hasattr(model, "get_app_setup") else {}


class DiffModel(BaseModel):
    def __init__(self, absorb):
        super(DiffModel, self).__init__()
        self.absorb = absorb

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]

    def get_app_setup(self, request):
        from cs.requirements.web.rest.diff.main import MOUNT_PATH as API_MOUNT_PATH
        table_base_model = TableDefBaseModel({"class_name": RQMSpecObject.__classname__})
        return {
            "diff_richtext_data_url": "/internal/%s/richtext/${left}/${right}/?languages=${languages}" % API_MOUNT_PATH,
            "diff_metadata_data_url": "/internal/%s/metadata/${left}/${right}/?languages=${languages}" % API_MOUNT_PATH,
            "diff_header_data_url": "/internal/%s/header/${left}/${right}/?languages=${languages}" % API_MOUNT_PATH,
            "diff_classification_data_url": "/internal/%s/classification/${left}/${right}/?languages=${languages}" % API_MOUNT_PATH,
            "diff_file_data_url": "/internal/%s/file/${left}/${right}/?languages=${languages}" % API_MOUNT_PATH,
            "diff_acceptance_criterion_data_url": "/internal/%s/acceptancecriterion/${left}/${right}/?languages=${languages}" % API_MOUNT_PATH,
            "matching_data_url": "/internal/%s/matching/${leftSpecificationObjectId}/${rightSpecificationObjectId}/${selectedCdbObjectId}/${targetSide}" % API_MOUNT_PATH,
            "specification_object_catalog": forms.FormInfoBase.get_catalog_config(
                request, "cdbrqm_spec_brows_baselines", is_combobox=False, as_objs=False),
            "languages_multiselect_catalog": forms.FormInfoBase.get_catalog_config(
                request, "cdbrqm_application_languages_browser", is_combobox=False, as_objs=False),
            "specification_rest_id_template": "/api/v1/collection/specification/${cdb_object_id}",
            "deleted_requirements_tabledef_url": request.link(
                table_base_model, app=get_internal(request).child(
                    TableDefApp("cdbrqm_spec_object_diff_del")
                )
            ),
            "deleted_requirements_tabledata_url": "/internal/%s/deleted/${left}/${right}/" % API_MOUNT_PATH,
            "diff_requirements_tabledef_url": request.link(
                table_base_model, app=get_internal(request).child(
                    TableDefApp("cdbrqm_spec2spec_obj_web_diff")
                )
            ),
            "diff_requirements_tabledata_url": "/internal/%s/requirements/${right}/" % API_MOUNT_PATH,
            "diff_requirements_diff_indicator_url": "/internal/%s/indicator/${left}/${right}/?languages=${languages}&criterions=${criterions}" % API_MOUNT_PATH,
            "default_languages": ",".join(rqm_utils.get_language_list()),
            "criterions": DiffCriterionRegistry.get_criterions(RQMSpecObject)
        }


@Root.mount(app=DiffApp, path=MOUNT_PATH)
def _mount_app():
    return DiffApp()


@DiffApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Diff"


@DiffApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    # Add rich text library
    request.app.include("cs-classification-web-component", "15.1.0")
    request.app.include("cs-requirements-web-richtext", "0.0.1")
    request.app.include("cs-requirements-web-weblib", "0.0.1")
    request.app.include("cs-requirements-web-diff", "0.0.1")
    return "cs-requirements-web-diff-MainComponent"


@DiffApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return MOUNT_PATH


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-requirements-web-diff", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-requirements-web-diff.js")
    lib.add_file("cs-requirements-web-diff.js.map")
    static.Registry().add(lib)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _initialize_rqm_diff_plugin_registry():
    registry = DiffCriterionRegistry.get_registry()
    sig.emit(RQMSpecification, "rqm_diff_plugins", "init")(registry)


@DiffApp.path(path='', model=DiffModel, absorb=True)
def _get_diff_ui_no_selection(absorb):
    return DiffModel(absorb=absorb)
