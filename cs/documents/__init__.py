#!/usr/bin/env powerscript
# -*- mode: python; coding: iso-8859-1 -*-
#
#
# Copyright (C) 1990 - 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# pylint: disable=E0102,W0612,W0201,too-many-lines,protected-access
# pylint: disable=bad-continuation

__all__ = ["Document", "NEVER_VALID_DATE"]

import logging
import os
from datetime import datetime
from urllib.parse import quote

from cdb import (
    CADDOK,
    ElementsError,
    auth,
    cad,
    constants,
    decomp,
    kernel,
    sig,
    sqlapi,
    typeconversion,
    ue,
    util,
)
from cdb.objects import (
    NULL,
    Forward,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_1,
    ReferenceMethods_N,
)
from cdb.objects.cdb_file import FILE_EVENT, CDB_File
from cdb.objects.org import User
from cdb.platform import olc
from cdb.platform.mom import CDBObjectHandle, SimpleArguments, entities, relships
from cs.activitystream.objects import Subscription
from cs.documents.batchoperations import BatchOperationDocumentAssignment
from cs.platform.web.rest import support
from cs.sharing import Sharing
from cs.sharing.groups import RecipientCollection
from cs.sharing.share_objects import WithSharing
from cs.tools.batchoperations import WithBatchOperations
from cs.tools.powerreports import WithPowerReports
from cs.workflow import briefcases

# These functions/classes should be part of the cs.document namespace
from .index import createDocIndex  # noqa F401
from .objects import (  # noqa F401
    CADDocumentType_FType,
    DocCategDecomposition,
    DocumentCategory,
    DocumentECN,
    DocumentReference,
    DocumentStatusProtocol,
    SheetReference,
    WorkflowAssignment,
)
from .typeselect import DocumentTypeSelector  # noqa F401

_Logger = logging.getLogger(__name__)

# Forward declare some classes
Document = Forward("cs.documents.Document")
fDocumentReference = Forward("cs.documents.DocumentReference")
fSheetReference = Forward("cs.documents.SheetReference")
f_cdb_file_base = Forward("cdb.objects.cdb_file.cdb_file_base")
fDocumentECN = Forward("cs.documents.DocumentECN")

NEVER_VALID_DATE = datetime(9999, 12, 31).replace(microsecond=0)


