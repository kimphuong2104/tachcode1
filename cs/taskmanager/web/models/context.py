#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import logging

from webob.exc import HTTPNotFound

from cdb.objects import ByID
from cs.taskmanager.conf import TaskClass


class TaskContextModel(object):
    def __init__(self, task_classname, task_oid):
        self.task_class = TaskClass.ByClassname(task_classname)

        if not self.task_class:
            logging.error("TaskContext: invalid task_classname: '%s'", task_classname)
            raise HTTPNotFound

        task = ByID(task_oid)

        if not (task and task.CheckAccess("read")):
            logging.error(
                "TaskContext: task does not exist or not readable: '%s'", task_oid
            )
            raise HTTPNotFound

        if not self.task_class.is_task_object(task):
            logging.error(
                "TaskContext: task of wrong class: '%s' (expected '%s')",
                task.GetClassname(),
                self.task_class.classname,
            )
            raise HTTPNotFound

        self.task = task

    def _remove_duplicates(self, tree_contexts):
        """
        Removes the duplicate contexts if any.
        """
        seen = set()
        result = []
        for item in tree_contexts:
            key = tuple(item)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def resolve_context(self, request):
        """
        Resolve the tree context for a given task.

        :param request: The request sent from the frontend
            (used for link generation)
        :type request: morepath.Request
        """
        tree_contexts = []
        objects = {}
        for tree_context in self.task_class.Contexts:
            contexts = tree_context.resolve(self.task, objects, request)
            tree_contexts.extend(contexts)

        return {
            "contexts": self._remove_duplicates(tree_contexts),
            "data": objects,
        }
