# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import argparse
import logging

from cdb import sqlapi, transactions
from cs.vp.items_documents import DocumentToPart

LOG = logging.getLogger(__name__)


def missing_doc2part_relations():
    stmt = """
                count(z_nummer) FROM zeichnung
                WHERE NOT EXISTS (
                    SELECT * from cdb_doc2part
                    WHERE
                        zeichnung.teilenummer=cdb_doc2part.teilenummer and
                        zeichnung.t_index=cdb_doc2part.t_index and
                        zeichnung.z_nummer=cdb_doc2part.z_nummer and
                        zeichnung.z_index=cdb_doc2part.z_index
                )
            """
    result = sqlapi.SQLselect(stmt)
    return sqlapi.SQLinteger(result, 0, 0)


def create_doc2part():
    doc2part_created = 0
    while missing_doc2part_relations() > 0:
        with transactions.Transaction():
            missing_doc2part_stmt = """
                SELECT z_nummer, z_index, teilenummer, t_index FROM zeichnung 
                WHERE NOT EXISTS (
                    SELECT * from cdb_doc2part
                    WHERE
                        zeichnung.teilenummer=cdb_doc2part.teilenummer and
                        zeichnung.t_index=cdb_doc2part.t_index and
                        zeichnung.z_nummer=cdb_doc2part.z_nummer and
                        zeichnung.z_index=cdb_doc2part.z_index
                )
            """
            rset = sqlapi.RecordSet2(sql=missing_doc2part_stmt, max_rows=10000)
            for row in rset:
                try:
                    # _Create is used for performance reasons
                    DocumentToPart._Create(  # pylint: disable=W0212
                        z_nummer=row.z_nummer, z_index=row.z_index,
                        teilenummer=row.teilenummer, t_index=row.t_index,
                        kind="strong"
                    )
                    LOG.info(
                        "Created strong doc2part relation for '%s/%s' -> '%s/%s'.",
                        row.z_nummer, row.z_index, row.teilenummer, row.t_index
                    )
                    doc2part_created = doc2part_created + 1
                except Exception:
                    LOG.exception(
                        "Error creating doc2part relation for '%s/%s' -> '%s/%s'.",
                        row.z_nummer, row.z_index, row.teilenummer, row.t_index
                    )
                    return doc2part_created
    return doc2part_created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Utility to create cdb_doc2part for all existing documents with teilenummer set.'
    )
    args = parser.parse_args()

    q = input('Are you sure to create all missing cdb_doc2part objects? (y/n)')
    if q == 'y':
        print("Creating missing doc2part relations ...")
        print("Missing doc2part relations: %d" % missing_doc2part_relations())
        doc2part_created = create_doc2part()
        print("Created {} doc2part relations.".format(doc2part_created))
        missing_doc2part_relations = missing_doc2part_relations()
        if missing_doc2part_relations > 0:
            print("Still missing doc2part relations: %d" % missing_doc2part_relations)
    else:
        print ("Aborted.")
