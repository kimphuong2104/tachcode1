#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Task Relationships
------------------

.. note ::

    All examples

    - assume A is the predecessor and B the successor of the relationship
    - show relationships with a gap of zero
      (other cases simply offset B by the amount of days equal to the gap)
    - use lighter boxes to indicate parts of the day the task does not cover
      due to its "early flag" values
      (each day is represented by three spaces representing the
      start, middle and end of the day, respectively)

.. code-block :: none

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Relationship                ┃ Early Flags         ┃ Gantt                      ┃
    ┃                             ┃                     ┃ . 00  02  04  06  08  10   ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ FS ("finish-to-start")      │ A ends late and     │ A     ████████████         │
    │ B must start after A ends   │ B starts early      │ B                 ████████ │
    │ (or at the same time)       │                     │                            │
    │                             │ A ends late and     │ A     ████████████         │
    │                             │ B starts late       │ B             ▒▒██████     │
    │                             │                     │                            │
    │                             │ A ends early and    │ A     ██████████▒▒         │
    │                             │ B starts late       │ B             ▒▒██████     │
    │                             │                     │                            │
    │                             │ A ends early and    │ A     ██████████▒▒         │
    │                             │ B starts early      │ B             ████████     │
    ├─────────────────────────────┼─────────────────────┼────────────────────────────┤
    │ SS ("start-to-start")       │ A starts early and  │ A     ████████████         │
    │ B must start after A starts │ B starts early      │ B     ████████             │
    │ (or at the same time)       │                     │                            │
    │                             │ A starts late and   │ A     ▒▒██████████         │
    │                             │ B starts late       │ B     ▒▒██████             │
    │                             │                     │                            │
    │                             │ A starts late and   │ A     ▒▒██████████         │
    │                             │ B starts early      │ B         ████████         │
    │                             │                     │                            │
    │                             │ A starts early and  │ A     ████████████         │
    │                             │ B starts late       │ B     ▒▒██████             │
    ├─────────────────────────────┼─────────────────────┼────────────────────────────┤
    │ FF ("finish-to-finish")     │ A ends late and     │ A     ████████████         │
    │ B must end after A ends     │ B ends late         │ B         ████████         │
    │ (or at the same time)       │                     │                            │
    │                             │ A ends late and     │ A     ████████████         │
    │                             │ B ends early        │ B             ██████▒▒     │
    │                             │                     │                            │
    │                             │ A ends early and    │ A     ██████████▒▒         │
    │                             │ B ends late         │ B         ████████         │
    │                             │                     │                            │
    │                             │ A ends early and    │ A     ██████████▒▒         │
    │                             │ B ends early        │ B         ██████▒▒         │
    ├─────────────────────────────┼─────────────────────┼────────────────────────────┤
    │ SF ("start-to-finish")      │ A starts early and  │ A     ████████████         │
    │ B must start after A ends   │ B ends late         │ B ████████                 │
    │ (or at the same time)       │                     │                            │
    │                             │ A starts late and   │ A     ▒▒██████████         │
    │                             │ B ends late         │ B ████████                 │
    │                             │                     │                            │
    │                             │ A starts late and   │ A     ▒▒██████████         │
    │                             │ B ends early        │ B   ██████▒▒               │
    │                             │                     │                            │
    │                             │ A starts early and  │ A     ████████████         │
    │                             │ B ends early        │ B ██████▒▒                 │
    ╰─────────────────────────────┴─────────────────────┴────────────────────────────╯


Relationship may have "gaps" that add or subtract any number of days
from the successor's implied start date

Relationships can be violated by constraints
(because in case of conflict, constraints "win").

