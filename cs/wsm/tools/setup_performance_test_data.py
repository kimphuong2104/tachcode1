#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import absolute_import
from __future__ import print_function

from cs.wsm.tools.create_test_workspace import (
    create_test_workspace,
    delete_workspace_with_referenced_documents,
)

from cs.workspaces import Workspace

PERFTEST_WORKSPACE_510 = "Perftest Workspace 510 models"
PERFTEST_WORKSPACE_1020 = "Perftest Workspace 1020 models"

Parameters = {
    "num_top_docs": 2,
    "num_children_per_doc": 2,
    "depth": 8,
    "num_index_per_doc": 3,
    "file_size": 512,
    "part_file_type": "inventor:prt",
    "assembly_file_type": "inventor:asm",
    "document_attributes": {
        "cdb_classname": "model",
        "z_art": "cad_assembly",
        "z_status": 0,
        "wsm_is_cad": "1",
    },
    "item_attributes": {},
}


def setup_performance_test_data():
    delete_old_performance_test_data()
    create_test_workspace(name=PERFTEST_WORKSPACE_510, parameters=Parameters, depth=8)
    create_test_workspace(name=PERFTEST_WORKSPACE_1020, parameters=Parameters, depth=9)


def delete_old_performance_test_data():
    for titel in [PERFTEST_WORKSPACE_510, PERFTEST_WORKSPACE_1020]:
        workspaces = Workspace.KeywordQuery(titel=titel)
        for ws in workspaces:
            print("\nDeleting old workspace '%s'" % titel)
            delete_workspace_with_referenced_documents(ws)


if __name__ == "__main__":
    setup_performance_test_data()
