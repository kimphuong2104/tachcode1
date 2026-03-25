#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import calendar
import logging
from collections import defaultdict
from cdb import auth
from cdb import ue
from cdb import tools
from cdb import sig
from cdb import sqlapi
from cdb import util
from cdb import lru_cache
from cdb import transactions
from cdb.constants import kOperationNew
from cdb.constants import kOperationModify
from cdb.constants import kOperationDelete
from cdb.util import SkipAccessCheck
from cdb.objects import Object
from cdb.objects import ByID
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMapping_N
from cdb.objects.org import Subject
from cdb.objects.operations import operation
from cdb.objects.operations import form_input
from cdb.platform.gui import CDBCatalog, I18nCatalogEntry
from cdb.platform.mom import entities
from cdb.typeconversion import from_legacy_date_format
from cs.platform.web.uisupport import get_webui_link
from cs.web.components.ui_support.user_settings import SettingsModel
from cs.taskboard.constants import SETTING_ID
from cs.taskboard import utils

fBoard = Forward(__name__ + ".Board")
fRow = Forward(__name__ + ".Row")
fColumn = Forward(__name__ + ".Column")
fIteration = Forward(__name__ + ".Iteration")
fCard = Forward(__name__ + ".Card")
fTeamMember = Forward(__name__ + ".TeamMember")
fTimeUnit = Forward(__name__ + ".TimeUnit")
fTeamMember = Forward(__name__ + ".TeamMember")


