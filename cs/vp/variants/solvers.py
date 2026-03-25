#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module Solvers

This is the documentation for the Solvers module.
"""

import time
import sys
import hashlib
import re
from cdb import util


class ProblemVariable(object):
    """ Base class and interface definition for problem variables. """

    def __init__(self, variable_id, name, values, value_names):
        self._id = variable_id
        self._name = name
        self._values = values
        self._value_dict = dict(zip(values, value_names))
        self._value_name_dict = dict(zip(value_names, values))

    def getId(self):
        """ Returns the unique id of the variable. """
        return self._id

    def getValues(self):
        """ Returns the possible variable values as list. """
        return self._values

    def hasValues(self):
        """ Returns True, if the variable has at least one value. """
        return len(self._values) > 0

    def getName(self):
        """ Returns the variable name."""
        return self._name

    def getValueName(self, value):
        """ Returns the value name for a given value.
        Returns the passed value, if the value does not exist for this variable.
        Returns an empty string, if value is None.
        """
        return "" if value is None else self._value_dict.get(value, value)

    def getValueNames(self):
        """ Returns all value names. """
        return list(self._value_dict.values())

    def getValueByName(self, value_name):
        """ Returns the value id for a given value display name.
        Note that value names must be unique per property."""
        return self._value_name_dict.get(value_name)

    def printVariable(self):
        """ Prints the variable. For logging and debugging purposes. """
        print("%s (%s): %s" % (self._name, self._id, self._values))


class ProblemConstraint(object):
    """  Abstract base class for problem constraints. """

    def __init__(self, used_variable_ids):
        self._variable_ids = used_variable_ids

    def variables_used(self):
        """ Returns a set of all variable ids used by the constraint """
        return self._variable_ids

    def compute(self):
        """ Returns the compute function """
        pass


class BasicProblemSolver(object):
    def __init__(self, variables, constraints, solution_variables=[]):

        self.variables = [v for v in variables if v.hasValues()]
        self.variable_ids = set([v.getId() for v in variables])
        self.constraints = [cons for cons in constraints if len(cons.variables_used()) > 1 and cons.variables_used() <= self.variable_ids]
        self.metrics = {}
        self.solution_variables = []
        self.solution_variable_ids = []
        if solution_variables:
            solution_variable_ids = set([v.getId() for v in solution_variables])
            if solution_variable_ids < self.variable_ids:
                self.solution_variables = solution_variables
                self.solution_variable_ids = solution_variable_ids
            elif solution_variable_ids != self.variable_ids:
                raise RuntimeError("solution_variables must be a subset of variables")
        self.solution_keys = set()
        self.problem = None
        self.persistent_pager = None
        self.solver_result_pager = None

    def _init(self, presettings=None):
        self._initMetrics()
        self.problem = self._setupProblem(presettings)
        self.solution_keys = set()

    def getSolutionVariables(self):
        return self.solution_variables if self.solution_variables else self.variables

    def getSolutionVariableIds(self):
        return self.solution_variable_ids if self.solution_variable_ids else self.variable_ids

    def getAllVariables(self):
        return self.getSolutionVariables()

    def _translate_solution(self, solution):
        """ Reduces the solution to self.solution_variables.
        Returns None, if the reduced solution already occurred.
        Returns the input solution, if self.solution_variables is empty.
        """
        if self.solution_variable_ids:
            checksum, signature = self.getSolutionChecksum(solution)
            if checksum not in self.solution_keys:
                self.solution_keys.add(checksum)
                return dict(zip(self.solution_variable_ids,
                                [solution[vid] for vid in self.solution_variable_ids]))
        else:
            return solution

    def getFilteredSolutionSignature(self, solution):
        solution_ids = [var.getId() for var in self.getSolutionVariables()]
        filtered_solution = ((x, y) for (x, y) in solution.items() if x in solution_ids)
        return self.getSolutionSignature(filtered_solution)

    @classmethod
    def getSolutionSignature(cls, solution):
        if type(solution) == dict:
            solution = list(solution.items())
        return ','.join(("%s:%s" % item for item in sorted(solution, key=lambda t: t[0])))

    @classmethod
    def parseSolutionSignature(cls, signature):
        if not signature:
            return {}

        def parse_value(val):
            if val in ["True", "False"]:
                return val
            else:
                return int(val)

        return dict((map(parse_value, re.findall(r'(\d+|True|False)', pair)) for pair in signature.split(',')))

    def getSolutionChecksum(self, solution):
        signature = self.getFilteredSolutionSignature(solution)
        m = hashlib.md5()
        m.update(signature.encode("utf-8"))
        return m.hexdigest(), signature

    def solve(self, presettings=None):
        """ Solves the problem completely. Returns a list of all solutions."""
        self._init(presettings)
        start = time.time()
        solutions = list(self.problem.getSolutions())
        solver_time = time.time() - start
        self.metrics["solver_time"] = solver_time

        if self.solution_variables:
            solutions = [s for s in [self._translate_solution(s) for s in solutions] if s is not None]
        self.metrics["n_all_solutions"] = len(solutions)
        return solutions

    def iterate(self, presettings=None):
        """ Iterates over the solutions without solving all."""
        self._init(presettings)
        for solution in self.problem.getSolutionIter():
            s = self._translate_solution(solution)
            if s:
                self.metrics["n_all_solutions"] += 1
                yield s

    def extract(self, solution_dict):
        result = {}
        for vid in self.getSolutionVariableIds():
            val = solution_dict.get(vid, None)
            if val is None:
                result = {}
                break
            else:
                result[vid] = val
        return result

    def containsAllVariables(self, solution_dict, exact=False):
        """ Returns true, if the solution dictionary contains
        all solution variables. If the exact flag ist set to True,
        the solution_dict must exactly contain the solution variables,
        not more or less."""
        if exact:
            return set(self.getSolutionVariableIds()) == set(solution_dict.keys())
        else:
            return set(self.getSolutionVariableIds()) <= set(solution_dict.keys())

    def validate(self, solution_dict):
        """ Returns True, if the solution described by solution_dict
        is a valid solution. Returns False, if the solution is not valid
        or contains more or less solution properties as defined by this solver."""

        # if not self.containsAllVariables(solution_dict, True):
        #     return False

        # FIXME: optimieren? auch bei NestedSolver?
        validator = self._setupProblem(solution_dict)

        if self.solution_variable_ids:
            result = False
            solution_keys = []
            for s in validator.getSolutionIter():
                checksum, signature = self.getSolutionChecksum(s)
                if checksum not in solution_keys:
                    solution_keys.append(checksum)
                if len(solution_keys) > 1:
                    break
            result = len(solution_keys) == 1
        else:
            # FIXME: distinguish between False and incomplete

            # check if the iterator is not empty
            # http://stackoverflow.com/a/3114640/785542
            result = any(True for _ in validator.getSolutionIter())
        return result

    def getMetrics(self):
        return self.metrics

    def getSolutionSpaceSize(self, with_presetted_variables=None):
        size_solution_space = 1
        for v in self.getSolutionVariables():
            if with_presetted_variables:
                if v not in with_presetted_variables:
                    size_solution_space *= len(v.getValues())
            else:
                size_solution_space *= len(v.getValues())
        return size_solution_space

    def printSolutions(self, presettings=None, max_solutions=0):
        output_table = SolutionTable(self.getSolutionVariables())
        output_table.make_header()
        output_table.make_separator()
        for n, solution in enumerate(self.iterate(presettings)):
            if max_solutions and n >= max_solutions:
                print("%s solutions displayed. More solutions are available but not shown." % n)
                break
            output_table.make_line("", n + 1, lambda var: solution[var])

    def printMetrics(self):
        print("Solver metrics:")
        for k, v in self.getMetrics().items():
            sys.stdout.write("{0:{width}}".format(k, width=25) + str(v) + "\n")

    def getPersistentPager(self, collection, forward_solved_pages):
        if not self.persistent_pager:
            from cs.vp.variants.pagers import ObjectCollectionPager
            self.persistent_pager = ObjectCollectionPager(self, collection, forward_solved_pages)
        return self.persistent_pager

    def getSolverResultPager(self, collection, forward_solved_pages):
        if not self.solver_result_pager:
            from cs.vp.variants.pagers import SolverResultPager
            self.solver_result_pager = SolverResultPager(self, forward_solved_pages,
                                                         self.getPersistentPager(collection, forward_solved_pages))
        return self.solver_result_pager

    # ---------- Internal methods to setup a problem -------------
    def _initMetrics(self):
        self.metrics = {"solver_time": 0,
                        "n_all_solutions": 0,
                        "size_solution_space": self.getSolutionSpaceSize(),
                        "n_properties": len(self.variables),
                        "n_constraints": len(self.constraints)}

    def _setupProblem(self, presettings=None):
        try:
            import constraint
        except ImportError:
            raise util.ErrorMessage("cdbvp_constraint_library")

        problem = constraint.Problem()
        for variable in self.variables:
            vid = variable.getId()
            if presettings and vid in presettings:
                problem.addVariable(vid, [presettings[vid]])
            else:
                problem.addVariable(vid, variable.getValues())

        for cons in self.constraints:
            problem.addConstraint(cons.compute(), cons.variables_used())
        return problem


class InnerProblem(object):

    MISSING_INNER_SOLUTION_VALUE = '-'
    UNDEFINED_INNER_SOLUTION_VALUE = ''

    def __init__(self, outer_variables, inner_variables, constraints):

        self.inner_variables = [v for v in inner_variables if v.hasValues()]
        self.inner_variable_ids = [v.getId() for v in self.inner_variables]
        self.inner_variable_ids.sort()
        self.all_variables = outer_variables + self.inner_variables
        self.inner_solver = BasicProblemSolver(self.all_variables, constraints)
        self.inner_validator = BasicProblemSolver(self.all_variables, constraints, self.inner_variables)
        self.missing_inner_solution_template = dict(zip(self.inner_variable_ids,
                                                        list(len(self.inner_variable_ids) *
                                                             self.MISSING_INNER_SOLUTION_VALUE)))
        self.undefined_inner_solution_template = dict(zip(self.inner_variable_ids,
                                                          list(len(self.inner_variable_ids) *
                                                               self.UNDEFINED_INNER_SOLUTION_VALUE)))

    def solveInnerProblem(self, outer_solution):
        """ Builds the inner problem with all variables (outer + inner) and preset
        outer variables with values from outer solution.
        Returns a list of inner solutions. """
        self.inner_solver._init(outer_solution)
        return self.inner_solver.problem.getSolutions()

    def solveInnerProblemIter(self, outer_solution, presettings=None):
        """ Builds the inner problem with all variables (outer + inner) and preset
        outer variables with values from outer solution.
        Returns a list of inner solutions. """
        if presettings:
            preset_variables = dict(outer_solution)
            preset_variables.update(presettings)
            self.inner_solver._init(preset_variables)
        else:
            self.inner_solver._init(outer_solution)
        return self.inner_solver.problem.getSolutionIter()

    def validateStandalone(self, inner_solution):
        return self.inner_validator.validate(inner_solution)

    def getVariables(self):
        return self.inner_variables

    def getFilteredSolutionSignature(self, solution):
        elems = []
        for vid in self.inner_variable_ids:
            val = solution.get(vid, None)
            if val in (self.MISSING_INNER_SOLUTION_VALUE, self.UNDEFINED_INNER_SOLUTION_VALUE):
                elems = []
                break
            if val is not None:
                elems.append("%s:%s" % (vid, val))
        return ','.join(elems)

    def getSolutionChecksum(self, solution):
        signature = self.getFilteredSolutionSignature(solution)
        m = hashlib.md5()
        m.update(signature.encode("utf-8"))
        return m.hexdigest(), signature

    def extract(self, solution):
        inner_variant = {}
        for vid in self.inner_variable_ids:
            val = solution.get(vid, None)
            if val in (None, self.MISSING_INNER_SOLUTION_VALUE, self.UNDEFINED_INNER_SOLUTION_VALUE):
                inner_variant = {}
                break
            else:
                inner_variant[vid] = val
        return inner_variant


class NestedProblemSolver(BasicProblemSolver):

    def __init__(self, outer_variables, inner_variables_sets, constraints):
        super(NestedProblemSolver, self).__init__(outer_variables, constraints)

        self.all_variables = list(self.variables)
        self.inner_problems = []
        for inner_variables in inner_variables_sets:
            self.inner_problems.append(InnerProblem(outer_variables, inner_variables, constraints))
            self.all_variables += inner_variables

        self.complete_dummy = {}
        for p in self.inner_problems:
            self.complete_dummy.update(p.undefined_inner_solution_template)

    def _initMetrics(self):
        super(NestedProblemSolver, self)._initMetrics()
        self.metrics["n_properties"] = len(self.all_variables)
        n_constraints = 0
        for p in self.inner_problems:
            n_constraints += len(p.inner_solver.constraints)
        self.metrics["n_constraints"] = n_constraints

    def extractPresettingsForInnerProblem(self, presettings, inner_problem):
        inner_presettings = {}
        for vid in inner_problem.inner_variable_ids:
            val = presettings.get(vid, None)
            if val is not None:
                inner_presettings[vid] = val
        return inner_presettings

    def extractPresettings(self, presettings):
        result = {}
        for i, inner_problem in enumerate(self.inner_problems):
            inner_presettings = self.extractPresettingsForInnerProblem(
                presettings, inner_problem)
            if inner_presettings:
                result[i] = inner_presettings
        return result

    def getCombinedSolutions(self, outer_solution):
        """ Solves the inner problem for the outer solution
        and returns a list of combined solutions. """
        result = []
        for solution in self.getCombinedSolutionsIter(outer_solution):
            result.append(solution)
        return result

    def getCombinedSolutionsIter(self,
                                 outer_solution,
                                 inner_problems_presettings={},
                                 invalid_persistent_inner_solutions={}):
        # Alle inneren Lösungen mit genau einem (oder keinem = Dummy) Ergebnis zu einer äußeren Lösung können
        # zu einer Zeile zusammengefasst werden.
        # Alle inneren Lösungen mit mehr als einem Ergebnis werden einzeln zur äußeren Lösung dargestellt.
        # Die Fehlenden anderen Lösungen werden mit Dummy Solution aufgefüllt.
        one_on_one_result = dict(outer_solution)
        any_inner_result = False
        any_one_on_one_result = False
        one_on_one_filtered_out = False
        for i, inner_problem in enumerate(self.inner_problems):

            others_have_search_conditions = False
            for inner_id, presettings in inner_problems_presettings.items():
                if inner_id != i and presettings:
                    others_have_search_conditions = True
                    break

            one_result = None
            first_result = None
            invalid_inner_solutions = invalid_persistent_inner_solutions.get(i, [])
            num_inner_results = len(invalid_inner_solutions)
            for n, complete_solution in enumerate(inner_problem.solveInnerProblemIter(outer_solution, inner_problems_presettings.get(i, None))):
                num_inner_results += 1
                any_inner_result = True
                if num_inner_results == 1:
                    # Die erste Lösung zurückstellen, weil wir erst
                    # wissen müssen, ob es noch mehr Lösungen gibt.
                    first_result = complete_solution
                    one_result = complete_solution
                else:
                    # Skip, if any other inner problem has search conditions.
                    # They cannot match because of all other inner solutions are undefined
                    # in this case.
                    if others_have_search_conditions:
                        break

                    one_result = None

                    # die ungültigen persistenten Lösungen rausgeben
                    invalid_inner_solutions.reverse()
                    while invalid_inner_solutions:
                        result = dict(self.complete_dummy)
                        result.update(outer_solution)
                        result.update(invalid_inner_solutions.pop())
                        yield result

                    # die erste zurückgestellte Lösung rausgeben
                    if first_result:
                        result = dict(self.complete_dummy)
                        result.update(first_result)
                        yield result
                        first_result = None
                    result = dict(self.complete_dummy)
                    result.update(complete_solution)
                    yield result

            if num_inner_results == 1:
                # genau eine innere Lösung -> in one_on_one_result integrieren
                if one_result:
                    one_on_one_result.update(one_result)
                else:
                    one_on_one_result.update(invalid_inner_solutions[0])
                any_one_on_one_result = True
            elif num_inner_results == 0:
                if inner_problems_presettings.get(i, None):
                    one_on_one_filtered_out = True
                one_on_one_result.update(inner_problem.missing_inner_solution_template)
            else:
                if inner_problems_presettings.get(i, None):
                    one_on_one_filtered_out = True
                one_on_one_result.update(inner_problem.undefined_inner_solution_template)

        # one_on_result nur dann rausgeben, wenn es entweder gar keine inneren
        # Lösungen gab oder wenn mindestens eine Lösung enthalten ist.
        if not one_on_one_filtered_out and (not any_inner_result or any_one_on_one_result):
            yield one_on_one_result

    def solve_combined(self, presettings=None):
        return [s for s in self.iterate_combined(presettings)]

    def iterate(self, presettings=None):
        """ Iterates over the outer solutions."""
        self._init(presettings)
        for solution in self.problem.getSolutionIter():
            self.metrics["n_all_solutions"] += 1
            yield solution

    def iterate_combined(self, presettings=None):
        """ Iterates over the combined outer and inner solutions.
        Returns a tuple containing the outer solution as first element,
        the combined solution as second element and the outer solution number
        as third element."""
        self._init(presettings)
        for n, outer_solution in enumerate(self.problem.getSolutionIter()):
            self.metrics["n_all_solutions"] += 1
            for complete_solution in self.getCombinedSolutionsIter(outer_solution):
                yield (outer_solution, complete_solution, n + 1)

    def validate_combined(self, outer_solution, inner_problem, inner_solution):
        # first validate inner solution standalone
        inner = inner_problem.validateStandalone(inner_solution)

        combined = False
        if inner:
            solution = dict(outer_solution)
            solution.update(inner_solution)

            if len(inner_problem.all_variables) != len(solution):
                return inner, False
            for v in inner_problem.all_variables:
                if v.getId() not in solution:
                    return inner, False

            for n, complete_solution in enumerate(inner_problem.solveInnerProblemIter(solution)):
                if n == 0:
                    combined = True
                else:
                    combined = False
                    break
        return inner, combined

    def getAllVariables(self):
        return self.all_variables

    def printSolutions(self, presettings=None, max_solutions=0):
        output_table = SolutionTable(self.all_variables)
        output_table.make_header()
        output_table.make_separator()
        n = 0
        for outer_solution, complete_solution, outer_solution_number in self.iterate_combined(presettings):
            n += 1
            output_table.make_line("", outer_solution_number, lambda var: complete_solution[var])
            if max_solutions and n >= max_solutions:
                print("%s solutions displayed. More solutions are available but not shown." % (n))
                break

    def getPersistentPager(self, collection, forward_solved_pages):
        if not self.persistent_pager:
            from cs.vp.variants.pagers import NestedObjectCollectionPager
            self.persistent_pager = NestedObjectCollectionPager(self, collection, forward_solved_pages)
        return self.persistent_pager

    def getSolverResultPager(self, collection, forward_solved_pages):
        if not self.solver_result_pager:
            from cs.vp.variants.pagers import NestedSolverResultPager
            self.solver_result_pager = NestedSolverResultPager(self, forward_solved_pages,
                                                               self.getPersistentPager(collection,
                                                                                       forward_solved_pages))
        return self.solver_result_pager


class NestedFilteredProblemSolver(NestedProblemSolver):
    def __init__(self, *args, **kwargs):
        self._visited = {}
        super(NestedFilteredProblemSolver, self).__init__(*args)
        self._hidden_props = kwargs.get("hidden_props", [])

    def _filter(self, prop_dict):
        if not self._hidden_props:
            return prop_dict
        else:
            return {prop: prop_dict[prop]
                    for prop in prop_dict.keys()
                    if prop not in self._hidden_props}

    def getFilteredSignature(self, prop_dict):
        return self.getSolutionSignature(self._filter(prop_dict))

    def getPersistentPager(self, collection, forward_solved_pages):
        if not self.persistent_pager:
            from cs.vp.variants.pagers import NestedObjectCollectionFilteredPager
            self.persistent_pager = NestedObjectCollectionFilteredPager(self, collection, forward_solved_pages)
        return self.persistent_pager

    def getSolverResultPager(self, collection, forward_solved_pages):
        if not self.solver_result_pager:
            from cs.vp.variants.pagers import NestedFilteredResultPager
            self.solver_result_pager = NestedFilteredResultPager(self, forward_solved_pages,
                                                                 self.getPersistentPager(collection, forward_solved_pages))
        return self.solver_result_pager


class SolutionTable(object):
    """ For debug and test purposes.
    Print a solution table to stdout. """

    def __init__(self, variables):
        self._variables = variables
        self._widths = {}
        for v in self._variables:
            self._widths[v.getId()] = 2 + max(
                len(literal)
                for literal in v.getValueNames() + [v.getName()])

    def make_line(self, prefix, nr, lookup, sep="|"):
        if prefix is None:
            return
        sys.stdout.write(prefix)
        sys.stdout.write("{0:{width}}{sep}".format(nr, width=4, sep=sep))
        for variable in self._variables:
            if nr == "No":  # header
                display_text = variable.getName()
            elif nr == "----":  # separator
                display_text = lookup(variable.getId())
            else:
                # get display text for value
                val_id = lookup(variable.getId())
                display_text = variable.getValueName(val_id)
            sys.stdout.write("{0:{width}}".format(display_text,
                                                  width=self._widths[variable.getId()]))
        sys.stdout.write("\n")

    def make_header(self, prefix=""):
        self.make_line(prefix, "No", lambda var: var)

    def make_separator(self, prefix=""):
        self.make_line(prefix, "----", lambda var: self._widths[var] * "-", sep="+")
