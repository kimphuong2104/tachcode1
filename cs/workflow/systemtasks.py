#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module systemtasks

This is the documentation for the systemtasks module.
"""

import logging
import cdbwrapc
import isodate
import os
from collections import defaultdict
from collections import namedtuple

from cdb import constants
from cdb import CADDOK
from cdb import ElementsError
from cdb import sqlapi
from cdb import typeconversion
from cdb import util

from cdb.lru_cache import lru_cache
from cdb.objects import common
from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import LocalizedField
from cdb.objects import org
from cdb.objects import operations
from cdb.platform import gui
from cdb.platform.mom import SimpleArguments
from cdb.platform.mom.operations import OperationConfig
from cs.platform.web.rest.generic.model import Workflow
from cs.sharing.share_objects import WithSharing
from cs.workflow import protocols
from cs.workflow.briefcases import BriefcaseContentWhitelist, FolderContent
from cs.workflow.forms import Form
from cs.workflow.forms import TaskWithForm
from cs.workflow.misc import notification_enabled
def notification_enabled():
    return False
from cs.workflow.misc import get_object_url
from cs.workflow.misc import get_email_language
from cs.workflow.tasks_plugin import WorkflowInfoMessageWithCsTasks

acs = None
CREATE_OPERATIONS = set(["CDB_Create", "CDB_Copy", "CDB_Index"])


def deferred_import_acs():
    # import only when needed so cdb.acs does not need to be distributed to
    # high-security environments
    from cdb import acs  # @UnusedImport # noqa


__all__ = [
    'STATUS_CHANGE_UNLOCK',
    'abort_process',
    'CloseTaskAsynchronously',
    'convert_files',
    'copy_objects',
    'create_new_index',
    'generate_info_message',
    'InfoMessage',
    'ParameterDefinition',
    'ProcessCompletedException',
    'ProcessAbortedException',
    'status_change',
    'SystemTaskDefinition',
    'TaskCancelledException',
    'TaskRefusedException',
]

STATUS_CHANGE_UNLOCK = "cs.workflow.status_change_unlock"

fParameterDefinition = Forward(__name__ + ".ParameterDefinition")
fSystemTaskDefinition = Forward(__name__ + ".SystemTaskDefinition")

fProcess = Forward("cs.workflow.processes.Process")
fTask = Forward("cs.workflow.tasks.Task")
fInfoMessage = Forward(__name__ + ".InfoMessage")
fCDB_File = Forward("cdb.objects.cdb_file.CDB_File")


def get_wfqueue_logger():
    from cs.workflow import wfqueue  # late import because of DB conn
    return wfqueue.getLogger()


# ===============================================================================
# Object Framework classes
# ===============================================================================

class SystemTaskDefinition(Object):
    __maps_to__ = "cdbwf_system_task_definition"
    __classname__ = "cdbwf_system_task_definition"

    Parameters = Reference_N(
        fParameterDefinition,
        fParameterDefinition.task_definition_id == fSystemTaskDefinition.cdb_object_id,
    )

    Images = Reference_N(fCDB_File,
                         fCDB_File.cdbf_object_id == fSystemTaskDefinition.cdb_object_id)

    def _getImage(self):
        if self.Images:
            return self.Images[0]
        else:
            return None

    Image = ReferenceMethods_1(fCDB_File, _getImage)

    Name = LocalizedField("name")


class ParameterDefinition(Object):
    __maps_to__ = "cdbwf_parameter_definition"
    __classname__ = "cdbwf_parameter_definition"

    SystemTaskDefinition = Reference_1(
        fSystemTaskDefinition,
        fParameterDefinition.task_definition_id
    )


# ===============================================================================
# Exceptions used for communication with the wfqueue service
# ===============================================================================

class TaskCancelledException(Exception):
    """
    Exception raised by custom methods to cancel the current task
    """
    pass


class TaskRefusedException(Exception):
    """
    Exception raised by custom methods to refuse the current task
    """
    pass


class ProcessPausedException(Exception):
    """
    Exception raised by custom methods to pause the current process
    """
    pass


class ProcessCompletedException(Exception):
    """
    Exception raised by custom methods to complete the current process
    """
    pass


class ProcessAbortedException(Exception):
    """
    Exception raised by custom methods to abort the current process
    """
    pass


class CloseTaskAsynchronously(Exception):
    """
    Exception raised by methods, which need to close the workflow task
    asynchronously (such as convert tasks)
    """
    pass


# ===============================================================================
# System tasks implementations
# ===============================================================================

@lru_cache(maxsize=10, clear_after_ue=True)
def get_status_change_unlock_param(classname):
    allowed = set([cdbwrapc.kNoUnlock,
                   cdbwrapc.kUnlockIfLockOwner,
                   cdbwrapc.kUnlockIfGranted])

    try:
        configured_value = util.PersSettings().getValue(
            STATUS_CHANGE_UNLOCK, classname)
    except KeyError:
        return None

    # raises TypeError or ValueError if value is not an integer!
    if int(configured_value) in allowed:
        return int(configured_value)

    return None


def check_status_transition(obj, target_status):
    if not obj.GetObjectKind():
        return False

    wf = Workflow(obj)
    return target_status in [
        status
        for status, _ in wf.next_steps()
    ]


def status_change(task, content, target_state):
    """ Changes the state of all objects into target_state.
    """
    if isinstance(target_state, list):
        task.addProtocol(
            str(
                util.get_label("cdbwf_system_task_ignr_addit_status")
            ).format(target_state[1:]),
            msgtype=protocols.MSGSYSTEM)
        target_state = int(target_state[0])
    else:
        target_state = int(target_state)

    all_objects = set(content["info"] + content["edit"])

    missing_transitions = [
        obj.GetDescription()
        for obj in all_objects
        if not check_status_transition(obj, target_state)
    ]
    if missing_transitions:
        msg = str(util.ErrorMessage("workflow_no_auth")).replace("\\n", "\n")
        missing_transitions = "\n- ".join(missing_transitions)
        raise RuntimeError(f"{msg}\n\n- {missing_transitions}")

    for obj in all_objects:
        unlock = get_status_change_unlock_param(obj.GetClassname())
        if unlock is None:
            obj.ChangeState(target_state)
        else:
            obj.ChangeState(target_state, unlock=unlock)


def copy_objects(task, content):
    """Copy all objects in content["info"] and put them in the "edit" briefcase"""

    # This task requires exactly one out briefcase
    if len(task.EditBriefcases) != 1:
        msg = util.get_label("cdbwf_only_one_out_briefcase") % task.GetDescription()
        raise RuntimeError(msg)

    briefcase = task.EditBriefcases[0]

    for obj in content["info"]:
        copyobj = operations.operation(
            constants.kOperationCopy,  # @UndefinedVariable
            obj)

        # unlock new object
        try:
            cd = obj.GetClassDef()
            if constants.kOperationUnlock in [oi.get_opname() for oi in cd.getOperationInfos()]:
                operations.operation(constants.kOperationUnlock, copyobj)  # @UndefinedVariable
        except RuntimeError:
            task.addProtocol(
                str(
                    util.get_label("cdbwf_cannot_unlock_object")
                ) % obj.GetDescription(),
                msgtype=protocols.MSGINFO
            )
            get_wfqueue_logger().exception("unlock before copy_objects failed")

        operations.operation(constants.kOperationNew,  # @UndefinedVariable
                             FolderContent,
                             cdb_folder_id=briefcase.cdb_object_id,
                             cdb_content_id=copyobj.cdb_object_id)


def create_new_index(task, content):
    """ Create a new index of all objects in content["info"] and puts
        the new indexes in the "edit" briefcase
    """
    # This task requires exactly one out briefcase
    if len(task.EditBriefcases) != 1:
        msg = util.get_label("cdbwf_only_one_out_briefcase") % task.GetDescription()
        raise RuntimeError(msg)

    briefcase = task.EditBriefcases[0]

    for obj in content["info"]:
        newindex = operations.operation(
            constants.kOperationIndex,  # @UndefinedVariable
            obj)

        operations.operation(constants.kOperationNew,  # @UndefinedVariable
                             FolderContent,
                             cdb_folder_id=briefcase.cdb_object_id,
                             cdb_content_id=newindex.cdb_object_id)


def complete_process(task, content):
    msg = util.get_label("cdbwf_process_done_by") % task.GetDescription()
    raise ProcessCompletedException(msg)


def abort_process(task, content):
    msg = util.get_label("cdbwf_process_aborted_by") % task.GetDescription()
    raise ProcessAbortedException(msg)


def run_loop(task, content, **kwargs):
    from cs.workflow.run_loop import RunLoopSystemTaskImplementation
    systask_impl = RunLoopSystemTaskImplementation(
        task,
        kwargs["current_cycle"],
        kwargs["max_cycles"]
    )
    systask_impl.run()


# Information task
class InfoMessage(org.WithSubject, common.WithEmailNotification, WithSharing,
                  WorkflowInfoMessageWithCsTasks, TaskWithForm):
    __maps_to__ = "cdbwf_info_message"
    __classname__ = "cdbwf_info_message"

    _EMAIL_TEMPLATE = "cdbwf_info_message.html"
    __notification_template_folder__ = os.path.join(
        os.path.dirname(__file__),
        "chrome",
    )

    Process = Reference_1(fProcess, fInfoMessage.cdb_process_id)
    RootProcess = ReferenceMethods_1(fProcess, lambda t: t.Process.RootProcess)
    Task = Reference_1(fTask,
                       fInfoMessage.cdb_process_id == fTask.cdb_process_id,
                       fInfoMessage.task_id == fTask.task_id)

    @classmethod
    def on_cdbwf_mark_read_now(cls, ctx):
        for message in cls.PersistentObjectsFromContext(ctx):
            message.Update(is_active=0)

    def sendNotification(self, ctx=None):
        if self.is_active and notification_enabled():
            self.Super(InfoMessage).sendNotification(ctx)

    def getNotificationTitle(self, ctx):
        title = self.Process.title if self.Process else ''
        label = gui.Label.ByKeys("cdbwf_info_message_email_title")
        msg = label.Text[get_email_language(self.Subject)]
        return f"{msg}: {title}"

    def getNotificationTemplateName(self, ctx):
        return self._EMAIL_TEMPLATE

    def isNotificationReceiver(self, pers, ctx):
        return all([
            pers.active_account == "1",
            pers.e_mail,
            pers.getSettingValue("user.email_wf_info") == "1",
        ])

    def getNotificationReceiver(self, ctx):
        tolist = []
        subject = self.Subject

        if isinstance(subject, org.AbstractRole):
            persons = subject.Persons
        else:
            persons = [subject]

        for person in persons:
            if self.isNotificationReceiver(person, ctx):
                tolist.append((person.e_mail, person.name))
        return [{"to": tolist}]

    # customisable
    def setNotificationContext(self, sc, ctx=None):
        task_link = get_object_url(self)
        sc.task_manager_url = task_link  # deprecated
        sc.action_url = task_link

        sc.get_url = get_object_url
        sc.message_title = str(self.title)
        sc.message_desc = str(self.description)

        if self.Process:
            sc.wf_title = str(self.Process.title)

        if self.Task:
            project = getattr(self.Task, "Project", None)

            if project:
                sc.project_name = str(project.project_name)

            briefcases = self.Task.Briefcases + self.Task.Process.Briefcases
            for briefcase in briefcases:
                if briefcase.Content:
                    # don't show the briefcase group at all in the notification
                    # when there's no content anyway
                    sc.briefcases = briefcases
                    break

    def _getForms(self, iotype):
        result = [x for x in self.Task.getContent(iotype) if isinstance(x, Form)]
        if self.Process:
            result += [x for x in self.Process.getContent(iotype)
                       if isinstance(x, Form)]
        return result

    event_map = {('create', 'post'): 'sendNotification'}


def generate_info_message(task, content, **args):
    # args contains already the attributes
    # cdb_project_id, subject_id, subject_type

    subject_type = args["subject_type"]
    subject_id = args["subject_id"]

    if subject_type in {"Common Role", "PCS Role"}:
        # fetch the role object
        if subject_type == "Common Role":
            from cdb.objects.org import CommonRole
            role = CommonRole.ByKeys(role_id=subject_id)
        else:
            from cs.pcs.projects import Role
            role = Role.ByKeys(cdb_project_id=task.cdb_project_id,
                               role_id=subject_id)

        # generate one object for every owner
        if role:
            for owner in role.Owners:
                owner_args = dict(args, **{"subject_id": owner.personalnummer,
                                           "subject_type": "Person"})
                generate_info_message(task, content, **owner_args)
    elif subject_type == "Person":
        kwargs = {"is_active": 1,
                  "cdb_process_id": task.cdb_process_id,
                  "cdb_project_id": task.cdb_project_id,
                  "task_id": task.task_id,
                  "title": task.title,
                  "description": task.description}
        kwargs.update(args)

        # creating the info message will send the notification
        operations.operation("CDB_Create", InfoMessage, **kwargs)


# Run Operation task
OPERATION_CONFIG = namedtuple(
    "operation_config",
    ["meta", "cdef_classnames", "obj_classnames"]
)
INDEXED_CONTENT = namedtuple(
    "indexed_content",
    ["keys", "object_list_by_classname"]
)


def get_form_data(content):
    """
    Read values additively from all Form objects in info, then edit content
    (overwriting any duplicate keys).

    Returns tuple (target, target_name, values) for read values. See
    ``get_operation_context`` for further information on return value.

    Mask attributes configured as dates are not returned as strings, but
    ``datetime`` objects.
    """
    values = {}

    def _update_values(objs):
        for obj in objs:
            if isinstance(obj, Form):
                values.update(
                    obj.read_data(
                        convert_dates=True
                    )
                )

    _update_values(content["info"])
    _update_values(content["edit"])

    return values


def convert_form_data(target, form_data):
    """
    :param target: Classname of object to convert ``form_data`` for.
    :type target: six.string_types or ``cdb.objects.Object``

    :param form_data: Data read from a form containing both ISO date strings
        and ``datetime`` objects in date fields.
    :type form_data: dict

    :returns: Converted ``form_data`` containing legacy date strings.
    :rtype: dict
    """
    result = dict(form_data)

    if hasattr(target, "GetClassDef"):
        cdef = target.GetClassDef()
    else:
        cdef = cdbwrapc.CDBClassDef(target)

    for attribute_def in cdef.getAttributeDefs():
        name = attribute_def.getName()

        try:
            value = result[name]
        except KeyError:
            continue

        try:
            sql_type = attribute_def.getSQLType()
        except ElementsError:
            # fields with complex data, such as long text
            logging.warning(
                "treating unknown form field '%s' as text (value '%s')",
                name, value,
            )
            sql_type = sqlapi.SQL_CHAR

        if sql_type == sqlapi.SQL_DATE:
            if value:
                # value is either
                # - isostring (preset from bc contents, but not in mask),
                # - date or datetime (date field in mask)
                if isinstance(value, str):
                    dt = isodate.parse_datetime(value)
                else:
                    dt = value
                result[name] = typeconversion.to_legacy_date_format(dt)
            else:
                del result[name]

    return result


def get_operation_config(operation_name):
    """
    Returns a three-tuple ``(meta, cdef_classnames, obj_classnames)``:

    :guilabel:`meta`
        Bool. If ``True``, at least one operation configuration with
        applicability ``Meta`` exists for given ``operation_name``.

    :guilabel:`cdef_classnames`
        Set of classnames with applicability ``Class`` for given
        ``operation_name``. The classname ``cdbwf_form`` is never included.

    :guilabel:`obj_classnames`
        Set of classnames with applicability other than ``Meta`` and ``Class``
        for given ``operation_name``. The classname ``cdbwf_form`` is never
        included.
    """
    meta = False
    cdef_classnames = set()
    obj_classnames = set()

    for conf in OperationConfig.KeywordQuery(name=operation_name):
        applicability = conf.applicability

        if applicability == constants.kOpApplicabilityMeta:
            meta = True

        elif applicability == constants.kOpApplicabilityClassDef:
            cdef_classnames.add(conf.classname)

        else:
            obj_classnames.add(conf.classname)

    # ignore "cdbwf_form"
    form_class = set([Form.__classname__])
    cdef_classnames.difference_update(form_class)
    obj_classnames.difference_update(form_class)

    return OPERATION_CONFIG(meta, cdef_classnames, obj_classnames)


def index_content_by_classname(object_list):
    """
    Returns a two-tuple ``keys``, ``object_list_by_classname``:

    :guilabel:`keys`
        Set of all classnames of objects in list ``object_list``.

    :guilabel:`object_list_by_classname`
        Dict containing lists of objects from ``object_list`` indexed by
        classname.
    """
    result = defaultdict(list)

    for obj in object_list:
        result[obj.GetClassname()].append(obj)

    return INDEXED_CONTENT(set(result.keys()), result)


def run_operation(task, content, operation_name):
    """
    :guilabel:`task`
        The workflow task calling this function.

    :guilabel:`content`
        Briefcase contents of task indexed by iotype (``info``, ``edit``).

    :guilabel:`operation_name`
        Name of the operation to run.

    Runs the operation named ``operation_name`` using values additively read
    from all forms attached to this task's briefcases.

    .. warning::
        Make sure forms do not overlap when using multiple forms. They are
        applied in natural order (e.g. no user-controlled order), although
        EditForms are applied after InfoForms, effectively overwriting any
        conflicting values.

    If at least one operation configuration for given ``operation_name`` with
    applicability ``Meta`` exists, the operation is run once without context.

    For each other operation configuration for given ``operation_name``, the
    operation is run:

    - Once for each distinct classname of objects in content["edit"] (except
      for ``cdbwf_form``) if an operation configuation for given
      ``operation_name``, classname and applicability ``Class`` exists.
    - Once for each non-form object in content["edit"] if an operation
      configuation for given ``operation_name``, object's classname and
      applicability other than ``Meta`` and ``Class`` exists.
    """
    op_config = get_operation_config(operation_name)
    form_data = get_form_data(content)
    edit_content = index_content_by_classname(
        content["edit"] + content["info"],
    )

    def _run_op(operation_name, target, _form_data):
        if isinstance(_form_data, SimpleArguments):
            return operations.operation(
                operation_name,
                target,
                _form_data
            )
        else:
            return operations.operation(
                operation_name,
                target,
                **_form_data
            )

    def run_op(target, description, _form_data):
        queue_logger = get_wfqueue_logger()

        def _simple_arg_sort_key(x):
            tokens = x.name.split(".", 1)
            if len(tokens) == 1:
                return "", tokens[0]
            return tokens

        if isinstance(_form_data, SimpleArguments):
            sorted_args = list(_form_data.iterator())
            sorted_args.sort(key=_simple_arg_sort_key)
            serialized_form_data = "\n".join([
                f"  {simple_arg.name}={simple_arg.value}"
                for simple_arg in sorted_args
            ])
        else:
            serialized_form_data = str(_form_data)

        task.addProtocol(
            util.get_label("cdbwf_run_operation_now") % (
                operation_name,
                description,
                serialized_form_data.replace("\n  ", ", ")
            ),
            msgtype=protocols.MSGINFO
        )
        queue_logger.info(
            "Operation paramters:\n%s",
            serialized_form_data,
        )
        try:
            return _run_op(operation_name, target, _form_data)
        except (ValueError, TypeError, ElementsError) as err:
            queue_logger.exception("run_operation failed")
            queue_logger.error("Operation paramters:\n%s", serialized_form_data)
            task.addProtocol(
                util.get_label("cdbwf_run_operation_failed") % (
                    str(err)
                ),
                msgtype=protocols.MSGSYSTEM
            )
            if isinstance(err, ElementsError):
                # ElementsError is a RuntimeError, so just re-raise it
                raise
            raise RuntimeError(str(err)) from err

    def prepare_form_data(target, description, _form_data):
        if target:
            return operations.form_input(
                target,
                **convert_form_data(target, _form_data)
            )
        return _form_data

    def attach_created_objects_wf(objects, task):
        for obj in objects:
            obj_id = obj.GetObjectID()
            if task.Briefcases:
                for briefcase in task.Briefcases:
                    briefcase.AddObject(obj_id)
            else:
                # No briefcase check added here becase a system
                # task without any briefcase can not work at all.
                briefcase = task.Process.Briefcases[0]
                briefcase.AddObject(obj_id)

    if op_config.meta:
        return run_op(None, "Meta", form_data)  # None for Meta ops

    result = []

    for classname in edit_content.keys.intersection(op_config.cdef_classnames):
        for obj in edit_content.object_list_by_classname[classname]:
            description = f"Class '{classname}'"
            _form_data = prepare_form_data(classname, description, form_data)
            result.append(run_op(classname, description, _form_data))

    for classname in edit_content.keys.intersection(op_config.obj_classnames):
        for obj in edit_content.object_list_by_classname[classname]:
            description = obj.GetDescription()
            _form_data = prepare_form_data(obj, description, form_data)
            result.append(run_op(obj, description, _form_data))

    if operation_name in CREATE_OPERATIONS:
        whitelisted = BriefcaseContentWhitelist.Classnames()
        if whitelisted:
            contents = [
                x for x in result
                if x.GetClassname() in whitelisted
            ]
        else:
            contents = result
        attach_created_objects_wf(contents, task)

    return result


# File conversion task
def ensure_acs_payload_dir():
    deferred_import_acs()
    # 1) an acs payloaddir isn't defined by default but required for parameterized acs jobs
    # 2) both processes (acs and wfqueue) must run on the same machine and have access rights to the
    #    payloaddir
    if not acs.getQueue().payloaddir:
        acs.getQueue().payloaddir = os.path.join(CADDOK.TMPDIR, 'acs_queue_payload')


def convert_files(task, content, file_reference=None, destination_file_types=None):
    """
    Convert files in the content. If, for instance, all primary files of the content's objects
    should be converted, then file_reference must be 'PrimaryFiles'. If files should be converted,
    which are directly contained in the content, then file_reference must be None.
    If destination_file_types is given, then convert to given destination file type(s), else convert
    to all registered conversion file types.
    """
    # importing self so we can use the convertFile callback as required
    # pylint: disable=import-self
    from cs.workflow import systemtasks
    from cdb.objects.cdb_file import CDB_File
    ensure_acs_payload_dir()
    jobs = []
    for obj in content['edit']:
        obj_files = []
        if file_reference in ["", None]:
            if not isinstance(obj, CDB_File):
                continue  # or raise an Exception?
            obj_files = [obj]
        else:
            if not hasattr(obj, file_reference):
                continue  # or raise an Exception?
            obj_files = getattr(obj, file_reference)
        for f in obj_files:
            if not isinstance(destination_file_types, list):
                destination_file_types = [destination_file_types]
            targets = []
            for ft in destination_file_types:
                if ft in ["", None]:
                    # get all registered target file types
                    targets.extend([rc[0] for rc in acs.registered_conversions(f.cdbf_type)])
                else:
                    targets.append(ft)
            targets = list(set(targets))
            for target in targets:
                # callback methods only get called if they are module level
                # methods (class methods can't be callback methods)
                task_keys = {'cdb_process_id': task.cdb_process_id,
                             'task_id': task.task_id}
                job = acs.convertFile(f, target,
                                      callback=(systemtasks,
                                                systemtasks.convert_files_done,
                                                systemtasks.convert_files_failed),
                                      paramDict=task_keys)
                jobs.append(job)
    if jobs:
        msg = util.get_label("cdbwf_n_file_conversions_initiated") % len(jobs)
        raise CloseTaskAsynchronously(msg)

    task.addProtocol(
        str(util.get_label("cdbwf_no_conversion_initiated")),
        protocols.MSGSYSTEM)


def convert_files_done(job):
    """Called by the ACS-Server after a successfull file conversion"""
    ensure_acs_payload_dir()
    task_keys = job.getParameters()
    from cs.workflow.tasks import Task
    task = Task.ByKeys(**task_keys)
    msg1 = util.get_label("cdbwf_system_task_run_async")
    msg2 = util.get_label("cdbwf_1_file_conversion_successful")
    task.addProtocol(f"{msg1}{msg2}", protocols.MSGSYSTEM)
    task.close_task()


def convert_files_failed(job):
    """Called by the ACS-Server after a failed file conversion"""
    ensure_acs_payload_dir()
    task_keys = job.getParameters()
    from cs.workflow.tasks import Task
    task = Task.ByKeys(**task_keys)
    msg1 = util.get_label("cdbwf_system_task_run_async")
    msg2 = util.get_label("cdbwf_1_file_conversion_failed")
    task.addProtocol(f"{msg1}{msg2}", protocols.MSGSYSTEM)
    if task.status == Task.EXECUTION.status:
        task.cancel_task()
