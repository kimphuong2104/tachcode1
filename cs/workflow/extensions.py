#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Interfaces for task extensions.
"""


from cdb.objects import Object, Forward, ReferenceMethods_1
from cdb.platform import mom
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import I18nCatalogEntry

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

fTask = Forward("cs.workflow.tasks.InteractiveTask")


class ExtensionAssignment(Object):
    __maps_to__ = "cdbwf_extension_assignment"
    __classname__ = "cdbwf_extension_assignment"

    @classmethod
    def getAssignments(cls, origin_clsdef):
        classnames = [origin_clsdef.getClassname()]
        classnames += origin_clsdef.getBaseClassNames()
        return cls.Query(cls.origin_cdb_classname.one_of(*classnames))


class ExtensionClassCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        result = [I18nCatalogEntry("", "")]
        origin_clsdef = None
        try:
            origin_clsdef = self.getInvokingOpClassDef()
        except Exception:
            pass
        if not origin_clsdef:
            return result

        all_assigned = ExtensionAssignment.getAssignments(origin_clsdef)

        for assigned in all_assigned:
            extension = mom.entities.CDBClassDef(
                assigned.extension_cdb_classname)
            if not extension:
                continue
            label = str(extension.getTitle())
            result.append(
                I18nCatalogEntry(assigned.extension_cdb_classname, label))
        return result


class TaskExtension(object):
    """
    Base class for the extension class.
    The extension class itself should inherit the cdb.objects.Object class or
    ensure that inheritance.
    """

    def _getReferencedTask(self):
        return fTask.ByKeys(cdb_process_id=self.cdb_process_id,
                            task_id=self.task_id)

    Task = ReferenceMethods_1(fTask, _getReferencedTask)

    @classmethod
    def getExtensionTypeDescription(cls):
        """
        Description of the extension type, would be used
        in menu to select task type, e.g. by creating task in
        Workflow Designer. In unicode.
        """
        return str(cls._getClassDef().getDesignation())

    @classmethod
    def getExtensionAreaTitle(cls):
        """
        Title of the extension area in user interface,
        such as in Workflow Designer. In unicode.
        """
        return str(cls._getClassDef().getDesignation())

    def getTaskTitle(self):
        """
        Title of the task. If provided, would be used to replace
        the original task title.
        """
        return u""

    def getExtensionIcon(self):
        """
        Icon of the extension task.
        """
        icon = self.GetClassIcon()
        if not icon:
            from cdb.objects import IconCache
            icon = IconCache.getIcon('cdbdd_facet')
        return icon

    def checkProcessStartConditions(self):
        """
        Called before a process's status is set to ``EXECUTION``. If you want to prevent
        the start you have to raise a `cs.workflow.tasks.TaskDataIncompleteException`
        with an error message using the language of the active session.
        Note that you should not use this callback to check mandatory fields -
        you cann overwrite `getMissingMandatoryFieldsAtProcessStart` to do this
        check.
        """
        pass

    def getMissingMandatoryFieldsAtProcessStart(self):
        """
        Called before a process's status is set to ``EXECUTION``. If some mandatory
        fields has not been filled you have to return a list of the
        names of the fiels using the language of the active session.
        If all fields are there you have to return an empty list as the
        base implementation does.
        """
        return []

    def getCsTasksProceedData(self, request=None):
        """
        See `WithTasksIntegration.getCsTasksProceedData`. You will have to
        overwrite this function if you do not want to use the standard
        rendering for the :guilabel:`Status` column of the taskmanger.
        """
        return None

    def getPluginDiscriminator(self, std_name):
        """
        Returns the name of the discriminator that should be used to find
        plugins in the task manager. `std_name` is the name that is used by
        the standard if this function returns ``None`` or if no specific
        plugin is configured. If you provide a name the plugin is selected
        using the configured priority.
        """
        return None

    @classmethod
    def getDesignerExtensionName(cls):
        """
        Name of the designer plugin.
        """
        return cls._getClassname()

    def close_task(self, comment):
        """
        Closes the task
        """
        self.Task.CloseTask(remark=comment)

    def refuse_task(self, comment):
        """
        Refuses the task
        """
        self.Task.RefuseTask(remark=comment)
