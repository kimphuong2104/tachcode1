#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from cs.pcs.scheduling.calendar import add_duration
from cs.pcs.scheduling.constants import (
    DR,
    EF,
    ES,
    FNET,
    FNLT,
    LF,
    LS,
    MFO,
    MSO,
    SNET,
    SNLT,
)


def handle_fixed_constraints(task, task_net):
    constraint_type, constraint_date = task["constraint_type"], task["constraint_date"]
    duration = task_net[DR]
    position_fix = task["position_fix"]

    if constraint_type == MSO:
        end = add_duration(constraint_date, duration, position_fix, True)
        task_net[ES] = constraint_date
        task_net[EF] = end
        task_net[LS] = constraint_date
        task_net[LF] = end

    elif constraint_type == MFO:
        start = add_duration(constraint_date, -duration, position_fix, False)
        task_net[ES] = start
        task_net[EF] = constraint_date
        task_net[LS] = start
        task_net[LF] = constraint_date

    elif constraint_type == SNET:
        if constraint_date > task_net[ES]:
            task_net[ES] = constraint_date
            task_net[EF] = add_duration(constraint_date, duration, position_fix, True)
            task_net[LS] = max(task_net[LS], task_net[ES])
            task_net[LF] = max(task_net[LF], task_net[EF])

    elif constraint_type == SNLT:
        if constraint_date < task_net[LS]:
            task_net[LS] = constraint_date
            task_net[LF] = add_duration(constraint_date, duration, position_fix, True)
            task_net[ES] = min(task_net[LS], task_net[ES])
            task_net[EF] = min(task_net[LF], task_net[EF])

    elif constraint_type == FNET:
        if constraint_date > task_net[EF]:
            task_net[ES] = add_duration(constraint_date, -duration, position_fix, False)
            task_net[EF] = constraint_date
            task_net[LS] = max(task_net[LS], task_net[ES])
            task_net[LF] = max(task_net[LF], task_net[EF])

    elif constraint_type == FNLT and constraint_date < task_net[LF]:
        task_net[LS] = add_duration(constraint_date, -duration, position_fix, False)
        task_net[LF] = constraint_date
        task_net[ES] = min(task_net[LS], task_net[ES])
        task_net[EF] = min(task_net[LF], task_net[EF])
