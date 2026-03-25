#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module SchemaComponents

This is the documentation for the SchemaComponents module.
"""

import datetime
import os

from cdb import util
from cdb import i18n
from cdb import typeconversion
from cdb.objects import Forward
from cdb.objects import NULL
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMapping_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.typeconversion import to_legacy_date_format

from cs.workflow.briefcases import WithBriefcase
from cs.workflow.misc import create_user_posting
from cs.workflow.misc import get_state_text
from cs.workflow.protocols import MSGCANCEL, MSGSYSTEM
from cs.workflow.processes import Process

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ['SchemaComponent']

fSchemaComponent = Forward(__name__ + ".SchemaComponent")
fBriefcaseLink = Forward("cs.workflow.briefcases.BriefcaseLink")
fConstraint = Forward("cs.workflow.constraints.Constraint")
fProcess = Forward("cs.workflow.processes.Process")


def _not_equal(old_value, new_value):
    result = False
    if isinstance(new_value, (datetime.datetime, datetime.date)):
        if old_value:
            result = old_value != to_legacy_date_format(new_value)
        # no else branch, because then old_value is uninitialized and we return false
    else:
        result = "%s" % (old_value) != "%s" % (new_value)
    return result


class SchemaComponent(Object, WithBriefcase):
    __maps_to__ = "cdbwf_task"

    BriefcaseLinksByType = ReferenceMapping_N(
        fBriefcaseLink,
        (fBriefcaseLink.cdb_process_id == fSchemaComponent.cdb_process_id) &
        (fBriefcaseLink.task_id == fSchemaComponent.task_id),
        indexed_by=fBriefcaseLink.iotype)

    BriefcaseLinks = Reference_N(
        fBriefcaseLink,
        fBriefcaseLink.cdb_process_id == fSchemaComponent.cdb_process_id,
        fBriefcaseLink.task_id == fSchemaComponent.task_id)

    def _get_PreviousSibling(self):
        if self.Parent and self.Parent.is_sequential():
            objects = self.Parent.Components.Query(
                (SchemaComponent.position < self.position) &
                (SchemaComponent.status != self.DISCARDED.status),
                order_by=(-SchemaComponent.position),
            )
            if objects:
                return objects[0]
        return None

    PreviousSibling = ReferenceMethods_1(Object, _get_PreviousSibling)

    # Only used for constraints (cdb_pyterm.attribute):
    PreviousOfParent = ReferenceMethods_N(fSchemaComponent,
                                          lambda self: [getattr(self.Parent, "Previous", None)])

    def _get_PreviousTask(self):
        """ Return the task or task group in the workflow,
            which comes immediately before the current task or task group
            (i.e. the component that triggers activation of the current object),
            if any.
        """
        if self.PreviousSibling:
            return self.PreviousSibling
        elif self.Parent:
            return getattr(self.Parent, "Previous", None)
        return None

    Previous = ReferenceMethods_1(Object, _get_PreviousTask)

    def _get_PreviousTasks(self):
        previous = self.Previous
        if previous:
            last_tasks = previous.get_last_tasks()
            filtered_tasks = [t for t in last_tasks if t.status != self.DISCARDED.status]
            if not filtered_tasks:
                return previous.PreviousTasks
            return filtered_tasks
        else:
            return []

    PreviousTasks = ReferenceMethods_N(Object, _get_PreviousTasks)

    # Only used for constraints (cdb_pyterm.attribute):
    PreviousN = ReferenceMethods_N(fSchemaComponent,
                                   lambda self: [getattr(self, "Previous", None)])

    def _get_NextSibling(self):
        if self.Parent and self.Parent.is_sequential():
            objects = self.Parent.Components.Query(
                SchemaComponent.position > self.position,
                order_by=SchemaComponent.position,
            )
            if objects:
                return objects[0]

        return None

    NextSibling = ReferenceMethods_1(Object, lambda self: self._get_NextSibling())

    def _get_NextTask(self):
        """ Return the task or task group in the workflow,
            which comes immediately after the current task or task group
            (i.e. the component whose activation is triggered by the current object),
            if any.
        """
        if self.NextSibling:
            return self.NextSibling
        elif self.Parent:
            return getattr(self.Parent, "Next", None)
        return None

    Next = ReferenceMethods_1(Object, _get_NextTask)

    # Only used for constraints (cdb_pyterm.attribute):
    NextN = ReferenceMethods_N(fSchemaComponent,
                                   lambda self: [getattr(self, "Next", None)])

    def _get_Parent(self):
        if self.parent_id not in ["", None, NULL]:
            return SchemaComponent.ByKeys(self.parent_id, self.cdb_process_id)
        return Process.ByKeys(self.cdb_process_id)

    Parent = ReferenceMethods_1(Object, lambda self: self._get_Parent())

    def _get_ancestors(self):
        result = []
        if isinstance(self.Parent, SchemaComponent):
            result += self.Parent._get_ancestors()
        result.append(self.Parent)
        return result

    Ancestors = ReferenceMethods_N(fSchemaComponent, _get_ancestors)

    Process = Reference_1(fProcess, fProcess.cdb_process_id)

    # Empty reference to content
    # We need to use this in the object rules, but there is no way
    # to define an object rule for cs.workflow.tasks.Task.
    # Therefore we need this reference already in the base class.
    Content = ReferenceMethods_N(Object, lambda x: [])

    Constraints = Reference_N(fConstraint,
                              fConstraint.cdb_process_id == fSchemaComponent.cdb_process_id,
                              fConstraint.task_id == fSchemaComponent.task_id)

    @classmethod
    def Create(cls, **kwargs):
        if not kwargs.get("cdb_extension_class", None):
            kwargs["cdb_extension_class"] = ""
        return super(SchemaComponent, cls).Create(**kwargs)

    event_map = {
        ("create", "pre"): ("setObjectLifeCycle", "init_extension_class"),
        (("create", "copy", "delete", "modify"), "post"): "addActionToProtocol",
        ("copy", "pre"): "reset_process_is_onhold",
    }

    def reset_process_is_onhold(self, ctx):
        if hasattr(ctx, 'error') and ctx.error:
            return
        process_paused = int(self.Process.status == Process.PAUSED.status)
        self.Update(process_is_onhold=process_paused)

    def addActionToProtocol(self, ctx):
        """
        extended logging for detailed workflow report and compliance,
        effectively tracks how a workflow was instantiatd and changed over
        time

        .. info ::

            this will not log anything if either

            1. the :envvar:`CS_WORKFLOW_SIMPLE_LOG_MODE` is set to anything
               but an empty string or
            2. ``ctx.error`` is a value mapping to ``True``.

        """
        simple_mode = os.getenv("CS_WORKFLOW_SIMPLE_LOG_MODE", None)
        if not (simple_mode or ctx.error):
            if ctx.action == "create":
                #  add ID of new component to the protocol
                self.addProtocol(util.get_label("cdbwf_component_add").format(
                    self.task_id,
                    self.title
                    )
                )
            elif ctx.action == "copy":
                # add copied component and where it comes from to the protocol
                self.addProtocol(util.get_label("cdbwf_component_copy").format(
                    self.task_id,
                    self.title,
                    ctx.cdbtemplate["process_title"],
                    ctx.cdbtemplate["cdb_process_id"]
                    )
                )
            elif ctx.action == "delete":
                # add deletion of component to the protocol
                self.addProtocol(
                    util.get_label("cdbwf_component_delete").format(
                        self.task_id,
                        self.title
                    )
                )
            elif ctx.action == "modify":
                # add modifications of component to the protocol
                msgs = self.get_modify_Protocol_text(ctx)
                if msgs:
                    label = util.get_label("cdbwf_component_modify")

                    self.addProtocol(
                        label.replace("\\n", "\n").format(
                            self.task_id,
                            self.title,
                            "\n".join(msgs)
                        )
                    )

    def get_modify_Protocol_text(self, ctx):
        msgs = []

        for fdname in ctx.ue_args.get_attribute_names():
            if fdname[:9] == "prot_old_":
                name = fdname[9:]
                old_value = ctx.ue_args[fdname]
                new_value = self[name]
                if (old_value or new_value) and _not_equal(old_value, new_value):
                    # if new value is a datetime object, both values represent dates
                    if isinstance(new_value, (datetime.datetime, datetime.date)):
                        # parse date values into format given by user settings
                        # only take the first 10 chars of the resulting date string,
                        # only taking the date
                        old_value = typeconversion.to_user_repr_date_format(old_value)[:10]
                        new_value = typeconversion.to_user_repr_date_format(new_value)[:10]
                    msgs.append("%s: %s -> %s" % (name,
                                                    old_value,
                                                    new_value))
        return msgs

    def addProtocol(self, msg, msgtype=MSGSYSTEM):
        if self.Process.status != self.Process.NEW.status or not self.Process.isTemplate():
            self.Process.addProtocol(msg, msgtype, self.task_id)

    def addASComment(self, comment):
        if self.Process.status != self.Process.NEW.status:
            create_user_posting(self, comment)

    def setObjectLifeCycle(self, ctx):
        if not self.cdb_objektart:
            self.cdb_objektart = self.getObjectLifeCycle()

    def init_extension_class(self, ctx):
        if not self.cdb_extension_class:
            self.cdb_extension_class = ""

    @classmethod
    def getObjectLifeCycle(cls):
        return getattr(cls, "__obj_class__", "")

    @classmethod
    def GetStateText(cls, state, lang=None):
        if lang is None:
            lang = i18n.default()
        return get_state_text(cls.getObjectLifeCycle(), state.status, lang)

    def AbsolutePath(self):
        obj = self
        lpos = []

        while obj:
            if isinstance(obj, SchemaComponent):
                lpos.append("%g" % (obj.position if obj.position else -1))
                obj = obj.Parent
            else:
                obj = obj.ParentTask

        return "/".join(reversed(lpos))

    def make_position(self, ctx):
        position = 10

        if self.Parent:
            max_pos = max(self.Parent.Components.position + [0])
            position = max_pos + 10
        self.position = position

    def check_position(self, ctx):
        if ctx.action == "modify":
            try:
                if ("position" in ctx.dialog.get_attribute_names() and
                        float(ctx.dialog.position) == float(ctx.object.position)):
                    return
            except ValueError:
                pass

        if SchemaComponent.KeywordQuery(cdb_process_id=self.cdb_process_id,
                                        parent_id=self.parent_id,
                                        position=self.position):
            raise util.ErrorMessage("cdbwf_err110")

        if self.Parent and not self.Parent.is_position_editable(self.position):
            from cs.workflow.taskgroups import ParallelTaskGroup
            if isinstance(self.Parent, ParallelTaskGroup):
                raise util.ErrorMessage("cdbwf_err114")
            else:
                raise util.ErrorMessage("cdbwf_err108", "%d" % (self.position))

    def is_position_editable(self, position):
        """Check if the addition of a new task in the given position is allowed."""

        return NotImplementedError("To be implemented by the subclasses")

    def check_constraints(self, interactive=False):
        """If 'interactive' is set to True, then an error message is displayed via UE exception, if
        any constraint is violated. If 'interactive' is set to False, then a protocol entry is made
        with the error message and the process component is reset to NEW, if any constraint is
        violated.

        :param interactive: True or False
        :type interactive: Bool

        :returns: Bool -- If 'interactive' is set to False

        :raises: ue.Exception -- If 'interactive' is set to True

        """
        for constraint in self.Constraints:
            if interactive:
                constraint.check_violation(self)
            else:
                if constraint.is_violated(self):
                    self.addProtocol(constraint.get_message_constraint_violated(self),
                                     MSGCANCEL)
                    return False
        return True

    def allow_new_task(self, ctx):
        from cs.workflow.tasks import Task
        if self.Parent.status > Task.EXECUTION.status:
            raise util.ErrorMessage("cdbwf_err111")
