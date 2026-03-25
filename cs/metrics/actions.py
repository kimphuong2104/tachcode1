#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
*****************************************************************
Module to handle the assignment of actions to a quality characteristic
*****************************************************************
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import util
from cdb import constants
from cdb import sqlapi

from cdb.objects.expressions import Expression, Literal
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Forward
from cdb.objects import NULL
from cdb.objects import Rule

from cs.metrics import targetprocessor as TargetProcessor

from cs import actions
from cs import currency

from cdb.platform.mom import entities

from cs.metrics import get_pydate_format

import functools
import operator
import sys
import six

# Object rule to decide which actions should be showed in the UI
__ACTION_RULE__ = "cdbqc: valid actions"
ActionRule = None
__ACTION_OPTIMAL_RULE__ = "cdbqc: optimal actions"
ActionOptimalRule = None
__QC_VISIBLE_RULE__ = "cdbqc: visible quality characteristics"
QCRule = None

fAction = Forward("cs.actions.Action")
fQCAction = Forward("cs.metrics.actions.QCAction")


class QCAction(Object):
    """ Link class between actions and quality characteristics

        :attribute Action: List of actions linked by an object.
    """
    __maps_to__ = "cdbqc_action2qc"
    __classname__ = "cdbqc_action2qc"

    Action = Reference_1(fAction, fAction.cdb_object_id == fQCAction.action_object_id)


def __loadRules():
    global ActionRule
    global ActionOptimalRule
    global QCRule
    if ActionRule is None:
        ActionRule = Rule.ByKeys(__ACTION_RULE__)
    if ActionOptimalRule is None:
        ActionOptimalRule = Rule.ByKeys(__ACTION_OPTIMAL_RULE__)
    if QCRule is None:
        QCRule = Rule.ByKeys(__QC_VISIBLE_RULE__)


def isValidTargetValue(target_value):
    """
    Check whether given target_value is valid
    """
    check = False
    if target_value is not None and target_value != NULL:
        try:
            TargetProcessor.TargetProcessor(target_value)
            check = True
        except TargetProcessor.InvalidTargetValue:
            check = False
    return check


def getActionData(qc_id, op_type, act_value, target_value):
    """
    Get Data needed to plot the graphic for action data

    :param qc_id: Id of quality characteristic to identify the object
    :type qc_id: A string which contains a cdb_object_id

    :param op_type: A flag to decide how to display results
    :type param: string

    :returns: a dictionary containing the data needed for the representation of actions
    """
    from cs.metrics import qualitycharacteristics

    __loadRules()
    # all mapped qc actions
    all_qcactions = sqlapi.RecordSet2(
        table="cdbqc_action2qc",
        condition=Expression('=', QCAction.qc_object_id, Literal(QCAction.qc_object_id, qc_id)).to_string(),
        access="read"
    )
    # valid actions
    valid_action_cache = {
        x.cdb_object_id: x for x in actions.Action.Query(
            condition=actions.Action.cdb_object_id.one_of(*[x.action_object_id for x in all_qcactions])
        ) if ActionRule.match(x)
    }
    # filtered qc actions
    qcactions = [x for x in all_qcactions if x.action_object_id in valid_action_cache]
    qc = qualitycharacteristics.QualityCharacteristic.ByKeys(qc_id)
    if QCRule.match(qc):
        if not qc:
            return {"data": [],
                     "qcd_unit_name": '',
                     "qcd_name": '',
                     "targets": []}
        create_action_url = QCAction.MakeCdbcmsg(
            constants.kOperationNew,  # @UndefinedVariable
            qc_object_id=qc.cdb_object_id
        ).get_url()

        qcdef = qc.Definition

        if not target_value:
            target_value = qc.target_value
        if not act_value:
            act_value = qc.act_value

        targets = []
        if isValidTargetValue(target_value):
            import sympy

            target_set = TargetProcessor.TargetProcessor(target_value.replace(",", ".")).values
            frmt = lambda x: "-inf" if x == -sympy.oo else "inf" if x == sympy.oo else float(x)
            if isinstance(target_set, sympy.Interval):
                targets = [[frmt(target_set.start), frmt(target_set.end)]]
            elif isinstance(target_set, sympy.FiniteSet):
                targets = [[frmt(num), frmt(num)] for num in target_set.args]
            elif isinstance(target_set, sympy.Union):
                intervals = [inte for inte in target_set.args if isinstance(inte, sympy.Interval)]
                fsets = [fset for fset in target_set.args if isinstance(fset, sympy.FiniteSet)]
                targets = [[frmt(inte.start), frmt(inte.end)] for inte in intervals] + \
                        (six.moves.reduce(operator.add,
                                [[[frmt(num), frmt(num)] for num in fset.args] for fset in fsets])
                                if fsets else [])
                targets.sort(key=lambda x: -sys.float_info.max if x[0] == "-inf" else
                                            sys.float_info.max if x[0] == "inf" else x[0])

        if op_type == "Zeige alle**":
            result = {"data": [[act.effect, act.action_object_id] for act in qcactions],
                      "qcd_unit_name": qcdef.Unit.Name[''] if qcdef.Unit is not None else '',
                      "qcd_name": qcdef.Name[''] if qcdef is not None else '',
                      "targets": targets, "act_value": act_value if (act_value is not None and act_value != NULL) else "",
                      "target_value": target_value if (target_value is not None and target_value != NULL) else "",
                      'create_action_url': create_action_url
                      }
        else:
            result = {"data": [[act.effect, act.action_object_id] for act in qcactions],
                      "optimal_mix": getResult(valid_action_cache, qcactions, act_value, target_value) if isValidTargetValue(target_value) else [],
                      "qcd_unit_name": qcdef.Unit.Name[''] if qcdef.Unit is not None else '',
                      "qcd_name": qcdef.Name[''] if qcdef is not None else '',
                      "targets": targets, "act_value": act_value if (act_value is not None and act_value != NULL) else "",
                      "target_value": target_value if (target_value is not None and target_value != NULL) else "",
                      'create_action_url': create_action_url
                      }
        return result
    else:
        raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_qc")


