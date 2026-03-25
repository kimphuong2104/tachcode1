# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module contains the implementation of some dialog hook function used
by the administration and configuration section of the system.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


from cdbwrapc import getOpNameFromMenuLabel
from cdb import constants
from cdb import fls
from cdb import util
from cdb import ElementsError
from cdb.objects import org
from cdb.platform import gui
from cdb.platform.mom.relships import Relship
from cdb.platform.mom import entities, SimpleArguments
from cdb.platform.mom.entities import CDBClassDef, DDClassJoin
from cs.web.components.ui_support.frontend_dialog import FrontendDialog


def _get_button_label(label):
    """
    Strips & and other things the client uses for buttons.
    """
    l = util.get_label(label)
    return getOpNameFromMenuLabel(l, False)


def class_confirm_fqpyname(hook):
    """
    This backend dialog hook checks if a fqpyname has been entered for
    a subclass and asks the user if this is ok.
    """
    def ask(hook, fqpyname):
        # Create a message box
        msg = gui.Message.GetMessage("csplatform_warning_subclass_fqpyname",
                                     fqpyname)
        fe = FrontendDialog('', msg, "cdb::argument.warning_subclass_fqpyname")
        fe.add_button(_get_button_label("button.mnemonic_yes"), 1,
                      FrontendDialog.ActionCallServer)
        fe.add_button(_get_button_label("button_cancel"), 0,
                      FrontendDialog.ActionBackToDialog, is_cancel=True)
        hook.set_dialog(fe)

    fqpyname = hook.get_new_object_value("fqpyname")
    base_cls = hook.get_new_object_value("base_cls")
    if fqpyname and base_cls:
        confirm = hook.get_new_values().get("cdb::argument.warning_subclass_fqpyname")
        if confirm is None or confirm == 0:
            # On modification only ask if either fqpyname or base_cls have changed
            if hook.get_operation_name() != constants.kOperationModify:
                ask(hook, fqpyname)
            else:
                obj = entities.Entity.ByKeys(hook.get_new_object_value("classname"))
                if fqpyname != obj.fqpyname or \
                   base_cls != obj.base_cls:
                    ask(hook, fqpyname)


def class_confirm_index_disable(hook):
    """
    Ask the user if a class should really be no longer searchable.
    """
    def ask(hook, classname):
        # Create a message box
        msg = gui.Message.GetMessage("disable_indexing", classname)
        fe = FrontendDialog('', msg, "cdb::argument.warning_index_disable")
        fe.add_button(_get_button_label("button.mnemonic_yes"), 1,
                      FrontendDialog.ActionCallServer)
        fe.add_button(_get_button_label("button.mnemonic_no"), 0,
                      FrontendDialog.ActionCallServer)
        hook.set_dialog(fe)

    # If is_indexed was true for the class, but the user changed it to false,
    # ask them it they are sure the wanted to do it. Otherwise, they could
    # accidently delete all the search index entries for the class. For a
    # class with file objects, this would mean a non trivial re-indexing of
    # the class.
    if hook.get_operation_name() == constants.kOperationModify:
        confirm = hook.get_new_values().get("cdb::argument.warning_index_disable")
        classname = hook.get_new_object_value("classname")
        if confirm is None and entities.Entity.ByKeys(classname).is_indexed:
            # Check if the value has changed
            new_value = hook.get_new_object_value("is_indexed")
            if new_value == 0:
                ask(hook, classname)
        else:
            if confirm == 0:
                # mark the class as is_indexed again.
                cdef = CDBClassDef("cdb_entity")
                hook.set(cdef.getAttrIdentifier("is_indexed"), 1)


def relship_confirm_join_change(hook):
    """
    This backend dialog hook checks if the change of a relationship affects
    a join and asks the user if he really wants to do so.
    """
    if hook.get_operation_name() != constants.kOperationModify:
        return
    rship = Relship.ByKeys(hook.get_new_object_value("name"))
    if rship.isJoinRelship():
        attrs = ["referer_kmap",
                 "reference_kmap",
                 "relship_cldef",
                 "referer",
                 "reference"]
        diffs = [attr for attr in attrs
                 if hook.get_new_object_value(attr) != rship[attr]]
        if diffs:
            join = DDClassJoin.KeywordQuery(join_relship=rship.name)[0]
            confirm = hook.get_new_values().get("cdb::argument.confirm_join_change")
            if confirm is None:
                cdef = CDBClassDef("cdb_relships")
                ui_names = [cdef.getAttributeDefinition(attr).getLabel()
                            for attr in diffs]
                msg = gui.Message.GetMessage("cdbdd_confirm_join_relship_change",
                                             join.classname, rship.reference,
                                             ', '.join(ui_names),
                                             join.classname)
                fe = FrontendDialog('',
                                    msg,
                                    "cdb::argument.confirm_join_change")
                fe.add_button(_get_button_label("button.mnemonic_yes"), 1,
                              FrontendDialog.ActionCallServer)
                fe.add_button(_get_button_label("button.mnemonic_no"), 0,
                              FrontendDialog.ActionCallServer,
                              is_default=True)
                hook.set_dialog(fe)
            elif confirm == 0:
                # Keep the original values
                cdef = CDBClassDef("cdb_relships")
                for attr in diffs:
                    hook.set(cdef.getAttrIdentifier(attr), rship[attr])
            elif confirm == 1:
                join.Class.setDirty()


