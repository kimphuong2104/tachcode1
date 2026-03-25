#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

import morepath

from cs.platform.web import root
from cs.fileclient.web.model import EditFileObject, UnboundQuery

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 201513 2019-09-17 14:21:44Z kbu $"


class InternalApp(morepath.App):
    pass


@root.Internal.mount(app=InternalApp, path="/cs.fileclient")
def _mount_api():
    return InternalApp()


@InternalApp.path(path="file", model=EditFileObject)
def get_object(app, extra_parameters):
    return EditFileObject(extra_parameters)


@InternalApp.path(path="unbound", model=UnboundQuery)
def get_query(app, extra_parameters):
    return UnboundQuery(extra_parameters)


with InternalApp.json(model=EditFileObject) as json:

    @json(name="presigned-blob-write-url")
    def get_presigned_blob_write_url(self, request):
        return self.get_presigned_blob_write_url()

    @json(name="blob-id", request_method="PUT")
    def put_blob_id(self, request):
        return self.put_blob_id()


with InternalApp.json(model=UnboundQuery) as json:

    @json(name="property")
    def get_property(self, request):
        return self.get_property()
