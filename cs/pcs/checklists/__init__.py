#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines

from cdb import ElementsError, auth, ddl, misc, sig, sqlapi, transactions, ue, util
from cdb.classbody import classbody
from cdb.constants import kOperationDelete
from cdb.fls import allocate_license
from cdb.objects import Forward, LocalizedField, Object, Reference_1, Reference_N
from cdb.objects.common import WithObjectCollection, WithStateChangeNotification
from cdb.objects.operations import operation
from cdb.objects.org import WithSubject
from cdb.platform import gui, olc
from cdb.platform.mom.entities import Entity

from cs.pcs.checklists.tasks_plugin import (
    ChecklistItemWithCsTasks,
    ChecklistWithCsTasks,
)
from cs.pcs.issues import WithFrozen
from cs.pcs.projects.common import assert_valid_project_resp
from cs.pcs.projects.common.sharing import WithSharingAndProjectRoles
from cs.pcs.projects.tasks import Task

__all__ = [
    "Checklist",
    "ChecklistItem",
    "RatingValue",
    "RatingSchema",
    "RedGreenYellowRating",
    "GradesRating",
    "ChecklistType",
    "RuleReference",
]

# Forward declarations
Project = Forward("cs.pcs.projects.Project")
fChecklist = Forward("cs.pcs.checklists.Checklist")
ChecklistItem = Forward("cs.pcs.checklists.ChecklistItem")
ChecklistType = Forward("cs.pcs.checklists.ChecklistType")
fRatingSchema = Forward("cs.pcs.checklists.RatingSchema")
fRatingValue = Forward("cs.pcs.checklists.RatingValue")
fDocumentTemplate = Forward("cs.pcs.checklists_documents.CLTemplateDocRef")
fItemDocumentTemplate = Forward("cs.pcs.checklists_documents.CLItemTemplateDocRef")

fRuleReference = Forward(__name__ + ".RuleReference")
fRule = Forward("cdb.objects.Rule")

CL_ITEM_EVALUATE_REMARK = "cdbpcs_clir_txt"


