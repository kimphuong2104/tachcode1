#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import logging

from cdb import sig
from cdb.classbody import classbody
from cdb.objects import Reference_1
from cdb import ue
from cdb import constants
from cdb.platform.mom import OperationContext

from cs.documents import Document
from cs.vp.bomcreator.bomconfig import BOMConfig
from cs.vp.items import Item
from cs.vp.cad import CADVariant


@classbody
class Document(object):
    @sig.connect(Document, "cdbwsm_createbom", "now")
    def _cdbwsm_createbom(self, ctx):
        """
        Called when the user wants to import a BOM for this document.
        Starts the bomcreator e-Link app."""
        ctx.url("/cs-vp-bomcreator/"
                "?cdb_object_id=%s&cadsource=%s" %
                (self.cdb_object_id, self.erzeug_system))

    @sig.connect(Document, "create", "pre_mask")
    @sig.connect(Document, "copy", "pre_mask")
    @sig.connect(Document, "modify", "pre_mask")
    def disable_bom_method(self, ctx):
        """
        Disable the "STL-Ausleitung" field except if the currently valid
        configuration of "Stuecklistenausleitung" results in a document-specific
        Ausleitungsmethode for this document.
        """
        if not self._has_document_specific_bom_creation():
            ctx.set_readonly('bom_method')
        return True

    special_reader = 'cs.vp.bomcreator.takereaderfromdocument.TakeReaderFromDocument'

    def _has_document_specific_bom_creation(self):
        if self.isModel() and self.erzeug_system is not None:
            config = BOMConfig.find_config(self.erzeug_system,
                                           self.cdb_object_id,
                                           only_applicables=False)
            if config is not None:
                if config.Method.class_name == self.special_reader:
                    return True
        return False


@classbody
class CADVariant(object):
    # for use by object rules
    Document = Reference_1(Document, CADVariant.z_nummer, CADVariant.z_index)

    @sig.connect(CADVariant, "cad_variant_copy_item", "now")
    def copy_item(self, ctx):
        """
        Convenience operation: copy the item of the CAD document and assign
                it to this CAD variant.
        """
        if self.Item:
            raise ue.Exception("cad_variant_already_has_valid_item", self.variant_name)

        document_item = self.Document.Item
        if not document_item:
            logging.error("CADVariant.copy_item: CAD document unexpectedly does not have an item.")
            return

        kwargs = {"cdb::argument.variant_object_id": self.cdb_object_id}
        ctx.url(document_item.MakeURL(constants.kOperationCopy, **kwargs))
        # the rest is done in Item.copy_post (see below)


@classbody
class Item(object):
    @sig.connect(Item, "copy", "post")
    def copy_post(self, ctx):
        if 'variant_object_id' in ctx.sys_args.get_attribute_names():
            # assign new item to variant
            variant_object_id = ctx.sys_args["variant_object_id"]
            variant = CADVariant.ByKeys(cdb_object_id=variant_object_id)
            if variant:
                variant.teilenummer = self.teilenummer
                variant.t_index = self.t_index

    @sig.connect(Item, "relship_copy", "pre")
    def before_relship_copy(self, ctx):
        # don't copy the BOM if we are copying this item for assignment to a
        # cad variant
        if ctx.relationship_name == "CDB::Relationship::STL::part2bom_item":
            if ctx.superior_operation_context_id:
                super_context = OperationContext(ctx.superior_operation_context_id)
                if super_context.getArgumentValueByName("cdb::argument.variant_object_id"):
                    ctx.skip_relationship_copy()
