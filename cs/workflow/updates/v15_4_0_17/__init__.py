# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cdb.comparch import protocol
from cs.workflow.updates.tools.revert_patches import revert_deleted_patch

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


class EnsureAccessPatches(object):
    def run(self):
        revert_deleted_patch(
            "cs.workflow",
            "cdb_relships",
            name="cdbwf_briefcase2form",
        )
        revert_deleted_patch(
            "cs.workflow",
            "cdb_rs_owner",
            name="cdbwf_briefcase2form",
            role_id="public",
        )
        sqlapi.SQLupdate(
            "cdb_op_names SET acl_allow='read' "
            "WHERE name = 'cdbwf_submit_form'"
        )
        protocol.logMessage(
            "require 'read' access to run operation 'cdbwf_submit_form'"
        )


pre = []
post = [EnsureAccessPatches]
