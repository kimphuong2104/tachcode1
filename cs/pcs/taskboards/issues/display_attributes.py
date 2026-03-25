#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import i18n, util
from cs.taskboard.interfaces.display_attributes import DisplayAttributes


class IssueDisplayAttributes(DisplayAttributes):
    def get_category(self):
        """
        Get category of the card.
        """
        return self.task.mapped_category_name

    def get_header(self):
        """
        Get header information.
        """
        return self.task.project_name

    def get_icon1(self):
        """
        Get the first icon. Extend the tooltip.
        """
        task_type = self.task.GetClassDef().getDesignation()
        status = self.task.joined_status_name
        tooltip = f"{task_type} ({status}) {self.description}"
        return {"src": self.task.GetObjectIcon(), "tooltip": tooltip}

    def _get_effort(self):
        """
        Get effort information.
        """
        effort = (
            self.task.GetFormattedValue("effort_plan")
            if self.task.effort_plan
            else (f"{0:.2f}").replace(".", i18n.get_decimal_separator())
        )
        return util.get_label("cs_taskboard_card_label_for_effort") % effort

    def get_footer1(self):
        """
        Get footer information.
        """
        return f"{self._get_effort()}  {self.task.mapped_priority_name}"

    def get_compact(self):
        """
        Get compact information.
        """
        return self._get_effort()

    def get_overdue(self):
        """
        Whether the task is overdue.
        """
        return self.task.status not in [180, 200] and super().get_overdue()
