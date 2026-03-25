#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module VPMSolvers

This is the documentation for the VPMSolvers module.
"""


from cs.vp.variants.solvers import ProblemVariable
from cs.vp.variants.solvers import ProblemConstraint
from cs.vp.variants.solvers import BasicProblemSolver
from cs.vp.variants.solvers import NestedProblemSolver
from cs.vp.variants.solvers import NestedFilteredProblemSolver


class VPMVariable(ProblemVariable):
    """ Variable implementation for VPM Properties """

    def __init__(self, prop):
        values = []
        value_texts = []
        if prop.GeneratorRelevantEnumValues:
            value_texts = [value.ValueText[''] for value in prop.GeneratorRelevantEnumValues]
            values = prop.GeneratorRelevantEnumValues.value

        super(VPMVariable, self).__init__(prop.id,
                                          prop.Name[''],
                                          values,
                                          value_texts)
        self._prop = prop

    def getProperty(self):
        return self._prop


class VPMConstraint(ProblemConstraint):
    """
    Constraint implementation for VPM constraints based on
    cs.vp.variants.constraints.Constraint.
    """

    def __init__(self, constraint):
        used_variables = set([p.id for p in constraint.properties_used()])
        super(VPMConstraint, self).__init__(used_variables)
        self._constraint = constraint

    def compute(self):
        return self._constraint.compute(self.variables_used())


class VPMGeneratedEnumValueConstraint(ProblemConstraint):
    """ Constraint implementation for in memory generated VPM constraints
    based on property dependencies (cs.vp.variants.properties.PropertyDependency)
    and it's generated enum values.
    This constraint type is used to set all usages of an enum value
    within generated enum values equal.
    """

    def __init__(self, cdbvp_enum_def, values):
        used_variables = set([cdbvp_enum_def.Property.id] + [x.Property.id for x in values])
        super(VPMGeneratedEnumValueConstraint, self).__init__(used_variables)
        self._enum_def = cdbvp_enum_def
        self._values = values

    def compute(self):
        return self._enum_def.compute_constraint(self.variables_used(), self._values)


# class VPMGeneratedSubpropertyConstraint(ProblemConstraint):
#     """ Constraint implementation for in memory generated VPM constraints
#         based on property dependencies.
#     """
#
#     def __init__(self, properties):
#         self._properties = properties
#         used_variables = set([prop.id for prop in properties])
#         super(VPMGeneratedSubpropertyConstraint, self).__init__(used_variables)
#
#     def compute(self):
#         def the_compute_function(*args):
#             solution = dict(zip(self.variables_used(), args))
#
#             result = all([
#                 (solution[prop.parent_id] or not solution[prop.id])
#                 for prop in self._properties if prop.parent_id is not None
#             ])
#             return result
#
#         return the_compute_function


class VPMSubproductConstraint(ProblemConstraint):
    def __init__(self, parent_product, sub_product, problem_props):
        from cs.vp.variants.properties import Property2SubProductProperty, EnumDefinition

        self._parent_product = parent_product
        self._sub_product = sub_product

        available_prop_ids = [p.id for p in problem_props]
        prop_mappings = Property2SubProductProperty.KeywordQuery(product_object_id=parent_product.cdb_object_id,
                                                                 subproduct_object_id=sub_product.cdb_object_id)
        prop_mappings = [m for m in prop_mappings if m.property_id in available_prop_ids]
        used_variables = set([m.property_id for m in prop_mappings])
        super(VPMSubproductConstraint, self).__init__(used_variables)

        mapping_dict = dict([(m.property_id, m.subproduct_property_id) for m in prop_mappings])
        self.valid_subproduct_variants = set()
        for v in sub_product.Variants:
            variant_dict = v.get_property_values()
            value_list = []
            for var in self.variables_used():
                value_list.append(variant_dict[mapping_dict[var]])
            self.valid_subproduct_variants.add(tuple(value_list))
        # load enum values for each subproduct property
        self._subproduct_enum_values = []
        for var in self.variables_used():
            prop_id = mapping_dict[var]
            enum_value_ids = EnumDefinition.KeywordQuery(product_object_id=sub_product.cdb_object_id,
                                                         id=prop_id).value
            self._subproduct_enum_values.append(enum_value_ids)

    def compute(self):
        def the_compute_function(*args):
            # The mapped subproduct properties may have less enum values than
            # the properties of the parent product. If an enum value contained in args
            # is not defined for the subproduct, this property is ignored on comparision.
            ignore_positions = []
            for i, enum_value in enumerate(args):
                if enum_value not in self._subproduct_enum_values[i]:
                    ignore_positions.append(i)
            if ignore_positions:
                for v in self.valid_subproduct_variants:
                    match = True
                    for i, enum_value in enumerate(args):
                        if v[i] != enum_value and i not in ignore_positions:
                            match = False
                            break
                    if match:
                        return True
                return False
            else:
                return tuple(args) in self.valid_subproduct_variants

        return the_compute_function


