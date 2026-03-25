#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=C1801,W0212

"""
cs.taskmanager conditions

Conditions are modeled as `cs.workflow.conditions.CONDITION`, a
`NamedTuple` named "TasksCondition" with these attributes:

- **users**: A non-empty list of user IDs,
- **substituted**: A non-empty list of user IDs,
- **contexts**: A list of context IDs (defaults to []) to be applied
  post-SELECT and
- **condition**: An SQL condition querying for user, type and deadline

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
from collections import defaultdict, namedtuple
from datetime import date, timedelta

import cdbwrapc
from cdb import auth, sqlapi
from cdb.objects import ByID
from cs.platform.org.user import UserSubstitute
from cs.taskmanager.web.util import format_in_condition

CONDITION = namedtuple(
    "TasksCondition", ["users", "substituted", "contexts", "condition"]
)
PERSONAL_TASKS = "(subject_type IN ('', 'Person') OR subject_type IS NULL)"
ROLE_TASKS = "(subject_type NOT IN ('', 'Person'))"


def parse_date(date_string):
    try:
        import dateutil.parser

        dt = dateutil.parser.parse(sqlapi.quote(date_string))
    except (TypeError, ValueError):
        return None
    return date(dt.year, dt.month, dt.day)


def get_substitutes(absence):
    """
    :param absence: If ``True``, only return users to be substituted
        that are currently absent.
    :type absence: bool

    :returns: IDs of users currently substituted by logged-in user.
    :rtype: tuple
    """
    cdbwrapc.clearUserSubstituteCache()
    return UserSubstitute.get_substituted_users(
        auth.persno,
        absence,
    )


# public API for cs.taskmanager.mapping
def get_conditions(  # pylint: disable=too-many-arguments
    users,
    my_personal=True,
    my_roles=False,
    substitutes=True,
    absence=True,
    user_personal=True,
    user_roles=False,
    types=None,
    contexts=None,
    days=None,
    start=None,
    end=None,
):
    """
    Public API for resolving filter conditions. Used by the mapping logic.

    :param users: List of ``personalnummer`` values of explicitely-selected
        users. Note that the logged-in user does not have to be included.
    :type users: list

    :param my_personal: If ``True``, include logged-in user's personal tasks.
        Defaults to ``True``.
    :type my_roles: bool

    :param my_roles: If ``True``, include logged-in user's role tasks.
        Defaults to ``False``.
    :type my_roles: bool

    :param substitutes: If ``True``, include personal tasks of users the
        logged-in user currently substitutes. Defaults to ``True``.
    :type substitutes: bool

    :param absence: If both this and ``substitutes`` are
        ``True``, only include substituted users that are currently absent.
        Defaults to ``True``.
    :type absence: bool

    :param user_personal: If ``True``, include personal tasks of users other
        than logged-in user. Defaults to ``True``.
    :type user_personal: bool

    :param user_roles: If ``True``, include role tasks of users other than
        logged-in user. Defaults to ``False``.
    :type user_roles: bool

    :param types: List of classnames to query for.
    :type types: list

    :param contexts: List of cdb_object_ids to query for.
    :type contexts: list

    :param days: Maximum amount of days task deadlines have to match relative
        to today. May be ``None``.
    :type days: int

    :param start: ISO date string containing smallest deadline of tasks to
        query for. May be ``None``.
    :type start: str

    :param end: ISO date string containing greatest deadline of tasks to
        query for. May be ``None``.
    :type end: str

    :returns: Special condition object to be applied by mapping logic in
        :py:mod:`cs.taskmanager.mapping`.
    :rtype: :py:const:`cs.taskmanager.conditions.CONDITION`
    """

    def _user_ids(user_ids):
        return [sqlapi.quote(user_id) for user_id in user_ids]

    user_ids = list(set(_user_ids(users)).difference([auth.persno]))
    substitute_ids = _user_ids(get_substitutes(absence)) if substitutes else []

    no_tasks_condition = [
        not my_personal,
        not my_roles,
        not substitute_ids,
        not user_ids,
    ]

    if all(no_tasks_condition):
        return CONDITION([], [], {}, "1=2")

    user_conditions = [
        _get_sql_condition([auth.persno], my_personal, my_roles),
        _get_sql_condition(user_ids, user_personal, user_roles),
        _get_sql_condition(substitute_ids, True, False),
    ]

    context_condition = _get_context_condition(contexts)
    sql_condition = "(({}) AND ({}) AND ({}))".format(
        "({})".format(
            " OR ".join(
                [user_condition for user_condition in user_conditions if user_condition]
            )
        ),
        format_in_condition("classname", types) if types else "1=1",
        _get_deadline_condition(days, start, end),
    )
    return CONDITION(
        user_ids + [auth.persno], substitute_ids, context_condition, sql_condition
    )


def apply_post_select_conditions(task, contexts=None):
    # if any value in task_row values is of the same type as a context,
    # but has a different UUID, return None
    # contexts is either falsy or a dict {classname: list of keydicts}

    if not task:
        return False

    if not contexts:
        return True

    from cs.taskmanager.conf import get_cache

    filterable_classes = get_cache().context_classnames

    _callable = getattr(task, "getCsTasksContexts", None)
    task_contexts = (_callable() or []) if _callable else []

    for task_context in task_contexts:
        if task_context:
            task_context_class = task_context.GetClassname()
            if task_context_class in filterable_classes:
                for context_keys in contexts.get(task_context_class, []):
                    if task_context._key_dict() == context_keys:
                        return True
            else:
                logging.error(
                    "class is missing in cs_tasks_context: '%s'",
                    task_context_class,
                )

    return False


def _get_context_condition(contexts=None):
    result = defaultdict(list)

    for context_object_id in contexts or []:
        context = ByID(context_object_id)
        if context and context.CheckAccess("read"):
            result[context.GetClassname()].append(context._key_dict())
        else:
            logging.error("unknown context: '%s'", context_object_id)

    return result


def _get_sql_condition(user_ids, personal, roles):
    if not user_ids:
        return None

    filter_condition = "{}{}".format(
        int(personal),
        int(roles),
    )

    if filter_condition == "00":
        return None

    personal_condition = format_in_condition(
        "persno",
        user_ids,
    )

    if filter_condition == "11":
        return personal_condition

    additional = ROLE_TASKS if filter_condition == "01" else PERSONAL_TASKS  # 10
    return "({})".format(
        " AND ".join(
            [
                personal_condition,
                additional,
            ]
        )
    )


def _get_deadline_condition(days=None, start=None, end=None):
    def _condition(date_obj, operator):
        return "deadline {} {}".format(
            operator,
            sqlapi.SQLdate_literal(date_obj),
        )

    try:
        days = int(days)
    except (TypeError, ValueError):
        days = None

    start_date = parse_date(start)
    end_date = parse_date(end)

    conditions = []

    if days is not None:
        max_deadline = date.today() + timedelta(days=days + 1)
        conditions.append(_condition(max_deadline, "<"))

    if start_date:
        conditions.append(_condition(start_date, ">="))

    if end_date:
        after_end = end_date + timedelta(days=1)
        conditions.append(_condition(after_end, "<"))

    if conditions:
        return "({})".format(" AND ".join(conditions))

    return "1=1"
