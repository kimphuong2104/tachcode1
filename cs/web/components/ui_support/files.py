#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
from . import get_uisupport_app

from cdb import ElementsError
from cdb import sig
from cdb import ue
from cdb import util
from cdb.util import CDBMsg
from cdb.objects import ByID, Object
from cdb.objects.cdb_file import CDB_File
from cdbwrapc import CDBObjectHandle
from cs.platform.web import PlatformApp, permissions
from cs.platform.web.uisupport import App as InternalUIApp
from cs.platform.web.rest import support
from cs.platform.web.rest.generic.main import get_generic_app, App as GenericApp
from webob import exc as webobexc
from six.moves.urllib.parse import urlparse


# Exported objects
__all__ = ["file_link_by_blob_id"]


def file_link_by_blob_id(request, cdb_object_id):
    cdbf = CDB_File.ByKeys(cdb_object_id=cdb_object_id)
    return _ui_file(cdbf, request)


@GenericApp.view(model=CDB_File, name='ui_link', internal=True)
def _ui_file(the_file, request):
    return request.link(the_file, app=get_uisupport_app(request))


@InternalUIApp.path(path="file/{cdb_object_id}", model=CDB_File)
def _get_model(cdb_object_id):
    return CDB_File.ByKeys(cdb_object_id=cdb_object_id)


@InternalUIApp.view(model=CDB_File)
def _file_access(the_file, request):
    """
    Instead of returning the standard JSON REST response
    in an error case this view returns a standard
    elements error page. So for interactive file requests
    this view should be used. The link to this view is provided
    in the REST data of a CDB_File object (system:ui_link).
    See E047580 for further details.
    """
    try:
        fobject = ByID(the_file.cdbf_object_id)
        generic_app = get_generic_app(request, fobject.GetClassDef().getRESTName())
        return request.view(the_file, app=generic_app)
    except webobexc.HTTPForbidden as ex:
        @request.after
        def set_status_code(response):
            response.content_type = "text/html; charset=utf-8"

        msg = CDBMsg(CDBMsg.kFatal, "csweb_err_file_access")
        ex.title = "%s" % msg

        return request.view(ex, app=PlatformApp())


@InternalUIApp.path(path="editable_files/{rest_name}/{rest_key}", model=Object)
def _get_model(rest_name, rest_key):
    return support.get_object_from_rest_name(rest_name, rest_key)


@InternalUIApp.json(model=Object)
def _editable_files(the_object, request):
    the_object = the_object.ToObjectHandle()
    fh_list = the_object.getEditableFileObjectHandles()
    msg = None if len(fh_list) else "%s" % util.CDBMsg(util.CDBMsg.kInfo, "docedit_nofiles")

    return {
        "blob_ids": [fh.getUUID() for fh in fh_list],
        "message": msg
    }


def _web_ui_edit(self, ctx):
    root = getattr(ctx.dialog, 'www_root_url', None)
    if root is None:
        raise ue.Exception('Failed to retrieve base url.')

    (scheme, host_and_port, _, _, _, _) = urlparse(root)
    ctx.url('cdbf://%s/%s/for_object/%s/%s'
            % (host_and_port,
               scheme,
               support.rest_name_for_class_name(self.GetClassname()),
               support.rest_key(self)))
