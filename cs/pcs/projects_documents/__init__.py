#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import logging

from cdb import auth, cad, kernel, misc, sig, ue, util
from cdb.classbody import classbody
from cdb.constants import kOperationCopy, kOperationShowObject
from cdb.objects import (
    ByID,
    Forward,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_1,
    ReferenceMethods_N,
    TableNotFound,
)
from cdb.objects.operations import operation
from cdb.platform.gui import PythonColumnProvider
from cdb.platform.olc import StatusInfo
from cs.actions import Action
from cs.documents import Document
from cs.platform.web.uisupport import get_webui_link
from cs.web.components.ui_support.files import _web_ui_edit

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.projects_documents import folders

fTaskDocumentReference = Forward(__name__ + ".TaskDocumentReference")
valid_index = "valid_index"
initial_index = "initial_index"


class AbstractTemplateDocRef(Object):
    @staticmethod
    def get_sorted_rows(rows):
        return sorted(rows, key=lambda row: (len(row.z_index), row.z_index))

    @classmethod
    def get_valid_doc(cls, docs):
        _all_valid_docs = [
            d for d in docs if d.MatchRule("cdbpcs: Documents valid for Instantiation")
        ]
        if _all_valid_docs:
            return cls.get_sorted_rows(_all_valid_docs)[-1]
        return None

    @classmethod
    def get_instantion_state_txt(cls, instantiation_state, objektart):
        if instantiation_state is not None:
            return StatusInfo(objektart, instantiation_state).getLabel()
        return ""

    def _get_document_to_copy(self):
        docs2copy = []
        if self.tmpl_index == valid_index:
            _docs = Document.KeywordQuery(z_nummer=self.z_nummer)
            if len(_docs):
                valid_doc = self.get_valid_doc(_docs)
                docs2copy = [valid_doc] if valid_doc else []
        else:
            doc = Document.ByKeys(z_nummer=self.z_nummer, z_index=self.tmpl_index)
            if doc.MatchRule(
                "cdbpcs: Index-dependent Valid Documents for Instantiation"
            ):
                docs2copy = [doc]
        return docs2copy

    # pylint: disable=protected-access
    DocumentsToCopy = ReferenceMethods_N(
        Document, lambda self: self._get_document_to_copy()
    )

    def _get_referer(self):
        return self.__referer_cls__.ByKeys(**self._get_referer_keys())

    Referer = ReferenceMethods_1(Object, lambda self: self._get_referer())

    def _get_referer_keys(self, with_baseline_id=True):
        result = {}
        for k in self.__referer_cls__.KeyNames():
            if k == "ce_baseline_id":
                if with_baseline_id:
                    result[k] = ""
            else:
                result[k] = self[k]
        return result

    @staticmethod
    def _find_document_templates(obj, template_ref_cls):
        try:
            ref_table = template_ref_cls.GetTableName()
        except TableNotFound as e:
            misc.cdblogv(
                misc.kLogMsg, 1, f"WithDocumentTemplates: Table not found: {e}"
            )
            return []
        template_refs = template_ref_cls.SQL(
            "SELECT %(ref_table)s.* FROM %(ref_table)s, %(target_table)s WHERE %(join)s"
            " AND %(target_table)s.status = %(ref_table)s.instantiation_state"
            " AND %(ref_table)s.created_at is null"
            % (
                {
                    "ref_table": ref_table,
                    "target_table": obj.GetTableName(),
                    "join": obj.JoinCondition(template_ref_cls),
                }
            )
        )
        valid_refs = []
        invalid_refs = []
        for ref in template_refs:
            if ref.DocumentsToCopy:
                valid_refs.append(ref)
            else:
                invalid_refs.append(ref)
        return (valid_refs, invalid_refs)

    @staticmethod
    def get_tmpl_index(doctmpl):
        if doctmpl.tmpl_index == valid_index:
            return util.get_label(valid_index)
        elif doctmpl.tmpl_index == "":
            return util.get_label(initial_index)
        else:
            return doctmpl.tmpl_index

    @staticmethod
    def create_docs_instances(obj, template_ref_cls):
        (valid_refs, invalid_refs) = AbstractTemplateDocRef._find_document_templates(
            obj, template_ref_cls
        )
        for ref in valid_refs:
            ref.create_doc_instances()
        if len(invalid_refs):
            doc_pattern = []
            for i in invalid_refs:
                doc_pattern.append(
                    f"- {i.z_nummer}/{AbstractTemplateDocRef.get_tmpl_index(i)}"
                )
            raise ue.Exception(
                "cdbpcs_no_valid_docs",
                "\n\n{}".format("\n".join(d for d in doc_pattern)),
            )

    def create_doc_instances(self, **kwargs):

        """Creates a new instance of the referenced template document and
        assigns the new document to the refer using the specified assign_cls.
        If assign_cls is None, the document will be assigned directly by setting
        the foreign keys of the referer (e.g. zeichnung.cdb_project_id).
        Keyword arguments are used as initial document attributes.
        """
        new_docs = []
        if "vorlagen_kz" not in kwargs:
            kwargs["vorlagen_kz"] = 0
        for doc in self.DocumentsToCopy:
            new_doc = operation(kOperationCopy, doc, **kwargs)
            self._assign_new_doc(new_doc)
            new_docs.append(new_doc)
        ref_object = self._get_referer()
        templateProject = False
        if ref_object:
            if hasattr(ref_object, "isPartOfTemplateProject"):
                templateProject = ref_object.isPartOfTemplateProject(ref_object)
            if (
                hasattr(ref_object, "Project")
                and ref_object.Project
                and hasattr(ref_object.Project, "isPartOfTemplateProject")
            ):
                templateProject = ref_object.Project.isPartOfTemplateProject(ref_object)
        if not templateProject:
            self.Update(created_at=datetime.datetime.utcnow())
        return new_docs

    def assignBy(self):
        return getattr(self, "__doc_ref_cls__", None)

    def _assign_new_doc(self, doc):

        """Assigns the newly created document to the referer object of the
        template document."""
        assign_cls = self.assignBy()
        if assign_cls:
            values = self.KeyDict()
            values.update(doc.KeyDict())
            assign_cls.Create(**values)
        else:
            doc.Update(**self._get_referer_keys(False))

    def on_CDB_WithDocTemplates_New_now(self, ctx):
        for doc in self.create_doc_instances():
            self.followUpAction(doc, ctx)

    def followUpAction(self, new_doc, ctx):
        """Sets a follow-up action after a new document instance has been created
        explicitly by the user. This method may be overriden to disable the follow-up
        action or to show a message instead of opening the new document.

        Sample code to display a usefull message instead of opening the document:

        raise ue.Exception(-4821, new_doc.GetDescription(), self.Referer.GetDescription())
        """
        if ctx.uses_webui:
            document_url = get_webui_link(None, new_doc)
            ctx.url(document_url)
        ctx.set_followUpOperation(kOperationShowObject, op_object=new_doc)

    def Reset(self):
        self.Update(created_at=None)

    def on_create_dialogitem_change(self, ctx):
        if ctx.changed_item == "z_nummer":
            self.set_index_readonly(ctx)

    def set_index_readonly(self, ctx):
        if self.z_nummer == "":
            ctx.set_fields_readonly(["tmpl_index"])
            ctx.set("tmpl_index", "")
        else:
            ctx.set_fields_writeable(["tmpl_index"])
            ctx.set("tmpl_index", util.get_label(valid_index))

    def set_tmpl_index(self, ctx):
        if self.tmpl_index == util.get_label(valid_index):
            ctx.set("tmpl_index", valid_index)
        elif self.tmpl_index == util.get_label(initial_index):
            ctx.set("tmpl_index", "")

    def set_mask_fields(self, ctx):
        ctx.set(
            "instantiation_state_name",
            self.get_instantion_state_txt(
                self.instantiation_state, self.Referer.cdb_objektart
            ),
        )

        if self.tmpl_index == valid_index:
            ctx.set("tmpl_index", util.get_label(valid_index))
        elif self.tmpl_index == "":
            ctx.set("tmpl_index", util.get_label(initial_index))

    def on_cdbpcs_latest_index_now(self, ctx):
        all_indexes = Document.KeywordQuery(z_nummer=self.z_nummer)
        latest_index = sorted(all_indexes, key=lambda x: (len(x.z_index), x.z_index))[
            -1
        ]
        ctx.url(latest_index.MakeURL("CDB_ShowObject"))

    def on_cdbpcs_index_currently_used_now(self, ctx):
        if self.tmpl_index != "valid_index":
            _used_index = Document.ByKeys(
                z_nummer=self.z_nummer, z_index=self.tmpl_index
            )
            used_index = AbstractTemplateDocRef.get_valid_doc([_used_index])
        else:
            all_indexes = Document.KeywordQuery(z_nummer=self.z_nummer)
            used_index = AbstractTemplateDocRef.get_valid_doc(all_indexes)
        if used_index:
            ctx.url(used_index.MakeURL("CDB_ShowObject"))
        else:
            raise ue.Exception("cdbpcs_no_valid_document", self.z_nummer)

    event_map = {
        (("create"), "pre_mask"): ("set_index_readonly"),
        (("create", "modify"), "pre"): ("set_tmpl_index"),
        (("modify", "info"), "pre_mask"): ("set_mask_fields"),
    }


