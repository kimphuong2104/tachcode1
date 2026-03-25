#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
from itertools import combinations

from cdb import ElementsError, misc
from cdb.cmsg import Cdbcmsg
from cdb.constants import kOperationShowObject
from cdb.objects.iconcache import IconCache, _LabelValueAccessor
from cs.platform.web.rest.generic.convert import dump_value
from cs.platform.web.rest.support import _REPLACEMENTS

SYSTEM_LINK_PATTERN = "{base}/info/{restName}/{restKey}"


def get_object_icon(obj, cdef):
    icon_id = cdef.getObjectIconId()
    return IconCache.getIcon(icon_id, accessor=_LabelValueAccessor(obj))


def get_cdbpc_url(obj_handle, cdef):
    classname = cdef.getClassname()
    msg = Cdbcmsg(classname, kOperationShowObject, True)
    table_name = cdef.getPrimaryTable()

    for key in cdef.getKeyNames():
        msg.add_item(key, table_name, obj_handle.getValue(key, False))

    return msg.cdbwin_url()


def get_ui_link(obj_handle, cdef, rest_key, request):
    """
    Gets the ui link for windows or web client.
    """
    # kAppl_IIOPServer and cdbpc URLs will be removed in CE 16
    if hasattr(misc, "kAppl_IIOPServer") and misc.CDBApplicationInfo().rootIsa(
        misc.kAppl_IIOPServer
    ):
        return get_cdbpc_url(obj_handle, cdef)

    rest_name = cdef.getRESTName()
    return SYSTEM_LINK_PATTERN.format(
        base=request.application_url if request else "",
        restName=rest_name,
        restKey=rest_key,
    )


def get_restkey(oh, cdef):
    keys = cdef.getKeyNames()
    values = []
    for k in keys:
        val = oh.getValue(k, False)
        k_v = ""
        for c in str(dump_value(val)):
            k_v += _REPLACEMENTS[c]
        values.append(k_v)
    return "@".join(values)


def update_objects(objects, obj_handle, request):
    """
    Mutates the objects dictionary with the new object if
    not already present.
    """
    cdef = obj_handle.getClassDef()
    rest_key = get_restkey(obj_handle, cdef)
    if rest_key not in objects:
        objects[rest_key] = {
            "description": obj_handle.getDesignation(),
            "system:ui_link": get_ui_link(obj_handle, cdef, rest_key, request),
            "icon": get_object_icon(obj_handle, cdef),
        }
    return rest_key


def get_relship_def(obj_handle, relship_name):
    cdef = obj_handle.getClassDef()
    relship = cdef.getRelationship(relship_name)

    if relship and relship.is_valid():
        return relship
    else:
        logging.info(
            "Relship '%s' is not configured for class '%s'",
            relship_name,
            cdef.getDesignation(),
        )
        return None


def navigate_relship(obj_handle, relship):
    """
    Given an object and relationship name, this method tries to resolve
    the relationship for the object.
    At first it tries to resolve the relationship as 1:1, if no result then
    tries to resolve the relship as 1:n, if no results then it tries to resolve the
    fallback relationship.

    :param obj_handle: object handle of the object to be used for resolving relship.
    :type obj_haneld: CDBObjectHandle

    :param relship: The configured relationship for the context.
    :type relship: cs.taskmanager.conf.TreeContextRelationship

    :returns: It returns a list of all the resolved objects.
    :rtype: list
    """
    try:
        # The CDBObjectHandle api (navigate_...Relship) for resolving relationships
        # already checks the read access rights.
        relship_def = get_relship_def(obj_handle, relship.parent_relship_name)
        if relship_def:
            if relship_def.is_one_on_one():
                result = obj_handle.navigate_OneOnOne_Relship(
                    relship.parent_relship_name
                )
                if result:
                    return [
                        result
                    ], False  # return list because result is a single object
            else:
                result = obj_handle.navigate_Relship(relship.parent_relship_name)
                if result:
                    return (
                        result,
                        False,
                    )  # now result is a list of resulting objects

        if (
            relship.source_classname != relship.parent_classname
            and relship.fallback_relship_name
        ):
            # since the parent_relship_name didn't resolve to object(s)
            # we now check if the fallback can be used to resolve to an object

            fallback_relship_def = get_relship_def(
                obj_handle, relship.fallback_relship_name
            )
            if fallback_relship_def and fallback_relship_def.is_one_on_one():
                result = obj_handle.navigate_OneOnOne_Relship(
                    relship.fallback_relship_name
                )
                if result:
                    return [result], True

        if relship.source_classname != relship.parent_classname:
            # in case we couldn't resolve to any object
            # we log this information here so that the config entry can be fixed
            logging.info(
                """Could not resolve configured relships '%s' or fallback """
                """relship '%s' for object '%s'.""",
                relship.parent_relship_name,
                relship.fallback_relship_name,
                obj_handle.getDesignation(),
            )

        return [], False

    except ElementsError:
        # in case navigate relships raised error, the platform would log it
        # we discontinue our search here but we still continue finding other contexts
        return [], False


