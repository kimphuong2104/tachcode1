#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import sys
from cdb import sqlapi
from cdb import tools
from cdb.platform import FolderContent
from cs.workflow.briefcases import Briefcase

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def usage():
    print("usage: assign_objects.py [--help]|clsname")
    print("\nExample: >powerscript assign_objects.py 'customer.wfm.MyObjectReference'")
    print("\nTools to map customized orole assignments into briefcase content after update.")
    print("The full qualified python name of the reference class should be given.")
    print("The object reference class should be importable in powerscript and define")
    print("'ReferencedObject' referenced to the target object as that in legacy ")
    print("'cdb.objects.wfm.ObjectReference' class.")
    print("\nThe referenced object must contain 'cdb_object_id' attribute.")


def assign_objects_from(pyname):
    """
    Tools to map customized orole assignments into briefcase content after update.

    The object reference class should be importable in powerscript and define
    `ReferencedObject`.

    The referenced object must contain `cdb_object_id` attribute.


    Usage::

        >powerscript assign_objects.py "customer.wfm.MyObjectReference"

    """
    try:
        cond = "cdb_process_id='%s' and role_id='%s'"
        ref_cls = tools.getObjectByName(pyname)
        refs = ref_cls.Query()
        for ref in refs:
            role_id = ref.role_id
            cdb_process_id = ref.cdb_process_id
            obj_id = ref.ReferencedObject.cdb_object_id
            orole = sqlapi.RecordSet2(table="cdbwf_orole",
                                      condition=cond % (cdb_process_id, role_id))
            role_name = None
            if orole:
                role_name = orole[0].role_name
            if role_name:
                briefcases = Briefcase.KeywordQuery(cdb_process_id=cdb_process_id,
                                                    name=role_name)
                if briefcases:
                    briefcase = briefcases[0]
                    if not briefcase.FolderContents.Query("cdb_content_id='%s'" % obj_id):
                        FolderContent.Create(cdb_folder_id=briefcase.cdb_object_id,
                                             cdb_content_id=obj_id)
    except Exception as e:
        print("Error: %s" % e)


if __name__ == "__main__":
    # Change sys.argv to unicode
    args = sys.argv[1:]
    if not args or args[0] == "--help" or len(args) > 1:
        usage()
    else:
        assign_objects_from(args[0])
