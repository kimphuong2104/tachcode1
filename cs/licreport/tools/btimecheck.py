# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module btimecheck

Scan a dataset and count the number of btime timeouts
for the sessions included.

"""
import datetime

# Some imports
import logging
import sys
from collections import defaultdict

from cdblic.lsession import BASE_FEATURE, get_event_iter
from cdblic.utils import parse_timestamp

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class TimeoutCounter(object):

    def __init__(self, btime, log):
        self.timeouts = defaultdict(list)
        self.seen = {}
        self.btime = datetime.timedelta(minutes=int(btime))
        self.log = log

    def process(self, event_iter):
        seen = self.seen
        btime = self.btime
        timeouts = self.timeouts
        # only handle base mno, only alloc and refresh
        for event in (event for event in event_iter
                      if event.feature_id == BASE_FEATURE
                      and event.event in (u'A', u'R')):
            last_activity = seen.get(event.pid)
            newtime = parse_timestamp(event.lbtime)
            seen[event.pid] = newtime
            if last_activity is None:
                self.log.debug("New session seen %s", event.pid)
            else:
                timeout = last_activity + btime
                if newtime > timeout:
                    # timeout
                    self.log.debug("New timeout for %s at %s",
                                   event.pid, timeout)
                    timeouts[event.pid].append(timeout)

    def report(self):
        self.log.info("Found %d unique sessions.", len(self.seen))
        self.log.info("Found %d sessions with timeouts.", len(self.timeouts))

        total_timeouts = sum(len(t) for t in self.timeouts.values())
        self.log.info("Found %d timeouts total.", total_timeouts)

    def plot(self, start_time, end_time):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            self.log.warning("MATPLOTLIB not installed, cannot plot.")
            return

        values = []
        for pid in self.seen.keys():
            if pid in self.timeouts:
                p = len(self.timeouts[pid])
                values.append(p)
            else:
                values.append(0)
        m = max(values)
        plt.hist(values, bins=m, histtype='step')
        plt.title("Number of base license timeouts per session"
                  "\nFor Timeslot %s - %s" % (start_time, end_time))
        plt.xlabel("Timeouts")
        plt.ylabel("No. of Sessions")
        plt.show()


def main(start_time, end_time):
    log = logging.getLogger('cdblic.btimecheck')
    # pick the right iterator to use for this dataset
    cnt, iter = get_event_iter(start_time, end_time)
    log.info("Found %d events to process between %s and %s",
             cnt, start_time, end_time)

    obj = TimeoutCounter(60, log)
    obj.process(iter)
    obj.report()
    obj.plot(start_time, end_time)


# Guard importing as main module
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(message)s',
                        datefmt='%H:%M:%S')
    start_time = '2014.10.21 00:00:00'
    end_time = '2014.12.01 18:00:00'
    sys.exit(main(start_time, end_time))