class Checklist(
    WithSubject,
    WithObjectCollection,
    WithSharingAndProjectRoles,
    WithFrozen,
    ChecklistWithCsTasks,
):
    __maps_to__ = "cdbpcs_checklst"
    __classname__ = "cdbpcs_checklist"

    Project = Reference_1(Project, fChecklist.cdb_project_id)
    ChecklistItems = Reference_N(
        ChecklistItem,
        ChecklistItem.cdb_project_id == fChecklist.cdb_project_id,
        ChecklistItem.checklist_id == fChecklist.checklist_id,
        order_by="position",
    )
    ParentChecklistItem = Reference_1(
        ChecklistItem,
        fChecklist.parent_cl_item_id,
        fChecklist.parent_checkl_id,
        fChecklist.cdb_project_id,
    )
    RatingSchema = Reference_1(fRatingSchema, fChecklist.rating_scheme)
    TypeDefinition = Reference_1(ChecklistType, fChecklist.type)

    Task = Reference_1(Task, fChecklist.cdb_project_id, fChecklist.task_id)

    RuleReferences = Reference_N(
        fRuleReference,
        fRuleReference.cdb_project_id == fChecklist.cdb_project_id,
        fRuleReference.checklist_id == fChecklist.checklist_id,
    )

    Rating = Reference_1(fRatingValue, fChecklist.rating_scheme, fChecklist.rating_id)

    DocumentTemplates = Reference_N(
        fDocumentTemplate,
        fDocumentTemplate.cdb_project_id == fChecklist.cdb_project_id,
        fDocumentTemplate.checklist_id == fChecklist.checklist_id,
    )

    # Methods to attach/detach the Checklist to a Checkpoint as Subchecklist
    def detachFromCheckpoint(self):
        self.parent_checkl_id = 0
        self.parent_cl_item_id = 0

    def attachToCheckpoint(self, cl_item):
        self.parent_checkl_id = cl_item.checklist_id
        self.parent_cl_item_id = cl_item.cl_item_id

    def updateParentCheckpoint(self, ctx=None):
        if ctx and ctx.error:
            return
        # Flag has_sub_cl des übergeordneten Checkpunkts aktualisieren.
        if self.ParentChecklistItem:
            self.ParentChecklistItem.updateSubChecklistsFlag()

    # Methods to handle checklist rating
    def calcRating(self, cdb_project_id, checklist_id, cl_item_id=None):
        for cl_item in self.ChecklistItems:
            if (
                self.RatingSchema.calcRating(
                    cl_item.rating_id,
                    cl_item.weight,
                    cl_item.ko_criterion,
                    cl_item.cdb_project_id,
                    cl_item.checklist_id,
                    cl_item.cl_item_id,
                )
                == -1
            ):
                break
        result = self.RatingSchema.getResult()
        if not result:
            return "clear"
        return result

    def setRating(self, force=False):
        if not force and self.status == Checklist.COMPLETED.status:
            return
        rating_id = self.calcRating(self.cdb_project_id, self.checklist_id, None)
        self.Update(rating_id=rating_id)

        # ggf. Bewertung für übergeordneten Prüfpunkt setzen
        if self.status == Checklist.COMPLETED.status and self.ParentChecklistItem:
            rating_result = self.ParentChecklistItem.calcRating(
                self.ParentChecklistItem.cdb_project_id,
                self.ParentChecklistItem.checklist_id,
                self.ParentChecklistItem.cl_item_id,
            )
            if rating_result:
                self.ParentChecklistItem.rating_id = rating_result

    # Checkpoint related methods
    def allItemsChecked(self):
        """Returns True, if all checkpoints have been rated"""
        return (
            len(
                self.ChecklistItems.Query(
                    ChecklistItem.status != self.TypeDefinition.rating_state
                )
            )
            == 0
        )

    def noItemChecked(self):
        """Returns True, if no checkpoint is rated"""
        return (
            len(
                self.ChecklistItems.Query(
                    ChecklistItem.status == self.TypeDefinition.rating_state
                )
            )
            == 0
        )

    def hasSubChecklists(self):
        """Returns True, if at least one checkpoint has a subchecklist"""
        return len(self.ChecklistItems.Query(ChecklistItem.has_sub_cl == 1)) > 0

    # Utils for copying and resetting checklists
    def Reset(self):
        self.Update(
            rating_id="clear",
            evaluator="",
            status=Checklist.NEW.status,
            cdb_status_txt=olc.StateDefinition.ByKeys(
                statusnummer=Checklist.NEW.status, objektart=self.cdb_objektart
            ).StateText[""],
        )
        self.resetItems()

    def adjustTemplateValue(self, template=False):
        self.template = bool(template)
        self.ChecklistItems.Update(template=template)

    def resetItems(self):
        for cl_item in self.ChecklistItems:
            cl_item.Reset()
            # reset subchecklists
            for sub_cl in cl_item.SubChecklists:
                sub_cl.Reset()

    def setItemsWaiting(self):
        for ci in self.ChecklistItems:
            ci.ChangeState(ChecklistItem.READY.status)
        self.ChecklistItems.Update(checklist_state=self.status)

    def cancelItems(self):
        items = self.ChecklistItems.Query(
            ChecklistItem.status != ChecklistItem.COMPLETED.status
        )
        items.Update(
            status=ChecklistItem.DISCARDED.status,
            cdb_status_txt=olc.StateDefinition.ByKeys(
                statusnummer=ChecklistItem.DISCARDED.status,
                objektart=self.TypeDefinition.cli_objektart,
            ).StateText[""],
            checklist_state=self.status,
        )

    def MakeCopy(self, project, assign_to=None, templates_only=False):
        self.checkLicense()
        if templates_only and not self.template:
            return None

        args = {
            "cdb_project_id": project.cdb_project_id,
            "checklist_id": util.nextval("cdbpcs_checklist"),
        }
        args.update(Checklist.MakeChangeControlAttributes())

        item_args = args
        if assign_to:
            args.update(assign_to.KeyDict())

        new_cl = self.Copy(**args)
        # Langtext mit Beschreibung kopieren
        new_cl.SetText("cdbpcs_cl_txt", self.GetText("cdbpcs_cl_txt"))
        new_cl.SetText("cdbpcs_clr_txt", self.GetText("cdbpcs_clr_txt"))
        # Checkpunkte kopieren
        curr_cl_item_id = 0
        for cl_item in self.ChecklistItems:
            curr_cl_item_id += 1
            item_args["cl_item_id"] = curr_cl_item_id
            item_args["template"] = self.template
            new_cl_item = cl_item.Copy(**item_args)
            # Langtext mit Beschreibung kopieren
            new_cl_item.SetText("cdbpcs_cli_txt", cl_item.GetText("cdbpcs_cli_txt"))
            new_cl_item.SetText("cdbpcs_clir_txt", cl_item.GetText("cdbpcs_clir_txt"))
            # Wenn dem Prüfpunkt weitere Checklisten zugeordnet sind, diese auch kopieren
            for sub_cl in cl_item.SubChecklists:
                new_sub_cl = sub_cl.MakeCopy(
                    project=project, templates_only=templates_only
                )
                if new_sub_cl:
                    new_sub_cl.attachToCheckpoint(new_cl_item)
            cli_docref = ddl.Table("cdbpcs_cli2doctmpl")
            if cli_docref.exists():
                for r in cl_item.TemplateDocRefs:
                    values = new_cl_item.KeyDict()
                    values["created_at"] = None
                    r.Copy(**values)

        # Referenzen auf Dokumentenvorlagen kopieren
        t = ddl.Table("cdbpcs_cl2doctmpl")
        if t.exists():
            for r in self.TemplateDocRefs:
                values = new_cl.KeyDict()
                values["created_at"] = None
                r.Copy(**values)
        # Bei Deliverables Regeln für zu erstellende Arbeitsgegenstände kopieren
        if self.type == "Deliverable":
            for rule in self.RuleReferences:
                rule.Copy(**new_cl.KeyDict())
        return new_cl

    def ForceDelete(self):
        self.Reset()
        for clit in self.ChecklistItems:
            if clit.SubChecklists:
                for cl in clit.SubChecklists:
                    cl.ForceDelete()
            operation(kOperationDelete, clit)
        operation(kOperationDelete, self)

    # Workflow Implementation
    def _mirrorState(self):
        # Den Status der Checkliste in die Stammdaten der Prüfpunkte
        # übernehmen  (cdbpcs_cl_item.checklist_state).
        # Auf dem gespiegelten Status stützt sich das Rechtesystem ab.
        self.ChecklistItems.Update(checklist_state=self.status)

    # Event Map Implementations
    def setChecklistID(self, ctx):
        self.checklist_id = util.nextval("cdbpcs_checklist")
        if not self.checklist_id:
            self.checklist_id = util.nextval("cdbpcs_checklist")

    def checkState(self, ctx):
        if (
            self.task_id != getattr(ctx.object, "task_id", self.task_id)
            and self.status != self.NEW.status
        ):
            # task reference may only be changed while checklist status is NEW
            raise ue.Exception("pcs_err_cl_move")
        if self.Task and self.Task.status in self.Task.endStatus(False):
            raise ue.Exception("cdbpcs_err_task_checklist", self.Task.task_name)
        if self.Project and self.Project.status in self.Project.endStatus(False):
            raise ue.Exception(
                "cdbpcs_err_project_checklist", self.Project.project_name
            )

    # Event Handler Implementations
    def on_create_pre_mask(self, ctx):
        if not self.division:
            self.division = auth.get_department()
        if self.Project:
            ctx.set("project_name", self.Project.project_name)
            # Bei Neuanlage im Kontext eines Checkpunktes weitere Attribute
            # der übergeordneten Checkliste übernehmen
            if ctx.relationship_name == "cdbpcs_cl_item2checklist":
                parent_cl = Checklist.ByKeys(
                    cdb_project_id=ctx.parent.cdb_project_id,
                    checklist_id=ctx.parent.checklist_id,
                )
                self.template = parent_cl.template
                self.rating_scheme = parent_cl.rating_scheme
                self.type = parent_cl.type
                ctx.set_readonly("template")
        else:
            # ggf. Übernahme Projektbezug vom Parent Objekt
            if ctx.relationship_name in [
                "cdbpcs_doc2topchecklists",
                "cdbpcs_model2topchecklists",
            ]:
                self._preset_project_from_doc(ctx)
            elif ctx.relationship_name == "cdbpcs_part2topchecklists":
                self._preset_project_from_item(ctx)
            if self.cdb_project_id:
                ctx.set(
                    "project_name",
                    Project.ByKeys(cdb_project_id=self.cdb_project_id).project_name,
                )
        if not self.Project:
            self.subject_id = auth.persno
            self.subject_type = "Person"
        if ctx.dragged_obj:
            self.type = ctx.dragged_obj.type
            self.rating_scheme = ctx.dragged_obj.rating_scheme
            self.subject_id = ctx.dragged_obj.subject_id
            self.subject_type = ctx.dragged_obj.subject_type
            self.auto = ctx.dragged_obj.auto
        self.rating_id = "clear"

    def on_copy_pre_mask(self, ctx):
        self.checklist_id = ""
        self.rating_id = "clear"
        self.type = ctx.object.type
        self.subject_id = ctx.object.subject_id
        self.subject_type = ctx.object.subject_type
        self.detachFromCheckpoint()

    def on_relship_copy_post(self, ctx):
        # Prüfpunkte zurücksetzen
        if ctx.relationship_name == "cdbpcs_checklist2cl_items":
            for cl_item in self.ChecklistItems:
                cl_item.Update(template=self.template, has_sub_cl=0)
                cl_item.Reset()

        if ctx.relationship_name == "cdbpcs_cl2doctmpl":
            for doctmpl in self.DocumentTemplates:
                doctmpl.Reset()

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    def on_delete_pre(self, ctx):
        # Checklisten dürfen nur gelöscht werden, wenn die zugehörigen
        # Prüfpunkte keine Unterchecklisten haben
        if self.hasSubChecklists():
            raise ue.Exception("pcs_err_del_cl1")

    def on_delete_post(self, ctx):
        if ctx.error != 0:
            return
        # Dokumentzuordnungen und Statusprotokoll der mitgelöschten Prüfpunkte löschen
        rels = ["cdbpcs_cli_prot", "cdbpcs_doc2cli"]
        for rel in rels:
            sqlapi.SQLdelete(
                f"FROM {rel} WHERE cdb_project_id = '{self.cdb_project_id}' "
                f" AND checklist_id = '{self.checklist_id}'"
            )

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = self.Super(Checklist).GetDisplayAttributes()
        results["attrs"].update({"heading": self["category"]})
        return results

    def copyDraggedChecklists(self, ctx):
        if ctx.dragged_obj:
            dragObj = Checklist.ByKeys(
                cdb_project_id=ctx.dragged_obj.cdb_project_id,
                checklist_id=ctx.dragged_obj.checklist_id,
            )
            change_control = self.MakeChangeControlAttributes()
            for checklistItem in dragObj.ChecklistItems:
                new_cli = checklistItem.Copy(
                    cdb_project_id=self.cdb_project_id,
                    checklist_id=self.checklist_id,
                    template=self.template,
                    has_sub_cl=0,
                    **change_control,
                )
                new_cli.Reset()
                # Langtext mit Beschreibung kopieren
                new_cli.SetText(
                    "cdbpcs_cli_txt", checklistItem.GetText("cdbpcs_cli_txt")
                )
                new_cli.SetText(
                    "cdbpcs_clir_txt", checklistItem.GetText("cdbpcs_clir_txt")
                )

                t = ddl.Table("cdbpcs_cli2doctmpl")
                if t.exists():
                    for r in checklistItem.TemplateDocRefs:
                        r.Copy(**self.KeyDict())

            t = ddl.Table("cdbpcs_cl2doctmpl")
            if t.exists():
                for r in dragObj.TemplateDocRefs:
                    r.Copy(**self.KeyDict())

    @classmethod
    def cdbpcs_checklist_assign(cls, obj, ctx):
        template_cl = cls.ByKeys(
            cdb_project_id=ctx.dialog.t_cdb_project_id,
            checklist_id=ctx.dialog.checklist_id,
        )
        template_cl.checkLicense()
        if "cdb_t_project_id" in ctx.dialog.get_attribute_names():
            project = Project.ByKeys(cdb_project_id=ctx.dialog.cdb_t_project_id)
        else:
            project = Project.ByKeys(cdb_project_id=ctx.dialog.cdb_project_id)
        new_checklist = template_cl.MakeCopy(project, obj, False)
        new_checklist.adjustTemplateValue(template=0)
        new_checklist.Reset()
        new_checklist.detachFromCheckpoint()
        ctx.url(new_checklist.MakeURL("cdbpcs_checklist"))
        return (project.cdb_project_id, new_checklist.checklist_id)

    def checkLicense(self, ctx=None):
        if self.type == "QualityGate":
            allocate_license("CHECKLISTS_006")
        elif self.type == "Deliverable":
            allocate_license("CHECKLISTS_007")

    def setEvaluator(self, ctx):
        persno = ""
        if self.status in (180, 200):
            persno = self.cdb_mpersno
        self.Update(evaluator=persno)

    def check_project_role_needed(self, ctx):
        self.Project.check_project_role_needed(ctx)

    def copy_rating_scheme_relship(self, ctx):
        if ctx.relationship_name == "cdbpcs_checklist2cl_items":
            self.ChecklistItems.Update(rating_scheme=self.rating_scheme)

    def deactivate_fields(self, ctx):
        ctx.set_fields_readonly(["project_name", "template", "type", "rating_scheme"])

    def validate_responsibility(self, ctx):
        assert_valid_project_resp(ctx)

    def setRelshipFieldsReadOnly(self, ctx):
        if ctx.relationship_name == "cdbpcs_project2cdbpcs_checklist":
            ctx.set_fields_readonly(["project_name"])

    event_map = {
        (("create", "modify", "copy", "delete", "wf_step"), "pre"): ("checkLicense"),
        (("create"), "pre_mask"): ("checkState", "setRelshipFieldsReadOnly"),
        (("create", "copy"), "pre"): (
            "checkState",
            "setChecklistID",
            "validate_responsibility",
        ),
        (("modify"), "pre_mask"): ("checkState", "deactivate_fields"),
        (("create"), "post"): (
            "updateParentCheckpoint",
            "copyDraggedChecklists",
            "check_project_role_needed",
        ),
        (("copy", "delete"), "post"): (
            "updateParentCheckpoint",
            "check_project_role_needed",
        ),
        (("modify", "state_change"), "post"): (
            "setEvaluator",
            "check_project_role_needed",
        ),
        ("relship_copy", "post"): "copy_rating_scheme_relship",
        (("cs_tasks_delegate"), "post"): ("check_project_role_needed"),
    }


