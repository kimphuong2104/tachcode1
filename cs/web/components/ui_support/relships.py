#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Access to configured relationship metadata via REST API
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from webob.exc import HTTPNotFound

from cdb import ElementsError
from cdb.lru_cache import lru_cache
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web.rest.classdef.main import App as ClassdefApp
from cs.web.components.ui_support.utils import class_available_in_ui


class RelshipsModel(object):
    def __init__(self, class_name):
        self.class_name = class_name


@lru_cache(maxsize=None, clear_after_ue=False)
def _retrieve_relships(class_name):
    """ Retrieve all relships that are configured to be shown in a dialog where
        the target class has a REST-API. The kernel API is expected to return the
        relships in the correct order for display, here we just add the position
        numbers so that the client can reconstruct the ordering from the map.
    """
    cdef = CDBClassDef(class_name)
    result = {}
    position = 10
    for rs_name in cdef.getRelationshipNames():
        rs = cdef.getRelationship(rs_name)
        if rs.is_valid() and rs.get_rolename():
            reference_cldef = rs.get_reference_cldef()
            if reference_cldef.getRESTName():
                ref_classname = reference_cldef.getClassname()
                available = class_available_in_ui(reference_cldef)
                link_class_def = rs.get_link_cldef()
                link_classname = link_class_def.getClassname() if link_class_def else None
                result[rs.get_rolename()] = {"pos": position,
                                             "name": rs.get_name(),
                                             "label": rs.get_label(),
                                             "icon_url": rs.get_icon_url(),
                                             "is_one_on_one": rs.is_one_on_one(),
                                             "hide": rs.hide_initially(),
                                             "show_in_mask": rs.show_in_mask(),
                                             "reference_classname": ref_classname,
                                             "link_classname": link_classname,
                                             "available_in_ui": available}
                position += 10
    return result


@ClassdefApp.path(path='{class_name}/relships', model=RelshipsModel)
def _relships_path(class_name):
    try:
        # Try to access the classdef to provoke an exception if the class does
        # not exist. We use the classname to actually access the relships, so
        # that the lru_cache works (CDBClassDef will return a new instance for
        # each call, even for the same classname).
        CDBClassDef(class_name)
        return RelshipsModel(class_name)
    except ElementsError as exc:
        raise HTTPNotFound(exc.message)


@ClassdefApp.json(model=RelshipsModel)
def _relships_view(model, _request):
    return _retrieve_relships(model.class_name)
