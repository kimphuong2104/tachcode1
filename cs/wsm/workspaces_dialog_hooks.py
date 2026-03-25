from __future__ import absolute_import
from cdb import ElementsError
from cdb import util
from cdb.objects import object_from_handle
from cdb.objects.operations import operation
from cdb.constants import kOperationLock
from cs.wsm import Document


# cs.wsm.workspaces_dialog_hooks.confirm_load_document
# AskUserToLoadDoc

# we use a configured "AskUserToLoadDoc" OperationHook wich is only available in webUI
# this OperationHook utilizes an OperationHookFunktion with the same name
# linking to this module. With this config and module we try to work around the fact
# that the powerscript operations have very limited (mostly raise ue.Exception)
# possibilities to give messages to user and get user decisions.
# Operations with mask configs have can use DialogHooks and DialogHooksFunctions.
# see: https://docs.contact.de/15.6/de/programming/web_ui_dev/web_ui_operations_hooks
#
# from cs.web.components.ui_support.frontend_dialog import FrontendDialog
# def my_dlg_hook_method(hook)
#     fe = FrontendDialog("LABEL_1", "LABEL_2")
#     fe.add_button("Load", "0",
#                   FrontendDialog.ActionSubmit, is_default=True)
#     fe.add_button("Cancel", "0",
#                   FrontendDialog.ActionCancel, is_default=False)
#     hook.set_dialog(fe)


def confirm_load_document(hooks, hook_ctx):
    """
    Objects passed to this method are implemented in
    cdb\\platform\\mom\\hooks.py

    :param hooks: list of all OperationHook objects connected to this method
    :param hook_ctx: OperationHookContext object.
    """
    op_ctx = hook_ctx.op_ctx
    # access to object via [0] is fine since the operation
    # is defined on SingleObject
    docObjHandle = op_ctx.getObjects()[0]

    doc = object_from_handle(docObjHandle)
    replacements = doc.GetDescription()
    db_label = util.get_label_with_fallback(
        "lock_failed_on_wsm_open_for_edit",
        "The document: '%s' is opened without locking in PDM.",
    )
    label = db_label % replacements
    primary_files = doc.Files.KeywordQuery(cdbf_primary="1")
    if len(primary_files) == 1:
        try:
            operation(kOperationLock, doc)
        except ElementsError:
            hook_ctx.add_message(label)
