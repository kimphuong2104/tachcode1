#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

from cdb.sqlapi import SQLupdate


class SetObjektArt(object):
    """ Processes templates have new OLC. Update cdb_objektart
    """
    def run(self):
        SQLupdate("cdbwf_process SET cdb_objektart='cdbwf_process' WHERE is_template='0'")
        SQLupdate("cdbwf_process SET cdb_objektart='cdbwf_process_template' WHERE is_template='1'")


class FixStatusForTemplateProcesses(object):
    """ Transition to new OLC for already defined template processes
    """
    def run(self):
        SQLupdate("cdbwf_process SET status='20', cdb_status_txt='freigegeben' WHERE is_template='1' AND status<>'40'")


pre = []
post = [SetObjektArt, FixStatusForTemplateProcesses]

# Guard importing as main module
if __name__ == "__main__":
    SetObjektArt().run()
    FixStatusForTemplateProcesses().run()
