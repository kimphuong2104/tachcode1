#!/usr/bin/env python
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import operator
import datetime
from cdb import sqlapi
from cdb import cdbtime
from cdb.objects import NULL
from cs.ec import EngineeringChange
from functools import reduce


def _get_closed_ecs_in_previous_year():
    ecs = EngineeringChange.KeywordQuery(template=0)

    # Find the ECs which where closed the previous year
    actual_ecs = []
    for ec in ecs:
        # Get last closing date
        condition = "cdb_ec_id='{id}' AND "\
                    "cdbprot_neustat='{status}'".format(id=ec.cdb_ec_id,
                                                        status="Completed")
        rs = sqlapi.RecordSet2(table="cdbecm_ec_prot",
                               columns=["cdb_ec_id", "cdbprot_neustat", "max(cdbprot_zeit) AS time"],
                               condition=condition,
                               addtl="GROUP BY cdb_ec_id, cdbprot_neustat")
        if rs:
            closing_date = rs[0]['time']
            if closing_date.year == datetime.datetime.today().year - 1:
                actual_ecs.append(ec)
    return actual_ecs


def ecm_compute_aver_part(qc):
    ecs = _get_closed_ecs_in_previous_year()

    if ecs:
        return reduce(operator.add, [len(ec.Items) for ec in ecs]) / float(len(ecs))
    else:
        return NULL


def ecm_compute_aver_doc(qc):
    ecs = _get_closed_ecs_in_previous_year()

    if ecs:
        return reduce(operator.add, [len(ec.Documents) for ec in ecs]) / float(len(ecs))
    else:
        return NULL


def ecm_compute_aver_process_time(qc):
    def _get_status_change_date(ec, status):
        condition = "cdb_ec_id='{id}' AND "\
                    "cdbprot_neustat='{status}'".format(id=ec.cdb_ec_id,
                                                        status=status)
        rs = sqlapi.RecordSet2(table="cdbecm_ec_prot",
                               columns=["cdb_ec_id", "cdbprot_neustat", "max(cdbprot_zeit) AS time"],
                               condition=condition,
                               addtl="GROUP BY cdb_ec_id, cdbprot_neustat")
        if not rs:
            return None
        status_change_date = rs[0]['time']
        return status_change_date

    def _get_process_time(ec):
        # Get last activation date
        activation_date = _get_status_change_date(ec, "In Progress")

        # Get last closing date
        closing_date = _get_status_change_date(ec, "Completed")

        if activation_date and closing_date:
            return (closing_date - activation_date).days
        else:
            return None

    ecs = EngineeringChange.KeywordQuery(template=0)
    process_times = []
    previous_year = datetime.datetime.today().year - 1
    for ec in ecs:
        if _get_status_change_date(ec, "Completed").year == previous_year:
            pt = _get_process_time(ec)
            if pt:
                process_times.append(pt)

    if process_times:
        return reduce(operator.add, process_times) / float(len(process_times))
    else:
        return NULL
