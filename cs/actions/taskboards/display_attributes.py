# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This class is used to design the cards. Methods of DisplayAttributes
are overwritten to display information about actions at the corresponding
position on the card.
"""


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


from cdb import i18n, typeconversion, util
from cs.taskboard.interfaces.display_attributes import DisplayAttributes


class ActionDisplayAttributes(DisplayAttributes):
    def get_title(self):
        """
        Get title for an action. Name of the action will be shown as title.
        """
        return self.task.name

    def get_due_date(self):
        """
        Get the due date in the card and in compact view.
        """
        if self.task.end_time_plan:
            return typeconversion.to_user_repr_date_format(self.task.end_time_plan)
        else:
            return None

    def get_overdue(self):
        """
        Get the overdue in the card and in compact view.
        """
        return self.task.joined_status_name not in [100, 200] and super().get_overdue()

    def get_footer1(self):
        """
        Get the effort for an action.
        """
        effort = (
            self.task.GetFormattedValue("effort")
            if self.task.effort
            else ("%.2f" % 0).replace(".", i18n.get_decimal_separator())
        )

        return util.get_label("cs_taskboard_card_effort") % effort

    def get_compact(self):
        """
        Get the editor in the card compact if field is filled.
        If not it displays the responsible.
        """
        if self.task.mapped_editor_name:
            return self.task.mapped_editor_name
        else:
            return self.task.mapped_subject_name
