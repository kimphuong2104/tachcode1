# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import sig
from cs.web.components.ui_support.embedded.model import EmbeddedClassSearchModel
from cs.web.components.configurable_ui import ConfigurableUIModel


def ensure_csp_header_set(request):
    try:
        from cs.threed.hoops.web.utils import add_csp_header
        request.after(add_csp_header)
    except ImportError:
        pass


@sig.connect(EmbeddedClassSearchModel, ConfigurableUIModel, "application_setup")
def _embedded_class_search_app_setup(model, request, app_setup):
    """Ensure that the embedded search UI (used for the CAD search in workspaces desktop) returns
    a CSP header which is required for the threed preview to work."""

    ensure_csp_header_set(request)
