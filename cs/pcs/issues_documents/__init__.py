#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

from cdb import sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_N, ReferenceMethods_N
from cs.documents import Document

from cs.pcs.issues import Issue

fIssueDocumentReference = Forward(__name__ + ".IssueDocumentReference")


class IssueDocumentReference(Object):
    __maps_to__ = "cdbpcs_doc2iss"
    __classname__ = "cdbpcs_doc2iss"

    Document = Reference_1(
        Document, fIssueDocumentReference.z_nummer, fIssueDocumentReference.z_index
    )


@classbody
class Issue:
    DocumentReferences = Reference_N(
        IssueDocumentReference,
        IssueDocumentReference.cdb_project_id == Issue.cdb_project_id,
        IssueDocumentReference.issue_id == Issue.issue_id,
    )

    def _getDocuments(self):
        return self.SimpleJoinQuery(Document, IssueDocumentReference)

    Documents = ReferenceMethods_N(Document, _getDocuments)

    @sig.connect(Issue, "create", "pre_mask")
    @sig.connect(Issue, "copy", "pre_mask")
    def setDefaultsByDocument(self, ctx):
        # ggf. Projektnummer aus Beziehungskontext uebernehmen
        if ctx.relationship_name == "cdbpcs_doc2issues":
            self.cdb_project_id = Document.ByKeys(
                z_nummer=ctx.parent.z_nummer, z_index=ctx.parent.z_index
            ).cdb_project_id


@classbody
class Document:
    def _getIssues(self):
        return self.SimpleJoinQuery(Issue, IssueDocumentReference)

    Issues = ReferenceMethods_N(Issue, _getIssues)

    @sig.connect(Document, "delete", "pre")
    def _check_doc_issues_delete_pre(self, ctx):
        if len(self.Issues) > 0:
            raise ue.Exception("pcs_err_del_doc2")

    @sig.connect(Document, "delete", "post")
    def _doc_issues_delete_post(self, ctx):
        # Einträge in PCS Verknüpfungsrelationen löschen
        if not ctx.error:
            sqlapi.SQLdelete(
                f"from cdbpcs_doc2iss where z_nummer = '{self.z_nummer}'"
                f" and z_index = '{self.z_index}'"
            )
