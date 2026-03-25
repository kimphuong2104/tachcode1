#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# pylint: disable-msg=R0901,R0902,R0201,R0904,E0203,W0212,W0201,W0232
# pylint: disable=bad-continuation

import logging
import os
from datetime import datetime

from cdb import auth, kernel, ue
from cdb.classbody import classbody
from cdb.objects import LocalizedField, N, Reference
from cdb.objects.common import WithStateChangeNotification
from cdb.objects.org import CommonRole
from cdb.rte import require_config
from cs.documents import CADDocumentType_FType, Document, DocumentCategory

_Logger = logging.getLogger(__name__)

# Sentinel: raise when "std-solution" is not set
require_config("std-solution")


@classbody
class Document(WithStateChangeNotification):
    def IsValidInteractiveTargetStatus(self, target_status):
        """
        Overwritten to exclude some status that can only be done
        by the system itself but not interactive by the user
        """
        # For legacy reasons call stateChangeAllowed
        # IsValidInteractiveTargetStatus is only called interactive
        return self.stateChangeAllowed(target_status, False)

    def stateChangeAllowed(self, target_state, batch):
        """
        Legacy function of the standard solution.
        """
        if batch:
            return True
        allowed = True
        if target_state in [180, 190]:
            allowed = False
        elif target_state == 200:
            # 0->200 nur fuer Dokumente ohne Pruefung
            if self.status == 0 and self.GetObjectKind() != "doc_standard":
                allowed = False
            if self.status == 190:
                allowed = False
        elif target_state == 300:
            allowed = False
        return allowed

    def on_state_change_post(self, ctx):
        self.Super(Document).on_state_change_post(ctx)

        if ctx.error:
            return

        if ctx.old.z_status in ["0", "100"] and ctx.new.z_status == "200":
            # Pruefer und Pruefdatum setzen
            self.Update(pruefer=auth.get_name(), pruef_datum=datetime.utcnow().date())
            # Vorgaengerindex von 'in �nderung' (190) nach 'ungueltig' (180) setzen
            old_state = 190
            new_state = 180
            docs = Document.KeywordQuery(z_nummer=self.z_nummer, z_status=old_state)
            for doc in docs:
                # In der Regel sollte es hier nur ein Dokument geben
                try:
                    doc.ChangeState(new_state)
                except RuntimeError as e:
                    raise ue.Exception(
                        "cdb_konfstd_008", "%s" % old_state, "%s" % new_state, e
                    )

    def on_modify_pre_mask(self, ctx):
        if self.isModel():
            ctx.set_fields_readonly(["teilenummer", "t_index"])

    @classmethod
    def GetInitialCreateValues(cls):
        """
        The function is called for `CDB_Create`
        to retrieve initial values as ``dict``.
        For interactive operations these attributes
        are set during the ``pre_mask`` call. For batch operations the
        attributes are set in ``pre`` if no value is supplied before.
        """
        return {
            "cdb_obsolete": 0,
            "z_bereich": auth.get_department(),
            "anlegetag": datetime.utcnow(),
            "zeichner": auth.get_name(),
            "vorlagen_kz": 0,
            "autoren": auth.get_name(),
        }

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
        return {"cdb_obsolete": 0, "pruefer": "", "pruef_datum": ""}

    def GetOLCRelevantAttributes(self):
        return self.CategoryAttributeNames()

    def CalculateOLC(self, ctx):
        """
        The function is called to calculate the object life cycle using the
        categories provided by ctx.dialog or self.
        """
        result = None
        categ_attrs = self.CategoryAttributeNames()
        erzeug_system = getattr(ctx.dialog, "erzeug_system", self.erzeug_system)
        for attr in reversed(categ_attrs):
            categ_id = getattr(ctx.dialog, attr, self[attr])
            if categ_id:
                result = DocumentCategory.getOLC(categ_id, erzeug_system)
                break

        return result

    def setWorkflow(self, ctx):
        if ctx.mode == "post_mask" or not ctx.interactive or ctx.uses_webui:
            wf = self.CalculateOLC(ctx)
            if not wf:
                raise ue.Exception("cdb_konfstd_011", self.getCategoryString())
            self.z_art = wf

    def _getCategoryPath(self):
        """Liefert die Werte der Kategorienattribute als Liste."""
        result = []
        attrs = self.CategoryAttributeNames()
        for attr in attrs:
            result.append(self[attr])
        return result

    def getCategoryPath(self):
        """Liefert Liste mit DocumentCategory Objekten gemaess der Werte der
        Kategorienattribute"""
        return DocumentCategory.ResolveByKeys(self._getCategoryPath())

    def getCategoryString(self):
        """Liefert internationalisierte Klartextbezeichnung des Kategorienpfades zur
        Verwendung in Fehlermeldungen. Beispiel: CAD Dokumente/Fertigungszeichnung"""
        return "/".join([c.Name[""] for c in self.getCategoryPath()])

    def getLeafCategory(self):
        result = None
        categories = self.getCategoryPath()
        if categories:
            result = categories[-1]
        return result

    def get_template_preset_attributes(self):
        """Return a list of attribute names that are to be copied from the
        template document, when the operation "New from template" is called.
        Overwrite this method in a project, to customize the list of
        attributes.
        """
        result = self.CategoryAttributeNames()
        result.append("titel")
        return result

    def presetProjectID(self, ctx):
        # ggf. die Projektnummer aus Beziehungskontext vorbelegen
        if ctx.relationship_name in [
            "cdbpcs_task2docs",
            "cdbpcs_checklist2docs",
            "cdbpcs_cl_item2docs",
            "cdbpcs_issue2docs",
        ]:
            self.cdb_project_id = ctx.parent.cdb_project_id

    def on_delete_post(self, ctx):
        if ctx.error:
            return
        # Statuswechsel des Vorgaengerindex von 190 (in �nderung) zurueck nach 200 (Konst. Freigabe)
        old_state = 190
        new_state = 200
        docs = Document.KeywordQuery(z_nummer=self.z_nummer, z_status=old_state)
        for doc in docs:
            # In der Regel sollte es hier nur ein Dokument geben
            try:
                doc.ChangeState(new_state)
            except RuntimeError as e:
                raise ue.Exception(
                    "cdb_konfstd_008", "%s" % old_state, "%s" % new_state, e
                )

    def clearAttributes(self):
        # Felder leeren
        attrs = ["ersatz_fuer", "ersatz_durch", "pruefer", "pruef_datum"]
        for attr in attrs:
            self[attr] = ""

    def on_index_pre(self, ctx):
        self.clearAttributes()

    def on_index_post(self, ctx):
        if ctx.error:
            return
        # autom. Statuswechsel des Vorgaengerindex von 200 (freigeben)
        # bzw. 300 (ERP freigeben) nach 190 (in �nderung)
        doc = Document.ByKeys(self.z_nummer, ctx.cdbtemplate.z_index)
        if doc and doc.z_status in [200, 300]:
            new_state = 190
            try:
                doc.ChangeState(new_state)
            except RuntimeError as e:
                raise ue.Exception(
                    "cdb_konfstd_008", "%s" % doc.z_status, "%s" % new_state, e
                )

    def setFilename(self, ctx):
        # Fuer Catia V4 muss der Dateiname gesetzt werden
        if self.erzeug_system == "Catia":
            self.dateiname = "%s-%s" % (self.z_nummer, self.z_index)

    def checkItemReference(self, ctx):
        if ctx.mode == "post_mask" or not ctx.interactive or ctx.uses_webui:
            # Pruefung, ob Artikelzuordnung fuer die Kategorie pflicht ist.
            # Fuer Modelle ist die Artikelzuordnung immer Pflicht, daher nur fuer Dokumente pruefen.
            if not self.isModel():
                c = self.getLeafCategory()
                if c and c.ItemReferenceMandatory() and not self.teilenummer:
                    # Fuer Dokumente der Kategorie %s ist die Zuordnung eines Artikels obligatorisch.
                    raise ue.Exception("cdb_konfstd_021", self.getCategoryString())

    def checkReferencesState(self, ctx, validStateList, msgNumber):
        if "question_wf_step_refs" in ctx.dialog.get_attribute_names():
            return

        # For legacy reasons we have to convert the list of validStates if
        # it is a string (in-condition) instead of a list
        if isinstance(validStateList, str):
            valid_states = [int(state) for state in validStateList.split(",")]
        else:
            valid_states = validStateList
        invalid_docs = self.GetReferencedDocsWithInvalidState(valid_states)
        if invalid_docs:
            docRefMsg = "\\n".join(doc.GetDescription() for doc in invalid_docs)

            # Warnmeldung ueber falschen Status der Referenzen
            msgbox = ctx.MessageBox(msgNumber, [docRefMsg], "question_wf_step_refs")
            msgbox.addYesButton(1)
            msgbox.addCancelButton()
            ctx.show_message(msgbox)

    def on_wf_step_post_mask(self, ctx):
        self.Super(Document).on_wf_step_post_mask(ctx)
        # Zur Freigabe sollten alle Komponenten den passenden Status
        # Pruefung oder freigegeben haben, sonst Frage
        if self.status == 100:
            self.checkReferencesState(ctx, [100, 200], "cdb_konfstd_024")
        elif self.status == 200:
            self.checkReferencesState(ctx, [200], "cdb_konfstd_025")

    def on_modify_post_mask(self, ctx):
        # Pruefung, ob Artikelzuordnung fuer die Kategorie pflicht ist, sofern diese geaendert wurde
        # oder der Artikelbezug entfernt wurde.
        # Fuer Modelle ist die Artikelzuordnung immer Pflicht, daher nur fuer Dokumente pruefen.
        if not self.isModel():
            attrs = self.CategoryAttributeNames()
            categ_changed = False
            for attr in attrs:
                if ctx.object[attr] != ctx.dialog[attr]:
                    categ_changed = True
                    break
            if categ_changed or (ctx.object.teilenummer and not ctx.dialog.teilenummer):
                self.checkItemReference(ctx)

    # == preview issues ==
    @classmethod
    def on_preview_available_now(cls, ctx):
        ctx.enablePreview()

    def on_preview_now(self, ctx):
        preview_file = self.GetPreviewFile()
        if preview_file:
            preview_file.handlePreviewCtx(ctx)
        else:
            self.Super(Document).on_preview_now(ctx)

    # == Email notification ==
    def getNotificationReceiver(self, ctx=None):
        rcvr = {}
        if self.status == 100:
            releaseRole = CommonRole.ByKeys("Design Release")
            for pers in releaseRole.getPersons():
                if pers.e_mail:
                    tolist = rcvr.setdefault("to", [])
                    tolist.append((pers.e_mail, pers.name))
        return [rcvr]

    # == End email notification ==

    def set_application_from_file(self, ctx):
        """Called from the doc create dialog to set the application according
        to the file to be imported.
        """
        if (
            ctx.changed_item == "localfilename"
            and "localfilename" in ctx.dialog.get_attribute_names()
        ):
            filename = ctx.dialog["localfilename"]
            if filename:
                ftypes = kernel.getFileTypesByFilename(filename)
                if ftypes:
                    ctx.set("erzeug_system", ftypes[0].getName())

    def set_categ_by_filetype(self, ctx):
        """Called on create pre/pre_mask to set the doc category for
        models, if called in an embedded context.
        """
        if not ctx.embedded or (
            ctx.mode == "pre" and (ctx.interactive or ctx.uses_webui)
        ):
            # not in an embedded context or
            # already called in pre_mask, so don't overwrite possible changes
            # done by the user
            return

        categs = []
        cur_categ = DocumentCategory.ByFiletype(ctx.cad_system)
        while cur_categ:
            categs.insert(0, cur_categ)
            cur_categ = cur_categ.ParentCategory
        _Logger.debug(
            "set_categ_by_filetype: got categories [%s] for file type '%s'",
            ", ".join([categ.name_uk for categ in categs]),
            ctx.cad_system,
        )

        if len(categs) == 1:
            # a root category is configured, set z_categ1 only
            if not self.z_categ1 and not self.z_categ2:
                self.z_categ1 = categs[0].categ_id
        elif len(categs) == 2:
            # a level-2 category is configured, set both category fields if
            # root either matches or is not yet set in self
            if (
                not self.z_categ1 or self.z_categ1 == categs[0].categ_id
            ) and not self.z_categ2:
                self.z_categ1 = categs[0].categ_id
                self.z_categ2 = categs[1].categ_id

    def check_file_edit(self, ctx):
        """Check whether there is a modified file in the doc edit window and
        ask the user if he really want's to change the state in this case.
        """
        arg_name = "cdb_doc_wf_editing_reallychange"

        def ask_user(ctx):
            msgbox = ctx.MessageBox(
                "cdb_question_doc_wf_editing",
                [],
                arg_name,
                ctx.MessageBox.kMsgBoxIconQuestion,
            )
            msgbox.addYesButton(1)
            msgbox.addCancelButton()
            ctx.show_message(msgbox)

        if (
            "doceditinprogress" in ctx.sys_args.get_attribute_names()
            and int(ctx.sys_args["doceditinprogress"]) > 1
            and (ctx.interactive or ctx.uses_webui)
            and not (arg_name in ctx.dialog.get_attribute_names())
        ):
            # Arg is missing, so ask the question
            ask_user(ctx)

    # file events, overwritten here from empty default implementations
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

        If the file is a primary file, will set the file modified date and
            possibly the application for this document.
        """
        updates = {}
        if the_file.isPrimary():
            # No need to update erzeug_system if it is already CONTAINER
            # or the System of the file
            # _determine_erz_sys() is quiet expensive
            erzeug_system = self.erzeug_system
            if (
                erzeug_system == self.GetDefaultErzSystem()
                and not kernel.CDBFileType(erzeug_system).isValid()
            ):
                # We are the first file
                erzeug_system = the_file.cdbf_type
            elif erzeug_system not in ("CONTAINER", the_file.cdbf_type):
                erzeug_system = self._determine_erz_sys()
            # If a CAD is active don't change the system to CONTAINER,
            # because this causes problems when integrations use
            # changeGenSystem.
            if (
                not ctx
                or not ctx.get_active_integration()
                or ctx.get_active_integration() == "wspmanager"
                or erzeug_system != "CONTAINER"
            ):
                if erzeug_system != self.erzeug_system:
                    updates["erzeug_system"] = erzeug_system
        if Document.IsRelevantForLastFileModification(the_file):
            # If we create a lot of files within a second it might be
            # unneccessary to update the info
            if self.cdb_m2date != the_file.cdb_mdate:
                updates["cdb_m2date"] = the_file.cdb_mdate
            if self.cdb_m2persno != the_file.cdb_mpersno:
                updates["cdb_m2persno"] = the_file.cdb_mpersno
        if updates:
            self.getPersistentObject().Update(**updates)

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

        Works like fileCreated(), but must take into account that the
        modification was to reset the 'primary' flag on the file; this
        means the call to _determine_erz_sys() has to be done in almost any case.
        """
        updates = {}

        def _need_to_call_determine_erz_sys():
            if the_file.isPrimary() and the_file.cdbf_type == self.erzeug_system:
                # Already the same
                return False

            if not ctx:
                return True

            ftype_old = getattr(ctx.previous_values, "cdbf_type", "")
            primary_old = getattr(ctx.previous_values, "cdbf_primary", "")
            if the_file.cdbf_primary == primary_old:
                if not the_file.isPrimary() or ftype_old == the_file.cdbf_type:
                    # No effect for calculation or no relevant changes
                    return False
            else:
                # Primary Flag has changed
                if the_file.isPrimary():
                    if self.erzeug_system in ("CONTAINER", the_file.cdbf_type):
                        return False
                elif self.erzeug_system != "CONTAINER":
                    return False
            return True

        if _need_to_call_determine_erz_sys():
            erz_sys = self._determine_erz_sys()
            if erz_sys and erz_sys != self.erzeug_system:
                updates["erzeug_system"] = erz_sys

        if Document.IsRelevantForLastFileModification(the_file):
            if self.cdb_m2date != the_file.cdb_mdate:
                updates["cdb_m2date"] = the_file.cdb_mdate
            if self.cdb_m2persno != the_file.cdb_mpersno:
                updates["cdb_m2persno"] = the_file.cdb_mpersno
        if updates:
            self.getPersistentObject().Update(**updates)

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

        If the file was a primary file, will possibly set the application
        for this document based on the remaining primary files.
        """
        if the_file.isPrimary():
            # If the file has been responsible for locking
            # the document we have to calculate the locking state
            # again
            if self.cdb_lock and the_file.cdb_lock == self.cdb_lock:
                self.fileUnlocked(the_file, ctx)

            erz_sys = self._determine_erz_sys()
            if erz_sys and erz_sys != self.erzeug_system:
                self.getPersistentObject().erzeug_system = erz_sys

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

        If the file is a primary file, will set the lock for this document
        too.
        """
        if the_file.isPrimary():
            if self.cdb_lock != the_file.cdb_lock:
                # We do not know if self is constructed using
                # _FromObjectHandle so we call getPersistentObject
                self.getPersistentObject().cdb_lock = the_file.cdb_lock

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

        If it was a primary file, checks to see whether there is another
        primary file that is still locked. If so, set this documents lock
        accordingly, else reset it.
        """
        # No need to do anything if we are not locked
        if not self.cdb_lock or not the_file.isPrimary():
            return
        locks = set(
            [
                f.cdb_lock
                for f in self.PrimaryFiles
                if f.cdb_object_id != the_file.cdb_object_id and f.cdb_lock
            ]
        )
        if locks and self.cdb_lock not in locks:
            self.getPersistentObject().cdb_lock = locks.pop()
        elif not locks and self.cdb_lock:
            self.getPersistentObject().cdb_lock = ""

    def _determine_erz_sys(self):
        """Determine what value to use for erzeug_system of this document. If
        all primary files have the same file type use that. If there are
        primary files with different types, use 'CONTAINER'.
        Returns None if no primary files are found.
        """
        ftypes = set([f.cdbf_type for f in self.PrimaryFiles])
        if not ftypes:
            new_erz_sys = None
        elif len(ftypes) > 1:
            new_erz_sys = "CONTAINER"
        else:
            new_erz_sys = ftypes.pop()
        return new_erz_sys

    event_map = {
        (("copy", "create"), "post_mask"): ("setWorkflow", "checkItemReference"),
        # Redefine setDocumentNumber from cs.document.Document event map
        # because it has to be called before setFilename
        (("copy", "create"), "pre"): (
            "setWorkflow",
            "setDocumentNumber",
            "setFilename",
            "checkItemReference",
        ),
        (("copy", "create"), "pre_mask"): ("presetProjectID"),
        ("create", "dialogitem_change"): ("set_application_from_file"),
        ("create", ("pre_mask", "pre")): "set_categ_by_filetype",
        ("modify", "pre"): ("_check_partno"),
        ("wf_step", "pre_mask"): ("check_file_edit"),
    }


# Email notification attributes
Document.__notification_template__ = "document_approval.html"
Document.__notification_title__ = (
    "CIM DATABASE - Dokument zur Pr�fung / Document for approval"
)
# Force looking for the template file in defined folder
_thisdir = os.path.dirname(__file__)
Document.__notification_template_folder__ = os.path.join(_thisdir, "chrome")


@classbody
class DocumentCategory(object):

    SubCategories = Reference(
        N, DocumentCategory, DocumentCategory.parent_id == DocumentCategory.categ_id
    )
    SubCategoriesByName = Reference(
        1,
        DocumentCategory,
        DocumentCategory.parent_id == DocumentCategory.categ_id,
        indexed_by=DocumentCategory.name_d,
    )
    ParentCategory = Reference(1, DocumentCategory, DocumentCategory.parent_id)

    Name = LocalizedField("name")

    @classmethod
    def ResolveByName(cls, name, parent_id=""):
        result = None
        categories = DocumentCategory.KeywordQuery(name_d=name, parent_id=parent_id)
        if len(categories) == 1:
            result = categories[0]
        elif len(categories) > 1:
            _Logger.error(
                "Document category name '%s' is not unique for parent category '%s'.",
                name,
                parent_id,
            )
        return result

    @classmethod
    def ResolveByNames(cls, names):
        result = []
        if not names:
            return result
        c = DocumentCategory.ResolveByName(names[0])
        if not c:
            return result
        result.append(c)
        del names[0]
        while names:
            c = c.SubCategoriesByName[names[0]]
            if not c:
                break
            result.append(c)
            del names[0]
        return result

    @classmethod
    def ResolveByKeys(cls, keys):
        result = []
        for key in keys:
            c = DocumentCategory.ByKeys(key)
            if not c:
                break
            result.append(c)
        return result

    @classmethod
    def ByFiletype(cls, ftype):
        cdoc_ftype = CADDocumentType_FType.ByKeys(ft_name=ftype)
        if not cdoc_ftype:
            return None
        else:
            return cls.ByKeys(categ_id=cdoc_ftype.cdb_cad_categ_id)

    def UpdateSubCategories(self, ctx):
        if self.HasField("item_ref_mandatory"):
            new_val = ctx.object.item_ref_mandatory
            if new_val == "":
                new_val = 0
            self._SubsSetItemRefMandatoryFlag(int(new_val))

    def _SubsSetItemRefMandatoryFlag(self, value):
        for sc in self.SubCategories:
            sc.item_ref_mandatory = value
            sc._SubsSetItemRefMandatoryFlag(value)

    event_map = {
        (("modify"), "post"): "UpdateSubCategories",
    }
