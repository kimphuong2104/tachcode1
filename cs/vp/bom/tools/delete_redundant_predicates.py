# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Delete BOM predicates for instantiated assemblies.

BOM predicates are only relevant for maxBOMs.
They are not needed for instatiated assemblies and can interefere with performace optimizations
in MBOM Manager.

It is therefore important to delete the redunant predicates.
"""

import argparse

from cdb import transactions
from cdb import sqlapi

from cs.vp import products


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


def run(product):
    query = """
        FROM {table}
        WHERE EXISTS (
            SELECT 42 FROM cdbvp_variant2part
            WHERE {table}.baugruppe=cdbvp_variant2part.teilenummer
                AND {table}.b_index=cdbvp_variant2part.t_index
                AND %s
        )
    """ % ("1=1" if product is None else "product_object_id='%s'" % product.cdb_object_id)

    with transactions.Transaction():
        for table in ["cdbvp_bom_predicate", "cdbvp_bom_term"]:
            sqlapi.SQLdelete(query.format(table=table))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Delete bom predicates for instantiated assemblies."
        )
    )

    parser.add_argument("-p", "--product", help="Attribute 'code' of the product")

    args = parser.parse_args()

    product = None
    if args.product:
        product = products.Product.ByKeys(code=args.product)

    run(product)
