#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


from cdb import classbody
from cdb.objects import cdb_file, references, rules
from cs.documents import Document
from cs.platform.web.uisupport import get_uisupport

# do not delete, this is needed for classbody
from cs.web.components.ui_support.operations import OperationInfoClass

WEBUIFILES_RULE = "WEBUI Files"


@classbody.classbody
class Document(object):
    def _web_ui_files(self):
        rule = rules.Rule.ByKeys(WEBUIFILES_RULE)

        # THINKABOUT: this can be a perfomance problem (it makes one SQL query
        # per file).
        return [f for f in self.Files if rule.match(f)] if rule else []

    WebUIFiles = references.ReferenceMethods_N(cdb_file.CDB_File, _web_ui_files)


def add_document_create(model, request, app_setup):
    us_app = get_uisupport(request)
    all_ops = [
        op_info
        for op_info in request.view(OperationInfoClass("document"), app=us_app)
        if (op_info["submit_url"] or op_info["form_url"])
        and op_info["opname"] == "CDB_Create"
    ]

    app_setup.merge_in(["cs-documents-web"], {"create_document": all_ops})
