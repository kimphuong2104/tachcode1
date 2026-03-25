# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.web.components.ui_support import forms


def add_app_settings(model, request, app_setup):
    data = {
        "class_property_catalog": forms.FormInfoBase.get_catalog_config(
            request, "cdbrqm_classification_class_properties", is_combobox=False, as_objs=True
        ),
    }
    app_setup.merge_in(["cs-requirements-web-specification-editor"], data)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-requirements-web-specification-editor", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'specification_editor', 'build'))
    lib.add_file("cs-requirements-web-specification-editor.js")
    # lib.add_file("cs-requirements-web-specification-editor.js.map")
    static.Registry().add(lib)
