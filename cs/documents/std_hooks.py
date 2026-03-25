# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
The module contains some dialog hooks used by `cs.documents`
"""

# pylint: disable=bad-continuation


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []

from cdb import constants, util
from cdb.platform import gui
from cdb.platform.olc import StatusInfo
from cs.documents import Document, DocumentCategory
from cs.web.components.ui_support.frontend_dialog import FrontendDialog


def OLCCheckLockedHook(hook):
    """
    Hook that looks for an argument that indicates that a status change should
    be done for a document locked by a different user.
    The hook displays a question if the user really wants to change the state.
    """
    arg = None
    try:
        arg = constants.kArgumentUnlockQuestion
    except AttributeError:
        # Seems to be an older version
        return
    msg = hook.get_new_values().get(arg, None)
    if msg is not None:
        fe = FrontendDialog("", msg, ".dokument_freigeben")
        fe.add_button(
            util.get_label("web.base.dialog_yes"),
            1,
            FrontendDialog.ActionSubmit,
            is_default=True,
        )
        fe.add_button(
            util.get_label("web.base.dialog_no"),
            0,
            FrontendDialog.ActionCancel,
            is_cancel=True,
        )
        hook.set_dialog(fe)


def OLCCheckReferencedHook(hook):
    """
    Hook that checks if referenced documents have an appropriate state.
    If not, the user will be asked if he wants to continue the action.

    Note that this hook will only work with the standard definitions of
    the object lifecycle.
    """
    zielstatus = hook.get_new_values().get(".zielstatus", "")
    obj = hook.get_operation_state_info().get_objects()[0]
    olc = obj["z_art"]
    si_100 = StatusInfo(olc, 100)
    si_200 = StatusInfo(olc, 200)
    msg = None
    inv_docs = []
    if si_100 and si_100.getLabel() == zielstatus:
        doc = Document._FromObjectHandle(obj)  # pylint: disable=protected-access
        inv_docs = doc.GetReferencedDocsWithInvalidState([100, 200])
        msg = "cdb_konfstd_024"
    elif si_200 and si_200.getLabel() == zielstatus:
        doc = Document._FromObjectHandle(obj)  # pylint: disable=protected-access
        inv_docs = doc.GetReferencedDocsWithInvalidState([200])
        msg = "cdb_konfstd_025"
    if msg and inv_docs:
        docRefMsg = "\\n".join(doc.GetDescription() for doc in inv_docs)
        msg = gui.Message.GetMessage(msg, docRefMsg)
        fe = FrontendDialog("", msg)
        fe.add_button(
            util.get_label("yes"), 1, FrontendDialog.ActionSubmit, is_default=True
        )
        fe.add_button(
            util.get_label("no"), 0, FrontendDialog.ActionCancel, is_cancel=True
        )
        hook.set_dialog(fe)


def CheckItemReference(hook):
    """
    Check if an item reference is obligatory for a document with the
    given category.
    """

    def _get_leaf_category(hook):  # pylint: disable=inconsistent-return-statements
        attrs = Document.CategoryAttributeNames()
        attrs.reverse()
        for attr in attrs:
            categ_id = hook.get_new_object_value(attr)
            if categ_id:
                return DocumentCategory.ByKeys(categ_id)

    if hook.get_operation_name() in [
        constants.kOperationNew,
        constants.kOperationCopy,
        constants.kOperationModify,
    ]:
        tnr = hook.get_new_object_value("teilenummer")
        if not tnr:
            c = _get_leaf_category(hook)
            if c and c.ItemReferenceMandatory():
                msg = gui.Message.GetMessage("cdb_konfstd_021", c.GetDescription())
                hook.set_error("", msg)
