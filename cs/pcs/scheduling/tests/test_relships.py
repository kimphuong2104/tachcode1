#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import pytest
from cdb import testcase

from cs.pcs.scheduling import relships
from cs.pcs.scheduling.constants import AA, DR, EF, ES, LF, LS, ZZ

MAP_CONSTANTS = {
    AA: "AA",
    DR: "DR",
    EF: "EF",
    ES: "ES",
    LF: "LF",
    LS: "LS",
    ZZ: "ZZ",
}


def setup_module():
    testcase.run_level_setup()


def _map_network(network):
    return {MAP_CONSTANTS[key]: value for key, value in network.items()}


def assert_partial_network(expected, network):
    assert set(expected.items()) <= set(
        network.items()
    ), f"{_map_network(network)} does not include {_map_network(expected)}"


def test_apply_relship_forward_fails():
    "[apply_relship_forward] fails"
    with pytest.raises(ValueError) as error:
        relships.apply_relship_forward(
            {DR: 0, ES: 1, EF: 1},
            {DR: 0},
            False,
            (None, None, "??", None, None, None),
            None,
        )

    assert str(error.value) == "unknown rel_type: '??'"


@pytest.fixture(params=[False, True])
def bool_input(request):
    return request.param


@pytest.fixture(params=[(0, 0), (0, 2), (2, 0), (2, 2)])
def durations(request):
    return request.param


