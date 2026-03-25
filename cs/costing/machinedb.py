#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
from cdb import util
from cs.audittrail import WithAuditTrail
from cdb.objects import Object
from cdb.objects import State
from cdb.platform import olc
from cdb.objects import operations
from cdb.objects import Reference_N
from cdb.objects import Forward

fMachine = Forward(__name__ + ".Machine")


class Machine(Object, WithAuditTrail):
    __maps_to__ = "cdbpco_machine_db"
    __classname__ = "cdbpco_machine_db"

    OtherVersions = Reference_N(fMachine,
                                fMachine.m_id == fMachine.m_id,
                                fMachine.m_index != fMachine.m_index)

    PreviousVersions = Reference_N(fMachine,
                                   fMachine.m_id == fMachine.m_id,
                                   fMachine.m_index < fMachine.m_index,
                                   order_by=fMachine.m_index)

    event_map = {
        ('cdbpco_new_revision', 'now'): 'create_index',
        ('delete', 'post'): 'delete_machinedb',
        ('create', 'pre'): 'create_id'
    }

    class DRAFT(State):
        status = 0

    class REVIEW(State):
        status = 100

    class BLOCKED(State):
        status = 170

        def post(state, self, ctx):  # @NoSelf
            self.active = 0

    class OBSOLETE(State):
        status = 180

        def post(state, self, ctx):  # @NoSelf
            self.active = 0

    class REVISION(State):
        status = 190

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(Machine.RELEASED.status)
                ctx.excl_state(Machine.OBSOLETE.status)
            super(Machine.REVISION, state).pre_mask(self, ctx)

    class RELEASED(State):
        status = 200

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(Machine.REVISION.status)
            super(Machine.RELEASED, state).pre_mask(self, ctx)

        def post(state, self, ctx):  # @NoSelf
            self.active = 1
            if len(self.PreviousVersions):
                if self.PreviousVersions[-1].status == Machine.REVISION.status:
                    self.PreviousVersions[-1].ChangeState(Machine.OBSOLETE.status)

    def create_index(self, ctx):
        if self.OtherVersions and max(self.OtherVersions.m_index) > self.m_index:
            new_index = max(self.OtherVersions.m_index) + 1
        else:
            new_index = self.m_index + 1

        def init_status_machinedb(m_index, schema_object_id):
            return {"status": 0,
                    "m_index": m_index,
                    "cdb_status_txt": olc.StateDefinition.ByKeys(0, "cdbpco_machine_db").StateText[''],
                    "schema_object_id": schema_object_id}

        schema_object_id = self.schema_object_id
        if "schema_object_id" in ctx.dialog.get_attribute_names():
            schema_object_id = ctx.dialog.schema_object_id
        new_db = operations.operation("CDB_Copy", self, **init_status_machinedb(new_index, schema_object_id))
        if new_db:
            self.ChangeState(Machine.REVISION.status)

    def delete_machinedb(self, ctx):
        if self.PreviousVersions:
            last_one = self.PreviousVersions[-1]
            if last_one.status == Machine.REVISION.status:
                last_one.ChangeState(Machine.RELEASED.status)

    def create_id(self, ctx):
        if self.m_id == "#":
            self.m_id = "M%08d" % util.nextval('cdbpco_machine_db')
