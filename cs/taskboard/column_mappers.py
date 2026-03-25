# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Predefined column mappers of |cs.taskboard|
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cs.taskboard.interfaces.column_mapper import ColumnMapper
from cs.taskboard.constants import COLUMN_DONE


class BasicOLCColumnMapper(ColumnMapper):
    """
    Defines, depending on the object life cycle status of the task,
    in which column the card of the task is displayed.

    This class derived from `cs.taskboard.interfaces.column_mapper.ColumnMapper`.
    """

    STATUS_TO_COLUMN = {}
    """
    Defines the valid columns of a card in relation to the object life cycle status
    of the task displayed by the card.
    The user can move the card to all columns defined for the object life cycle status.

    When the card of the task is created for the first time, it is displayed on the first column defined here.

    ``STATUS_TO_COLUMN`` is a dictionary consisting of status numbers as keys and
    a list of :ref:`column types <cs_taskboard_api_column_types>` as values.

       .. code-block:: python

          from cs.taskboard.column_mappers import OLCColumnMapper
          from cs.pcs.projects.tasks import Task
          from cs.taskboard.constants import COLUMN_READY
          from cs.taskboard.constants import COLUMN_DOING
          from cs.taskboard.constants import COLUMN_DONE

          class CustomBoardTaskColumnMapper(OLCColumnMapper):

              STATUS_TO_COLUMN = {
                  Task.NEW.status: [COLUMN_READY],
                  Task.READY.status: [COLUMN_READY],
                  Task.EXECUTION.status: [COLUMN_DOING],
                  Task.DISCARDED.status: [COLUMN_DONE],
                  Task.FINISHED.status: [COLUMN_DONE],
                  Task.COMPLETED.status: [COLUMN_DONE]
              }

    """

    COLUMN_TO_STATUS = {}
    """
    Defines for a column the valid object life cacle status of a task displayed on the card.

    In this property, all valid statuses must be configured for each column.
    The configuration is used, among other things, to determine the availability, visibility, and positioning of the task on the board.

    If the user drags the card to a column
    and the current status of the task does not correspond to a value from the list of valid statuses,
    the status of the task is changed to the first status of the list.

    If the user drags the card to a column
    and the current status of the task corresponds to a value from the list of valid statuses,
    a status change is not triggered.

    ``COLUMN_TO_STATUS`` is a dictionary consisting of :ref:`column types <cs_taskboard_api_column_types>`
    as keys and a list of status numbers as values.

       .. code-block:: python

          from cs.taskboard.column_mappers import OLCColumnMapper
          from cs.pcs.projects.tasks import Task
          from cs.taskboard.constants import COLUMN_READY
          from cs.taskboard.constants import COLUMN_DOING
          from cs.taskboard.constants import COLUMN_DONE

          class CustomBoardTaskColumnMapper(OLCColumnMapper):

              COLUMN_TO_STATUS = {
                  COLUMN_READY: [Task.READY.status],
                  COLUMN_DOING: [Task.EXECUTION.status],
                  COLUMN_DONE: [Task.FINISHED.status]
              }

    """

    @classmethod
    def get_done_status_list(cls):
        return cls.COLUMN_TO_STATUS.get(COLUMN_DONE, [])

    @classmethod
    def change_to(cls, board_adapter, card_adapter, card, column):
        status_list = cls.COLUMN_TO_STATUS.get(column.column_name)
        status = board_adapter.get_status(card.context_object_id)
        if status_list is not None and status not in status_list:
            task = card.TaskObject
            if task:
                task.ChangeState(status_list[0])


class OLCColumnMapper(BasicOLCColumnMapper):
    """
    Defines, depending on the object life cycle status of the task,
    in which column the card of the task is displayed.

    This class derived from `cs.taskboard.interfaces.column_mapper.ColumnMapper`.
    """

    @classmethod
    def validate(cls, board_adapter, card_adapter, card, task):
        status = board_adapter.get_status(card.context_object_id)
        if status not in cls.STATUS_TO_COLUMN:
            return False
        return bool(board_adapter.get_column_type(card.Column) in
                    cls.STATUS_TO_COLUMN[status])

    @classmethod
    def init_column(cls, board_adapter, card_adapter, task):
        # Return specified column for new adding card according
        # to task status
        if not task:
            return None
        should_be = cls.STATUS_TO_COLUMN.get(task.status)
        if not should_be:
            return None
        return board_adapter.get_column_by_type(should_be[0])

    @classmethod
    def auto_change(cls, board_adapter, card_adapter, card, task):
        status = board_adapter.get_status(card.context_object_id)
        if status in cls.STATUS_TO_COLUMN:
            should_be = cls.STATUS_TO_COLUMN[status]
            if board_adapter.get_column_type(card.Column) in should_be:
                return True
            col = board_adapter.get_column_by_type(should_be[0])
            if col:
                if card.column_object_id != col.cdb_object_id:
                    card.column_object_id = col.cdb_object_id
                return True
        # can not be auto reassigned, maybe mark it dirty
        return False


class TeamOLCColumnMapper(OLCColumnMapper):
    """
    Defines, depending on the object life cycle status of the task,
    in which column the card of the task is displayed.
    Only contains tasks of the assigned team members.

    This class derived from `cs.taskboard.column_mappers.OLCColumnMapper`.
    """
    pass


class DateColumnMapper(BasicOLCColumnMapper):
    """
    Defines, depending on the object life cycle status and the due date of the task,
    in which column the card of the task is displayed.

    This class derived from `cs.taskboard.interfaces.column_mapper.ColumnMapper`.
    """

    @classmethod
    def validate(cls, board_adapter, card_adapter, card, task):
        if not board_adapter.validate_team(task):
            return False
        status = board_adapter.get_status(card.context_object_id)
        if status not in cls.STATUS_TO_COLUMN:
            return False
        column_type = board_adapter.get_column_type(card.Column)
        should_be = cls.STATUS_TO_COLUMN[status]
        # FIXME: s. user story, may check COLUMN_DOING explicitly
        pos = 0
        if card_adapter.get_due_date(card.context_object_id) and len(should_be) > pos + 1:
            pos += 1
        return bool(column_type == should_be[pos])

    @classmethod
    def init_column(cls, board_adapter, card_adapter, task):
        # Return specified column for new adding card according
        # to task status
        if not task:
            return None
        should_be = cls.STATUS_TO_COLUMN.get(task.status)
        if not should_be:
            return None
        pos = 0
        if card_adapter.get_due_date(task.cdb_object_id) and len(should_be) > pos + 1:
            pos += 1
        return board_adapter.get_column_by_type(should_be[pos])

    @classmethod
    def auto_change(cls, board_adapter, card_adapter, card, task):
        status = board_adapter.get_status(card.context_object_id)
        if status in cls.STATUS_TO_COLUMN:
            should_be = cls.STATUS_TO_COLUMN[status]
            pos = 0
            if card_adapter.get_due_date(card.context_object_id) and len(should_be) > pos + 1:
                pos += 1
            col = board_adapter.get_column_by_type(should_be[pos])
            if col:
                if card.column_object_id != col.cdb_object_id:
                    card.column_object_id = col.cdb_object_id
                return True
        # can not be auto reassigned, maybe mark it dirty
        return False


class TeamDateColumnMapper(DateColumnMapper):
    """
    Defines, depending on the object life cycle status and the due date of the task,
    in which column the card of the task is displayed.
    Only contains tasks of the assigned team members.

    This class inherits `cs.taskboard.interfaces.column_mapper.DateColumnMapper`.
    """
    pass
