# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tool for pinpointing any possible cyclical structures in a Document Structure
"""



__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import argparse

from cdb import sqlapi

from cs import documents
from cs.vp import utils

# Exported objects
__all__ = []


def get_cycles(*roots):
    """ Return a RecordSet of all the cycles in the document reference structure

        :param positional arguments: instances of cs.documents.Document of which the cycles are
        to be checked

        :returns: a record set containing all the detected circular paths in the bom
    """
    doc_rel_keys = ["z_nummer2", "z_index2", "z_nummer", "z_index"]
    keys = ", ".join(["{table}" + name for name in doc_rel_keys])

    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        cycle_clause = "CYCLE z_nummer2, z_index2 SET oracle_is_cycle TO 1 DEFAULT 0"
    else:
        cycle_clause = ""

    QUERYSTR = """
            WITH {recursive} flat_bom ({keys}, path, is_cycle)
            AS (
                SELECT {einzelteile_keys}, ',' {cat} cast(z_nummer2 as {chartype}) {cat} '@'
                    {cat} cast(z_index2 as {chartype}) {cat} ',', 0
                FROM cdb_doc_rel
                WHERE {root_condition}
                UNION ALL
                SELECT {einzelteile_keys},
                       flat_bom.path {cat} cast(cdb_doc_rel.z_nummer2 as {chartype}) {cat} '@'
                            {cat} cast(cdb_doc_rel.z_index2 as {chartype}) {cat} ',',
                       case when flat_bom.path like '%,'
                            {cat} cast(cdb_doc_rel.z_nummer2 as {chartype}) {cat} '@'
                            {cat} cast(cdb_doc_rel.z_index2 as {chartype}) {cat} ',%'
                            then 1 else 0 end
                FROM flat_bom
                JOIN cdb_doc_rel
                ON flat_bom.z_nummer2=cdb_doc_rel.z_nummer AND
                    flat_bom.z_index2=cdb_doc_rel.z_index
                WHERE flat_bom.is_cycle = 0
            )
            {cycle_clause}
            SELECT {keys}, path
            FROM flat_bom
            WHERE is_cycle = 1
        """

    root_condition = " OR ".join([
        "(z_nummer='{number}' AND z_index='{index}')"
        .format(number=root.z_nummer, index=root.z_index)
        for root in roots
    ])

    query = QUERYSTR.format(
        recursive=utils.sql_recursive(),
        root_condition=root_condition,
        keys=keys.format(table=""),
        einzelteile_keys=keys.format(table="cdb_doc_rel."),
        flat_bom_keys=keys.format(table="flat_bom."),
        cat=sqlapi.SQLstrcat(),
        chartype="{type}(4000)".format(type=sqlapi.SQLchartype()),
        cycle_clause=cycle_clause,
        )

    result = sqlapi.RecordSet2(sql=query)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Shows the cyclical document structures found within the given document."
            "path value shows the location of the cycle, starting from the root document"
        )
    )

    parser.add_argument(
        "z_nummer", nargs=1,
        help="teilenummer of the bom to be checked"
    )
    parser.add_argument(
        "z_index", nargs="?", default="",
        help="z_index of the bom to be checked"
    )

    args = parser.parse_args()
    doc = documents.Document.ByKeys(z_nummer=args.z_nummer[0], z_index=args.z_index)
    if doc:
        cycles = get_cycles(doc)
        if cycles:
            print("\nThe following {} cycles were found in the Document structure for {}@{}: \n\n"\
                .format(len(cycles), args.z_nummer[0], args.z_index))
            for entry in cycles:
                print(str(entry) + "\n")
        else:
            print("No cycles detected in this Document structure")
    else:
        parser.print_help()
        parser.error("No corresponding Document found, please check z_nummer and z_index were correct")
