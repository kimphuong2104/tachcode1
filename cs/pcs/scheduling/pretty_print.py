#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import re
from functools import wraps

from cs.pcs.scheduling.constants import AA, EF, ES, ZZ
from cs.pcs.scheduling.helpers import log_level_is_enabled

# gantt constants
NO_BAR = " "
BAR = "█"
BAR_WIDTH = 2
GANTT_DIFF_NONE = BAR_WIDTH * "▒"
GANTT_SPACE = BAR_WIDTH * " "
GANTT_BAR = BAR_WIDTH * "█"
GANTT_DIFF = {
    (0, 0): GANTT_SPACE,
    (0, 1): BAR_WIDTH * "▄",  # +
    (1, 1): GANTT_BAR,  # =
    (1, 0): BAR_WIDTH * "▀",  # -
}

# text constants
NETWORK = "[{}]"
TASK_ID = "{:.1}"
TWO_DIGITS = "{:0>2}"  # makes sure at least 2 digits are printed
EMPTY = ""
COMMA = ", "
SPACE = " "
NEWLINE = "\n"
TEXT_DIFF_NONE = "[OK]    "  # must be as long or longer than dates_line's end date
TEXT_DIFF_MISSING = "[None]  "  # must be as long or longer than dates_line's end date
ELLIPSIS = "..."
NONE = "--"


def two_digits(value):
    return TWO_DIGITS.format(NONE if value is None else value)


def trim_lines(max_line_length, max_actual_length, lines):
    # max_line_length 80 should only truncate the gantt part
    remaining_line_length = (
        max_line_length - len(ELLIPSIS)
    ) // 2  # to either side of the ellipsis
    re_truncate_line = re.compile(
        f"^(.{{{remaining_line_length}}}).*(.{{{remaining_line_length}}})$"
    )
    re_ellipsis = rf"\g<1>{ELLIPSIS}\g<2>"  # noqa

    def _trim(line):
        return re.sub(re_truncate_line, re_ellipsis, line)

    if max_actual_length > max_line_length:
        lines = [_trim(line) for line in lines]

    return [line.rstrip() for line in lines]


def block(make_lines):
    @wraps(make_lines)
    def _block(*args, **kwargs):
        lines = make_lines(*args, **kwargs)
        max_len = max(len(line) for line in lines)
        return [line.ljust(max_len) for line in lines]

    return _block


@block
def get_task_id_block(uuids):
    lines = [TASK_ID.format(uuid) for uuid in uuids]
    return lines


@block
def get_network_block(network, uuids):
    """
    [01, 02, 03, 04, 05, 06, 07, 08, 09]
    [01, 02, 03, 04, 05, 06, 07, 08, 09]
    [01, 02, 03, 04, 05, 06, 07, 08, 09]
    """
    lines = [
        NETWORK.format(COMMA.join([two_digits(value) for value in network[uuid]]))
        for uuid in uuids
    ]
    return lines


def get_range(start, end):
    return range(start, end + 1, 2)


def gantt_line(start, end, task_net, diff_net, start_index, end_index):
    no_diff = task_net == diff_net

    # pylint: disable=disallowed-name
    if not diff_net or no_diff:
        bar = GANTT_DIFF_NONE if no_diff else GANTT_BAR
        task_start = task_net[start_index]
        task_end = task_net[end_index] + 1

        return EMPTY.join(
            [
                GANTT_SPACE * (task_start - start),
                bar * (task_end - task_start),
                GANTT_SPACE * (end + 1 - task_end),
            ]
        )

    def _visible(net, index):
        task_start = net[start_index]
        task_end = net[end_index] + 1
        return task_start <= index < task_end

    return EMPTY.join(
        [
            GANTT_DIFF[(_visible(task_net, index), _visible(diff_net, index))]
            for index in range(start, end + 1)
        ]
    )


@block
def get_gantt_block(network, diff, uuids, start, end, start_index, end_index):
    """
    A ████         A
    B     ████████ B
    C ████████     C
    """
    lines = [
        gantt_line(
            start,
            end,
            network[uuid],
            diff.get(uuid, None),
            start_index,
            end_index,
        )
        for uuid in uuids
    ]
    return lines


@block
def get_diff_block(network, diff, uuids):
    """
    [OK]
    [None]
    [01, 02, 03, 04, 05, 06, 07, 08, 09]
    """
    if not diff:
        return [TEXT_DIFF_NONE] * len(uuids)

    lines = []

    for uuid in uuids:
        task_net = network[uuid]
        diff_net = diff.get(uuid, None)

        if diff_net:
            lines.append(
                TEXT_DIFF_NONE
                if task_net == diff_net
                else NETWORK.format(
                    COMMA.join([two_digits(value) for value in diff_net])
                )
            )
        else:
            lines.append(TEXT_DIFF_MISSING)

    return lines