class ChecklistItem(
    WithSubject,
    WithStateChangeNotification,
    WithSharingAndProjectRoles,
    WithFrozen,
    ChecklistItemWithCsTasks,
):
    __maps_to__ = "cdbpcs_cl_item"
    __classname__ = "cdbpcs_cl_item"

    Project = Reference_1(Project, ChecklistItem.cdb_project_id)
    RatingSchema = Reference_1(fRatingSchema, ChecklistItem.rating_scheme)
    Rating = Reference_1(
        fRatingValue, ChecklistItem.rating_scheme, ChecklistItem.rating_id
    )
    SubChecklists = Reference_N(
        fChecklist,
        fChecklist.cdb_project_id == ChecklistItem.cdb_project_id,
        fChecklist.parent_checkl_id == ChecklistItem.checklist_id,
        fChecklist.parent_cl_item_id == ChecklistItem.cl_item_id,
    )
    Checklist = Reference_1(
        fChecklist, ChecklistItem.cdb_project_id, ChecklistItem.checklist_id
    )
    DocumentTemplates = Reference_N(
        fItemDocumentTemplate,
        fItemDocumentTemplate.cdb_project_id == ChecklistItem.cdb_project_id,
        fItemDocumentTemplate.checklist_id == ChecklistItem.checklist_id,
        fItemDocumentTemplate.cl_item_id == ChecklistItem.cl_item_id,
    )

    def calcRating(self, cdb_project_id, checklist_id, cl_item_id=None):
        weight = 1  # Unterchecklisten haben immer die Gewichtung 1
        ko_criterion = 0  # Unterchecklisten können kein k.o. Kriterium sein
        for cl in self.SubChecklists:
            if (
                cl.RatingSchema.name != self.RatingSchema.name
                or cl.status == Checklist.COMPLETED.status
            ):
                # Checkpunkt ist nicht automatisch bewertbar, weil
                # die Unterchecklisten ein anderes Bewertungsschema haben
                # oder noch nicht alle Unterchecklisten bewertet sind.
                return None
            if (
                self.RatingSchema.calcRating(
                    cl["rating_id"],
                    weight,
                    ko_criterion,
                    self.cdb_project_id,
                    self.checklist_id,
                    self.cl_item_id,
                )
                == -1
            ):
                break
        return self.RatingSchema.getResult()

    def clearRating(self):
        if self.status == ChecklistItem.COMPLETED.status:
            self.ChangeState(ChecklistItem.READY.status)
            if self.Checklist.status in [
                Checklist.COMPLETED.status,
                Checklist.DISCARDED.status,
            ]:
                self.Checklist.ChangeState(Checklist.EVALUATION.status)

    def tryRating(self, rating_id, update_cl_rating=True, rating_remark=""):
        if not self.setRating(rating_id, update_cl_rating, rating_remark):
            return self.criterion + " (" + f"{self.cl_item_id}" + ")\n"
        return ""

    def setRating(self, rating_id, update_cl_rating=True, rating_remark=""):
        if self.subChecklistsRated():
            self.Update(rating_id=rating_id)
            if rating_id == "clear":
                self.clearRating()
                # checklist rating can change when a checklist item's rating becomes 'clear'
                if update_cl_rating:
                    self.Checklist.setRating(force=True)
                return True
            if rating_remark is not None:
                self.SetText("cdbpcs_clir_txt", rating_remark)
            # Statuswechsel in den Bewertungsstatus
            rating_state = self.Checklist.TypeDefinition.rating_state
            if self.status != rating_state:
                try:
                    self.ChangeState(rating_state)
                except ElementsError as error:
                    misc.cdblogv(
                        misc.kLogErr,
                        0,
                        f"Checklist Item {self.GetDescription()}: {error} "
                        f"(from {self.status} to {rating_state})",
                    )
                    raise ue.Exception("pcscl_wf_rej_5", self.GetDescription(), error)
            if update_cl_rating:
                self.Checklist.setRating()
            return True
        return False

    def Reset(self):
        self.Update(
            status=ChecklistItem.NEW.status,
            cdb_status_txt=olc.StateDefinition.ByKeys(
                statusnummer=ChecklistItem.NEW.status, objektart=self.cdb_objektart
            ).StateText[""],
            checklist_state=self.Checklist.status,
            rating_id="clear",
            evaluator="",
        )

    def subChecklistsRated(self):
        for cl in self.SubChecklists:
            if cl.status not in (
                Checklist.COMPLETED.status,
                Checklist.DISCARDED.status,
            ):
                return False
        return True

    def updateSubChecklistsFlag(self):
        if self.SubChecklists:
            self.has_sub_cl = 1
        else:
            self.has_sub_cl = 0

    def setID(self, ctx):
        self.cl_item_id = util.nextval("cdbpcs_cl_item")

    def setPosition(self, ctx):
        cl_list = self.Checklist.ChecklistItems
        max_pos = 0
        for cl_item in cl_list:
            pos = cl_item.position
            if pos and pos > max_pos:
                max_pos = pos
        self.position = max_pos + 10

    def on_create_pre_mask(self, ctx):
        # Attribute der Checkliste übernehmen
        attrs = [
            "subject_id",
            "subject_type",
            "division",
            "target_date",
            "rating_scheme",
            "type",
            "category",
        ]
        for attr in attrs:
            if self.Checklist[attr]:
                self[attr] = self.Checklist[attr]
        ctx.set("template", self.Checklist["template"])
        self.rating_id = "clear"
        self.checklist_state = self.Checklist.status
        # Workflow für den Checkpunkt laut Konfiguration in Relation cdbpcs_cl_types setzen.
        self.cdb_objektart = self.Checklist.TypeDefinition.cli_objektart

    def on_copy_pre_mask(self, ctx):
        self.cl_item_id = None
        self.Reset()

    def on_delete_pre(self, ctx):
        # Prüfpunkte dürfen nur gelöscht werden, wenn es keine Unterchecklisten gibt
        if len(self.SubChecklists) > 0:
            raise ue.Exception("pcs_err_del_cli1")

    def on_modify_pre(self, ctx):
        # Bewertung nur erlauben, wenn alle Unterchecklisten bewertet oder verworfen sind (sofern vorhanden)
        if self.rating_id != ctx.object.rating_id and not self.subChecklistsRated():
            raise ue.Exception(
                "pcs_err_cp_rating2",
                ctx.object["criterion"] + " (" + str(self.checklist_id) + ")",
            )

        # Bewertungsrelevante attribute geändert
        attrs = ["rating_id", "weight", "ko_criterion"]
        for attr in attrs:
            if f"{self[attr]}" != f"{ctx.object[attr]}":
                ctx.keep(attr + "_changed", "1")
                if attr == "rating_id":
                    if self.rating_id in ["", "clear"]:
                        # reset
                        ctx.set("rating_id", "clear")
                    else:
                        self.Checklist.change_status_of_checklist(
                            self.Checklist.NEW,
                            self.Checklist.EVALUATION,
                        )
                        ctx.refresh_tables(["cdbpcs_checklst"])

    def on_modify_post(self, ctx):
        self.checkLicense()
        ue_args = ctx.ue_args.get_attribute_names()
        if "rating_id_changed" in ue_args:
            if self.rating_id in ["", "clear"]:
                self.clearRating()
                ctx.refresh_tables(["cdbpcs_checklst"])
            else:
                # Be aware:
                # - operation does not call pre_mask
                # - use persistent object here to avoid NotImplementedError
                persistent_object = self.getPersistentObject()
                operation(
                    "cdbpcs_clitem_rating", persistent_object, rating_id=self.rating_id
                )
        if "weight_changed" in ue_args or "ko_criterion_changed" in ue_args:
            self.Checklist.setRating()
            ctx.refresh_tables(["cdbpcs_checklst"])

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    @classmethod
    def get_mandatory_remark_from_ctx(cls, ctx):
        try:
            return bool(int(getattr(ctx.dialog, "mandatory_remark")))
        except ValueError:
            return False

    @classmethod
    def set_evaluate_remark_mandatory(cls, ctx, pre_mask=False):
        def get_mandatory_remark():
            if pre_mask:
                # pre-set the remark field in case of pre_mask ue
                if hasattr(ctx.dialog, "quickEvaluation"):
                    # `mandatory_remark` field is set along with `quickEvaluation`
                    # this code block will be called in case the operation is called
                    # from webui
                    return cls.get_mandatory_remark_from_ctx(ctx)
                else:
                    rating_id = getattr(ctx.dialog, "rating_id")
                    name = getattr(ctx.dialog, "rating_scheme")
                    rv = RatingValue.KeywordQuery(name=name, rating_id=rating_id)
                    if rv:
                        return rv[0]["mandatory_remark"]
                    else:
                        return False
            else:
                # this code branch is run in case of dialogitem change
                return cls.get_mandatory_remark_from_ctx(ctx)

        if get_mandatory_remark():
            ctx.set_mandatory(CL_ITEM_EVALUATE_REMARK)
        else:
            ctx.set_optional(CL_ITEM_EVALUATE_REMARK)

    @classmethod
    def evaluate_skip_dialog_if_necessary(cls, ctx):
        # only do it incase of web quick evaluation and no manadatory remarks
        if (
            ctx.uses_webui
            and hasattr(ctx.dialog, "quickEvaluation")
            and not cls.get_mandatory_remark_from_ctx(ctx)
        ):
            ctx.skip_dialog()

    @classmethod
    def check_cdbpcs_clitem_rating(cls, ctx):
        """
        Check preconditions for rating one or more checklist items:

        - all items belong to the same (exactly one) checklist
        - checklist license is available (depending on checklist type)
        - checklist status is `NEW` or `EVALUATION`
            (if `NEW`, it will be changed to `EVALUATION`)

        :returns: the shared checklist of items to be rated
        :raises cdb.ue.Exception: if any condition is violated
        """
        if hasattr(ctx, "objects"):
            cl_items = ChecklistItem.PersistentObjectsFromContext(ctx)
            # we need a single checklist or fail
            cl_keys = {(item.cdb_project_id, item.checklist_id) for item in cl_items}
            cl = cl_items[0].Checklist if len(cl_keys) == 1 else None
        else:
            kwargs = {
                key: ctx.object[key]
                for key in [
                    "cdb_project_id",
                    "checklist_id",
                    "cl_item_id",
                ]
            }
            cl = Checklist.ByKeys(**kwargs)

        if not cl:
            raise ue.Exception("pcs_items_of_multiple_cls")

        cl.checkLicense()

        if cl.status not in [cl.NEW.status, cl.EVALUATION.status]:
            raise ue.Exception("cdbpcs_err_checklist")

        return cl

    @classmethod
    def on_cdbpcs_clitem_rating_pre_mask(cls, ctx):
        cl = cls.check_cdbpcs_clitem_rating(ctx)

        ctx.set("rating_scheme", cl.rating_scheme)
        ctx.set("cdb_project_id", cl.cdb_project_id)
        ctx.set("checklist_id", cl.checklist_id)
        ctx.set("evaluator", auth.persno)

        cls.set_evaluate_remark_mandatory(ctx, True)
        cls.evaluate_skip_dialog_if_necessary(ctx)

    def rating_dialogitem_change(self, ctx):
        self.set_evaluate_remark_mandatory(ctx)

    @classmethod
    def on_cdbpcs_clitem_rating_now(cls, ctx):
        """
        If the assigned checklist is not in the required status, the status will be changed
        The rating is applied to all selected checklist items
        """
        with transactions.Transaction():
            cl = cls.check_cdbpcs_clitem_rating(ctx)
            cl.prepare_for_rating()

            cl_items = ChecklistItem.PersistentObjectsFromContext(ctx)
            if not cl_items:
                return

            err_string = ""
            rating_id = ctx.dialog["rating_id"]
            rating_remark = (
                ctx.dialog["cdbpcs_clir_txt"]
                if "cdbpcs_clir_txt" in ctx.dialog.get_attribute_names()
                else None
            )

            for cp in cl_items:
                cp.evaluator = auth.persno
                err_string += cp.tryRating(
                    rating_id,
                    True,
                    rating_remark=rating_remark,
                )

            cl.setRating(force=True)
            ctx.refresh_tables(["cdbpcs_checklst", "cdbpcs_cl_item"])
            if err_string:
                raise ue.Exception("pcs_err_cp_rating", err_string)

    def checkState(self, ctx):
        if self.Checklist.status not in [
            Checklist.NEW.status,
            Checklist.EVALUATION.status,
        ]:
            raise ue.Exception("cdbpcs_err_checklist")
        self.Checklist.checkState(ctx)

    # == Email notification ==

    def getNotificationTitle(self, ctx=None):
        """
        :param ctx:
        :return: title of the notification mail
        :rtype: basestring
        """
        return (
            f'{gui.Message.GetMessage("branding_product_name")} - '
            "Prüfpunkt bereit / Checklist item ready"
        )

    def getNotificationTemplateName(self, ctx=None):
        """
        :param ctx:
        :return: template name of the notification mail body
        :rtype: basestring
        """
        return "cdbpcs_clitem_ready.html"

    def getNotificationReceiver(self, ctx=None):
        rcvr = {}
        if self.Subject:
            for pers in self.Subject.getPersons():
                if pers.email_notification_task():
                    tolist = rcvr.setdefault("to", [])
                    tolist.append((pers.e_mail, pers.name))
        return [rcvr]

    # == End email notification ==

    def checkLicense(self, ctx=None):
        self.Checklist.checkLicense()

    def setEvaluator(self, ctx):
        persno = ""
        if self.status in (180, 200):
            persno = self.cdb_mpersno
        self.Update(evaluator=persno)

    def check_project_role_needed(self, ctx):
        self.Project.check_project_role_needed(ctx)

    def update_evaluator_checklist_item(self, ctx):
        if ctx and ctx.error:
            return
        if ctx.dialog["rating_id"] not in ["", "clear"]:
            self.getPersistentObject().Update(evaluator=auth.persno)
            ctx.refresh_tables(["cdbpcs_checklst", "cdbpcs_cl_item"])

    def deactivate_evaluation(self, ctx):
        ctx.set_fields_readonly(["rating_value", "cdbpcs_clir_txt"])

    def validate_responsibility(self, ctx):
        assert_valid_project_resp(ctx)

    def on_relship_copy_post(self, ctx):
        if ctx.relationship_name == "cdbpcs_cli2doctmpl":
            for doctmpl in self.DocumentTemplates:
                doctmpl.Reset()

    event_map = {
        (("modify", "delete", "wf_step"), "pre"): ("checkLicense"),
        (("create", "copy"), "pre"): (
            "checkState",
            "checkLicense",
            "setID",
            "setPosition",
            "validate_responsibility",
        ),
        (("create", "copy", "modify"), "pre_mask"): (
            "checkState",
            "deactivate_evaluation",
        ),
        (("modify", "delete", "state_change"), "post"): (
            "setEvaluator",
            "check_project_role_needed",
        ),
        (("create", "copy"), "post"): (
            "check_project_role_needed",
            "update_evaluator_checklist_item",
        ),
        (("cs_tasks_delegate"), "post"): ("check_project_role_needed"),
        (("cdbpcs_clitem_rating"), "dialogitem_change"): ("rating_dialogitem_change"),
    }