class Document(
    Object,
    WithPowerReports,
    WithBatchOperations,
    briefcases.BriefcaseContent,
    WithSharing,
):
    __maps_to__ = "zeichnung"
    __classname__ = "document"

    DocumentReferences = Reference_N(
        fDocumentReference,
        fDocumentReference.z_nummer == Document.z_nummer,
        fDocumentReference.z_index == Document.z_index,
    )

    ReverseReferences = Reference_N(
        fDocumentReference,
        fDocumentReference.z_nummer2 == Document.z_nummer,
        fDocumentReference.z_index2 == Document.z_index,
    )

    WorkspaceItems = Reference_N(
        f_cdb_file_base, f_cdb_file_base.cdbf_object_id == Document.cdb_object_id
    )

    Files = Reference_N(CDB_File, CDB_File.cdbf_object_id == Document.cdb_object_id)
    PrimaryFiles = Reference_N(
        CDB_File,
        CDB_File.cdbf_object_id == Document.cdb_object_id,
        CDB_File.cdbf_primary == "1",
    )

    kCategoryAttrPrefix = "z_categ"

    def _PreviousIndex(self):
        ctx = self.GetContext()
        if ctx and ctx.action == "index" and ctx.mode in ["post_mask", "pre"]:
            prev_idx = ctx.cdbtemplate.z_index
        elif ctx and ctx.action == "delete" and ctx.mode in ["post", "final"]:
            # The kernel code does not work if the document has been removed
            # from the database
            sort_attr = util.PersonalSettings()[
                (constants.kVersioningIndexOrderDoc, sqlapi.SQLdbms())
            ]
            if not sort_attr:
                sort_attr = "z_index"

            val = sort_attr.replace("z_index", "'%s'" % sqlapi.quote(self.z_index))
            stmt = (
                "z_index, %s FROM zeichnung " % (sort_attr)
                + "WHERE z_nummer='%s' " % (sqlapi.quote(self.z_nummer))
                + "AND %s < %s " % (sort_attr, val)
                + "ORDER BY 2 DESC, 1 DESC"
            )
            t = sqlapi.SQLselect(stmt)
            if sqlapi.SQLrows(t):
                prev_idx = sqlapi.SQLstring(t, 0, 0)
            else:
                return None
        else:
            prev_idx = kernel.get_prev_index(
                self.z_nummer, self.z_index, self.GetTableName()
            )
        return Document.ByKeys(self.z_nummer, prev_idx)

    PreviousIndex = ReferenceMethods_1(Document, _PreviousIndex)

    """
    A `cdb.objects.ReferenceMethod_1` that returns the document that represents
    the previous version of `self` usually by selecting all versions and
    sorting them using the configuration of the property ``ixsm`` and
    ``z_index``. This is quite expensive - if you know your indexing schema
    you should use an implementation that do not need DB-Statements.

    Note that this function will not work for a 'delete'-'post' user exit
    if your sorting uses any other attribute from ``zeichnung`` than
    ``z_index`` for sorting.
    """

    def _getReferencedDocuments(self):
        return Document.SQL(
            (
                "SELECT DISTINCT zeichnung.*"
                "  FROM zeichnung, cdb_doc_rel"
                " WHERE zeichnung.z_nummer=cdb_doc_rel.z_nummer2"
                "   AND zeichnung.z_index=cdb_doc_rel.z_index2"
                "   AND cdb_doc_rel.z_nummer='%s'"
                "   AND cdb_doc_rel.z_index='%s'"
            )
            % (sqlapi.quote(self.z_nummer), sqlapi.quote(self.z_index))
        )

    ReferencedDocuments = ReferenceMethods_N(Document, _getReferencedDocuments)

    def _getReferencingDocuments(self):
        return Document.SQL(
            (
                "SELECT DISTINCT zeichnung.*"
                "  FROM zeichnung, cdb_doc_rel"
                " WHERE zeichnung.z_nummer=cdb_doc_rel.z_nummer"
                "   AND zeichnung.z_index=cdb_doc_rel.z_index"
                "   AND cdb_doc_rel.z_nummer2='%s'"
                "   AND cdb_doc_rel.z_index2='%s'"
            )
            % (sqlapi.quote(self.z_nummer), sqlapi.quote(self.z_index))
        )

    ReferencingDocuments = ReferenceMethods_N(Document, _getReferencingDocuments)

    # handling of drawings with multiple sheets
    SheetsReferences = Reference_N(
        fSheetReference,
        fSheetReference.z_nummer == Document.z_nummer,
        fSheetReference.z_index == Document.z_index,
    )

    DrawingOfSheetReferences = Reference_N(
        fSheetReference,
        fSheetReference.z_nummer2 == Document.z_nummer,
        fSheetReference.z_index2 == Document.z_index,
    )

    def _getDrawingsSheets(self):
        return Document.SQL(
            (
                "SELECT DISTINCT zeichnung.*"
                "  FROM zeichnung, cdb_drawing2sheets"
                " WHERE zeichnung.z_nummer=cdb_drawing2sheets.z_nummer2"
                "   AND zeichnung.z_index=cdb_drawing2sheets.z_index2"
                "   AND cdb_drawing2sheets.z_nummer='%s'"
                "   AND cdb_drawing2sheets.z_index='%s'"
            )
            % (sqlapi.quote(self.z_nummer), sqlapi.quote(self.z_index))
        )

    DrawingSheets = ReferenceMethods_N(Document, _getDrawingsSheets)

    def _getSheetsDrawing(self):
        return Document.SQL(
            (
                "SELECT DISTINCT zeichnung.*"
                "  FROM zeichnung, cdb_drawing2sheets"
                " WHERE zeichnung.z_nummer=cdb_drawing2sheets.z_nummer"
                "   AND zeichnung.z_index=cdb_drawing2sheets.z_index"
                "   AND cdb_drawing2sheets.z_nummer2='%s'"
                "   AND cdb_drawing2sheets.z_index2='%s'"
            )
            % (sqlapi.quote(self.z_nummer), sqlapi.quote(self.z_index))
        )

    CorrespondingDrawings = ReferenceMethods_N(Document, _getSheetsDrawing)

    def _getVersions(self):
        # implemented as ReferenceMethods_N, because CADDOK.SQLDBMS_STRLEN must
        # not be evaluated when importing this module!
        idx_len = "%s(z_index)" % CADDOK.SQLDBMS_STRLEN
        return Document.KeywordQuery(
            order_by=[idx_len, "z_index"], z_nummer=self.z_nummer
        )

    Versions = ReferenceMethods_N(Document, _getVersions)

    ChangeNotice = Reference_1(fDocumentECN, Document.z_nummer, Document.z_index)

    def isModel(self):
        return (
            self.GetClassname() == "model"
            or "model" in self.GetClassDef().getBaseClassNames()
        )

    def GetObjectKind(self):
        return self.z_art

    def CreateIndex(self, new_index="", **kwargs):
        """
        Creates and returns a new version of `self`. You can use `new_index`
        to predefine the value of ``z_index``. If `new_index` is emtpy it is
        generated using the index schema of your installation.
        """
        from .index import _createDocIndex

        index_created = _createDocIndex(
            self.z_nummer, self.z_index, new_index, **kwargs
        )
        indexed_object = Document.ByKeys(z_nummer=self.z_nummer, z_index=index_created)
        return indexed_object

    @classmethod
    def makeNumber(cls, doc):
        """
        Returns a new document number for the passed document object.
        Document numbers are generated differently depending on whether an
        item is assigned or not.

        Documents without assigned Item:
          A six digit number is generated from cdb_counter DOK_NR_SEQ and a leading ``D`` is prepended.
          Example: D000001

        Documents with assigned Item:
          Each item number has it's own range of document numbers starting at 1. A document number
          is generated by appending an increasing id from this range of numbers to the item number.

          Examples for documents assigned to item 123456

            z_nummer = 123456-1 for the first document assigned to the item

            z_nummer = 123456-2 for the second document assigned to the item

        The passed document object may also be ``None``. In this case a six digit number
        is generated from cdb_counter ``DOK_NR_SEQ`` and a leading ``D`` is
        prepended.
        You might overwrite the implementation if you want to generate other numbers.
        """
        result = ""
        if not doc or not doc.teilenummer:
            result = "D%06d" % (util.nextval("DOK_NR_SEQ"))
        else:
            doc._check_partno()
            prefSet = sqlapi.RecordSet2(
                "prefixes", "prefix='%s'" % doc.teilenummer, updatable=1
            )
            if not prefSet:
                curSeq = 1
                sqlapi.SQLinsert(
                    "into prefixes (prefix,seq) values ('%s',%s)" % (doc.teilenummer, 2)
                )
            else:
                curSeq = prefSet[0].seq
                prefSet[0].update(seq=(curSeq + 1))
            result = "%s-%d" % (doc.teilenummer, curSeq)
        return result

    def setDocumentNumber(self, ctx):
        """
        Checks if the document number is predefined. If not, a new number
        is generated using `makeNumber` and set. The standard calls this
        function automatically - you might overwrite the implementation.
        """
        generate_nr = not self.z_nummer or self.z_nummer in ("#", "...")

        # Handle template creation
        if not generate_nr and ctx.action in ("copy", "create"):
            # We have to create a new number if we still have the templates number
            # This also affects Drag & Drop
            generate_nr = self.z_nummer == getattr(ctx.cdbtemplate, "z_nummer", "")

        # Handle Drag & Drop
        if not generate_nr and ctx.dragdrop_action_id != "" and ctx.action == "create":
            # We have to create a new number if we still have the dropped objects
            # number
            generate_nr = self.z_nummer == getattr(ctx.dragged_obj, "z_nummer", "")

        if generate_nr:
            self.z_nummer = self.makeNumber(self)

    def _check_partno(self, ctx=None):
        """Checks that the part number / index point to a valid part"""
        # Usually an item is already known in the server - so use the
        # objecthandle to find out if an item exists
        if self.teilenummer:
            try:
                cdef = entities.CDBClassDef("part")
                keys = SimpleArguments(
                    teilenummer=self.teilenummer, t_index=self.t_index
                )
                item = CDBObjectHandle(cdef, keys, True, True)
                if not item.exists():
                    raise ue.Exception("part_number", self.teilenummer, self.t_index)
            except ElementsError:
                # Seems to be an installation without items
                pass

    def getFileSuffix(self):
        """Returns the file suffix for the primary format"""
        return cad.getCADConfValue("ZVS Zeichnung Endung", self.erzeug_system)

    def copyDoc(self, **kwargs):
        """
        Returns a copy of self using `makeNumber` to generate a new document
        number. The function uses `cdb.objects.Object.Copy` which means at
        this time that there is no access check and no user exits are called.
        The attributes returned by `GetInitialCopyValues` are used to create
        the copy. The status is set to ``0`` and the attribute ``dateiname``
        is cleared. ``cdb_lock`` is set to an empty string.
        The function also copies the non derived files of the document using
        `cdb.objects.cdb_file.CDB_File.copy_file`.

        The function might be replaced in future versions - you should use
        `cdb.objects.operations.operation` for the regular behaviour.
        """

        import warnings

        warnings.warn(
            "copyDoc is deprecated. Use normal copy operation from cdb.objects.operations.operation instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        new_znum = self.makeNumber(None)
        new_zidx = kernel.new_index()
        state_txt = ""
        try:
            state_txt = olc.StatusInfo(self.z_art, 0).getStatusTxt()
        except AttributeError:
            # Invalid state or z_art
            pass
        args = self.GetInitialCopyValues()
        # These are the args of the legacy implementation
        args.update(
            {
                "z_nummer": new_znum,
                "z_index": new_zidx,
                "cdb_object_id": "",
                "z_status": 0,
                "z_status_txt": state_txt,
                "cdb_lock": "",
                "dateiname": "",
            }
        )
        args.update(Document.MakeChangeControlAttributes())
        args.update(kwargs)
        new_doc = self.Copy(**args)
        # alle nicht abgeleiteten Dateien kopieren
        new_basename = new_znum + "-" + new_zidx
        for f in self.Files:
            if not f.cdbf_derived_from:
                base, ext = os.path.splitext(f.cdbf_name)
                f.copy_file(new_doc, new_basename + ext)
        return new_doc

    def isTemplate(self):
        return self.vorlagen_kz

    def _resolveReferencedDocs(self, depth, nodes, links, path):
        # Prevent recursions
        p = list(path)
        if self not in path:
            nodes.append(self)
            links[self] = []
            p.append(self)
        if depth != 0:
            for ref in self.DocumentReferences:
                doc = ref.ReferencedDocument
                if doc:
                    # Recursion check
                    if self in links and doc not in p:
                        links[self].append(doc)
                    if doc not in nodes:
                        doc._resolveReferencedDocs(depth - 1, nodes, links, p)
                else:
                    _Logger.warning(
                        "DocumentReference %s references an unknown document",
                        ref.GetDescription(),
                    )

    def resolveReferencedDocuments(self, depth=0):
        """
        Returns a list of all documents that are referenced by `self` by
        navigating `DocumentReferences` until depth is reached or a
        recursion occures. If depth is ``0`` all references will be returned.
        The result does not contain any duplicates and
        will be sorted in a way that if ``D1`` references ``D2`` that
        ``D1`` is located before ``D2`` in the result as long a there are
        no recursions.

        If a document reference points to an invalid document this reference
        will be ignored.
        """

        def toposort2(nodes, graph):
            counts = dict((n, 0) for n in nodes)
            for targets in graph.values():
                for n in targets:
                    counts[n] += 1
            result = []
            independent = set(n for n in nodes if counts[n] == 0)
            while independent:
                n = independent.pop()
                result.append(n)
                for m in graph.pop(n, ()):
                    counts[m] -= 1
                    if counts[m] == 0:
                        independent.add(m)
            if graph:
                # Recursion add the rest.
                for n in list(graph):
                    result.append(n)
            return result

        nodes = []
        links = {}
        # Keep original semantic
        if depth == 0:
            depth = -1
        self._resolveReferencedDocs(depth, nodes, links, [self])
        return toposort2(nodes, links)

    @classmethod
    def _set_template_catalog_query_args(cls, ctx):
        if ctx.catalog_invoking_op_name == "cdb_create_doc_from_template":
            if not ctx.catalog_requery:
                if "templatecatalogargsset" not in ctx.ue_args.get_attribute_names():
                    ctx.keep("templatecatalogargsset", "1")
                    ctx.set("cdb_obsolete", "0")
                    # We might got some decomposition-attributes by on_cdb_create_doc_from_template_now
                    for attr in ctx.catalog_invoking_dialog.get_attribute_names():
                        if attr[-15:] == "_initalqueryarg":
                            ctx.set(attr[:-15], ctx.catalog_invoking_dialog[attr])

    @classmethod
    def on_cdb_create_doc_from_template_now(cls, ctx):
        """
        Create an document by selecting an template and copy it
        """

        def _uniquote(s):
            if isinstance(s, str):
                v = s.encode("utf-8")
            else:
                v = s
            return quote(v)

        if ctx.relationship_name == "cdb_referenced_docs":
            raise ue.Exception("error_cdb_doc_rel_create_interactive")

        if ctx.uses_webui:
            url = "/cs-documents/template_creation"
            if ctx.relationship_name:
                # We have to provide information about the relationship and the
                # parent
                rs = relships.Relship.ByKeys(ctx.relationship_name)
                cdef = entities.CDBClassDef(rs.referer)
                o = support._RestKeyObj(cdef, ctx.parent)
                key = support.rest_key(o)
                url += "?classname=%s&rs_name=%s&keys=%s" % (
                    _uniquote(rs.referer),
                    _uniquote(rs.rolename),
                    _uniquote(key),
                )
            ctx.url(url)
            return

        # Get the project
        if not ctx.catalog_selection:
            kwargs = {}
            # If we are in a decomposition, evaluate the predefined attributes
            if "decompositionclsid" in ctx.sys_args.get_attribute_names():
                decomposition = ctx.sys_args["decompositionclsid"]
                if decomposition:
                    # get predefined attrs, e.g. from decompositions
                    cdef = entities.CDBClassDef(decomposition)
                    predef_args = cdef.getPredefinedOpArgs("CDB_Search", True)
                    for arg in predef_args:
                        # This one is for the catalog configuration
                        # to behave as if the attributes were in the
                        # dialog
                        kwargs[arg.name] = arg.value
                        # This one is for _set_template_catalog_query_args
                        kwargs[arg.name + "_initalqueryarg"] = arg.value

            ctx.start_selection(catalog_name="cdb_doc_template", **kwargs)
        else:
            znumber = ctx.catalog_selection[0]["z_nummer"]
            zidx = ctx.catalog_selection[0]["z_index"]
            template = Document.ByKeys(znumber, zidx)
            predef = [("erzeug_system", template["erzeug_system"])]
            ueargs = []
            if template.ShouldCallEditAfterTemplateCreation(ctx):
                ueargs = [("runeditaftercreate", "1")]
            # Zerlegungsattribute vorbelegen
            if "decompositionclsid" in ctx.sys_args.get_attribute_names():
                decomposition = ctx.sys_args["decompositionclsid"]
                if decomposition:
                    # get predefined attrs, e.g. from decompositions
                    cdef = entities.CDBClassDef(decomposition)
                    predef_args = cdef.getPredefinedOpArgs("CDB_Create", True)
                    for arg in predef_args:
                        predef.append((arg.name, arg.value))

            ctx.set_followUpOperation(
                opname="CDB_Create",
                keep_rship_context=True,
                opargs=ueargs,
                predefined=predef,
                tmpl_object=template,
            )

    def _copy_classification_data_from_template(self, ctx):
        """
        Copies the classification data from the template.
        """
        try:
            from cs.classification import copy_classification, prepare_read

            try:
                prepare_read(self.obj.GetClassname())
            except Exception:  # nosec # pylint: disable=broad-except
                # no license
                return

            template_id = getattr(ctx.cdbtemplate, "cdb_object_id", None)
            if template_id:
                copy_classification(template_id, self)
        except ImportError:
            # No classification
            pass

    def _handle_template_create_pre_mask(self, ctx):  # pylint: disable=no-self-use
        """
        At this time classification properties cannot be predefined.
        So we have to skip the classification register.
        """
        if getattr(ctx.cdbtemplate, "cdb_object_id", None):
            ctx.disable_registers(
                [
                    "cs_classification",
                    "cs_classification_web",
                    "cs_classification_tab_c",
                    "cs_classification_tab_c_web",
                ]
            )

    def _handle_template_create_post(self, ctx):
        self._copy_classification_data_from_template(ctx)
        if "runeditaftercreate" in ctx.ue_args.get_attribute_names():
            ft = kernel.CDBFileType(self.erzeug_system)
            if ft.getEditMode() != "None":
                ctx.set_followUpOperation(opname="CDB_Edit", use_result=True)

    def delete_batch_op_assignments(self, ctx):
        """Delete any references to batch operations for a deleted document."""
        if not ctx.error:
            assgns = BatchOperationDocumentAssignment.KeywordQuery(
                z_nummer=self.z_nummer, z_index=self.z_index
            )
            assgns.Delete()
            # Delete associated long text fields
            sqlapi.SQLdelete(
                ("FROM cdbbop_doc_log WHERE z_nummer = '%s' AND z_index = '%s'")
                % (sqlapi.quote(self.z_nummer), sqlapi.quote(self.z_index))
            )

    def purgeFileHistoriesAfterRelease(self, ctx):
        """After release of a document, remove old versions of all files
        attached to this document.
        """
        if not ctx.error and self.status == 200:
            for f in self.Files:
                f.purgeFileHistory()

    def IsFileConversionStatus(self, status=None):
        """
        Called by the standard to determine if file conversion
        jobs should be created if the given `status` is the target
        status of a status change. It is also called to determine if
        the modification of a file should result in creating a new
        conversion job. If the caller does not provide
        a status the status of `self` is used.
        """
        if status is None:
            status = self.z_status

        return status in [100, 200]

    def handleFileConversionOnStatusChange(self, ctx):
        """
        Creates a conversion job if the new status is returned
        by `IsFileConversionStatus`
        """
        enable = self.enableConversionJobHandling("status_change")
        if enable and self.IsFileConversionStatus(self.status):
            primary_only = enable == 1
            self.createConvertJob(ctx, primary_only)

    ################################################################################
    # File related methods

    def getExternalFilename(self, suffix=None):
        """Returns the filename to use for an attached file with the given
        suffix. If suffix == None, use the name of the primary file if one
        exists.
        If no file with the desired suffix exists, compute the standard
        filename to use and return that.
        """
        if suffix:
            files = self.getFilesBySuffix(suffix)
        else:
            files = self.getPrimaryFiles()
        if files:
            return files[0].cdbf_name
        # no matching file found; see if we have to derive the suffix from our
        # file type
        if suffix:
            return self.ToObjectHandle().getStandardFilenameBySuffix(suffix)
        else:
            return self.ToObjectHandle().getStandardFilenameByFileTypeName(
                self.erzeug_system
            )

    def getPrimaryFile(self):
        """Get the (single) primary file from the document. If there is more
        than one, issue a log message and take the first one found. If no
        primary file is found, raise an Exception.
        """
        primary_files = self.getPrimaryFiles()
        if not primary_files:
            raise Exception("No primary file for %s-%s" % (self.z_nummer, self.z_index))
        else:
            if len(primary_files) > 1:
                _Logger.info(
                    "%d primary files for %s-%s",
                    len(primary_files),
                    self.z_nummer,
                    self.z_index,
                )
            return primary_files[0]

    def checkoutPrimaryFile(self, dstFPName):
        """Check out the primary file for this document to the given path.
        Returns the checked out file
        """
        primary_file = self.getPrimaryFile()
        primary_file.checkout_file(dstFPName)
        return primary_file

    def getFilesBySuffix(self, suffix=None):
        """Return a list of files with the given suffix."""
        if not suffix:
            return self.getPrimaryFiles()
        result = []
        for f in self.Files:
            if f.cdbf_name.lower().endswith(suffix.lower()):
                result.append(f)
        return result

    def getFileBySuffix(self, suffix=None):
        """Return a files with the given suffix, if the Document has one. If
        more than one file with this suffix is found, a randomly choosen
        one is returned. If no file is found, returns None.
        """
        lst = self.getFilesBySuffix(suffix)
        if not lst:
            return None
        else:
            return lst[0]

    def checkoutFile(self, dstFPName, suffix=None):
        """Check out the file with the given suffix to the given path. No
        suffix means to get the primary file. If more than one file with
        the suffix exists, the first one encountered in the list is used.
        If no file is found, the function will raise an Exception.
        Returns the checked out file.
        """
        if not suffix:
            return self.checkoutPrimaryFile(dstFPName)
        else:
            f = self.getFileBySuffix(suffix)
            if f:
                f.checkout_file(dstFPName)
                return f
            raise Exception(
                "No file with suffix '%s' for %s-%s"
                % (suffix, self.z_nummer, self.z_index)
            )

    def checkinFile(self, srcFPName, primary=False):
        """Check in a file. Searches for a file with the same file name, and
        overwrites that if found. Otherwise, creates a new file. If a new
        file is created, set the primary flag according to the parameter.
        Returns the checked in file
        """
        fname = os.path.basename(srcFPName)
        the_file = None
        for f in self.Files:
            if f.cdbf_name.lower() == fname.lower():
                the_file = f
                break
        if the_file:
            # we found an existing file, so use that
            the_file.checkin_file(srcFPName)
        else:
            # create a new file
            the_file = CDB_File.NewFromFile(self.cdb_object_id, srcFPName, primary)
        return the_file

    def get_preview_file(self):
        """
        Deprecated function to get a preview file.
        Use `GetPreviewFile` instead.
        """
        import warnings

        warnings.warn(
            "Documents.get_preview_file is deprecated. Use GetPreviewFile instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.GetPreviewFile()

    ################################################################################
    # CAD specific stuff, handled via strategy object

    def _getCadStrategy(self):
        """Returns the strategy object to handle calls to this document. If
        necessary, the strategy is created.
        """
        # FIX: Caching temporarily disabled due to E023381
        # cs = getattr(self, '_cad_strategy', None)
        if True:  # cs is None: # pylint: disable=using-constant-test
            from cs.documents.docref_resolver_registry import Registry

            cs = Registry.getStrategy(self)
            self._cad_strategy = cs
        return cs

    def getProjectValue(self):
        return self._getCadStrategy().getProjectValue()

    def getPrimaryFiles(self):
        """Returns the primary files for this Document, or in the case of a
        multi sheet drawing, the primary files of the Document representing
        the first sheet.
        """
        the_doc = self._getCadStrategy().getDrawingOfSheet()
        return [f for f in the_doc.Files if f.cdbf_primary == "1"]

    def getAllRefDocs(self, include_wsm_refs=False):
        # include_wsm_refs: temporary fix for E023381
        cs = self._getCadStrategy()
        cs._include_wsm_refs = include_wsm_refs
        return cs.getAllRefDocs()

    def getSMLModels(self):
        return self._getCadStrategy().getSMLModels()

    def getChildren(self, include_wsm_refs=False):
        # include_wsm_refs: temporary fix for E023381
        cs = self._getCadStrategy()
        cs._include_wsm_refs = include_wsm_refs
        return cs.getChildren()

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the HTML display in the client."""
        results = super(Document, self).GetDisplayAttributes()
        results["viewurl"] = str(self.MakeURL("CDB_View"))
        results.update(
            {
                "iconPopUp": "Format: %s" % (str(self["erzeug_system"])),
                "showMore": "1",
            }
        )
        heading = [
            self[f]
            for f in ["category1_name", "category2_name", "category3_name"]
            if self.HasField(f, addtl_field_type=any) and self[f] not in (NULL, "")
        ]
        results["attrs"].update(
            {
                "person": str(self.zeichner if self.zeichner != NULL else ""),
                "heading": " - ".join(heading),
            }
        )
        return results

    # file events: these are called from CDB_File event handlers
    def fileCreated(self, the_file, ctx=None):
        """
        Called when a new file has been assigned to the document.

        :param self: If the user setting with the id
            ``cs.documents.fileevent.use_object_handle``-``create`` is ``1``
            self is constructed using a `cdb.platform.mom.CDBObjectHandle` which
            avoids the statement to construct a persistent `cs.documents.Document`
            object. If you need to call any modifying operation you have to use
            `cdb.objects.Object.getPersistentObject` in this case.
        :param the_file: A `cdb.objects.cdb_file.CDB_File` object that
            represents the file created.
        :param ctx: The `cdb._ctx.Context` of the current operation.
        """
        pass

    def fileModified(self, the_file, ctx=None):
        """
        Called when a file that is assigned to the document has been modified.

        :param self: If the user setting with the id
            ``cs.documents.fileevent.use_object_handle``-``modify`` is ``1``
            self is constructed using a `cdb.platform.mom.CDBObjectHandle` which
            avoids the statement to construct a persistent `cs.documents.Document`
            object. If you need to call any modifying operation you have to use
            `cdb.objects.Object.getPersistentObject` in this case.
        :param the_file: A `cdb.objects.cdb_file.CDB_File` object that
            represents the file modified.
        :param ctx: The `cdb._ctx.Context` of the current operation.
        """
        pass

    def fileDeleted(self, the_file, ctx=None):
        """
        Called when a file that is assigned to the document has been deleted.

        :param self: If the user setting with the id
            ``cs.documents.fileevent.use_object_handle``-``delete`` is ``1``
            self is constructed using a `cdb.platform.mom.CDBObjectHandle` which
            avoids the statement to construct a persistent `cs.documents.Document`
            object. If you need to call any modifying operation you have to use
            `cdb.objects.Object.getPersistentObject` in this case.
        :param the_file: A `cdb.objects.cdb_file.CDB_File` object that
            represents the file.
        :param ctx: The `cdb._ctx.Context` of the current operation.
        """
        pass

    def fileLocked(self, the_file, ctx=None):
        """
        Called when a file assigned to this Document has been locked.

        :param self: If the user setting with the id
            ``cs.documents.fileevent.use_object_handle``-``CDB_Lock`` is ``1``
            self is constructed using a `cdb.platform.mom.CDBObjectHandle` which
            avoids the statement to construct a persistent `cs.documents.Document`
            object. If you need to call any modifying operation you have to use
            `cdb.objects.Object.getPersistentObject` in this case.
        :param the_file: A `cdb.objects.cdb_file.CDB_File` object that
            represents the file.
        :param ctx: The `cdb._ctx.Context` of the current operation.
        """
        pass

    def fileUnlocked(self, the_file, ctx=None):
        """
        Called when a file assigned to this Document has been unlocked.

        :param self: If the user setting with the id
            ``cs.documents.fileevent.use_object_handle``-``CDB_Unlock`` is ``1``
            self is constructed using a `cdb.platform.mom.CDBObjectHandle` which
            avoids the statement to construct a persistent `cs.documents.Document`
            object. If you need to call any modifying operation you have to use
            `cdb.objects.Object.getPersistentObject` in this case.
        :param the_file: A `cdb.objects.cdb_file.CDB_File` object that
            represents the unlocked file.
        :param ctx: The `cdb._ctx.Context` of the current operation.
        """
        pass

    def on_create_pre(self, ctx):
        self.cdb_obsolete = 0

    def GetActivityStreamTopics(self, posting):
        """
        Returns the Activity stream topics where a posting to the
        document should occure. The default implementation assigns
        a posting to the project and the object itself.
        """
        return [self, self.Project] if hasattr(self, "Project") else [self]

    @classmethod
    def GetSpecificVersion(cls, docs, method_name):
        """
        Used by the REST API for collections if the query parameter
        ``one_version_method`` is set. If you want to provide your own
        implementations you have to overwrite this method.

        :param docs: A list of cs.documents.Document objects. If it is an
           `ObjectCollection` the caller should call `Execute` on the
           collection to avoid unecessary SQL traffic

        :param method_name: The name of a rule that determines the version.
           You can use ``GetLatestObjectVersion`` to call
           `GetLatestObjectVersion`.

        :returns: The cdb.objects.Object or ``None``
        """
        if method_name == "GetLatestObjectVersion":
            return cls.GetLatestObjectVersion(docs)
        return None

    @classmethod
    def GetLatestObjectVersion(cls, docs):
        """Used by the REST API, this gets a list of document versions, and
        returns the latest released version from this list. If no such
        version exists, try in_revision versions, and as a fallback just
        take the latest versions.
        """
        # First of all, sort by index, so that we can return the highest index
        # if more than one match.
        sorted_docs = sorted(docs, key=lambda d: (len(d.z_index), d.z_index))
        released = [d for d in sorted_docs if d.z_status in (200, 300)]
        if released:
            return released[-1]
        in_revision = [d for d in sorted_docs if d.z_status == 190]
        if in_revision:
            return in_revision[-1]
        # Fallback: just return the highest index
        return sorted_docs[-1] if sorted_docs else None

    @classmethod
    def DocumentFromRestKey(cls, vals):
        # Keys may be:
        #   doc_number
        #   doc_number + doc_index
        #   doc_number + function_name
        if len(vals) == 1:
            docs = cls.KeywordQuery(z_nummer=vals[0]).Execute()
            # If there is more than one document, but no more keys, return the
            # latest version. Call the function with a document instance, so that
            # a customer subclass can override this.
            # Note: assumes that all versions of a document are of the same class!
            return docs[0].GetLatestObjectVersion(docs) if docs else None
        elif len(vals) == 2:
            # Assume doc_number + doc_index
            return cls.ByKeys(*vals)
        elif len(vals) == 3 and vals[1] == "one_version_method":
            docs = cls.KeywordQuery(z_nummer=vals[0]).Execute()
            # ... or a function (see comment above)
            if not docs:
                return None
            return docs[0].GetSpecificVersion(docs, vals[2])
        else:
            raise ValueError("DocumentFromRestKey: cannot interpret %s" % vals)

    def GetReferencedDocsWithInvalidState(self, validStateList):
        """
        Returns a list of documents that are referenced by `self` and
        does not have a state listed in `validStateList`.
        """
        state_cond = ",".join([str(state) for state in validStateList])
        # self.DocumentReferences is not used because of performance issues
        t = sqlapi.SQLselect(
            "r.z_nummer2, r.z_index2 FROM "
            "cdb_doc_rel r, zeichnung z WHERE "
            "r.z_nummer='%s' AND r.z_index='%s' "
            "AND r.z_nummer2=z.z_nummer "
            "AND r.z_index2=z.z_index "
            "AND z.z_status not in (%s)"
            % (sqlapi.quote(self.z_nummer), sqlapi.quote(self.z_index), state_cond)
        )
        return [
            Document.ByKeys(sqlapi.SQLstring(t, 0, i), sqlapi.SQLstring(t, 1, i))
            for i in range(sqlapi.SQLrows(t))
        ]

    @classmethod
    def on_cdbdoc_decomp_now(cls, ctx):
        cls.GenerateDecomposition()

    @classmethod
    def GenerateDecomposition(cls):
        sa = util.PersonalSettings().getValueOrDefaultForUser(
            "decomp_sort_attribute", "DOC", "caddok", "name_d"
        )
        decompsource = decomp.DecompSource(
            source_id=None,
            relation="cdb_doc_categ",
            key_attr="categ_id",
            parent_key_attr="parent_id",
            attribute_mappings={"z_categ<level>": "categ_id"},
            c_conditions={},
            s_conditions={},
            label_attribute="name_<language>",
            position_attr="",
            icon_attr="icon_id",
            leaf_attr="leaf",
            default_icon="Folder",
            leaf_icon="Folder",
            root_id="",
            order_by=sa,
            table_attr="tab_name",
            py_generator=__name__ + ".Document.GenerateDecomposition",
            obsolete_attr="obsolete",
        )
        # remove decompositions based on the source object
        decompsource.delete_decompositions()
        # create filter object
        myfilter = decomp.DecompSourceFilter("cdb_dcat_decomp", "decomp_name")
        # create decompositions
        decompsource.generate_decompositions("DOC", myfilter)

    def GetExcludedFieldsOnExport(self):  # pylint: disable=no-self-use
        return ["cdb_lock", "wsp_lock_id", "share_status"]

    def getAuthorSubjects(self, sharingGroup):
        "support for ObjectSharingGroup 'Authors'"
        author_names = self.autoren.split("/")
        authors = []
        if author_names:
            authors = User.KeywordQuery(name=author_names)
        return RecipientCollection(authors).subjects

    def getReleasedBySubjects(self, sharingGroup):
        "support for ObjectSharingGroup 'ReleasedBy'"
        return RecipientCollection(User.KeywordQuery(name=self.pruefer)).subjects

    def GetOLCRelevantAttributes(self):  # pylint: disable=no-self-use
        """
        The function should return a list of attributes that are relevant
        for `CalculateOLC` to determine the object life cycle.
        """
        return []

    def GetReadonlyAttrsIfOLCStarted(self):
        """
        Returns a list of attributes that should be set readonly if
        the document has left the initial state. The default implementation
        calls `GetOLCRelevantAttributes`.
        """
        return self.GetOLCRelevantAttributes()

    def _OLCRelevantAttrsChanged(self, ctx):
        """
        Returns the list of attributes that are relevant for calculating
        the object life cylde where the value of `ctx.dialog.attr` differs
        from `self.attr`.
        """
        result = []
        for attr in self.GetOLCRelevantAttributes():
            if getattr(ctx.dialog, attr, self[attr]) != ctx.object[attr]:
                result.append(attr)
        return result

    def CalculateOLC(self, ctx):  # pylint: disable=no-self-use
        """
        The function is called to calculate the object life cycle from the
        attributes provided by ctx.dialog or self. You can overwrite this
        function to adapt the system behaviour. If there is no rule, you should
        return ``None``. The function is used to prevent object
        modifications that implies a change of the object life cycle if the
        document state is not ``0``.
        """
        return None

    def _handleOLCRo(self, ctx):
        if self.z_status == 0:
            return
        attrs = self.GetReadonlyAttrsIfOLCStarted()
        result = list(attrs)  # short list for source_attr in attrs
        # Check if there are attributs - especially mapped attributes, that
        # depends on the attributes used for calculation
        for adef in self.GetClassDef().getAttributeDefs():
            source_attrs = adef.getSQLSelectNames()
            for source_attr in source_attrs:
                if source_attr in attrs:
                    result.append(adef.getName())
        ctx.set_fields_readonly(result)

    def _adaptOLC(self, ctx):
        """
        Calls `CalculateOLC` to determine the suitable object life cycle.
        If the life cycle differs from the actual one and the status is
        ``0`` the lifecylce is changed. If the status is not ``0`` the
        modification is refused.
        """
        changed_attrs = self._OLCRelevantAttrsChanged(ctx)
        if changed_attrs:
            new_olc = self.CalculateOLC(ctx)
            if new_olc is not None and new_olc != self.z_art:
                if self.z_status == 0:
                    ctx.set("z_art", new_olc)
                    ctx.set("z_status_txt", olc.StatusInfo(new_olc, 0).getStatusTxt())
                else:
                    cdef = self.GetClassDef()
                    changed_attrs = ", ".join(
                        [
                            cdef.getAttributeDefinition(attr).getLabel()
                            for attr in changed_attrs
                        ]
                    )
                    raise ue.Exception("err_modify_new_olc", changed_attrs)

    def IsValidInteractiveTargetStatus(
        self, target_status
    ):  # pylint: disable=no-self-use
        """
        Called by the framework as an additional check if a target status
        should be selectable by an user. If you return ``False`` the standard
        implementation ensures that the status is excluded in the target status
        catalog of the operation ``CDB_Workflow``. Trying to set the status of
        `self` to `target_status` using a batch operation will also fail.
        You can overwrite this function to exclude status from interactive
        use.
        """
        return True

    def _exclude_batchonly_states(self, ctx):
        # Exclude states that cannot be used interactive
        # Using a batch operation is a kind of interaction
        if not ctx.batch:
            for status in ctx.statelist:
                if not self.IsValidInteractiveTargetStatus(status):
                    ctx.excl_state(status)

    @classmethod
    def IsRelevantForLastFileModification(cls, f):
        """
        Returns ``True`` if the attribute ``cdb_m2date`` should be set
        if the file `f` is created or saved. The default implementation
        looks at the default setting ``cs.documents.m2date_force_primary``.
        If it is True only primary files leads to a change of the attribute
        which is more performant. If not all non derived files will change
        the date.
        """
        if not f:
            return False
        primary_only = False
        try:
            s = util.PersonalSettings()["cs.documents.m2date_force_primary"]
            primary_only = typeconversion.to_bool(s)
        except KeyError:
            pass
        if primary_only:
            return f.cdbf_primary == "1"
        return not (f.cdb_belongsto or f.cdbf_derived_from)

    @classmethod
    def GetDefaultErzSystem(cls):
        """
        Retrieve the default that has to be used to initialize the
        attribute ``erzeug_system`` from the personal setting
        ``cs.documents.default_cad``.
        """
        try:
            return util.PersonalSettings()["cs.documents.default_cad"]
        except KeyError:
            return "-"

    @classmethod
    def GetInitialCreateValues(cls):
        """
        The function is called for `CDB_Create`
        to retrieve initial values as ``dict``.
        For interactive operations these attributes
        are set during the ``pre_mask`` call. For batch operations the
        attributes are set in ``pre`` if no value is supplied before.
        """
        return {"cdb_obsolete": 0}

    @classmethod
    def GetInitialIndexValues(cls):
        """
        The function is called for `CDB_Index`
        to retrieve values as ``dict`` that should not be
        copied from the previous version.
        For interactive operations these attributes
        are set during the ``pre_mask`` call. For batch operations the
        attributes are set in ``pre``.
        """
        return {"cdb_obsolete": 0}

    @classmethod
    def GetInitialCopyValues(cls):
        """
        The function is called for `CDB_Copy`
        to retrieve values as ``dict`` that should not be
        copied from the previous version.
        For interactive operations these attributes
        are set during the ``pre_mask`` call. For batch operations the
        attributes are set in ``pre``.
        """
        # Copy is the same as creating a new document
        result = cls.GetInitialCreateValues()
        # At least all attributes resetted for a new version has to
        # be resetted too
        result.update(cls.GetInitialIndexValues())
        return result

    @classmethod
    def CalculateSourceOID(cls, ctx):  # pylint: disable=inconsistent-return-statements
        """
        Called by the framework to set the ``source_oid`` attribute
        during the creation of a document.
        The default returns the ``cdb_object_id`` of the template if you
        use :guilabel:`Create from template` and the ``cdb_object_id`` of the
        copy source if the ``CDB_Copy`` operation is used.
        """
        if ctx.action == "create" and ctx.cdbtemplate:
            return getattr(ctx.cdbtemplate, "cdb_object_id", None)
        elif ctx.action == "copy":
            return ctx.object.cdb_object_id

    def _handle_initial_values(self, ctx):
        vals = {}
        if ctx.action == "create":
            vals = self.GetInitialCreateValues()
            if (
                "erzeug_system" not in vals
                and not ctx.cad_system
                and not getattr(ctx.dialog, "erzeug_system", "")
            ):
                dflt = self.GetDefaultErzSystem()
                if dflt:
                    vals["erzeug_system"] = self.GetDefaultErzSystem()

        elif ctx.action == "copy":
            vals = self.GetInitialCopyValues()
        elif ctx.action == "index":
            vals = self.GetInitialIndexValues()
        if ctx.action in ("copy", "index"):
            if "wsp_filename" not in vals:
                sid = "cs.documents.clear_wsp_filename"
                val = util.PersonalSettings()[(sid, ctx.action)]
                if typeconversion.to_bool(val):
                    vals["wsp_filename"] = ""
        source_oid = self.CalculateSourceOID(ctx)
        if source_oid:
            vals["source_oid"] = source_oid
        for attr, value in vals.items():
            # At create set if no different value is supplied, e.g. by the wsm
            # At other times reset the existing one
            if not getattr(ctx.dialog, attr, "") or ctx.action != "create":
                if ctx.mode == "pre_mask" or (
                    not ctx.interactive and not ctx.uses_webui
                ):
                    ctx.set(attr, value)

    def GetASAutoSubscriptions(self):
        """
        The function is called to determine which subscriptions to the
        documents activity stream should be done automatically on creation.
        The default implementation adds the creator of the document if the
        setting ``cs.documents.creation.autosubscribe`` is set to ``1``.
        """
        result = []  # Default behaviour - no subscription
        try:
            sid = "cs.documents.creation.autosubscribe"
            val = util.PersonalSettings()[(sid, "")]
            if typeconversion.to_bool(val) and self.cdb_cpersno:
                result.append(self.cdb_cpersno)
        except KeyError:
            # No setting - return the default
            pass
        return result

    def _handle_as_auto_subscription(self, ctx):
        if not ctx.error:
            plist = self.GetASAutoSubscriptions()
            for persno in plist:
                Subscription.subscribeToChannel(self.cdb_object_id, persno)

    @classmethod
    def CategoryAttributeNames(cls):
        def to_int(s):
            if s:
                try:
                    return int(s)
                except ValueError:
                    pass
            return None

        result = []
        ti = util.tables["zeichnung"]
        for i in range(ti.number_columns()):
            colname = ti[i].name()
            if colname.find(cls.kCategoryAttrPrefix) == 0 and to_int(
                colname[len(cls.kCategoryAttrPrefix) :]
            ):
                result.append(colname)
        result.sort()
        return result

    def get_template_preset_attributes(self):
        """
        Return a list of attribute names that are to be copied from the
        template document, when the operation :guilabel:`New from template`
        is called. You may overwrite this method to customize the list of
        attributes.
        """
        return self.CategoryAttributeNames()

    def preset_template_attributes(self, ctx):
        """
        Copy attributes from a template document bevor showing the
        document creation mask. The standard implementation copies
        every attribute returned by `get_template_preset_attributes`
        from the template if no value has been defined before.
        """
        if ctx.action == "create":
            # Check for action here instead of creating a separate event_map
            # entry so that the call order is kept from the event map.
            tmpl = ctx.cdbtemplate
            if tmpl and int(tmpl.vorlagen_kz):
                for attr in self.get_template_preset_attributes():
                    if attr in tmpl.get_attribute_names() and not self[attr]:
                        self[attr] = tmpl[attr]

    def GetReviewer(self):
        """
        Returns a list of personal numbers of the persons that should
        review or have reviewed the document. This is e.g. used to implement
        the recipient list :guilabel:`Reviewer` of the sharing. The default
        tries to map the value of the attribute ``pruefer`` to the
        personal no.
        """
        return User.KeywordQuery(name=self.pruefer).personalnummer

    def getReviewerSharingRecipients(self, sharing_group):
        """
        Used for the sharing_group ``Reviewer`` to calculate the
        recipients.
        """
        return [(persno, "Person") for persno in self.GetReviewer()]

    def HandleUnlockForeignLock(self, f, previous_locker, ctx):
        """
        The framework calls this function as part of the ``post``
        user exit of the ``CDB_Unlock`` action of the class
        `cdb.objects.Object.cdb_file.CDB_File` if the user has unlocked
        a file locked by the user identified by `previous_locker`.
        The function generates a sharing to send this information to
        the previous locker. You might overwrite the function to adapt
        this behaviour.
        """
        prev_locker = User.ByKeys(previous_locker)
        if prev_locker:
            msg_lang = prev_locker.GetPreferredLanguage()
            msg = util.CDBMsg(
                util.CDBMsg.kNone, "cs.documents.file_unlocked_sharing_text"
            )
            msg.addReplacement(prev_locker.name)
            msg.addReplacement(f.GetDescription())
            msg.addReplacement(self.GetDescription())
            msg.addReplacement(auth.name)
            text = msg.getText(msg_lang, True)
            Sharing.createFromObjects(
                [self], subjects=[(previous_locker, "Person")], text=text
            )

    def ShouldCallEditAfterTemplateCreation(self, ctx=None):
        """
        Called by the framework to evaluate if the operation :guilabel:`Edit'
        should be started automatically after creating a document from a
        template. The default implementation looks at the default setting
        of `cs.documents.template_creation.call_edit` with ``erzeug_system``
        as section parameter. You might overwrite this function to add
        different behaviour.

        :param ctx: The context adaptor of the template create operation

        :returns: ``True`` if the edit operation should be called automatically
        """
        result = True  # Default behaviour
        try:
            sid = "cs.documents.template_creation.call_edit"
            val = util.PersonalSettings()[(sid, self.erzeug_system)]
            result = typeconversion.to_bool(val)
        except KeyError:
            # No setting - return the default
            pass
        return result

    @classmethod
    def restrictConversionJobHandlingToPrimFiles(cls):
        """
        Returns ``True`` if the standard should only create
        jobs for primary files.
        """
        return False

    @classmethod
    def enableConversionJobHandling(cls, action):
        """
        The function is called to determine if conversion jobs should be
        created automatically for the given `action`. You can overwrite this
        function to modify the behaviour.

        :param action: At this time always ``status_change``

        :return: ``0`` if the code should not create jobs for the action,
            ``1`` if the code should create jobs for the primary files,
            ``2`` if the code should create jobs for all non derived files
        """
        if action == "status_change":
            return 1 if cls.restrictConversionJobHandlingToPrimFiles() else 2
        return 0

    def createConvertJob(self, ctx=None, primary_files=True):
        """
        Searches for possible conversions for each (primary) file of
        the document and creates the jobs. If you call the
        function as part of an user exit you can provide the `ctx`.
        Future versions might display a success or failure message in this
        case.

        :param primary_files: If ``True`` jobs are created only for primary
            files. If ``False`` all files that are not derived will be
            inspected.
        """
        from cdb.acs import convertFile, registered_conversions

        if primary_files:
            files = self.PrimaryFiles
        else:
            files = [f for f in self.Files if not f.cdbf_derived_from]
        for f in files:
            for (target, _plugin) in registered_conversions(f.cdbf_type):
                if target == "multi_target":
                    # multi_target needs parameter so skip conversion for now
                    # if there is more information available from the conversion plugins conversions can
                    # be skipped or combined here (see E070406)
                    continue
                convertFile(f, target)

    def transfer_file_office_to_pdf(self, ctx=None, primary_files=True):
        from cdb.acs import convertFile, registered_conversions
        if primary_files:
            files = self.PrimaryFiles
        else:
            files = [f for f in self.Files if not f.cdbf_derived_from]
        for f in files:
            for (target, _plugin) in registered_conversions(f.cdbf_type):
                if "pdf" == target:
                    try:
                        convertFile(f, target)
                    except Exception:
                        continue


    @classmethod
    def on_doc_create_acs_job_now(cls, ctx):
        primary_only = cls.restrictConversionJobHandlingToPrimFiles()
        for obj in cls.PersistentObjectsFromContext(ctx):
            obj.createConvertJob(ctx, primary_only)

    def _prevent_create_in_docref_rship(cls, ctx):  # pylint: disable=no-self-use
        """
        The entries in ``cdb_doc_rel`` should only be created by
        the WSM or other integrations - so prevent creating objects
        within the relationship.
        """
        if ctx.relationship_name == "cdb_referenced_docs":
            raise ue.Exception("error_cdb_doc_rel_create_interactive")

    def reset_effectivity_dates(self, ctx):
        """
        Resets both `ce_valid_from` and `ce_valid_to` to `None`. By default, this method is used by the copy
        pre_mask step to clear the dates when copying an existing document.
        """
        self.ce_valid_from = None
        self.ce_valid_to = None

    def set_never_effective(self, ctx, keep_existing):
        """
        Sets the document as never being valid yet.

        :param keep_existing: If True and `ce_valid_from` is already set, neither `ce_valid_from` nor
            `ce_valid_to` will be changed.
            Otherwise, `ce_valid_from` will be set to the `NEVER_VALID_DATE` and `ce_valid_to` will be set to
            None.
        """
        if keep_existing and self.ce_valid_from:
            return

        self.ce_valid_from = NEVER_VALID_DATE
        self.ce_valid_to = None

    def set_effectivity_dates_on_state_change(self, ctx):
        """
        Handles the effectivity changes when changing the document life cycle status.

        By default, when the document is released, the document is set as valid (`ce_valid_from` is set to the
        date of the state change). When the document is set as obsolete, `ce_valid_to` is set to the date of
        the state change.
        """
        if ctx.new.z_status == "200":
            self.getPersistentObject().Update(
                ce_valid_from=datetime.utcnow(), ce_valid_to=None
            )
        elif ctx.new.z_status in ["170", "180"]:
            self.getPersistentObject().Update(ce_valid_to=datetime.utcnow())

    event_map = {
        (("create", "copy", "index"), ("pre_mask", "pre")): ("_handle_initial_values"),
        (("create", "copy", "index"), ("post")): ("_handle_as_auto_subscription"),
        (("copy", "create"), "pre"): ("setDocumentNumber"),
        (("copy", "create"), "pre_mask"): (
            "_prevent_create_in_docref_rship",
            "preset_template_attributes",
        ),
        ("create", "pre_mask"): ("_handle_template_create_pre_mask"),
        ("create", "post"): ("_handle_template_create_post"),
        ("query_catalog", ("pre_mask", "pre")): ("_set_template_catalog_query_args"),
        ("delete", "post"): ("delete_batch_op_assignments"),
        ("state_change", "pre_mask"): ("_exclude_batchonly_states"),
        ("state_change", "post"): (
            "handleFileConversionOnStatusChange",
            "purgeFileHistoriesAfterRelease",
        ),
        ("modify", "pre_mask"): ("_handleOLCRo"),
        ("modify", "pre"): ("_adaptOLC"),
    }


# If a file connected to a Document changes, trigger propagation to the Document
# instance.
@sig.connect(FILE_EVENT, Document.__maps_to__, any)
def _file_event_handler(the_file, doc_obj_hndl, ctx):
    use_object_handle = False
    try:
        sid = "cs.documents.fileevent.use_object_handle"
        val = util.PersonalSettings()[(sid, ctx.action)]
        use_object_handle = typeconversion.to_bool(val)
    except KeyError:
        # No setting - use the cs.documents.Document object
        pass
    if use_object_handle:
        doc = Document._FromObjectHandle(doc_obj_hndl)
    else:
        doc = Document.ByKeys(
            doc_obj_hndl.getValue("z_nummer", False),
            doc_obj_hndl.getValue("z_index", False),
        )
    if doc is None:
        return
    if ctx.action == "create":
        doc.fileCreated(the_file, ctx)
        doc.transfer_file_office_to_pdf(ctx, False)
    elif ctx.action == "modify":
        doc.fileModified(the_file, ctx)
    elif ctx.action == "delete":
        doc.fileDeleted(the_file, ctx)
    elif ctx.action == "CDB_Lock":
        doc.fileLocked(the_file, ctx)
    elif ctx.action == "CDB_Unlock":
        doc.fileUnlocked(the_file, ctx)
        previous_locker = getattr(ctx.sys_args, "previous_locker", "")
        if previous_locker and previous_locker != auth.persno:
            doc.HandleUnlockForeignLock(the_file, previous_locker, ctx)


@sig.connect(CDB_File, "relship_navigate", "now")
def _hide_hidden_files(self, ctx):
    if ctx.relationship_name == "document2visible_cdb_file":
        ctx.setFilter("cdbf_hidden", 0)


class ChangeCause(Object):
    __maps_to__ = "cdb_mod_event"


class ChangeSource(Object):
    __maps_to__ = "cdb_mod_source"


class ChangeType(Object):
    __maps_to__ = "cdb_mod_kind"
