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

from collections import defaultdict
import datetime
from webob.exc import HTTPForbidden
from cdb import util
from cdb import constants
from cdb import ue
from cdb import sqlapi
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cdb.platform.mom.entities import CDBClassDef
from cdb.objects import Object
from cs.taskboard import db_tools
from cs.taskboard.objects import Board
from cs.taskboard.objects import Row
from cs.taskboard.objects import Column
from cs.taskboard.interfaces.task_object_wrapper import TaskObjectWrapper
from cs.taskboard.groups import get_group_labels, get_group_for_class
from cs.taskboard.utils import partition


class BoardAdapter(object):
    __CARD_ADAPTERS__ = {}
    """
    Define which types of task object can be set directly
    on a card.
    Otherwise they might be treated as attachments or disallowed
    by the board.
    Each card adapter should register itself via REGISTER_BOARD_ADAPTER
    signal by a board adapter
    In this form::

        {
            <classname>: {
                "adapter": <AdapterClass>
            }
         }
    """

    __ALLOWED_CONTEXT_CLASSES__ = {}
    """
    Define which context object types are allowed on this board.
    Each context adapter should register itself via REGISTER_BOARD_ADAPTER
    signal by a board adapter
    In this form::

        {
            <classname>: {
                "adapter": <AdapterClass>
            }
         }
    """

    COLUMN_NAME_TO_TYPE = {}
    """
    The mapping is only necessary if the `column_name` is different from the `COLUMN_\<TYPE\>`.

    Maps the `column_name` of a column to a `COLUMN_\<TYPE\>`.

    Column types predefined in the :ref:`constants<cs_taskboard_api_column_types>` module.

        .. code-block:: python

            from cs.taskboard.interfaces.board_adapter import BoardAdapter

            class SampleBoardAdapter(BoardAdapter)

                COLUMN_NAME_TO_TYPE = {
                    'sample_column_name': 'COLUMN_EVALUATION',
                    'BACKLOG': 'COLUMN_BACKLOG'  # not required,
                                                 # it meets the default naming convention
                    }

    """

    HAS_BACKLOG = False
    """
    Defines whether the board has a :guilabel:`Planning View`.
    In the :guilabel:`Planning View`, all existing tasks of the used context
    are displayed in a backlog column.
    This property is usually applied to sprint boards.
    """

    HAS_TEAM = False
    """
    Defines whether the board has a :guilabel:`Board Member` view to allow managing board members.
    This property is usually applied to team boards.
    """

    HAS_EVALUATION = False
    """
    Defines whether the board has a :guilabel:`Review` tab.
    The :guilabel:`Review` tab provides information from the past, usually about completed iterations.
    The cards cannot be moved in this view.
    This property is usually applied to sprint boards.
    """

    HAS_PREVIEW = False
    """
    Defines whether the board has a :guilabel:`Preview` tab.
    The :guilabel:`Preview` tab provides information about upcoming iterations.
    The cards cannot be moved in this view.
    This property is usually applied to sprint boards.
    """

    HAS_PREVIEW_ADD_BUTTON = False
    """
    Defines whether the board has a :guilabel:`Add New Task` button.
    The :guilabel:`Add New Task` button provides the possibility to add tasks
    within the preview tab.
    """

    ENABLE_MOVING_CARDS_IN_PREVIEW = False
    """
    Defines whether the board enables the moving of cards between iterations
    within the iterations preview tab.
    """

    ENABLE_MOVING_CARDS_IN_GROUPS = False
    """
    Defines whether the board enables the moving of cards between groups
    within the active tab.
    """

    ITERATION_CLASS = None
    """
    Defines which type of iteration should be used on this task board.
    The assigned class should be derived from `cs.taskboard.objects.Iteration`.
    This property is usually only applied to sprint boards.

       .. code-block:: python

          from cs.taskboard.interfaces.board_adapter import BoardAdapter
          from cs.taskboard.objects import Sprint

          class SampleBoardAdapter(BoardAdapter)

              ITERATION_CLASS = Sprint

    """

    # cache for card adapters
    __ADAPTER_CACHE__ = {}

    # map task object ID to CDBObjectHandle
    __AVAILABLE_TASKS__ = {}

    # map card adapter to its available task IDs
    __AVAILABLE_TASK_IDS__ = {}

    # cache for the last reload to a task
    __UPDATE_CACHE__ = defaultdict(bool)

    # cache for the last result dictionary created for a task
    __RESULT_CACHE__ = defaultdict(dict)

    # cache for look up whether a subject is board team member
    __TEAM_CACHE__ = {}

    # cache grouped data temporarily
    __GROUP_CACHE__ = {}

    __SPLIT_COUNT__ = 999

    # detail outlet names indexed by classname; overwrite if you want
    # something else than the frontend default ("selected_object")
    DETAIL_OUTLETS = {}
    """
    To use another detail outlet than "selectd_object" in this board,
    overwrite ``DETAIL_OUTLETS``:

    .. code-block :: python

        DETAIL_OUTLETS = {
            "cs_taskboard_simpletask": "simpletask_details",
        }

    """

    def _get_api_name(self):
        return "%s.%s" % (self.__module__, self.__class__.__name__)

    def __init__(self, board_object_id):
        """
        :param board_object_id: uuid of an instance of `cs.taskboard.objects.Board`
        :type board_object_id: basestring
        """
        self.board_object_id = board_object_id
        self.last_update = None

    def get_board(self):
        """
        Get the task board object bounded with this board adapter.

        :return: a task board object.
        :rtype: instance of ``cs.taskboard.objects.Board``
        """
        return Board.ByKeys(self.board_object_id)

    def get_context_adapter(self):
        """
        Get the :ref:`cs_taskboard_api_context_adapter` for the context object
        bounded with this board adapter.

        :return: A adapter class corresponding to the type of the context object of the current board
        :rtype: specialized instance of ``cs.taskboard.interfaces.context_adapter.ContextAdapter``
        """
        board = self.get_board()
        if board.ContextObject:
            return self.get_context_adapter_by_classname(
                board.ContextObject.GetClassname())
        return None

    @classmethod
    def get_context_adapter_by_classname(cls, classname):
        adapter = cls.__ALLOWED_CONTEXT_CLASSES__.get(classname)
        if adapter is None:
            for clsname in CDBClassDef(classname).getBaseClassNames():
                adapter = cls.__ALLOWED_CONTEXT_CLASSES__.get(clsname)
                if adapter is not None:
                    return adapter
        return adapter

    @classmethod
    def get_all_content_classnames(cls):
        # Which content object types are allowed on this board
        return set(cls.__CARD_ADAPTERS__.keys())

    def get_card_adapters(self):
        adapters = [
            self._get_card_adapter_config(task_type)
            for task_type in self.get_all_content_classnames()
        ]
        return [conf["adapter"] for conf in adapters if conf is not None]

    def get_subjects(self):
        """
        :return: Returns a tuple of lists containing the IDs of all board members grouped by type
                 - type == Person: angestellter.personalnummer
                 - type == Common Role: cdb_global_role.role_id
                 - type == PCS Role: cdbpcs_role_def.name
        :rtype: tupel of lists
        """
        board = self.get_board()
        persons = [x.subject_id for x in [x for x in board.TeamMembers if x.subject_type == 'Person']]
        common_roles = [x.subject_id for x in [x for x in board.TeamMembers if x.subject_type == 'Common Role']]
        project_roles = [x.subject_id for x in [x for x in board.TeamMembers if x.subject_type == 'PCS Role']]
        return persons, common_roles, project_roles

    def set_update_status(self, oid, update_status):
        self.__UPDATE_CACHE__[oid] = bool(update_status)

    def is_up_to_date(self, oid):
        return self.__UPDATE_CACHE__.get(oid, False)

    def clear_update_cache(self):
        self.__UPDATE_CACHE__.clear()

    def add_result(self, oid, obj):
        self.__RESULT_CACHE__[(oid, self)] = obj

    def get_result(self, oid):
        return self.__RESULT_CACHE__[(oid, self)]

    def get_available_tasks(self, refresh=False):
        """
        Determines and returns all available tasks using the method
        :py:func`get_available_records` on all registered
        :ref:`cs_taskboard_api_card_adapter`.

        The tasks are cached to ensure an appropriate performance.

        If the tasks are not to be provided using the cache, set the argument ``Refresh`` to ``True``.

        :param refresh: False (Default), if the cache is to be used

                        True, if the tasks are to be retrieved from the database again
        :type refresh: bool
        :return: a dict contains `cdb.platform.mom.CDBObjectHandle` of tasks,
                 indexed by their Object UUID
        """
        board = self.get_board()
        if refresh and board and (board.is_aggregation or board.ContextObject):
            task_oids = set()
            for adapter in self.get_card_adapters():
                objs = adapter.get_available_records(self)
                ava_ids = self._register_objects_and_get_oids(adapter, objs)
                self.__AVAILABLE_TASK_IDS__[adapter] = ava_ids
                # add modified tasks to list
                has_mod_date = bool(adapter.get_mod_date_attribute(list(objs)[0])
                                    if len(objs) else "")
                for oid in ava_ids:
                    if not has_mod_date or not self.is_up_to_date(oid):
                        task_oids.add(oid)
            if task_oids:
                for oid, oh in getObjectHandlesFromObjectIDs(list(task_oids),
                                                             True, True).items():
                    self.__AVAILABLE_TASKS__[oid] = oh
        return self.__AVAILABLE_TASKS__

    @classmethod
    def _get_records_by_oids(cls, oids):
        if not oids:
            return set()
        sql = "SELECT relation FROM cdb_object WHERE id = '%s'" % list(oids)[0]
        table_name = sqlapi.RecordSet2(sql=sql)[0]["relation"]
        oor = db_tools.OneOfReduced(table_name=table_name)
        cond = oor.get_expression(column_name='cdb_object_id', values=oids)
        return sqlapi.RecordSet2(table=table_name, condition=cond)

    def _register_objects_and_get_oids(self, card_adapter, objs):
        if not len(objs):
            return set()
        result = set()
        last_update = self.get_last_update()
        d_attr = card_adapter.get_due_date_attribute(list(objs)[0])
        c_attr = card_adapter.get_completion_date_attribute(list(objs)[0])
        s_attr = card_adapter.get_status_attribute(list(objs)[0])
        m_attr = card_adapter.get_mod_date_attribute(list(objs)[0])
        for r in objs:
            # add object id to result set
            result.add(r.cdb_object_id)

            # register attribute values in caches to avoid round trips
            if d_attr:
                card_adapter.add_due_date(r.cdb_object_id, r[d_attr])
            if c_attr:
                card_adapter.add_completion_date(r.cdb_object_id, r[c_attr])
            if s_attr:
                self.add_done_status(r.cdb_object_id, r[s_attr])

            if r.cdb_object_id in self.__UPDATE_CACHE__:
                # check for need of update within board front end
                # NOTE: Not only evaluated for the update of the front end.
                #       In the calling method (BoardAdapter#get_available_tasks), the task is only
                #       added to the task cache __AVAILABLE_TASKS__ if it is not marked as
                #       up-to-date in this  __UPDATE_CACHE__.
                utd = m_attr and bool(last_update and last_update >= r[m_attr])
                self.set_update_status(r.cdb_object_id, utd)
            else:
                # Add new task in status False,
                # because the card has not yet been created or has not yet been completely created.
                self.set_update_status(r.cdb_object_id, False)

        return result

    TASK_DONE_STATUS = {}

    @classmethod
    def add_done_status(cls, task_oid, status):
        cls.TASK_DONE_STATUS[task_oid] = status

    @classmethod
    def get_status(cls, task_oid):
        if task_oid not in cls.TASK_DONE_STATUS:
            return None
        return cls.TASK_DONE_STATUS[task_oid]

    def is_done(self, card_adapter, task_oid):
        status_list = card_adapter.get_done_status_list()
        status = self.get_status(task_oid)
        if status is None:
            task = self.get_task(task_oid)
            status_attr = card_adapter.get_status_attribute(task)
            status = task[status_attr]
        return status in status_list

    def _get_available_task_ids_by_adapter(self, card_adapter):
        return self.__AVAILABLE_TASK_IDS__.get(card_adapter, set())

    def _get_card_adapter_config(self, task_clsname):
        if not task_clsname:
            return None
        task_types = self.get_board().content_types
        available_types = set(task_types.split(",") if task_types else [])
        # double check
        configs = self.get_all_content_classnames()
        if available_types:
            configs = configs & available_types
        if task_clsname in configs:
            return self.__CARD_ADAPTERS__[task_clsname]
        else:
            for clsname in CDBClassDef(task_clsname).getBaseClassNames():
                if clsname in configs:
                    return self.__CARD_ADAPTERS__[clsname]
        return None

    def _get_task_objecthandle(self, task_object_id):
        return self.__AVAILABLE_TASKS__.get(task_object_id, None)

    def get_task(self, task_object_id):
        """
        Returns the tasks data as a wrapped object providing access similar to an instance of
        ``cdb.objects.Object``.

        .. hint::

          Due to performance reasons, the task is ***not*** provided as an instance of
          ``cdb.objects.Object``.

        If you want to determine the data of the assigned task for a card, use the
        method :py:func:`get_card_task`.

        :param task_object_id: Object ID of a task
        :type task_object_id: basestring
        :return: a wrapped object with similar but limited
                access like a `cdb.platform.mom.CDBObjectHandle` object.
        :rtype: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        """
        oh = self._get_task_objecthandle(task_object_id)
        if oh is None:
            return None
        return TaskObjectWrapper(oh)

    def get_card_task(self, card):
        """
        This method is only a wrapper if you do not want to retrieve the data of the task via its UUID,
        but via its card.

        Returns the tasks data as a wrapped object providing access similar to an instance of
        ``cdb.objects.Object``.

        For further details please refer to the method :py:func:`get_task`.

        :param card: the current card
        :type card: cs.taskboard.objects.Card
        """
        return self.get_task(card.context_object_id)

    def get_card_task_classname(self, card):
        task_oh = self._get_task_objecthandle(card.context_object_id)
        if task_oh is None:
            return None
        return task_oh.getClassDef().getClassname()

    def get_card_adapter(self, card):
        """
        Returns the card adapter of the requested card.

        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :return: :ref:`cs_taskboard_api_card_adapter`
        :rtype: specialized instance of ``cs.taskboard.interfaces.card_adapter.CardAdapter``
        """
        adapter = self.__ADAPTER_CACHE__.get(card.cdb_object_id, None)
        if adapter:
            return adapter
        task_classname = self.get_card_task_classname(card)
        config = self._get_card_adapter_config(task_classname)
        if not config:
            return None
        self.__ADAPTER_CACHE__[card.cdb_object_id] = config["adapter"]
        return config["adapter"]

    def _setup(self):
        self.setup()
        for adapter in self.get_card_adapters():
            adapter.setup_board(self)

    def can_change_card_position(self, card):
        """
        Check whether the position of a card can be changed at all

        :param card: the card to be checked
        :type card: cs.taskboard.objects.Card

        :rtype: bool
        """
        return self.can_change_position(card) and \
               self.get_card_adapter(card).can_change_position(self, card)

    # def can_change_card_position_to(self, card, row_id, col_id):
    #     # Check whether the card can be changed into a special position
    #     # DO NOT OVERRIDE
    #     row = Row.ByKeys(row_id) if row_id else card.Row
    #     column = Column.ByKeys(col_id)
    #     return self._can_change_card_position_to(card, row, column)
    #
    # def _can_change_card_position_to(self, card, row, column):
    #     # DO NOT OVERRIDE
    #     return self.can_change_position_to(card, row, column) and \
    #            card.Adapter.can_change_position_to(row, column)

    def change_card_position_to(self, card, row_id, col_id, group=None):
        """
        Moves the card to the requested position.
        The position is determined by the column, row and group.
        Optionally returns a follow-up operation using :py:func:`get_change_position_followup`.

        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param row_id: UUID og the target row
        :type row_id: basestring
        :param col_id: Object ID of target column
        :type col_id: basestring
        :param group: String or object of target group
        :type group: basestring or object
        :return: Optional, for further information refer to :py:func:`get_change_position_followup`.
        """
        row = Row.ByKeys(row_id) if row_id else card.Row
        if row_id and not row:
            row = card.Row
        column = Column.ByKeys(col_id)
        self.on_change_position_pre(card, row, column)
        if group:
            self.get_card_adapter(card).change_to_group(self, card, group, row_id)
        self.get_card_adapter(card).change_position(self, card, row, column)
        self.on_change_position_post(card)
        return self.get_change_position_followup(card, row, column)

    @classmethod
    def get_group_attributes(cls):
        """
        Returns the attributes of the tasks offered to group the cards on the board.

        :return: list of (group name, label) pairs with

                 `group  name`
                   group name as used by :py:func:`group_by`
                 `label`
                    text to be displayed

        """
        if getattr(cls, "__group_attributes__", None) is None:
            attributes = set()
            for classname in cls.get_all_content_classnames():
                mapping = get_group_for_class(classname)
                if mapping:
                    attributes |= set(mapping.keys())
            labels = get_group_labels()
            attributes &= set(labels.keys())
            cls.__group_attributes__ = [(att, labels[att]) for att in attributes]
        return cls.__group_attributes__

    def group_by(self, group_attribute):
        """
        Groups the cards on this board by the specified group attribute.

        :param group_attribute: name of the grouping attribute
        :return: dict of groups indexed by group name, value is
                 a dict contains of

                 `title`
                   title of the group,
                 `context_object`
                   If the group refers to an context object
                 `card_ids`
                   A list of card UUIDs associated with the group

        """
        groups = {}
        board = self.get_board()
        iteration = board.ActiveIteration or board.NextIteration
        cards = iteration.Cards if iteration else board.VisibleCards
        for card in cards:
            task = self.get_card_task(card)
            task_classname = task.GetClassDef().getClassname()
            config = get_group_for_class(task_classname).get(group_attribute, {})
            resolver = config.get("resolver", None)
            value = None
            if resolver:
                if callable(resolver):
                    value = resolver(task)
                elif isinstance(resolver, str):
                    value = task[resolver]
            context_object = None
            if isinstance(value, Object):
                context_object = value
                group_name = value.ID()
            else:
                group_name = str(value) if value is not None else ""
            group = groups.setdefault(group_name, {
                "title": group_name,
                "context_object": context_object,
                "card_ids": [],
                "aggregations": []
            })
            group["card_ids"].append(card.cdb_object_id)
            aggregator = config.get("aggregator", None)
            if callable(aggregator):
                group["aggregations"].append(
                    dict(aggregator(task), cdb_object_id=task.cdb_object_id))
        self.__GROUP_CACHE__ = groups
        return groups

    def get_group_by_results(self):
        """
        Get latest grouping results without performing :py:func:`group_by`
         again.
        """
        return self.__GROUP_CACHE__

    def get_column_types(self):
        """
        Returns the types of all available columns

        For further information refer to :ref:`cs_taskboard_api_column_types`.
        """
        return self.get_board().Columns.column_name

    def get_column_type(self, column):
        """
        Returns the type of the requested column
        :param column: requested column
        :type column: cs.taskboard.objects.Column
        :return: type of the column
        :rtype: basestring
        """
        if not column:
            return ""
        return self.COLUMN_NAME_TO_TYPE.get(column.column_name, column.column_name)

    def get_column_by_type(self, column_type, **kwargs):
        """
        Returns the column of the board corresponding to the requested column type
        A board usually has only one column per column type.
        If not, then a column of the type is returned randomly.

        :param column_type: type of the requested column
        :param kwargs: optional conditions
        :return: one of the columns on the board that meets the conditions
        :rtype: cs.taskboard.objects.Column
        """
        col_name = next(
            (k for k, v in self.COLUMN_NAME_TO_TYPE.items() if v == column_type),
            column_type)
        cols = self.get_board().Columns.KeywordQuery(column_name=col_name, **kwargs)
        if len(cols):
            return cols[0]
        return None

    def has_backlog(self):
        """
        Whether the board has a backlog view.
        For further information refer to :py:attr:`HAS_BACKLOG`.
        """
        return self.HAS_BACKLOG

    def has_team(self):
        """
        Whether the current board has team members.
        For further information refer to :py:attr:`HAS_TEAM`.
        """
        return self.HAS_TEAM

    def has_evaluation(self):
        """
        Whether the current board has a evaluation view.
        For further information refer to :py:attr:`HAS_EVALUATION`.
        """
        return self.HAS_EVALUATION

    def has_preview(self):
        """
        Whether the current board has a preview view.
        For further information refer to :py:attr:`HAS_PREVIEW`.
        """
        return self.HAS_PREVIEW

    def has_preview_add_button(self):
        """
        Whether the current board has a preview view add button.
        For further information refer to :py:attr:`HAS_PREVIEW_ADD_BUTTON`.
        """
        return self.HAS_PREVIEW_ADD_BUTTON

    def enable_moving_cards_in_preview(self):
        """
        Whether the current board enables the moving of cards
        between preview iterations.
        For further information refer to :py:attr:`ENABLE_MOVING_CARDS_IN_PREVIEW`.
        """
        return self.ENABLE_MOVING_CARDS_IN_PREVIEW

    def enable_moving_cards_in_groups(self):
        """
        Whether the current board enables the moving of cards
        between groups.
        For further information refer to :py:attr:`ENABLE_MOVING_CARDS_IN_GROUPS`.
        """
        return self.ENABLE_MOVING_CARDS_IN_GROUPS

    @classmethod
    def get_filters(cls):
        """
        Returns the available filters offered to filter the cards on the board.

        The offered values of the filters are determined from the tasks displayed on the board.
        A selected option in a previous filter therefore limits the options in the following filter.

        :return: list of dictionaries containing values for "name" (name of the filter)
                    and "label" (label identifier) like
                [ {"name": "categories_filter", "label": "label_nameA"},
                  {"name": "responsible_filter", "label": "label_nameB"},
                  {"name": "priority_filter", "label": "label_nameC"} ]
        """
        return []

    @classmethod
    def get_filter_names(cls):
        return [dict(filter, title=util.get_label(filter["label"]))
                for filter in cls.get_filters()]

    def get_readonly_fields(self):
        return set([])

    def get_create_operations(self):
        result = []
        for adapter in self.get_card_adapters():
            opdata = adapter.get_create_operation(self)
            if opdata is not None:
                if "name" not in opdata:
                    opdata["name"] = constants.kOperationNew
                result.append(opdata)
        return result

    def validate_team(self, task):
        """
        Checks whether the requested task is assigned to a member
        of the board team.

        :param task: object to be checked
        :param subject_type: type of the requested subject
        :return: True, if the task is assigned to a board member

                 False, if the task is not assigned to a board member
        :rtype: bool
        """
        if self.has_team():
            return self.is_in_team(task.subject_id, task.subject_type)
        return True

    def is_in_team(self, subject_id, subject_type):
        """
        Checks whether the requested person or role is a member of the board team.

        :param subject_id: unique identifier of the requested subject
        :param subject_type: type of the requested subject
        :return: True, if the subject is a board member

                 False, if the subject is not a board member
        :rtype: bool
        """
        if (subject_id, subject_type) not in self.__TEAM_CACHE__:
            board = self.get_board()
            self.__TEAM_CACHE__[(subject_id, subject_type)] = \
                subject_type in board.TeamMemberByTypes.keys() and \
                subject_id in board.TeamMemberByTypes[subject_type].subject_id
        return self.__TEAM_CACHE__.get((subject_id, subject_type), False)

    def allow_board_context_object(self, obj_hdl):
        """
        Check whether the object is allowed to be board context
        """
        clsdef = obj_hdl.getClassDef()
        clsnames = set(clsdef.getBaseClassNames())
        clsnames.add(clsdef.getClassname())
        allowed = set(self.__ALLOWED_CONTEXT_CLASSES__.keys())
        return len(clsnames & allowed) > 0

    def allow_board_content_object(self, obj):
        """
        Check whether the object is allowed to be shown on board
        """
        clsdef = obj.ToObjectHandle().getClassDef()
        clsnames = set(clsdef.getBaseClassNames())
        clsnames.add(clsdef.getClassname())
        allowed_content_classes = self.get_all_content_classnames()
        allowed_content_types = set(self.board.content_types.split(",")
                                    if self.board.content_types else [])
        return len(clsnames & allowed_content_classes & allowed_content_types) > 0

    def get_iteration_class(self):
        """
        Returns the class of the iteration type.
        For sprint boards, the class must be set in derived classes.
        This method is usually applied to sprint boards.
        For further details refer to :py:attr:`ITERATION_CLASS`.
        """
        return self.ITERATION_CLASS

    def change_card_iteration(self, card, iteration_id):
        """
        Moves the card to the requested iteration.
        This method is usually applied to sprint boards.

        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param iteration_id: UUID of target iteration
        :type iteration_id: basestring
        """
        # Only works if iterations exist on board
        if not self.ITERATION_CLASS:
            return
        iter_cls = self.ITERATION_CLASS
        new_iter = iter_cls.ByKeys(iteration_id)
        self.change_card_iteration_pre(card, new_iter)
        card.modifyCard(sprint_object_id=iteration_id)

    def on_iteration_start_pre(self, iteration):
        """
        Called before an iteration starts to allow pre-processing.

        :param iteration: the starting iteration
        :type iteration: cs.taskboard.objects.Iteration
        """
        for adapter in self.get_card_adapters():
            adapter.on_iteration_start_pre(self, iteration)

    def on_iteration_start_post(self, iteration):
        """
        Called after an iteration starts to allow post-processing.

        :param iteration: the started iteration
        :type iteration: cs.taskboard.objects.Iteration
        """
        for adapter in self.get_card_adapters():
            adapter.on_iteration_start_post(self, iteration)

    def on_iteration_stop_pre(self, iteration):
        """
        Called before an iteration stops to allow pre-processing.

        :param iteration: the stopping iteration
        :type iteration: cs.taskboard.objects.Iteration
        """
        for adapter in self.get_card_adapters():
            adapter.on_iteration_stop_pre(self, iteration)

    def on_iteration_stop_post(self, iteration):
        """
        Called after an iteration stops to allow post-processing.

        :param iteration: the stopped iteration
        :type iteration: cs.taskboard.objects.Iteration
        """
        for adapter in self.get_card_adapters():
            adapter.on_iteration_stop_post(self, iteration)

    def get_active_iteration(self):
        """
        Get the active iteration of the board. Default is
        the iteration in status `EXECUTION` if found, else None.

        :rtype : cs.taskboard.objects.Iteration
        """
        return self.get_board().ActiveIteration

    def update_cards(self):
        """
        Makes the board's cards synchronized with the available tasks.
        Cards are added or removed as needed.

        The task cache is not updated.
        If you want to update the board including the available tasks, use :py:func:`update_board` instead.

        :return: Nothing
        """
        # Only handle existing collection of available tasks
        tasks = self.get_available_tasks(refresh=False)
        task_ids = set(tasks.keys())
        added = set()
        remove = set()
        to_hide = set()
        to_show = set()
        board = self.get_board()
        if not board.is_aggregation and not board.ContextObject:
            raise ue.Exception(u"cs_taskboard_context_object_missing")
        for card in board.Cards:
            oid = card.context_object_id
            if oid not in task_ids:
                remove.add(oid)
            else:
                card_adapter = self.get_card_adapter(card)
                task = self.get_card_task(card)
                if not card_adapter or \
                        not card_adapter.validate(self, card, task):
                    remove.add(oid)
                else:
                    added.add(oid)
                    visible = card_adapter.check_visibility(self, card, task)
                    if card.is_hidden == 1 and visible:
                        to_show.add(oid)
                    if card.is_hidden != 1 and not visible:
                        to_hide.add(oid)
        for adapter in self.get_card_adapters():
            ava_ids = self.__AVAILABLE_TASK_IDS__.get(adapter, set())
            adapter.add_cards(self, ava_ids - added - remove)

        board_oid = sqlapi.quote(self.board_object_id)
        # FIXME: maybe paging? The oids string can be overlong...
        if remove:
            for object_ids in partition(list(remove), self.__SPLIT_COUNT__):
                oids = u",".join([u"'%s'" % sqlapi.quote(x) for x in object_ids])
                sqlapi.SQLdelete(
                    u"FROM cs_taskboard_card WHERE "
                    u"context_object_id IN ({remove})"
                    u"AND board_object_id = '{board_oid}'".format(
                        remove=oids, board_oid=board_oid))
        if to_show:
            for object_ids in partition(list(to_show), self.__SPLIT_COUNT__):
                oids = u",".join([u"'%s'" % sqlapi.quote(x) for x in object_ids])
                sqlapi.SQLupdate(
                    u"cs_taskboard_card SET is_hidden=0 WHERE "
                    u"context_object_id IN ({to_show})"
                    u"AND board_object_id = '{board_oid}'".format(
                        to_show=oids, board_oid=board_oid))

        if to_hide:
            for object_ids in partition(list(to_hide), self.__SPLIT_COUNT__):
                oids = u",".join([u"'%s'" % sqlapi.quote(x) for x in object_ids])
                sqlapi.SQLupdate(
                    u"cs_taskboard_card SET is_hidden=1 WHERE "
                    u"context_object_id IN ({to_hide})"
                    u"AND board_object_id = '{board_oid}'".format(
                        to_hide=oids, board_oid=board_oid))

    def set_last_update(self):
        self.last_update = datetime.datetime.utcnow()

    def get_last_update(self):
        return self.last_update

    def get_display_configs(self):
        result = set()
        for adapter in self.get_card_adapters():
            configs = adapter.get_display_configs()
            if configs:
                result |= set(configs)
        return result

    # =========== Board logic API: to be overridden ===========

    def setup(self):
        """
        This method should only be called once.
        It sets up the board the very first time it is called.

        :return: Nothing
        """
        self.update_board()

    def update_board(self):
        """
        This method updates the board. The update includes:

        - The list of all tasks to be displayed on the board will be recalculated.
          The task cache is being updated.
          If you want to update the cards only, use :py:func:`update_cards` instead.

        - The method :py:func:`prepare_validation` is called.
          Additional, available information can be requested here
          that is required for arranging the cards using method :py:func:`update_cards`.
        - The method :py:func:`update_cards` is called to arrange the cards on the board.
        """
        # clean up team cache, it will get rebuilt on demand
        self.__TEAM_CACHE__.clear()
        # Force looking up available tasks
        self.get_available_tasks(refresh=True)
        self.prepare_validation()
        self.update_cards()
        board = self.get_board()
        board.Reload()

    def prepare_validation(self):
        """
        If more information is needed to arrange the cards on the board,
        it can be provided using this method
        The method is usually used in aggregating boards, e.g. Team Board.
        """
        pass

    def can_change_position(self, card):
        """
        Check whether the card position can be changed at all.

        :param card: the card to be checked
        :type card: instance of ``cs.taskboard.objects.Card``
        :return: True or False
        :rtype: boolean
        """
        return True

    # def can_change_position_to(self, card, row, column):
    #     """
    #     Check whether the card can be changed into a special position
    #     """
    #     return True
    #
    def on_change_position_pre(self, card, row, column):
        """
        This method is called :emphasis:`before` a card changes its position on the board.
        Here you can implement whatever you want, for example: checking conditions,
        preparations for following actions

        This method is applied when the card is moved in the working views
        (e.g. :guilabel:`Current Sprint`).

        :param card: the current card
        :type card: instance of ``cs.taskboard.objects.Card``
        :param row: the target row
        :type row: instance of ``cs.taskboard.objects.Row``
        :param column: the target column
        :type column: instance of ``cs.taskboard.objects.Column``
        :return: Nothing
        """
        pass

    def on_change_position_post(self, card):
        """
        This method is called :emphasis:`after` the card has been moved on the board.
        Here you can implement whatever you want, for example: changing referenced objects

        This method is applied when the card is moved in the working views
        (e.g. :guilabel:`Current Sprint`).

        :param card: the current card
        :type card: instance of ``cs.taskboard.objects.Card``
        :return: Nothing
        """
        pass

    def get_change_position_followup(self, card, row, column):
        """
        Returns an operation and its arguments.
        This operation is performed :emphasis:`after` the card has been moved on the board.

        The predefined operation `cs_taskboard_move_card` can be used to change
        selected data of the task.

        .. code-block:: python

           from cs.taskboard.interfaces.board_adapter import BoardAdapter

           class SampleBoardAdapter(BoardAdapter)

               def get_change_position_followup(self, card, row, column):
                   if sample_condition:
                       return dict(name="cs_taskboard_move_card",
                                   args={"cdb::argument.sample_arg": "sample_value"})

        :param card: the card that was moved
        :type card: instance of ``cs.taskboard.objects.Card``
        :param row: the row that the card gets put into
        :type row: instance of ``cs.taskboard.objects.Row``
        :param column: the column that the card gets put into
        :type column: instance of ``cs.taskboard.objects.Column``
        :return: `name` and `arguments` of an operation
        :rtype: dict

                `name`
                  name of the operation
                `argument`
                  arguments as dict
        """
        # deren Auslösezeitpunkt orientieren, also z.B. cs_taskboard_modify_by_moving
        return None

    def get_header_dialog_name(self):
        """
        Returns the dialog name, which will be used to
        display data in header area of a task board.
        By default, if a context adapter for the board is found,
        use the dialog name provided by `get_header_dialog_name()` from
        the context adapter.

        :return: the name of a dialog
        :rtype: basestring
        """
        context_adapter = self.get_context_adapter()
        if context_adapter:
            return context_adapter.get_header_dialog_name()
        return ""

    def adjust_new_card(self, task_object_id, **kwargs):
        """
        Adjust a card if its task object is newly created, e.g. assign it
        to a proper interval.

        This method is applied when a new card is created because the user has performed
        the :guilabel:`Create new task` operation on the board.

        :param task_object_id: Object UUID of the newly created task
        :return: True or False
        :rtype: boolean
        """
        return False

    def get_due_date(self, card=None):
        """
        Returns the due date on which the cards on the board are evaluated
        with respect to their due date.

        By default, this is the current day.

        :param card: the card getting checked currently
        :return: due date of the board
        :rtype: datetime.date
        """
        return datetime.date.today() - datetime.timedelta(days=1)

    def get_extra_operations(self):
        """
        Defines additional operations to be offered on the board.
        The buttons for the operation are located to the right of the button for the
        operation :guilabel:`Create new task`.

        :returns: a list of dict with keys:

                    `name`
                        name of the operation

                    `classname`
                        the context object class of the operation

                    `context_rest_key`
                        optional, rest_key of the context object, on which
                        the operation should be called

                    `arguments`
                        optional, contains operation arguments as a dict

                    `label`
                        optional, label to be displayed,
                        default is the label from operation configuration

                    `icon`
                        optional, icon to be displayed,
                        default is the icon from operation configuration

        For example, to provide a modify operation on context object of current
        board:

        .. code-block:: python

            from cs.platform.web.rest import support
            ...

            def get_extra_operations(self):
                ctx = self.get_board().ContextObject
                return [{
                    "classname": ctx.GetClassname(),
                    "name": "CDB_Modify",
                    "context_rest_key": support.rest_key(ctx)
                }]

        """
        return []

    def change_card_iteration_pre(self, card, iteration):
        """
        This method is called :emphasis:`before` a card changes its position on the board.
        Here you can implement whatever you want, for example: checking conditions,
        preparations for following actions

        By default it checks the access right for the iterations.

        This method is applied when the card is moved in the :guilabel:`Planning View`.

        :param card: the card to be checked
        :type card: cs.taskboard.objects.Card
        :param iteration: the target iteration for the card
        :type iteration: cs.taskboard.objects.Iteration
        :rtype: HTTPForbidden,  if the access right has not been granted

                Nothing, otherwise
        """
        if (iteration and not iteration.CheckAccess("save")) or \
                (card.Iteration and not card.Iteration.CheckAccess("save")):
            e = ue.Exception(iteration.__no_access_msg__)
            raise HTTPForbidden(str(e))

    def get_working_view_title(self):
        """
        Returns the text with which the working view is labeled.
        Example:
        The working view of a sprint board is labeled as :guilabel:`Active Sprint`.
        The working view of a team board is labeled as :guilabel:`Period und Consideration`.
        :rtype: basestring
        """
        return util.Labels()["web.cs-taskboard.board"]

    def validate_task(self, card_adapter, card, task):
        """
        Checks whether the requested task fit the board logic at all.
        If not, the card would be removed by default.

        :param card_adapter: corresponding card adapter
        :param card: the existing card or `None` for checking adding card
        :type card: cs.taskboard.objects.Card
        :param task: object to be checked
        :return: True, if the task should be represented with a card,
                 otherwise False.
        :rtype: bool
        """
        return True

    def validate_iteration(self, card_adapter, card, task):
        """
        Checks whether the requested task fits the iteration
        logic. If not, the card should be hidden but not removed by default.

        :param card_adapter: corresponding card adapter
        :param card: the existing card or `None` for checking adding card
        :type card: cs.taskboard.objects.Card
        :param task: object to be checked
        :return: True, if the card is assigned to the right iteration, otherwise
                 False.
        :rtype: bool
        """
        return True

    def autoadjust_iteration(self, card_adapter, card, task):
        """
        Try to automatically adjust the iteration assignment of
        an existing card.

        :param card_adapter: corresponding card adapter
        :param card: the existing card
        :type card: cs.taskboard.objects.Card
        :param task: object to be checked
        :return: True, if the card can be assigned to the right iteration, otherwise
                 False.
        :rtype: bool
        """
        return True
