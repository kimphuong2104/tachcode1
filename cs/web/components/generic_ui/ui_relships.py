#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This module implements links to relationship targets for the UI URL space.
Navigating such a link redirects the browser to the actual UI page for the
target object.

Bookmarking such links in the form <source object UI URL>/relship/<relship_name>
is meaningful, in the sense that it always resolves to the currently valid
relationship target.
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from webob.exc import HTTPForbidden, HTTPNotFound, HTTPBadRequest
import morepath
from cdb.constants import kAccessRead
from cs.platform.web.rest import support
from cs.platform.web.uisupport import get_ui_link
from cs.platform.web.rest.relship.main import make_relship_target
from . import GenericUIApp


class UI_RelshipModel(object):

    def __init__(self, for_object, relship_name):
        super(UI_RelshipModel, self).__init__()
        self.for_object = for_object
        self.relship_name = relship_name


@GenericUIApp.path(path="{rest_name}/{keys}/relship/{relship_name}", model=UI_RelshipModel)
def _get_model(rest_name, keys, relship_name):
    # In here, check that the source object of the relship actually exists,
    # and is readable by the user.
    if support.cls_def(name=rest_name) is None:
        return None
    the_object = support.get_object_from_rest_name(rest_name, keys)
    if the_object is None:
        return None
    if not the_object.CheckAccess(kAccessRead):
        # no read access to the source object means the relship must not be
        # navigated
        return HTTPForbidden()
    return UI_RelshipModel(the_object, relship_name)


@GenericUIApp.view(model=UI_RelshipModel)
def _redirect_to_relship_target(model, request):
    # Navigate the relationship with the given name, and compute the UI URL for
    # the target. Then redirect the caller to this URL.
    rs_target = make_relship_target(model.for_object, model.relship_name)
    if rs_target is None:
        return HTTPNotFound()
    # For now, we handle unary relationships only.
    if not rs_target.is_unary:
        return HTTPBadRequest()
    _, target_obj = rs_target.resolve()
    if target_obj is None:
        return HTTPNotFound()
    target_link = get_ui_link(request, target_obj)
    if target_link is None:
        # Might be due to info operation not configured for the Web UI, see E042515
        return HTTPNotFound()
    return morepath.redirect(target_link)
