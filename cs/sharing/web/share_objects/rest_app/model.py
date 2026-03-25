#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import re

import six
from cdb import sqlapi, ue
from cdb.objects import ByID
from cdb.objects.org import CommonRole, User

from cs.sharing.groups import (
    ObjectSharingGroup,
    PersonalSharingGroup,
    RecipientCollection,
    RecipientsBrowser,
    SharingGroup,
    SharingGroupMember,
    isUserVisible,
)

__docformat__ = "restructuredtext en"


def getRecipientClass(json):
    if "@type" not in list(json):
        raise ue.Exception("cdb_sharing_no_recipient_type", json)
    return json["@type"].rsplit("/", 1)[-1]


class NewSharingModel(object):
    def getAttachments(self, json):
        result = []

        for attachment in json["attachments"]:
            _id = attachment["cdb_object_id"]
            obj = ByID(sqlapi.quote(_id))
            if obj and obj.CheckAccess("read"):
                result.append(obj)

        if not result:
            raise ue.Exception("cdb_sharing_no_attachment")

        return result

    def getRecipients(self, json):
        result = []
        for recipient in json["recipients"]:
            classname = getRecipientClass(recipient)

            if classname == User.__classname__:
                result.append(
                    (sqlapi.quote(recipient["personalnummer"]), User.__subject_type__)
                )

            # resolve roles and recipient lists now
            elif classname == "cdb_global_role":
                role = [(recipient["role_id"], CommonRole.__subject_type__)]
                for p in RecipientCollection(subjects=role).iterPersons():
                    result.append((p.personalnummer, User.__subject_type__))

            elif classname == PersonalSharingGroup.__classname__:
                group = [
                    (recipient["cdb_object_id"], PersonalSharingGroup.__subject_type__)
                ]
                for p in RecipientCollection(subjects=group).iterPersons():
                    result.append((p.personalnummer, User.__subject_type__))

            elif classname == ObjectSharingGroup.__classname__:
                group = [
                    (recipient["cdb_object_id"], ObjectSharingGroup.__subject_type__)
                ]
                rcol = RecipientCollection(subjects=group).iterPersons(
                    self.getAttachments(json)
                )
                for p in rcol:
                    result.append((p.personalnummer, User.__subject_type__))

        if not result:
            raise ue.Exception("cdb_sharing_no_recipient")

        return result

    def getText(self, json):
        return json["message"]


class AttachmentData(object):
    __oid__ = re.compile(
        r"{0}{{8}}-{0}{{4}}-{0}{{4}}-" "{0}{{4}}-{0}{{12}}".format("[a-z0-9]")
    )
    __malformed_query__ = "cdb_sharing_malformed_query"

    def getIDsFromQuery(self, query_string):
        if query_string:
            result = six.moves.urllib.parse.parse_qs(query_string)["attachments"][
                0
            ].split(",")
            for x in result:
                if not self.__oid__.match(x):
                    raise ue.Exception(self.__malformed_query__)
            return result
        else:
            return []

    def getAttachmentAndGroups(self, theObject):
        return theObject, ObjectSharingGroup.nonEmptyForObject(theObject)

    def loadObjects(self, request):
        ids = self.getIDsFromQuery(request.query_string)
        result = []
        for oid in ids:
            obj = ByID(oid)
            if obj and obj.CheckAccess("read"):
                if obj not in result:
                    result.append(obj)
            else:
                raise ue.Exception("cdb_sharing_no_object", oid)

        return [self.getAttachmentAndGroups(o) for o in result]


class RecipientsData(object):
    @classmethod
    def getAllRecipients(cls, query, limit):
        return RecipientsBrowser.getAllPossibleRecipients(
            flat=True, query=query, limit=limit
        )


class ObjectGroupModel(object):
    def getPersons(self, group_id, attachment_id):
        group = ObjectSharingGroup.ByKeys(group_id)
        attachment = ByID(attachment_id)
        return group.getPersons([attachment])


class NewSharingGroupModel(object):
    __classmap__ = {
        "angestellter": ("personalnummer", User.__subject_type__),
        "cdb_global_role": ("role_id", CommonRole.__subject_type__),
        "cdb_personal_sharing_group": (
            "cdb_object_id",
            PersonalSharingGroup.__subject_type__,
        ),
    }

    def getEscapedName(self, name):
        return sqlapi.quote(name)

    def getEscapedSubjectList(self, recipients):
        result = []
        for recipient in recipients:
            classname = getRecipientClass(recipient)
            attrs = self.__classmap__.get(classname, None)
            if not attrs:
                raise ue.Exception("cdb_sharing_illegal_recipient", classname)

            result.append((sqlapi.quote(recipient[attrs[0]]), attrs[1]))

        return result

    def createSharingGroup(self, json):
        name = self.getEscapedName(json["name"])
        subject_list = self.getEscapedSubjectList(json["recipients"])
        return PersonalSharingGroup.fromSubjectList(name, subject_list)


class SharingGroupBaseModel(object):
    def getGroup(self, group):
        result = SharingGroup.ByKeys(sqlapi.quote(group["cdb_object_id"]))
        return result

    def getMember(self, member):
        result = SharingGroupMember.KeywordQuery(
            cdb_object_id=sqlapi.quote(member["cdb_object_id"])
        )
        if result:
            return result[0]
        return None


class GroupSizeModel(SharingGroupBaseModel):
    def getGroupSize(self, group):
        # FIXME: use vanilla SQL to make this even faster?
        if getRecipientClass(group) == "cdb_global_role":
            role = CommonRole.ByKeys(sqlapi.quote(group["role_id"]))
            return len([p for p in role.getPersons() if isUserVisible(p)])

        sharing_group = self.getGroup(group)
        return len(sharing_group.getPersons())


class ResolveModel(SharingGroupBaseModel):
    def resolveGroupToUsers(self, group, attachments=None):
        if getRecipientClass(group) == "cdb_global_role":
            role = CommonRole.ByKeys(sqlapi.quote(group["role_id"]))
            # FIXME: this is dog slow, even when using an ObjectCollection
            # from cs.platform.web.rest.generic.model import ObjectCollection
            # return ObjectCollection("person", extra_parameters={
            #     "$filter": "substringof(cdb_object_id,'%s')" % ", ".join(
            #         p.cdb_object_id for p in role.getPersons())}, rule="")
            return [p for p in role.getPersons() if isUserVisible(p)]

        sharing_group = self.getGroup(group)
        if isinstance(sharing_group, PersonalSharingGroup):
            return sharing_group.getPersons()
        else:
            return sharing_group.getPersons(attachments if attachments else [])


class GetMembersModel(SharingGroupBaseModel):
    def getGroupMembers(self, group):
        sharing_group = self.getGroup(group)
        return sharing_group.Members


class DeleteModel(SharingGroupBaseModel):
    def delete(self, json):
        if json.get("member", None):
            member = self.getMember(json["member"])
            member.CDB_Delete()
        else:
            group = self.getGroup(json["group"])
            group.CDB_Delete()


class RecipientAccessCheckModel(object):
    def check_access(self, persno, attachments):
        user = User.ByKeys(personalnummer=persno)
        return [
            {
                "cdb_object_id": attachment.cdb_object_id,
                "description": attachment.GetDescription(),
                "name": user.name,
            }
            for attachment in attachments
            if not user or not attachment.CheckAccess("read", persno=persno)
        ]

    def check_group_access(self, group, attachments):
        members = ResolveModel().resolveGroupToUsers(group, attachments)
        return [
            {
                "id": member.personalnummer,
                "result": self.check_access(member.personalnummer, attachments),
            }
            for member in members
        ]
