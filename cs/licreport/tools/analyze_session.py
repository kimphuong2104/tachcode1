#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module analyze_session

Load and analyze a single license session
"""
# Some imports
import datetime
import io
import logging
import os
import sys
from collections import defaultdict

from cdb import sqlapi

from . import config
from .utils import format_timestamp, parse_timestamp

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


def load_uuid_list(filename):
    values = []
    with io.open(filename, encoding="utf-8") as fd:
        for line in fd:
            line = line.strip()
            if line.startswith("#"):
                continue
            if not line:
                continue
            values.append(line)
    return values


def load_dataset(pids):
    if len(pids) == 1:
        rs = sqlapi.RecordSet2(
            config.LSTAT_TABLE, "pid='%s'" % sqlapi.quote(pids[0]), addtl="ORDER BY id"
        )
    else:
        rs = sqlapi.RecordSet2(
            config.LSTAT_TABLE,
            "pid IN (%s)" % (", ".join("'%s'" % sqlapi.quote(p) for p in pids)),
            addtl="ORDER BY pid, id",
        )

    return rs


def check_common_data(rows):
    """Verify the common data is really common.

    Common data is:
        - uname
        - hostname
        - hostid
        - software version
        - pid
    """
    log = logging.getLogger("cdblic.analyze.common")
    common = {}
    row0 = rows[0]
    common["uname"] = row0["uname"]
    common["hostname"] = row0["hostname"]
    common["hostid"] = row0["hostid"]
    common["pid"] = row0["pid"]
    common["version"] = row0["statpwd"].split(":", 1)[0]

    for row in rows:
        for name in ("uname", "hostname", "hostid", "pid"):
            if not row[name] == common[name]:
                log.warning(
                    "Mismatch in common data '%s', expect '%s' got %s",
                    name,
                    common[name],
                    str(row),
                )
            if not row["statpwd"].split(":", 1)[0] == common["version"]:
                log.warning(
                    "Software version change '%s' -> %s", common["version"], str(row)
                )

    return common


def decode_version(versiontag):
    val = int(versiontag, 16)
    version = val >> 10
    major = version // 10
    minor = version % 10
    sl = val & 1023
    return "%s.%s.%s" % (major, minor, sl)


def pretty_print_common(common):
    print("PID: %s" % common["pid"])
    print(
        "User: %20s\tHost: %s [%s]"
        % (common["uname"], common["hostname"], common["hostid"])
    )
    print("Software Version: %s" % decode_version(common["version"]))
    print("=" * 80)


def check_gap(btime_ts, current_tick, row):
    if not current_tick:
        return False

    timeout = parse_timestamp(current_tick) + btime_ts
    if timeout < parse_timestamp(row.lbtime):
        return timeout
    else:
        return False


def pretty_print_events(data, btime, lics):
    btime_ts = datetime.timedelta(minutes=btime)
    row0 = data[0]

    tlen = len(row0["lbtime"])
    maxlic = max(len(k) for k in lics.keys())

    colnames = []
    mapping = {}
    for colnum, name in enumerate(sorted(lics.keys())):
        colnames.append("%*s" % (maxlic, name.replace("-", "|")))
        mapping[colnum] = name

    for i in range(maxlic):
        line = " " * (tlen + 1)
        for col in colnames:
            line += "%s " % col[i]
        print(line)

    current_tick = None
    events = {}

    for row in data:
        if current_tick == row.lbtime:
            # same tick, accumulate
            events[row.mno] = row.event
        else:
            # print leftover
            if current_tick:
                line = "%s " % current_tick
                for i in range(len(colnames)):
                    mno = mapping[i]
                    if mno in events:
                        line += "%s " % events[mno]
                    else:
                        line += "  "
                print(line)
            events.clear()
            # check if this could be a gap
            timeout = check_gap(btime_ts, current_tick, row)
            if timeout:
                line = "%s" % format_timestamp(timeout)
                line += "/" * (len(colnames) * 2 + 1)
                print(line)
            current_tick = row.lbtime
            events[row.mno] = row.event
    # print leftover
    if current_tick and events:
        line = "%s " % current_tick
        for i in range(len(colnames)):
            mno = mapping[i]
            if mno in events:
                line += "%s " % events[mno]
            else:
                line += "  "
        print(line)


def pretty_print_summary(summary):
    start_time, end_time, duration, lics = summary

    print("Start: %s\tEnd: %s\tDuration: %s\n" % (start_time, end_time, duration))

    print("LICS:")
    for key in sorted(lics.keys()):
        print("%-20s\t%s" % (key, "".join(lics[key])))
    print("-" * 80)


def summary(data):
    start_time = parse_timestamp(data[0].lbtime)
    end_time = parse_timestamp(data[-1].lbtime)
    duration = end_time - start_time

    lics = defaultdict(list)
    for row in data:
        lics[row["mno"]].append(row["event"])
    return start_time, end_time, duration, lics


def split_sets(data):
    datasets = defaultdict(list)
    for row in data:
        datasets[row.pid].append(row)
    return datasets


def main(args):
    if len(args) == 1 and os.path.exists(args[0]):
        args = load_uuid_list(args[0])

    all_data = split_sets(load_dataset(args))

    for key in sorted(all_data.keys()):
        data = all_data[key]
        common = check_common_data(data)

        pretty_print_common(common)
        summary_data = summary(data)
        pretty_print_summary(summary_data)
        pretty_print_events(data, 60, summary_data[3])


# Guard importing as main module
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
    )
    sys.exit(main(sys.argv[1:]))