class Board(Object):
    __classname__ = "cs_taskboard_board"
    __maps_to__ = "cs_taskboard_board"

    __SPLIT_COUNT__ = 999

    Rows = Reference_N(fRow,
                       fRow.board_object_id == fBoard.cdb_object_id,
                       order_by=fRow.display_order)

    Columns = Reference_N(fColumn,
                          fColumn.board_object_id == fBoard.cdb_object_id,
                          order_by=fColumn.display_order)

    Iterations = Reference_N(fIteration,
                          fIteration.board_object_id == fBoard.cdb_object_id,
                          order_by=fIteration.end_date)

    Cards = Reference_N(fCard, fCard.board_object_id == fBoard.cdb_object_id,
                        order_by=fCard.display_order)

    VisibleCards = Reference_N(fCard,
                               fCard.board_object_id == fBoard.cdb_object_id,
                               fCard.is_hidden != 1,
                               order_by=fCard.display_order)

    TimeUnit = Reference_1(fTimeUnit, fBoard.interval_type)
    TeamMembers = Reference_N(fTeamMember, fTeamMember.taskboard_oid == fBoard.cdb_object_id)
    TeamMemberByTypes = ReferenceMapping_N(
        fTeamMember,
        fTeamMember.taskboard_oid == fBoard.cdb_object_id,
        indexed_by=fTeamMember.subject_type
    )

    def _getActiveIteration(self):
        iterations = self.Iterations.KeywordQuery(status=50)
        if len(iterations):
            return iterations[0]
        return None
    ActiveIteration = ReferenceMethods_1(fBoard, lambda self: self._getActiveIteration())

    OpenIterations = Reference_N(fIteration,
                                 fIteration.board_object_id == fBoard.cdb_object_id,
                                 fIteration.status.one_of(0, 50),
                                 order_by=fIteration.end_date)

    def _getNextIteration(self):
        iterations = self.Iterations.KeywordQuery(status=0)
        if len(iterations):
            return iterations[0]
        return None
    NextIteration = ReferenceMethods_1(fBoard, lambda self: self._getNextIteration())

    CompletedIterations = Reference_N(fIteration,
                                fIteration.board_object_id == fBoard.cdb_object_id,
                                fIteration.status == 200,
                                order_by=fIteration.end_date)

    def _getContextObject(self):
        return ByID(self.context_object_id)
    ContextObject = ReferenceMethods_1(Object, lambda self: self._getContextObject())

    def getAdapter(self):
        return get_board_adapter(self.cdb_object_id, self.board_api)

    def set_fields_readonly(self, ctx):
        adapter = self.getAdapter()
        read_only_fields = adapter.get_readonly_fields()
        read_only_fields.add("template_object_id")
        if not self.CheckAccess("save"):
            read_only_fields.add("description")
        if not adapter.has_preview():
            read_only_fields.add("auto_create_iteration")
        if read_only_fields:
            ctx.set_fields_readonly(read_only_fields)

    event_map = {
        # TODO: copy post? AFTER copying relships!
        ("create", "post"): "setupBoard",
        ("modify", "pre_mask"): ("init_board_type_names", "set_fields_readonly"),
        ("modify", "pre"): "keep_interval",
        ("modify", "post"): "adjust_interval",
        ("delete", "post"): ("deleteUserSettings", "removeAdapter",
                             "remove_cards")
    }

    @classmethod
    def get_boards_by_context_object_ids(cls, object_ids):
        if type(object_ids) not in (list, set, tuple):
            object_ids = [object_ids]
        context_ids = map(lambda x: u"'{}'".format(x), object_ids)
        id_string = ", ".join(context_ids)
        if not id_string:
            return []
        return cls.Query(
            "is_template = 0 AND is_aggregation = 0 AND available = 1 "
            "AND cdb_object_id IN ("
            "SELECT board_object_id FROM cs_taskboard_card "
            "WHERE context_object_id IN ({}))".format(id_string)
        )

    @classmethod
    def refresh_boards_by_context_object_ids(cls, object_ids, active_board=None):
        boards = cls.get_boards_by_context_object_ids(object_ids)
        for b in boards:
            if not active_board or b.cdb_object_id != active_board.cdb_object_id:
                b.updateBoard()

    def keep_interval(self, ctx):
        names = ctx.dialog.get_attribute_names()
        interval_length = ctx.dialog.interval_length \
            if "interval_length" in names else str(self.interval_length).decode('utf-8')
        interval_type = ctx.dialog.interval_type \
            if "interval_type" in names else self.interval_type

        if ctx.object.start_date and self.start_date:
            new_start_date = from_legacy_date_format(ctx.object.start_date).date()
            old_start_date = utils.ensure_date(self.start_date)

            changed = int(interval_length != ctx.object.interval_length or
                      interval_type != ctx.object.interval_type or
                      new_start_date != old_start_date)
        elif not ctx.object.start_date and not self.start_date:
            changed = int(interval_length != ctx.object.interval_length or
                      interval_type != ctx.object.interval_type)
        else:
            changed = 1

        ctx.keep("changed_interval", changed)

    def getFollowUpIteration(self, predecessor_iteration):
        iters = self.Iterations
        count = len(iters) - 1
        for i in range(count):
            if iters[i] == predecessor_iteration:
                return iters[i + 1]
        return None

    def adjust_interval(self, ctx=None):
        changed_interval = int(ctx.ue_args["changed_interval"]) if ctx else 1
        if changed_interval:
            last_iteration = None
            for iteration in self.Iterations:
                if iteration.status == 0:
                    changes = self._next_iteration_timeframe(last_iteration=last_iteration)
                    if changes:
                        iteration.Update(**changes)
                last_iteration = iteration

    def get_present_timeframe(self):
        start_date = None
        end_date = None
        if self.Iterations:
            start_date = self.Iterations[0].start_date
            end_date = self.Iterations[0].end_date
        return start_date, end_date

    def get_total_timeframe(self):
        start_date = None
        end_date = None
        if self.Iterations:
            start_date = self.Iterations[0].start_date
            end_date = self.Iterations[-1].end_date
        return start_date, end_date

    def _next_iteration_timeframe(self, last_iteration):
        start_date = self.start_date
        if last_iteration and last_iteration.end_date:
            start_date = last_iteration.end_date + datetime.timedelta(days=1)
        result = self._calc_next_timeframe(start_date)
        return result

    def _calc_next_timeframe(self, start_date):
        if not start_date:
            return {}
        changes = {}
        end_date = start_date
        interval_type = self.interval_type
        interval_length = self.interval_length
        if interval_type and interval_length and start_date:
            if interval_type == "1":
                end_date = start_date + datetime.timedelta(days=interval_length - 1)
            elif interval_type == "2":
                end_date = start_date + datetime.timedelta(days=interval_length * 7 - 1)
            elif interval_type == "3":
                end_date = add_months(start_date, interval_length)
                end_date -= datetime.timedelta(days=1)
        if start_date and end_date:
            changes.update(start_date=start_date, end_date=end_date)
        return changes

    def deleteUserSettings(self, ctx=None):
        SettingsModel(SETTING_ID, self.cdb_object_id).delete()

    def remove_cards(self, ctx=None):
        self.Cards.Delete()

    def removeAdapter(self, ctx=None):
        self.__taskboard_adapter__ = None

    def getCardAdapter(self, card):
        return self.getAdapter().get_card_adapter(card)

    def addCard(self, task, title=None, attachment=None, batch_mode=False):
        return self.getAdapter().add_card(task, title, attachment, batch_mode)

    def setupBoard(self, ctx=None):
        if not self.is_template:
            self.getAdapter()._setup()

    def get_iteration_by_due_date(self, due_date):
        """
        :param due_date: Target date of a card object.
        :type due_date: datetime.date or datetime.datetime
        """
        # step through iterations by order
        if not due_date:
            return None

        due_date = utils.ensure_date(due_date)

        for iteration in self.Iterations:
            if not iteration.is_completed() and iteration.start_date and iteration.end_date:
                if due_date <= iteration.end_date:
                    return iteration
        return None

    def get_iteration_by_time_interval(self, start, end):
        # step through iterations by order
        if not start or not end:
            return None
        for iteration in self.Iterations:
            if not iteration.is_completed() and iteration.start_date and iteration.end_date:
                if (start <= iteration.end_date and iteration.end_date <= end or
                        iteration.start_date <= start and end <= iteration.end_date):
                    return iteration
        return None

    @classmethod
    def adjust_card_to_interval(cls, task, start, end):
        """
        Adjust all cards to the given time interval.

        :param task: the task to be evaluated
        :type task: cdb.objects.Object
        :param start: the start of the interval
        :type start: datetime.date
        :param end: the end of the interval
        :type end: datetime.date
        """
        cards = Card.KeywordQuery(context_object_id=task.cdb_object_id)
        for card in cards:
            prj_iter = card.Board.get_iteration_by_time_interval(start, end)
            if prj_iter:
                card.sprint_object_id = prj_iter.cdb_object_id
            else:
                card.sprint_object_id = u""

    def updateBoard(self):
        if utils.is_board_update_activated():
            self.Reload()
            if not self.is_template:
                self.getAdapter().update_board()
            utils.clear_update_stack()
            sig.emit(self.__class__, "board_updated")(self)

    def on_create_pre_mask(self, ctx):
        if ctx.object:
            existing_boards = Board.KeywordQuery(
                context_object_id=ctx.object["context_object_id"])
            if existing_boards:
                raise ue.Exception("cs_taskboard_context_limit")

    def get_detail_outlets(self):
        adapter = self.getAdapter()
        if adapter:
            return getattr(adapter, "DETAIL_OUTLETS", {})
        return {}

    def get_allowed_classes(self):
        adapter = self.getAdapter()
        if adapter:
            return adapter.get_all_content_classnames()
        return set()

    def _get_class_converter_map(self):
        acc_map = {}
        for cls_name in self.get_allowed_classes():
            cls_def = entities.CDBClassDef(cls_name)
            cls_label = str(cls_def.getDesignation())
            acc_map[cls_label] = cls_name
            acc_map[cls_name] = cls_label
        return acc_map

    def _convert_to_content_types(self, my_types):
        acc_map = self._get_class_converter_map()
        return [x for x in [acc_map.get(x, None) for x in my_types] if x]

    def _convert_to_content_names(self, my_types):
        acc_map = self._get_class_converter_map()
        return [x for x in [acc_map.get(x, None) for x in my_types] if x]

    def init_board_type_names(self, ctx):
        content_types = self.content_types.split(',')
        try:
            content_types_names = self._convert_to_content_names(content_types)
        except ValueError as err:
            logging.error("Error while looking up board content types: %s", err)
            return
        ctx.set("content_types_names", ','.join(content_types_names))

    def on_create_post(self, ctx):
        with SkipAccessCheck():
            templates = Board.KeywordQuery(is_template=1)
            if templates:
                tmpl = templates[0]
                for col in tmpl.Columns:
                    col.Copy(board_object_id=self.cdb_object_id)
                for row in tmpl.Rows:
                    row.Copy(board_object_id=self.cdb_object_id)

    def access_granted(self):
        if self.CheckAccess("open taskboard", auth.persno):
            return True
        return False

    def on_cs_taskboard_open_now(self, ctx):
        if not self.CheckAccess("open taskboard", auth.persno):
            raise ue.Exception("cs_taskboard_no_access_rights")

        ui_url = get_webui_link(None, self)
        if ui_url:
            ctx.url(ui_url)

    @classmethod
    def on_cs_taskboard_create_team_board_pre_mask(cls, ctx):
        board = Board.Query()[0]
        sig.emit(Board, "cs_taskboard_create_team_board", "pre_mask")(board, ctx)

    @classmethod
    def on_cs_taskboard_create_team_board_now(cls, ctx):
        board = _create_board(ctx, check_access="create")
        ctx.set_followUpOperation('cs_taskboard_open', op_object=board)

    def getBoardContentTypes(self):
        if self.content_types:
            return self.content_types.split(',')
        return list(self.getAdapter().get_all_content_classnames())

    def getBoardContentTypesAndNames(self):
        if self.is_aggregation:
            return defaultdict(str)
        content_types = self.getBoardContentTypes()
        content_types_names = self._convert_to_content_names(content_types)
        return {
            "content_types": ",".join(content_types),
            "content_types_names": ",".join(content_types_names)
        }

    @classmethod
    def adjust_display_order(cls, board_oid, moved_cards, succsessor_oid):
        if not moved_cards:
            return
        gap = len(moved_cards) * 10
        new_position = 0
        board = Board.ByKeys(board_oid)
        next_iteration = Sprint.ByKeys(moved_cards[0].sprint_object_id)

        # determine successor card of next iteration if existing and needed
        if next_iteration:
            while not succsessor_oid and next_iteration:
                next_iteration = board.getFollowUpIteration(next_iteration)
                if next_iteration and next_iteration.Cards:
                    succsessor_oid = next_iteration.Cards[0].cdb_object_id
            if not succsessor_oid:
                cards = board.Cards.KeywordQuery(sprint_object_id="")
                if cards:
                    succsessor_oid = cards[0].cdb_object_id

        # open gap for new display order
        if succsessor_oid:
            succsessor_card = Card.ByKeys(succsessor_oid)
            new_position = succsessor_card.display_order
            for cards in utils.partition(moved_cards, cls.__SPLIT_COUNT__):
                card_oids = ", ".join(["'%s'" % sqlapi.quote(c.cdb_object_id)
                                       for c in cards])
                stmt = """
                cs_taskboard_card
                SET display_order = display_order + {gap}
                WHERE board_object_id = '{board_oid}'
                AND cdb_object_id NOT IN ({card_oids})
                AND display_order >= {new_position}
                """.format(gap=gap,
                           board_oid=board_oid,
                           card_oids=card_oids,
                           new_position=new_position)
                sqlapi.SQLupdate(stmt)
        else:
            cards = Card.KeywordQuery(board_object_id=board_oid)
            new_position = 10 + max([0] + [c.display_order for c in cards])

        # adjust moved tasks to new display order
        for card in moved_cards:
            stmt = """
            cs_taskboard_card
            SET display_order = {new_position}
            WHERE board_object_id = '{board_oid}'
            AND cdb_object_id = '{card_oid}'
            """.format(new_position=new_position,
                       board_oid=board_oid,
                       card_oid=card.cdb_object_id)
            sqlapi.SQLupdate(stmt)
            new_position += 10

        # close gaps in new display order
        cls._close_display_order_gaps(board_oid)

    @classmethod
    def _close_display_order_gaps(cls, board_oid):
        stmt = """
        SELECT backlog, start_date, display_order, cdb_object_id FROM
            (SELECT c.board_object_id, i.start_date, display_order,
                    c.cdb_object_id, 0 AS backlog
             FROM cs_taskboard_card c JOIN cs_taskboard_iteration i
             ON c.sprint_object_id = i.cdb_object_id
             UNION
             SELECT c.board_object_id, NULL AS start_date, display_order,
                    c.cdb_object_id, 1 AS backlog
             FROM cs_taskboard_card c
             WHERE c.sprint_object_id IS NULL OR c.sprint_object_id = '') a
        WHERE board_object_id = '{board_oid}'
        ORDER BY backlog, start_date, display_order
        """.format(board_oid=board_oid)
        result = sqlapi.RecordSet2(sql=stmt)
        i = 0
        new_order = defaultdict(list)
        for r in result:
            i += 10
            diff = i - r.display_order
            if diff:
                new_order[diff] += [r.cdb_object_id]
        for diff, oids in new_order.items():
            for object_ids in utils.partition(oids, cls.__SPLIT_COUNT__):
                card_oids = ", ".join(["'%s'" % sqlapi.quote(oid)
                                       for oid in object_ids])
                upd_stmt = """
                cs_taskboard_card
                SET display_order = display_order + {diff}
                WHERE cdb_object_id IN ({cdb_object_id})
                """.format(diff=diff, cdb_object_id=card_oids)
                sqlapi.SQLupdate(upd_stmt)

    def close_display_order_gaps(self):
        Board._close_display_order_gaps(self.cdb_object_id)

    def copyBoard(self, check_access=None, **kwargs):

        if check_access:
            if not util.check_access(self.GetTableName(), self._CopyInternal(**kwargs), check_access):
                raise ue.Exception("cs_taskboard_board_create_access_denied")

        with transactions.Transaction():
            obj = self.Copy(**kwargs)
            # Copy Iterations, Columns and Rows
            for x in self.Iterations:
                x.Copy(board_object_id=obj.cdb_object_id)
            for x in self.Columns:
                x.Copy(board_object_id=obj.cdb_object_id)
            for x in self.Rows:
                x.Copy(board_object_id=obj.cdb_object_id)
            sig.emit(Board, "copyBoard")(obj)
            return obj

    def modifyBoard(self, **kwargs):
        with transactions.Transaction():
            self.Update(**kwargs)
            self.adjust_interval()