class RatingValue(Object):
    __maps_to__ = "cdbpcs_rat_val"

    Value = LocalizedField("rating_value")


class RatingSchema(Object):
    """
    Base class of evaluation schemes used by Checklist and Checklist Items

    Derived classes need to be specialized using the __match__
    property and the getResult method similar to this:

        class OkOrNotOk(RatingSchema):

            __match__ = RatingSchema.name == 'OkOrNotOk'

            def getResult(self):
                '''
                :return: type: unicode, valid evaluation scheme value
                  (cdbpcs_rat_val.rating_id) or empty string
                '''
                # Place your specialized code here...
                return <my_rating_id>

    The prerequisite is that the evaluation scheme has been configured and
    assigned to a checklist type in the database.
    To visualize the evaluation values, you must define your own
    icons and integrate them into the existing icon definitions.
    """

    __maps_to__ = "cdbpcs_rat_def"
    __classname__ = "cdbpcs_rat_def"

    RatingValues = Reference_N(fRatingValue, fRatingValue.name == fRatingSchema.name)

    def calcRating(
        self,
        rating_id,
        weight,
        ko_criterion,
        cdb_project_id,
        checklist_id,
        cl_item_id=None,
    ):
        """
        A method of this name is currently used by default schemes.
        In derived classes, this method must exist but does not have to be used.
        :param: All parameters match the names of the class's Checklist Item
            (cdbpcs_cl_item) attributes.
        :return: No value is expected
        """
        pass

    def getResult(self):
        """
        This method must be customized in derived classes. This method is the
        only method that must exist in derived classes. The method provides the
        evaluation value of the checklist. Each evaluation scheme requires its own
        calculation algorithm to determine the evaluation value of the checklist.
        :return: type: unicode, valid evaluation scheme value
        (cdbpcs_rat_val.rating_id) or empty string
        """
        return ""