def resolve_contexts(obj_handle, relships, objects, request, result):
    """
    Recursive method to gather all the resolved contexts.
    """
    if relships and not obj_handle:
        # relships still exist but no obj_handle, meaning we didn't reach the root
        # due to incorrect config or no access rights -> return empty result
        return []

    if (
        obj_handle and not relships
    ) or not (  # all relships are exhausted -> return result
        obj_handle and relships
    ):
        return result

    new_result = []

    relship = relships.pop()

    next_handles, is_fallback = navigate_relship(obj_handle, relship)
    is_same_handle = False
    if not next_handles:
        if relship.parent_classname == relship.source_classname:
            # use the same object in case
            next_handles = [obj_handle]
            is_same_handle = True
        else:
            # the relship didn't resolve into any object we terminate our recursion
            return []

    def drill_down(handle, next_result):
        next_handle = handle
        last_handle = handle
        while next_handle:
            last_handle = next_handle
            next_handle, _ = navigate_relship(next_handle, relship)
            if next_handle:
                next_handle = next_handle[0]
                rest_key = update_objects(objects, next_handle, request)
                next_result.append(rest_key)

        return last_handle

    for handle in next_handles:
        if is_same_handle:
            next_result = list(result[0])
        else:
            rest_key = update_objects(objects, handle, request)
            next_result = list(result[0])
            next_result.append(rest_key)

            if not is_fallback and relship.parent_classname == relship.source_classname:
                # in case when we want to resolve to the same class
                # we resolve all the objects of the same type untill
                # there are no more objects
                handle = drill_down(handle, next_result)

        # collect the results
        if is_fallback:
            # in case of fallback relship collect the results so far and don't recurse further
            new_result.extend([next_result])
        else:
            new_result.extend(
                resolve_contexts(
                    handle, list(relships), objects, request, [next_result]
                )
            )

    # return collected results
    return new_result


def get_redundant(index_a, index_b, a, b):
    """
    :param index_a: Index of first path in parent iterable
    :type index_a: int

    :param index_b: Index of first path in parent iterable
    :type index_b: int

    :param b: Index of first path in parent iterable
    :type b: list

    :returns: Index of the shorter path if it's redundant.
        ``None`` if no path is redundant
    :rtype: int

    :raises TypeError: if either ``a`` or ``b``
        has no implementation for ``len``
    """
    if len(a) <= len(b):
        shorter_index, shorter, longer = index_a, a, b
    else:
        shorter_index, shorter, longer = index_b, b, a

    try:
        start = longer.index(shorter[0])
    except (ValueError, IndexError):
        return None

    if shorter == longer[start : start + len(shorter)]:
        # shorter is completely contained in longer
        return shorter_index

    return None


def filter_redundant(contexts):
    """
    :param contexts: Contexts as returned from :py:func:`resolve_contexts`
    :type contexts: list

    :returns: ``contexts`` without "redundant" entries (see below for details)
    :rtype: list

    Two contexts A and B are defined as redundant if one of these is true:

    1. A completely contains B, meaning that all nodes of B
       are appearing in identical order (and without any nodes in between) in A.
       This fixes overlapping context configuration from different packages
       (which we cannot control by any other means).
    2. A and B share the same root and A completely contains B ignoring the root.
       "Completely contains" is defined as in case 1.
        This fixes partially overlapping context configuration
        when we would need more than one fallback level to express a context.

    .. note ::

        Runtime of this function is quadratic
        because we compare each context with all other contexts.
        Do not use with many contexts.

    :raises TypeError: if ``contexts`` has no implementation for ``len``
    :raises IndexError: if ``contexts`` contains an empty list
    """
    redundant = set()

    indexes = list(range(len(contexts)))

    for index_a, index_b in combinations(indexes, 2):
        a, b = contexts[index_a], contexts[index_b]
        root_a, root_b = a[-1], b[-1]

        if root_a == root_b:
            # root is shared? just compare the rest
            redundant.add(get_redundant(index_a, index_b, a[:-1], b[:-1]))
        else:
            # else: full compare
            redundant.add(get_redundant(index_a, index_b, a, b))

    result = [
        context for index, context in enumerate(contexts) if index not in redundant
    ]
    return result