def user_quest_deactivate_account(hook):
    """
    Ask the user if the account should be deactivated if the visibility flag
    is ``0``.
    """
    def ask(hook):
        # Create a message box
        msg = gui.Message.GetMessage("quest_deactivate_account")
        fe = FrontendDialog('', msg, "cdb::argument.quest_deactivate_account")
        fe.add_button(_get_button_label("change_visibility_flag"),
                      "change_visibility_flag",
                      FrontendDialog.ActionBackToDialog)
        fe.add_button(_get_button_label("change_active_account"),
                      "change_active_account",
                      FrontendDialog.ActionBackToDialog)
        fe.add_button(_get_button_label("button_cancel"), "",
                      FrontendDialog.ActionBackToDialog, is_cancel=True)
        hook.set_dialog(fe)

    if hook.get_operation_name() == constants.kOperationModify:
        confirm = hook.get_new_values().get("cdb::argument.quest_deactivate_account")
        if not confirm:
            try:
                active_account = int(hook.get_new_object_value("active_account"))
            except Exception:
                active_account = 0
            visibility_flag = hook.get_new_object_value("visibility_flag")
            if not visibility_flag and active_account:
                ask(hook)
        else:
            if confirm == "change_visibility_flag":
                hook.set("visibility_flag", 1)
            else:
                hook.set("active_account", "0")


def ce_convert_to_user(hook):
    if hook.get_operation_name() != "ce_convert_to_user":
        # The hook is only for ce_convert_to_user
        return
    persno = hook.get_new_object_value("personalnummer")
    if not persno:
        # This should never happen so just an english error
        hook.set_error("", "Failed to retrieve personal number")
        return
    p = org.Person.ByKeys(persno)
    try:
        p.convert_to_user(SimpleArguments(**hook.get_new_values()))
    except ElementsError as e:
        hook.set_error(util.get_label("error_title_ce_convert_to_user"),
                       str(e))


def ce_protect_lic_feature_assignments(hook):
    """
    Protect the assignments of module `module_id`
    """
    confirm = hook.get_new_values().get("cdb::argument.assign_done")
    if confirm:
        # Assignment already done
        return
    from cdbwrapc import sign_module_features
    module_id = hook.get_new_object_value("module_id")
    master_pw = hook.get_new_value(".master_pw")
    count = sign_module_features(module_id, master_pw)
    if count < 0:
        msg = gui.Message.GetMessage("cdb_lic_feature_assign_wrong_pw")
        title = util.get_label("web.base.op_failed")
        fe = FrontendDialog(title, msg, "cdb::argument.assign_dummy")
        fe.add_button(_get_button_label("ok"), 0,
                      FrontendDialog.ActionBackToDialog, is_cancel=True)
        hook.set_dialog(fe)
        return
    else:
        msg = gui.Message.GetMessage("cdb_lic_feature_assign_done", count)
        fe = FrontendDialog('', msg, "cdb::argument.assign_done")
        fe.add_button(_get_button_label("ok"), 1,
                      FrontendDialog.ActionCallServer)
        hook.set_dialog(fe)


def fls_confirm_install_lics(hook):
    """
    Ask the user if a he really wants to install the license file if there are
    already licenses in the system.
    """
    def ask(hook):
        # Create a message box
        msg = gui.Message.GetMessage("cdblic_askinst")
        fe = FrontendDialog('', msg, constants.kArgumentLicReallyInstall)
        fe.add_button(_get_button_label("button.mnemonic_yes"), 1,
                      FrontendDialog.ActionSubmit)
        fe.add_button(_get_button_label("button.mnemonic_no"), 0,
                      FrontendDialog.ActionSubmit)
        hook.set_dialog(fe)

    confirm = hook.get_new_values().get(constants.kArgumentLicReallyInstall)
    if confirm is None and fls.get_licsystem_info()["lics_installed"]:
        ask(hook)


# Guard importing as main module
if __name__ == "__main__":
    pass