class ProjectTemplateDocRef(AbstractTemplateDocRef):
    __maps_to__ = "cdbpcs_prj2doctmpl"
    __classname__ = "cdbpcs_prj2doctmpl"
    __referer_cls__ = Project

    def create_doc_instances(self, **kwargs):
        """Obverriden to add cdb_project_id to the document attributes."""
        kwargs["cdb_project_id"] = self.cdb_project_id
        return self.Super(ProjectTemplateDocRef).create_doc_instances(**kwargs)


class DocTemplateColumns(PythonColumnProvider):
    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [
            {
                "column_id": "doc_title",
                "label": util.get_label("pccl_grid_head"),
                "data_type": "text",
            },
            {
                "column_id": "z_index",
                "label": util.get_label("used_index"),
                "data_type": "text",
            },
            {
                "column_id": "used_version",
                "label": util.get_label("used_version"),
                "data_type": "text",
            },
            {
                "column_id": "create_on_status",
                "label": util.get_label("create_on_status"),
                "data_type": "text",
            },
        ]

    @staticmethod
    def get_objektart(classname):
        if classname == "cdbpcs_prj2doctmpl":
            return "cdbpcs_project"
        elif classname == "cdbpcs_task2doctmpl":
            return "cdbpcs_task"
        elif classname == "cdbpcs_cl2doctmpl":
            return "cdbpcs_checklist"
        elif classname == "cdbpcs_cli2doctmpl":
            return "cdbpcs_cl_item"
        else:
            return None

    @staticmethod
    def get_document(data):
        if data["tmpl_index"] != "valid_index":
            document = Document.ByKeys(
                z_nummer=data["z_nummer"], z_index=data["tmpl_index"]
            )
            is_valid = document.MatchRule("cdbpcs: Documents valid for Instantiation")
            return document, is_valid
        else:
            _docs = Document.KeywordQuery(z_nummer=data["z_nummer"])
            if _docs:
                valid_doc = AbstractTemplateDocRef.get_valid_doc(_docs)
                if valid_doc:
                    return valid_doc, True
                else:
                    return AbstractTemplateDocRef.get_sorted_rows(_docs)[0], False
            else:
                return None, None

    @staticmethod
    def getDoc(data, classname):
        result = {}
        objektart = DocTemplateColumns.get_objektart(classname)

        if data["instantiation_state"] != "":
            result["create_on_status"] = StatusInfo(
                objektart, int(data["instantiation_state"])
            ).getLabel()
        else:
            result["create_on_status"] = ""

        document, is_valid = DocTemplateColumns.get_document(data)
        if not document:
            result["title"] = util.get_label("missed_document")
            result["z_index"] = util.get_label("missed_document")
            if data["tmpl_index"] == "":
                result["used_version"] = util.get_label("initial_index")
            elif data["tmpl_index"] == "valid_index":
                result["used_version"] = util.get_label("valid_index")
            else:
                result["used_version"] = data["tmpl_index"]
            return result

        result["title"] = document.titel

        if data["tmpl_index"] == "valid_index":
            result["used_version"] = util.get_label("valid_index")
        elif data["tmpl_index"] == "":
            result["used_version"] = util.get_label("initial_index")
        else:
            result["used_version"] = data["tmpl_index"]

        if not is_valid:
            result["z_index"] = util.get_label("no_valid_index_found")
        elif document.z_index == "":
            result["z_index"] = util.get_label("initial_index")
        else:
            result["z_index"] = document.z_index
        return result

    @staticmethod
    def getColumnData(classname, table_data):
        result = []
        for data in table_data:
            doc_template_data = DocTemplateColumns.getDoc(data, classname)
            result.append(
                {
                    "doc_title": doc_template_data["title"],
                    "z_index": doc_template_data["z_index"],
                    "used_version": doc_template_data["used_version"],
                    "create_on_status": doc_template_data["create_on_status"],
                }
            )
        return result

    @staticmethod
    def getRequiredColumns(classname, available_columns):
        return ["z_nummer", "tmpl_index", "instantiation_state"]


