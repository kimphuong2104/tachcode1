#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import absolute_import
from __future__ import print_function

import six
import sys
from cdb import sqlapi


help_text = (
    "\nThis script enables common operations on workspaces, (CAD) documents and parts\n"
    "for use in Workspaces Desktop.\n"
    "This is only needed when using the 'CEWeb' adapter, for example when deployed in a SaaS scenario.\n\n"
    "As a side effect, the operations also become available in the regular Elements UI in the web browser.\n\n"
)


def enable_embedded_operations():
    operations = [
        "CDB_ShowObject",
        "CDB_Modify",
        "CDB_Create",
        "CDB_Index",
        "CDB_Search",
        "CDB_Workflow",
        "CDB_Copy",
    ]
    classes = ["document", "model", "cdb_wsp", "part"]

    # offer_in_web_ui
    stmt = """
           cdb_operations
       SET offer_in_web_ui = 1
     WHERE name in (%s)
       AND classname in (%s)
       AND offer_in_web_ui = 0
    """ % (
        ",".join("'%s'" % op for op in operations),
        ",".join("'%s'" % cls for cls in classes),
    )
    changes = sqlapi.SQLupdate(stmt)
    print("Changed 'offer_in_web_ui' in %s operations." % changes)

    # menu_visible
    changes = 0
    for prevState, newState in [
        (0, 4),  # "not visible" -> "visible only in Web UI"
        (2, 1),
    ]:  # "visible only in Windows Client" -> "visible in every client"
        stmt = """
              cdb_operations
           SET menu_visible = %s
         WHERE menu_visible = %s
           AND name in (%s)
           AND classname in (%s)
        """ % (
            newState,
            prevState,
            ",".join("'%s'" % op for op in operations),
            ",".join("'%s'" % cls for cls in classes),
        )
        changes += sqlapi.SQLupdate(stmt)

    print("Changed 'menu_visible' in %s operations." % changes)
    print("Completed without error.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        enable_embedded_operations()
    else:
        print(help_text)
        yes = six.moves.input(
            "Do you really want to run the script? [y|N]? "
        ).lower() in ["y", "yes"]
        if yes:
            enable_embedded_operations()
