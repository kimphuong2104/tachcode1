#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import auth, i18n, util
from cdb.lru_cache import lru_cache
from cdb.objects import MixIn
from cdb.objects.org import Subject
from cdb.platform.olc import StateChangeDefinition, StatusInfo
from cdb.transactions import Transaction
from cs.activitystream import PostingRuleChecker
from cs.activitystream.objects import SystemPosting
from cs.platform.web.rest.generic.model import Workflow


@lru_cache(maxsize=50, clear_after_ue=False)
def get_status_data(kind, status):
    info = StatusInfo(kind, status)
    label = info.getLabel()

    return {
        "status": status,
        "label": label,
        "dialog": {
            "zielstatus": label,
        },
        "color": info.getCSSColor(),
    }


def get_target_status_data(kind, old_status, status):
    transition = StateChangeDefinition.ByKeys(kind, old_status, status)
    result = get_status_data(kind, status)
    result["priority"] = 999999 if transition.rang is None else transition.rang
    return result


class WithTasksIntegration(MixIn):
    """
    MixIn to include in classes to be displayed by cs.taskmanager for easy
    setup. Mainly provides getters for composite attributes and the "proceed"
    operation.
    """

    __mixin_active__ = True
    __cs_tasks_proceed_access__ = None
    __cs_tasks_delegate_msg__ = "cs_tasks_delegate"

    PRIO_HIGH = "cs_tasks_prio_high"
    PRIO_MEDIUM = "cs_tasks_prio_medium"
    PRIO_LOW = "cs_tasks_prio_low"

    def getCsTasksContexts(self):
        """
        .. _`getCsTasksContexts`:

        Implement this method to support the context filter.

        :returns: The objects representing the task's context.
        :rtype: list of cdb.objects.Object

        Example implementation using Powerscript References:

        .. code-block :: python

            from cdb.objects import Reference_1
            from cs.pcs import projects
            from cs.taskmanager.mixin import WithTasksIntegration

            class MyProjectTask(WithTasksIntegration):
                Project = Reference_1(projects.Project, MyProjectTask.cdb_project_id)

                def getCsTasksContexts(self):
                    return [self.Project]


        """
        return []

    def getCsTasksResponsible(self):
        """
        Resolves asynchronous values for the default responsible column.

        :returns: Person or role
        :rtype: cdb.objects.Object
        """
        return self.Subject

    def getCsTasksStatusData(self):
        """
        Resolves asynchronous values for the default status column.
        This is the default implementation for tasks with an object lifecycle.

        :returns: Status data
        :rtype: dict

        :raises AttributeError: if `self` is missing either
            "cdb_objektart" or "status".

        Example return value:

        .. code-block :: python

            {
                "status": 0,
                "label": "New",
                "dialog": {
                    "zielstatus": "New",
                },
                "color": "#FFFFFF",
            }
        """
        kind = self.GetObjectKind()
        if kind:
            return get_status_data(kind, self.status)
        return None

    def getCsTasksNextStatuses(self):
        """
        Called when user opens a specific status cell dropdown for the first time.
        This is the default implementation for tasks with an object lifecycle.

        :returns: Possible target statuses in order of appearance
        :rtype: list

        :raises AttributeError: if `self` is missing either
            "cdb_objektart" or "status".

        Example return value:

        .. code-block :: python

            [
                {
                    "priority": 1,
                    "status": 10,
                    "label": "Completed",
                    "dialog": {
                        "zielstatus": "Completed",
                    },
                    "color": "#00A000",
                },
                {
                    "priority": 2,
                    "status": 20,
                    "label": "Canceled",
                    "dialog": {
                        "zielstatus": "Canceled",
                    },
                    "color": "#000000",
                },
            ]
        """
        kind = self.GetObjectKind()

        if not kind:
            return None

        wf = Workflow(self)

        targets = [
            get_target_status_data(kind, self.status, status)
            for status, _ in wf.next_steps()
        ]
        targets.sort(
            key=lambda status: (
                status["priority"],
                status["status"],
            )
        )
        return targets

    event_map = {
        ("cs_tasks_delegate", "pre_mask"): "preset_csTasksDelegate",
        ("cs_tasks_delegate", "now"): "csTasksDelegate",
        ("cs_tasks", "now"): "csTasksOpen",
    }

    def csTasksDelegate_get_project_manager(self):
        """
        Usable by tasks with Project reference (not used by cs.taskmanager
        itself).

        The delegation dialog has to contain the context ID (cdb_project_id)
        attribute (usually hidden).
        """
        from cs.pcs.projects import (
            kProjectManagerRole,  # pylint: disable=no-name-in-module
        )

        name = self.Project.getProjectManagerName()
        if name:
            return kProjectManagerRole, "PCS Role", name

        return "", "", ""

    def csTasksDelegate_get_default(self):
        """
        Overwrite this for task objects having an "80%" correct delegation
        target, e.g. a person managing the parent object.

        Always return a 3-tuple of subject_id, subject_type, subject_name. If
        subject_id is not empty, the values will be used to preset the
        operation.
        """
        return "", "", ""

    def preset_csTasksDelegate(self, ctx):
        subj_id, subj_type, subj_name = self.csTasksDelegate_get_default()
        if subj_id:
            ctx.set("subject_id", subj_id)
            ctx.set("subject_type", subj_type)
            ctx.set("subject_name", subj_name)

    def csTasksDelegate(self, ctx):
        """
        Overwrite this for task objects without "subject logic", e.g. those,
        that use other attributes to identify responsible user(s).

        Note that you will also have to modify the operation dialog for these
        task classes.
        """
        if not ctx.dialog.subject_id and not ctx.dialog.subject_type:
            import logging

            logging.error("No selection made on the dialog")
            return

        old = {}

        if self.Subject:
            subject_id = self.Subject.SubjectID()
            old = {
                "subject_id": subject_id[0],
                "subject_type": self.Subject.SubjectType(),
            }

        new = {
            "subject_id": ctx.dialog.subject_id,
            "subject_type": ctx.dialog.subject_type,
        }

        # only update if old and new values differ
        if old != new:
            with Transaction():
                # delegate, fire post actions (cs.web operation does not do so)
                self.Update(**new)
                self._csTasksDelegatePost(ctx, old, new)

    def _csTasksSysPostingVals(self, old, new):
        def _adapt_value(attribute, attr_value):
            try:
                attr_value = attr_value[
                    : util.tables["cdbblog_posting"].column(attribute).length()
                ]
            except (ValueError, AttributeError):
                pass
            return attr_value.replace("\\n", "\n")

        values = {
            "context_object_id": self.cdb_object_id,
            "type": "update",
        }

        old_values = dict(self)
        old_values.update(old)
        new_values = dict(self)
        new_values.update(new)

        usr_subject = Subject.findSubject(
            SubjectFromContext(subject_id=auth.persno, subject_type="Person")
        )
        old_subject = Subject.findSubject(SubjectFromContext(**old_values))
        new_subject = Subject.findSubject(SubjectFromContext(**new_values))

        # Generate a text for all active languages
        for lang in i18n.getActiveGUILanguages():
            msg = util.CDBMsg(util.CDBMsg.kNone, self.__cs_tasks_delegate_msg__)
            msg.addReplacement(usr_subject.GetDescription(lang))
            msg.addReplacement(new_subject.GetDescription(lang))
            msg.addReplacement(old_subject.GetDescription(lang))
            value = msg.getText(lang, True)
            attrname = "title_" + lang
            values[attrname] = _adapt_value(attrname, value)

        return values

    def _csTasksDelegatePost(self, ctx, old, new):
        # it is strongly advised to always create these postings
        if PostingRuleChecker().checkRules(self.ToObjectHandle()):
            SystemPosting.do_create(**self._csTasksSysPostingVals(old, new))

        # send email notification if task class supports it
        if hasattr(self, "sendNotification"):
            setattr(ctx, "task_delegated", "1")
            self.sendNotification(ctx)  # E042355 ctx=None


class SubjectFromContext(object):
    def __init__(self, **kwargs):
        for attr, val in kwargs.items():
            setattr(self, attr, val)
        self._refcache = {}
