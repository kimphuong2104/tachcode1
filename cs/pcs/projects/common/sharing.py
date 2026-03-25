#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines,protected-access

from cs.sharing.groups import RecipientCollection
from cs.sharing.share_objects import WithSharing


def is_project(obj):
    classdef = obj.GetClassDef()
    classnames = [classdef.getClassname()] + list(classdef.getBaseClassNames())
    return "cdbpcs_project" in classnames


class WithSharingAndProjectRoles(WithSharing):
    """
    Base your class on this one instead of ``cs.sharing.sharing_objects.WithSharing``
    if you want to support the object sharing groups "Project Managers"
    and "Project Members".

    Requires a ``Reference`` of cardinality 1 named "Project".
    """

    def _getProjectSubjects(self, role_name):
        if is_project(self):
            project = self
        else:
            project = getattr(self, "Project", None)
        if project:
            role = project.RolesByID[role_name]
            if role:
                role_members = [(p.personalnummer, "Person") for p in role.getPersons()]
                return RecipientCollection(subjects=role_members).subjects
        return []

    def getProjectManagerSubjects(self, _):
        "support for ObjectSharingGroup 'Project Managers'"
        return self._getProjectSubjects("Projektleiter")

    def getProjectMemberSubjects(self, _):
        "support for ObjectSharingGroup 'Project Members'"
        return self._getProjectSubjects("Projektmitglied")
