#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Import result objects.
"""

from collections import OrderedDict

from cdb import sig
from cdb.objects import Object

from cs.pcs.msp.misc import KeyObject, get_classname, get_icon_name, logger
from cs.pcs.projects.tasks import Task


class DiffType:
    """
    Defines the type of modifications

    :cvar ADDED: used for added tasks
    :cvar DELETED: used for deleted tasks
    :cvar MODIFIED: used for modified tasks
    :cvar ADDED: used for unmodified tasks
    """

    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"
    UNMODIFIED = "unmodified"


class DiffObject:
    """
    Contains the details about the modification of a task.

    Prepares information for the import preview.

    :ivar classname: classname of the business object
    :vartype classname: basestring
    :ivar diff_type: type of modification using constant from :py:class:`cs.pcs.msp.import_results.DiffType`
    :vartype diff_type: basestring
    :ivar diffs: label, old and new value of changed attributes in preparation for the preview
    :vartype diffs: OrderedDict with `old_value`, `new_value` and `label` as keys
    :ivar exceptions: one or more error messages that prevent the import process
    :vartype exceptions: list
    :ivar icon_name: icon name in preparation for the preview
    :vartype icon_name: basestring
    :ivar pcs_object: Attribute-value pairs of the business object
    :vartype pcs_object: wenn in added verwendet: dict
                          sonst instance of :py:class:`cs.pcs.project.tasks.Task`
    :ivar references: Relationships between the tasks of the project, according to
        the type of relationship and grouped by use cases
    :vartype references: dict with classname as key and an instance of
        :py:class:`cs.pcs.msp.import_results.DiffObjectCollection` as value
    """

    def __init__(
        self,
        pcs_object,
        diff_type=DiffType.UNMODIFIED,
        classname=None,
        icon_name=None,
        diffs=None,
        exception=None,
    ):
        self.pcs_object = pcs_object
        self.diff_type = diff_type
        self.classname = classname or get_classname(pcs_object)
        self.icon_name = icon_name or get_icon_name(self.classname)
        self.diffs = OrderedDict()
        self.references = {}
        self.exceptions = []
        self.add_diffs(diffs)
        self.add_exception(exception)

    def add_diffs(self, diffs):
        if diffs:
            self.diffs.update(diffs)

    def add_exception(self, exception):
        if not exception:
            return
        exception = f"{exception}"
        if exception not in self.exceptions:
            self.exceptions.append(exception)


class DiffObjectCollection:
    """
    Container for all tasks, grouped by added, modified and deleted tasks

    :ivar added: tasks that are added to the project
    :vartype added: list of :py:class:`cs.pcs.msp.import_results.DiffObject`
    :ivar modified: existing tasks of the project that have been modified
    :vartype modified: list of :py:class:`cs.pcs.msp.import_results.DiffObject`
    :ivar deleted: tasks of the project that have been deleted
    :vartype deleted: list of :py:class:`cs.pcs.msp.import_results.DiffObject`
    :ivar all: all tasks of the project
    :vartype all: OrderedDict with

                  key: instance of :py:class:`cs.pcs.msp.misc.KeyObject`

                  value: :py:class:`cs.pcs.msp.import_results.DiffObject`
    """

    def __init__(self):
        self.all = OrderedDict()
        self.added = []
        self.modified = []
        self.deleted = []
        self.excepted = []

    def clone(self):
        doc = DiffObjectCollection()
        doc.all = self.all
        doc.added = self.added[:]
        doc.modified = self.modified[:]
        doc.deleted = self.deleted[:]
        doc.excepted = self.excepted[:]
        return doc


class ImportResult:
    """
    Container for the information about the project and the current transfer process

    :ivar project: The project that is transferred between the systems
    :vartype project: instance of :py:class:`cs.pcs.msp.import_results.DiffObject`
    :ivar tasks: Project tasks, grouped by use cases
    :vartype tasks: instance of :py:class:`cs.pcs.msp.import_results.DiffObjectCollection`
    :ivar references: Relationships between the tasks of the project,
        according to the type of relationship and grouped by use cases
    :vartype references: dict with classname as key and an instance of
        :py:class:`cs.pcs.msp.import_results.DiffObjectCollection` as value
    :ivar workflow_content: Pairs of workflow and task objects. Tasks will be
        attached to their workflow after being inserted into the database.
    :vartype workflow_content: list of tuples
    """

    def __init__(self, pcs_project):
        """
        :param pcs_project: current project
        :type: instance of :py:class:`cs.pcs.projects.Project`
        """
        self.project = DiffObject(pcs_project)
        self.tasks = DiffObjectCollection()
        self.num_old_tasks = 0
        self.only_system_attributes = []
        self.references = {"cdbpcs_taskrel": DiffObjectCollection()}
        self.workflow_content = []

    def clone(self):
        ir = ImportResult(self.project.pcs_object)
        ir.project = self.project
        ir.tasks = self.tasks.clone()
        ir.num_old_tasks = self.num_old_tasks
        ir.references = {"cdbpcs_taskrel": self.references["cdbpcs_taskrel"].clone()}
        return ir

    def get_diff_object_collection(self, classname):
        if classname == "cdbpcs_task":
            return self.tasks
        elif classname != "cdbpcs_project":
            return self.references.setdefault(classname, DiffObjectCollection())
        return None

    def get_diff_object(self, key_object, classname):
        """
        Method for accessing a DiffObject from the ImportResult

        :param key_object: KeyObject accessor to be found
        :param classname: classname string of the object to be found
        :return: returns the corresponding DiffObject if found otherwise None
        """
        if classname == "cdbpcs_project":
            return self.project
        else:
            diff_obj_coll = self.get_diff_object_collection(classname)
            if key_object in diff_obj_coll.all:
                return diff_obj_coll.all[key_object]
        return None

    def add_exception(self, pcs_object, classname, exception):
        if not classname:
            classname = get_classname(pcs_object)
        key_object = self.get_key_object(pcs_object, classname)
        diffobject = self.get_diff_object(key_object, classname)
        if diffobject:
            diffobject.add_exception(exception)
            self.get_diff_object_collection(classname).excepted.append(diffobject)
            return True
        else:
            return False

    def add_exception_to_diff_object(self, key_object, classname, message_text):
        """
        Generates an error for a business object that prevents the import.
        The transferred message is displayed as an error message in the import preview.

        :param key_object: KeyObject as accessor to identify the diff object
        :type key_object: instance of :py:class:`cs.pcs.msp.misc.KeyObject`
        :param classname: classname of the object
        :type classname: basestring
        :param message_text: message text display in the preview

                             For multi-language support, determine the message text
                             using :py:func:`cs.platform.gui.Message.GetMessage`.

        :type message_text: basestring
        :return: True if diff object was found, otherwise False
        """
        diff_object = self.get_diff_object(key_object, classname)
        if not diff_object:
            return False
        diff_object.add_exception(message_text)
        self.get_diff_object_collection(classname).excepted.append(diff_object)
        return True

    def get_key_object(self, pcs_object, classname):
        if classname == "cdbpcs_task":
            return KeyObject(
                {
                    "cdb_project_id": pcs_object["cdb_project_id"],
                    "task_id": pcs_object["task_id"],
                }
            )
        return KeyObject(pcs_object)

    def add_diff_object(
        self,
        diff_type,
        pcs_object,
        cls_or_clsname=None,
        icon_name=None,
        diffs=None,
        parent=None,
        exception=None,
    ):
        # pylint: disable=too-many-arguments
        classname = get_classname(cls_or_clsname or pcs_object)
        key_object = self.get_key_object(pcs_object, classname)
        diff_object = self.get_diff_object(key_object, classname)
        if not diff_object:
            diff_object = DiffObject(
                pcs_object, diff_type, classname, icon_name, diffs, exception
            )
        else:
            if diffs:
                diff_object.add_diffs(diffs)
            if exception:
                diff_object.add_exception(exception)
                desc = (
                    pcs_object.GetDescription()
                    if isinstance(pcs_object, Object)
                    else f"{pcs_object}"
                )
                logger.error("%s: %s ==> %s", cls_or_clsname, desc, exception)

        if classname == "cdbpcs_project":
            if self.project.diff_type == DiffType.UNMODIFIED:
                self.project = diff_object
                self.project.diff_type = diff_type
        else:
            diff_obj_coll = self.get_diff_object_collection(classname)
            if key_object not in diff_obj_coll.all:
                diff_obj_coll.all[key_object] = diff_object
            if diff_type != DiffType.UNMODIFIED:
                diff_obj_list = getattr(diff_obj_coll, diff_type, None)
                if diff_object not in diff_obj_list:
                    diff_obj_list.append(diff_object)
            if exception and (diff_object not in diff_obj_coll.excepted):
                diff_obj_coll.excepted.append(diff_object)
            if parent:
                # currently parent can only be a task
                parent_key_obj = KeyObject(parent)
                if parent_key_obj in self.tasks.all:
                    parent_diff_object = self.tasks.all[parent_key_obj]
                else:
                    parent_diff_object = self.add_diff_object(
                        DiffType.MODIFIED, parent, Task
                    )
                diff_obj_list = parent_diff_object.references.setdefault(classname, {})
                diff_obj_list[key_object] = diff_object
        return diff_object

    def exceptions_occurred(self):
        num = len(self.project.exceptions)
        num += len([d.exceptions for d in self.tasks.excepted])
        for reference in self.references.values():
            num += len([d.exceptions for d in reference.excepted])
        return num

    def log_count(self):
        logger.info("Modified project attributes: %s", len(self.project.diffs))
        logger.info("Added tasks: %s", len(self.tasks.added))
        logger.info("Modified tasks: %s", len(self.tasks.modified))
        logger.info("Deleted tasks: %s", len(self.tasks.deleted))
        logger.info(
            "Added task links: %s", len(self.references["cdbpcs_taskrel"].added)
        )
        logger.info(
            "Modified task links: %s", len(self.references["cdbpcs_taskrel"].modified)
        )
        logger.info(
            "Deleted task links: %s", len(self.references["cdbpcs_taskrel"].deleted)
        )
        num_added_references = 0
        for reference in self.references.values():
            num_added_references += len(reference.added)
        logger.info("Added references: %s", num_added_references)
        logger.info("Number of exceptions: %s", self.exceptions_occurred())


class ImportException(Exception):
    """
    Raised in order to cancel a whole import transaction, e.g. when single import operations fail.
    """

    pass


# Empty signal handler for documentation purposes
# noinspection PyUnusedLocal
@sig.connect("cs.pcs.msp.pre_import")
def pre_import(import_result):
    """
    Makes it possible to implement advanced customizing

    Will be called **before** the changes are applied to the database

    The import behavior can be customized.

    For each business object you can raise an error, which is displayed with a suitable message
    in the import preview and prevents the import process
    (:py:func:`cs.pcs.msp.import_results.ImportResult.add_exception_to_diff_object`)

    .. important::

        You must be aware that many data records can be changed in this context.
        This signal handler must be implemented with special attention to the runtime behavior:

        - Instantiating objects from |cdbpy| Objects Framework is to be avoided, basically
          prohibited (even if it is technically possible)
        - Access of any kind to the database should be reduced to an absolute minimum

    :param import_result: contains considerable data of the import process
    :type import_result: instance of :py:class:`cs.pcs.msp.import_results.ImportResult`
    :return: None
    """
    pass


# Empty signal handler for documentation purposes
# noinspection PyUnusedLocal
@sig.connect("cs.pcs.msp.post_import")
def post_import(import_result):
    """
    Makes it possible to implement advanced customizing

    Will be called **after** the changes have been committed to the database.

    The import behavior can no longer be customized.
    The already saved data can only be changed afterwards using :py:mod:`cdb.sqlapi`.

    For each business object you can change data using the :py:mod:`cdb.sqlapi`
    depending on your specific business logic.

    .. important::

        You must be aware that many data records can be changed in this context.
        This signal handler must be implemented with special attention to the runtime behavior:

        - Instantiating objects from |cdbpy| Objects Framework is to be avoided, basically
          prohibited (even if it is technically possible)
        - Access of any kind to the database should be reduced to an absolute minimum

    :param import_result: contains considerable data of the import process
    :type import_result: instance of :py:class:`cs.pcs.msp.import_results.ImportResult`
    :return: None
    """
    pass
