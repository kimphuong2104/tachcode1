#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import

from cdb import auth

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.filereplication import FileReplication


class PostBlobDownProcessor(CmdProcessorBase):
    """
    Called after blobs were transferred to client (as part of any checkoutRevision with file download).
    """

    name = u"postblobdown"

    def call(self, resultStream, request):

        # clean up file replication groups
        user = auth.persno
        mac_address = self._rootElement.mac_address
        windows_session_id = self._rootElement.windows_session_id
        repl = FileReplication(user, mac_address, windows_session_id)
        repl.cleanUp()

        return WsmCmdErrCodes.messageOk