def getCost(action):
    costs = None
    if action.cost != NULL:
        if action.Currency:
            costs = action.Currency.convertToReference(value=action.cost)
        else:
            costs = action.cost

    if action.effort != NULL and util.get_prop('qcwr') is not '':
        wage_rate = None
        try:
            wage_rate = float(util.get_prop('qcwr'))
        except ValueError:
            pass
        if wage_rate:
            additional_costs = (action.effort * wage_rate)
            if costs is not None:
                costs += additional_costs
            else:
                costs = additional_costs
    return costs


def __formatCosts(costs):
    if costs is not None:
        c = entities.CDBClassDef('cdb_action')
        a = c.getAttributeDefinition('cost')
        return a.format_value(costs)
    else:
        return ""


def getTooltipData(action_id, qc_id):
    """
    Get Data needed to display the Tooltip

    :param action_id: Id of the action to identify the object
    :type action_id: String, containing a cdb_object_id
    """
    action = actions.Action.ByKeys(cdb_object_id=action_id)
    qc_action = QCAction.ByKeys(qc_object_id=qc_id, action_object_id=action_id)

    base_costs = getCost(action)
    if action.Currency:
        costs = currency.Currency.getReferenceCurrency()\
                .convertTo(action.Currency, base_costs)
        currency_symbol = " " + action.Currency.symbol
    else:
        costs = base_costs
        currency_symbol = ""

    data = list(map(str, [action.name,
                     str(__formatCosts(costs)) + currency_symbol,
                     action.cdb_status_txt,
                     action.mapped_subject_name,
                     action.end_time_plan.strftime(get_pydate_format())
                     if action.end_time_plan else "",
                     qc_action.GetFormattedValue('effect')]))
    return {'data': data}


def getResult(action_cache, actions, act_value, target_value):
    """
    Identifies an optimal set of actions, which satisfy the constraints.

    :param action_cache: Cache of Actions by cdb_object_id
    :type action_cache: dict (cdb_object_id: Action)
    :param actions: List of available Actions.
    :type actions: QCAction
    :param act_value: Actual value of the quality characteristic
    :param target_value: Constraints which the values need to satisfy
    :type target_value: A string that can be parsed by TargetProcessor
    """
    __loadRules()
    opt_actions = []
    if len(actions):
        opt_actions = [
            x for x in actions if (
                x.action_object_id in action_cache and
                ActionOptimalRule.match(
                    action_cache.get(x.action_object_id)
                )
            )
        ]

    if len(opt_actions):
        def objective(*args):
            tp = TargetProcessor.TargetProcessor(target_value.replace(",", "."))
            if type(act_value) == float:
                result = tp(act_value + sum(args))
            else:
                result = tp(float(act_value.replace(",", ".")) + sum(args))
            return result

        costs = [getCost(action_cache.get(act.action_object_id)) for act in opt_actions if act.action_object_id in action_cache]
        effects = [act.effect for act in opt_actions]
        action_ids = [act.action_object_id for act in opt_actions]

        if None in costs:
            return []

        try:
            optimum, solution = solve_optimization(len(opt_actions), costs, effects, objective)
        except UnfeasibleProblemError:
            return []

        result = [action for action, chosen in zip(action_ids, solution) if chosen]
        return result
    else:
        return []


class UnfeasibleProblemError(Exception):
    """ Exception raised when an optimization problem is unfeasible (i.e. has no solution). """
    pass


def solve_optimization(n, costs, effects, target, coeff=0):
    """
    Solves the optimization problem of finding an optimal action set
    which satisfies the target.

    :param n: number of actions being considers, needs to equal ``len(costs)`` and ``len(effects)``
    :param costs: costs of each action
    :type costs: list of floats
    :param effects: effects of each action on the value of the quality characteristic
    :type effects: list of floats
    :param target: constraints that the value need to satisfy
    :type target: a function that accepts a list of floats and returns True if its sum satisfies the constraints
    """
    if n == 1:
        if target(0):
            return (coeff, [False])
        elif target(effects[0]):
            return (costs[0] + coeff, [True])
        else:
            raise UnfeasibleProblemError("ProblemUnfeasible")
    else:
        try:
            a, solution_a = solve_optimization(n - 1, costs[1:], effects[1:],
                                               target, coeff)
        except UnfeasibleProblemError:
            a = None

        try:
            b, solution_b = solve_optimization(n - 1, costs[1:], effects[1:],
                                               functools.partial(target, effects[0]),
                                               coeff + costs[0])
        except UnfeasibleProblemError:
            b = None

        if a is None:
            if b is None:
                raise UnfeasibleProblemError("ProblemUnfeasible")
            else:
                return (b, [True] + solution_b)
        elif b is None:
            return (a, [False] + solution_a)
        elif a <= b:
            return (a, [False] + solution_a)
        else:
            return (b, [True] + solution_b)