class Row(Object):
    __classname__ = "cs_taskboard_row"
    __maps_to__ = "cs_taskboard_row"


class Column(Object):
    __classname__ = "cs_taskboard_column"
    __maps_to__ = "cs_taskboard_column"


class Iteration(Object):
    __classname__ = "cs_taskboard_iteration"
    __maps_to__ = "cs_taskboard_iteration"

    """
    The system proposes a name for the iteration.
    The name consists of a prefix and a continuous number.
    You can overwrite the prefix.
    """

    __no_access_msg__ = ""
    __single_iteration_msg__ = "cs_taskboard_single_iteration"
    __automatic_assignment_active__ = False

    Board = Reference_1(fBoard, fIteration.board_object_id)
    Cards = Reference_N(fCard, fCard.sprint_object_id == fIteration.cdb_object_id,
                        order_by=fCard.display_order)

    def on_taskboard_start_sprint_pre_mask(self, ctx):
        if not self.CheckAccess("save", auth.persno):
            raise ue.Exception(self.__no_access_msg__)
        running = Iteration.KeywordQuery(board_object_id=self.board_object_id,
                                         status=Iteration.EXECUTION.status)
        if running:
            raise ue.Exception(self.__single_iteration_msg__)

    def on_taskboard_start_sprint_now(self, ctx):
        if not self.CheckAccess("save", auth.persno):
            raise ue.Exception(self.__no_access_msg__)
        with utils.NoBoardUpdate():
            sig.emit("starting_iteration")(self)
            self.Board.getAdapter().on_iteration_start_pre(self)
            self.ChangeState(Iteration.EXECUTION.status)
            self.Board.getAdapter().on_iteration_start_post(self)
            sig.emit("iteration_started")(self)
        self.Board.updateBoard()

    def on_taskboard_stop_sprint_pre_mask(self, ctx):
        if not self.CheckAccess("save", auth.persno):
            raise ue.Exception(self.__no_access_msg__)
        feedback = []
        complete = 0
        incomplete = 0
        for c in self.Cards:
            board_adapter = self.Board.getAdapter()
            card_adapter = self.Board.getCardAdapter(c)
            obj = c.TaskObject
            info = card_adapter.get_feedback(board_adapter, obj)
            if info:
                feedback.append(info)
            if board_adapter.is_done(card_adapter, c.context_object_id):
                complete += 1
            else:
                incomplete += 1
        a = util.get_label("iteration_result_1") % self.title
        b = util.get_label("iteration_result_2") % str(complete + incomplete)
        c = util.get_label("iteration_result_3") % str(complete)
        d = util.get_label("iteration_result_4") % str(incomplete)
        f = util.get_label("iteration_result_6")
        result = a + '\n\n' + b + '\n\n' + c + '\n' + d + '\n\n%s\n' + f
        # check for next iteration available
        if not self.Board.NextIteration:
            result = result + '\n' + util.get_label("iteration_result_no_iteration")
            ctx.set("next_iteration", 1)
        ctx.set("result", result % "\n".join(feedback))

    def on_taskboard_stop_sprint_now(self, ctx):
        if not self.CheckAccess("save", auth.persno):
            raise ue.Exception(self.__no_access_msg__)
        board_adapter = self.Board.getAdapter()
        board_adapter.on_iteration_stop_pre(self)
        if hasattr(ctx.dialog, "create_next_iteration"):
            # if the cards need to be moved to next iteration
            # check if the next iteration exists, otherwise create
            # next iteration. The assignment to the next iteration is done by
            # autoadjust_iteration method of BoardAdapter.
            if not self.Board.NextIteration:
                kwargs = {"board_object_id": self.Board.cdb_object_id}
                operation(kOperationNew, self, **kwargs)
        else:
            # if the not completed cards need to be moved to the backlog remove their
            # association to any iteration
            for card in self.Cards:
                card_adapter = self.Board.getCardAdapter(card)
                if not board_adapter.is_done(card_adapter, card.context_object_id):
                    card.Update(sprint_object_id="")

        self.ChangeState(Iteration.COMPLETED.status)
        board_adapter.on_iteration_stop_post(self)

    def is_completed(self):
        return self.status == Iteration.COMPLETED.status

    def check_dates(self, ctx=None):
        self._dates_valid(self.start_date, self.end_date)
        if self.Board:
            # why do we get datetime from the dialog in create pre?
            new_sd = utils.ensure_date(self.start_date)
            new_ed = utils.ensure_date(self.end_date)

            for sprint in self.Board.Iterations:
                if self.cdb_object_id != sprint.cdb_object_id:
                    sd = sprint.start_date
                    ed = sprint.end_date
                    if new_sd and new_ed and sd and ed and \
                        new_sd <= ed and sd <= new_ed:
                        raise ue.Exception("cs_taskboard_invalid_dates")

    def _dates_valid(self, start, end):
        if start and end and start > end:
            raise ue.Exception("cs_taskboard_invalid_dates")

    def overlap(self, iteration):
        if not iteration:
            return False
        if not (self.start_date and self.end_date):
            return False
        if not (iteration.start_date and iteration.end_date):
            return False
        if iteration.end_date < self.start_date:
            return False
        if self.end_date < iteration.start_date:
            return False
        return True

    def generateName(self):
        clabel = self.GetClassDef().getDesignation()
        count = ""
        if self.Board:
            count = len(self.Board.Iterations) + 1
        return "%s %s" % (clabel, count)

    def shift_cards(self, ctx=None):
        self.Cards.Update(sprint_object_id="")
        self.Board.close_display_order_gaps()

    def deleteIteration(self):
        with transactions.Transaction():
            self.shift_cards()
            self.Delete()

    event_map = {
        (("create", "copy", "modify"), "pre"): "check_dates",
        (("delete"), "pre"): "shift_cards",
    }


