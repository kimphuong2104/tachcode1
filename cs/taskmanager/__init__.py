#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=W0212

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from cdb import ddl, sig, sqlapi, ue
from cdb.objects.rules import Predicate, Term
from cdb.platform.acs import OrgContextActivation
from cs.taskmanager.conf import TaskClass

HEADER_VIEW = "cs_tasks_headers_v"


def get_collation():
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        return "COLLATE {}".format(CollationDefault.get_default_collation())
    return ""


def generate_cs_tasks_headers_v():
    """view containing current tasks for each user"""
    try:
        # dirty hack - object rule for pcs tasks contains Reference_N from
        # another package, so we have to import it manually
        # pylint: disable=W0612,W0611
        from cs.pcs.resources.pcs_extensions import Task  # noqa: F401
    except ImportError:
        pass
    stmt = TaskHeaders.getCombinedViewStatement()
    if stmt == "":
        # no task classes yet; return dummy statement so generation won't fail
        stmt = """SELECT
                name {collation} AS task_classname,
                classname {collation} AS classname,
                '' {collation} AS persno,
                '' {collation} AS cdb_object_id,
                '' {collation} AS subject_id,
                '' {collation} AS subject_type,
                NULL AS deadline
            FROM cs_tasks_class
        """.format(
            collation=get_collation()
        )
    return stmt


class TaskHeaders(object):
    SQL_PATTERN = """
        SELECT * FROM (
            SELECT * FROM {view}
            WHERE persno IN ('{user_ids}')
        ) task_headers
        WHERE {condition}
        ORDER BY task_classname"""

    @classmethod
    def getCombinedViewStatement(cls):
        """union statements of all class instances"""
        task_classes = "\nUNION ALL ".join(
            cls._getViewStatement(index, task_class)
            for index, task_class in enumerate(TaskClass.Query())
        )
        return task_classes

    @classmethod
    def _getViewStatement(cls, index, task_class):
        """custom version of cdb.objects.Rule.stmt"""
        kwargs = {"persno": "caddok"}

        if not task_class.Rule:
            raise ue.Exception(
                "cs_tasks_invalid_rule", task_class.rule_id, task_class.name
            )

        objects_cls = task_class.ObjectsClass
        root = task_class.Rule._GetNode(objects_cls, **kwargs)
        angestellter = "angestellter{}".format(index)

        base_table = "{} {}".format(root.cls.GetTableName(), root.alias)
        join = root.build_join().split(base_table, 1)[1]

        deadline = (
            "{}.{}".format(root.alias, task_class.deadline)
            if task_class.deadline
            else "NULL"
        )

        tbl = ddl.Table(root.cls.GetTableName())

        def get_subject_attr(attr):
            return (
                "{}.{}".format(root.alias, attr)
                if tbl.hasColumn(attr)
                else "'' {collation} AS {attr}".format(
                    collation=get_collation(), attr=attr
                )
            )

        stmt = """
            SELECT
                '{task_class.name}' {collation} AS task_classname,
                '{task_class.classname}' {collation} AS classname,
                {angestellter}.personalnummer {collation} AS persno,
                {alias}.cdb_object_id {collation} AS cdb_object_id,
                {subject_id},
                {subject_type},
                {deadline} AS deadline
            FROM
                {base_table}
            INNER JOIN angestellter {angestellter} ON 1=1
                {join}
        """.format(
            task_class=task_class,
            deadline=deadline,
            subject_id=get_subject_attr("subject_id"),
            subject_type=get_subject_attr("subject_type"),
            alias=root.alias,
            base_table=base_table,
            join=join,
            angestellter=angestellter,
            collation=get_collation(),
        )

        stmt += (
            " WHERE {where} AND "
            "{angestellter}.cdb_classname='angestellter'".format(
                where=str(task_class.Rule.expr(objects_cls, **kwargs)),
                angestellter=angestellter,
            )
        )
        return stmt.replace("'caddok'", "{}.personalnummer".format(angestellter))

    @classmethod
    def compileToView(cls, fail=False):
        """recreates tasks view from current object rules"""
        from cdb.platform.mom.relations import DDUserDefinedView

        view = DDUserDefinedView.ByKeys(HEADER_VIEW)

        try:
            view.rebuild()
        except RuntimeError:
            logging.exception("compileToView failed")
            if fail:
                raise
            return False

        logging.info("compileToView succeeded")
        return True

    @classmethod
    def GetHeaders(cls, users, condition):
        """
        :param users: user IDs that are a superset of condition
        :type users: list of str

        :param condition: SQL condition without "WHERE"
        :type condition: str

        :returns: Task classnames indexed by task UUID
            of tasks matching `condition`
        :rtype: dict
        """
        stmt = cls.SQL_PATTERN.format(
            view=HEADER_VIEW,
            user_ids="', '".join(users),
            condition=condition,
        )
        headers = sqlapi.RecordSet2(sql=stmt)
        result = {header.cdb_object_id: header.task_classname for header in headers}
        return result


@sig.connect(Predicate, "copy", "post")
@sig.connect(Predicate, "delete", "post")
@sig.connect(Term, "create", "post")
@sig.connect(Term, "copy", "post")
@sig.connect(Term, "delete", "post")
@sig.connect(Term, "modify", "post")
@sig.connect(OrgContextActivation, "create", "post")
@sig.connect(OrgContextActivation, "copy", "post")
@sig.connect(OrgContextActivation, "delete", "post")
@sig.connect(OrgContextActivation, "modify", "post")
def compileCsTasksView(self, ctx):
    """
    Recompiles cs_tasks_headers_v after object rule changes that impact the
    rule's results (only if ``ctx.error`` is falsy).

    .. note ::
        Creating a predicate does not impact results (zero terms translate to
        "no object matches" instead of "all objects match"). This is an
        undocumented feature of object rules.

    .. warning ::
        Because changing object rules is something that is not expected to
        happen frequently in production, the view is always recompiled,
        regardless of the changed element's relevance to cs.taskmanager.
        Checking relevance is also not trivial as rules can be arbitrarily
        nested.

    Recompilation is also done after changing
    organizational context "activations" (e.g. assigned tables).

    :raises Exception: if recompile fails.
    """
    if ctx.error:
        return

    TaskHeaders.compileToView(fail=True)
