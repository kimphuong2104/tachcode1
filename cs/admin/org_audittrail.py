# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module audittrail

This is the documentation for the audittrail module.
"""

from __future__ import absolute_import

import six

from cdb import cdbuuid
from cdb import constants
from cdb import misc
from cdb import rte
from cdb import sig
from cdb import util
from cdb.objects.org import Person, CommonRole
from cdb._ctx import cdbserver
from cs.audittrail import AuditTrailDetail

try:
    # With CE <16 use a different hook
    START_LISTENER_HOOK = rte.USER_IMPERSONATED_HOOK
except AttributeError:
    START_LISTENER_HOOK = rte.APPLICATIONS_LOADED_HOOK

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


@six.add_metaclass(misc.Singleton)
class RoleAssignmentEventListener(util.DBEventListener):
    """
    A listener to create audit trail entries on role
    assignments
    """
    def __init__(self):
        super(RoleAssignmentEventListener, self).__init__("cdb_global_subj")

    @classmethod
    def _create_detail_entry(cls, at, old_value, new_value):
        if at:
            ti = util.tables["cdb_audittrail_detail"]
            AuditTrailDetail.CreateNoResult(
                detail_object_id=cdbuuid.create_sortable_id(),
                audittrail_object_id=at.audittrail_object_id,
                attribute_name="",
                old_value=ti.truncateForDB("old_value", old_value, "..."),
                new_value=ti.truncateForDB("new_value", new_value, "..."),
                label_de="",
                label_en="")

    @classmethod
    def _person_2_roles_changed(cls, role_id, subject_id, event):
        person = Person.ByKeys(subject_id)
        role = CommonRole.ByKeys(role_id)

        if event == util.kRecordInserted:
            if person:
                at = person.createAuditTrail("assign_role_to_person")
                cls._create_detail_entry(at, "", role_id)
            if role:
                at = role.createAuditTrail("add_role_owner_p")
                val = person.GetDescription() if person else subject_id
                cls._create_detail_entry(at, "", val)
        elif event == util.kRecordDeleted:
            if person:
                at = person.createAuditTrail("remove_role_from_person")
                cls._create_detail_entry(at, role_id, "")
            if role:
                at = role.createAuditTrail("remove_role_owner_p")
                val = person.GetDescription() if person else subject_id
                cls._create_detail_entry(at, val, "")

    @classmethod
    def _role_2_roles_changed(cls, role_id, subject_id, event):
        assigned_role = CommonRole.ByKeys(subject_id)
        role = CommonRole.ByKeys(role_id)
        if event == util.kRecordInserted:
            if assigned_role:
                at = assigned_role.createAuditTrail("add_assigned_role")
                cls._create_detail_entry(at, "", role_id)
            if role:
                at = role.createAuditTrail("add_role_owner_r")
                cls._create_detail_entry(at, "", subject_id)
        elif event == util.kRecordDeleted:
            if assigned_role:
                at = assigned_role.createAuditTrail("remove_assigned_role")
                cls._create_detail_entry(at, role_id, "")
            if role:
                at = role.createAuditTrail("remove_role_owner_r")
                cls._create_detail_entry(at, subject_id, "")

    def notify(self, relation, event):
        """
        Callback method for event notifications
        """
        # No get support in m_keys ...
        subject_type = event.m_keys["subject_type"]
        if subject_type not in (constants.kSubjectPerson,
                                constants.kCommonRole):
            # At time we do not handle assignments to exceptional roles
            return

        if event.m_event not in (util.kRecordInserted, util.kRecordDeleted):
            return

        subject_id = event.m_keys["subject_id"]
        role_id = event.m_keys["role_id"]
        if not role_id or not subject_id:
            return
        try:
            if subject_type == constants.kSubjectPerson:
                self._person_2_roles_changed(role_id, subject_id, event.m_event)
            elif subject_type == constants.kCommonRole:
                self._role_2_roles_changed(role_id, subject_id, event.m_event)
        except Exception as e:
            misc.log_traceback("Caught %s during role audit trail event" % (e))


@sig.connect(START_LISTENER_HOOK)
def activateRoleAssignmentEventListener():
    RoleAssignmentEventListener()


@sig.connect(Person, any, "pre_mask")
@sig.connect(CommonRole, any, "pre_mask")
def adjust_audittrail_url(self, ctx):
    if "audittrail_web_ctrl" not in ctx.dialog.get_attribute_names():
        return
    cdef = self.GetClassDef()
    if not cdef:
        return
    rest_name = cdef.getRESTName()
    rsdef = cdef.getRelationshipByRolename("AuditTrail")
    if not rsdef:
        return
    rs_name = rsdef.get_name()
    url = "/cs-audittrail-web?object_id={cdb_object_id}&restname={rest_name}&relshipName=AuditTrail"
    ctx.set_elink_url("cdb::argument.audittrail_web_ctrl",
                      url.format(cdb_object_id=self.cdb_object_id,
                                 rest_name=rest_name,
                                 rsname=rs_name))


@sig.connect(Person, any, "pre_mask")
@sig.connect(CommonRole, any, "pre_mask")
def skip_audittrail_reg(self, ctx):
    if ctx.action not in ["info", "modify"]:
        if isinstance(ctx, cdbserver.Context):
            ctx.disable_registers(["cs_admin_audittrail_reg"])
