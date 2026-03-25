#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import constants, rte, sig, ue, util
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_N
from cdb.objects.operations import operation

from cs.documents import Document
from cs.vp.items import Item
from cs.vp.items_documents import dialog_utils

DocumentToPart = Forward(__name__ + ".DocumentToPart")


@classbody
class Document(object):
    Item = Reference_1(Item, Document.teilenummer, Document.t_index)

    ItemReferences = Reference_N(
        DocumentToPart,
        DocumentToPart.z_nummer == Document.z_nummer,
        DocumentToPart.z_index == Document.z_index
    )

    def create_or_update_part_reference(self):
        if self.teilenummer:
            references = DocumentToPart.KeywordQuery(
                z_nummer=self.z_nummer,
                z_index=self.z_index,
                teilenummer=self.teilenummer,
                t_index=self.t_index
            )
            if references:
                # update existing weak references
                references.Update(kind=DocumentToPart.KIND_STRONG)
            else:
                DocumentToPart.Create(
                    z_nummer=self.z_nummer, z_index=self.z_index,
                    teilenummer=self.teilenummer, t_index=self.t_index,
                    kind=DocumentToPart.KIND_STRONG
                )

    def doc2part_disable_part_key(self, ctx):
        if ctx.relationship_name in ["cdb_part2documents", "cdb_bom_item_component2documents"]:
            ctx.set_fields_readonly(["teilenummer", "t_index"])

    def doc2part_preset_part_attributes(self, ctx):
        if ctx.relationship_name in ["cdb_part2documents", "cdb_bom_item_component2documents"]:
            self.teilenummer = ctx.parent["teilenummer"]
            self.t_index = ctx.parent["t_index"]
            dialog_utils.set_dlg_joined_part_fields(ctx, self, Item.ByKeys(self.teilenummer, self.t_index))

    def doc2part_create_strong_reference(self, ctx):
        if ctx.error:
            return
        if (
                ctx.relationship_name in ["cdb_part2documents", "cdb_bom_item_component2documents"] and
                ctx.parent.teilenummer == self.teilenummer and
                ctx.parent.t_index == self.t_index
        ):
            # rel object has already been created from kernel
            return
        self.create_or_update_part_reference()

    def doc2part_keep_old_part_keys_if_needed(self, ctx):
        if ctx.object.teilenummer != self.teilenummer or ctx.object.t_index != self.t_index:
            ctx.keep("doc2part_old_part_number", ctx.object.teilenummer)
            ctx.keep("doc2part_old_part_index", ctx.object.t_index)

    def doc2part_prevent_duplicate(self, ctx):
        if ctx.relationship_name == "cdb_part2documents":
            # if a document index is created in doc2part relationship context the relationship object is
            # created because of the relship profile and a second relationship object would be created
            # due to the relationship context. to avoud the second creation and the duplicate pri key
            # error message we skip the second creation.
            ctx.skip_relationship_assignment()

    def doc2part_update_strong_reference(self, ctx):
        part_ref_changed = "doc2part_old_part_number" in ctx.ue_args.get_attribute_names()
        if part_ref_changed:
            if (
                self.teilenummer != ctx.ue_args["doc2part_old_part_number"] or
                self.t_index != ctx.ue_args["doc2part_old_part_index"]
            ):
                # delete existing doc2part objects that have been created with old partnumber and old part index
                references = DocumentToPart.KeywordQuery(
                    z_nummer=self.z_nummer,
                    z_index=self.z_index,
                    teilenummer=ctx.ue_args["doc2part_old_part_number"],
                    t_index=ctx.ue_args["doc2part_old_part_index"]
                )
                for reference in references:
                    operation(constants.kOperationDelete, reference)
            if self.teilenummer:
                self.create_or_update_part_reference()


@classbody
class Item(object):
    Documents = Reference_N(Document,
                            Document.teilenummer == Item.teilenummer,
                            Document.t_index == Item.t_index)

    DocumentReferences = Reference_N(
        DocumentToPart,
        DocumentToPart.teilenummer == Item.teilenummer,
        DocumentToPart.t_index == Item.t_index
    )


class DocumentToPart(Object):
    __maps_to__ = "cdb_doc2part"
    __classname__ = "cdb_doc2part"

    KIND_STRONG = 'strong'
    KIND_WEAK = 'weak'

    Document = Reference_1(Document, DocumentToPart.z_nummer, DocumentToPart.z_index)
    Item = Reference_1(Item, DocumentToPart.teilenummer, DocumentToPart.t_index)

    def can_delete(self, ctx):
        if self.Document.teilenummer == self.teilenummer and self.Document.t_index == self.t_index:
            raise ue.Exception('cdb_doc2part_not_deletable')

    def ensure_correct_kind(self, ctx):
        if self.Document.teilenummer == self.teilenummer and self.Document.t_index == self.t_index:
            self.kind = DocumentToPart.KIND_STRONG
        else:
            self.kind = DocumentToPart.KIND_WEAK

    def skip_dialog(self, ctx):
        if (
                ctx.relationship_name in ["cdb_document2parts", "cdb_part2documents"] and
                self.teilenummer and
                self.z_nummer
        ):
            # skip dialog if foreign keys are already set, otherwise the dialog is diplayed if a user copies
            # or indexes a part or document in relationship context of doc2part relation
            ctx.skip_dialog()

    def is_effectivity_period_valid(self, ctx):
        if self.ce_valid_from is None or self.ce_valid_to is None:
            return

        if self.ce_valid_to < self.ce_valid_from:
            raise ue.Exception("cdbvp_bom_invalid_effectivity_period")

    event_map = {
        ("create", "pre_mask"): "skip_dialog",
        (("create", "modify"), "pre"): "ensure_correct_kind",
        (("create", "copy", "modify"), "pre"): "is_effectivity_period_valid",
        ("delete", "pre"): "can_delete"
    }


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def connect_document_user_exits():
    if util.get_prop("d2p") != "0":
        sig.connect(Document, "copy", "pre_mask")(document_copy_pre_mask)
        sig.connect(Document, "create", "pre_mask")(document_create_pre_mask)
        sig.connect(Document, "copy", "post")(create_strong_reference)
        sig.connect(Document, "create", "post")(create_strong_reference)
        sig.connect(Document, "copy", "pre")(keep_old_part_keys_if_needed)
        sig.connect(Document, "index", "pre")(keep_old_part_keys_if_needed)
        sig.connect(Document, "modify", "pre")(keep_old_part_keys_if_needed)
        sig.connect(Document, "index", "pre")(prevent_duplicate)
        sig.connect(Document, "index", "post")(update_strong_reference)
        sig.connect(Document, "modify", "post")(update_strong_reference)


def document_copy_pre_mask(doc, ctx):
    doc.doc2part_disable_part_key(ctx)


def document_create_pre_mask(doc, ctx):
    doc.doc2part_preset_part_attributes(ctx)


def create_strong_reference(doc, ctx):
    doc.doc2part_create_strong_reference(ctx)


def prevent_duplicate(doc, ctx):
    doc.doc2part_prevent_duplicate(ctx)


def keep_old_part_keys_if_needed(doc, ctx):
    doc.doc2part_keep_old_part_keys_if_needed(ctx)


def update_strong_reference(doc, ctx):
    doc.doc2part_update_strong_reference(ctx)
