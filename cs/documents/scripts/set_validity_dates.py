# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# pylint: disable=bad-continuation

import argparse
import logging
import sys
from builtins import input

from cdb import sqlapi
from cdb.imex import RowGenerator
from cs.documents import NEVER_VALID_DATE

LOG = logging.getLogger(__name__)


def set_validity_dates(
    draft_state_numbers, valid_state_numbers, obsolete_state_numbers
):
    def get_status_dates(r, released_state, with_document_status=False):
        in_status = (
            "{}, {}".format(released_state, r.z_status)
            if with_document_status
            else "200"
        )
        stmt = """
            select cdbprot_newstate, cdbprot_zeit
            from cdb_z_statiprot where z_nummer = '{}' and z_index = '{}' and cdbprot_newstate in ({})
            order by cdbprot_newstate, cdbprot_zeit
        """.format(
            sqlapi.quote(r.z_nummer), sqlapi.quote(r.z_index), in_status
        )
        valid_from = None
        valid_to = None
        for record in sqlapi.RecordSet2(sql=stmt):
            if not valid_from and record.cdbprot_newstate == released_state:
                valid_from = record.cdbprot_zeit if record.cdbprot_zeit else None
            if with_document_status and record.cdbprot_newstate == r.z_status:
                valid_to = record.cdbprot_zeit if record.cdbprot_zeit else None
        return (valid_from, valid_to)

    dates_set = 0
    generator = RowGenerator(
        "zeichnung",
        """
        select z_nummer, z_index, z_status, ce_valid_from, ce_valid_to from zeichnung
        order by z_nummer, z_index
        """,
    )
    for r in generator.get_data():
        if r.ce_valid_from or r.ce_valid_to:
            continue
        valid_from = None
        valid_to = None
        if r.z_status in draft_state_numbers:
            valid_from = NEVER_VALID_DATE
        elif r.z_status in valid_state_numbers:
            valid_from, valid_to = get_status_dates(r, 200, False)
        elif r.z_status in obsolete_state_numbers:
            valid_from, valid_to = get_status_dates(r, 200, True)
        else:
            doc_status = str(r.z_status) if r.z_status is not None else ""
            LOG.warning(
                "No status protocol entry found for document '%s/%s' and status %s.",
                r.z_nummer,
                r.z_index,
                doc_status,
            )
        if valid_from or valid_to:
            r.update(ce_valid_from=valid_from, ce_valid_to=valid_to)
            LOG.info(
                "Set validity for document '%s/%s': ce_valid_from=%s, ce_valid_to=%s",
                r.z_nummer,
                r.z_index,
                valid_from,
                valid_to,
            )
            dates_set = dates_set + 1

    return dates_set


def get_status_numbers(statetype, arg):
    try:
        state_numbers = [int(status) for status in arg.split(",")]
        print("Using {} for {}".format(state_numbers, statetype))
        return set(state_numbers)
    except:  # noqa E722 pylint: disable=bare-except
        print("Cannot convert {} to list of status numbers: {}".format(type, arg))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Utility to set ce_valid_from and ce_valid_to for documents from statusprotool"
    )
    parser.add_argument(
        "--draft_states",
        default="0, 100",
        dest="draft_states",
        help="Commaseperated list of release status numbers (default: 0, 100)",
        type=str,
    )
    parser.add_argument(
        "--valid_states",
        default="190, 200",
        dest="valid_states",
        help="Commaseperated list of release status numbers (default: 190, 200, 300)",
        type=str,
    )
    parser.add_argument(
        "--obsolete_states",
        default="170, 180",
        dest="obsolete_states",
        help="Commaseperated list of obsolete status numbers (default: 170, 180)",
        type=str,
    )
    args = parser.parse_args()

    draft_state_numbers = get_status_numbers("draft_states", args.draft_states)
    valid_state_numbers = get_status_numbers("valid_states", args.valid_states)
    obsolete_state_numbers = get_status_numbers("obsolete_states", args.obsolete_states)

    if (
        not draft_state_numbers
        and not valid_state_numbers
        and not obsolete_state_numbers
    ):
        print("State numbers have to be given")

    q = input(u"Are you sure to set all missing validity dates? (y/n)")
    if q == u"y":
        print("Set missing validity dates for documents ...")
        dates_set = set_validity_dates(
            draft_state_numbers, valid_state_numbers, obsolete_state_numbers
        )
        print("Set validity dates for {} documents.".format(dates_set))
    else:
        print("Aborted.")