"""

from cs.pcs.scheduling.calendar import (
    IndexedCalendar,
    add_duration,
    add_gap,
    get_duration_in_days,
)
from cs.pcs.scheduling.constants import (
    AA,
    DR,
    EF,
    ES,
    LF,
    LS,
    RELSHIP_FF,
    RELSHIP_FS,
    RELSHIP_SF,
    RELSHIP_SS,
    ZZ,
)
from cs.pcs.scheduling.helpers import get_value


def apply_relship_forward(pred_net, succ_net, succ_fix, relship, finalize):
    """
    Calculate successor's earliest dates and update ``succ_net`` accordingly.
    There's also some validation:
    The successor is only updated with earliest dates later than its current ones.

    :param pred_net: Network of predecessor task
    :type pred_net: list

    :param succ_net: Network of successor task
    :type succ_net: list

    :param succ_fix:
        - If true, the successor's early flag is fixed.
            The successor will be scheduled starting early and ending late,
            maybe leaving a gap of less than a full workday.
        - If false, the successor will be scheduled optimally.
    :type succ_fix: bool

    :param relship: Relationship info consisting of 4 members:
        1. UUID of the predecessor (unused)
        2. Relationship type
        3. Gap in days
        4. Flag if predecessor is discarded (unused)
        5. Flag if this is a non-persistent parent-child relship (unused)
    :type relship: tuple

    :param finalize: If true, the calculation is based on the
        predecessor's scheduled dates (instead of its earliest dates).
        In this case, the validation will also make sure the successor is not updated so
        its earliest dates are later than its (already calculated) latest dates.
    :type finalize: bool

    :raises TypeError: if the relationship is not iterable
    :raises ValueError: if the relationship cannot be unpacked or its type is invalid
    :raises KeyError: if any network is incomplete
    """
    rel_type = relship[2]
    gap = relship[3]

    if finalize:
        pred_es = get_value(pred_net, AA, ES)
        pred_ef = get_value(pred_net, ZZ, EF)
    else:
        pred_es = pred_net[ES]
        pred_ef = pred_net[EF]

    if rel_type == RELSHIP_FS:
        new_es = add_gap(pred_ef, gap, succ_fix, True, True)
        new_ef = add_duration(new_es, succ_net[DR], succ_fix, True)

    elif rel_type == RELSHIP_SS:
        new_es = add_gap(pred_es, gap, succ_fix, True, True)
        new_ef = add_duration(new_es, succ_net[DR], succ_fix, True)

    elif rel_type == RELSHIP_FF:
        new_ef = add_gap(pred_ef, gap, succ_fix, False, True)
        new_es = add_duration(new_ef, -succ_net[DR], succ_fix, False)

    elif rel_type == RELSHIP_SF:
        new_ef = add_gap(pred_es, gap, succ_fix, False, True)
        new_es = add_duration(new_ef, -succ_net[DR], succ_fix, False)

    else:
        raise ValueError(f"unknown rel_type: '{rel_type}'")

    if finalize:  # apply if between earliest and latest
        if succ_net[ES] < new_es <= succ_net[LS]:
            succ_net[ES] = new_es

        if succ_net[EF] < new_ef <= succ_net[LF]:
            succ_net[EF] = new_ef

    else:
        if new_es > succ_net[ES]:
            succ_net[ES] = new_es

        if new_ef > succ_net[EF]:
            succ_net[EF] = new_ef


def apply_relship_backward(pred_net, succ_net, pred_fix, relship, pred_discarded):
    """
    Calculate predecessor's latest dates and update ``pred_net`` accordingly.
    There's also some validation:
    The predecessor is only updated with latest dates earlier than its current ones.

    :param pred_net: Network of predecessor task
    :type pred_net: list

    :param succ_net: Network of successor task
    :type succ_net: list

    :param pred_fix:
        - If true, the predecessor's early flag is fixed.
            The predecessor will be scheduled starting early and ending late,
            maybe leaving a gap of less than a full workday.
        - If false, the predecessor will be scheduled optimally.
    :type pred_fix: bool

    :param relship: Relationship info consisting of 4 members:
        1. UUID of the successor (unused)
        2. Relationship type
        3. Gap in days
        4. Flag if successor is discarded (unused)
        5. Flag if this is a non-persistent parent-child relship (unused)
    :type relship: tuple

    :param pred_discarded: If true, the predecessor is discarded.
        In this case, its latest dates are also enforced
        to be later than its earliest dates.
        This edge case might come up due to the special handling of discarded tasks.
    :type pred_discarded: bool

    :raises TypeError: if the relationship is not iterable
    :raises ValueError: if the relationship cannot be unpacked or its type is invalid
    :raises KeyError: if any network is incomplete
    """
    rel_type = relship[2]
    gap = relship[3]

    if rel_type == RELSHIP_FS:
        new_lf = add_gap(succ_net[LS], -gap, pred_fix, False, False)
        new_ls = add_duration(new_lf, -pred_net[DR], pred_fix, False)

    elif rel_type == RELSHIP_SS:
        new_ls = add_gap(succ_net[LS], -gap, pred_fix, True, False)
        new_lf = add_duration(new_ls, pred_net[DR], pred_fix, True)

    elif rel_type == RELSHIP_FF:
        new_lf = add_gap(succ_net[LF], -gap, pred_fix, False, False)
        new_ls = add_duration(new_lf, -pred_net[DR], pred_fix, False)

    elif rel_type == RELSHIP_SF:
        new_ls = add_gap(succ_net[LF], -gap, pred_fix, True, False)
        new_lf = add_duration(new_ls, pred_net[DR], pred_fix, True)

    else:
        raise ValueError(f"unknown rel_type: '{rel_type}'")

    if new_ls < pred_net[LS]:
        pred_net[LS] = new_ls

    if new_lf < pred_net[LF]:
        pred_net[LF] = new_lf

    if pred_discarded:
        if pred_net[ES] > pred_net[LS]:
            pred_net[LS] = pred_net[ES]
        if pred_net[EF] > pred_net[LF]:
            pred_net[LF] = pred_net[EF]


def relship_gap_from_network(pred_net, succ_net, rel_type):
    """
    :param pred_net: Predecessor's network
    :type pred_net: list

    :param succ_net: Successor's network
    :type succ_net: list

    :param rel_type: Type of the relship
    :type rel_type: str

    :returns: Amount of full days between related tasks
        according to given calendar profile.
        Note that the result ignores fractions of a day.
        The gap between the index 2 (start of workday day 1)
        and the 5 (end of workday 2) will be 1,
        even though the gap covers 2 full workdays.
    :rtype: int

    :raises ValueError: if the relationship type is invalid
    """
    if rel_type == RELSHIP_FS:
        start, end = pred_net[ZZ], succ_net[AA]

    elif rel_type == RELSHIP_SS:
        start, end = pred_net[AA], succ_net[AA]

    elif rel_type == RELSHIP_FF:
        start, end = pred_net[ZZ], succ_net[ZZ]

    elif rel_type == RELSHIP_SF:
        start, end = pred_net[AA], succ_net[ZZ]

    else:
        raise ValueError(f"unknown rel_type: '{rel_type}'")

    return get_duration_in_days(start, end)


def calculate_relship_gap(calendar_profile_id, pred, succ, rel_type):
    """
    :param calendar_profile_id: Calendar profile to use to determine workdays
    :type calendar_profile_id: cs.pcs.calendar.CalendarProfile

    :param pred: Predecessor of the relationship
    :type pred: cs.pcs.projects.tasks.Task

    :param succ: Successor of the relationship
    :type succ: cs.pcs.projects.tasks.Task

    :param rel_type: Type of the relship
    :type rel_type: str

    :returns: Amount of workdays between related tasks
        according to given calendar profile
    :rtype: int

    :raises ValueError: if the relationship type is invalid
    """
    calendar = IndexedCalendar(
        calendar_profile_id,
        # only load dates close to the actual used dates
        pred.start_time_fcast,
    )

    if rel_type == RELSHIP_FS:
        start = calendar.day2network(
            pred.end_time_fcast, pred.milestone, pred.end_is_early
        )
        end = calendar.day2network(succ.start_time_fcast, True, succ.start_is_early)

    elif rel_type == RELSHIP_SS:
        start = calendar.day2network(pred.start_time_fcast, True, pred.start_is_early)
        end = calendar.day2network(succ.start_time_fcast, True, succ.start_is_early)

    elif rel_type == RELSHIP_FF:
        start = calendar.day2network(
            pred.end_time_fcast, pred.milestone, pred.end_is_early
        )
        end = calendar.day2network(
            succ.end_time_fcast, succ.milestone, succ.end_is_early
        )

    elif rel_type == RELSHIP_SF:
        start = calendar.day2network(pred.start_time_fcast, True, pred.start_is_early)
        end = calendar.day2network(
            succ.end_time_fcast, succ.milestone, succ.end_is_early
        )

    else:
        raise ValueError(f"unknown rel_type: '{rel_type}'")

    return get_duration_in_days(start, end)
