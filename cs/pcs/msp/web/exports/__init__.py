#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import os
from contextlib import contextmanager

import webob
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal
from webob.exc import HTTPBadRequest, HTTPInternalServerError

from cs.pcs.msp.web import APP
from cs.pcs.projects import Project


class ExportXMLApp(JsonAPI):
    pass


@contextmanager
def file_context(tmp_filename):

    tmp_file = open(tmp_filename, encoding="utf-8")
    try:
        yield tmp_file
    finally:
        tmp_file.close()
        if os.path.isfile(tmp_filename):
            os.remove(tmp_filename)


class ExportXMLAppModel:
    def __init__(self, cdb_project_id):
        self.cdb_project_id = cdb_project_id
        self.tmp_filename = ""

    def prepare(self):
        # find the project
        project = Project.Query(
            f"cdb_project_id='{self.cdb_project_id}' AND ce_baseline_id=''",
            access="read",
        )
        if not project:
            logging.error("Project not found.")
            raise HTTPBadRequest

        # create the xml file to export
        self.tmp_filename = project[0].get_temp_export_xml_file()

    def __iter__(self):
        # export the file
        try:
            with file_context(self.tmp_filename) as file_ctx:
                for line in file_ctx:
                    yield line.encode("utf-8")
        except OSError as os_error:
            logging.error("File export not successful: %s", os_error)
            raise HTTPInternalServerError from os_error

    def get_file_name(self):
        return self.cdb_project_id


@Internal.mount(app=ExportXMLApp, path=APP)
def _mount_app():
    return ExportXMLApp()


@ExportXMLApp.path(path="export/{cdb_project_id}", model=ExportXMLAppModel)
def _(request, cdb_project_id):
    return ExportXMLAppModel(cdb_project_id)


@ExportXMLApp.view(model=ExportXMLAppModel)
def exportFile(model, request):
    model.prepare()
    response = webob.Response(content_type="application/xml", app_iter=model)
    response.content_disposition = f"attachment; filename={model.get_file_name()}.xml"
    return response
