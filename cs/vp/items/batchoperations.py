#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import ue

from cs.tools.batchoperations import BatchOperation
from cs.tools.batchoperations import ObjectAssignment


class BatchOperationItemAssignment(ObjectAssignment):
    __maps_to__ = "cdbbop_item_asgn"


class PartStateChangeImpl(BatchOperation):
    """ batch status change for parts """

    __match__ = BatchOperation.type_id == 'teile_stamm' and BatchOperation.operation == 'PartStateChange'

    def init(self, params):
        def to_int(s, default):
            try:
                return int(s)
            except Exception:
                return default
        self.target_state = to_int(params["param1"], None)
        if self.target_state is None:
            raise ue.Exception("cdb_konfstd_013")
        self.recursive = to_int(params["param3"], 0)

    def change_state(self, item, session):
        if hasattr(item, "stateChangeAllowed"):
            if item.stateChangeAllowed(self.target_state, False):
                item.ChangeState(self.target_state)
            else:
                from cdb.platform.gui import Message
                return Message.GetMessage("authorization16")
        else:
            item.ChangeState(self.target_state)

    def perform_action(self, item, session):
        err_msg = ""

        from cs.vp.items import visit_dfs
        if not item:
            return "Item does not exist."
        if item.status == self.target_state:
            return

        if self.recursive:
            visited = []
            for comp in visit_dfs(item):
                i = comp.Item
                if i.cdb_object_id not in visited:
                    _, msg = self._call("change_state", i, session)
                    if msg:
                        err_msg += i.GetDescription() + "\n" + msg + "\n"
                    visited.append(i.cdb_object_id)

        _, msg = self._call("change_state", item, session)
        if msg:
            err_msg = "%s%s" % (msg, err_msg)

        return err_msg