class Sprint(Iteration):
    __classname__ = "cs_taskboard_iter_sprint"
    __match__ = fIteration.cdb_classname >= __classname__
    __no_access_msg__ = "cs_taskboard_no_access_modify_sprint"
    __single_iteration_msg__ = "cs_taskboard_single_sprint"
    __automatic_assignment_active__ = False

    def on_taskboard_start_sprint_now(self, ctx):
        start = ctx.dialog["start_date"]
        end = ctx.dialog["end_date"]
        operation(kOperationModify, self, start_date=start, end_date=end)
        self.Super(Sprint).on_taskboard_start_sprint_now(ctx)


class Interval(Iteration):
    __classname__ = "cs_taskboard_iter_interval"
    __match__ = fIteration.cdb_classname >= __classname__
    __no_access_msg__ = "cs_taskboard_no_access_modify_interval"
    __single_iteration_msg__ = "cs_taskboard_single_interval"
    __automatic_assignment_active__ = True


class Card(Object):
    """
    Subject is mapped from subject of the context object to the card.
     This works only if the board adapter get updated.
    """
    __classname__ = "cs_taskboard_card"
    __maps_to__ = "cs_taskboard_card"

    Board = Reference_1(fBoard, fCard.board_object_id)
    Iteration = Reference_1(fIteration, fCard.sprint_object_id)
    Row = Reference_1(fRow, fCard.row_object_id)
    Column = Reference_1(fColumn, fCard.column_object_id)

    def _getTaskObject(self):
        return ByID(self.context_object_id)
    TaskObject = ReferenceMethods_1(Object, lambda self: self._getTaskObject())

    def _get_subject(self):
        board_adapter = self.Board.getAdapter()
        task = board_adapter.get_card_task(self)
        card_adapter = board_adapter.get_card_adapter(self)
        if not task or not card_adapter:
            return None
        return card_adapter.find_subject(task)
    Subject = ReferenceMethods_1(Object, lambda self: self._get_subject())

    def getResponsibleName(self):
        if self.Subject:
            return self.Subject.GetDescription()
        return u""

    def init_position(self, ctx=None):
        if not self.board_object_id:
            return

        result = sqlapi.RecordSet2(
            sql="""SELECT MAX(display_order) AS max_display_order
            FROM cs_taskboard_card WHERE board_object_id = '%s'""" % self.board_object_id)
        cards_pos = 0
        if result and result[0]["max_display_order"]:
            cards_pos = result[0]["max_display_order"]
        self.display_order = cards_pos + 10

        # FIXME: Initialization of row and column does not apply to aggregated boards.
        #        Code must be moved to the specialized classes
        # FIXME: Coming from add_cards via createCard,
        #        - the row and column are determined by the mapper and must never be set
        #          to initial values without being checked again.
        #        - these values can be used as arguments in the create statement,
        #          so no update call will be required later.
        # FIXME: Order, initial row and initial column are set by three single statements.
        #        What about performance?

        # Do NOT initialize row and column coming from add_cards via createCard
        # (check using existing operation context)
        if ctx:
            if self.Board.Rows:
                self.row_object_id = self.Board.Rows[0].cdb_object_id
            if self.Board.Columns:
                self.column_object_id = self.Board.Columns[0].cdb_object_id

    def close_display_order_gaps(self, ctx=None):
        self.Board.close_display_order_gaps()

    @classmethod
    def createCard(cls, **kwargs):
        # FIXME: Get the values for the order, initial row and initial column
        #        before the Create operation and use this value when creating the record.
        #        Avoid the later update calls in init_position.
        with transactions.Transaction():
            obj = cls.Create(**kwargs)
            obj.init_position()
            return obj

    def modifyCard(self, **kwargs):
        with transactions.Transaction():
            self.Update(**kwargs)

    event_map = {
        ("create", "pre"): ("init_position"),
        (("create", "delete"), "post"): ("close_display_order_gaps"),
    }


class BoardTemplatesCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        obj_hdl = None
        try:
            obj_hdl = self.getInvokingOpObjects()[0]
        except ue.Exception:
            pass
        if not obj_hdl:
            return []
        result = []
        for tmpl in Board.KeywordQuery(is_template=1,
                                       available=1,
                                       is_aggregation=0):
            try:
                adapter = tmpl.getAdapter()
            except ValueError as err:
                logging.error("Error while looking up board adapter: %s", err)
            else:
                if adapter.allow_board_context_object(obj_hdl):
                    result.append(I18nCatalogEntry(tmpl.cdb_object_id, tmpl.title))
        return result


class TeamBoardTemplatesCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        result = []
        for tmpl in Board.Query("board_type LIKE 'team%' AND is_template = 1 AND available = 1"):
            try:
                adapter = tmpl.getAdapter()
            except ValueError as err:
                logging.error("Error while looking up board adapter: %s", err)
            else:
                result.append(I18nCatalogEntry(tmpl.cdb_object_id, tmpl.title))
        return result


class TimeUnit(Object):
    __classname__ = "cs_taskboard_time_unit"
    __maps_to__ = "cs_taskboard_time_unit"


class TeamMember(Object):
    __classname__ = "cs_taskboard_team"
    __maps_to__ = "cs_taskboard_team"

    Board = Reference_1(fBoard, fTeamMember.taskboard_oid)

    def on_create_post(self, ctx):
        adapter = self.Board.getAdapter()
        adapter.clear_update_cache()


