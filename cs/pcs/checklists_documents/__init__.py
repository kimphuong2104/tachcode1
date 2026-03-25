#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

import logging

from cdb import auth, sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_N, ReferenceMethods_N
from cs.documents import Document

from cs.pcs.checklists import Checklist, ChecklistItem
from cs.pcs.projects import Project
from cs.pcs.projects_documents import AbstractTemplateDocRef

fCLItemDocumentReference = Forward(__name__ + ".CLItemDocumentReference")
fChecklistDocumentReference = Forward(__name__ + ".ChecklistDocumentReference")


class ChecklistDocumentReference(Object):
    __maps_to__ = "cdbpcs_doc2cl"
    __classname__ = "cdbpcs_doc2cl"

    Document = Reference_1(
        Document,
        fChecklistDocumentReference.z_nummer,
        fChecklistDocumentReference.z_index,
    )


class CLTemplateDocRef(AbstractTemplateDocRef):
    __maps_to__ = "cdbpcs_cl2doctmpl"
    __classname__ = "cdbpcs_cl2doctmpl"
    __referer_cls__ = Checklist
    __doc_ref_cls__ = ChecklistDocumentReference

    def create_doc_instances(self, **kwargs):
        """Obverriden to add cdb_project_id to the document attributes."""
        kwargs["cdb_project_id"] = self.cdb_project_id
        kwargs["autoren"] = auth.name
        return self.Super(CLTemplateDocRef).create_doc_instances(**kwargs)


@classbody
class Checklist:
    def _get_Documents(self):
        return self.SimpleJoinQuery(Document, ChecklistDocumentReference)

    Documents = ReferenceMethods_N(Document, _get_Documents)
    Documents.isCollection = 1

    TemplateDocRefs = Reference_N(
        CLTemplateDocRef,
        CLTemplateDocRef.cdb_project_id == Checklist.cdb_project_id,
        CLTemplateDocRef.checklist_id == Checklist.checklist_id,
    )

    @sig.connect(Checklist, "state_change", "post")
    def create_doc_instances(self, ctx):
        """Creates instances of assigned document templates."""
        if not ctx.error:
            try:
                CLTemplateDocRef.create_docs_instances(self, CLTemplateDocRef)
            except ue.Exception as exc:
                logging.error("%s: %s", self.GetDescription(), exc)

    def _preset_project_from_doc(self, ctx):
        self.cdb_project_id = Document.ByKeys(
            z_nummer=ctx.parent.z_nummer, z_index=ctx.parent.z_index
        ).cdb_project_id

    def get_doc_template_references(self):
        return self.TemplateDocRefs


class CLItemDocumentReference(Object):
    __maps_to__ = "cdbpcs_doc2cli"
    __classname__ = "cdbpcs_doc2cli"

    Document = Reference_1(
        Document, fCLItemDocumentReference.z_nummer, fCLItemDocumentReference.z_index
    )


class CLItemTemplateDocRef(AbstractTemplateDocRef):
    __maps_to__ = "cdbpcs_cli2doctmpl"
    __classname__ = "cdbpcs_cli2doctmpl"
    __referer_cls__ = ChecklistItem
    __doc_ref_cls__ = CLItemDocumentReference

    def create_doc_instances(self, **kwargs):
        """Obverriden to add cdb_project_id to the document attributes."""
        kwargs["cdb_project_id"] = self.cdb_project_id
        return self.Super(CLItemTemplateDocRef).create_doc_instances(**kwargs)


@classbody
class ChecklistItem:

    TemplateDocRefs = Reference_N(
        CLItemTemplateDocRef,
        CLItemTemplateDocRef.cdb_project_id == ChecklistItem.cdb_project_id,
        CLItemTemplateDocRef.checklist_id == ChecklistItem.checklist_id,
        CLItemTemplateDocRef.cl_item_id == ChecklistItem.cl_item_id,
    )

    def _get_Documents(self):
        return self.SimpleJoinQuery(Document, CLItemDocumentReference)

    Documents = ReferenceMethods_N(Document, _get_Documents)
    Documents.isCollection = 1

    @sig.connect(ChecklistItem, "state_change", "post")
    def create_doc_instances(self, ctx):
        """Creates instances of assigned document templates."""
        if not ctx.error:
            try:
                CLItemTemplateDocRef.create_docs_instances(self, CLItemTemplateDocRef)
            except ue.Exception as exc:
                logging.error("%s: %s", self.GetDescription(), exc)

    def get_doc_template_references(self):
        return self.TemplateDocRefs


@classbody
class Document:
    def _getChecklists(self):
        return self.SimpleJoinQuery(Checklist, ChecklistDocumentReference)

    Checklists = ReferenceMethods_N(Checklist, _getChecklists)

    def create_relationship_object(self, cdb_project_id, checklist_id):
        ChecklistDocumentReference.Create(
            z_nummer=self.z_nummer,
            z_index=self.z_index,
            cdb_project_id=cdb_project_id,
            checklist_id=checklist_id,
        )

    @sig.connect(Document, "cdbpcs_checklist_assign", "now")
    def _assign_doc_checklist(self, ctx):
        (cdb_project_id, checklist_id) = Checklist.cdbpcs_checklist_assign(self, ctx)
        self.create_relationship_object(cdb_project_id, checklist_id)

    @sig.connect(Document, "delete", "pre")
    def _check_doc_checklists_delete_pre(self, ctx):
        if len(self.Checklists) > 0:
            raise ue.Exception("pcs_err_del_doc1")

    @sig.connect(Document, "delete", "post")
    def _doc_checklists_delete_post(self, ctx):
        if not ctx.error:
            sqlapi.SQLdelete(
                f"from cdbpcs_doc2cl where z_nummer = '{self.z_nummer}' "
                f"and z_index = '{self.z_index}'"
            )
            sqlapi.SQLdelete(
                f"from cdbpcs_doc2cli where z_nummer = '{self.z_nummer}' "
                f"and z_index = '{self.z_index}'"
            )


@classbody
class Project:
    @sig.connect(Project, "copy", "post")
    def handle_checklist_doc_templates(self, ctx):
        if ctx.error != 0 or self.template:
            return

        self._create_documents_from_templates(ChecklistItem, CLItemTemplateDocRef)
        self._create_documents_from_templates(Checklist, CLTemplateDocRef)
