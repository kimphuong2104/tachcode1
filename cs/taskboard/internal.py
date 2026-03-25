#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Internal morepath app for the dashboard. Provides the API for the dashboard page.
"""



import itertools
__revision__ = "$Id: internal.py 217038 2020-09-21 09:25:15Z heg $"

from webob.exc import HTTPForbidden
from webob.exc import HTTPBadRequest
from webob.exc import HTTPInternalServerError
from cdb import auth
from cdb import ue
from cdb import sig
from cdb import ElementsError
from cdb import util
from cdb.objects import ByID
from cdb.platform.mom.fields import DDTextField
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal
from cs.platform.web.rest.app import get_collection_app
from cs.platform.web.rest.generic.model import Workflow
from cs.taskboard import utils
from cs.taskboard.objects import Board
from cs.taskboard.objects import Card
from cs.taskboard.objects import get_personal_board
from cs.taskboard.objects import get_team_boards
from cs.taskboard.objects import get_project_boards
from cs.taskboard.objects import do_project_boards_exist
from cs.platform.web.uisupport import get_uisupport
from cs.platform.web.uisupport import get_webui_link
from cs.platform.web.rest import support
from cs.web.components.ui_support.operations import OperationInfo
from cs.web.components.ui_support.forms import FormInfoClassDef
from cs.web.components.ui_support.display_contexts import DisplayConfiguration


WEB_MY_TASKBOARD_SIGNAL = sig.signal()


class InternalTaskboardApp(JsonAPI):
    PATH = "cs.taskboard"

    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(cls.PATH)


@Internal.mount(app=InternalTaskboardApp, path=InternalTaskboardApp.PATH)
def _mount_app():
    return InternalTaskboardApp()


def _readable(obj):
    if obj and obj.CheckAccess("read"):
        return obj
    return None


@InternalTaskboardApp.path(model=Board, path="board/{cdb_object_id}")
def _board_path(cdb_object_id):
    return _readable(Board.ByKeys(cdb_object_id))


@InternalTaskboardApp.path(model=Card, path="card/{cdb_object_id}")
def _card_path(cdb_object_id):
    return _readable(Card.ByKeys(cdb_object_id))


def group_view(board, group, request):
    if not group:
        return None
    ctx = group.get("context_object")
    result = dict(title=group.get("title"),
                  card_ids=group.get("card_ids"),
                  context_object=request.view(
                      ctx, app=get_collection_app(request)),
                  display_attributes=get_group_header(board, ctx, request))
    return result


def board_base_view(board, request):
    return {
        "@id": request.link(board),
        "title": board.title,
        "system:description": board.GetDescription(),
        "cdb_object_id": board.cdb_object_id,
        "context_object_id": board.context_object_id,
        "board_type": board.board_type,
        "is_template": board.is_template,
        "system:classname": board._getClassname(),
        "system:navigation_id": board.cdb_object_id,
        "detail_outlets": board.get_detail_outlets(),
    }


def opdata_view(opdata, request):
    if opdata:
        us_app = get_uisupport(request)
        # Use classname and label from object class if specified,
        # otherwise they should be defined in opdata directly
        objcls = opdata.get("class", None)
        if objcls:
            classname = objcls._getClassname()
            label = objcls._getClassDef().getDesignation()
            icon = objcls.GetClassIcon()
        else:
            classname = opdata.get("classname")
            label = opdata.get("label")
            icon = opdata.get("icon")
        opinfo = OperationInfo(classname, opdata.get("name"))
        if opinfo:
            if not icon:
                icon_urls = opinfo.get_icon_urls()
                if len(icon_urls):
                    icon = "/%s" % icon_urls[0]
            ctx = opdata.get("context_rest_key", None)
            return dict(
                opinfo=request.view(opinfo, app=us_app),
                label=label if label else opinfo.get_label(),
                icon=icon,
                arguments=opdata.get("arguments"),
                context={"system:navigation_id": ctx} if ctx else None
            )
    return None


def check_update_board_access(board):
    if not board.access_granted():
        e = ue.Exception("cs_taskboard_no_access_rights")
        raise HTTPForbidden(str(e))

def filter_empty_operations(operations):
    return list(filter(bool, operations))

def _get_board_view(model, request, group_by=None):
    adapter = model.getAdapter()
    adapter.update_board()
    board = board_base_view(model, request)
    board.update({
        "group_types": adapter.get_group_attributes(),
        "filters": adapter.get_filter_names(),
        "workingViewTitle": adapter.get_working_view_title()
    })
    # which fields should be provided in order to generate board header
    # Only UUID fields to referenced objects are needed.
    board.update({
        "headerDataFields": ["context_object_id"]
    })
    rows = [{
                "cdb_object_id": obj.cdb_object_id,
                "title": obj.title,
                "context_object_id": obj.context_object_id,
                "display_order": obj.display_order
            } for obj in model.Rows]

    cols = [{
                "cdb_object_id": obj.cdb_object_id,
                "title": obj.title,
                "column_name": obj.column_name,
                "display_order": obj.display_order
            } for obj in model.Columns]

    cards = [_get_card(card, request) for card in model.VisibleCards]

    create_ops = filter_empty_operations([opdata_view(opdata, request)
                  for opdata in adapter.get_create_operations() if opdata])
    extra_ops = filter_empty_operations([opdata_view(opdata, request)
                  for opdata in adapter.get_extra_operations() if opdata])
    enableGroupMoving = adapter.enable_moving_cards_in_groups()
    board.update(
        enableGroupMoving=enableGroupMoving,
        rows=rows,
        columns=cols,
        cards=cards,
        createOperations=create_ops,
        extraOperations=extra_ops,
        adjustNewCardURL=request.link(model, name="+adjust_new_card"),
        moveCardsURL=request.link(model, name="+move_cards"))
    groups = None
    group_attr = request.params.get("group_by", group_by)
    if group_attr:
        groups = adapter.group_by(group_attr)
        if groups:
            groups = [
                group_view(model, group, request)
                for group in groups.values()
            ]
    board.update(groups=groups)
    # Iterations
    collection_app = get_collection_app(request)
    use_iter_class = adapter.get_iteration_class()
    has_backlog = adapter.has_backlog()
    has_evaluation = adapter.has_evaluation()
    has_preview = adapter.has_preview()
    hasPreviewAddButton = adapter.has_preview_add_button()
    enableMoving = adapter.enable_moving_cards_in_preview()
    sprints = dict(
        hasBacklog=has_backlog,
        hasEvaluation=has_evaluation,
        hasPreview=has_preview,
        hasPreviewAddButton=hasPreviewAddButton,
        enableMoving=enableMoving,
        sprints=[],
        active_sprint_id=None,
        next_sprint_id=None,
        sprint_status={},
        sprint_context_type=use_iter_class._getClassname() if use_iter_class else "")
    if has_backlog or has_evaluation or has_preview:
        sprints.update(
            sprints=[
                request.view(sprint, app=collection_app)
                for sprint in model.OpenIterations
            ],
            completed_sprints=[
                request.view(sprint, app=collection_app)
                for sprint in model.CompletedIterations
            ],
            sprint_status=dict([
                (sprint.cdb_object_id, Workflow(sprint).current_status)
                for sprint in model.Iterations
            ])
        )
        asprint = adapter.get_active_iteration()
        if asprint:
            sprints.update(active_sprint_id=asprint.cdb_object_id)
        else:
            nsprint = model.NextIteration
            if nsprint:
                sprints.update(next_sprint_id=nsprint.cdb_object_id)
    board.update(sprints)
    board.update(hasTeam=adapter.has_team(), teamAssigned=False)
    if adapter.has_team():
        board.update(teamAssigned=len(model.TeamMembers) > 0)
    display_configs = {}
    for conf in adapter.get_display_configs():
        display_configs[conf] = _display_config(conf)
    board.update(display_configs=display_configs)
    return board


def _display_config(name):
    from cdb.platform import gui
    return gui.get_dialog(name)


@InternalTaskboardApp.json(model=Board)
def _get_board(model, request, group_by=None):
    check_update_board_access(model)
    return _get_board_view(model, request, group_by)


def _get_task_view(task, request):
    oh = task.ToObjectHandle()
    cdef = oh.getClassDef()
    key_dict = {}
    for k in cdef.getKeyNames():
        key_dict[k] = task[k]

    key_dict.update({
        "@id": support.get_restlink(oh, request),
        "system:classname": cdef.getClassname(),
        "system:navigation_id": support.rest_key(oh)
    })
    return key_dict


RESPONSIBLE_CACHE = {}


def _get_card_responsible(card, request):
    responsible = card.Subject
    if responsible is None:
        return {}
    resp_id = responsible.ID()
    if resp_id not in RESPONSIBLE_CACHE:
        result = {}
        thumbnail = None
        thumbnail_file = None
        if hasattr(responsible, "GetThumbnailFile"):
            thumbnail_file = responsible.GetThumbnailFile()
        if thumbnail_file:
            thumbnail = request.link(thumbnail_file, app=get_collection_app(request))
        name = responsible.GetDescription()
        result.update(name=name, thumbnail=thumbnail)
        RESPONSIBLE_CACHE[resp_id] = result
    return RESPONSIBLE_CACHE[resp_id]


def _get_display_attributes(request, board_adapter, card_adapter, card, task):
    dattrs = card_adapter.get_display_attributes(board_adapter, card, task)
    result = {"responsible": _get_card_responsible(card, request)}
    if dattrs:
        result.update(dattrs.get_values())
    return result


@InternalTaskboardApp.json(model=Card)
def _get_card(model, request):
    card = model
    board_adapter = card.Board.getAdapter()
    card_adapter = board_adapter.get_card_adapter(card)
    if not card_adapter:
        return None
    task = board_adapter.get_task(card.context_object_id)
    due_date = card_adapter.get_due_date(card.context_object_id)
    result = board_adapter.get_result(card.context_object_id)
    up_to_date = board_adapter.is_up_to_date(card.context_object_id)
    if not result or not up_to_date:
        result.update(**{
            "context_object": _get_task_view(task, request),
            "context_object_icon": None,
            "displayAttributes": _get_display_attributes(
                request, board_adapter, card_adapter, card, task),
            "displayConfigs": card_adapter.get_display_configs_for_task(
                board_adapter, card, task),
            "cardColor": card_adapter.get_card_color(board_adapter, card, task),
            "filters": card_adapter.get_filters(board_adapter, card, task),
            "due_date": due_date.isoformat() if due_date else ""
        })
        board_adapter.add_result(card.context_object_id, result)
        # The cache status only needs to be set to valid if the cache has been updated.
        board_adapter.set_update_status(card.context_object_id, True)
    result.update(**{
        "@id": request.link(card),
        "cdb_object_id": card.cdb_object_id,
        "context_object_id": card.context_object_id,
        "row_object_id": card.row_object_id,
        "column_object_id": card.column_object_id,
        "sprint_object_id": card.sprint_object_id,
        "display_order": card.display_order,
        "draggable": board_adapter.can_change_card_position(card),
    })
    board_adapter.set_last_update()
    return result


@InternalTaskboardApp.json(model=Card, request_method="POST")
def _change_card(model, request):
    if not model.TaskObject.CheckAccess("save", auth.persno):
        e = ue.Exception("cs_taskboard_no_access_modify_card")
        raise HTTPForbidden(str(e))
    row_object_id = request.json.get("row_object_id")
    column_object_id = request.json.get("column_object_id")
    next_card_object_id = request.json.get("next_card_object_id")
    group_by = request.json.get("group_by")
    sprint_object_id = model.sprint_object_id
    if "sprint_object_id" in request.json:
        sprint_object_id = request.json.get("sprint_object_id")
    # TODO: should initialize the drop action from Board or Card?
    followup_op = None
    board = model.Board
    board_adapter = board.getAdapter()
    with utils.NoBoardUpdate():
        try:
            if row_object_id or column_object_id:
                opdata = board_adapter.change_card_position_to(
                    model, row_object_id, column_object_id, group_by)
                if opdata:
                    followup_op = opdata_view(
                        dict(classname=model.TaskObject.GetClassname(), **opdata),
                        request)
            elif sprint_object_id != model.sprint_object_id:
                board_adapter.change_card_iteration(model, sprint_object_id)
        except ElementsError as e:
            raise HTTPForbidden(str(e))
        except RuntimeError as x:
            raise HTTPBadRequest(detail=str(x))
        except ue.Exception as x:
            raise HTTPBadRequest(detail=str(x))
    Board.adjust_display_order(model.board_object_id,
                               [model], next_card_object_id)
    Board.refresh_boards_by_context_object_ids(model.context_object_id, board)
    return dict(
        runOp=followup_op,
        board=_get_board(model.Board, request, request.json.get("group_by"))
    )


@InternalTaskboardApp.json(model=Board,
                           name="header",
                           request_method="POST")
def get_form_info(model, request):
    # As a "redirect" to the standard form API
    adapter = model.getAdapter()
    dlg = adapter.get_header_dialog_name()
    if dlg:
        fi = FormInfoClassDef(dlg, model.GetClassDef(), {"refresh": "1"})
        fi.use_object_links(get_webui_link(request, model))
        return request.view(
            fi, app=get_uisupport(request), request_method="POST")
    return None


@InternalTaskboardApp.json(model=Board,
                           name="adjust_new_card",
                           request_method="POST")
def adjust_new_card_on_board(model, request):
    check_update_board_access(model)
    adapter = model.getAdapter()
    task_object_id = request.json.get("task_object_id")
    if task_object_id:
        adapter.adjust_new_card(task_object_id)
    model.close_display_order_gaps()
    return _get_board_view(model, request, request.json.get("group_by"))


@InternalTaskboardApp.json(model=Board,
                           name="move_cards",
                           request_method="POST")
def _change_cards(board, request):
    card_object_ids = request.json.get("cards")
    row_object_id = request.json.get("row_object_id")
    column_object_id = request.json.get("column_object_id")
    next_card_object_id = request.json.get("next_card_object_id")
    sprint_object_id = request.json.get("sprint_object_id")
    cards = []
    context_object_ids = []
    # Only process further if access allowed on all selected cards
    for card_id in card_object_ids:
        card = Card.ByKeys(card_id)
        context_object_ids.append(card.context_object_id)
        if not card.TaskObject.CheckAccess("save", auth.persno):
            e = ue.Exception("cs_taskboard_no_access_modify_card")
            raise HTTPForbidden(str(e))
        cards.append(card)

    def take_display_order(card):
        return card.display_order
    cards.sort(key=take_display_order)

    board_adapter = board.getAdapter()
    # TODO: maybe later a common followup operation for multi selected cards
    followup_op = None
    sig.emit("changing_cards")(board, context_object_ids)
    with utils.NoBoardUpdate():
        for card in cards:
            try:
                if row_object_id or column_object_id:
                    board_adapter.change_card_position_to(
                        card, row_object_id, column_object_id)
                elif sprint_object_id != card.sprint_object_id:
                    board_adapter.change_card_iteration(card, sprint_object_id)
            except ElementsError as e:
                raise HTTPForbidden(str(e))
            except RuntimeError as x:
                raise HTTPBadRequest(detail=str(x))
            except ue.Exception as x:
                raise HTTPBadRequest(detail=str(x))
    sig.emit("cards_changed")(board, context_object_ids)
    if cards:
        Board.adjust_display_order(cards[0].board_object_id,
                                   cards, next_card_object_id)
        Board.refresh_boards_by_context_object_ids(context_object_ids, board)
    return dict(
        runOp=followup_op,
        board=_get_board(board, request, request.json.get("group_by"))
    )


class MyTaskBoards(object):
    """
    Collections of boards for `My Boards` application
    """
    def get_personal_boards(self):
        pboards = get_personal_board()
        if pboards:
            return [get_personal_board()]
        return []

    def get_team_boards(self):
        return get_team_boards()

    def get_project_boards(self):
        return get_project_boards()

    def do_project_boards_exist(self):
        return do_project_boards_exist()


@InternalTaskboardApp.path(model=MyTaskBoards, path="my-boards")
def _my_boards_path():
    return MyTaskBoards()


def _get_my_board_view(board, request):
    result = board_base_view(board, request)
    result["system:ui_link"] = get_webui_link(request, board)
    result["system:icon_link"] = board.GetObjectIcon()
    return result


@InternalTaskboardApp.json(model=MyTaskBoards)
def _my_boards_view(model, request):
    result = sig.emit(WEB_MY_TASKBOARD_SIGNAL)(model, request)
    if len(result) != 1:
        return []
    return result[0]


@sig.connect(WEB_MY_TASKBOARD_SIGNAL)
def default_taskboard_blocks(model, request):
    labels = util.Labels()
    result = []
    # add personal task boards
    pers_boards = model.get_personal_boards()
    if len(pers_boards) > 0:
        block = {
            "title": labels["web.cs-taskboard.personal_board"],
            "boards": [_get_my_board_view(b, request) for b in pers_boards]
        }
        result.append(block)
    # add team task boards
    team_boards = model.get_team_boards()
    block = {
        "title": labels["web.cs-taskboard.team_boards"],
        "boards": [_get_my_board_view(b, request) for b in team_boards],
        "operations": ["cs_taskboard_create_team_board"]
    }
    if len(team_boards) == 0:
        block.update(
            emptyTitle=labels["web.cs-taskboard.no_team_boards"],
            emptyMsg=labels["web.cs-taskboard.create_team_boards_msg"]
        )
    result.append(block)
    # add project task boards
    if do_project_boards_exist():
        prj_boards = model.get_project_boards()
        block = {
            "title": labels["web.cs-taskboard.project_boards"],
            "boards": [_get_my_board_view(b, request) for b in prj_boards],
        }
        if len(prj_boards) == 0:
            block.update(
                emptyTitle=labels["web.cs-taskboard.no_project_boards"],
                emptyMsg=labels["web.cs-taskboard.create_project_boards_msg"]
            )
        result.append(block)
    return result


class GroupInfo(FormInfoClassDef):
    """
    Class to provide dialogs customized with the
    |elements| dialog configuration to the REST API in
    the context of a specific class
    """
    def __init__(self, dialog_name, clsdef,
                 extra_parameters=None, board=None, obj=None):
        super(GroupInfo, self).__init__(dialog_name, clsdef, extra_parameters)
        self.taskboard = board
        self.group_context_object = obj

    def get_form_def_and_values(self, request):
        values = {}
        for attr_def in self.clsdef.getAttributeDefs():
            text_fields = self.clsdef.getTextFieldNames()
            if attr_def.getName() in text_fields:
                values[attr_def.getIdentifier()] = \
                    self.group_context_object.GetText(attr_def.getName())
            else:
                values[attr_def.getIdentifier()] = \
                    self.group_context_object[attr_def.getName()]
        values.update(
            cs_taskboard_board_object_id=self.taskboard.cdb_object_id)
        try:
            form_info = self.clsdef.get_dialog(self.dialog_name,
                                               values)
        except:
            # Older versions do not support the extra parameter vals
            form_info = self.clsdef.get_dialog(self.dialog_name)
        return self.get_forminfo_dict(request,
                                      form_info,
                                      values)


def get_group_header(board, model, request):
    if model is None:
        return None
    dialog_name = DisplayConfiguration.get_mask_name(
        model.GetClassname(), "taskboard_group_header")
    if not dialog_name:
        return None
    fi = GroupInfo(dialog_name, model.GetClassDef(), board=board, obj=model)
    fi.use_object_links(get_webui_link(request, model))
    return request.view(
        fi, app=get_uisupport(request), request_method="POST")


class TaskLongTextModel(object):
    """
    Model for task long text field.
    """
    def __init__(self, cdb_object_id, text_name):
        self.text_name = text_name
        self.task = ByID(cdb_object_id)
        self.classname = self.task.GetClassname()

    def get_text(self):
        return self.task.GetText(self.text_name)

    def get_label(self):
        # subclasses cannot access long text fields
        # only the exact class they're defined for do
        classdef = self.task.GetClassDef()
        for base_class in itertools.chain([classdef], classdef.getBaseClasses()):
            field = DDTextField.ByKeys(
                base_class.getClassname(), self.text_name)
            if field:
                return field.getLabel()

        # technical name as fallback
        return self.text_name


@InternalTaskboardApp.path(model=TaskLongTextModel,
    path="task_long_text/{cdb_object_id}/{text_name}")
def _task_path(cdb_object_id, text_name):
    return TaskLongTextModel(cdb_object_id, text_name)


@InternalTaskboardApp.json(model=TaskLongTextModel)
def _get_attribute(model, request):
    try:
        text = model.get_text()
        field_label = model.get_label()
        return {
            model.text_name: text,
            "field_label": field_label
        }
    except Exception as ex:
        raise HTTPInternalServerError(ex)
