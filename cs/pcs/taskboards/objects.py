#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import defaultdict

from cdb import auth, sig, sqlapi
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_Methods, Reference_N, Rule
from cs.taskboard.objects import Board

from cs.pcs.projects import Project, TeamMember
from cs.pcs.projects.tasks import Task

fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")
fBoard = Forward("cs.taskboard.objects.Board")

PROJECT_BOARD_RULE = "cdbpcs: Valid Projects for Taskboards"
PERS_TEAM_BOARD_RULE = "cdbpcs: Valid Projects for Persnoal And Team Boards"


@sig.connect(Board, "copyBoard")
@sig.connect(Board, "create", "post")
@sig.connect(Board, "copy", "post")
def link_taskboard(self, ctx=None):
    if self.ContextObject and isinstance(self.ContextObject, (Project, Task)):
        self.ContextObject.taskboard_oid = self.cdb_object_id


@sig.connect(Board, "delete", "pre")
def unlink_taskboard(self, ctx=None):
    if self.ContextObject and isinstance(self.ContextObject, (Project, Task)):
        self.ContextObject.taskboard_oid = ""


@sig.connect("get_valid_board_object_ids")
def get_valid_board_object_ids_on_projects():
    return get_valid_board_object_ids(Project, PERS_TEAM_BOARD_RULE)


@sig.connect("get_valid_board_object_ids")
def signal_get_valid_board_object_ids_on_tasks():
    return get_valid_board_object_ids(Task, PERS_TEAM_BOARD_RULE)


def get_valid_board_object_ids(cls, rule):
    chr1 = "''"
    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        chr1 = "chr(1)"
    rule = Rule.ByKeys(name=rule)
    root = rule._GetNode(cls)
    add_expr = (
        "{alias}.taskboard_oid != {chr1} AND " "{alias}.taskboard_oid IS NOT NULL"
    ).format(alias=root.alias, chr1=chr1)
    return rule.stmt(cls, add_expr=add_expr).replace("*", "taskboard_oid")


def _get_board_condition(cls):
    chr1 = "''"
    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        chr1 = "chr(1)"
    return (
        "SELECT a.taskboard_oid"
        f" FROM {cls.GetTableName()} a, {TeamMember.GetTableName()} t"
        " WHERE a.cdb_project_id = t.cdb_project_id"
        " AND a.taskboard_oid IS NOT NULL"
        f" AND a.taskboard_oid != {chr1}"
        f" AND t.cdb_person_id = '{auth.persno}'"
    )


@sig.connect(Object, "get_project_board_condition")
def get_project_board_condition():
    p_board_ids = f"cdb_object_id IN ({_get_board_condition(Project)})"
    p_rule_ids = (
        f"cdb_object_id IN ({get_valid_board_object_ids(Project, PROJECT_BOARD_RULE)})"
    )
    p_stmt = f"({p_board_ids} AND {p_rule_ids})"

    t_board_ids = f"cdb_object_id IN ({_get_board_condition(Task)})"
    t_rule_ids = (
        f"cdb_object_id IN ({get_valid_board_object_ids(Task, PROJECT_BOARD_RULE)})"
    )
    t_stmt = f"({t_board_ids} AND {t_rule_ids})".format(t_board_ids, t_rule_ids)

    included_boards = " OR ".join([p_stmt, t_stmt])
    return f"({included_boards})"


@sig.connect(Object, "do_project_boards_exist")
def do_project_boards_exist():
    return True


@sig.connect(Task, "copy_task_hook")
def _reset_taskboard_oid(self, project, task):
    task.taskboard_oid = ""


def getBoard(obj):
    if obj.Taskboards:
        return obj.Taskboards[0]
    return None


def refresh_taskboards(obj):
    board = get_project_board(obj)
    if board:
        board.updateBoard()


def get_project_board(obj):
    parent = obj.getParent()
    if not parent:
        return None
    if parent.taskboard_oid:
        return parent.Taskboard
    return get_project_board(parent)


@classbody
class Project:

    Taskboard = Reference_Methods(
        fBoard, lambda self: getBoard(self)  # pylint: disable=unnecessary-lambda
    )
    Taskboards = Reference_N(fBoard, fBoard.context_object_id == fProject.cdb_object_id)

    def getTaskSets(self, task_id=""):
        tasks = defaultdict(None)
        tasks_py_parent = defaultdict(set)
        sqlstr = (
            "SELECT * FROM cdbpcs_task"
            f" WHERE cdb_project_id = '{self.cdb_project_id}'"
            " AND ce_baseline_id = ''"
        )
        for t in sqlapi.RecordSet2(table="cdbpcs_task", sql=sqlstr):
            tasks[t["task_id"]] = t
            tasks_py_parent[t["parent_task"]].add(t["task_id"])
        return self._getSubTaskSet(task_id, tasks, tasks_py_parent)

    def _getSubTaskSet(self, task_id, tasks, tasks_py_parent):
        result = set([])
        tasks_with_board = set([])
        task_group = set([])
        subtasks = tasks_py_parent[task_id]
        for t in subtasks:
            task = tasks[t]
            result.add(task)
            if task.is_group:
                task_group.add(task)
            if task.taskboard_oid:
                tasks_with_board.add(task)
            else:
                r1, r2, r3 = self._getSubTaskSet(t, tasks, tasks_py_parent)
                result |= r1
                tasks_with_board |= r2
                task_group |= r3
        return result, tasks_with_board, task_group

    @sig.connect(Project, "copy", "post")
    def _reset_taskboard_oid(self, ctx):
        persistent_obj = self.getPersistentObject()
        persistent_obj.taskboard_oid = ""


@classbody
class Task:

    Taskboard = Reference_Methods(
        fBoard, lambda self: getBoard(self)  # pylint: disable=unnecessary-lambda
    )
    Taskboards = Reference_N(fBoard, fBoard.context_object_id == fTask.cdb_object_id)

    @sig.connect(Task, "copy", "post")
    def _reset_taskboard_oid(self, ctx):
        persistent_obj = self.getPersistentObject()
        persistent_obj.taskboard_oid = ""
