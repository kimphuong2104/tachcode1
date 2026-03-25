#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import pytest

from cs.pcs.projects.common import sharing


def get_mock_with_classdef(classname, *base_classes):
    obj = mock.Mock()
    obj.GetClassDef.return_value.getClassname.return_value = classname
    obj.GetClassDef.return_value.getBaseClassNames.return_value = base_classes
    return obj


def test_is_project():
    "[is_project]"
    project = get_mock_with_classdef("cdbpcs_project")
    project_subclass = get_mock_with_classdef("foo", "bar", "cdbpcs_project")
    no_project = get_mock_with_classdef("foo", "bar")
    result = [
        sharing.is_project(project),
        sharing.is_project(project_subclass),
        sharing.is_project(no_project),
    ]
    assert result == [True, True, False]


@pytest.mark.parametrize(
    "classname,subject",
    [
        ("cdbpcs_project", "bar"),
        ("whatever", "Project.bar"),
    ],
)
def test_getProjectSubjects(classname, subject):
    "[WithSharingAndProjectRoles._getProjectSubjects]"
    obj = get_mock_with_classdef(classname)

    direct_role = mock.Mock()
    direct_role.getPersons.return_value = [mock.Mock(personalnummer="bar")]
    obj.RolesByID = {"foo": direct_role}

    indirect_role = mock.Mock()
    indirect_role.getPersons.return_value = [mock.Mock(personalnummer="Project.bar")]
    obj.Project.RolesByID = {"foo": indirect_role}

    with mock.patch.object(sharing, "RecipientCollection") as RC:
        result = sharing.WithSharingAndProjectRoles._getProjectSubjects(obj, "foo")
    assert result == RC.return_value.subjects
    RC.assert_called_once_with(subjects=[(subject, "Person")])


def test_getProjectSubjects_no_project():
    "[WithSharingAndProjectRoles._getProjectSubjects] no project"
    obj = get_mock_with_classdef("whatever")
    obj.Project = None

    result = sharing.WithSharingAndProjectRoles._getProjectSubjects(obj, "foo")
    assert result == []


def test_getProjectManagerSubjects():
    "[WithSharingAndProjectRoles.getProjectManagerSubjects]"
    obj = mock.Mock()
    result = sharing.WithSharingAndProjectRoles.getProjectManagerSubjects(obj, None)
    assert result == obj._getProjectSubjects.return_value
    obj._getProjectSubjects.assert_called_once_with("Projektleiter")


def test_getProjectMemberSubjects():
    "[WithSharingAndProjectRoles.getProjectMemberSubjects]"
    obj = mock.Mock()
    result = sharing.WithSharingAndProjectRoles.getProjectMemberSubjects(obj, None)
    assert result == obj._getProjectSubjects.return_value
    obj._getProjectSubjects.assert_called_once_with("Projektmitglied")
