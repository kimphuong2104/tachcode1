#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Module Services

Services to compute and aggregate quality characteristics
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import sched
import datetime
import time

from cdb import ue
from cdb import misc
from cdb import fls
from cdb.objects import ByID

from cs.metrics import computationrules as ComputationRules

from cdb.platform.mom.entities import CDBClassDef

# Number of seconds in a day
_DAY_SECONDS = 86400

# How often we should compute the QCs (value in days)
_UPDATE_CLOCK = 1

# Schedulers
scheduler = sched.scheduler(time.time, time.sleep)

update_clocks = None


def resolve(name):
    global update_clocks

    if update_clocks is None:
        update_clocks = dict([(uc.name_de, uc.position) for uc in ComputationRules.UpdateClock.Query()])

    return update_clocks[name]


def seconds_to_midnight():
    """Returns the number of seconds between the current time and midnight of the next day."""
    lt = time.localtime()
    return _DAY_SECONDS - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)


def get_next_computation(clock, start_date=None):
    """
    Returns the date of the next computation, for a quality characteristic being computed today.

    :param clock: the clock (i.e. how often) of the computation
    :type clock: the UUID of an object of the class cdbqc_update_clocks

    :raise: cdbqc_invalid_update_clock
    """
    if not start_date:
        today = datetime.date.today()
    else:
        today = start_date
    clock = int(clock)

    if clock == resolve("täglich"):
        result = today + datetime.timedelta(1)
    elif clock == resolve("wöchentlich"):
        result = today + datetime.timedelta(7 - today.weekday())
    elif clock == resolve("monatlich"):
        result = datetime.date(day=1, month=(today.month % 12) + 1,
                               year=today.year if today.month != 12 else today.year + 1)
    elif clock == resolve("vierteljährlich"):
        # No. of months
        length = 3
        # In which period we are (starting from 1)
        period = ((today.month - 1) / length) + 1
        # Beginning of the next period
        kwargs = {"day": 1,
                  "month": (period * length) % 12 + 1,
                  "year": today.year if period != 12 / length else today.year + 1}
        result = datetime.date(**kwargs)
    elif clock == resolve("halbjährlich"):
        # No. of months
        length = 6
        # In which period we are (starting from 1)
        period = ((today.month - 1) / length) + 1
        # Beginning of the next period
        kwargs = {"day": 1,
                  "month": ((period + 1) * length - 1) % 12 + 1,
                  "year": today.year if period != 12 / length else today.year + 1}
        result = datetime.date(**kwargs)
    elif clock == resolve("jährlich"):
        result = datetime.date(day=1, month=1, year=today.year + 1)
    elif clock == resolve("manuell"):
        result = datetime.date.max
    else:
        raise ue.Exception("cdbqc_invalid_update_clock")

    return result


# Compute the quality characteristics
def computeQCs():
    """Computes the quality characteristics, which are due today"""
    from cs.metrics import qualitycharacteristics
    misc.cdblogv(misc.kLogMsg, 0, "QC Engine: computing quality characteristics")

    # allocate license for feature "Metrics: Compute Values"
    fls.allocate_license("METRICS_015")

    # Find all computed quality characteristics
    stmt = "SELECT * FROM %s WHERE computed=1 AND status=%s ORDER BY priority DESC" % \
            (CDBClassDef("cdbqc_def2class").getRelation(),
             qualitycharacteristics.QCDefinition.VALID.status)
    associations = qualitycharacteristics.ClassAssociation.SQL(stmt)

    # Compute QualityCharacteristics
    for ass in associations:
        next_computation = ass.next_computation
        if not next_computation or next_computation <= datetime.datetime.now():
            for qc in ass.QualityCharacteristics:
                if not isinstance(qc, qualitycharacteristics.ObjectQualityCharacteristic) or \
                    (not ass.ORule or ass.ORule.match(ByID(qc.cdbf_object_id))):
                    try:
                        ass.ComputationRule.compute(qc)
                    except Exception as e:
                        misc.cdblogv(misc.kLogErr, 0, "QC Engine: %s" % repr(e))
            ass.next_computation = get_next_computation(ass.update_clock)


def run_loop():
    try:
        # First execution is scheduled for next midnight
        scheduler.enter(seconds_to_midnight(), 1, computeQCs, [])
        scheduler.run()
    except Exception as exc:
        misc.cdblogv(misc.kLogErr, 0, "QC Engine: %s" % repr(exc))
    except KeyboardInterrupt:
        misc.cdblogv(misc.kLogMsg, 0, "QC Engine, shutting down")
        return

    # The following executions are scheduled once a day, every _UPDATE_CLOCK days
    while True:
        try:
            scheduler.enter(_UPDATE_CLOCK * seconds_to_midnight(), 1, computeQCs, [])
            scheduler.run()
        except Exception as exc:
            misc.cdblogv(misc.kLogErr, 0, "QC Engine: %s" % repr(exc))
        except KeyboardInterrupt:
            misc.cdblogv(misc.kLogMsg, 0, "QC Engine, shutting down")
            return


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='QC Computation Engine.')
    parser.add_argument('--compute', dest='compute', action='store_true', default=False,
                        help='compute the quality characteristics')

    # This is for debug purposes
    parser.add_argument('--debug', dest='debug', action='store_true', default=False,
                        help='compute now!')

    args = parser.parse_args()

    misc.cdblogv(misc.kLogMsg, 2, "QC Engine: running %s engine" % "computation" if args.compute else "aggregation")

    # This is for debug purposes
    if args.debug:
        computeQCs()
    else:
        run_loop()