@sig.connect(Object, "changed_to_finial_status")
def reset_iteration_oid(self):
    for c in Card.KeywordQuery(context_object_id=self.cdb_object_id):
        if c.Iteration and c.Iteration.__automatic_assignment_active__:
            c.sprint_object_id = ''


@sig.connect(Object, "cs_taskboard_open_from_context", "now")
def on_open_board_from_context_now(self, ctx):
    board = Board.ByKeys(cdb_object_id=self.taskboard_oid)
    if not board:
        raise ue.Exception("cs_taskboard_not_found")
    if not board.CheckAccess("open taskboard", auth.persno):
        raise ue.Exception("cs_taskboard_no_access_rights")

    ui_url = get_webui_link(None, board)
    if ui_url:
        ctx.url(ui_url)


@sig.connect(Object, "cs_taskboard_create_board", "pre_mask")
def on_create_board_pre_mask(self, ctx):
    if Board.KeywordQuery(context_object_id=ctx.object["cdb_object_id"]):
        raise ue.Exception("cs_taskboard_context_limit")


@sig.connect(Object, "cs_taskboard_create_board", "now")
def on_create_board_now(self, ctx):
    changes = {"context_object_id": self.cdb_object_id}
    board = _create_board(ctx, check_access="create", **changes)
    ctx.set_followUpOperation('cs_taskboard_open', op_object=board)