def get_start_and_end(network, diff, start_index, end_index):
    start = min(
        [network[task_uuid][start_index] for task_uuid in network]
        + [diff[task_uuid][start_index] for task_uuid in diff]
    )
    end = start

    for net in [network, diff]:
        for task_uuid in net:
            task_end = net[task_uuid][end_index]
            if net[task_uuid][start_index] == task_end:
                task_end = task_end + 1
            end = max(end, task_end)

    return start, end


def get_title_line(start, end, widths):
    indexes = GANTT_SPACE.join(
        [two_digits(str(index)[-2:]) for index in get_range(start, end)]
    )
    network_width, ids_width, gantt_width, ids2_width, diff_width = widths
    has_diff = diff_width > len(TEXT_DIFF_MISSING)
    return SPACE.join(
        [
            "Result".ljust(network_width),
            EMPTY.ljust(ids_width),
            indexes.ljust(gantt_width),
            EMPTY.ljust(ids2_width),
            ("Expected" if has_diff else EMPTY).ljust(diff_width),
        ]
    )


def get_dates_line(calendar, start, end, widths):
    network_width, ids_width, gantt_width, ids2_width, diff_width = widths
    date_start = calendar.network2day(start).strftime("%b %Y").rjust(network_width)
    days = GANTT_SPACE.join(
        [two_digits(calendar.network2day(index).day) for index in get_range(start, end)]
    ).ljust(gantt_width)
    date_end = calendar.network2day(end).strftime("%b %Y").ljust(diff_width)
    return SPACE.join(
        [date_start, ids_width * SPACE, days, ids2_width * SPACE, date_end]
    )


def pretty_print(calendar, network, diff=None, max_line_length=200, earliest=False):
    """
    Pretty-prints task network ``network``
    given an IndexedCalendar instance ``calendar``.

    Example output:

    Result                                 06  08  10  12  14  16  18  20  22  24  26
    [05, 16, 21, 16, 21, 16, 21, 00, 00] A                     ████████████             A
    [05, 20, 25, 20, 25, 20, 25, 00, 00] B                             ████████████     B
    [03, 06, 09, 06, 09, 06, 09, 00, 00] C ████████                                     C
    [05, 22, 27, 22, 27, 22, 27, 00, 00] D                                 ████████████ D
                                Aug 2016   31  01  02  05  06  07  08  09  12  13  14     Sep 2016

    If ``diff`` is given, the output highlights differences:

    Result                                 06  08  10  12  14  16  18  20  22  24  26     Expected
    [05, 16, 21, 16, 21, 16, 21, 00, 00] A                     ▒▒▒▒▒▒▒▒▒▒▒▒             A [OK]
    [05, 20, 26, 20, 26, 20, 26, 00, 00] B                         ▄▄▄▄████████████▀▀▀▀ B [18, 25...
    [05, 06, 11, 26, 31, 06, 11, 20, 20] C ▀▀▀▀▀▀▀▀▀▀▀▀                        ▄▄▄▄▄▄▄▄ C [24, 27...
    [05, 22, 27, 22, 27, 22, 27, 00, 00] D                                 ▒▒▒▒▒▒▒▒▒▒▒▒ D [OK]
                                Aug 2016   31  01  02  05  06  07  08  09  12  13  14     Sep 2016

    (note that the network on the right side is shortened;
    its format would match the one on the left)

    If ``earliest`` is true, the gantt shows earliest dates instead of scheduled ones.
    """
    if not network:
        return "empty network"

    if not diff:
        diff = {}

    start_index, end_index = (ES, EF) if earliest else (AA, ZZ)

    start, end = get_start_and_end(network, diff, start_index, end_index)
    uuids = sorted(network)

    id_block = get_task_id_block(uuids)
    blocks = [
        get_network_block(network, uuids),
        id_block,
        get_gantt_block(network, diff, uuids, start, end, start_index, end_index),
        id_block,
        get_diff_block(network, diff, uuids),
    ]
    widths = [len(block[0]) for block in blocks]
    total_width = sum(widths)

    title_line = get_title_line(start, end, widths)
    dates_line = get_dates_line(calendar, start, end, widths)

    lines = (
        [EMPTY, title_line]
        + [SPACE.join(block_lines) for block_lines in zip(*blocks)]
        + [dates_line]
    )

    return NEWLINE.join(trim_lines(max_line_length, total_width, lines))


def pretty_log(msg, *args, **kwargs):
    if log_level_is_enabled(logging.INFO):
        logging.info(msg)
        logging.info(pretty_print(*args, **kwargs))
