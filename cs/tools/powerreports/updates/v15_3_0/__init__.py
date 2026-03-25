#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Update Tasks for cs.tools.powerreports 15.3.0
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import comparch, dberrors, sqlapi, util


class AddDialogHooks(object):
    """
    There is a generic handler for the 'Save filter'  button.
    This script adds the dialog hooks we need to handle this
    button.
    The script also adds a ::PRE_DISPLAY:: hook for the masks that
    contain this button to preset the values stored by the filter.
    """

    def run(self):
        cond = (
            "user_exit = 'cdbxml_set_defaults' AND "
            + "cdb_module_id like '%s.%%'" % comparch.get_dev_namespace()
            + "AND cdb_module_id != 'cs.tools.powerreports'"
        )
        rs = sqlapi.RecordSet2(
            "masken", columns=["name", "attribut", "cdb_module_id"], condition=cond
        )
        for r in rs:
            # Try to create a dialog hook
            i = util.DBInserter("csweb_dialog_hook")
            i.add("dialog_name", r.name)
            i.add("attribut", r.attribut)
            i.add("hook_name", "EmulateLegacyDialogButton")
            i.add("position", "10")
            i.add("active", "1")
            i.add("cdb_module_id", r.cdb_module_id)
            try:
                i.insert()
            except dberrors.DBConstraintViolation:
                # Doesn't matter - hook seems to be already there
                pass
            i.add("hook_name", "ReportLoadParameter")
            i.add("attribut", "::PRE_DISPLAY::")
            try:
                i.insert()
            except dberrors.DBConstraintViolation:
                # Doesn't matter - hook seems to be already there
                pass


post = [AddDialogHooks]
