# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tool for pinpointing any possible cyclical structures in a BOM
"""



__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import argparse
import sys

from cdb import sqlapi

from cs.vp import items, utils


# Exported objects
__all__ = []


def get_cycles(*roots):
    """ Return a RecordSet of all the cycles in the bom structure

        :param positional arguments: instances of cs.vp.items.Item of which the cycles are
        to be checked

        :returns: a record set containing all the detected circular paths in the bom
    """
    bom_keys = ["teilenummer", "t_index", "baugruppe", "b_index"]
    keys = ", ".join(["{table}" + name for name in bom_keys])

    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        cycle_clause = "CYCLE teilenummer, t_index SET oracle_is_cycle TO 1 DEFAULT 0"
    else:
        cycle_clause = ""

    QUERYSTR = """
            WITH {recursive} flat_bom ({keys}, path, is_cycle)
            AS (
                SELECT {einzelteile_keys}, ',' {cat} cast(teilenummer as {chartype}) {cat} '@'
                    {cat} cast(t_index as {chartype}) {cat} ',', 0
                FROM einzelteile
                WHERE {root_condition}
                UNION ALL
                SELECT {einzelteile_keys},
                       flat_bom.path {cat} cast(einzelteile.teilenummer as {chartype}) {cat} '@'
                            {cat} cast(einzelteile.t_index as {chartype}) {cat} ',',
                       case when flat_bom.path like '%,'
                            {cat} cast(einzelteile.teilenummer as {chartype}) {cat} '@'
                            {cat} cast(einzelteile.t_index as {chartype}) {cat} ',%'
                            then 1 else 0 end
                FROM flat_bom
                JOIN einzelteile
                ON flat_bom.teilenummer=einzelteile.baugruppe AND
                    flat_bom.t_index=einzelteile.b_index
                WHERE flat_bom.is_cycle = 0
            )
            {cycle_clause}
            SELECT {keys}, path
            FROM flat_bom
            WHERE is_cycle = 1
        """

    query = QUERYSTR.format(
        recursive=utils.sql_recursive(),
        root_condition=make_root_condition(*roots),
        keys=keys.format(table=""),
        einzelteile_keys=keys.format(table="einzelteile."),
        flat_bom_keys=keys.format(table="flat_bom."),
        cat=sqlapi.SQLstrcat(),
        chartype="{type}(4000)".format(type=sqlapi.SQLchartype()),
        cycle_clause=cycle_clause,
        )

    result = sqlapi.RecordSet2(sql=query)

    return result


def make_root_condition(*roots):
    return " OR ".join([
        "(baugruppe='{number}' AND b_index='{index}')"
        .format(number=root.teilenummer, index=root.t_index)
        for root in roots
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Shows the cyclical BOM structures found within the given BOM."
            "path value shows the location of the cycle, starting from the root of the BOM"
        )
    )

    parser.add_argument(
        "teilenummer", nargs=1,
        help="teilenummer of the bom to be checked"
    )
    parser.add_argument(
        "t_index", nargs="?", default="",
        help="t_index of the bom to be checked"
    )

    args = parser.parse_args()
    bom = items.Item.ByKeys(teilenummer=args.teilenummer[0], t_index=args.t_index)
    if bom:
        cycles = get_cycles(bom)
        if cycles:
            print("\nThe following {} cycles were found in the BOM for {}@{}: \n\n"
                 .format(len(cycles), args.teilenummer[0], args.t_index))
            for entry in cycles:
                print(str(entry) + "\n")
        else:
            print("No cycles detected in this BOM")
        sys.exit()
    else:
        parser.print_help()
        parser.error("No corresponding BOM found, please check teilenummer and t_index were correct")
