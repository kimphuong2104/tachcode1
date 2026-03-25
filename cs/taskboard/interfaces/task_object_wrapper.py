#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Common interface of |cs.taskboard|
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import util
from cdb.objects.core import ObjectHandleWrapper
from cdb.objects.iconcache import IconCache
from cdb.objects.iconcache import _LabelValueAccessor


# noinspection PyPep8Naming
class TaskObjectWrapper(ObjectHandleWrapper):
    """
    A wrapper for all task-like objects of a task board.

    Due to performance reasons |cs.taskboard| uses instances of `cdb.objects.core.ObjectHandleWrapper`
    instead of `cdb.objects.Object` for task-like objects.

    The wrapper provides a limited API as described below.
    """

    def GetDescription(self):
        """
        Returns the object description of the task-like object.

        The result is similar to :py:func:`cdb.objects.Object.GetDescription`.
        """
        return self.oh.getDesignation()

    def GetClassDef(self):
        """
        Returns the class definition of the task-like object.

        The result is similar to :py:func:`cdb.platform.mom.entities.CDBClassDef`
        """
        return self.oh.getClassDef()

    def GetObjectIcon(self, **kwargs):
        """
        Returns the object icon of the task-like object.

        The result is similar to :py:func:`cdb.objects.Object.GetObjectIcon`.
        """
        result = ""
        cldef = self.GetClassDef()
        if cldef:
            icon_id = cldef.getObjectIconId()
            if icon_id:
                result = IconCache.getIcon(
                    icon_id, accessor=_LabelValueAccessor(self.oh))
        return result

    def GetFormattedValue(self, fieldname):
        """
        Returns the formatted value of `fieldname`.

        The format depends on the data type and user-specific settings.

        The result is similar to :py:func:`cdb.objects.Object.GetFormattedValue`.

        :param fieldname: attribute name of the class as defined in the data dictionary
        :type fieldname: basestring
        :return: formatted value
        """
        adef = None
        cldef = self.GetClassDef()
        if cldef:
            adef = cldef.getAttributeDefinition(fieldname)
        if adef:
            return adef.format_value(self.oh[fieldname])
        else:
            raise AttributeError(fieldname)

    def ToObjectHandle(self):
        """
        Returns the object handle.

        The result is similar to `cdb.platform.mom.CDBObjectHandle`.
        """
        return self.oh

    def get_text(self, textname):
        """
        Returns the text of the object.

        :param textname: text field for the object
        """

        oid_info = self.oh.getOIDInfo()
        key_dict = oid_info[1]

        # update the keys of the object because keys are prefixed
        # with class name at the start e.g. 'cdbpcs_task.task_id'
        # and we only need 'task_id' for util.text_read api
        for key in key_dict.keys():
            new_key = key.split('.')[1] if '.' in key else key
            key_dict[new_key] = key_dict[key]
            del key_dict[key]

        return util.text_read(textname, list(key_dict.keys()), list(key_dict.values()))
