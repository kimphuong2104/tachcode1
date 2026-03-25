# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module wseditview

This is the documentation for the wseditview module.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"


import logging

from cdb import sig
from cdb import ue, ElementsError
from cdb.objects.operations import operation
from cdb.constants import kOperationLock
from cdb.platform.mom.operations import OperationConfig
from cdb.objects import ClassRegistry
from cs.documents import Document
from cs.workspaces import open_with_cdbwscall

from cs.wsm.cadfiletypes import get_cad_file_types

_CDBWSCALL_LOAD_AND_OPEN_CAD_DOCUMENT_FILE = u"""<?xml version="1.0"?>
<cdbwsinfo>
   <command>loadandopencaddocument</command>
   <options>
      <pdmadapter>{pdmadapter}</pdmadapter>
      <office_mode>{office_mode_value}</office_mode>
      <requiredversion>3.2.0</requiredversion>
   </options>
   <parameters>
       <parameter>{cdb_object_id}</parameter>
   </parameters>
</cdbwsinfo>
"""


class EditView(object):
    def __init__(self, cdbObj):
        self.cdbObj = cdbObj

    def open_document_for_view(self, ctx=None):
        self.check_single_anchor_file()
        office_mode = self.handle_as_non_cad_document()
        self.open_doc_with_cdbwscall(ctx, office_mode)

    def open_document_for_edit(self, ctx=None):
        self.check_single_anchor_file()
        office_mode = self.handle_as_non_cad_document()
        if self.try_lock_document(ctx, office_mode):
            self.open_doc_with_cdbwscall(ctx, office_mode)

    def handle_as_non_cad_document(self):
        """
        Handle a document or any other object, that is file-based, as
        a non-CAD object, when

        1. The object has no folders
        2. The object is a Document and erzeug_system != CAD
        3. The object is not a Document and primary file type is != CAD

        :return: Whether to handle the object/document as a non-cad object.
        :rtype: bool
        """
        ret = False
        folder_items = self.cdbObj.Files.KeywordQuery(cdb_classname="cdb_folder_item")
        has_folder = bool(folder_items)
        if not has_folder:
            cad_file_types = get_cad_file_types()
            if isinstance(self.cdbObj, Document):
                isCad = self.cdbObj.erzeug_system in cad_file_types
                ret = not isCad
            else:
                primFiles = self.cdbObj.Files.KeywordQuery(cdbf_primary="1")
                ret = primFiles and primFiles[0].cdbf_type not in cad_file_types
        return ret

    def check_single_anchor_file(self, ctx=None):
        """
        Raises a user-visible exception unless the document has exactly one main file.
        """
        numPrimaryFiles = len(self.cdbObj.Files.KeywordQuery(cdbf_primary="1"))
        if numPrimaryFiles == 0:
            raise ue.Exception("wsd_no_anchor_file")
        elif numPrimaryFiles > 1:
            raise ue.Exception("wsd_no_unique_anchor_file")

    def open_doc_with_cdbwscall(self, ctx, office_mode):
        """
        :param office_mode: bool
        """
        open_with_cdbwscall(
            ctx,
            _CDBWSCALL_LOAD_AND_OPEN_CAD_DOCUMENT_FILE,
            office_mode_value=1 if office_mode else 0,
            cdb_object_id=self.cdbObj.cdb_object_id,
        )

    def try_lock_document(self, ctx, office_mode):
        """
        Returns True if document was immediatly locked successfully.
        When using Windows Client,
         will ask user if it should open even when locking was not possible.
        When using Web client,
         a dialog hook will show a message if the locking failed (see workspaces_dialog_hooks.py).
        """
        # lock document and all primary files
        try:
            operation(kOperationLock, self.cdbObj)
            return True
        except ElementsError:
            self.notify_user_and_load(ctx, office_mode)
            return False

    def notify_user_and_load(self, ctx, office_mode):
        """
        Notify user about failed locking of document.
        Ask the user if he still wants to load document.
        """
        arg_name = u"lock_failed_on_wsm_open_for_edit"
        if arg_name not in ctx.dialog.get_attribute_names() and not ctx.uses_webui:
            # Arg is missing, so ask user whether document should be
            # loaded nevertheless we use already existing error
            # message and button label from cs.platform.core
            msgbox = ctx.MessageBox(
                "dok_save_warning", [], arg_name, ctx.MessageBox.kMsgBoxIconQuestion
            )
            btn = ctx.MessageBoxButton(
                "cdbwin_ll_Bearbeit",
                "1",
                ctx.MessageBoxButton.kButtonActionCallServer,
                is_dflt=1,
            )
            msgbox.addButton(btn)
            msgbox.addCancelButton()
            ctx.show_message(msgbox)
        else:
            self.open_doc_with_cdbwscall(ctx, office_mode)


def open_document_for_view(obj, ctx=None):
    ev = EditView(obj)
    ev.open_document_for_view(ctx)


def open_document_for_edit(obj, ctx=None):
    ev = EditView(obj)
    ev.open_document_for_edit(ctx)


def register_edit_and_view():
    connected_classes = set()
    for opname in ["wsd_edit", "wsd_view"]:
        register_operation(opname, connected_classes)


def register_operation(op_name, connected_classes):
    for op in OperationConfig.KeywordQuery(name=op_name):
        register_class(op.classname, op_name, connected_classes)


def register_class(classname, op_name, connected_classes):
    """
    signal fuer die jeweilge Klasse registrieren...
    """
    cl = ClassRegistry()
    clToConnect = cl.findByClassname(classname)
    if (clToConnect, op_name) not in connected_classes:
        logging.debug("Registers %s for %s" % (str(clToConnect), op_name))
        if op_name == "wsd_edit":
            sig.connect(clToConnect, op_name, "now")(open_document_for_edit)
        elif op_name == "wsd_view":
            sig.connect(clToConnect, op_name, "now")(open_document_for_view)
        connected_classes.add((clToConnect, op_name))