def _create_board(ctx, check_access=None, **changes):
    template = Board.ByKeys(ctx.dialog["template_object_id"])
    if not template:
        return None
    for attr in ctx.dialog.get_attribute_names():
        changes[attr] = ctx.dialog[attr]
    changes.update(Board.MakeChangeControlAttributes())
    board = template.copyBoard(check_access=check_access,
                               is_template=0, **changes)
    # the Task Board opens immediately in the desktop client
    board.setupBoard()
    return board


@sig.connect(Object, "cs_taskboard_delete_board", "now")
def on_delete_board_now(self, ctx):
    board = Board.ByKeys(cdb_object_id=self.taskboard_oid)
    if not board:
        raise ue.Exception("cs_taskboard_not_found")
    operation(kOperationDelete, board)


@sig.connect(Object, "cs_taskboard_move_card", "now")
def on_cs_taskboard_move_card_now(self, ctx):
    attrs = ctx.dialog.get_attribute_names()
    key_attrs = self.KeyNames()
    values = dict([(k, ctx.dialog[k]) for k in attrs if k not in key_attrs])
    operation(kOperationModify,
              self,
              form_input(self.GetClassDef(), **values))


@sig.connect(Object, "cs_taskboard_move_card", "pre_mask")
def on_cs_taskboard_move_card_pre_mask(self, ctx):
    ctx.set_button_label(ctx.kButtonLabelCancel, "cs_taskboard_skip_button")