@pytest.mark.parametrize(
    "rel_type,pred,succ_fix,gap,expected",
    [
        # note: each test is repeated 8x:
        #       - for finalize True, False (2x)
        #       - for each combination of pred and succ duration 0, 2 (4x)
        # Test cases are named:
        # {relship}.{pred late, pred early}.{gap 0, positive, negative}
        # and may contain multiple gap values and position fixed True, False
        # FS.1: A ends at the end of a day
        # FS.1.1: gap of 0 workdays
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A ▒▒██
        # B     ██▒▒        # B   ██▒▒
        ("EA", {EF: 1}, True, 0, {ES: 2}),
        ("EA", {EF: 1}, False, 0, {ES: 1}),
        # FS.1.2: gap of 1 workday
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A ▒▒██
        # B         ██▒▒    # B       ██▒▒
        ("EA", {EF: 1}, True, 1, {ES: 4}),
        ("EA", {EF: 1}, False, 1, {ES: 3}),
        # FS.1.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A     ▒▒██
        # B     ██▒▒
        ("EA", {EF: 3}, True, -1, {ES: 2}),
        ("EA", {EF: 3}, False, -1, {ES: 2}),
        # FS.2: A ends at the start of a day
        # FS.2.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A ██
        # B ██▒▒
        ("EA", {EF: 0}, True, 0, {ES: 0}),
        ("EA", {EF: 0}, False, 0, {ES: 0}),
        # FS.2.2: gap of 1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ██              # A ██
        # B     ██▒▒        # B   ██▒▒
        ("EA", {EF: 0}, True, 1, {ES: 2}),
        ("EA", {EF: 0}, False, 1, {ES: 1}),
        # FS.2.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A   ▒▒██
        # B ██▒▒
        ("EA", {EF: 2}, True, -1, {ES: 0}),
        ("EA", {EF: 2}, False, -1, {ES: 0}),
        # SS.1: A starts at the end of a day
        # SS.1.1: gap of 0 workdays
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A   ██▒▒          # A   ██▒▒
        # B     ██▒▒        # B   ██▒▒
        ("AA", {ES: 1}, True, 0, {ES: 2}),
        ("AA", {ES: 1}, False, 0, {ES: 1}),
        # SS.1.2: gap of 1 workday
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A   ██▒▒          # A   ██▒▒
        # B         ██▒▒    # B       ██▒▒
        ("AA", {ES: 1}, True, 1, {ES: 4}),
        ("AA", {ES: 1}, False, 1, {ES: 3}),
        # SS.1.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A   ██▒▒
        # B ██▒▒
        ("AA", {ES: 1}, True, -1, {ES: 0}),
        ("AA", {ES: 1}, False, -1, {ES: 0}),
        # SS.2: A starts at the start of a day
        # SS.2.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A ██▒▒
        # B ██▒▒
        ("AA", {ES: 0}, True, 0, {ES: 0}),
        ("AA", {ES: 0}, False, 0, {ES: 0}),
        # SS.2.2: gap of 1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ██▒▒            # A ██▒▒
        # B     ██▒▒        # B   ██▒▒
        ("AA", {ES: 0}, True, 1, {ES: 2}),
        ("AA", {ES: 0}, False, 1, {ES: 1}),
        # SS.2.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A     ██▒▒
        # B ██▒▒
        ("AA", {ES: 2}, True, -1, {ES: 0}),
        ("AA", {ES: 2}, False, -1, {ES: 0}),
        # FF.1: A ends at the end of a day
        # FF.1.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A ▒▒██
        # B ▒▒██
        ("EE", {EF: 1}, True, 0, {EF: 1}),
        ("EE", {EF: 1}, False, 0, {EF: 1}),
        # FF.1.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ▒▒██
        # B     ▒▒██
        ("EE", {EF: 1}, True, 1, {EF: 3}),
        ("EE", {EF: 1}, False, 1, {EF: 3}),
        # FF.1.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A     ▒▒██        # A     ▒▒██
        # B ▒▒██            # B   ▒▒██
        ("EE", {EF: 3}, True, -1, {EF: 1}),
        ("EE", {EF: 3}, False, -1, {EF: 2}),
        # FF.2: A ends at the start of a day
        # FF.2.1: gap of 0 workdays
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A   ▒▒██          # A   ▒▒██
        # B     ▒▒██        # B   ▒▒██
        ("EE", {EF: 2}, True, 0, {EF: 3}),
        ("EE", {EF: 2}, False, 0, {EF: 2}),
        # FF.2.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ██
        # B ▒▒██
        ("EE", {EF: 0}, True, 1, {EF: 1}),
        ("EE", {EF: 0}, False, 1, {EF: 1}),
        # FF.2.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A       ▒▒██      # A       ▒▒██
        # B ▒▒██            # B   ▒▒██
        ("EE", {EF: 4}, True, -1, {EF: 1}),
        ("EE", {EF: 4}, False, -1, {EF: 2}),
        # SF.1: A starts at the end of a day
        # SF.1.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A   ██▒▒
        # B ▒▒██
        ("AE", {ES: 1}, True, 0, {EF: 1}),
        ("AE", {ES: 1}, False, 0, {EF: 1}),
        # SF.1.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A   ██▒▒
        # B     ▒▒██
        ("AE", {ES: 1}, True, 1, {EF: 3}),
        ("AE", {ES: 1}, False, 1, {EF: 3}),
        # SF.1.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A       ██▒▒      # A       ██▒▒
        # B ▒▒██            # B   ▒▒██
        ("AE", {ES: 3}, True, -1, {EF: 1}),
        ("AE", {ES: 3}, False, -1, {EF: 2}),
        # SF.2: A starts at the start of a day
        # SF.2.1: gap of 0 workdays
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A     ██▒▒        # A     ██▒▒
        # B     ▒▒██        # B   ▒▒██
        ("AE", {ES: 2}, True, 0, {EF: 3}),
        ("AE", {ES: 2}, False, 0, {EF: 2}),
        # SF.2.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ██▒▒
        # B ▒▒██
        ("AE", {ES: 0}, True, 1, {EF: 1}),
        ("AE", {ES: 0}, False, 1, {EF: 1}),
        # SF.2.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A         ██▒▒    # A         ██▒▒
        # B ▒▒██            # B   ▒▒██
        ("AE", {ES: 4}, True, -1, {EF: 1}),
        ("AE", {ES: 4}, False, -1, {EF: 2}),
    ],
)
def test_apply_relship_forward(
    rel_type, pred, succ_fix, gap, expected, bool_input, durations
):
    "[apply_relship_forward] A -rel_type+0-> B"
    relship = (None, None, rel_type, gap, None, None)
    finalize = bool_input
    pred_net = {DR: durations[0]}
    pred_net.update(pred)

    if ES in pred:
        pred_net[EF] = pred[ES] + pred_net[DR]
    elif EF in pred:
        pred_net[ES] = pred[EF] - pred_net[DR]

    succ_net = {DR: durations[1], ES: -99, EF: -99}
    pred_net.update(pred)

    if finalize:
        pred_net[AA] = pred_net[ES]
        pred_net[ZZ] = pred_net[EF]
        del pred_net[ES]
        del pred_net[EF]
        succ_net.update(
            {
                LS: 99,
                LF: 99,
            }
        )

    assert (
        relships.apply_relship_forward(pred_net, succ_net, succ_fix, relship, finalize)
        is None
    )
    assert_partial_network(expected, succ_net)


