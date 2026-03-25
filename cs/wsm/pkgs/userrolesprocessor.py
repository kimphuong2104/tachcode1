#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import logging

from lxml import etree
from cdb import util, auth
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class UserRolesProcessor(CmdProcessorBase):
    """
    Retrieve the roles of the current user.
    """

    name = u"getuserroles"

    def call(self, resultStream, request):
        userRoles = util.get_roles("GlobalContext", "", auth.persno)
        logging.info(
            "Request roles for WSM user %s: %s", auth.persno, ", ".join(userRoles)
        )

        rolesEl = etree.Element("ROLES")
        for userRole in userRoles:
            roleEl = etree.Element("ROLE", {"name": userRole})
            rolesEl.append(roleEl)

        replyString = etree.tostring(rolesEl, encoding="utf-8")
        resultStream.write(replyString)
        return WsmCmdErrCodes.messageOk
