#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

from cs.pcs.checklists import Checklist


def reset_checklists(tasks):
    for t in tasks:
        for cl in t.Checklists:
            if cl.status != Checklist.DISCARDED.status:
                cl.Reset()


def reset_start_time_act(tasks):
    tasks.Update(start_time_act="", days_act="")


def set_start_time_act_to_now(tasks):
    if tasks and tasks[0].Project.act_vals_status_chng:
        tasks.Update(
            start_time_act=datetime.date.today(),
            days_act="",
        )


def reset_end_time_act(tasks):
    tasks.Update(end_time_act="", days_act="")


def set_end_time_act_to_now(tasks):
    if tasks and tasks[0].Project.act_vals_status_chng:
        tasks.Update(end_time_act=datetime.date.today())


def set_percentage_to_0(tasks):
    tasks.Update(percent_complet=0)


def set_percentage_to_1(tasks):
    tasks.Update(percent_complet=1)


def set_percentage_to_100(tasks):
    tasks.Update(percent_complet=100)
