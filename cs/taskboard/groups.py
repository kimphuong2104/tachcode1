#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# pylint: disable-msg=global-statement

"""
Provides the APIs to use and extend the grouping of cards
on a task board.
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import rte
from cdb import sig
from cdb import util
from cdb.objects.org import Person

from cs.taskboard.constants import GROUP_CATEGORY
from cs.taskboard.constants import GROUP_RESPONSIBLE
from cs.taskboard.constants import GROUP_PRIORITY
from cs.taskboard.objects import find_subject

GROUP_LABELS = {}


GROUP_MAPPINGS = {}


def add_group(group_id, label):
    """

    Add group ID and label globally for all boards.

    .. code-block:: python

        from cdb import rte
        from cdb import sig
        from cdb import util
        from cs.taskboard.groups import add_group

        GROUP_PROJECT = "custom.po.project"

        @sig.connect(rte.APPLICATIONS_LOADED_HOOK)
        def register_groups():
            add_group(GROUP_PROJECT, util.Labels()["custom.po.group_by.project"])

    :param group_id: unique identifier of the group
    :type group_id: basestring
    :param label: label of the option in the drop-down list for grouping
    :type label: basestring
    """
    global GROUP_LABELS
    GROUP_LABELS[group_id] = label


def add_group_mapping(classname, mapping):
    """
    The name of the attribute whose value is evaluated within a group
    can be different in the task-like classes.
    This method defines for a task type from which attribute the values for a group are used.

    If the attribute of a class is defined more than once for the mapping of class and task type,
    only the last mapping defined becomes effective.

    .. code-block:: python

        from cdb import rte
        from cdb import sig
        from cs.taskboard.groups import add_group_mapping
        from cs.taskboard.groups import get_subject_group_context
        from cs.taskboard.constants import GROUP_RESPONSIBLE
        from cs.taskboard.constants import GROUP_PRIORITY
        from cs.taskboard.constants import GROUP_CATEGORY
        from cs.pcs.issues import Issue

        @sig.connect(rte.APPLICATIONS_LOADED_HOOK)
        def register_groups():
            add_group_mapping(Issue._getClassname(), {
                GROUP_RESPONSIBLE: get_subject_group_context,
                GROUP_CATEGORY: "mapped_category_name",
                GROUP_PRIORITY: "mapped_priority_name"
            })


    :param classname: classname of the task type to be grouped
    :param mapping: a dictionary with group ID as keys, and the values should be
                    one of following:

                    - attribute name of the task type, to access the value or
                      further referenced object
                    - or a function, which returns the value or referenced
                      object for grouping

    """
    global GROUP_MAPPINGS
    setting = GROUP_MAPPINGS.setdefault(classname, {})
    for name in mapping:
        prev = setting.setdefault(name, {})
        prev["resolver"] = mapping[name]


def add_group_aggregators(classname, aggregators):
    """
    Add class specific group aggregator.
    Multiple declaration for the same class will get merged, and
    the latest declared will be set in case of conflict.

    For example::

        from cdb import rte
        from cdb import sig
        from cdb import util
        from cs.taskboard.groups import add_group_aggregators
        from cs.taskboard.constants import GROUP_RESPONSIBLE
        from cs.taskboard.constants import GROUP_PRIORITY
        from cs.taskboard.constants import GROUP_CATEGORY
        from cs.pcs.issues import Issue


        def responsible_group_aggregator(issue):
            return {"effort": issue.effort_plan}


        @sig.connect(rte.APPLICATIONS_LOADED_HOOK)
        def register_group_aggregators():
            add_group_aggregators(Issue._getClassname(), {
                GROUP_RESPONSIBLE: responsible_group_aggregator
            })


    :param classname: classname of the task on a card to be grouped
    :param mapping: a dict, indexed by group IDs, and the values should be
                    a function, which returns a dict contains names and values
                    to be aggregated.

    """
    global GROUP_MAPPINGS
    setting = GROUP_MAPPINGS.setdefault(classname, {})
    for name in aggregators:
        prev = setting.setdefault(name, {})
        prev["aggregator"] = aggregators[name]


def get_group_labels():
    return GROUP_LABELS


def get_group_for_class(classname):
    return GROUP_MAPPINGS.get(classname, {})


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_groups():
    labels = util.Labels()
    add_group(GROUP_CATEGORY, labels["cs_taskboard_label_category"])
    add_group(GROUP_RESPONSIBLE, labels["cs_taskboard_label_responsible"])
    add_group(GROUP_PRIORITY, labels["cs_taskboard_label_priority"])


def get_subject_group_context(task):
    """
    Predefined function to achieve the responsible of a task
    when grouped by
    :py:attr:`cs.taskboard.constants.GROUP_RESPONSIBLE`.

    :param task: the task to be grouped by
    :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
    :return: responsible person of the task,
             or its description for non-person subject
    :rtype: cdb.objects.org.Person or basestring
    """
    result = find_subject(task)
    if result is None:
        return result
    # Person object expected, for roles: return as text.
    if result.SubjectType() != Person.SubjectType():
        return result.GetDescription()
    return result
