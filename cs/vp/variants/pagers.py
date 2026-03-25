#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module Pagers

This is the documentation for the Pagers module.
"""

from collections import namedtuple

from cdb.objects import iterate, NULL
from cs.vp.variants.varianttableadapters import SyncStatus
from cs.vp.variants.varianttableadapters import MappingStatus

from cs.vp.variants import ViewVariant
from cs.vp.variants import VariantMapping

VariantInfo = namedtuple("VariantInfo",
                         "variant_object state generator_infos inner_variant_infos")


class Pager(object):
    def __init__(self, solver, forward_solved_pages):
        self._solver = solver
        self._solve_ahead = forward_solved_pages
        self.setup()
        self._resetted = False

    def setup(self, presettings=None, addtl_args=None, page_size=50):
        self._solved = []
        self._all = {}
        self._end = False
        self._presettings = presettings if presettings is not None else {}
        self._addtl_args = addtl_args if addtl_args is not None else {}
        self._iterator = self.get_iterator(self._presettings, page_size)

    def reset(self):
        self._solved = []
        self._all = {}
        self._end = False
        self._iterator = self.get_iterator(self._presettings, page_size=50)
        self._resetted = True

    def nextpage(self, presettings, addtl_args, page_size, start_row):
        if presettings != self._presettings or addtl_args != self._addtl_args:
            self.setup(presettings, addtl_args, page_size)
            self._resetted = True
        else:
            self._resetted = False

        if self._solve_ahead:
            solve_to_row = start_row + (page_size * (self._solve_ahead + 1))
        else:
            solve_to_row = start_row + page_size

        while solve_to_row > len(self._solved) and not self._end:
            try:
                sol = self._fetch()
                if not self._visit(sol):
                    self._solved.append(sol)
            except StopIteration:
                self._end = True
        return self._solved[start_row:start_row + page_size]

    def _fetch(self):
        result = None
        match = False
        while not match:
            elem = next(self._iterator)
            match, result = self.process(elem, self._presettings, self._addtl_args)
        return result

    def _visit(self, solution):
        return False

    def end(self):
        return self._end

    def resetted(self):
        return self._resetted

    def addToCache(self, key, result, match):
        if key:
            self._all[key] = (result, match)

    def find(self, key):
        return self._all.get(key, None)

    def solved(self):
        return len(self._solved)

    def get_iterator(self, presettings, page_size):
        """ To be implemented by subclasses """
        pass

    def process(self, elem, presettings, addtl_args):
        """ To be implemented by subclasses.
        Matches the element against presettings and addtl_args.
        Return a tuple with three elements. The first element is
        the boolean match result. The second element is the
        result, which will be returned by the pager.
        This must be tuple with two elements:  property key/value dict, VariantInfo tuple
        """
        return False, ({}, VariantInfo(None, None, {}, []))

    def getMetrics(self):
        # Die genaue Anzahl der Varianten ist unbekannt,
        # solange nicht alle möglichen Varianten durch den Solver gelöst wurden.
        # iTotalRecords wird vom DataTable für das Paging ausgewertet.
        # Es wird daher immer mehrere Pages im vorraus gesolved, damit der Next-Button
        # verfügbar bleibt.
        return {"iTotalRecords": self.solved(),
                "all_solved": 1 if self.end() else 0,
                "pager_resetted": 1 if self.resetted() else 0}


class SolverResultPager(Pager):

    def __init__(self, solver, forward_solved_pages, persistent_pager=None):
        super(SolverResultPager, self).__init__(solver, forward_solved_pages)
        self._persistent_pager = persistent_pager

    def get_iterator(self, presettings, page_size):
        return self._solver.iterate(presettings)

    def process(self, solution, presettings, addtl_args):
        # Die presettings werden schon mit in den solver gepackt, so dass
        # diese hier nicht mehr geprüft werden müssen.
        match = False
        state = None
        checksum, _signature = self._solver.getSolutionChecksum(solution)
        persistent_result = self._persistent_pager.find(checksum)
        if not persistent_result:  # or persistent_result[1].state not in [SyncStatus.ok.name, SyncStatus.manual.name]:
            # All variants from the solver, that are not contained within
            # the persistent variants with state ok or manual, are of state 'new'.
            state = SyncStatus.new.name
            state_search = addtl_args.get("state", None)
            match = (not state_search or (state_search and state == state_search))
        pager_result = (solution, VariantInfo(None, state, {}, None))
        return match, pager_result


class FilteredPager(Pager):
    def setup(self, presettings=None, addtl_args=None, page_size=50):
        self._solver._visited.clear()
        super(FilteredPager, self).setup(presettings, addtl_args, page_size)

    def reset(self):
        self._solver._visited.clear()
        super(FilteredPager, self).reset()

    def _visit(self, solution):
        signature = self._solver.getFilteredSignature(solution[0])
        occurences = self._solver._visited.get(signature, 0)

        self._solver._visited[signature] = occurences + 1
        return occurences


def _build_inner_variant_infos(complete_solution, inner_problems, pager, mappings=None):
    if mappings is None:
        mappings = {}

    inner_variant_infos = []
    mapping_infos = {}
    for i, inner_problem in enumerate(inner_problems):
        checksum, signature = inner_problem.getSolutionChecksum(complete_solution)
        if signature:
            # lookup in mappings and set mapping_state attribute.
            mapping_infos["mapping_state_%s" % i] = mappings.get(signature, MappingStatus.new.name)

            cached = pager.find(checksum)
            if cached:
                inner_variant_infos.append(cached[0][1])
            else:
                # DB Lookup for inner variant with signature
                product_object_id = inner_problem.inner_variables[0].getProperty().product_object_id
                obj = ViewVariant.BySignature(product_object_id, signature)
                if obj:
                    if obj.solver_status in (NULL, SyncStatus.manual.value):
                        state = SyncStatus.manual.name
                    else:
                        state = SyncStatus.ok.name
                else:
                    state = SyncStatus.new.name
                variant_info = VariantInfo(obj, state, {}, None)
                inner_variant_infos.append(variant_info)
                # Add to cache. The same inner variant can occur multiple times for
                # different outer variants
                inner_solution = inner_problem.extract(complete_solution)
                pager.addToCache(checksum, (inner_solution, variant_info), True)
        else:
            # add empty dummy for missing inner variant
            inner_variant_infos.append(VariantInfo(None, "", None, None))
            mapping_infos["mapping_state_%s" % i] = ""
    return inner_variant_infos, mapping_infos


class NestedSolverResultPager(SolverResultPager):
    def iterate(self, presettings):
        # extract presettings of inner problems
        inner_presettings = self._solver.extractPresettings(self._presettings)

        for n, outer_solution in enumerate(self._solver.iterate(presettings)):
            # pre process outer solution to avoid useless solving of inner variants
            match, _result = super(NestedSolverResultPager,
                                   self).process(outer_solution,
                                                 self._presettings,
                                                 self._addtl_args)
            if match:
                # calculate inner solutions
                for complete_solution in self._solver.getCombinedSolutionsIter(outer_solution, inner_presettings):
                    yield outer_solution, complete_solution, n + 1

    def get_iterator(self, presettings, page_size):
        return self.iterate(presettings)

    def process(self, elem, presettings, addtl_args):
        match, result = super(NestedSolverResultPager, self).process(elem[0], presettings, addtl_args)

        addtl_info = {"outer_solution_number": elem[2]}
        inner_variant_infos = []
        if match:
            inner_variant_infos, mapping_infos = _build_inner_variant_infos(elem[1], self._solver.inner_problems, self)
            addtl_info.update(mapping_infos)

        pager_result = (elem[1], VariantInfo(None, result[1].state, addtl_info, inner_variant_infos))
        return match, pager_result


def _build_simple_inner_variant_infos(complete_solution, inner_problems):
    inner_variant_infos = [VariantInfo(None, "", None, None)] * len(inner_problems)
    mapping_infos = {}

    return inner_variant_infos, mapping_infos


class NestedFilteredResultPager(NestedSolverResultPager, FilteredPager):
    def process(self, elem, presettings, addtl_args):
        # HINT: Not calling the direct parent class is a feature, not an accident here!
        match, result = super(NestedSolverResultPager, self).process(elem[0], presettings, addtl_args)

        addtl_info = {"outer_solution_number": elem[2]}
        inner_variant_infos = []
        if match:
            inner_variant_infos, mapping_infos = _build_simple_inner_variant_infos(elem[1], self._solver.inner_problems)
            addtl_info.update(mapping_infos)

        pager_result = (elem[1], VariantInfo(None, result[1].state, addtl_info, inner_variant_infos))
        return match, pager_result


class ObjectCollectionPager(Pager):
    def __init__(self, solver, collection, forward_solved_pages):
        self._collection = collection
        super(ObjectCollectionPager, self).__init__(solver,
                                                    forward_solved_pages)

    def iterate(self, page_size):
        for obj in iterate(self._collection, page_size):
            solution = obj.get_property_values()
            if solution:
                yield obj, solution

    def get_iterator(self, presettings, page_size):
        return self.iterate(page_size)

    def process(self, elem, presettings, addtl_args):
        state = None
        match = False
        variant_obj = elem[0]
        solution_dict = elem[1]
        if variant_obj.match(presettings):
            state_search = addtl_args.get("state", None)
            if variant_obj.solver_status in (NULL, SyncStatus.manual.value):
                state = SyncStatus.manual
            elif self._solver.validate(solution_dict):
                state = SyncStatus.ok if self._solver.containsAllVariables(solution_dict) else SyncStatus.incomplete
            else:
                state = SyncStatus.invalid

            match = (not state_search or (state_search and state.name == state_search))
        pager_result = (solution_dict, VariantInfo(variant_obj, state.name if state else None, {}, None))
        checksum, _signature = self._solver.getSolutionChecksum(solution_dict)
        self.addToCache(checksum, pager_result, match)
        return match, pager_result


class NestedObjectCollectionPager(ObjectCollectionPager):
    def process_inner(self, inner_problem, variant_obj, inner_solution,
                      outer_solution, presettings, addtl_args, manual_mapping):
        checksum, _signature = inner_problem.getSolutionChecksum(inner_solution)

        inner_presettings = self._solver.extractPresettingsForInnerProblem(
            presettings, inner_problem)

        cached = self.find(checksum)
        if cached:
            if manual_mapping:
                mapping_state = MappingStatus.manual.name
            else:
                inner, mapping = self._solver.validate_combined(outer_solution, inner_problem, inner_solution)
                mapping_state = MappingStatus.ok.name if mapping else MappingStatus.invalid.name
            return cached[1], cached[0], mapping_state
        else:
            state = SyncStatus.invalid.name
            match = False
            mapping_state = MappingStatus.invalid.name
            if variant_obj.match(inner_presettings):
                state_search = None  # addtl_args.get("state", None)
                if variant_obj.solver_status in (NULL, SyncStatus.manual.value):
                    state = SyncStatus.manual.name
                    mapping_state = MappingStatus.manual.name
                else:
                    inner, mapping = self._solver.validate_combined(outer_solution, inner_problem, inner_solution)
                    state = SyncStatus.ok.name if inner else SyncStatus.invalid.name
                    if manual_mapping:
                        mapping_state = MappingStatus.manual.name
                    else:
                        mapping_state = MappingStatus.ok.name if mapping else MappingStatus.invalid.name
                match = (not state_search or (state_search and state == state_search))

            result = (inner_solution, VariantInfo(variant_obj, state, {}, None))
            self.addToCache(checksum, result, match)
            return match, result, mapping_state

    def iterate(self, page_size):
        # view ids of solved inner problems
        view_ids = self._solver.getViews()

        # extract presettings of inner problems
        inner_presettings = self._solver.extractPresettings(self._presettings)
        outer_presettings = {
            id: value
            for id, value in self._presettings.items()
            if all((id not in ip for ip in inner_presettings.values()))
        }

        for n, obj in enumerate(iterate(self._collection, page_size)):
            outer_solution = obj.get_property_values()
            if not outer_solution:
                continue

            # pre process outer solution to avoid useless solving of inner variants
            match, _result = super(NestedObjectCollectionPager, self)\
                .process(
                    (obj, outer_solution),
                    outer_presettings,
                    self._addtl_args
                )

            if match:
                # DB lookup of persistently mapped variants.
                # Caches found mappings and processed inner variants for further processing.
                mappings = {}
                invalid_persistent_inner_solutions = {}
                for mapping in obj.VariantMappings.Query(VariantMapping.view_id.one_of(*view_ids)):
                    inner_variant = mapping.ViewVariant
                    if inner_variant:
                        inner_problem, inner_problem_index = self._solver.getInnerProblem(inner_variant.view_id)
                        if inner_problem:
                            inner_solution = inner_variant.get_property_values()
                            if inner_solution:
                                inner_match, inner_result, mapping_state = self.process_inner(inner_problem,
                                                                                              inner_variant,
                                                                                              inner_solution,
                                                                                              outer_solution,
                                                                                              self._presettings,
                                                                                              self._addtl_args,
                                                                                              mapping.manual)
                                mappings[inner_variant.signature] = mapping_state
                                if inner_match:
                                    # Add inner solution to invalid_persistent_inner_solutions variable,
                                    # if inner variant or mapping is invalid, because
                                    # these rows will not returned by the solver.
                                    # If mapping or inner variant is manual, the real solver state must
                                    # be determined.
                                    inner_state = inner_result[1].state
                                    if inner_state == SyncStatus.manual.name or mapping_state == MappingStatus.manual.name:
                                        # resolve real solver state for mapping and inner variant (valid or invalid)
                                        inner_valid, mapping_valid = self._solver.validate_combined(outer_solution,
                                                                                                    inner_problem,
                                                                                                    inner_solution)
                                        inner_state = SyncStatus.ok.name if inner_valid else SyncStatus.invalid.name
                                        mapping_state = MappingStatus.ok.name if mapping_valid else MappingStatus.invalid.name
                                    if inner_state == SyncStatus.invalid.name or mapping_state == MappingStatus.invalid.name:
                                        if inner_problem_index not in invalid_persistent_inner_solutions:
                                            invalid_persistent_inner_solutions[inner_problem_index] = []
                                        invalid_persistent_inner_solutions[inner_problem_index].append(inner_solution)

                # calculate inner solutions
                for solution in self._solver.getCombinedSolutionsIter(outer_solution,
                                                                      inner_presettings,
                                                                      invalid_persistent_inner_solutions):
                    yield obj, outer_solution, solution, n + 1, mappings

    def process(self, elem, presettings, addtl_args):
        # outer solution is already pre processed (see iterate) and already in the cache.
        checksum, _signature = self._solver.getSolutionChecksum(elem[1])
        result, match = self.find(checksum)

        addtl_info = {"outer_solution_number": elem[3]}
        inner_variant_infos = []
        if match:
            inner_variant_infos, mapping_infos = _build_inner_variant_infos(elem[2],
                                                                            self._solver.inner_problems,
                                                                            self,
                                                                            elem[4])
            addtl_info.update(mapping_infos)

        pager_result = (elem[2], VariantInfo(elem[0], result[1].state, addtl_info, inner_variant_infos))
        return match, pager_result


class NestedObjectCollectionFilteredPager(ObjectCollectionPager, FilteredPager):
    def iterate(self, page_size):
        # extract presettings of inner problems
        inner_presettings = self._solver.extractPresettings(self._presettings)

        for n, obj in enumerate(iterate(self._collection, page_size)):
            outer_solution = obj.get_property_values()
            if not outer_solution:
                continue

            # pre process outer solution to avoid useless solving of inner variants
            match, _result = super(NestedObjectCollectionFilteredPager, self).process((obj, outer_solution), self._presettings, self._addtl_args)

            if match:
                mappings = {}
                invalid_persistent_inner_solutions = {}

                # calculate inner solutions
                for solution in self._solver.getCombinedSolutionsIter(outer_solution,
                                                                      inner_presettings,
                                                                      invalid_persistent_inner_solutions):
                    yield obj, outer_solution, solution, n + 1, mappings

    def process(self, elem, presettings, addtl_args):
        # outer solution is already pre processed (see iterate) and already in the cache.
        checksum, _signature = self._solver.getSolutionChecksum(elem[1])
        result, match = self.find(checksum)

        addtl_info = {"outer_solution_number": elem[3]}
        inner_variant_infos = []
        if match:
            inner_variant_infos, mapping_infos = _build_simple_inner_variant_infos(elem[2], self._solver.inner_problems)
            addtl_info.update(mapping_infos)

        pager_result = (elem[2], VariantInfo(elem[0], result[1].state, addtl_info, inner_variant_infos))
        return match, pager_result


class CombinedPager(Pager):
    def __init__(self, solver, collection, forward_solved_pages):
        self._persistent_pager = solver.getPersistentPager(collection, forward_solved_pages)
        self._solver_pager = solver.getSolverResultPager(collection, forward_solved_pages)
        super(CombinedPager, self).__init__(solver, forward_solved_pages)

    def setup(self, presettings=None, addtl_args=None, page_size=50):
        self._presettings = presettings if presettings is not None else {}
        self._addtl_args = addtl_args if addtl_args is not None else {}
        self._persistent_pager.setup(self._presettings, self._addtl_args, page_size)
        self._solver_pager.setup(self._presettings, self._addtl_args, page_size)

        state_search = self._addtl_args.get("state", None)
        self._solver_pager_is_active = not state_search or state_search == SyncStatus.new.name

    def reset(self):
        self._persistent_pager.reset()
        self._solver_pager.reset()
        self._resetted = True

    def nextpage(self, presettings, addtl_args, page_size, start_row):
        if presettings != self._presettings or addtl_args != self._addtl_args:
            self.setup(presettings, addtl_args, page_size)
            self._resetted = True
        else:
            self._resetted = False

        result = self._persistent_pager.nextpage(presettings, addtl_args, page_size, start_row)
        if self._persistent_pager.end() and self._solver_pager_is_active:
            # get variants from solver
            new_start_row = start_row - self._persistent_pager.solved() + len(result)
            new_page_size = page_size - len(result)
            self._solver_pager.nextpage(presettings, addtl_args, page_size, new_start_row)
            if new_page_size > 0:
                result += self._solver_pager.nextpage(presettings, addtl_args, new_page_size, new_start_row)
        return result

    def _fetch(self):
        pass

    def find(self, key):
        return None

    def end(self):
        return self._solver_pager.end() if self._solver_pager_is_active else self._persistent_pager.end()

    def solved(self):
        return self._persistent_pager.solved() + self._solver_pager.solved()