def test_apply_relship_backward_fails():
    "[apply_relship_backward] fails"
    with pytest.raises(ValueError) as error:
        relships.apply_relship_backward(
            {DR: 0}, {DR: 0}, False, (None, None, "??", None, None, None), None
        )

    assert str(error.value) == "unknown rel_type: '??'"


@pytest.mark.parametrize(
    "rel_type,succ,pred_fix,gap,expected",
    [
        # note: each test is repeated 8x:
        #       - for pred_discarded True, False (2x)
        #       - for each combination of pred and succ duration 0, 2 (4x)
        # Test cases are named:
        # {relship}.{pred late, pred early}.{gap 0, positive, negative}
        # and may contain multiple gap values and position fixed True, False
        # FS.1: B starts at the end of a day
        # FS.1.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A ▒▒██
        # B   ██▒▒
        ("EA", {LS: 1}, True, 0, {LF: 1}),
        ("EA", {LS: 1}, False, 0, {LF: 1}),
        # FS.1.2: gap of 1 workday
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A   ▒▒██
        # B       ██▒▒      # B       ██▒▒
        ("EA", {LS: 3}, True, 1, {LF: 1}),
        ("EA", {LS: 3}, False, 1, {LF: 2}),
        # FS.1.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A     ▒▒██
        # B   ██▒▒
        ("EA", {LS: 1}, True, -1, {LF: 3}),
        ("EA", {LS: 1}, False, -1, {LF: 3}),
        # FS.2: B starts at the start of a day
        # FS.2.1: gap of 0 workdays
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A   ▒▒██
        # B     ██▒▒        # B     ██▒▒
        ("EA", {LS: 2}, True, 0, {LF: 1}),
        ("EA", {LS: 2}, False, 0, {LF: 2}),
        # FS.2.2: gap of 1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A   ▒▒██
        # B         ██▒▒    # B         ██▒▒
        ("EA", {LS: 4}, True, 1, {LF: 1}),
        ("EA", {LS: 4}, False, 1, {LF: 2}),
        # FS.2.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ▒▒██
        # B ██▒▒
        ("EA", {LS: 0}, True, -1, {LF: 1}),
        ("EA", {LS: 0}, False, -1, {LF: 1}),
        # SS.1: B starts at the end of a day
        # SS.1.1: gap of 0 workdays
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A ██▒▒            # A   ██▒▒
        # B   ██▒▒          # B   ██▒▒
        ("AA", {LS: 1}, True, 0, {LS: 0}),
        ("AA", {LS: 1}, False, 0, {LS: 1}),
        # SS.1.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ██▒▒
        # B   ██▒▒
        ("AA", {LS: 1}, True, 1, {LS: 0}),
        ("AA", {LS: 1}, False, 1, {LS: 0}),
        # SS.1.3: gap of -1 workday
        # position_fix      # !position_fix
        # . 00  02  04      # . 00  02  04
        # A         ██▒▒    # A       ██▒▒
        # B   ██▒▒          # B   ██▒▒
        ("AA", {LS: 1}, True, -1, {LS: 4}),
        ("AA", {LS: 1}, False, -1, {LS: 3}),
        # SS.2: B starts at the start of a day
        # SS.2.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A ██▒▒
        # B ██▒▒
        ("AA", {LS: 0}, True, 0, {LS: 0}),
        ("AA", {LS: 0}, False, 0, {LS: 0}),
        # SS.2.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ██▒▒
        # B     ██▒▒
        ("AA", {LS: 2}, True, 1, {LS: 0}),
        ("AA", {LS: 2}, False, 1, {LS: 0}),
        # SS.2.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A     ██▒▒        # A   ██▒▒
        # B ██▒▒            # B ██▒▒
        ("AA", {LS: 0}, True, -1, {LS: 2}),
        ("AA", {LS: 0}, False, -1, {LS: 1}),
        # FF.1: B ends at the end of a day
        # FF.1.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A ▒▒██
        # B ▒▒██
        ("EE", {LF: 1}, True, 0, {LF: 1}),
        ("EE", {LF: 1}, False, 0, {LF: 1}),
        # FF.1.2: gap of 1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A   ▒▒██
        # B     ▒▒██        # B     ▒▒██
        ("EE", {LF: 3}, True, 1, {LF: 1}),
        ("EE", {LF: 3}, False, 1, {LF: 2}),
        # FF.1.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A     ▒▒██
        # B ▒▒██
        ("EE", {LF: 1}, True, -1, {LF: 3}),
        ("EE", {LF: 1}, False, -1, {LF: 3}),
        # FF.2: B ends at the start of a day
        # FF.2.1: gap of 0 workdays
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A   ▒▒██
        # B   ▒▒██          # B   ▒▒██
        ("EE", {LF: 2}, True, 0, {LF: 1}),
        ("EE", {LF: 2}, False, 0, {LF: 2}),
        # FF.2.2: gap of 1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ▒▒██            # A   ▒▒██
        # B       ▒▒██      # B       ▒▒██
        ("EE", {LF: 4}, True, 1, {LF: 1}),
        ("EE", {LF: 4}, False, 1, {LF: 2}),
        # FF.2.3: gap of -1 workday
        # . 00  02  04 (position_fix does not matter)
        # A     ▒▒██
        # B   ▒▒██
        ("EE", {LF: 2}, True, -1, {LF: 3}),
        ("EE", {LF: 2}, False, -1, {LF: 3}),
        # SF.1: B ends at the end of a day
        # SF.1.1: gap of 0 workdays
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A ██▒▒            # A   ██▒▒
        # B ▒▒██            # B ▒▒██
        ("AE", {LF: 1}, True, 0, {LS: 0}),
        ("AE", {LF: 1}, False, 0, {LS: 1}),
        # SF.1.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A     ██▒▒
        # B     ▒▒██
        ("AE", {LF: 3}, True, 1, {LS: 2}),
        ("AE", {LF: 3}, False, 1, {LS: 2}),
        # SF.1.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A         ██▒▒    # A       ██▒▒
        # B ▒▒██            # B ▒▒██
        ("AE", {LF: 1}, True, -1, {LS: 4}),
        ("AE", {LF: 1}, False, -1, {LS: 3}),
        # SF.2: B ends at the start of a day
        # SF.2.1: gap of 0 workdays
        # . 00  02  04 (position_fix does not matter)
        # A     ██▒▒
        # B   ▒▒██
        ("AE", {LF: 2}, True, 0, {LS: 2}),
        ("AE", {LF: 2}, False, 0, {LS: 2}),
        # SF.2.2: gap of 1 workday
        # . 00  02  04 (position_fix does not matter)
        # A ██▒▒
        # B   ▒▒██
        ("AE", {LF: 2}, True, 1, {LS: 0}),
        ("AE", {LF: 2}, False, 1, {LS: 0}),
        # SF.2.3: gap of -1 workday
        # position_fix      # not position_fix
        # . 00  02  04      # . 00  02  04
        # A         ██▒▒    # A       ██▒▒
        # B   ▒▒██          # B   ▒▒██
        ("AE", {LF: 2}, True, -1, {LS: 4}),
        ("AE", {LF: 2}, False, -1, {LS: 3}),
    ],
)
def test_apply_relship_backward(
    rel_type, succ, pred_fix, gap, expected, bool_input, durations
):
    "[apply_relship_backward] A -rel_type+0-> B"
    relship = (None, None, rel_type, gap, None, None)
    pred_discarded = bool_input
    pred_net = {DR: durations[0], LS: 99, LF: 99}
    succ_net = {DR: durations[1]}
    succ_net.update(succ)

    if LS in succ:
        succ_net[LF] = succ[LS] + succ_net[DR]
    elif LF in succ:
        succ_net[LS] = succ[LF] - succ_net[DR]

    if pred_discarded:
        pred_net.update(
            {
                ES: -99,
                EF: -99,
            }
        )

    assert (
        relships.apply_relship_backward(
            pred_net, succ_net, pred_fix, relship, pred_discarded
        )
        is None
    )
    assert_partial_network(expected, pred_net)


