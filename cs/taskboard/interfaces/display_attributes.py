#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Common interface of |cs.taskboard|
"""



__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from cdb.typeconversion import to_user_repr_date_format
from cdb.platform.olc import StatusInfo

from cs.taskboard.utils import ensure_date


class DisplayAttributes(object):
    """
    Determines and returns the data of a task to be displayed on the card.

    Each card adapter has to be assigned a class of type `DisplayAttributes`.
    """

    def __init__(self, board_adapter, card_adapter, card, task):
        """
        Each argument is available in an instance variable of the same name in all methods of the class.

        :param board_adapter: the current board adapter
        :param card_adapter: the current card adapter
        :param card: the current card object
        :type card: cs.taskboard.objects.Card
        :param task: the task to be displayed of the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        """
        self.board_adapter = board_adapter
        self.card_adapter = card_adapter
        self.card = card
        self.task = task
        self.description = task.GetDescription() if task else ""

    def get_values(self):
        """
        .. _`cs_taskboard_api_display_attributes_get_values`:

        A :ref:`mask <ce_admin_en:cdb-gui-maskconfig>` is configured to position information on the mask.

        The data for the card is provided by methods of this class.

        This method returns a dictionary that associates each mask item with a method.

        The key corresponds to the attribute names of mask items.

        The value defines the name of the method that provides the information to display the data.

        .. important::
           The persons responsible for all tasks on a task board are determined by the system
           in a performance-optimized way.
           The attribute `responsible` must not be assigned in :py:meth:`get_values` of the data provider.

        :rtype: dict
        :returns: The following configuration is delivered:

        """
        # Start of the manual part for ATTR_METH_MAP
        attribute_method_mapping = {
            "context_name": self.get_header(),
            "card_title": self.get_title(),
            "icon1": self.get_icon1(),
            "icon2": self.get_icon2(),
            "icon3": self.get_icon3(),
            "icon4": self.get_icon4(),
            "category": self.get_category(),
            "due_date": self.get_due_date(),
            "overdue": self.get_overdue(),
            "footer1": self.get_footer1(),
            "footer2": self.get_footer2(),
            "compact_title": self.get_compact_title(),
            "compact": self.get_compact(),
            "compact_icon": self.get_compact_icon(),
            "status_icon": self.get_status_icon()
        }
        # End of the manual part for ATTR_METH_MAP

        return attribute_method_mapping

    def get_title(self):
        """
        Returns the title of the card.
        Default value is object description of the task.

        :return: Default: object description
        :rtype: basestring
        """
        return self.description

    def get_compact_title(self):
        """
        Get title in compact mode. Default is
        the same information as usual title.
        """
        return self.get_title()

    def get_category(self):
        """
        Returns the category of the card.
        Default value is empty.

        :return: Default: empty string.
        :rtype: basestring
        """
        return ""

    def get_header(self):
        """
        Returns header information.

        :return: Default: empty string
        :rtype: basestring
        """
        return ""

    def get_footer1(self):
        """
        Returns 1st footer information.

        :return: Default: empty string
        :rtype: basestring
        """
        return ""

    def get_footer2(self):
        """
        Returns 2nd footer information.

        :return: Default: empty string
        :rtype: basestring
        """
        return ""

    def get_due_date(self):
        """
        Returns the due date of the task calling
         :py:meth:`cs.taskboard.interfaces.card_adapter.CardAdapter.get_due_date`

        If the card adapter does not provide a value, the placeholder `-` will be provided.
        The user's settings for the date format are taken into account.

        :return: due date or placeholder
        :rtype: string
        """
        val = self.card_adapter.get_due_date(self.card.context_object_id)
        return to_user_repr_date_format(val) if val else '-'

    def get_overdue(self):
        """
        Returns whether the task is overdue or not.

        It's an auxiliary method.
        It is not associated with a mask field.
        It is called by the Web component
        :ref:`cs-taskboard-CardDueDate <taskboard_admin_en:cs.taskboard_admin_task_board_card_pre_configured_web_components_due_date>`

        :return: True: if the due date of a task is before the current date

                 False: if the due date is in the future
        :rtype: bool
        """
        due_date = self.card_adapter.get_due_date(self.card.context_object_id)
        target_date = self.board_adapter.get_due_date(self.card)
        if not due_date or not target_date:
            return False
        return ensure_date(due_date) < ensure_date(target_date)

    def get_compact(self):
        """
        Returns additional information in compact mode.

        :return: return value of :py:meth:`get_footer1`
        """
        return self.get_footer1()

    def get_status_icon(self):
        """
        Returns status icon information of underlying object.

        :return: returns an object containing status color, label and size.
        """

        # try to determine the olc configuration
        olc_configuration = None
        try:
            olc_configuration = self.task.oh.getOLC()
        except AttributeError:
            logger = logging.getLogger(__name__)
            logger.warning("The object '{}' of type '{}' has no OLC configuration".format(
                self.task.GetDescription(),
                self.task.GetClassDef().getClassname()
            ))

        if not olc_configuration:
            return None

        info = StatusInfo(olc_configuration, self.task.status)

        return {
            'status': self.task.status,
            'color': info.getCSSColor(),
            'label': info.getLabel()
        }

    def get_icon1(self):
        """
        Returns the first icon showed on the card.

        :returns: `None` for no icon or

                  `cs.taskboard.constants.BLANK_ICON` as `name` to show an empty icon as placeholder  or

                  a dict contains:

            `name`
                a configured icon ID

            `src`
                optional, an URL to an icon, if given then preferred over `name`

            `tooltip`
                optional, tooltip to the icon

            Default: object icon of the task on the card.

        :rtype: dict
        """
        return {
            "src": self.task.GetObjectIcon(),
            "tooltip": self.description
        }

    def get_icon2(self):
        """
        Returns the second icon showed on the card.

        :returns: `None` for no icon or

                  `cs.taskboard.constants.BLANK_ICON` as `name` to show an empty icon as placeholder  or

                  a dict contains:

            `name`
                a configured icon ID

            `src`
                optional, an URL to an icon, if given then preferred over `name`

            `tooltip`
                optional, tooltip to the icon

            Default: None

        :rtype: dict
        """
        return None

    def get_icon3(self):
        """
        Returns the third icon showed on the card.

        :returns: `None` for no icon or

                  `cs.taskboard.constants.BLANK_ICON` as `name` to show an empty icon as placeholder  or

                  a dict contains:

            `name`
                a configured icon ID

            `src`
                optional, an URL to an icon, if given then preferred over `name`

            `tooltip`
                optional, tooltip to the icon

            Default: None

        :rtype: dict
        """
        return None

    def get_icon4(self):
        """
        Returns the fourth icon showed on the card.

        :returns: `None` for no icon or

                  `cs.taskboard.constants.BLANK_ICON` as `name` to show an empty icon as placeholder  or

                  a dict contains:

            `name`
                a configured icon ID

            `src`
                optional, an URL to an icon, if given then preferred over `name`

            `tooltip`
                optional, tooltip to the icon

            Default: None

        :rtype: dict
        """
        return None

    def get_compact_icon(self):
        """
        Returns the icon in compact mode.

        :returns: `None` for no icon or a dict contains:

            `name`
                a configured icon ID

            `src`
                optional, an URL to an icon, if given then preferred over `name`

            `tooltip`
                optional, tooltip to the icon

            Default: return value of :py:func:`get_icon1`

        :rtype: dict

        """
        return self.get_icon1()
