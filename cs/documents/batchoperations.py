#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# pylint: disable=bad-continuation

from cdb import ue, workflow
from cdb.platform import gui
from cs.tools.batchoperations import BatchOperation, ObjectAssignment


class BatchOperationDocumentAssignment(ObjectAssignment):
    __maps_to__ = "cdbbop_doc_asgn"


class DocumentStateChangeImpl(BatchOperation):
    """Sammelstatuswechsel fuer Dokumente"""

    __match__ = (
        BatchOperation.type_id == "zeichnung"
        and BatchOperation.operation == "DocStateChange"
    )

    def init(self, params):
        def to_int(s, default):
            try:
                return int(s)
            except ValueError:
                return default

        self.recursive = to_int(params["param3"], 0)
        self.unlock_document = to_int(params["param4"], 0)
        self._in_recursion = False
        self.err_msg = ""
        self.target_state = to_int(params["param1"], None)
        if self.target_state is None:
            raise ue.Exception("cdb_konfstd_013")

    def perform_action(  # pylint: disable=inconsistent-return-statements
        self, doc, session
    ):
        if not doc:
            return "Document does not exist."
        if doc.status == self.target_state:
            return

        if self.recursive and not self._in_recursion:
            self._in_recursion = True
            all_docs = doc.resolveReferencedDocuments()
            all_docs.reverse()
            for d in all_docs:
                doc_desc = d.GetDescription()
                session.log(doc_desc + "\n")
                _info_str, msg = self._call("perform_action", d, session)
                if msg:
                    self.err_msg += doc_desc + "\n" + msg + "\n"
            self._in_recursion = False

        if not doc.IsValidInteractiveTargetStatus(self.target_state):
            return gui.Message.GetMessage("workflow_no_auth")

        if self.unlock_document:
            unlock = workflow.kUnlockIfGranted
        else:
            unlock = workflow.kNoUnlock

        doc.ChangeState(self.target_state, unlock=unlock)

        if self.recursive and not self._in_recursion:
            err = self.err_msg
            self.err_msg = ""
            return err