@pytest.mark.parametrize(
    "rel_type,pred,succ,expected",
    [
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("EA", {ZZ: 4}, {AA: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("EA", {ZZ: 5}, {AA: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("EA", {ZZ: 4}, {AA: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("EA", {ZZ: 5}, {AA: 1}, -2),
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("AA", {AA: 4}, {AA: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("AA", {AA: 5}, {AA: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("AA", {AA: 4}, {AA: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("AA", {AA: 5}, {AA: 1}, -2),
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("EE", {ZZ: 4}, {ZZ: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("EE", {ZZ: 5}, {ZZ: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("EE", {ZZ: 4}, {ZZ: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("EE", {ZZ: 5}, {ZZ: 1}, -2),
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("AE", {AA: 4}, {ZZ: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("AE", {AA: 5}, {ZZ: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("AE", {AA: 4}, {ZZ: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("AE", {AA: 5}, {ZZ: 1}, -2),
    ],
)
def test_relship_gap_from_network(rel_type, pred, succ, expected):
    "[relship_gap_from_network]"
    result = relships.relship_gap_from_network(pred, succ, rel_type)
    assert result == expected


@pytest.mark.parametrize(
    "rel_type,pred,succ,expected",
    [
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("EA", {ZZ: 4}, {AA: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("EA", {ZZ: 5}, {AA: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("EA", {ZZ: 4}, {AA: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("EA", {ZZ: 5}, {AA: 1}, -2),
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("AA", {AA: 4}, {AA: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("AA", {AA: 5}, {AA: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("AA", {AA: 4}, {AA: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("AA", {AA: 5}, {AA: 1}, -2),
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("EE", {ZZ: 4}, {ZZ: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("EE", {ZZ: 5}, {ZZ: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("EE", {ZZ: 4}, {ZZ: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("EE", {ZZ: 5}, {ZZ: 1}, -2),
        # 00  02  04
        #         ██▒▒
        # ██▒▒
        ("AE", {AA: 4}, {ZZ: 0}, -2),
        # 00  02  04
        #         ▒▒██
        # ██▒▒
        ("AE", {AA: 5}, {ZZ: 0}, -3),
        # 00  02  04
        #         ██▒▒
        # ▒▒██
        ("AE", {AA: 4}, {ZZ: 1}, -1),
        # 00  02  04
        #         ▒▒██
        # ▒▒██
        ("AE", {AA: 5}, {ZZ: 1}, -2),
    ],
)
def test_calculate_relship_gap(rel_type, pred, succ, expected):
    _pred = mock.Mock()
    _succ = mock.Mock()

    with mock.patch.object(relships, "IndexedCalendar") as IndexedCalendar:
        day2network = IndexedCalendar.return_value.day2network
        day2network.side_effect = [
            pred.get(AA, pred.get(ZZ)),
            succ.get(AA, succ.get(ZZ)),
        ]
        result = relships.calculate_relship_gap("CAL_PROF", _pred, _succ, rel_type)

    assert result == expected
    assert day2network.call_count == 2
