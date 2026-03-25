#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.taskmanager.mixin import WithTasksIntegration


class ActionWithCsTasks(WithTasksIntegration):
    def getCsTasksContexts(self):
        return [self.Project]
