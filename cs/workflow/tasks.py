#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module Tasks

This is the documentation for the Tasks module.
"""

import datetime
import json
import logging
import os

from cdb import ue
from cdb import auth
from cdb import constants
from cdb import transactions
from cdb import util
from cdb import ElementsError
from cdb.typeconversion import to_legacy_date_format

from cdb.objects import Object
from cdb.objects import operations
from cdb.objects import org
from cdb.objects import Forward
from cdb.objects import NULL
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMapping_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import Reference_Methods
from cdb.objects import State
from cdb.objects import Rule
from cdb.objects.common import WithStateChangeNotification
from cdb.objects.iconcache import _LabelValueAccessor
from cdb.objects.iconcache import IconCache
from cdb.objects.org import User
from cdb.objects.org import Subject

from cs.platform.org.user import UserSubstitute
from cs.sharing.share_objects import WithSharing
from cs.taskmanager.userdata import Tags
from cs.workflow.forms import TaskWithForm
from cs.workflow.tasks_plugin import WorkflowTaskWithCsTasks
from cs.workflow.misc import _run_op
from cs.workflow.misc import calc_deadline
from cs.workflow.misc import set_state
from cs.workflow.misc import set_state_interactive
from cs.workflow.misc import get_object_url
from cs.workflow.misc import get_object_class_by_name
from cs.workflow.misc import notification_enabled
from cs.workflow.misc import require_feature_viewing
from cs.workflow.protocols import MSGCANCEL
from cs.workflow.protocols import MSGDONE
from cs.workflow.protocols import MSGREFUSE
from cs.workflow.protocols import MSGSYSTEM
from cs.workflow.protocols import MSGTASKREADY
from cs.workflow.protocols import Protocol
from cs.workflow.pyrules import WithRuleWrapper
from cs.workflow.schemacomponents import SchemaComponent
from cs.workflow import briefcases
from cs.workflow import exceptions

__all__ = [
    "ApprovalTask",
    "ExaminationTask",
    "ExecutionTask",
    "FilterParameter",
    "InteractiveTask",
    "SystemTask",
    "Task",
    "TaskDataIncompleteException",
]

fTask = Forward(__name__ + ".Task")
fFilterParameter = Forward(__name__ + ".FilterParameter")

fProcess = Forward("cs.workflow.processes.Process")
fProtocol = Forward("cs.workflow.protocols.Protocol")
fSchemaComponent = Forward("cs.workflow.schemacomponents.SchemaComponent")
fTaskGroup = Forward("cs.workflow.taskgroups.TaskGroup")
fSystemTaskDefinition = Forward("cs.workflow.systemtasks.SystemTaskDefinition")
fBriefcase = Forward("cs.workflow.briefcases.Briefcase")
fOperation = Forward("cdb.platform.mom.operations.Operation")

fRule = Forward("cdb.objects.Rule")

_TASK_RULES = ["cdbtodo: task_approval",
               "cdbtodo: task_examination",
               "cdbtodo: task_execution"]
CTX_OLD = "%s_old"
UNSUPPORTED_CONTEXT_TYPE = "Unsupported context type"


def _run(opname, target, **kwargs):
    return _run_op(
        opname,
        target,
        operations.form_input(target, **kwargs)
    )


def combine_error_messages(errors):
    return " / ".join([x for x in errors if x])


class TaskDataIncompleteException(Exception):
    """
    Exception raised by `check_process_start_preconditions` if
    the conditions are not fulfilled.
    """
    pass


class Task(SchemaComponent,
           org.WithSubject, WithStateChangeNotification, TaskWithForm):
    """
    Base class for both interactive task and system task types.
    Defines some common APIs to handle workflow task.
    """

    __classname__ = "cdbwf_task"
    __match__ = fSchemaComponent.cdb_classname >= __classname__
    __obj_class__ = "cdbwf_task"

    __notification_template_folder__ = os.path.join(
        os.path.dirname(__file__),
        "chrome",
    )

    # Attribute that may contain a fully qualified python name to
    # add object specific workflow behavior.
    __wf_handler_attr__ = "task_handler"

    TaskGroup = Reference_1(fTaskGroup, fTask.parent_id, fTask.cdb_process_id)
    Process = Reference_1(fProcess, fTask.cdb_process_id)
    RootProcess = ReferenceMethods_1(fProcess, lambda t: t.Process.RootProcess)
    TerminatedParents = Reference_Methods(fProcess, lambda t: t.Process.TerminatedParents)

    Protocols = Reference_N(fProtocol,
                            fProtocol.cdb_process_id == fTask.cdb_process_id,
                            fProtocol.task_id == fTask.task_id)

    Protocols = Reference_N(
        fProtocol,
        fProtocol.cdb_process_id == fTask.cdb_process_id,
        fProtocol.task_id == fTask.task_id,
    )

    event_map = {
        (("create", "copy"), "pre"): ("check_position",
                                      "make_task_id",
                                      "make_project_id"),
        (("create", "copy"), "pre_mask"): ("allow_new_task",
                                           "make_position",
                                           "make_project_id"),
        (("create", "copy", "modify"), "pre"): "check_max_duration",
        (("modify"), "pre"): "check_position",
        ("cdbwf_close_task", "now"): "op_close_task",
        ("cdbwf_refuse_task", "now"): "op_refuse_task",
        ("cdbwf_forward_task", "now"): "op_forward_task",
        (("copy"), "post"): "copy_tags",
    }

    def copy_tags(self, ctx):
        if ctx.error:
            return
        if ctx.cdbtemplate:
            for t in Tags.KeywordQuery(
                    task_object_id=ctx.cdbtemplate.cdb_object_id
            ):
                values = dict(**t)
                values.update(task_object_id=self.cdb_object_id)
                t.Create(**values)

    def notifyAfterStateChange(self, ctx=None):
        ''' Overwrite, so no message will be send if an error occured '''
        if not ctx or not ctx.error:
            self.Super(Task).notifyAfterStateChange(ctx)

    def op_close_task(self, ctx):
        comment = getattr(ctx.dialog, "remark", "")
        self._op_change_task("close", comment)

    def op_refuse_task(self, ctx):
        comment = getattr(ctx.dialog, "remark", "")
        self._op_change_task("refuse", comment)

    def op_forward_task(self, ctx):
        if not self.isForwardable():
            raise util.ErrorMessage("cdbwf_task_not_forwardable")

        comment = getattr(ctx.dialog, "remark", "")
        self._op_change_task("forward", comment)

    def _op_change_task(self, op, comment):
        assert(op in ["close", "refuse", "forward"])

        if self.status != self.EXECUTION.status:
            raise util.ErrorMessage("cdbwf_task_not_ready")

        try:
            getattr(self, op + "_task")(comment)
        except (util.ErrorMessage, ElementsError, ue.Exception) as e:
            raise util.ErrorMessage("just_a_replacement", str(e))
        except Exception:
            logging.exception("could not change task's status")
            raise util.ErrorMessage("pccl_err_statechan")

    class NEW(State):
        status = 0

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch and (
                self.Parent.is_sequential()
                or self.Parent.status != self.Parent.EXECUTION.status
            ):
                ctx.excl_state(Task.EXECUTION.status)
            super(Task.NEW, state).pre_mask(self, ctx)

        def pre(state, self, ctx):  # @NoSelf
            self.start_date = ""
            self.end_date_act = ""
            super(Task.NEW, state).pre(self, ctx)

    class EXECUTION(State):
        status = 10

        def pre_mask(state, self, ctx):  # @NoSelf
            if not self.isRefuseable():
                ctx.excl_state(self.REJECTED.status)
            super(Task.EXECUTION, state).pre_mask(self, ctx)

        def pre(state, self, ctx):  # @NoSelf
            # if title and responsible are not set, set them to default
            self.set_title()
            self.set_responsible()

            for briefcase in self.BriefcaseLinks:
                try:
                    briefcase.check_obj_rights(ctx, persno=self.Process.started_by)
                except ue.Exception as ex:
                    msg = ''.join(str(x) for x in ex.errp[0])
                    self.addProtocol(msg)

            self.start_date = datetime.date.today()
            calc_deadline(self)
            self.preset_data()  # defined in TaskWithForm
            self.addProtocol(util.get_label("cdbwf_task_set_ready"), MSGTASKREADY)
            super(Task.EXECUTION, state).pre(self, ctx)

    class COMPLETED(State):
        status = 20

        def pre(state, self, ctx):  # @NoSelf
            self.check_form_data()  # defined in TaskWithForm
            comment = getattr(ctx.dialog, "comment", "")
            if self.requiresComment() and comment == "":
                raise util.ErrorMessage("cdbwf_err101")
            self.end_date_act = datetime.date.today()
            lbl = util.get_label("cdbwf_task_done")
            self.addProtocol("%s \n%s" % (lbl, comment), MSGDONE)
            self.addASComment(comment)
            super(Task.COMPLETED, state).pre(self, ctx)

    class REJECTED(State):
        status = 30

        def pre(state, self, ctx):  # @NoSelf
            comment = getattr(ctx.dialog, "comment", "")
            if self.requiresComment() and comment == "":
                raise util.ErrorMessage("cdbwf_err101")
            self.end_date_act = datetime.date.today()
            lbl = util.get_label("cdbwf_task_refused")
            self.addProtocol("%s \n%s" % (lbl, comment), MSGREFUSE)
            self.addASComment(comment)
            super(Task.REJECTED, state).pre(self, ctx)

        def post(state, self, ctx):  # @NoSelf
            super(Task.REJECTED, state).post(self, ctx)

    class DISCARDED(State):
        status = 35

        def pre(state, self, ctx):  # @NoSelf
            super(Task.DISCARDED, state).pre(self, ctx)

            comment = getattr(ctx.dialog, "comment", "")
            self.addProtocol(
                str(
                    util.get_label("cdbwf_task_discarded")
                ) % comment,
                MSGCANCEL)
            self.addASComment(comment)

    # ===========================================================================
    # New interface
    # ===========================================================================

    def activate_task(self):
        """
        Attempts to set the current task ready. If the constraints check fails,
        the task would be cancelled.
        """
        require_feature_viewing()
        if not self.check_constraints():
            self.cancel_task()
            raise exceptions.TaskCancelledException()

        if not self.isSystemTask():
            self.set_briefcase_rights()

        self.setReady()

    def cancel_task(self, comment=""):
        """
        Attempts to cancel the current task.
        """
        require_feature_viewing()
        self.setCancelled(comment)

    def close_task(self, comment=""):
        """
        Attempts to close the current task by set it as done.
        """
        self.setDone(comment)

        if self.Parent:
            self.Parent.propagate_done(self)

    def refuse_task(self, comment=""):
        """
        Attempts to refuse the current task.
        """

        self.setRefused(comment)

        if self.Parent:
            self.Parent.propagate_refuse(self, comment)

    def forward_task(self, comment=""):
        """
        Attempts to close the current task and forward
        the decision to another task.
        """
        if self.requiresComment() and comment == "":
            raise util.ErrorMessage("cdbwf_err101")

        self.addProtocol(
            str(util.get_label("cdbwf_task_forwarded")),
            MSGSYSTEM)
        self.__forwarded__ = True

        self.close_task(comment)

    # ===========================================================================
    # End new interface
    # ===========================================================================

    # Other methods

    @classmethod
    def new_task_id(cls):
        return "T%08d" % util.nextval("cdbwf_task.task_id")

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    def on_cdbwf_show_recipients_now(self, ctx):
        class Referrer(object):
            def __init__(self):
                self.subject_id = ''
                self.subject_type = ''
                self.cdb_project_id = ''
                self._refcache = {}

        params = self.AllParameters.KeywordQuery(name=["subject_id", "subject_type"])

        referrer = Referrer()
        for param in params:
            if param.name == 'subject_id':
                referrer.subject_id = param.value
            elif param.name == 'subject_type':
                referrer.subject_type = param.value

        # add cdb_project_id only if cs.pcs is installed
        if hasattr(self.Process, 'cdb_project_id'):
            referrer.cdb_project_id = self.Process.cdb_project_id

        subject = Subject.findSubject(referrer)
        if subject:
            return subject.Open()
        else:
            raise util.ErrorMessage("cdb_org_open_subject")

    def on_modify_pre_mask(self, ctx):
        if self.status > Task.NEW.status:
            ctx.set_fields_readonly(["position", "mapped_classname"])

    def on_modify_pre(self, ctx):
        # Fixing E014422
        obj = Task.ByKeys(self.task_id, self.cdb_process_id)
        for fdname in obj.GetFieldNames():
            if (fdname[:4] != "cdb_" and
                    fdname in ctx.dialog.get_attribute_names() and
                    ctx.dialog[fdname] != obj[fdname]):
                fd_value = obj[fdname]
                if isinstance(fd_value, (datetime.datetime, datetime.date)):
                    fd_value = to_legacy_date_format(fd_value)
                ctx.keep("prot_old_%s" % fdname, fd_value)
        obj.Lock()

    def AddActionToProtocol(self, ctx):
        self.Super(Task).AddActionToProtocol(ctx)
        if ctx.action == "modify":
            self.Unlock()

    def check_max_duration(self, ctx):
        if self.max_duration is not None and self.max_duration < 1:
            raise util.ErrorMessage("cdbwf_max_duration_greater_0")

    def make_task_id(self, ctx):
        if ctx.action == "copy":
            # No need to change the task_id if the process id has changed
            template_id = getattr(ctx.cdbtemplate, "cdb_process_id", self.cdb_process_id)
            if template_id == self.cdb_process_id:
                self.task_id = self.new_task_id()
        else:
            self.task_id = self.new_task_id()

    def allow_new_task(self, ctx):
        # No creation of tasks out of a process context
        if not ctx.parent.get_attribute_names():
            raise util.ErrorMessage("cdbwf_err103")
        self.Super(Task).allow_new_task(ctx)

    def make_project_id(self, ctx):
        if self.Process:
            # derive process's project id
            self.cdb_project_id = self.Process.cdb_project_id

    def isExaminationTask(self):
        return (Task.cdb_classname >= "cdbwf_task_examination").eval(self)

    def isExecutionTask(self):
        return (Task.cdb_classname >= "cdbwf_task_execution").eval(self)

    def isApprovalTask(self):
        return (Task.cdb_classname >= "cdbwf_task_approval").eval(self)

    def isSystemTask(self):
        return (Task.cdb_classname >= "cdbwf_system_task").eval(self)

    def isForwardable(self):
        """
        Manually check whether a task can be forwarded or not.
        """
        return False

    def isRefuseable(self):
        """
        Manually check whether a task can be refused or not.
        """
        return False

    def requiresComment(self):
        """
        Manually check whether the comment is required while closing
        or canceling a task.
        """
        return False

    def setReady(self):
        set_state(self, self.EXECUTION)

    def setDone(self, comment="", interactive=False):
        if interactive:
            set_state_interactive(self, self.COMPLETED, comment=comment)
        else:
            set_state(self, self.COMPLETED, comment=comment)

    def setNew(self):
        set_state(self, self.NEW)

    def setRefused(self, comment="", interactive=False):
        if interactive:
            set_state_interactive(self, self.REJECTED, comment=comment)
        else:
            set_state(self, self.REJECTED, comment=comment)

    def setCancelled(self, comment=""):
        set_state(self, self.DISCARDED, comment=comment)

    def RenderHtml(self, request, **kwargs):
        args = kwargs.copy()
        args["commenthref"] = Protocol.MakeCdbcmsg(
            "CDB_Create",
            cdb_process_id=self.cdb_process_id,
            task_id=self.task_id).eLink_url()
        args["commenticon"] = Protocol.GetClassIcon()

        args["checkboxonly"] = not self.requiresComment()

        args["links"] = self.Process._Links()

        return super(Task, self).RenderHtml(request, **args)

    def get_responsible_name(self):
        rname = self.subject_id
        if self.subject_type == "Person":
            rname = User.ByKeys(self.subject_id).name
        return rname

    def get_last_tasks(self):
        return [self]

    @classmethod
    def get_all_tasks_by_user(cls, condition=""):
        """All (non-new and non-cancelled) tasks which are either
        directly assigned to a given user id or indirectly via a role"""

        tasks = []
        for rulename in _TASK_RULES:
            rule = Rule.ByKeys(name=rulename)
            tasks.extend(rule.getObjects())

        hidden_task_status = ["%d" % status.status
                              for status in [cls.NEW, cls.DISCARDED]]

        sql_condition = ("status NOT IN ({hidden_states})")\
            .format(hidden_states=",".join(hidden_task_status))
        if condition:
            sql_condition = "(%s) AND (%s)" % (sql_condition, condition)

        task_condition = InteractiveTask.cdb_object_id\
            .one_of(*[task.cdb_object_id for task in tasks])
        result = InteractiveTask.Query(task_condition)\
            .Query(sql_condition, order_by="deadline DESC")
        return result

    def GetActivityStreamTopics(self, posting):
        """Topics for Postings"""
        return [
            self,
            self.Process,
            getattr(self, "Project", None),
        ] + [
            parent
            for parent in self.TerminatedParents
        ]

    def set_title(self, ctx=None):
        if not self.title:
            self.title = str(self.mapped_classname)

    def set_responsible(self):
        if not self.subject_id:
            self.subject_id = self.Process.subject_id
            self.subject_type = self.Process.subject_type

    def get_violated_process_start_preconditions(self):
        """
        Checks preconditions for starting the process. If at least one
        precondition is violated, returns a non-empty error message.
        """
        from cdb.platform import gui
        missing_mandatory_fields = []

        extension_obj = self.getExtensionObject()
        errors = []

        if extension_obj:
            missing_mandatory_fields.extend(
                extension_obj.getMissingMandatoryFieldsAtProcessStart())
            try:
                extension_obj.checkProcessStartConditions()
            except TaskDataIncompleteException as e:
                errors.append(str(e))

        if missing_mandatory_fields:
            if len(missing_mandatory_fields) == 1:
                errors.append(
                    gui.Message.GetMessage(
                        "cdbwf_task_mandatory_field",
                        missing_mandatory_fields[0],
                    )
                )
            else:
                errors.append(
                    gui.Message.GetMessage(
                        "cdbwf_task_mandatory_fields",
                        ", ".join(missing_mandatory_fields),
                    )
                )

        return combine_error_messages(errors)

    def check_process_start_preconditions(self):
        """
        Checks preconditions for starting the process. If at least one
        precondition is violated, raises a `TaskDataIncompleteException`.
        """
        errmsg = self.get_violated_process_start_preconditions()

        if errmsg:
            raise TaskDataIncompleteException(errmsg)

    def getExtensionObject(self):
        """
        Get the task extension object instance, if the current task
        is extended. You can overwrite this function if your kind of
        task supports extensions.
        """
        return None

    def sendNotification(self, ctx=None):
        if self.status == self.EXECUTION.status and notification_enabled():
            self.Super(Task).sendNotification(ctx)

    def add_briefcase_to_cycle(self, briefcase):
        if isinstance(self, RunLoopSystemTask):
            existing_briefcases = briefcases.Briefcase.KeywordQuery(
                cdb_process_id=self.CurrentCycle.cdb_process_id,
                name=briefcase.name
            )
            if existing_briefcases:
                return

            vals = {
                "cdb_process_id": self.CurrentCycle.cdb_process_id,
                "name": briefcase.name,
                "briefcase_id": briefcases.Briefcase.new_briefcase_id()
            }
            briefcases.Briefcase.Create(**vals)


class SystemTask(Task):
    __classname__ = "cdbwf_system_task"
    __match__ = fTask.cdb_classname >= __classname__

    Definition = Reference_1(fSystemTaskDefinition, fTask.task_definition_id)

    AllParameters = Reference_N(
        fFilterParameter,
        (fFilterParameter.cdb_process_id == fTask.cdb_process_id) &
        (fFilterParameter.task_id == fTask.task_id)
    )

    Parameters = Reference_N(
        fFilterParameter,
        (fFilterParameter.cdb_process_id == fTask.cdb_process_id) &
        (fFilterParameter.task_id == fTask.task_id) &
        (fFilterParameter.rule_name == "")
    )

    FilterParameters = ReferenceMapping_N(
        fFilterParameter,
        (fFilterParameter.cdb_process_id == fTask.cdb_process_id) &
        (fFilterParameter.task_id == fTask.task_id),
        indexed_by=fFilterParameter.rule_name
    )

    def isRefuseable(self):
        return True

    def _getObjectFilters(self):
        return [f.RuleWrapper for f in self.AllParameters if f.rule_name]

    ObjectFilters = Reference_Methods(Rule, _getObjectFilters)

    event_map = {
        (("create", "copy"), "pre"): ("set_service_user"),
        ("create", "pre"): "set_title"
    }

    def set_service_user(self, ctx):
        from cs.workflow.services import WFServer
        user = WFServer.get_service_user()
        if user not in ["", None, NULL]:
            self.subject_id = user
            self.subject_type = "Person"

    def set_title(self, ctx=None):
        """ Set the title to the name of the System task definition
            in the login language.
        """
        if not self.title:
            self.title = self.Definition.Name[""]

    def get_system_task_icon(self, base_uri=None):
        iconfile = self.Definition.Image
        if iconfile:
            from cs.workflow.designer import wfinterface
            return wfinterface.get_picture_url(iconfile)
        return None

    def _get_icon(self, icon_id, obj, base_uri=None):
        if base_uri is None:
            from cdb import elink
            base_uri = getattr(
                elink.getCurrentRequest(),
                "base_uri",
                "BASE_URI/"
            )

        try:
            result = IconCache.getIcon(
                icon_id,
                accessor=_LabelValueAccessor(obj, True)
            )
        except (KeyError, AttributeError):
            obj_h = obj.ToObjectHandle()
            if obj_h:
                result = IconCache.getIcon(
                    icon_id,
                    accessor=_LabelValueAccessor(obj_h)
                )

        return u"".join([base_uri[:-1], result])

    class EXECUTION(Task.EXECUTION):
        status = 10

        def post(state, self, ctx):  # @NoSelf
            super(SystemTask.EXECUTION, state).post(self, ctx)

            # Send Job to WFQueue
            from cs.workflow import wfqueue
            wfqueue.wfqueue.put(cdb_process_id=self.cdb_process_id,
                                task_id=self.task_id)

    __required_params__ = {
        "cs.workflow.systemtasks.status_change": set(["target_state"]),
        "cs.workflow.systemtasks.generate_info_message": set([
            "subject_id",
            "subject_type",
        ]),
        "cs.workflow.systemtasks.run_loop": set([
            "max_cycles",
            "current_cycle"
        ])
    }
    __required_params_err_msgs__ = {
        "cs.workflow.systemtasks.generate_info_message": (
            "cdbwf_info_no_recipient"
        ),
    }

    def get_violated_process_start_preconditions(self):
        """
        Checks preconditions for starting the process. If at least one
        precondition is violated, returns a non-empty error message.
        """
        errmsg = super(SystemTask,
                       self).get_violated_process_start_preconditions()

        errors = [errmsg] if errmsg else []

        if self.Definition:
            fqpyname = self.Definition.function_fqpyname
        else:
            fqpyname = None
            errors.append(str(util.ErrorMessage(
                "cdbwf_no_task_definition",
                self.GetDescription())))

        # requires exactly one out briefcase
        if (fqpyname == "cs.workflow.systemtasks.copy_objects"
                and len(self.EditBriefcases) != 1):
            errors.append(util.get_label(
                "cdbwf_only_one_out_briefcase") % self.GetDescription())

        # requires global briefcase flag or local briefcase
        if (fqpyname == "cs.workflow.systemtasks.status_change"
                and not self.uses_global_maps
                and not self.Briefcases):
            errors.append(str(util.ErrorMessage(
                "cdbwf_task_no_briefcase", self.GetDescription())))

        parameters = set(self.AllParameters.name)
        missing_parameters = self.__required_params__.get(
            fqpyname, set()).difference(parameters)

        if missing_parameters:
            err_msg = self.__required_params_err_msgs__.get(
                fqpyname, None
            )
            if err_msg:
                error_msg = util.ErrorMessage(err_msg)
            else:
                error_msg = util.ErrorMessage(
                    "cdbwf_missing_parameters",
                    self.GetDescription(),
                    ", ".join(missing_parameters)
                )

            errors.append(str(error_msg))

        return combine_error_messages(errors)


class RunOperationSystemTask(SystemTask):
    __match__ = (
        fTask.cdb_classname >= SystemTask.__classname__ and
        fTask.task_definition_id == "f16b8b40-706e-11e7-9aef-68f7284ff046"
    )

    def _getOperation(self):
        for param in self.Parameters.KeywordQuery(name="operation_name"):
            return fOperation.ByKeys(param.value)

    Operation = ReferenceMethods_1(fOperation, _getOperation)

    def get_system_task_icon(self, base_uri=None):
        op = self.Operation

        if op and op.icon_id:
            return self._get_icon(op.icon_id, op, base_uri)

        return super(RunOperationSystemTask, self).get_system_task_icon()


class RunLoopSystemTask(SystemTask):
    """
    Business logic for "subworkflow/loop". For its runtime implementation, see
    :py:class:`cs.workflow.run_loop.RunLoopSystemTaskImplementation`
    """
    __match__ = (
        fTask.cdb_classname >= SystemTask.__classname__ and
        fTask.task_definition_id == "2df381c0-1416-11e9-823e-605718ab0986"
    )

    Cycles = Reference_N(
        fProcess,
        fProcess.parent_task_object_id == fTask.cdb_object_id,
        order_by=fProcess.current_cycle
    )

    def _getCycle(self):
        cycles = self.Cycles
        if cycles:
            return cycles[-1]
        return None

    CurrentCycle = ReferenceMethods_1(fProcess, _getCycle)

    # behave like review task (refusable)
    def isRefuseable(self):
        return True

    # behave like review task (process carries on after refusal)
    def refuse_task(self, comment=""):
        self.setRefused(comment)

        if self.Parent:
            self.Parent.propagate_done(self)

    def cancel_task(self, comment=""):
        """
        Cancel active cycle after canceling ``self``.
        No new cycle is spawned because of this order.
        """
        super(RunLoopSystemTask, self).cancel_task(comment)
        cycle = self.CurrentCycle

        if cycle and cycle.status == cycle.EXECUTION.status:
            cycle.cancel_process(comment)

    def get_violated_process_start_preconditions(self):
        """
        Extends SystemTask`s implementation to check current cycle.
        """
        errors = [
            super(RunLoopSystemTask, self)
            .get_violated_process_start_preconditions(),
            self.CurrentCycle.get_violated_process_start_preconditions(),
        ]
        return combine_error_messages(errors)

    event_map = {
        (("create", "copy"), "post"): "add_default_parameters",
        ("copy", "post"): "copy_cycle",
        ("modify", "pre"): "remember_old_title",
        ("modify", "post"): "update_cycle_title",
    }

    def add_default_parameters(self, ctx):
        params = {
            # wf-designer: subworkflow completed
            "success_condition": "60fd3480-1eed-11e9-a6c4-68f7284ff046",
            # wf-designer: subworkflow failed
        }
        if ctx.action == "create":
            self.AddParameters(
                max_cycles=1,
                current_cycle=1
            )
            params["failure_condition"] = "7bd6ade1-1eed-11e9-a1ce-68f7284ff046"
        for condition, rule_name in params.items():
            if ctx.cdbtemplate:
                old_task = Task.ByKeys(
                    cdb_process_id=ctx.cdbtemplate.cdb_process_id,
                    task_id=ctx.cdbtemplate.task_id
                )
                c = old_task.AllParameters.KeywordQuery(
                    name=condition
                )
            else:
                c = self.AllParameters.KeywordQuery(
                    name=condition
                )
            if not c:
                args = {}
                args[condition] = "50"
                self.AddParameters(
                    rule_name=rule_name,
                    **args
                )

    def get_cycle_args(self):
        return {
            "parent_task_object_id": self.cdb_object_id,
            "cdb_objektart": self.Process.cdb_objektart,
            "is_template": self.Process.is_template,
            "current_cycle": 1,
            "cdb_project_id": self.Process.cdb_project_id,
            "subject_id": self.Process.subject_id,
            "subject_type": self.Process.subject_type,
        }

    def copy_cycle(self, ctx):
        if ctx.error:
            return

        source = Task.ByKeys(
            task_id=ctx.cdbtemplate.task_id,
            cdb_process_id=ctx.cdbtemplate.cdb_process_id
        )
        if not source.CurrentCycle:
            raise ElementsError(util.ErrorMessage("cdbwf_no_subwf_cycle"))
        with transactions.Transaction():
            try:
                _run(
                    constants.kOperationCopy,
                    source.CurrentCycle,
                    **self.get_cycle_args()
                )
            except ElementsError:
                logging.exception(
                    "Failed to copy cycle '%s' in task '%s', '%s'",
                    source.CurrentCycle.cdb_process_id,
                    source.cdb_process_id,
                    source.task_id,
                )
                raise

    def create_first_cycle(self, template_process_id=None):
        from cs.workflow.processes import Process
        from cs.workflow.run_loop import syncBriefcasesToCycle

        with transactions.Transaction():
            args = self.get_cycle_args()
            if template_process_id:
                new_cycle = Process.CreateFromTemplate(
                    template_process_id,
                    args
                )
            else:
                args["title"] = self.title
                new_cycle = _run(
                    constants.kOperationNew,
                    Process,
                    **args
                )
            if self.Process.isTemplate():
                new_cycle.Update(is_template="1",
                                 cdb_objektart="cdbwf_process_template")
            syncBriefcasesToCycle(self, new_cycle)

        return new_cycle

    def remember_old_title(self, ctx):
        ctx.keep("title_old", ctx.object.title)

    def update_cycle_title(self, ctx):
        """
        Update current cycle's title to reflect self's changed title (only if
        current cycle has not terminated yet).
        """
        if ctx.error:
            return

        old_title = getattr(
            ctx.ue_args,
            "title_old",
            self.title
        )
        cycle = self.CurrentCycle

        if old_title != self.title and cycle and cycle.status in [
                cycle.NEW.status,
                cycle.EXECUTION.status
        ]:
            cycle.Update(title=self.title)

    def get_max_cycles(self):
        for param in self.Parameters.KeywordQuery(name="max_cycles"):
            try:
                return int(param.value)
            except (ValueError, TypeError):
                logging.error(
                    "illegal value for 'max_cycles': '%s'",
                    param.value
                )
        return None

    def get_system_task_icon(self, base_uri=None):
        if self.get_max_cycles() == 1:
            return self.Process.GetObjectIcon()

        return self._get_icon("loop_cycles", self, base_uri)

    def on_relship_copy_post(self, ctx):
        from cs.workflow.processes import Process
        if (ctx.relationship_name == 'cdbwf_system_task2all_parameters'
                and self.Process.status != Process.EXECUTION.status):
            cc = self.AllParameters.KeywordQuery(
                name="current_cycle"
            )
            if cc:
                cc[0].ModifyParameter(value="1")


class InteractiveTask(Task, WithSharing, WorkflowTaskWithCsTasks):
    __classname__ = "cdbwf_interactive_task"
    __match__ = fTask.cdb_classname >= __classname__
    # allowed target statuses for interactive status change (e.g. from taskmanager)
    __status_whitelist__ = [Task.COMPLETED.status, Task.REJECTED.status]

    event_map = {
        (("create", "copy", "modify"), "pre_mask"): ("set_responsible_mandatory"),
        ("modify", "pre"): "check_modification_pre",
        ("modify", "post"): ("check_modification_post", "activity_posting"),
        ("modify", "final"): "check_modification_final",
        ("create", "post"): "check_extension_title",
        ("cdbwf_close_task", "pre_mask"): "handle_comment_mandatory",
        ("cdbwf_refuse_task", "pre_mask"): "handle_comment_mandatory",
        ("cs_tasks_delegate", "pre_mask"): "keep_old_subject",
        ("cs_tasks_delegate", "post"): ("log_new_subject", "check_modification_post"),
        ("cs_tasks_delegate", "final"): "check_modification_final",
        ("cdbwf_CDB_Workflow", "pre_mask"): "handle_comment_mandatory",
        ("cdbwf_CDB_Workflow", "now"): "op_status_change",
    }

    def op_status_change(self, ctx):
        target_status = int(ctx.dialog.zielstatus_int)  # might raise TypeError or ValueError
        followup = {
            self.COMPLETED.status: "cdbwf_close_task",
            self.REJECTED.status: "cdbwf_refuse_task",
        }
        operation_name = followup[target_status]  # might raise KeyError
        # _run might raise TypeError or ElementsError
        _run(operation_name, self, remark=ctx.dialog.remark)

    def activity_posting(self, ctx):
        if self.status == self.EXECUTION.status:
            if ctx.error:
                return
            old = {
                "subject_id": ctx.ue_args["subject_id_old"],
                "subject_type": ctx.ue_args["subject_type_old"]
                }
            new = {
                "subject_id": ctx.dialog.subject_id,
                "subject_type": ctx.dialog.subject_type,
            }
            super(InteractiveTask, self)._csTasksDelegatePost(ctx, old, new)

    def keep_old_subject(self, ctx):
        ctx.keep("subject_id_old", self.subject_id)
        ctx.keep("subject_type_old", self.subject_type)

    def log_new_subject(self, ctx):
        msgs = []
        ctx.object = ctx.dialog

        old_subject_id = getattr(ctx.ue_args, "subject_id_old", None)
        old_subject_type = getattr(ctx.ue_args, "subject_type_old", None)

        if old_subject_id and old_subject_type:
            new_subject_id = self.subject_id
            new_subject_type = self.subject_type

            if old_subject_id != new_subject_id:
                msgs.append("%s: %s -> %s" % ("subject_id",
                                                old_subject_id,
                                                new_subject_id))

            if old_subject_type != new_subject_type:
                msgs.append("%s: %s -> %s" % ("subject_type",
                                                old_subject_type,
                                                new_subject_type))

        if msgs:
            self.addProtocol("[Task modified] \n" + "\n".join(msgs))

    def handle_comment_mandatory(self, ctx):
        if self.requiresComment():
            ctx.set_mandatory("remark")

    # if following attributes of an active task get changed, then the task
    # responsibles get directly notified about it via mail/protocol
    NOTIFIABLE_ATTRS = ["subject_id", "subject_type",
                        "deadline", "max_duration"]

    def get_violated_process_start_preconditions(self):
        """
        Checks preconditions for starting the process. If at least one
        precondition is violated, returns a non-empty error message.
        """
        errors = [
            super(InteractiveTask, self)
            .get_violated_process_start_preconditions(),
        ]

        if not self.Subject:
            from cdb.platform import gui
            errors.append(
                gui.Message.GetMessage(
                    "cdbwf_task_mandatory_field",
                    util.get_label("cdbwf_ahwf_27"),
                )
            )

        return combine_error_messages(errors)

    @classmethod
    def get_running_tasks_by_briefcase(cls, briefcase):
        """
        Find out which running tasks are linked with a
        given briefcase.

        :return: a list of tasks
        """
        tasks = []
        for briefcase_link in briefcase.Links:
            task = briefcase_link.Task
            if task:
                if task.status == task.EXECUTION.status:
                    tasks.append(task)
            else:
                # *global* briefcase
                tasks.extend(InteractiveTask.Query(
                    "cdb_process_id = '%s' AND status = '%s'" %
                    (briefcase_link.cdb_process_id, InteractiveTask.EXECUTION.status)))
        return tasks

    def check_modification_pre(self, ctx):
        # keep some old values for the diffing in the 'post' event
        for attr in self.NOTIFIABLE_ATTRS:
            ctx.keep(CTX_OLD % attr, getattr(ctx.object, attr))
        if self.status == self.EXECUTION.status:
            # fields not in NOTIFIABLE_ATTRS should not be modified
            # if the task is already in execution
            unknown_attrs = set(ctx.dialog.get_attribute_names()) -\
                set(self.NOTIFIABLE_ATTRS)
            clsdef = self.GetClassDef()
            fields = self.GetFieldNames()
            for attr in unknown_attrs:
                if attr not in fields and\
                   not clsdef.getFacetAttributeDefinition(attr):
                    continue
                dval = getattr(ctx.dialog, attr)
                oval = getattr(ctx.object, attr)
                if attr == "position":
                    try:
                        if float(dval) == float(oval):
                            continue
                    except Exception:
                        pass
                if dval != oval:
                    raise util.ErrorMessage("cdbwf_modify_ready_task")

    def check_modification_post(self, ctx):
        from cdb.platform.mom.fields import DDField
        changed_attrs = {}
        for attr in self.NOTIFIABLE_ATTRS:
            if hasattr(ctx.ue_args, CTX_OLD % attr) and hasattr(ctx.object, attr):
                old_value = getattr(ctx.ue_args, CTX_OLD % attr)
                new_value = getattr(ctx.object, attr)
                if old_value != new_value:
                    setattr(ctx, "modified_task_attrs", changed_attrs)
                    field = DDField.ByKeys("cdbwf_process_component", attr)
                    changed_attrs[attr] = {"label": field.getLabel(),
                                           "value": new_value}
                    if attr == "subject_id":
                        # special case when changing task responsibles:
                        # also inform the old one(s) about losing the responsibility
                        if hasattr(ctx.ue_args, "subject_type_old"):
                            self.subject_type = getattr(ctx.ue_args, "subject_type_old")
                        self.subject_id = old_value
                        self.sendNotification(ctx)
                        if hasattr(ctx.ue_args, "subject_type_old"):
                            self.subject_type = getattr(ctx.object, "subject_type")
                        self.subject_id = new_value
        if changed_attrs:
            ctx.keep('modified_task_attrs', json.dumps(changed_attrs))

    def check_modification_final(self, ctx):
        if hasattr(ctx.ue_args, 'modified_task_attrs'):
            modified_task_attrs = json.loads(getattr(ctx.ue_args, 'modified_task_attrs'))
            # don't send the notification in the 'post' event,
            # since it might result in wrong mail receivers
            setattr(ctx, "modified_task_attrs", modified_task_attrs)
            self.sendNotification(ctx)

    def set_responsible_mandatory(self, ctx):
        # If process is already running, a responsible must be specified
        from cs.workflow.processes import Process
        if self.Process and self.Process.status == Process.EXECUTION.status:
            ctx.set_mandatory("mapped_subject_name")

    # == Email notification ==
    def getNotificationTemplateName(self, ctx=None):
        if not ctx or hasattr(ctx, "task_delegated"):
            # no ctx object means default case (task set ready)
            return "cdbwf_task_ready.html"
        elif hasattr(ctx, "modified_task_attrs"):
            return "cdbwf_task_modified.html"
        elif hasattr(ctx, "content_change_bobject"):
            return "cdbwf_content_change.html"
        else:
            raise util.ErrorMessage(
                "just_a_replacement",
                UNSUPPORTED_CONTEXT_TYPE
            )

    def setNotificationContext(self, sc, ctx=None):
        sc.ctx = ctx
        sender = User.ByKeys(personalnummer=auth.persno)
        sc.sender_firstname = str(sender.firstname)
        sc.sender_lastname = str(sender.lastname)

        sc.action_url = get_object_url(self)
        sc.task_title = self.title
        sc.get_url = get_object_url
        sc.task_desc = self.description

        sc.wf_title = str(self.Process.title)
        project = getattr(self, "Project", None)
        if project:
            sc.project_name = str(project.project_name)

        if not ctx or hasattr(ctx, "task_delegated"):
            # cdbwf_task_ready.html
            pass
        elif hasattr(ctx, "modified_task_attrs"):
            # cdbwf_task_modified.html
            sc.modified_attrs = [
                {
                    "label": str(attr["label"]),
                    "value": str(attr["value"]),
                }
                for attr in ctx.modified_task_attrs.values()
            ]
        elif hasattr(ctx, "content_change_bobject"):
            # cdbwf_content_change.html
            changed_file = getattr(ctx, "content_change_file", None)
            if changed_file:
                sc.changed_file_desc = str(
                    changed_file.GetDescription()
                )
            changed_obj = getattr(ctx, "content_change_bobject", None)
            if changed_obj:
                sc.changed_obj_desc = str(
                    changed_obj.GetDescription()
                )

        all_briefcases = self.Briefcases + self.Process.Briefcases
        for briefcase in all_briefcases:
            if briefcase.Content:
                # don't show the briefcase group at all in the notification
                # when there's no content anyway
                sc.briefcases = all_briefcases
                break

    def getNotificationTitle(self, ctx=None):
        # Advantages of the eval workaround for cdb labels below:
        # 1) able to omit 'self.'
        # 2) able to access all attributes of the object
        # Example:
        # '"CIM DATABASE - Task ready: " + title + " / " + Process.title' +
        # ((" / " + Project.project_name) if (has_key("Project") and Project) else "")
        eval_dict = {}
        for attr_name in dir(self):
            eval_dict[attr_name] = getattr(self, attr_name)
        if not ctx or hasattr(ctx, "task_delegated"):
            # no ctx object means default case (task set ready)
            prefix = "cdbwf_notification_title_prefix_task_ready"
        elif hasattr(ctx, "modified_task_attrs"):
            prefix = "cdbwf_notification_title_prefix_task_modified"
        elif hasattr(ctx, "content_change_bobject"):
            prefix = "cdbwf_notification_title_prefix_content_change"
        else:
            raise util.ErrorMessage(
                "just_a_replacement",
                UNSUPPORTED_CONTEXT_TYPE
            )

        prefix = eval(util.get_label(prefix), globals(), eval_dict)
        suffix = eval(util.get_label("cdbwf_notification_title_suffix"), globals(), eval_dict)
        return "%s %s" % (prefix, suffix)

    def getNotificationSender(self, ctx=None):
        if ctx:
            # cases: -task modified
            #        -document added or removed
            #        -object changed
            #        - task delegated
            current_pers = User.ByKeys(personalnummer=auth.persno)
            sender_mail = current_pers.e_mail
            sender_name = current_pers.name
        else:
            # cases: - task set ready
            responsible_pers = self.Process.StartedBy

            if not (responsible_pers and responsible_pers.e_mail):
                logging.error(util.ErrorMessage("cdbwf_no_wf_starter"))
                return ("", "")

            sender_mail = responsible_pers.e_mail
            sender_name = responsible_pers.name
        return (sender_mail, sender_name)

    def isNotificationReceiver(self, pers, ctx):
        # exclude the task responsible(s) in some cases
        # no ctx object means default case (task set ready)
        if ctx:
            task_changed = hasattr(ctx, "modified_task_attrs")
            content_changed = hasattr(ctx, "content_change_bobject")
            task_delegated = hasattr(ctx, "task_delegated")

            if any([task_changed, content_changed, task_delegated]):
                if getattr(pers, 'personalnummer', None) == auth.persno:
                    # operation was triggered by this person.. exclude him
                    return False
            else:
                raise util.ErrorMessage(
                    "just_a_replacement",
                    UNSUPPORTED_CONTEXT_TYPE
                )

        return all([
            # TODO wait for public API (E043114)
            pers.active_account == "1",
            pers.email_notification_task(),
        ])

    def getNotificationReceiver(self, ctx=None):
        rcvr = {}
        if self.Subject:
            for pers in self.Subject.getPersons():
                if self.isNotificationReceiver(pers, ctx):
                    tolist = rcvr.setdefault("to", set())
                    # send the notification the the responsible
                    tolist.add((pers.e_mail, pers.name))
                    # if the responsible is absent send the notification to substitutes as well
                    if pers.is_absent() and self.subject_type == "Person":
                        substitutes = UserSubstitute.get_substitutes(pers.personalnummer)
                        for substitute in substitutes:
                            user = User.ByKeys(substitute)
                            tolist.add((user.e_mail, user.name))

        # if not ctx: 'task ready' notification - wf owners never get a copy
        if ctx and not "wf_owner_ok" in ctx.ue_args.get_attribute_names():
            # flag "wf_owner_ok" ensures only a single mail is sent even
            # for operations triggering multiple sendNotification calls
            # (e.g. content changes)
            for pers in self.Process.Subject.getPersons():
                # always include wf owners if they didn't trigger the operation

                if pers.email_notification_task() and \
                (pers.personalnummer != auth.persno):
                    tolist = rcvr.setdefault("cc", set())
                    tolist.add((pers.e_mail, pers.name))

            ctx.keep("wf_owner_ok", True)

        return [rcvr]
    # == End email notification ==

    @classmethod
    def getPossibleExtensions(cls):
        """
        Get the possible extension types for the current task type.

        :return: a list of dictionary with keys `label` and `classname`  of
                 each available extension type.
        """
        result = []
        from cs.workflow.extensions import ExtensionAssignment
        assignments = ExtensionAssignment.getAssignments(cls._getClassDef())
        for asgn in assignments:
            ext_cls = get_object_class_by_name(asgn.extension_cdb_classname)
            if not ext_cls:
                continue
            label = ""
            if getattr(ext_cls, "getExtensionTypeDescription"):
                label = ext_cls.getExtensionTypeDescription()
            if label:
                result.append(dict(label=label,
                                   classname=asgn.extension_cdb_classname))
        return result

    def getExtensionObject(self):
        """
        Get the task extension object instance, if the current task
        is extended.
        """
        if not self.cdb_extension_class:
            return None
        ext_cls = get_object_class_by_name(self.cdb_extension_class)
        if not ext_cls:
            return None
        return ext_cls.ByKeys(cdb_process_id=self.cdb_process_id,
                              task_id=self.task_id)

    def check_extension_title(self, ctx):
        if self.title:
            return
        extension = self.getExtensionObject()
        if extension:
            self.getPersistentObject().title = extension.getTaskTitle()


class ExecutionTask(InteractiveTask):
    __classname__ = "cdbwf_task_execution"
    __match__ = fTask.cdb_classname >= __classname__


class ApprovalTask(InteractiveTask):
    __classname__ = "cdbwf_task_approval"
    __match__ = fTask.cdb_classname >= __classname__

    def isRefuseable(self):
        return True

    def requiresComment(self):
        return True

    def isForwardable(self):
        return self.finish_option and self.Next \
            and self.Parent.is_sequential()


class ExaminationTask(InteractiveTask):
    __classname__ = "cdbwf_task_examination"
    __match__ = fTask.cdb_classname >= __classname__

    def isRefuseable(self):
        return True

    def requiresComment(self):
        return True

    def isForwardable(self):
        return self.finish_option and self.Next \
            and self.Parent.is_sequential()

    def refuse_task(self, comment=""):
        self.setRefused(comment)

        if self.Parent:
            self.Parent.propagate_done(self)


class FilterParameter(Object, WithRuleWrapper):
    __maps_to__ = "cdbwf_filter_parameter"
    __classname__ = "cdbwf_filter_parameter"

    def _get_rule_object_id(self):
        return self.rule_name

    Task = TaskGroup = Reference_1(fTask, fFilterParameter.task_id, fTask.cdb_process_id)


# obsolete status classes
Task.READY = Task.EXECUTION
Task.DONE = Task.COMPLETED
Task.REFUSED = Task.REJECTED
Task.CANCELLED = Task.DISCARDED
