# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module contains the `cdb.objects.Object` class for document categories.
"""


__docformat__ = "restructuredtext en"

# Exported objects
__all__ = [
    "DocumentCategory",
    "WorkflowAssignment",
    "CADDocumentType_FType",
    "DocumentReference",
    "SheetReference",
    "DocumentECN",
]

import re

from cdb import ue, util
from cdb.lru_cache import lru_cache
from cdb.objects import Forward, N, Object, Reference, Reference_1

fDocument = Forward("cs.documents.Document")
fDocumentCategory = Forward("cs.documents.DocumentCategory")
fDocumentReference = Forward("cs.documents.DocumentReference")
fSheetReference = Forward("cs.documents.SheetReference")
fDocumentECN = Forward("cs.documents.DocumentECN")
fWorkflowAssignment = Forward("cs.documents.WorkflowAssignment")


class DocumentCategory(Object):

    WorkflowAssignments = Reference(
        N,
        fWorkflowAssignment,
        fWorkflowAssignment.categ_id == fDocumentCategory.categ_id,
    )

    __maps_to__ = "cdb_doc_categ"

    def ItemReferenceMandatory(self):
        """
        Returns ``True`` if a document of this category has to be
        assigned to an item.
        """
        if self.HasField("item_ref_mandatory"):
            return self.item_ref_mandatory
        return False

    @classmethod
    def generateID(cls):
        """
        Generates an id for a new category. The method is also used if
        a document category is created in batch mode.
        """
        return str(util.nextval("doc_categ_id"))

    def setCategID(self, ctx):
        """
        Checks if the category id is predefined. If not, a new id
        is generated using `generateID` and set. The standard calls this
        function automatically - you might overwrite the implementation.
        """
        generate_nr = not self.categ_id or self.categ_id in ("#", "...")

        # Handle template creation
        if not generate_nr and ctx.action in ("copy", "create"):
            # We have to create a new number if we still have
            # the templates number
            # This also affects Drag & Drop
            generate_nr = self.categ_id == getattr(ctx.cdbtemplate, "categ_id", "")

        if generate_nr:
            self.categ_id = self.generateID()

    @classmethod
    @lru_cache(clear_after_ue=False)
    def getOLC(cls, categ_id, cad_sys):
        """
        Retrieve the object life cycle by calling `getWorkflow` for
        the given category. The result is cached.

        :param categ_id: The primary key value of the category
        :param cad_sys: The integration that creates a document with
            the given `categ_id`.

        :return: The object lifecycle or an empty string if no
            lifecycle can be found.
        """
        result = ""
        if categ_id:
            categ = cls.ByKeys(categ_id)
            if categ:
                result = categ.getWorkflow(cad_sys)
        return result

    def getWorkflow(self, cad_sys):
        result = ""
        for wfa in self.WorkflowAssignments:
            match = re.match(wfa.cad_system, cad_sys)
            if match is not None and match.end() == len(cad_sys):
                result = wfa.name
                break
        return result

    event_map = {(("copy", "create"), "pre"): ("setCategID")}


class WorkflowAssignment(Object):
    __maps_to__ = "doctype_assign"


class CADDocumentType_FType(Object):
    __maps_to__ = "cdb_cad_categ_ftype"


class DocCategDecomposition(Object):
    __maps_to__ = "cdb_dcat_decomp"


class DocumentReference(Object):
    __maps_to__ = "cdb_doc_rel"

    ReferencedDocument = Reference_1(
        fDocument, fDocumentReference.z_nummer2, fDocumentReference.z_index2
    )

    ReferencingDocument = Reference_1(
        fDocument, fDocumentReference.z_nummer, fDocumentReference.z_index
    )

    def _prevent_interactive_remove(self, ctx):  # pylint: disable=no-self-use
        """
        The entries in ``cdb_doc_rel`` should only be removed by
        the WSM or other integrations.
        """
        if (ctx.interactive or ctx.uses_webui) and not ctx.active_integration:
            raise ue.Exception("error_cdb_doc_rel_remove_interactive")

    def _prevent_interactive_create(self, ctx):  # pylint: disable=no-self-use
        """
        The entries in ``cdb_doc_rel`` should only be created by
        the WSM or other integrations.
        """
        if (ctx.interactive or ctx.uses_webui) and not ctx.active_integration:
            raise ue.Exception("error_cdb_doc_rel_create_interactive")

    event_map = {
        ("create", "pre_mask"): "_prevent_interactive_create",
        ("delete", "pre"): "_prevent_interactive_remove",
    }


class SheetReference(Object):
    __maps_to__ = "cdb_drawing2sheets"
    __classname__ = "cdb_drawing2sheets"

    Sheet = Reference_1(fDocument, fSheetReference.z_nummer2, fSheetReference.z_index2)

    Drawing = Reference_1(fDocument, fSheetReference.z_nummer, fSheetReference.z_index)


class DocumentECN(Object):
    __maps_to__ = "aenderung"
    __classname__ = "aenderung"

    Document = Reference_1(fDocument, fDocumentECN.z_nummer, fDocumentECN.z_index)


class DocumentStatusProtocol(Object):
    __maps_to__ = "cdb_z_statiprot"
    __classname__ = "cdb_z_statiprot"