class RedGreenYellowRating(RatingSchema):
    __match__ = RatingSchema.name == "RedGreenYellow"

    __result = ""
    __memory = {}
    __colors = {0: "", 1: "gruen", 2: "gelb", 3: "rot"}

    def _get_rating(self, cdb_project_id, checklist_id):
        result = 0
        for k, v in list(self.__memory.items()):
            if k[0] == cdb_project_id and k[1] == checklist_id:
                if v == self.__colors[3] and result < 3:
                    result = 3
                elif v == self.__colors[2] and result < 2:
                    result = 2
                elif v == self.__colors[1] and result < 1:
                    result = 1
        return self.__colors[result]

    def calcRating(
        self,
        rating_id,
        weight,
        ko_criterion,
        cdb_project_id,
        checklist_id,
        cl_item_id=None,
    ):
        self.__memory[(cdb_project_id, checklist_id, cl_item_id)] = rating_id
        if rating_id == "rot":
            self.__result = "rot"
            return -1  # break
        else:
            self.__result = self._get_rating(cdb_project_id, checklist_id)
        return self.__result

    def getResult(self):
        return self.__result


class GradesRating(RatingSchema):
    __match__ = RatingSchema.name == "Grades"

    __rating_sum = 0
    __rating_weight_sum = 0
    __result = ""
    __memory_ratings = {}
    __memory_weights = {}

    def _get_rating(self):
        self.__rating_sum = 0
        self.__rating_weight_sum = 0
        ratings = []
        weights = []
        for v in self.__memory_ratings.values():
            ratings.append(v)
        for v in self.__memory_weights.values():
            weights.append(v)
        for i, rat in enumerate(ratings):
            self.__rating_sum += rat * weights[i]
            self.__rating_weight_sum += weights[i]

    def calcRating(
        self,
        rating_id,
        weight,
        ko_criterion,
        cdb_project_id,
        checklist_id,
        cl_item_id=None,
    ):
        try:
            rating_id = int(rating_id)
            weight = int(weight)
        except ValueError:
            try:
                del self.__memory_ratings[(cdb_project_id, checklist_id, cl_item_id)]
                del self.__memory_weights[(cdb_project_id, checklist_id, cl_item_id)]
            except KeyError:
                pass
            return 0
        self.__memory_ratings[(cdb_project_id, checklist_id, cl_item_id)] = rating_id
        self.__memory_weights[(cdb_project_id, checklist_id, cl_item_id)] = weight

        # Checkliste wird mit 6 Bewertet, wenn mindestens ein k.o. Kriterium mit 6 bewertet ist
        if ko_criterion and rating_id == 6:
            self.__result = "6"
            return -1  # break

    def getResult(self):
        self._get_rating()
        if self.__rating_sum == 0:
            self.__result = ""
        else:
            self.__result = (
                f"{int(round(self.__rating_sum / self.__rating_weight_sum))}"
            )
        return self.__result


GermanSchoolmarksRating = GradesRating


def fieldExists(cls, attr):
    rat_val_fields = Entity.ByKeys(classname=cls).DDAllFields
    attr_list = []
    for t in rat_val_fields:
        attr_list.append(t.field_name)
    if attr not in attr_list:
        return False
    else:
        return True


class ChecklistType(Object):
    __maps_to__ = "cdbpcs_cl_types"


class RuleReference(Object):
    __maps_to__ = "cdbpcs_deliv2rule"
    __classname__ = "cdbpcs_deliv2rule"

    Rule = Reference_1(fRule, fRuleReference.rule_id)
    Checklist = Reference_1(
        fChecklist, fRuleReference.cdb_project_id, fRuleReference.checklist_id
    )


@classbody
class Task:
    @sig.connect(Task, "cdbpcs_checklist_assign", "now")
    def _assign_item_checklist(self, ctx):
        Checklist.cdbpcs_checklist_assign(self, ctx)


class ChecklistCategory(Object):
    __maps_to__ = "cdbpcs_cl_cat"


class RatingWeighting(Object):
    __maps_to__ = "cdbpcs_rat_wght"


class RatingAssignment(Object):
    __maps_to__ = "cdbpcs_rat_asgn"
