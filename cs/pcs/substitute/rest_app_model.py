#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
cs.pcs.substitute.rest_app_model
================================

Model classes for the REST application of ``cs.pcs.substitute``.

.. autoclass :: SubstitutionInfoModel
    :members: getProjectTeamMembers, getInfo, isFullySubstituted

.. autoclass :: RoleComparisonModel
    :members: getAllRoles

.. autoclass :: SubjectModel
    :members: setOrgContext, unassignRole, assignRole
"""

import logging
from collections import namedtuple
from datetime import date

import webob
from cdb import ElementsError, constants, util
from cdb.objects.operations import operation
from cdb.objects.org import Person
from cs.platform.org.user import UserSubstitute
from cs.platform.web.rest.support import rest_object, values_from_rest_key

from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects import Project
from cs.pcs.substitute.util import (
    ISOStringToDate,
    datetimeToDate,
    get_org_context_attributes,
    get_rest_objects,
    get_role_context,
    get_role_contexts,
    substitute_sort_key,
)

MIN_DATE = date(1, 1, 1)
MAX_DATE = date(9999, 12, 31)
DateRange = namedtuple("DateRange", ["start", "end"])


def getSubstitutesInPeriod(persno, fromDate, toDate):
    """
    Wrapper for
    :py:func`cs.platform.org.user.UserSubstitute.get_substitutes_in_period`
    that works with date strings in ISO format instead of ``datetime``
    objects.

    :param persno: ID of user to find substitutes for.
    :type persno: basestring

    :param fromDate: Start of query period as ISO date string.
    :type fromDate: basestring

    :param endDate: End of query period as ISO date string.
    :type endDate: basestring

    :returns: The user substitutes for ``persno`` in the given period.
    :rtype: :py:class`cdb.objects.references.ObjectCollection` of
        :py:class`cs.platform.org.user.UserSubstitute`
    """
    substitutes = UserSubstitute.get_substitutes_in_period(
        persno, ISOStringToDate(fromDate), ISOStringToDate(toDate)
    )
    return substitutes


class ProjectTeamModel:
    def __init__(self, rest_key):
        object_keys = values_from_rest_key(rest_key)
        kwargs = {"cdb_project_id": object_keys[0], "ce_baseline_id": ""}
        project = get_and_check_object(Project, "read", **kwargs)

        if project is None:
            raise webob.exc.HTTPNotFound()

        self.cdb_project_id = object_keys[0]
        self.project = project

    def getProjectTeamMembers(self):
        return [member.Person for member in self.project.TeamMembers]


class UserSubstitutesModel:
    def __init__(self, persno):
        self.user = rest_object(Person, persno)
        self.persno = self.user.personalnummer

        if not (self.user and self.user.CheckAccess("read")):
            raise webob.exc.HTTPNotFound()

    def getUserSubstitutes(self, fromDate, toDate):
        substitutes = getSubstitutesInPeriod(self.persno, fromDate, toDate)
        user_ids = set(substitutes.personalnummer).union(substitutes.substitute)
        users = [
            user
            for user in Person.KeywordQuery(personalnummer=user_ids)
            if user.CheckAccess("read")
        ]
        return substitutes, users


class SubstitutionInfoModel:
    def __init__(self, cdb_project_id):
        self.team_model = ProjectTeamModel(cdb_project_id)

    def getProjectTeamMembers(self):
        return self.team_model.getProjectTeamMembers()

    @classmethod
    def getInfo(cls, users, fromDate, toDate):
        """
        :param users: Person REST objects
        :type users: list

        :param fromDate: ISO date string indicating the start of the date
            range to consider, ``None`` meaning "today".
        :type fromDate: basestring

        :param toDate: ISO date string indicating the end of the date range to
            consider, ``None`` meaning "never".
        :type toDate: basestring

        :returns: Bools indexed by each entry's ``@id`` in ``users``. The bool
            indicates whether that user is fully substituted in the given date
            range (see `isFullySubstituted`).
        :rtype: dict
        """
        return {
            user["@id"]: cls.isFullySubstituted(
                user["personalnummer"], fromDate, toDate
            )
            for user in users
        }

    @classmethod
    def isFullySubstituted(cls, persno, fromDate, toDate):
        """
        Determine if substitute entries for user identified by ``self.persno``
        completely cover the date range given by ``fromDate`` to ``toDate``.
        Either may be ``None``, representing an unbounded date range. If
        ``fromDate`` is ``None`` or earlier than today, today's date will be
        used instead.

        :param persno: ID of user to get information for.
        :type persno: basestring

        :param fromDate: ISO date string indicating the start of the date
            range to consider. If ``fromDate`` is ``None`` or earlier than
            today, today's date will be used instead.
        :type fromDate: basestring

        :param toDate: ISO date string indicating the end of the date range to
            consider, ``None`` meaning "never".
        :type toDate: basestring

        :returns: ``True`` if given date range is covered by substitute
            entries, otherwise ``False``
        :rtype: bool
        """
        sub_model = UserSubstitutesModel(persno)
        substitutes = getSubstitutesInPeriod(sub_model.persno, fromDate, toDate)
        # sort substitutes so we can determine in a single pass if user is
        # fully substituted in period
        # cannot use kwargs with ObjectCollection.sort because of _wrapX,
        # so use positional arg for "key"
        substitutes.sort(key=substitute_sort_key)
        fromDate = ISOStringToDate(fromDate)
        toDate = ISOStringToDate(toDate)

        if toDate is None:
            if not substitutes.KeywordQuery(period_end=None):
                return False

        today = date.today()

        if toDate and toDate < today:
            return True

        if fromDate is None:
            fromDate = today
        else:
            fromDate = max(fromDate, today)

        remaining = DateRange(start=fromDate, end=toDate)

        sub_ranges = [
            DateRange(
                start=datetimeToDate(s.period_start, MIN_DATE),
                end=datetimeToDate(s.period_end, MAX_DATE),
            )
            for s in substitutes
        ]

        for sub in sub_ranges:
            if sub.start > remaining.start:
                return False

            if remaining.end is None or sub.end >= remaining.end:
                return True

            # tuple is immutable - effectively set remaining.start to sub.end
            remaining = DateRange(start=sub.end, end=toDate)

        return False


class RoleComparisonModel:
    """
    Handles getting roles for both a user and their substitute based on a
    single `cs.platform.org.user.UserSubstitute` object.
    """

    def __init__(self, substitute_oid, org_contexts=None):
        """
        :param substitute_oid: ``cdb_object_id`` of the
            `cs.platform.org.user.UserSubstitute` object.
        :type substitute_oid: basestring

        :param org_contexts: Org. context data. Will always handle global
            context, if not given or ``None``, will _only_ handle the global
            context. See `cs.pcs.substitute.util.get_org_context_attributes`
            for details.
        :type org_contexts: dict
        """
        kwargs = {"cdb_object_id": substitute_oid}
        substitute = get_and_check_object(UserSubstitute, "read", **kwargs)
        if substitute is None:
            raise webob.exc.HTTPNotFound()

        self.substitute_oid = substitute_oid
        self.substitute = substitute

        self.user = self.substitute.personalnummer
        self.substituted = self.substitute.substitute

        self.org_contexts = get_org_context_attributes(org_contexts)
        self.role_contexts = get_role_contexts()

    def _get_roles_by_subject_query(self, query, role_context):
        _query = dict(query)

        if role_context.context_attr:
            context = self.org_contexts[role_context.role_classname]
            _query[role_context.context_attr] = context[role_context.context_attr]
            role_query = {role_context.context_attr: context[role_context.context_attr]}
        else:
            role_query = {}

        subjects = role_context.subject_class.KeywordQuery(**_query)
        role_query["role_id"] = subjects.role_id

        return role_context.role_class.KeywordQuery(**role_query)

    def _get_context_roles_by_inverted_subject_query(self, query_str, role_context):
        """
        :param query_str: Query string identifying subjects
            (role assignments) for the given context.
        :type query_str: basestring

        :param role_context: Role context info object.
        :type role_context: See `cs.pcs.substitute.util.get_role_context` for
            details.

        :returns: All roles of the given context
            where no subject exists for the given query string.

        :raises KeyError: If it is not called/used in project context.
            This method is called only by
            RoleComparisonModel._getUnassignedContextRoles().

        :rubric: Usage example

            _get_context_roles_by_inverted_subject_query(
                query_str = (
                    "subject_id IN ('{}', '{}') "
                    "AND subject_type='{}'".format(
                    user,
                    substituted,
                    Person.__subject_type__,
                ),
                role_context
        )
        """
        context = self.org_contexts[role_context.role_classname]
        context_query_str = (
            f"{role_context.context_attr}='{context[role_context.context_attr]}'"
        )

        subject_query_str = f"{query_str} AND {context_query_str}"
        subjects = role_context.subject_class.Query(subject_query_str)
        in_clause = "', '".join(subjects.role_id)
        role_query_str = f"role_id NOT IN ('{in_clause}') AND {context_query_str}"

        return role_context.role_class.Query(role_query_str, access="read")

    def _getContextRolesByPersno(self, persno, role_context):
        """
        :param persno: ID of the user to get roles for.
        :type persno: basestring

        :param role_context: Role context info object.
        :type role_context: See `cs.pcs.substitute.util.get_role_context` for
            details.

        :returns: All roles of user identified by ``persno`` for given
            ``role_context``. Identification of concrete org. contexts uses
            ``self.org_contexts``.
        :rtype: `cdb.objects.references.ObjectCollection`

        .. note ::
            This does intentionally not respect nested role assignments like
            `cdb.util.get_roles` does, only roles directly assigned to the
            user.
        """
        subject_query = {
            "subject_id": persno,
            "subject_type": Person.__subject_type__,
        }

        result = self._get_roles_by_subject_query(subject_query, role_context)
        return result

    def _getRolesByPersno(self, persno):
        """
        :param persno: ID of the user to get roles for.
        :type persno: basestring

        :returns: All roles of user identified by ``persno`` for all contexts
            in ``self.org_contexts``.
        :rtype: list

        .. note ::
            This does intentionally not respect nested role assignments like
            `cdb.util.get_roles` does, only roles directly assigned to the
            user.
        """
        result = []

        for role_classname in self.org_contexts:
            role_context = self.role_contexts[role_classname]
            result += self._getContextRolesByPersno(persno, role_context)

        return result

    def _getUnassignedContextRoles(self):
        result = []
        subject_query_str = (
            f"subject_id IN ('{self.user}', '{self.substituted}') "
            f"AND subject_type='{Person.__subject_type__}'"
        )

        for role_classname in self.org_contexts:
            role_context = self.role_contexts[role_classname]

            if role_context.context_attr:
                result += self._get_context_roles_by_inverted_subject_query(
                    subject_query_str, role_context
                )
            # else ignore global context

        return result

    def getAllRoles(self, request):
        """
        :param request: The morepath request. Used for serializing results to
            JSON.

        :returns: All global roles of user and substitute referenced by
            ``self.substitute`` and all context roles in of contexts
            ``self.org_contexts`` (regardless of user assignments).
        :rtype: dict

        Example result:

        .. code-block :: python

            result = {
                "objects": [
                    {
                        "@id": "http://localhost/api/v1/collection/person/s",
                        "system:description": "Substitute",
                    },
                    {
                        "@id": "http://localhost/api/v1/collection/person/u",
                        "system:description": "Person",
                    },
                ],
                "userRoleIDs": [
                    "http://localhost/api/v1/collection/person/u",
                ],
                "substituteRoleIDs": [
                    "http://localhost/api/v1/collection/person/s",
                ],
            }

        .. warning ::
            Will locally reload role caches each time it is called.

        .. note ::
            This does intentionally not respect nested role assignments like
            `cdb.util.get_roles` does, only roles directly assigned to the
            user.
        """
        util.reload_cache(util.kCGRoleCaches, util.kLocalReload)

        def get_rest_ids(rest_objects):
            return [r["@id"] for r in rest_objects]

        def get_type_designation(role_classes):
            return {
                role_class.getClassname(): role_class.getDesignation()
                for role_class in role_classes
            }

        user_roles = self._getRolesByPersno(self.user)
        substituted_roles = self._getRolesByPersno(self.substituted)
        context_roles = self._getUnassignedContextRoles()

        user_roles_rest = get_rest_objects(user_roles, request)
        substituted_roles_rest = get_rest_objects(substituted_roles, request)
        context_roles_rest = get_rest_objects(context_roles, request)

        role_classes = [
            role_context.role_class().GetClassDef()
            for role_context in self.role_contexts.values()
        ]

        return {
            "objects": (user_roles_rest + substituted_roles_rest + context_roles_rest),
            "types": get_type_designation(role_classes),
            "userRoleIDs": get_rest_ids(user_roles_rest),
            "substituteRoleIDs": get_rest_ids(substituted_roles_rest),
        }


class SubjectModel:
    def __init__(self, role_classname, role_id, persno):
        """
        :param role_classname: Role classname
        :type role_classname: basestring

        :param role_id: Role ID
        :type role_id: basestring

        :param persno: Person ID
        :type persno: basestring
        """
        try:
            self.role_context = get_role_context(role_classname)
        except KeyError as exc:
            raise webob.exc.HTTPNotFound() from exc

        self.vals = {
            "cdb_classname": self.role_context.cdb_classname,
            "role_id": role_id,
            "subject_id": persno,
            "subject_type": Person.__subject_type__,
            "exception_id": "",
        }

    def setOrgContext(self, org_context):
        """
        Extends ``self.vals`` with given ``org_context``. Not used in the
        constructor for simplified and unified URLs.

        :param org_context: Org. context data for given ``role_classname``
            only. Defaults to ``None``, which is suitable for the global
            context. See `cs.pcs.substitute.util.get_org_context_attributes`
            for details.
        :type org_context: dict
        """
        self.vals.update(org_context)

    def unassignRole(self):
        """
        Delete subject identified by ``self.vals`` using core operation
        ``CDB_Delete``. Ignore missing subject, as the desired result has
        already been achieved.

        :raises webob.exc.HTTPBadRequest: If operation fails.
        :raises webob.exc.HTTPForbidden: If ``self.vals`` identifies multiple
            subjects.
        """
        subject_class = self.role_context.subject_class
        subjects = subject_class.KeywordQuery(**self.vals)

        if not subjects:
            logging.info("found 0 role assignments for values %s", self.vals)
            # ignore the fact the role was not assigned in the first place
        elif len(subjects) == 1:
            try:
                operation(constants.kOperationDelete, subjects[0])
            except ElementsError as error:
                logging.exception(
                    "could not delete role assignment %s",
                    self.vals,
                )
                raise webob.exc.HTTPBadRequest(str(error)) from error
        else:
            logging.error(
                "found %s role assignments for values %s",
                len(subjects),
                self.vals,
            )
            raise webob.exc.HTTPForbidden("multiple objects found")

    def assignRole(self):
        """
        Create subject identified by ``self.vals`` using core operation
        ``CDB_Create``. Ignore already existing subject, as the desired result
        has already been achieved.

        :raises webob.exc.HTTPBadRequest: If operation fails.
        """
        subject_class = self.role_context.subject_class

        if hasattr(subject_class, "subject_id2"):
            self.vals["subject_id2"] = ""

        subjects = subject_class.KeywordQuery(**self.vals)

        if subjects:
            logging.info("already found role assignment for values %s", self.vals)
            # ignore the fact the role was already assigned
        else:
            try:
                operation(
                    constants.kOperationNew,
                    self.role_context.cdb_classname,
                    **self.vals,
                )
            except ElementsError as error:
                logging.exception(
                    "could not assign role %s",
                    self.vals,
                )
                raise webob.exc.HTTPBadRequest(str(error)) from error
