# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module generate_string_predicates

Convert the term-based bom predicates to string-based bom predicates.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Some imports
import argparse
import collections
import operator

from cdb import sqlapi
from cdb import objects
from cdb import cdbuuid
from cdb import constants
from cdb import transactions
from cdb.objects import operations

from cs.vp import bom
from cs.vp import items
from cs.vp import products
from cs.vp.variants import bomlinks


def make_predicate_condition(predicate):
    def __isnumber(n):
        try:
            float(n)
            return True
        except (ValueError, TypeError):
            return False

    if isinstance(predicate, bomlinks.BOM_Term_Predicate):
        conditions = []
        for term in predicate.Terms:
            if term.Property:
                if term.operator == '\N{BALLOT BOX WITH CHECK}':
                    conditions.append("%s" % term.Property.erp_code)
                elif term.operator == '\N{BALLOT BOX}':
                    conditions.append("not %s" % term.Property.erp_code)
                elif term.PropertyValue:
                    operator = "==" if term.operator == "=" else term.operator

                    value = term.PropertyValue.name
                    if not __isnumber(value):
                        value = '"%s"' % value

                    conditions.append("(%s %s %s)" % (
                        term.Property.erp_code,
                        operator,
                        value
                    ))
        return " and ".join(conditions)


def make_component_conditions(comp, product_object_id):
    conditions = []
    for predicate in comp.VPMPredicates.KeywordQuery(product_object_id=product_object_id):
        if isinstance(predicate, bomlinks.BOM_Term_Predicate):
            condition = make_predicate_condition(predicate)
            if condition:
                conditions.append("(%s)" % condition)
    return conditions


def generate_string_predicates(item, product_object_id):
    for comp in item.Components:
        if comp.VPMPredicates:
            log("Migrating (%s, %s, %s)" % (comp.baugruppe, comp.b_index, comp.position))

            conditions = make_component_conditions(comp, product_object_id)
            for predicate in comp.VPMPredicates.KeywordQuery(product_object_id=product_object_id):
                if isinstance(predicate, bomlinks.BOM_Term_Predicate):
                    operations.operation(
                        constants.kOperationDelete,
                        predicate
                    )

            # since the expression must be shorter than 1000 chars
            # we build chunks smaller than 1000 chars
            while len(conditions) > 0:
                for i in range(1, len(conditions) + 1):
                    if len(" or ".join(conditions[:i + 1])) >= 1000:
                        break
                condition = " or ".join(conditions[:i])  # pylint: disable=undefined-loop-variable
                conditions = conditions[i:]  # pylint: disable=undefined-loop-variable

                log("\t%s" % condition)
                operations.operation(
                    constants.kOperationNew,
                    bomlinks.BOM_String_Predicate,
                    baugruppe=comp.baugruppe,
                    b_index=comp.b_index,
                    teilenummer=comp.teilenummer,
                    variante=comp.variante,
                    position=comp.position,
                    product_object_id=product_object_id,
                    predicate_id=bomlinks.BOM_Predicate.newID(),
                    expression=condition
                )
        if comp.Item:
            generate_string_predicates(comp.Item, product_object_id)


verbose = False


def log(msg):
    if verbose:
        print(msg)


# Guard importing as main module
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Convert the term-based bom predicates to string-based bom predicates."
        )
    )

    parser.add_argument("product", help="Attribute 'code' of the product")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    verbose = args.verbose

    product = products.Product.ByKeys(code=args.product)
    if product is not None:
        with transactions.Transaction():
            for maxbom in product.MaxBoms:
                log("Migrating predicates for maxbom %s" % maxbom.GetDescription())
                generate_string_predicates(maxbom, product.cdb_object_id)
    else:
        log("Cannot find product")