@classbody
class Project:

    Documents = Reference_N(Document, Document.cdb_project_id == Project.cdb_project_id)
    PrimaryMSPDocuments = Reference_N(
        Document,
        Document.z_nummer == Project.msp_z_nummer,
        Document.cdb_obsolete == 0,
        Document.z_status < 100,
    )

    def getLastPrimaryMSPDocument(self):
        """
        :returns: The document containing the current time schedule.
            - The document number is directly referenced in the project's metadata
            - The document index is determined using the platform feature
              "idnex sequence" (default setting `versioning.index_order.doc`),
              e.g. the highest, non-obsolete index.

        :rtype: cs.document.Document
        """
        if not self.msp_z_nummer:
            return None
        index = cad.getMaxIndex(self.msp_z_nummer, Document.__maps_to__)
        result = Document.ByKeys(z_nummer=self.msp_z_nummer, z_index=index)
        while result and result.cdb_obsolete:
            index = kernel.get_prev_index(
                result.z_nummer, result.z_index, result.__maps_to__
            )
            result = Document.ByKeys(z_nummer=self.msp_z_nummer, z_index=index)
        return result

    def on_cdbpcs_msp_schedule_now(self, ctx):
        if ctx.uses_webui:
            msp_doc = self.getLastPrimaryMSPDocument()
            if not msp_doc:
                msp_doc = self.addMSPSchedule(force=True)
                if not msp_doc:
                    raise ue.Exception(
                        "cdbpcs_msp_neither_primary_plan_set_nor_template_defined"
                    )
            # Check if msp doc contain no mpp file
            if len(msp_doc.Files.KeywordQuery(cdbf_type="MS-Project")) == 0:
                raise ue.Exception("cdbpcs_msp_no_mpp_files")
            _web_ui_edit(msp_doc, ctx)
            return

        if not self.msp_active or not self.CheckAccess("save"):
            if "open_in_msp_anyway" not in ctx.dialog.get_attribute_names():
                msgbox = ctx.MessageBox(
                    "cdbpcs_msp_msp_not_set_as_project_editor", [], "open_in_msp_anyway"
                )
                msgbox.addYesButton(is_dflt=1)
                msgbox.addNoButton()
                ctx.show_message(msgbox)
                return
            else:
                if ctx.dialog["open_in_msp_anyway"] != ctx.MessageBox.kMsgBoxResultYes:
                    return
        msp_doc = self.getLastPrimaryMSPDocument()
        if not msp_doc:
            msp_doc = self.addMSPSchedule(force=True)
            if not msp_doc:
                raise ue.Exception(
                    "cdbpcs_msp_neither_primary_plan_set_nor_template_defined"
                )
        # Check if msp doc contain no mpp file
        if len(msp_doc.Files.KeywordQuery(cdbf_type="MS-Project")) == 0:
            if "inform" not in ctx.dialog.get_attribute_names():
                msgbox = ctx.MessageBox(
                    "cdbpcs_msp_no_mpp_files",
                    [],
                    "inform",
                    ctx.MessageBox.kMsgBoxIconAlert,
                )
                msgbox.addButton(ctx.MessageBoxButton("ok", "OK"))
                ctx.show_message(msgbox)
                return
            else:
                if ctx.dialog["inform"] == "OK":
                    return
        ctx.set_followUpOperation(
            "CDB_Edit", keep_rship_context=True, op_object=msp_doc
        )

    @sig.connect(Project, "state_change", "post")
    def create_doc_instances(self, ctx=None):
        """Creates instances of assigned document templates."""
        if (ctx is None or not ctx.error) and not self.template:
            ProjectTemplateDocRef.create_docs_instances(self, ProjectTemplateDocRef)

    @sig.connect(Project, "relship_copy", "post")
    def handle_doc_templates(self, ctx):
        if ctx.error != 0:
            return

        # ggf. Dokumentvorlagen instanziieren
        if ctx.relationship_name == "cdbpcs_prj2doctmpl":
            self.create_doc_instances()
        elif ctx.relationship_name == "cdbpcs_project2task_doctemplates":
            if not self.template:
                self._create_documents_from_templates(Task, TaskTemplateDocRef)

    def _create_documents_from_templates(self, with_templates_cls, template_ref_cls):
        v = {
            "ref_table": template_ref_cls.GetTableName(),
            "target_table": with_templates_cls.GetTableName(),
            "cdb_project_id": self.cdb_project_id,
            # pylint: disable=protected-access
            "join": with_templates_cls._buildKeyJoin(template_ref_cls),
        }

        stmt = (
            "SELECT %(ref_table)s.* FROM %(ref_table)s, %(target_table)s WHERE %(join)s"
        )
        stmt += """ AND %(target_table)s.cdb_project_id = '%(cdb_project_id)s'
                AND %(target_table)s.status = %(ref_table)s.instantiation_state"""
        stmt += " AND %(ref_table)s.created_at is null"
        refs = template_ref_cls.SQL(stmt % v)
        for ref in refs:
            docs = ref.DocumentsToCopy
            if docs:
                for _ in docs:
                    ref.create_doc_instances()

    def copyPrimaryMSPDocument(self, ctx):
        template_project = Project.ByKeys(
            cdb_project_id=ctx.cdbtemplate.cdb_project_id,
            ce_baseline_id=ctx.cdbtemplate.ce_baseline_id,
        )
        msp_doc = template_project.getLastPrimaryMSPDocument()
        if msp_doc:
            kwargs = {
                "cdb_project_id": self.cdb_project_id,
                "autoren": auth.name,
                "vorlagen_kz": self.template,
            }
            new_msp_doc = operation(kOperationCopy, msp_doc, **kwargs)
            if self.msp_active:
                persistent_obj = self.getPersistentObject()
                persistent_obj.msp_z_nummer = new_msp_doc.z_nummer
        return msp_doc

    @sig.connect(Project, "modify", "post")
    def msp_active_doc_modify_post(self, ctx):
        self.addMSPSchedule()

    @sig.connect(Project, "create", "post")
    def msp_active_doc_create_post(self, ctx):
        self.addMSPSchedule()

    @sig.connect(Project, "copy", "post")
    def msp_active_doc_copy_post(self, ctx):
        if ctx.error != 0:
            return
        if ctx.cdbtemplate.ce_baseline_id != "":
            logging.error(
                """"
                project_documents.Project.msp_active_doc_copy_post:
                Cannot call this operation on baseline Project
                %s with baseline id %s""",
                ctx.cdbtemplate.cdb_project_id,
                ctx.cdbtemplate.ce_baseline_id,
            )
            raise ValueError("Cannot call this operation on a project baseline.")

        msp_doc = self.copyPrimaryMSPDocument(ctx)
        if not msp_doc:
            self.addMSPSchedule()

    @sig.connect(Project, "delete", "pre")
    def check_docs_delete_pre(self, ctx):
        if self.Documents:
            raise ue.Exception("pcs_err_del_proj2")

    # -------------- Folders --------------------------------

    def copyFolders(self, ctx):
        tpl_folders = folders.Folder.Query(
            f"cdb_project_id = '{ctx.cdbtemplate.cdb_project_id}' and parent_id = 'root'",
            order_by="folder_id",
        )
        for tf in tpl_folders:
            folders.Folder.CopyFolderStructure(tf, self.cdb_project_id, copy_docs=True)
        if tpl_folders:
            ctx.refresh_tables(["cdb_folder2doc", "cdb_folder"])

    @sig.connect(Project, "copy", "post")
    def _copyFolders(self, ctx):
        if ctx.error != 0:
            return
        self.copyFolders(ctx)

    def deleteFolders(self, ctx):
        tpl_folders = folders.Folder.Query(
            f"cdb_project_id = '{self.cdb_project_id}' and parent_id = 'root'",
            order_by="folder_id",
        )
        for tf in tpl_folders:
            tf.DeleteFolderStructure(ctx)

    @sig.connect(Project, "delete", "post")
    def _deleteFolders(self, ctx):
        if ctx.error != 0:
            return
        self.deleteFolders(ctx)

    @classmethod
    @sig.connect(Project, "cdb_copyfolderstruct_pcs", "pre_mask")
    def PredefineCopyStructLanguage(cls, ctx):
        folders.Folder.PredefineCopyStructLanguage(ctx)

    @sig.connect(Project, "cdb_copyfolderstruct_pcs", "now")
    def CopyFoldStruct(self, ctx):
        folders.Folder.CopyFolderStruct(ctx, self.cdb_project_id)

    def get_doc_template_references(self):
        return self.DocumentTemplates