def add_months(mydate, months):
    month = mydate.month - 1 + months
    year = mydate.year + month // 12
    month = month % 12 + 1
    day = min(mydate.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def get_personal_board(person_object_id=None):
    """
    Returns the personal board of the requested user.
    The optional argument is mainly used for tests and should not be required for productive operation.
    :param person_object_id: uuid of an user  (Default: logged-in user)
    :type person_object_id: basestring
    :return: personal board of the requested user
    :rtype: instance of cs.taskboard.objects.Board
    """
    pers_object_id = auth.get_attribute("cdb_object_id") if person_object_id is None else person_object_id
    pboards = Board.KeywordQuery(
        context_object_id=pers_object_id,
        board_type="personal_board",
        is_template=0
    )
    pboard = None
    if len(pboards):
        pboard = pboards[0]
    else:
        tmpl = Board.KeywordQuery(
            context_object_id="",
            board_type="personal_board",
            is_template=1,
            available=1
        )
        if len(tmpl):
            pboard = tmpl[0].copyBoard(is_template=0,
                                       title=util.get_label(u'web.cs-taskboard.personal_board'),
                                       context_object_id=pers_object_id,
                                       **Board.MakeChangeControlAttributes())
    return pboard


def get_team_boards():
    persno = auth.persno
    # base condition: team board instances
    cond = "board_type LIKE 'team%' AND is_template != 1 AND ("
    # creator
    cond += "cdb_cpersno = '%s'" % persno
    # team membership
    cond += (
        " OR cdb_object_id in (select t.taskboard_oid from %s t where"
        " t.subject_id='%s' and t.subject_type='Person')" % (
            TeamMember.GetTableName(), persno)
    )
    cond += ")"
    return Board.Query(cond)


def do_project_boards_exist():
    result = sig.emit(Object, "do_project_boards_exist")()
    return bool(len([x for x in result if bool(x)]))


def get_project_boards():
    project_conds = sig.emit(Object, "get_project_board_condition")()
    if not project_conds:
        return []
    # base condition: project board instances
    cond = "board_type NOT LIKE 'personal%' AND is_template != 1 AND "
    cond += "board_type NOT LIKE 'team%' AND ("

    # get additional constraints
    cond += " OR ".join(project_conds)
    cond += ")"
    return Board.Query(cond)


@lru_cache.lru_cache(maxsize=10)
def get_board_adapter(board_object_id, board_api):
    adapter = tools.load_callable(board_api)(board_object_id)
    # create task cache
    adapter.get_available_tasks(refresh=True)
    return adapter


def find_subject(obj):
    # FIXME: BySubjectReferrer can be changed...
    def find(cls):
        for spec in cls.__specializations__:
            if hasattr(spec, "__subject_type__"):
                if spec.__subject_type__ == obj.subject_type:
                    return spec.BySubjectReferrer(obj)
            else:
                subj = find(spec)
                if subj:
                    return subj
    return find(Subject)
