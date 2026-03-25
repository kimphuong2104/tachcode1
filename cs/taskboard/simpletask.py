#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import constants
from cdb.objects import Object, operations


class SimpleTask(Object):
    __classname__ = "cs_taskboard_simpletask"
    __maps_to__ = "cs_taskboard_simpletask"

    @classmethod
    def createTask(cls, name="", attachment=None):
        task_name = name
        if not task_name:
            if attachment:
                task_name = attachment.GetDescription()
            else:
                task_name = cls._getClassDef().getDesignation()
        task = operations.operation(constants.kOperationNew,
                                    cls._getClassDef(),
                                    task_name=task_name)
        # TODO: attach the attachment
        return task