class TaskDocumentReference(Object):
    __maps_to__ = "cdbpcs_doc2task"

    Document = Reference_1(
        Document, fTaskDocumentReference.z_nummer, fTaskDocumentReference.z_index
    )

    def on_create_pre(self, ctx):
        if not self.rel_type:
            self.rel_type = "doc2task"


class TaskTemplateDocRef(AbstractTemplateDocRef):
    __maps_to__ = "cdbpcs_task2doctmpl"
    __classname__ = "cdbpcs_task2doctmpl"
    __referer_cls__ = Task
    __doc_ref_cls__ = TaskDocumentReference

    def _assign_new_doc(self, doc):
        values = self.KeyDict()
        values.update(doc.KeyDict())
        values["rel_type"] = "doc2task"
        self.assignBy().Create(**values)

    def create_doc_instances(self, **kwargs):
        """Obverriden to add cdb_project_id to the document attributes."""
        kwargs["cdb_project_id"] = self.cdb_project_id
        return self.Super(TaskTemplateDocRef).create_doc_instances(**kwargs)


@classbody
class Task:

    DocumentReferences = Reference_N(
        TaskDocumentReference,
        TaskDocumentReference.cdb_project_id == Task.cdb_project_id,
        TaskDocumentReference.task_id == Task.task_id,
    )

    def _get_Documents(self):
        return self.SimpleJoinQuery(Document, TaskDocumentReference)

    Documents = ReferenceMethods_N(Document, _get_Documents)

    TemplateDocRefs = Reference_N(
        TaskTemplateDocRef,
        TaskTemplateDocRef.cdb_project_id == Task.cdb_project_id,
        TaskTemplateDocRef.task_id == Task.task_id,
    )

    @sig.connect(Task, "state_change", "post")
    def create_doc_instances(self, ctx):
        """Creates instances of assigned document templates."""
        if not ctx.error:
            TaskTemplateDocRef.create_docs_instances(self, TaskTemplateDocRef)

    @classmethod
    @sig.connect(Task, "query_catalog", "pre")
    @sig.connect(Task, "query_catalog", "pre_mask")
    def searchTasksInSameProject(cls, ctx):
        if ctx.action == "requery" or ctx.catalog_requery:
            return
        invoking_dialog = ctx.catalog_invoking_dialog
        if (
            ctx.catalog_name == "cdbpcs_tasks"
            and "z_nummer" in invoking_dialog.get_attribute_names()
        ):  # opened by a document
            doc = Document.ByKeys(invoking_dialog.z_nummer, invoking_dialog.z_index)
            if doc.cdb_project_id and (
                ctx.mode == "pre_mask"
                and ctx.uses_webui
                or ctx.mode == "pre"
                and not ctx.uses_webui
            ):
                ctx.set("cdb_project_id", doc.cdb_project_id)

    def get_doc_template_references(self):
        return self.TemplateDocRefs


