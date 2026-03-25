#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.pcs.projects.updates.v15_7_0 import InitSortableIDBase


class InitSortableID_Checklist(InitSortableIDBase):
    """
    Initializes the new primary key ``cdbpcs_cl_prot.cdbprot_sortable_id``.
    """

    __table_name__ = "cdbpcs_cl_prot"


class InitSortableID_CLI(InitSortableIDBase):
    """
    Initializes the new primary key ``cdbpcs_cli_prot.cdbprot_sortable_id``.
    """

    __table_name__ = "cdbpcs_cli_prot"


pre = [InitSortableID_Checklist, InitSortableID_CLI]
post = []
