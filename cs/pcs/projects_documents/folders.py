#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module folders.py
This is the documentation for the folders.py module.
"""

import logging

from cdb import i18n, misc, transaction, ue, util
from cdb.objects import Forward, Object, Reference_1, Reference_N
from cs.documents import Document

__all__ = ["Folder", "Folder2doc"]


fFolder = Forward(__name__ + ".Folder")
fFolder2doc = Forward(__name__ + ".Folder2doc")


class Folder(Object):
    __maps_to__ = "cdb_folder"
    __classname__ = "cdb_folder"

    fProject = Forward("cs.pcs.projects.Project")
    ParentFolder = Reference_1(fFolder, fFolder.parent_id)
    MainProject = Reference_1(fProject, fFolder.cdb_project_id)
    SubFolders = Reference_N(
        fFolder, fFolder.parent_id == fFolder.folder_id, addtl="ORDER BY folder_id"
    )
    DocAssignments = Reference_N(
        fFolder2doc, fFolder.folder_id == fFolder2doc.folder_id
    )

    @classmethod
    def CopyFolderStructure(
        cls,
        template_folder,
        dest_project_id,
        copy_docs,
        iso_lang=None,
        parent_folder=None,
    ):
        """
        Copy the complete structure of a template project to another project.
        @type template_folder: Folder instance - folder in the template project
        @type dest_project   : Project instance - active project
        @copy_doc            : Copy corresponding documents
        @iso_lang            : Standard-project-language - None copies original
        @type parent_folder  : Folder instance - parent folder in avtive project
        """
        with transaction.Transaction():
            if parent_folder:
                parent_id = parent_folder.folder_id
            else:
                parent_id = "root"

            # Perform the copy (memorize the template folder in each copy. Might become
            # important if template is modified and the modification should be
            # inherited to all projects within the template has been used).
            std_label = template_folder.name
            if iso_lang and template_folder["name_" + iso_lang]:
                std_label = template_folder["name_" + iso_lang]

            new_folder = template_folder.Copy(
                folder_id=cls.GenerateFolderID(),
                cdb_project_id=dest_project_id,
                name=std_label,
                parent_id=parent_id,
                **cls.MakeChangeControlAttributes(),
            )

            # Determine all subfolders.
            for subfolder in template_folder.SubFolders:
                Folder.CopyFolderStructure(
                    subfolder, dest_project_id, copy_docs, iso_lang, new_folder
                )

            # Determine all documents.
            if copy_docs:
                for doc in template_folder.DocAssignments:
                    doc.Copy(folder_id=new_folder.folder_id)

    # Deletes the folder with subfolders and document assignments
    def DeleteFolderStructure(self, ctx=None):
        with transaction.Transaction():
            for subfolder in self.SubFolders:
                subfolder.DeleteFolderStructure()
            for doc in self.DocAssignments:
                doc.Delete()
            if ctx:
                ctx.refresh_tables(["cdb_folder", "cdb_folder2doc"])
            else:
                self.Delete()

    # Called by standard solution - placed here to have a chance to call
    # it from pcs.Project
    @classmethod
    def CopyFolderStruct(cls, ctx, dest_prj_id, parent_folder=None):
        tpl_folders = []

        if ctx.dialog["templ_folder_id"]:
            template_folder = Folder.ByKeys(folder_id=ctx.dialog["templ_folder_id"])
            if template_folder:
                tpl_folders.append(template_folder)

        else:
            # Determine all root folders of the template project
            template_project_id = ctx.dialog["templ_project_id"]
            if template_project_id:
                tpl_folders = Folder.Query(
                    f"cdb_project_id = '{template_project_id}' and parent_id = 'root'",
                    order_by="folder_id",
                )

        iso_lang = None
        if "iso_lang" in ctx.dialog.get_attribute_names():
            iso_lang = ctx.dialog["iso_lang"]

        copy_docs = 1
        if ctx and "copy_docs" in ctx.dialog.get_attribute_names():
            copy_docs = int(ctx.dialog["copy_docs"])

        for tf in tpl_folders:
            cls.CopyFolderStructure(tf, dest_prj_id, copy_docs, iso_lang, parent_folder)

        if tpl_folders:
            ctx.refresh_tables(["cdb_folder2doc", "cdb_folder"])

    @classmethod
    def PredefineCopyStructLanguage(cls, ctx):
        # choose the user's language
        ctx.set("iso_lang", i18n.default())

    @classmethod
    def GenerateFolderID(cls):
        return f'F{util.nextval("CDB_FOLDER_ID"):09d}'

    def SetFolderID(self, ctx):
        if self.folder_id in ["#", "", "root"]:
            self.folder_id = self.GenerateFolderID()

    def HandleParentFolderCreate(self, ctx):
        """
        Handles issues dealing with the creation of a folder
        in the context of the parent-folder relationship.
        The parent folder is now created with the same
        project id. The new folder is set as the
        child's parent folder in mode ``post``.
        """
        if ctx.relationship_name == "cdb_subfolder2folder":
            if ctx.mode == "pre_mask":
                # If the creation of a folder is possible in this context
                # the folder_id is predefined with 'root' by the relationship
                # This is not a suitable folder_id so set the value to
                # # (numgen)
                ctx.set("folder_id", "#")
                if ctx.parent:
                    fld = Folder.ByKeys(folder_id=ctx.parent.folder_id)
                    if fld:
                        ctx.set("cdb_project_id", getattr(fld, "cdb_project_id", ""))
            elif ctx.mode == "post":
                # Set the parent_id
                if ctx.error == 0:
                    if ctx.parent:
                        fld = Folder.ByKeys(folder_id=ctx.parent.folder_id)
                        if fld:
                            fld.parent_id = self.folder_id

    # Applies Defaults - at this time the doc categories defined in the
    # folder object. If overwrite is false only empty attributes will
    # be set
    def ApplyDefaults(self, obj, overwrite):
        misc.cdblogv(
            misc.kLogMsg,
            7,
            f"Entering Folder.ApplyDefaults with object of type {type(obj)}",
        )
        if isinstance(obj, Document):
            misc.cdblogv(misc.kLogMsg, 7, "Entering Folder.ApplyDefaults for documents")
            predefine = ["cdb_project_id"]

            predefine.extend(["z_categ1", "z_categ2"])

            for attr in predefine:
                try:
                    if (
                        obj.HasField(attr)
                        and self[attr]
                        and (overwrite or not obj[attr])
                    ):
                        obj[attr] = self[attr]
                except Exception:
                    logging.exception(
                        "ApplyDefaults failed for folder '%s', attr '%s'",
                        self.folder_id,
                        attr,
                    )

    def SetDefaultValues(self, ctx):
        if ctx.relationship_name == "cdb_folder2folder":
            # Set some values identical to that of the parent folder.
            # E.g. each folder must have a project id to
            # implement project specific security.
            if self.ParentFolder:
                self.cdb_project_id = self.ParentFolder.cdb_project_id

                # Set the default document categories identical to that of the parent folder.
                for attr in ["z_categ1", "z_categ2"]:
                    setattr(self, attr, getattr(self.ParentFolder, attr))

        # Its not a subfolder:
        else:
            # Set the root_folder attribute.
            self.parent_id = "root"
            if "cdb_project_id" in ctx.parent.get_attribute_names():
                self.cdb_project_id = ctx.parent.cdb_project_id

        # Set the immutable flag
        # In an template project a folder should be immutable unless
        # the user says it is not.
        is_immutable = 0
        if self.cdb_project_id:
            if self.MainProject and self.MainProject.template:
                is_immutable = 1

        self.immutable = is_immutable

        # if no project-origin is set, it is not a copy
        if not self.project_origin:
            self.project_origin = self.cdb_project_id

    def CopyFoldStructFld(self, ctx):
        self.CopyFolderStruct(ctx, self.cdb_project_id, self)

    event_map = {
        (("create", "copy"), "pre"): ("SetFolderID"),
        (("create", "copy"), "pre_mask"): (
            "HandleParentFolderCreate",
            "SetDefaultValues",
        ),
        (("create"), "post"): ("HandleParentFolderCreate"),
        (("cdb_copyfolderstruct_fld"), "pre_mask"): ("PredefineCopyStructLanguage"),
        (("cdb_copyfolderstruct_fld"), "now"): ("CopyFoldStructFld"),
        (("delete"), "pre"): ("DeleteFolderStructure"),
    }


class Docfolder_dynamic(Folder):
    __classname__ = "cdb_docfolder_dynamic"
    __match__ = Folder.cdb_classname >= __classname__

    @classmethod
    def assign_dynamic(cls):
        return True


class Docfolder_exact(Folder):
    __classname__ = "cdb_docfolder_exact"
    __match__ = Folder.cdb_classname >= __classname__

    @classmethod
    def assign_dynamic(cls):
        return False


class Folder2doc(Object):
    __maps_to__ = "cdb_folder2doc"
    __classname__ = "cdb_folder2doc"

    Folder = Reference_1(fFolder, fFolder2doc.folder_id)

    def _check_duplicates(self, ctx):
        # Baseline or Label folder may not contain same document with different indexes
        if self.Folder.assign_dynamic():
            if Folder2doc.Query(
                f"folder_id = '{self.folder_id}' and z_nummer = '{self.z_nummer}'"
            ):
                raise ue.Exception("err_folder_dups")

    def on_create_pre_mask(self, ctx):
        # Baseline or Label folder may not contain same document with different indexes
        if self.Folder.assign_dynamic():
            self._check_duplicates(ctx)
            # if a document has been created we predefine the index to avoid
            # the mask
            if ctx and ctx.relationship_name == "cdb_folder2valid_docs":
                # z_index vorgeben, damit die Maske nicht kommt
                if "z_index" in ctx.dragged_obj.get_attribute_names():
                    ctx.set("z_index", ctx.dragged_obj["z_index"])
                else:
                    # we can not have z_index none
                    ctx.set("z_index", getattr(ctx.dialog, "z_index", ""))

    def on_create_pre(self, ctx):
        self._check_duplicates(ctx)

    def DocDeleted(self, doc, ctx):
        # if the folder works exact, we can remove ourself
        remove = False
        if self.Folder.assign_dynamic():
            # if doc is the only valid doc, we removal is ok
            docs = Document.KeywordQuery(z_nummer=self.z_nummer, cdb_obsolete=0)
            # doc itself has already been removed,
            if not docs:
                remove = True
        else:
            remove = True
        if remove:
            self.Delete()
            if ctx:
                ctx.refresh_tables(["cdb_folder2doc"])
