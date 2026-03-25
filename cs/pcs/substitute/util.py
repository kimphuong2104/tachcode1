# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
cs.pcs.substitute.util
======================

Utility functions for "Manage Substitutes" web application.

.. autofunction :: register_role_context

.. autofunction :: get_role_context

.. autofunction :: get_role_contexts

.. autofunction :: get_org_context_attributes

"""

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

__all__ = [
    "register_role_context",
    "get_role_context",
    "get_role_contexts",
    "get_org_context_attributes",
]

from collections import namedtuple
from datetime import date

import dateutil.parser
from cdb import sqlapi
from cdb.objects import ClassRegistry
from cdbwrapc import CDBClassDef
from cs.platform.web.root import get_v1

from cs.pcs.helpers import is_feature_licensed

# role contexts
SubjectClasses = namedtuple(
    "SubjectClasses",
    [
        "role_classname",
        "role_class",
        "subject_class",
        "cdb_classname",
        "context_attr",
    ],
)
ROLE_CONTEXTS = {}
GLOBAL_ORG_CONTEXT_ATTRIBUTES = {"cdb_global_role": {}}


def is_substitute_licensed():
    return is_feature_licensed(["ORG_010"])


def register_role_context(role_classname, subject_per_classname, context_attr):
    """
    Registers given values for assigning roles of that class to users from
    within the application:

    .. code-block :: python

        from cdb import rte, sig
        from cs.pcs.substitute.util import register_role_context

        @sig.connect(rte.APPLICATIONS_LOADED_HOOK)
        def _register_role_contexts():
            register_role_context(
                "cdb_global_role",
                "cdb_global_subject",
                None
            )
            register_role_context(
                "cdbpcs_prj_role",
                "cdbpcs_subject_per",
                "cdb_project_id"
            )

    .. note ::
        `register_role_context` should be called when
        `cdb.rte.APPLICATIONS_LOADED_HOOK` is emitted. Registering the same
        context multiple times is allowed, subsequent calls will overwrite
        prior calls with the same first argument (``role_classname``).

    This data can then be retrieved from the global registry using
    `get_role_context` (to get a single entry) or `get_role_contexts` (to get
    all entries).

    :param role_classname: Classname of role class.
    :type role_classname: basestring

    :param subject_per_classname: Classname of class for subject assignments
        to users for given ``role_classname``.
    :type subject_per_classname: basestring

    :param context_attr: Attribute name containing the org. context ID. May be
        ``None`` for the global context only.
    :type context_attr: basestring

    :raises cdb.ElementsError: If no ``cdb.objects`` class is found for
        ``role_classname`` or ``role_classname`` is no string.
    """
    cdef = CDBClassDef(role_classname)
    role_class = ClassRegistry().find(cdef.getPrimaryTable())
    subject_class = role_class.__subject_assign_cls__

    data = SubjectClasses(
        role_classname, role_class, subject_class, subject_per_classname, context_attr
    )

    ROLE_CONTEXTS[role_classname] = data


def get_role_context(role_classname):
    """
    Returns role context information as a named tuple
    :py:const:`cs.pcs.substitute.util.SubjectClasses`:

    +-----+---------------------------+--------------------------------------+
    | Pos | Attribute                 | Value Description                    |
    +=====+===========================+======================================+
    | 0   | ``role_classname``        | ``role_classname`` as given          |
    +-----+---------------------------+--------------------------------------+
    | 1   | ``role_class``            | The `cdb.objects` role class         |
    +-----+---------------------------+--------------------------------------+
    | 2   | ``subject_class``         | The `cdb.objects` role assignment    |
    |     |                           | class                                |
    +-----+---------------------------+--------------------------------------+
    | 3   | ``subject_per_classname`` | The `cdb_classname` for role         |
    |     |                           | assignments to users                 |
    +-----+---------------------------+--------------------------------------+
    | 4   | ``context_attr``          | The attribute name containing the    |
    |     |                           | org. context ID                      |
    +-----+---------------------------+--------------------------------------+

    :param role_classname: Classname of role class.
    :type role_classname: basestring

    :returns: Named tuple "SubjectClasses", for given ``role_classname``
        (details see above).
    :rtype: :py:const:`cs.pcs.substitute.util.SubjectClasses`

    :raises KeyError: If ``role_classname`` is not registered (see
        `register_role_context`).

    .. rubric :: Example result

    .. code-block :: python

        from cdb.objects import org
        from cs.pcs.substitute import util

        util.get_role_context("cdb_global_role") == util.SubjectClasses(
            role_classname='cdb_global_role',
            role_class=org.CommonRole,
            subject_class=org.CommonRoleSubject,
            cdb_classname='cdb_global_subject',
            context_attr=None
        )
    """
    return ROLE_CONTEXTS[role_classname]


def get_role_contexts():
    """
    :returns: All registered role contexts indexed by role classnames (see
        `get_role_context` for details on role context data).
    :rtype: dict
    """
    return ROLE_CONTEXTS


def get_org_context_attributes(org_contexts):
    """
    Handles org. context data (attributes and values indexed by role
    classnames). This data can be used to identify up to one org. context
    object per role classname.

    :param org_contexts: Org. context data for non-global contexts.
    :type org_contexts: dict

    :returns: Org. context data as given, but extended to include the global
        context.
    :rtype: dict

    .. rubric :: Example ``org_contexts`` and result

    .. code-block :: python

        from cs.pcs.substitute import util
        org_contexts = {
            "cdbpcs_prj_role": {"cdb_project_id": "P00033"}
        }
        util.get_org_context_attributes(org_contexts) == {
            "cdbpcs_prj_role": {
                "cdb_project_id": "P00033",
            },
            "cdb_global_role": {}
        }
    """
    result = dict(org_contexts) if org_contexts else {}
    result.update(GLOBAL_ORG_CONTEXT_ATTRIBUTES)
    return result


# conversion helpers
def get_rest_objects(objs, request):
    collection_app = get_v1(request).child("collection")
    return [
        request.view(obj, app=collection_app) for obj in objs if obj.CheckAccess("read")
    ]


def get_rest_types(objs, request):
    collection_app = get_v1(request).child("class")
    return [request.view(obj, app=collection_app) for obj in objs]


def ISOStringToDate(date_string):
    try:
        dt_object = dateutil.parser.parse(sqlapi.quote(date_string))
    except (TypeError, ValueError):
        return None

    return datetimeToDate(dt_object)


def datetimeToISOString(datetime_object):
    if datetime_object:
        return str(datetime_object.isoformat())
    return None


def datetimeToDate(dt_object, default_value=None):
    if dt_object:
        return date(dt_object.year, dt_object.month, dt_object.day)
    return default_value


# misc
MIN_ORDINAL = 1
MAX_ORDINAL = 3652059


def substitute_sort_key(sub):
    """
    Calculates a sort key for user substitutes to sort by

    1. Ascending ``period_start`` (``None`` first)
    2. Descending ``period_end`` (``None`` first)

    This sort order is used to calculate if a person is fully substituted in a
    given observation period.

    :param sub: The substitute object to calculate the sort key for.
    :type sub: `cs.platform.org.user.UserSubstitute`

    :returns: Sort key for substitutes; first the ordinal of the start date
        (``None`` becomes ``1``), then the additive inverse of the end date's
        ordinal (``None`` becomes the lowest possible ordinal).
    :rtype: tuple
    """

    return (
        sub.period_start.toordinal() if sub.period_start else MIN_ORDINAL,
        -sub.period_end.toordinal() if sub.period_end else -MAX_ORDINAL,
    )
