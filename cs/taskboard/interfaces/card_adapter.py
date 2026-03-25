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


from cdb import sqlapi
from cdb import ue
from cs.taskboard.objects import Card
from cs.taskboard.interfaces.column_mapper import ColumnMapper
from cs.taskboard.interfaces.display_attributes import DisplayAttributes
from cs.taskboard.interfaces.row_mapper import RowMapper
from cs.taskboard.constants import UI_VIEWS
from cdb.objects.org import Subject


# cache for the due date of tasks
DUE_DATE_CACHE = {}


# cache for the completion date of tasks
COMPLETION_DATE_CACHE = {}


class CardAdapter(object):
    """
    Defines the behavior of the cards for specified type of task objects
    on a board.
    """
    ROW_MAPPER = RowMapper
    """
    Assign `cs.taskboard.interfaces.row_mapper.RowMapper` to this adapter.
    """

    COLUMN_MAPPER = ColumnMapper
    """
    Assign `cs.taskboard.interfaces.column_mapper.ColumnMapper` to this adapter.
    """

    PROTOCOL_TABLE = ""
    """
    Defines the status protocol table for the task type.

    Task Boards can display tasks of different types.
    The corresponding values for status changes are stored in this table.
    """

    COMPLETION_DATE_ATTRIBUTE = ""
    """
    Defines the field name that contains the completion date.

    Task Boards can display tasks of different types.
    The corresponding date is usually in fields with different names.
    """

    DUE_DATE_ATTRIBUTE = ""
    """
    Defines the field name that contains the target or due date.

    Task Boards can display tasks of different types.
    The corresponding date is usually in fields with different names.
    """

    STATUS_ATTRIBUTE = "status"
    """
    Defines the field name that contains the status of the task.

    Task Boards can display tasks of different types.
    By default the status is stored within the attribute 'status'.
    """

    MOD_DATE_ATTRIBUTE = "cdb_mdate"
    """
    Defines the field name that contains the date of the last modification
    of the tasks.

    Task Boards can display tasks of different types.
    By default the modification date is stored within the attribute 'cdb_mdate'.
    """

    DISPLAY_ATTRIBUTES = DisplayAttributes
    """
    Assign `cs.taskboard.interfaces.display_attributes.DisplayAttributes` to this adapter.
    """

    DISPLAY_CONFIGS = {
        "*": "cs_taskboard_card_web_compact",
        UI_VIEWS["BOARD"]: "cs_taskboard_card_web"
    }
    """
    Map the `view name` on task board User Interface to a configured dialog to use its layout.
    Default config can be defined with `*` as view name.

    View names predefined in the :ref:`constants` module.

        .. code-block:: python

            from cs.taskboard.interfaces.board_adapter import CardAdapter
            from cs.taskboard.constants import UI_VIEWS

            class SampleProjectTaskCardAdapter(CardAdapter)

                DISPLAY_CONFIGS = {
                    "*": "cs_taskboard_card_web",
                    UI_VIEWS["BACKLOG"]: "cs_taskboard_card_web_compact"
                }

    """

    USE_CDB_MDATE = True
    """
    Defines if the adapter may use a modification date attribute to evaluate changes on tasks.

    The evaluation of the modification attribute is a good way to enhance the performance.
    It will only be of any use, if such an attribute is defined for the class of the task
    and adjusted with every change to the task.
    By default, the change log attribute 'cdb_mdate' is used for this purpose and
    the enhancement is activated.
    """

    @classmethod
    def get_due_date_attribute(cls, task):
        return cls.DUE_DATE_ATTRIBUTE if hasattr(task, cls.DUE_DATE_ATTRIBUTE) else ""

    @classmethod
    def get_completion_date_attribute(cls, task):
        return cls.COMPLETION_DATE_ATTRIBUTE if hasattr(task, cls.COMPLETION_DATE_ATTRIBUTE) else ""

    @classmethod
    def get_status_attribute(cls, task):
        return cls.STATUS_ATTRIBUTE if hasattr(task, cls.STATUS_ATTRIBUTE) else ""

    @classmethod
    def get_mod_date_attribute(cls, task):
        if not cls.USE_CDB_MDATE:
            return ""
        return cls.MOD_DATE_ATTRIBUTE if hasattr(task, cls.MOD_DATE_ATTRIBUTE) else ""

    @classmethod
    def add_done_status(cls, task_oid, status):
        """
        Deprecated function
        """
        import warnings
        warnings.warn("Use of add_done_status is deprecated.", DeprecationWarning, stacklevel=2)

    @classmethod
    def add_cards(cls, board_adapter, ids):
        # Method called by board updating.
        # add new cards to board
        for new_id in ids:
            cls.add_card(board_adapter, new_id, batch_mode=True)

    @classmethod
    def add_card(cls, board_adapter, task_object_id,
                 title=None, attachment=None, batch_mode=False):
        """
        Add new card for specified object if allowed.
        """
        task = board_adapter.get_task(task_object_id)
        # Validation
        # Allowed by team member check? Allowed by task data check?
        if not board_adapter.validate_team(task) or \
                not cls.valid_task(board_adapter, task) or \
                not board_adapter.validate_task(cls, None, task):
            if not batch_mode:
                # Stop and notify the user about it if not in batch mode.
                # TODO: message
                raise Exception("Task not suit for the board")
            return None

        # Visibility
        #  Shown by iteration logic?
        visible = board_adapter.validate_iteration(cls, None, task)
        # Init position for the new card possible?
        row, column = cls.get_init_position(board_adapter, task)
        visible = visible and bool(row) and bool(column)
        card = Card.createCard(
            board_object_id=board_adapter.board_object_id,
            context_object_id=task_object_id,
            row_object_id=row.cdb_object_id,
            column_object_id=column.cdb_object_id,
            sprint_object_id="",
            is_hidden=int(not visible))
        cls.setup_card(board_adapter, card, task)
        cls.check_visibility(board_adapter, card, task)
        return card

    @classmethod
    def get_init_position(cls, board_adapter, task):
        row = cls.ROW_MAPPER.init_row(board_adapter, cls, task)
        column = cls.COLUMN_MAPPER.init_column(board_adapter, cls, task)
        return row, column

    @classmethod
    def valid_task(cls, board_adapter, task):
        # TODO: Deprecated Should be removed in future version
        return True

    @classmethod
    def get_feedback(cls, board_adapter, task):
        return ""

    @classmethod
    def validate(cls, board_adapter, card, task):
        """
        Validate the existing card. Invalid card should be removed by board updating.
        """
        # here we check team members
        if not board_adapter.validate_team(task):
            return False
        # check other data of the task
        return board_adapter.validate_task(cls, card, task) and \
               cls.valid_task(board_adapter, task)

    @classmethod
    def check_visibility(cls, board_adapter, card, task):
        """
        Check whether to show an existing card.
        Serves as pre-filter.
        """
        # Check board logic i.e. iteration logic and attempt to fix it
        if not board_adapter.validate_iteration(cls, card, task) and \
                not board_adapter.autoadjust_iteration(cls, card, task):
            return False
        # Check the mappers: whether the card is in right position.
        # If not, try to adjust position of the card automatically.
        available = board_adapter._get_available_task_ids_by_adapter(cls)
        if card.context_object_id not in available:
            return False
        visible = cls.ROW_MAPPER.validate(board_adapter, cls, card, task) and \
                  cls.COLUMN_MAPPER.validate(board_adapter, cls, card, task)
        if not visible:
            return cls.auto_change_position(board_adapter, card, task)
        return True

    # def can_change_position_to(self, row, column):
    #     # Check whether the card can be changed into a special position
    #     return self.ROW_MAPPER.can_change(self, row) and \
    #            self.COLUMN_MAPPER.can_change(self, column)
    #
    @classmethod
    def auto_change_position(cls, board_adapter, card, task):
        # Check whether the card can be changed into a special position
        return cls.ROW_MAPPER.auto_change(board_adapter, cls, card, task) and \
               cls.COLUMN_MAPPER.auto_change(board_adapter, cls, card, task)

    @classmethod
    def on_change_position_pre(cls, board_adapter, card, row, column):
        cls.ROW_MAPPER.change_to(board_adapter, cls, card, row)
        cls.COLUMN_MAPPER.change_to(board_adapter, cls, card, column)

    @classmethod
    def change_to_group(cls, board_adapter, card, group_name, group_obj):
        """
        This method can be overwritten to adjust card to changed group.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param group_name: String that identifies target group
        :type group_name: basestring
        :param group_obj: UUID og the target row
        :type group_obj: basestring or object id
        """
        pass

    @classmethod
    def change_position(cls, board_adapter, card, row, column):
        cls.on_change_position_pre(board_adapter, card, row, column)
        card.Update(row_object_id=row.cdb_object_id,
                    column_object_id=column.cdb_object_id)
        cls.on_change_position_post(board_adapter, card)

    @classmethod
    def get_done_status_list(cls):
        get_done_status = getattr(cls.COLUMN_MAPPER, "get_done_status_list", None)
        if get_done_status:
            return get_done_status()
        return []

    @classmethod
    def add_due_date(cls, oid, due_date):
        DUE_DATE_CACHE[oid] = due_date

    @classmethod
    def add_completion_date(cls, oid, completion_date):
        COMPLETION_DATE_CACHE[oid] = completion_date

    @classmethod
    def get_cards_for_iteration(cls, board_adapter, iteration):
        """
        Returns the cards for the tasks to be displayed on the board.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param iteration: the iteration
        :type iteration: cs.taskboard.objects.Iteration
        :return: a list of  cards
        :rtype: list of `cs.taskboard.objects.Card` objects
        """
        available = board_adapter._get_available_task_ids_by_adapter(cls)
        return [card for card in iteration.Cards
                if card.context_object_id in available]

    @classmethod
    def get_display_configs(cls):
        if cls.DISPLAY_CONFIGS:
            return list(cls.DISPLAY_CONFIGS.values())
        return []

    # # =========== Board logic API: to be overridden ===========

    @classmethod
    def find_subject(cls, task):
        """
        Returns the object (usually of type cdb.objects.org.Person)
        that is responsible for the given task.
        By default, this object will be the cdb.objects.org.Subject
        the task is assigned to.

        :param obj: the task to be evaluated
        :type obj: cdb.objects.Object
        :rtype: cdb.objects.org.Subject
        """
        # FIXME: BySubjectReferrer can be changed...
        def find(cls):
            for spec in cls.__specializations__:
                if hasattr(spec, "__subject_type__"):
                    if spec.__subject_type__ == task.subject_type:
                        return spec.BySubjectReferrer(task)
                else:
                    subj = find(spec)
                    if subj:
                        return subj
        return find(Subject)

    @classmethod
    def get_available_records(cls, board_adapter):
        """
        Returns a set consisting of unique records.
        Each entry is a record representing an object of the corresponding task type.
        These objects are basically available for usage on the board.

        .. note ::

            If the class is part of a class hierarchy,
            make sure to only return records with ``cdb_classname``
            matching the classname this card adapter is registered for.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :rtype: record set
        """
        return set()

    @classmethod
    def setup_board(cls, board_adapter):
        """
        This method should only be called once.
        It sets up the board the very first time it is called,
        e.g. to adjust some attributes of the board.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        """
        pass

    @classmethod
    def get_change_date(cls, task):
        """
        Deprecated since cs.taskboard 15.1.2

        Returns the date the last change of status on the given task has been done.
        If class of task has a status protocol, the latest date of a status change
        to the active status should be returned, else None is being returned

        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: date of the last change to the active status of the given task
        :rtype: datetime.datetime
        """
        status_attr = cls.get_status_attribute(task)
        if not cls.PROTOCOL_TABLE or not status_attr:
            return None
        pkeys = task.ToObjectHandle().getClassDef().getKeyNames()
        keys = " AND ".join(["%s = '%s'" % (key, task[key]) for key in pkeys])
        stmt = """cdbprot_newstate = {status} AND {keys}""".format(
            keys=keys, status=task[status_attr])
        result = sqlapi.RecordSet2(cls.PROTOCOL_TABLE, stmt)
        if result:
            return max([x.cdbprot_zeit for x in result])
        return None

    @classmethod
    def get_completion_date(cls, oid):
        """
        Returns the completion date of the given task.
        Default is the value of the attribute defined
        in :py:attr:`COMPLETION_DATE_ATTRIBUTE`.

        :param oid: the object id of the task represented by the card
        :type oid: string
        :return: completion date of the given task
        :rtype: datetime.datetime
        """
        return COMPLETION_DATE_CACHE.get(oid, None)

    @classmethod
    def get_due_date(cls, oid):
        """
        Returns the due date of the given task.
        Default is the value of the attribute defined in :py:attr:`DUE_DATE_ATTRIBUTE`.

        :param oid: the object id of the task represented by the card
        :type oid: string
        :return: due date of the given task
        :rtype: datetime.datetime
        """
        return DUE_DATE_CACHE.get(oid, None)

    @classmethod
    def set_completion_date(cls, task, completion_date, overwrite=False):
        """
        Adjusts the completion date of the given task.
        The value of the attribute defined in :py:attr:`DUE_DATE_ATTRIBUTE`
        is being modified.

        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :param completion_date: the new completion date for the task object
        :type completion_date: datetime.datetime
        :param overwrite: overwrite the value if already set. Default is False
        :type overwrite: boolean
        """
        if not cls.COMPLETION_DATE_ATTRIBUTE:
            return
        if not task[cls.COMPLETION_DATE_ATTRIBUTE] or overwrite:
            if task[cls.COMPLETION_DATE_ATTRIBUTE] != completion_date:
                changes = {cls.COMPLETION_DATE_ATTRIBUTE: completion_date}
                cca = task.MakeChangeControlAttributes()
                if cca:
                    changes.update({
                        "cdb_mdate": cca["cdb_mdate"],
                        "cdb_mpersno": cca["cdb_mpersno"],
                        })
                task.Update(**changes)

    @classmethod
    def set_due_date(cls, task, due_date, overwrite=False):
        """
        Adjusts the due date of the given task.
        The value of the attribute defined in :py:attr:`DUE_DATE_ATTRIBUTE`
        is being modified.

        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :param due_date: the new due date for the task object
        :type due_date: datetime.datetime
        :param overwrite: overwrite the value if already set. Default is False
        :type overwrite: boolean
        """
        if not cls.DUE_DATE_ATTRIBUTE:
            return
        if not task[cls.DUE_DATE_ATTRIBUTE] or overwrite:
            if task[cls.DUE_DATE_ATTRIBUTE] != due_date:
                changes = {cls.DUE_DATE_ATTRIBUTE: due_date}
                cca = task.MakeChangeControlAttributes()
                if cca:
                    changes.update({
                        "cdb_mdate": cca["cdb_mdate"],
                        "cdb_mpersno": cca["cdb_mpersno"],
                        })
                task.Update(**changes)

    @classmethod
    def setup_card(cls, board_adapter, card, task):
        """
        Sets up the card when it is added to the board.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        """
        pass

    @classmethod
    def can_change_position(cls, board_adapter, card):
        """
        Check whether the card position can be changed at all

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :return: True (default) or False
        :rtype: bool
        """
        return True

    @classmethod
    def on_change_position_post(cls, board_adapter, card):
        """
        This method is called :emphasis:`after` the card has been moved on the board.
        Here you can implement whatever you want, for example: changing referenced objects

        This method is applied when the card is moved in the working views
        (e.g. :guilabel:`Active Sprint`).

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :return: Nothing
        """
        pass

    @classmethod
    def get_display_attributes(cls, board_adapter, card, task):
        return cls.DISPLAY_ATTRIBUTES(board_adapter, cls, card, task)

    @classmethod
    def get_card_color(cls, board_adapter, card, task):
        """
        Label and color for highlighting the card.

        :param board_adapter: the current board adapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: dict with keys: `label` used for tool tip
                 and `color` used for highlighting
        """
        return None

    @classmethod
    def get_filters(cls, board_adapter, card, task):
        """
        Returns the values of the business object represented by the card for the filters of the board.

        If a filter cannot be applied to the business object, use an empty string as a placeholder.

        .. code-block:: python

            class SampleProjectTaskCardAdapter(object):

                def get_filters(cls, board_adapter, card, task):
                    return {
                        "categories_filter": {"label": task.category,
                                              "value": task.mapped_category},
                        "responsible_filter": {"label": task.mapped_subject_name,
                                               "value": task.subject_id},
                        "priority_filter": {"label": "", "value": ""}
                    }


        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: dict with keys as filter names
                 provided by `cs.taskboard.interfaces.board_adapter.BoardAdapter`
                 and values as a dict with identifier as keys and visible values as a dict containing
                 values and labels.
        """
        return dict()

    @classmethod
    def get_create_operation(cls, board_adapter):
        """
        Returns class, operation name for the creation and operation arguments
        with which a new task can be created.

        .. note ::

            The arguments for creating a new class are only applied if the property
            :guilabel:`Prefer Classic UI in Hybrid Client` is not set at the operation
            ``CDB_Create`` of the corresponding task class.

            If the context object of the board is not assigned to the task using a foreign key
            (e.g. open issues to project task), but using a relationship class, then it is
            recommended to pass the keys of the context object as system arguments.
            These arguments can be requested in User Exit ``create / post`` in ``ctx.sys_args``
            and used to create a record of the relationship class.

        .. note ::

            If the create operation is not allowed for the current user, it is excluded
            by the CardAdapter.


        .. code-block :: python

            from cdb.constants import kOperationNew
            from cs.pcs.issues import Issue

            class SampleIssueCardAdapter(object):

            @classmethod
            def get_create_operation(cls, board_adapter):
                ctx = board_adapter.get_board().ContextObject
                return {
                    "class": Issue,
                    "name": kOperationNew,  # key `name` optional
                    "arguments": {
                        "cdb_project_id": getattr(ctx, "cdb_project_id", ""),
                        "task_id": getattr(ctx, "task_id", "")
                    }
                }

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :returns: None or dict (see example below)

        .. rubric :: Example return values

        Examples below show two variants of providing operation information.
        If the ``class`` key is given, it will be used.
        ``classname`` is used as a fallback and used especially for subclasses
        without a dedicated ``cdb.objects.Object`` class.

        If using the simple ``classname``,
        you also have to provide ``label`` and ``icon``
        since they cannot be calculated automatically based on ``class``.

        .. code-block :: python

            from my.module import MyTask

            variant_1 = {
                "class": MyTask,       # cdb.objects.Object class
                "name": "CDB_Create",  # optional operation name (defaults to "CDB_Create")
                "arguments": {},       # optional operation arguments
            }

            variant_2 = {
                "classname": "my_subclass",  # classname from Data Dictionary
                "label": "Subclass Task",    # button label in session language
                "icon": "/resources/icons/byname/foo",  # button icon URL
                # keys "name" and "arguments" as above
            }
        """
        return None

    @classmethod
    def on_iteration_start_pre(cls, board_adapter, iteration):
        """
        This method is called :emphasis:`before` an iteration will be :emphasis:`started`.
        Here you can implement whatever you want.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param iteration: the iteration to be started
        :type iteration: cs.taskboard.objects.Iteration
        :return: Nothing
        """
        pass

    @classmethod
    def on_iteration_start_post(cls, board_adapter, iteration):
        """
        This method is called :emphasis:`after` an iteration has been :emphasis:`started`.
        Here you can implement whatever you want.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param iteration: the iteration just started
        :type iteration: cs.taskboard.objects.Iteration
        :return: Nothing
        """
        pass

    @classmethod
    def on_iteration_stop_pre(cls, board_adapter, iteration):
        """
        This method is called :emphasis:`before` an iteration will be :emphasis:`finished`.
        Here you can implement whatever you want.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param iteration: the iteration to be ended
        :type iteration: cs.taskboard.objects.Iteration
        :return: Nothing
        """
        pass

    @classmethod
    def on_iteration_stop_post(cls, board_adapter, iteration):
        """
        This method is called :emphasis:`after` an iteration has been :emphasis:`finished`.
        Here you can implement whatever you want.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param iteration: the iteration just ended
        :type iteration: cs.taskboard.objects.Iteration
        :return: Nothing
        """
        pass

    @classmethod
    def get_display_configs_for_task(cls, board_adapter, card, task):
        """
        Return display configurations of different views
        for specified task on current board. Default is
        :py:attr:`DISPLAY_CONFIGS`.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: dict with keys as view IDs
                 defined in `cs.taskboard.constants.UI_VIEWS`
                 and values as dialog names.
        """
        return cls.DISPLAY_CONFIGS

    @classmethod
    def is_new(cls, task):
        """
        Return whether the given task is in status with the meaning of `New`.
        They may be irrelevant to a working process and so filtered out from
        the views.

        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        """
        return False