@sig.connect(Document, "state_change", "post")
def delete_invalid_doc_templates(cls, ctx):
    document = ctx.object
    from cs.pcs.checklists_documents import CLTemplateDocRef

    template_refs = CLTemplateDocRef.KeywordQuery(z_nummer=document.z_nummer)
    for template_ref in template_refs:
        # If related document state is invalid
        if len([doc for doc in template_ref.DocumentsToCopy if doc.status != 180]) == 0:
            template_ref.Delete()


@sig.connect(Document, "delete", "pre")
def delete_msp_time_schedule(cls, ctx):
    """Prevents deleting a document when it's set as a project's time schedule"""
    prj = Project.KeywordQuery(msp_z_nummer=ctx.object.z_nummer)
    if prj:
        raise ue.Exception(
            "cdbpcs_msp_time_schedule_must_not_be_deleted", prj[0].GetDescription()
        )


@classbody
class Document:
    Project = Reference_1(Project, Document.cdb_project_id)

    FolderAssignments = Reference_N(
        folders.Folder2doc,
        folders.Folder2doc.z_nummer == Document.z_nummer,
        folders.Folder2doc.z_index == Document.z_index,
    )

    def PresetFolderAttributes(self, ctx):
        if ctx.relationship_name in ["cdb_folder2doc", "cdb_folder2valid_docs"]:
            folder_id = ctx.parent["folder_id"]
            if folder_id:
                f = folders.Folder.ByKeys(folder_id=folder_id)
                f.ApplyDefaults(self, overwrite=False)

    @sig.connect(Document, "copy", "pre_mask")
    @sig.connect(Document, "create", "pre_mask")
    def _PresetFolderAttributes(self, ctx):
        self.PresetFolderAttributes(ctx)

    @sig.connect(Document, "create", "pre_mask")
    @sig.connect(Document, "cdb_create_doc_from_template", "pre_mask")
    def _preset_project_id(self, ctx):
        """
        When a document is created in the context of a project-specific action,
        the system proposes the project number of the action as the project number of
        the document. If a document is copied in the context of a project-specific action,
        the document's existing project number will not be changed.
        """
        if ctx.relationship_name == "cdb_action2docs" and hasattr(
            ctx.parent, "cdb_object_id"
        ):
            parent_object = ByID(ctx.parent.cdb_object_id)
            if isinstance(parent_object, Action) and parent_object.cdb_project_id:
                ctx.set("cdb_project_id", parent_object.cdb_project_id)
        elif ctx.relationship_name == "cdbpcs_project2all_docs" and hasattr(
            ctx.parent, "cdb_project_id"
        ):
            ctx.set("cdb_project_id", ctx.parent.cdb_project_id)

    @sig.connect(Document, "create", "post")
    def CopyFilesAtDragAndDrop(self, ctx):
        """
        Drag&Drop of a document into a relationship tab triggers the creation of a new document,
        where the properties of the source document are preset.
        This method copies the files of the source document
        """
        if not ctx.dragdrop_action_id:
            # No drag&drop action
            return
        z_nummer = getattr(ctx.dragged_obj, "z_nummer", None)
        z_index = getattr(ctx.dragged_obj, "z_index", None)
        if z_nummer is None or z_index is None:
            # Source does not seem to be a document
            return

        src_doc = Document.ByKeys(ctx.dragged_obj.z_nummer, ctx.dragged_obj.z_index)
        if not src_doc:
            # Source is not a document
            return

        # Finally, all non-derived files are copied, just like copying a document
        kwargs = {"cdbf_object_id": self.cdb_object_id}
        for f in src_doc.Files:
            if not f.cdbf_derived_from:
                operation(kOperationCopy, f, **kwargs)

    def CheckFolderAssignment(self, ctx):
        # Unterbindet ggf. die Zuordnung eines neuen Indexstandes oder
        # einer Kopie zur Verknuepfungsrelation
        if ctx.relationship_name == "cdb_folder2valid_docs":
            # Wenn im Kontext dieser Beziehung eine Versionierung vorgenommen wurde
            # ist schon der alte Index drin, sonst haette man es ja nicht aufrufen koennen
            if ctx.action == "index":
                ctx.skip_relationship_assignment()

    @sig.connect(Document, "index", "pre")
    def _CheckFolderAssignment(self, ctx):
        self.CheckFolderAssignment(ctx)

    def RemoveFolderAssignments(self, ctx):
        # Loescht das Dokument aus der Ordnerzuordnung
        if not ctx or not ctx.error:
            assignments = self.FolderAssignments
            for a in assignments:
                a.DocDeleted(self, ctx)

    @sig.connect(Document, "delete", "post")
    def _RemoveFolderAssignments(self, ctx):
        self.RemoveFolderAssignments(ctx)
