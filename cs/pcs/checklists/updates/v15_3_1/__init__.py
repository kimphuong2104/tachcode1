#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sqlapi


class AdjustRatingSchemeOfChecklistItems:
    def run(self):
        sqlapi.SQLupdate(
            "cdbpcs_cl_item SET rating_scheme=( "
            "SELECT rating_scheme "
            "FROM cdbpcs_checklst "
            "WHERE cdbpcs_cl_item.cdb_project_id=cdbpcs_checklst.cdb_project_id "
            "AND cdbpcs_cl_item.checklist_id=cdbpcs_checklst.checklist_id "
            ")"
            "WHERE cdb_object_id IN ( "
            "SELECT ci.cdb_object_id "
            "FROM cdbpcs_cl_item ci "
            "JOIN cdbpcs_checklst cl "
            "ON ci.cdb_project_id=cl.cdb_project_id "
            "AND ci.checklist_id=cl.checklist_id "
            "WHERE ci.rating_scheme!=cl.rating_scheme "
            ")"
        )


pre = []
post = [AdjustRatingSchemeOfChecklistItems]