class BasicVPMSolver(BasicProblemSolver):
    def __init__(self, product, problem_props=[], solution_props=[]):
        self._product = product
        self._problem_props = problem_props
        self._solution_props = solution_props

        variables = [VPMVariable(p) for p in problem_props]
        constraints = [VPMConstraint(c) for c in product.AllConstraints]
        constraints += computeConstraintsForGeneratedEnums(problem_props)
        constraints += computeConstraintsForSubproducts(self._product, problem_props)
#        constraints.append(VPMGeneratedSubpropertyConstraint(problem_props))

        solution_variables = []
        if solution_props:
            solution_variables = [VPMVariable(p) for p in solution_props]
        super(BasicVPMSolver, self).__init__(variables, constraints, solution_variables)


class NestedVPMSolver(NestedProblemSolver):
    def __init__(self, product, outer_props, inner_prop_sets):
        self._product = product
        self._outer_props = outer_props
        self._view_ids = []

        constraints = [VPMConstraint(c) for c in product.AllConstraints]

        all_props = list(outer_props)
        for prop_set in inner_prop_sets:
            all_props += prop_set
        constraints += computeConstraintsForGeneratedEnums(all_props)
        constraints += computeConstraintsForSubproducts(self._product, all_props)

        outer_variables = [VPMVariable(p) for p in outer_props]
        inner_variable_sets = []
        for prop_set in inner_prop_sets:
            inner_variable_sets.append([VPMVariable(p) for p in prop_set])
            self._view_ids.append(prop_set[0].view_id)

        super(NestedVPMSolver, self).__init__(outer_variables, inner_variable_sets, constraints)

    def getViews(self):
        return self._view_ids

    def getInnerProblem(self, view_id):
        result = None
        index = -1
        try:
            index = self._view_ids.index(view_id)
            result = self.inner_problems[index]
        except ValueError:
            pass
        return result, index


class NestedVPMFilteredSolver(NestedFilteredProblemSolver, NestedVPMSolver):
    def __init__(self, product, outer_props, inner_prop_sets, hidden_props):
        super(NestedVPMFilteredSolver, self).__init__(product,
                                                      outer_props,
                                                      inner_prop_sets,
                                                      hidden_props=hidden_props)
        self._hidden_props = hidden_props


def computeConstraintsForGeneratedEnums(properties):
    """
    Additionally computed constraints for dependencies
    between generated enum values
    """

    input_props_by_id = {}
    for prop in properties:
        input_props_by_id[prop.id] = prop

    value_combinations = []
    occurences = {}
    source_props = set()
    for p in properties:
        has_generated_enum_values = False
        for v in p.GeneratedValidEnumValues:
            values = v.PropertyValues.rated_property_value
            if not values:
                continue
            has_generated_enum_values = True
            values.sort()
            if values not in value_combinations:
                value_combinations.append(values)
            # remember occurence (generated enum value) of
            # this combination
            key = str(values)
            if key not in occurences:
                occurences[key] = [v]
            else:
                occurences[key].append(v)

        if has_generated_enum_values:
            for prop_id in p.PropertyDependencies.property_id2:
                if prop_id in input_props_by_id:
                    source_props.add(input_props_by_id[prop_id])

    for prop in source_props:
        for v in prop.EnumValues:
            values = [v.value]
            if values not in value_combinations:
                value_combinations.append(values)
            # remember occurence of this value
            key = str(values)
            if key not in occurences:
                occurences[key] = [v]
            else:
                occurences[key].append(v)

    # Build result dictionary.
    # Keys are the output property values to build a constraint on.
    # The values are lists of property values that satisfy the output condition.
    result = {}
    for v in value_combinations:
        for v2 in value_combinations:
            if set(v) < set(v2):
                for occurence in occurences[str(v)]:
                    if occurence not in result:
                        result[occurence] = []
                    for o2 in occurences[str(v2)]:
                        result[occurence].append(o2)
            elif set(v) == set(v2):
                # all occurences must be equal
                if len(occurences[str(v)]) > 1:
                    for occurence in occurences[str(v)]:
                        if occurence not in result:
                            result[occurence] = []
                        for o2 in occurences[str(v)]:
                            if occurence != o2:
                                result[occurence].append(o2)
    # Logging for debug purposes
    # for k,v in result.items():
    #    exprs = []
    #    for x in v:
    #        exprs.append(x.Property.name + "=" + x.value_txt_de + "/" + str(x.value))
    #    msg = k.Property.name + "=" + k.value_txt_de + "/" + str(k.value) + " WENN %s " % (" OR ".join(exprs))
    #    misc.cdblogv(misc.kLogErr, 0, msg)
    # ----------------------------------
    constraints = []
    for k, v in result.items():
        constraints.append(VPMGeneratedEnumValueConstraint(k, v))
    return constraints


def computeConstraintsForSubproducts(product, problem_props):
    constraints = []
    for subproduct_ref in product.SubproductReferences:
        if subproduct_ref.SubProduct:
            constraints.append(VPMSubproductConstraint(product, subproduct_ref.SubProduct, problem_props))
    return constraints
