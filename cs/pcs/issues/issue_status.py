#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

from cdb import ue
from cdb.classbody import classbody
from cdb.objects import Object, State, Transition

# Issue is imported so it can be extended via classbody
from cs.pcs.issues import Issue  # pylint: disable=unused-import


class IssueStatusProtocol(Object):
    __maps_to__ = "cdbpcs_iss_prot"
    __classname__ = "cdbpcs_iss_prot"


@classbody
class Issue:
    @classmethod
    def endStatus(cls, full_cls=True):
        """
        returns set of "final" status classes (full_cls True) or integer values
        (full_cls False) and cache them for subsequent access
        """
        if not hasattr(cls, "__end_status_cls__"):
            cls.__end_status_cls__ = set([cls.DISCARDED, cls.COMPLETED])
            cls.__end_status_int__ = {x.status for x in cls.__end_status_cls__}
        if full_cls:
            return cls.__end_status_cls__
        return cls.__end_status_int__

    class NEW(State):
        status = 0

    class EVALUATION(State):
        status = 30

    class EXECUTION(State):
        status = 50

        def Constraints(transition, self):
            from cs.pcs.projects.tasks import Task

            return [
                (
                    "MatchStateList",
                    [
                        [self.Task],
                        [Task.READY, Task.NEW, Task.EXECUTION],
                        "pcstask_wf_rej_1",
                    ],
                )
            ]

    class DEFERRED(State):
        status = 60

    class WAITINGFOR(State):
        status = 70

        def pre(state, self, ctx):
            # 'reason' and 'waiting for' are mandatory in this case only
            if (
                ctx.dialog["waiting_reason"] == ""
                or ctx.dialog["waiting_for_name"] == ""
            ):
                # special error message until E049045 is fixed
                from cs.pcs.issues.tasks_plugin import PROCEED_FLAG

                if ctx.active_integration == PROCEED_FLAG:
                    raise ue.Exception("pcs_err_iss_proceed")

                from cdb.platform import gui

                mask = gui.Mask.ByName("cdbpcs_issue_state")[0]
                waiting_for_name = mask.AttributesByName["waiting_for_name"][0].Label[
                    ""
                ]
                waiting_reason = mask.AttributesByName["waiting_reason"][0].Label[""]
                attrs = f"'{waiting_for_name}', '{waiting_reason}'"
                raise ue.Exception(
                    "pcs_err_iss_state",
                    ctx.dialog["zielstatus"],
                    attrs,
                )

        def post(state, self, ctx):
            # 'Warten auf' und 'Grund' aus der Statuswechselmaske uebernehmen.
            if not ctx.error:
                self.Update(
                    reason=ctx.dialog["waiting_reason"],
                    waiting_for=ctx.dialog["waiting_for_persno"],
                )

    class REVIEW(State):
        status = 100

    class DISCARDED(State):
        status = 180

        def FollowUpStateChanges(state, self):
            if self.Task:
                target_status = self.Task.getFinalStatus()
                if target_status:
                    return [(target_status, [self.Task], 0, False)]
            return []

    class COMPLETED(State):
        status = 200

        def FollowUpStateChanges(state, self):
            if self.Task:
                target_status = self.Task.getFinalStatus()
                if target_status:
                    return [(target_status, [self.Task], 0, False)]
            return []

    class FROM_WAITINGFOR(Transition):
        transition = (70, "*")

        def post(state, self, ctx):
            # Felder 'warten auf' und 'Grund' leeren
            if not ctx.error:
                self.Update(
                    reason="",
                    waiting_for="",
                )

    # Flag setzen, ob der Offene Punkt abgeschlossen ist.
    # {angelegt, Analyse, in Bearbeitung, Pruefung, Wartet auf jemand anders} => nein
    # {abgeschlossen, gestrichen} => ja
    # {zurueckgestellt} => offen
    class TO_DISCARDED_OR_COMPLETED(Transition):
        transition = ("*", (180, 200))

        def post(state, self, ctx):
            if not ctx.error:
                updates = {"close_flag": "ja"}
                if not self.completion_date:
                    updates["completion_date"] = datetime.date.today()
                self.Update(**updates)

    class TO_DEFERRED(Transition):
        transition = ("*", 60)

        def post(state, self, ctx):
            if not ctx.error:
                self.Update(
                    close_flag="offen",
                    completion_date="",
                )

    class TO_NOT_COMPLETED(Transition):
        transition = ("*", (0, 30, 50, 70, 100))

        def post(state, self, ctx):
            if not ctx.error:
                self.Update(
                    close_flag="nein",
                    completion_date="",
                )
