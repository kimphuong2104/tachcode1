#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module cdblic.lsession

License session analysis with block based license allocation
assumptions.
"""
import datetime
import gc
import heapq
import logging
import random
from collections import OrderedDict, defaultdict, namedtuple

from cdb import sqlapi
from cs.licreport.errors import DataFormatError, NoDataError
from cs.licreport.utils import first_row, first_value, format_timestamp, parse_timestamp

from . import config

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = [
    'build_event_queue',
    'count_lic_events',
    'count_lic_events_grouped',
    'count_license_sets',
    'count_license_sets_by_user',
    'extract_sessions',
    'EventPseudonymizer',
]

LicInfo = namedtuple('LicInfo', ['mno', 'start_time', 'lkind'])

# The first feature allocated by a starting server
# Marks start of a session
BASE_FEATURE = "PLATFORM_001"
LARGE_ROWSET_THRESHOLD = 200000


# FIXME: Handle Server-License Logging codes
# G -> Servlic alloc
# N -> Servlic failed
# C -> Servlic free/release


def get_sample_row(data_table=config.LSTAT_TABLE):
    # get first row from lstatistics, used to get version used in sampling
    db_type = sqlapi.SQLdbms()
    if db_type == sqlapi.DBMS_MSSQL:
        sql = "SELECT TOP 1 * FROM %s" % data_table
    elif db_type == sqlapi.DBMS_ORACLE:
        sql = "SELECT * FROM %s WHERE rownum = 1" % data_table
    elif db_type == sqlapi.DBMS_SQLITE:
        sql = "SELECT * FROM %s LIMIT 1" % data_table
    else:
        raise NotImplementedError("Unknown Database Code %s" % db_type)

    row = None
    rset = sqlapi.RecordSet2(sql=sql)
    if rset:
        row = rset[0]
    return row


def decode_versioninfo(statpwd):
    catch_all_old_versions = "9.9.0"
    if ':' not in statpwd:  # old versions have no encoding in statpwd for release
        versionstring = catch_all_old_versions  # pre-E024180
    elif statpwd == '00000:rewrite':
        versionstring = catch_all_old_versions  # fixed old 9.9 version
    else:  # regular data
        val, pwd = statpwd.split(':', 1)
        # string is like 1901c:d3/ctoROno6 = <encodedversion>:<hash>
        val = int(val, 16)
        # base 16, 5 hexadecimals = 20 bit, first 10 bit for major, minor, last 10 bit for sl
        version = val >> 10
        # kick out last ten bit => keep first ten bit
        major = version // 10
        # version is 10*major + minor, assuming minor < 10
        minor = version % 10
        sl = val & 1023  # 1023 = 0b1111111111 => keep last ten bit, this is sl
        versionstring = "%s.%s.%s" % (major, minor, sl)
    return versionstring


def get_cdb_version(data_table=config.LSTAT_TABLE):
    row = get_sample_row(data_table)
    if row:
        statpwd = row["statpwd"]
        versionstring = decode_versioninfo(statpwd)
        major, minor, sl = versionstring.split('.')
        cdb_version = "%s.%s" % (major, minor)
    else:  # shouldn't happen ;-) unless statistics table is empty
        raise NoDataError(data_table, "No Data in statistics Table.")
    return cdb_version


def has_current_format(lbtime_start, lbtime_end, base_table=config.LSTAT_TABLE):
    """ Check if statpwd has the version info encoded.

        Older versions have incorrect PIDs, those cannot
        be used with this report.
    """
    oracle_sql = """SELECT count(*) FROM %s
             WHERE lbtime BETWEEN '%s' AND '%s'
             AND SUBSTR(statpwd,6,1) = ':'""" % (
        base_table, lbtime_start, lbtime_end)
    ms_sql = """SELECT count(*) FROM %s
             WHERE lbtime BETWEEN '%s' AND '%s'
             AND SUBSTRING(statpwd,6,1) = ':'""" % (
        base_table, lbtime_start, lbtime_end)
    count = None
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        count = first_value(ms_sql)
    else:
        count = first_value(oracle_sql)

    if not count:
        return False
    else:
        return True


def find_max_btime(base_table):
    """ Get the highest btime in the whole table

        Needed for safe btime shadowing calculations.
    """
    sql = """SELECT MAX(btime) FROM %s""" % base_table
    count = first_value(sql)
    if count is None:
        return 0
    return int(count)


# get a compact version repr for event data,
# with attr access like recordset
event_attrs = [
    'pid',
    'feature_id',
    'mno',
    'event',
    'uname',
    'lbtime',
    'lkind',
    'btime',
    'hostname'
]
EventInfo = namedtuple('EventInfo', event_attrs)


class EventPseudonymizer(object):
    """
    Pseudonymize the event data, so the report does not have PII.

    The report does not need the actual data, it only needs to know
    if u1 == u2 or u1 != u2 for some fields.

    So user1 will not be user1 on the next run.

    In this case any id will be replace by a prefix and a random number
    between 1 and 999.999.

    """
    def __init__(self):
        self.rd = random.SystemRandom()
        self.mapping = {}
        self.used = set()

    def get_id(self, prefix, name):
        idv = self.mapping.get(name)
        if idv:
            return idv
        while 1:
            idv = u"%s%-10d" % (prefix, self.rd.randint(1, 999999))
            if idv not in self.used:
                self.used.add(idv)
                self.mapping[name] = idv
                return idv

    def __call__(self, event):
        return EventInfo(
            event.pid,
            event.feature_id,
            event.mno,
            event.event,
            self.get_id(u"user", event.uname),
            event.lbtime,
            event.lkind,
            event.btime,
            self.get_id(u"host", event.hostname),
        )


class RowsetIter(object):
    """ Iterate over EventInfo objects
    """

    def __init__(self, start_time, end_time, base_table):
        self.start_time = start_time
        self.end_time = end_time
        self.base_table = base_table
        self.columns = event_attrs
        self.orderby = "ORDER BY lbtime, cs_sortable_id"

    def __iter__(self):
        return self

    def next(self):
        raise StopIteration()


# The world is just too simple, lets make it more complex
# with arcane SQL.
#
# One might assume it would be enough to look at the events
# inside the measurment interval and include just sessions,
# mentioned in the interval but that is sadly wrong.
# In fact, sessions outside the measurment interval
# may overshadow the measurment interval with a kind of
# residual background license count (weird: yes).
#
# This has two consequences:
#
# 1. Binding Time Shadowing
#
#    We need to work with start_time - binding_time to get the
#    relevant starting point for this statement, otherwise we would
#    misclassify intervals that timeout just inside the
#    lower interval border (between |t_start and t_start+btime|.
#    Changing the offset marks them as 'before' and 'inside'
#    instead of just 'before'.
#
#    Call find_max_btime() to find a safe value to use.
#
# 2. Suspended Session Residuals
#
#    A session may allocate a license, go to sleep due to binding
#    time having elapsed and can be waked up later. If this suspension
#    is longer than the measurment interval, we do not see ANY event
#    of this session inside lbtime_start/lbtime_end, still we need
#    to count it for the maximum, otherwise we get weird maxima fluctuations,
#    when measurment intervals are moved around.
#
#    This is insane. Should probably be handled differently, but the current
#    definition is like this.
#

SESSIONS_AFFECTING_THE_INTERVAL = """
    SELECT pid
    FROM (
    SELECT
    b.pid pid,
    CASE
    WHEN EXISTS (SELECT 1 FROM %(lstatistics)s a
                 WHERE a.pid = b.pid AND lbtime > '%(end_time)s') THEN 1
        ELSE 0
    END after_interval,
    CASE
        WHEN EXISTS (SELECT 1 FROM %(lstatistics)s a
                     WHERE a.pid = b.pid AND lbtime < '%(start_time)s') THEN 1
        ELSE 0
    END before_interval,
    CASE
    WHEN EXISTS (SELECT 1 FROM %(lstatistics)s a
                 WHERE a.pid = b.pid AND lbtime <= '%(end_time)s'
                 AND lbtime >= '%(start_time)s') THEN 1
        ELSE 0
    END in_interval
    FROM (SELECT DISTINCT pid FROM %(lstatistics)s) b
    ) c
    WHERE (c.after_interval = 1 AND c.before_interval = 1)
    OR c.in_interval = 1
"""


class LargeOracleRowsetIter(RowsetIter):
    """
    Generator for huge rowsets that would create out-of-memory
    conditions otherwise.

    Pagination is done over the tuple (lbtime, id).

    The end_time must be in the past and events must be stable
    inside the measurment interval.
    """
    BLOCKSIZE = 100000

    def __init__(self, *args, **kwargs):
        super(LargeOracleRowsetIter, self).__init__(*args, **kwargs)
        self.rowset = None
        self.columns.append('cs_sortable_id')
        self.sql = None
        self.start_time = args[0]
        self.end_time = args[1]
        self.max_btime = datetime.timedelta(minutes=find_max_btime(self.base_table))
        self.inner_sql = None
        self.log = logging.getLogger('cdblic.lsession.LargeRowsetIter')

    def setup_initial_condition(self):
        # collect insanity points
        # effective start_time
        eff_start_time = format_timestamp(
            parse_timestamp(self.start_time) - self.max_btime)
        d = {'start_time': eff_start_time,
             'end_time': self.end_time,
             'lstatistics': self.base_table}
        cols = ",".join('%s' % col for col in self.columns)
        self.inner_sql = "(%s)" % SESSIONS_AFFECTING_THE_INTERVAL % d

        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            # MS-SQL
            self.sql = """
                WITH subtable AS
                (   SELECT %s, ROW_NUMBER() OVER (%s) AS rownum
                    FROM %s
                    WHERE pid IN %s
                    AND event in ('A', 'F', 'X', 'R', 'S', 'Q')
                )
                SELECT %s FROM subtable WHERE rownum <= %d
                """ % (cols,
                       self.orderby,
                       self.base_table,
                       self.inner_sql,
                       cols,
                       self.BLOCKSIZE)
        else:
            # Oracle
            self.sql = """
                SELECT * FROM
                    (SELECT %s
                    FROM %s
                    WHERE pid IN %s
                    AND event in ('A', 'F', 'X', 'R', 'S', 'Q')
                    %s)
                    WHERE rownum <= %d
                """ % (cols,
                       self.base_table,
                       self.inner_sql,
                       self.orderby,
                       self.BLOCKSIZE)

    def setup_paging_condition(self, last_row):
        cols = ",".join('%s' % col for col in self.columns)

        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            # MS-SQL
            self.sql = """
                WITH subtable as
                (   SELECT %s, ROW_NUMBER() OVER (%s) AS rownum
                    FROM %s
                    WHERE pid IN %s
                    AND event in ('A', 'F', 'X', 'R', 'S', 'Q')
                    AND
                    (lbtime > '%s' OR (lbtime = '%s' AND cs_sortable_id > '%s'))
                    AND
                    lbtime <= '%s'
                )
                SELECT %s FROM subtable WHERE rownum <= %d
                """ % (cols,
                       self.orderby,
                       self.base_table,
                       self.inner_sql,
                       last_row['lbtime'], last_row['lbtime'],
                       last_row['cs_sortable_id'],
                       self.end_time,
                       cols,
                       self.BLOCKSIZE)
        else:
            # Oracle
            self.sql = """
            SELECT * FROM
                (SELECT %s
                FROM %s
                WHERE pid IN %s
                AND event in ('A', 'F', 'X', 'R', 'S', 'Q')
                AND
                (lbtime > '%s' OR (lbtime = '%s' AND cs_sortable_id > '%s'))
                AND
                lbtime <= '%s'
                %s
                )
                WHERE rownum <= %d
            """ % (cols,
                   self.base_table,
                   self.inner_sql,
                   last_row['lbtime'], last_row['lbtime'],
                   last_row['cs_sortable_id'],
                   self.end_time,
                   self.orderby,
                   self.BLOCKSIZE)

    def paging_rowset_generator(self):
        total = 0
        while 1:
            rowset = sqlapi.RecordSet2(table=self.base_table,
                                       sql=self.sql)

            if not rowset:
                self.log.info("Loaded %d rows in total", total)
                return

            total += len(rowset)
            self.log.info("Page of rowset fetched. %d items", len(rowset))

            # memorize the last row for pagination
            last_row = dict(rowset[-1].items())

            # switch to next page
            for row in rowset:
                values = row.values()
                # strip off the id column
                yield EventInfo(*values[:-1])

            gc.collect()
            self.log.debug(
                "Next page (total=%d), starting after id=%s, lbtime=%s",
                total, last_row['cs_sortable_id'], last_row['lbtime'])
            self.setup_paging_condition(last_row)

    def __iter__(self):
        self.setup_initial_condition()
        self.log.info(
            "Loading rowset from '%s' via Paging "
            "RecordSet2 with Pagesize of '%d'",
            self.base_table, self.BLOCKSIZE)
        return self.paging_rowset_generator()


class SmallRowsetIter(RowsetIter):
    """
    Smaller iterator, for rowsets that easily fit into main memory.
    """

    def __init__(self, *args, **kwargs):
        super(SmallRowsetIter, self).__init__(*args, **kwargs)
        self.condition = None
        self.start_time = args[0]
        self.end_time = args[1]
        self.inner_sql = None
        self.max_btime = datetime.timedelta(minutes=find_max_btime(self.base_table))
        self.log = logging.getLogger('cdblic.lsession.SmallRowsetIter')

    def setup_condition(self):
        # collect insanity points
        # effective start_time
        eff_start_time = format_timestamp(
            parse_timestamp(self.start_time) - self.max_btime)
        d = {'start_time': eff_start_time,
             'end_time': self.end_time,
             'lstatistics': self.base_table}

        self.inner_sql = SESSIONS_AFFECTING_THE_INTERVAL % d
        self.condition = """pid IN (%s) AND lbtime <= '%s' AND event in ('A', 'F', 'X', 'R', 'S', 'Q')""" % (
            self.inner_sql, self.end_time)

    def __iter__(self):
        self.setup_condition()
        self.log.info("Loading rowset from '%s' via RecordSet2 with '%s'",
                      self.base_table, self.condition)
        rowset = sqlapi.RecordSet2(table=self.base_table,
                                   columns=self.columns,
                                   condition=self.condition,
                                   addtl=self.orderby)
        self.log.info("Rowset fetched. %d items", len(rowset))

        # use the fast and memory efficient values() optimization
        # of the RecordSet2 iterator if present
        return (EventInfo(*row.values()) for row in rowset)


def get_event_iter(start_time, end_time, tables, threshold=LARGE_ROWSET_THRESHOLD):
    """
    Get an appropriate iter for the size of the dataset
    """
    count_query = """
        SELECT COUNT(*) items
        FROM %s
        WHERE lbtime BETWEEN '%s' AND '%s'
        """ % (tables['lstatistics'], start_time, end_time)

    rowcount = first_value(count_query)
    if rowcount and not has_current_format(start_time, end_time, tables['lstatistics']):
        raise DataFormatError(
            "%s data is in unknown or old (pre-E024180) format" % tables['lstatistics'])

    if rowcount > threshold:
        return rowcount, LargeOracleRowsetIter(start_time, end_time, tables['lstatistics'])
    else:
        return rowcount, SmallRowsetIter(start_time, end_time, tables['lstatistics'])


class Session(object):
    # use slots to minimize memory usage,
    # we could have a lot of these objects
    __slots__ = ['pid',
                 'uname',
                 'included_licenses',
                 'failed_licenses',
                 'start_time',
                 'end_time',
                 'last_activity',
                 'stream_id',
                 'hostname'
                 ]

    def __init__(self):
        self.pid = None
        self.uname = None
        self.hostname = None
        # list of licinfos
        self.included_licenses = []
        self.failed_licenses = []
        self.start_time = None
        self.end_time = None
        self.last_activity = None

    def complete(self):
        """Check if the session is complete and closed"""
        return self.end_time is not None

    def process(self, event):
        """
        Add an event to the session
        """
        assert event.event in (u'R', u'X', u'A', u'F', u'S', u'Q'), event

        call = getattr(self, event.event)
        call(event)

    def __contains__(self, mno):
        """ Check if the given mno is in the included licenses
        """
        return any(mno == lic.mno for lic in self.included_licenses)

    def add_lic(self, mno, lbtime, lkind):
        """ Add a license mno to the included licenses
        """
        assert mno
        assert mno not in self
        assert lkind in (u'EX',  # Integration License
                         u'SD',  # SOED
                         u'FL',  # Floating
                         u'FX',  # Node (9.9.0- or Named User 10.0+)
                         u'XX')  # Unknown, from session fixer
        self.included_licenses.append(LicInfo(mno, lbtime, lkind))

    def S(self, event):
        """
        Process Session Start events
        """
        assert event.event == u'S'
        if self.pid is None:
            # First 'S' in a session
            assert self.uname is None
            assert self.start_time is None
            assert self.end_time is None
            assert len(self.included_licenses) == 0
            self.pid = event.pid
            self.uname = event.uname
            self.start_time = event.lbtime
            self.hostname = event.hostname
        else:
            # Second 'S' should only happen when license system
            # gets reinitialized in rare cases.
            assert self.pid == event.pid
            assert self.uname == event.uname
            assert self.start_time
            # Remove the end time in this case...
            self.end_time = None

        # After a start we have a start time
        assert self.start_time
        # No start should ever close a session
        assert self.end_time is None
        # After a start, we have a uname
        assert self.uname
        # After a start, we have a pid
        assert self.pid

    def Q(self, event):
        """
        Process Session Quit
        """
        assert event.event == u'Q'
        if self.pid is None:
            # Quit at the start of a session
            # Can only happen when lstatistics data has been lost
            self.start_time = event.lbtime
            self.end_time = event.lbtime
            self.pid = event.pid
            self.uname = event.uname
            log = logging.getLogger('cdblic.SessionBuilder.warn.W08')
            log.debug("Quit at start of session pid=%s time=%s user=%s",
                      self.pid, event.lbtime, self.uname)
        else:
            assert self.start_time <= event.lbtime
            assert self.uname == event.uname
            assert self.pid == event.pid
            self.end_time = event.lbtime
        assert self.start_time
        assert self.end_time
        assert self.pid
        assert self.uname

    def A(self, event):
        """
        Process License Allocation events
        """
        assert event.event == u'A'
        assert self.end_time is None
        if self.pid is None:
            # First license allocation in this session
            assert self.uname is None
            assert self.start_time is None
            assert len(self.included_licenses) == 0
            self.pid = event.pid
            self.uname = event.uname
            self.start_time = event.lbtime
            self.hostname = event.hostname
            self.add_lic(event.mno, event.lbtime, event.lkind)
        else:
            # Second or later license allocation in this session
            assert self.pid == event.pid
            if self.uname != event.uname:
                # Probably API abuse to switch users in a UE to avoid
                # a proper access system/role configuration or some other
                # bizarre situation.
                log = logging.getLogger('cdblic.SessionBuilder.warn.W01')
                log.debug("User Switch during session pid=%s, mno=%s "
                          "changed from '%s' to '%s'",
                          self.pid, event.mno, self.uname, event.uname)
            if event.feature_id == BASE_FEATURE:
                # base license
                # Unusual, as this should always be
                # the first event in a session.
                if event.mno in self:
                    # ignore
                    # This is just a base session alloc that expired
                    # due to binding time. If the old license slot is
                    # already reassigned, this is logged as an allocation.
                    #
                    ev = [ev for ev in self.included_licenses
                          if ev.mno == event.mno]
                    log = logging.getLogger('cdblic.SessionBuilder.warn.W07')
                    log.debug("Duplicate Allocation of base license: pid=%s "
                              "lbtime=%s uname=%s previous=%s",
                              self.pid, event.lbtime, event.uname, ev)

                elif self.included_licenses:
                    # Bad. Some non-base license was allocated before
                    # the base license.
                    if self.included_licenses[0].mno != u'CON-PA-GEN/SRV':
                        # TODO. ignore, but log an error for analysis
                        log = logging.getLogger('cdblic.SessionBuilder.warn.W02')
                        log.warning("Non-Base license allocated before base"
                                    "license: pid=%s lbtime=%s mno=%s uname=%s\n%s",
                                    self.pid, event.lbtime, event.mno, event.uname,
                                    self.included_licenses)
                else:
                    # Ok, just a session start marker 'S', add our 'A' now
                    self.add_lic(event.mno, event.lbtime, event.lkind)

            else:
                # non-base license
                if event.mno in self:
                    # TODO.
                    # duplicate..., ignore and log
                    log = logging.getLogger('cdblic.SessionBuilder.warn.W03')
                    log.debug("Double allocation of non-base license:"
                              "pid=%s lbtime=%s mno=%s",
                              self.pid, event.lbtime, event.mno)
                else:
                    self.add_lic(event.mno, event.lbtime, event.lkind)

        # No allocation should ever close a session
        assert self.end_time is None
        # After an allocation, we have a uname
        assert self.uname
        # After an allocation, we have a pid
        assert self.pid
        # After an allocation, we have at least one license
        assert len(self.included_licenses) > 0

    def X(self, event):
        """
        Process License allocation failure
        """
        assert event.event == u'X'
        # should log something, for now just ignore it
        failed = LicInfo(event.mno, event.lbtime, event.lkind)
        if failed not in self.failed_licenses:
            log = logging.getLogger('cdblic.SessionBuilder.warn.W04')
            log.info("Failed to allocate license: lbtime=%s mno=%s uname=%s",
                     event.lbtime, event.mno, event.uname)
        self.failed_licenses.append(LicInfo(event.mno, event.lbtime, event.lkind))

    def R(self, event):
        """
        Process License refresh Events
        """
        assert event.event == u'R'
        assert self.end_time is None
        if self.pid is None:
            # Start of a truncated session, we haven't seen an allocation yet
            assert self.uname is None
            assert self.start_time is None
            assert len(self.included_licenses) == 0

            # Identical for base and non-base license
            self.pid = event.pid
            self.uname = event.uname
            # start time is unknown!
            self.add_lic(event.mno, None, event.lkind)
            self.start_time = event.lbtime
            # start time stays unknown
            # assert self.start_time is None
        else:
            assert event.pid == self.pid
            # assert event.uname == self.uname
            if self.uname != event.uname:
                # Probably API abuse to switch users in a UE to avoid
                # a proper access system/role configuration or some other
                # bizarre situation.
                log = logging.getLogger('cdblic.SessionBuilder.warn.W01')
                log.debug("User Switch during session pid=%s, mno=%s "
                          "changed from '%s' to '%s'",
                          self.pid, event.lbtime, self.uname, event.uname)
            if event.mno in self:
                # already exists, all good
                # TODO. check further invariants (lkind, lbtime_old < lbtime)
                pass
            else:
                # Auto extended to start_time.
                #
                # We did not see the alloc, so we must assume, the allocation
                # happend between start_time and this event.
                # So be conservative and use session start_time.
                if self.start_time is not None:
                    # we saw the session start alloc, so this is fishy...
                    log = logging.getLogger('cdblic.SessionBuilder.warn.W05')
                    log.debug("Refresh for license without an allocation first: pid=%s lbtime=%s mno=%s",
                              event.pid, event.lbtime, event.mno)

                self.add_lic(event.mno, self.start_time, event.lkind)

        # No refresh should ever close a session
        assert self.end_time is None
        # After a refresh, we have a uname
        assert self.uname
        # After a refresh, we have a pid
        assert self.pid
        # After a refresh, we have at least one license
        assert len(self.included_licenses) > 0

    def F(self, event):
        """
        Process License Free events
        """
        assert event.event == u'F'
        if event.feature_id == BASE_FEATURE:
            if self.pid:
                if not (event.mno in self):
                    # add a proper base license record with unknown start_time
                    self.add_lic(event.mno, None, event.lkind)
                self.end_time = event.lbtime
            else:
                # Got a free, but no previous info, Bad.
                # In general we will not be able to log this
                # session correctly. It can have too
                # few license allocations.
                log = logging.getLogger('cdblic.SessionBuilder.warn.W06')
                # TODO: log to file instead of console, notify user of log file afterwards
                log.debug("Free event without previous info found: pid=%s lbtime=%s uname=%s mno=%s",
                          event.pid, event.lbtime, event.uname, event.mno)
                self.pid = event.pid
                self.uname = event.uname
                self.start_time = event.lbtime
                self.add_lic(event.mno, None, event.lkind)
                self.end_time = event.lbtime
        else:
            # Other license free, treat like a refresh
            # All non base licenses cannot be freed really.
            # This is the major change to the previous reports.
            refresh_event = EventInfo(
                event.pid,
                event.feature_id,
                event.mno,
                u'R',
                event.uname,
                event.lbtime,
                event.lkind,
                event.btime,
                event.hostname
            )
            return self.R(refresh_event)

        # session should be closed
        assert self.end_time
        # and have at least the base license
        assert len(self.included_licenses) > 0
        # After a free, we have a uname
        assert self.uname
        # After a free, we have a pid
        assert self.pid

    def dump(self):
        s = "PID %s Start Time %s End Time %s Uname %s" % (
            self.pid, self.start_time, self.end_time, self.uname)
        s += "Lics: %s" % (", ".join(str(s) for s in self.included_licenses))
        return s

    def verify(self):
        try:
            self._verify()
        except AssertionError:
            log = logging.getLogger('cdblic.SessionBuilder')
            log.error("Verification error: %s", self.dump())
            raise

    def _verify(self):
        """ Integrity check for the session
        """
        unique_mno = set()
        for lic in self.included_licenses:
            assert lic.start_time is None or (
                lic.start_time >= self.start_time
            ), (lic.start_time, self.start_time)
            assert lic.start_time is None or (
                lic.start_time <= self.end_time
            ), (lic.start_time, self.end_time)
            assert lic.mno
            assert lic.mno not in unique_mno
            unique_mno.add(lic.mno)

        assert (self.start_time is None) or (self.end_time is None) or (
            self.start_time <= self.end_time), (self.start_time, self.end_time)

    def dt_start(self):
        """ Get start date as datetime object
        """
        return parse_timestamp(self.start_time)

    def dt_end(self):
        """ Get end date as datetime object
        """
        return parse_timestamp(self.end_time)

    def duration(self):
        """ Length of a session as a datetime.timedelta
        """
        assert self.start_time
        assert self.end_time
        return self.dt_end() - self.dt_start()


class SessionBuilder(object):
    """
       Analyzes a stream of lstatistics rows
       for license session data and extract the sessions.
    """

    def __init__(self, pseudonymizer=None):
        self.log = logging.getLogger('cdblic.SessionBuilder')
        # All pids we ever saw in this interval
        self.all_pids = None
        # Session for which we didn't see the end tag yet
        self.incomplete_sessions = None
        # pseudonymous mapper
        self.event_mapper = pseudonymizer if pseudonymizer else lambda x: x

    def process(self, rowset):
        """
        Consume the rowset and yield sessions
        """
        # use faster local variables
        all_pids = set()
        tombstoned = set()
        incomplete_sessions = defaultdict(Session)
        for e in rowset:
            # Pseudonymize dataset
            event = self.event_mapper(e)
            assert event.pid is not None

            all_pids.add(event.pid)
            if event.pid in tombstoned:
                if event.event not in (u'F', u'Q'):
                    # The session is dead already, zombies?

                    # For 'F' this is okay, as the license cleanup
                    # frees licenses in the unexpected order of allocation
                    # (not reversed).
                    # Base license is freed first, before others get freed.
                    #
                    # For other events this is just wrong and should not happen.
                    self.log = logging.getLogger(
                        'cdblic.SessionBuilder.warn.W07')
                    self.log.warning(
                        "Received event %s - %s for already closed session %s.",
                        event.event, event.mno, event.pid)
                continue

            session = incomplete_sessions[event.pid]
            session.process(event)
            if session.complete():
                session.verify()
                tombstoned.add(session.pid)
                del incomplete_sessions[session.pid]
                yield session

        broken_sessions = []
        for k, s in incomplete_sessions.items():
            if s.pid is None:
                # shouldn't be possible, but a pid with only one event with 'X' produces it, will remove
                broken_sessions.append(k)
        for k in broken_sessions:
            del incomplete_sessions[k]
            all_pids.remove(k)

        # copy the local vars to object vars
        self.all_pids = all_pids
        self.incomplete_sessions = incomplete_sessions

        self.log.info("Have seen %d unique PIDs. %d sessions "
                      "completed, %d incomplete.",
                      len(self.all_pids), len(tombstoned),
                      len(self.incomplete_sessions))

    def finalize(self):
        """
        Get all incomplete sessions

        Those sessions need some fixup, as either end_time or start_time
        is missing.
        """
        result = list(self.incomplete_sessions.values())
        self.incomplete_sessions = {}
        return result


class UnfinishedSessionFixer(object):
    """ Complete unfinished sessions with a good estimate

        An unfinished session end_time can happen for various reasons.

        1. Session starts or ends outside the reporting interval
        2. cdbsrv could not write finalization marker (due to crash
          or database connectivity issues)
        3. cdbsrv did not free license due to binding time timeout
          (e.g. a license is only explicitly freed if still in use,
           this is skipped if binding time has expired)

        So we need to fill in some valid guess for the license
        end_time, based on assumptions.

        As follows:

        - If a free mark is found outside the base interval, use it.
        - Otherwise use the last activity for the pid.

        This underestimates the license time for case 3., but the
        client just idled in that case, so it was no active usage.

        An uncertain start_time can happen just due to 1., so the
        logic is as follows:

        - If an alloc is found outside the base interval, use it.
        - Otherwise use the start_time of the base_interval.

    """

    def __init__(self, start_time, end_time, base_table=config.LSTAT_TABLE):
        self.start_time = start_time
        self.end_time = end_time
        self.base_table = base_table
        self.log = logging.getLogger('cdblic.SessionFixer')
        self.start_interval_default = 0
        self.start = parse_timestamp(self.start_time)
        self.end = parse_timestamp(self.end_time)
        # According to measurment theory, this needs to be of the magnitude
        # of the binding time of the base license.
        self.assume_active_period = datetime.timedelta(seconds=7200)
        self.zero_duration_sessions = 0
        self.start_time_fix = 0
        self.end_time_fix = 0

    def process(self, session):
        """ Fixup the given session
        """

        # TODO: log to file instead of console
        self.log.debug(
            "Completing session pid: %s user, %s start: %s end: %s [%s]",
            session.uname, session.pid, session.start_time, session.end_time, session.included_licenses)

        if session.start_time is None:
            self.start_time_fix += 1
            self.fix_start_time(session)
            self.log.debug("Fixed session: no start time; pid: %s start: %s end: %s",
                           session.pid, session.start_time, session.end_time)

        if session.end_time is None:
            self.end_time_fix += 1
            self.fix_end_time(session)
            self.log.debug("Fixed session: no end time; pid: %s start: %s end: %s",
                           session.pid, session.start_time, session.end_time)

        if session.start_time == session.end_time:
            self.zero_duration_sessions += 1
            self.adjust_zero_size_session(session)
            self.log.debug("Fixed session: duration zero; pid: %s start: %s end: %s",
                           session.pid, session.start_time, session.end_time)

        session.verify()

        return session

    def fix_start_time(self, session):
        """ Find a good start time for the session
        """
        assert session.start_time is None
        sql = """SELECT MIN(lbtime) lbtime,
                        MIN(lkind) lkind
                 FROM %s
                 WHERE feature_id='%s'
                 AND lbtime <= '%s'
                 AND event IN ('A', 'R')
                 AND pid='%s'
              """ % (self.base_table,
                     BASE_FEATURE,
                     self.start_time,
                     session.pid)
        row = first_row(sql)
        lbtime = row['lbtime']
        if lbtime is not sqlapi.NULL:
            # alloc found, use it
            session.start_time = lbtime
            self.log.debug("Add start time from previous alloc pid: %s start: %s",
                           session.pid, session.start_time)
            return

        # no alloc or refresh for base lic found,
        # check ANY activity for this pid
        sql = """SELECT MIN(lbtime) lbtime
                 FROM %s
                 WHERE pid='%s'
                 AND lbtime < '%s'
              """ % (self.base_table, session.pid, self.end_time)
        lbtime = first_value(sql)
        assert lbtime is not sqlapi.NULL
        activity = parse_timestamp(lbtime)

        if activity < self.start:
            # first activity is before our measurment start time, use it,
            # only the duration session is wrong, but harmless
            session.start_time = lbtime
            self.log.debug("Add start time from pre measurment interval "
                           "activity pid: %s start: %s",
                           session.pid, session.start_time)
        elif activity < self.start + self.assume_active_period:
            # first activity is close to the measurment start time,
            # so we assume the allocation overlapped the start time
            self.start_interval_default += 1
            session.start_time = self.start_time
            self.log.debug("Add start time from measurment interval start "
                           "(approximation) pid: %s start: %s",
                           session.pid, session.start_time)
        else:
            # first activity is way inside the measurment interval,
            # seems the alloc was lost or this is a dormant session revived
            # after a very long idle sleep.
            # Assuming an extension to measurment start leads to unjustified
            # results, with sessions that are extended to hundreds of days,
            # which is obviously the wrong approach.
            # So we assume the first activity is a good indicator of session
            # start and use that, giving the customer the benefit of doubt here.
            #
            # We don't really know what happend so assume first activity
            # is a good approximation for the start time.
            session.start_time = lbtime
            self.log.debug("Add start time from first seen activity "
                           "(approximation) pid: %s start: %s",
                           session.pid, session.start_time)
        assert session.start_time

    def fix_end_time(self, session):
        """ Find a good end time for the session
        """
        assert session.start_time
        assert session.end_time is None

        sql = """SELECT MAX(lbtime) last_activity
                 FROM %s
                 WHERE pid='%s'
                 AND lbtime >= '%s'
              """ % (self.base_table,
                     session.pid,
                     session.start_time)
        last_activity = first_value(sql)
        if last_activity is sqlapi.NULL:
            # no info, end of interval
            session.end_time = self.end_time
            self.log.debug("Add end time from interval pid: %s start: %s",
                           session.pid, session.end_time)
        else:
            # last activity
            session.end_time = last_activity
            self.log.debug("Add end time from last activity pid: %s start: %s",
                           session.pid, session.end_time)

        assert session.end_time

    def adjust_zero_size_session(self, session):
        """ Session may not have a duration of zero

            So we fix this by assuming a 30 Minute session.
        """
        assert session.start_time
        assert session.end_time
        assert session.end_time == session.start_time
        self.log.debug("Correcting zero duration session: %s start: %s uname: %s",
                       session.pid, session.end_time, session.uname)
        end_time = session.dt_end() + datetime.timedelta(minutes=30)
        session.end_time = end_time.strftime("%Y.%m.%d %H:%M:%S")


CountEvent = namedtuple('CountEvent',
                        ['lbtime', 'evtype', 'mno', 'group',
                         'pid', 'stream_id', 'uname', 'lkind', 'hostname'])


FREE = 0
ALLOC = 1


def build_event_queue(sessions, uname_mapper=None):
    """ Turn a list of events into an heap of allocation
        and free events for counting

        An uname_mapper function can add an extra grouping key to the events.
    """
    heap = []
    counter = 0
    group_key = lambda x: None
    if callable(uname_mapper):
        group_key = uname_mapper

    seen = set()
    for session in sessions:
        assert session.start_time is not None
        assert session.end_time is not None
        assert session.uname
        # We may have failed allocations only
        if session.failed_licenses and not session.included_licenses:
            # Empty session with just failed allocations
            # Skip
            continue

        if hasattr(session, 'stream_id'):
            stream_id = session.stream_id
        else:
            stream_id = 0
        surrogate = (session.pid, stream_id)

        assert surrogate not in seen, surrogate
        seen.add(surrogate)

        group = group_key(session.uname)

        included_licenses = session.included_licenses

        for lic in included_licenses:
            start_time = lic.start_time
            if start_time is None:
                start_time = session.start_time
            counter += 1
            assert start_time >= session.start_time
            assert lic.mno

            # frees with same times must sort lower, so use free=0/alloc=1,
            # otherwise maxima get too high
            alloc = CountEvent(start_time,
                               ALLOC, lic.mno, group,
                               session.pid, stream_id,
                               session.uname, lic.lkind,
                               session.hostname)

            # handle early free by conversion
            free_time = session.end_time
            free = CountEvent(free_time, FREE, lic.mno, group,
                              session.pid, stream_id,
                              session.uname, lic.lkind,
                              session.hostname)
            assert alloc.lbtime <= free.lbtime
            heapq.heappush(heap, alloc)
            heapq.heappush(heap, free)
    # only one alloc and one free event per lic
    assert counter * 2 == len(heap)
    # Special case named user licenses
    heap = filter_named_user_allocations(heap)
    heap = filter_parallel_floating_sessions(heap)
    return heap


def filter_named_user_allocations(event_queue):
    """Normalize the license allocations for named user licenses"""
    assert len(event_queue) % 2 == 0
    out = []
    seen = defaultdict(int)
    while event_queue:
        ev = heapq.heappop(event_queue)
        # Skip if not named user
        if ev.lkind != 'FX':
            heapq.heappush(out, ev)
            continue

        # Check if we already saw this license/user for alloc/free
        # keep a refcount.
        pushed = False
        key = (ev.uname, ev.mno)
        if key not in seen:
            seen[key] = 0
            heapq.heappush(out, ev)
            pushed = True

        if ev.evtype == ALLOC:
            seen[key] += 1
        elif ev.evtype == FREE:
            seen[key] -= 1

        # Remove when refcount drops to zero
        if seen[key] <= 0:
            del seen[key]
            if not pushed:
                heapq.heappush(out, ev)

    # The queue must still have an even number of events
    assert len(out) % 2 == 0
    return out


def filter_parallel_floating_sessions(event_queue):
    """Normalize the license allocations for floating sessions on the same host"""
    assert len(event_queue) % 2 == 0
    out = []
    seen = defaultdict(int)
    while event_queue:
        ev = heapq.heappop(event_queue)
        # Skip if not floating session
        if ev.lkind == 'FX':
            heapq.heappush(out, ev)
            continue

        # Check if we already saw this license/user/host triple for alloc/free
        # keep a refcount.
        pushed = False
        key = (ev.uname, ev.mno, ev.hostname)
        if key not in seen:
            seen[key] = 0
            heapq.heappush(out, ev)
            pushed = True

        if ev.evtype == ALLOC:
            seen[key] += 1
        elif ev.evtype == FREE:
            seen[key] -= 1

        # Remove when refcount drops to zero
        if seen[key] <= 0:
            del seen[key]
            if not pushed:
                heapq.heappush(out, ev)

    # The queue must still have an even number of events
    assert len(out) % 2 == 0
    return out


def count_lic_events(event_queue, measurement_points):
    """
    Count license events in the intervals given by measurement points.

    This ignores the group key in the events.
    """
    result = OrderedDict()
    lbtime_max = defaultdict(str)
    count = defaultdict(int)
    maxresult = defaultdict(int)

    # copy, as we modify it
    measurement_points = measurement_points[:]
    assert len(measurement_points) >= 2

    start_time = measurement_points.pop(0)
    end_time = measurement_points[-1]
    assert start_time is not None
    assert end_time is not None
    assert start_time < end_time

    lower_interval_border = start_time
    upper_interval_border = measurement_points.pop(0)
    assert lower_interval_border <= upper_interval_border

    while event_queue:
        ev = heapq.heappop(event_queue)

        while 1:
            # loop until the event is inside the current interval
            if ev.lbtime > upper_interval_border:
                # interval completed, store result and shift to the next one
                val = (count, maxresult, lbtime_max)
                result[(lower_interval_border, upper_interval_border)] = val

                # reset the maximum to the value at the upper interval border
                lbtime_max = defaultdict(str)
                maxresult_new = defaultdict(int)
                for key in maxresult.keys():
                    maxresult_new[key] = count[key]
                    lbtime_max[key] = upper_interval_border

                maxresult = maxresult_new

                # keep the current value of the counter
                new_count = defaultdict(int)
                new_count.update(count)
                count = new_count

                lower_interval_border = upper_interval_border
                if measurement_points:
                    # open next interval
                    upper_interval_border = measurement_points.pop(0)
                else:
                    break
            else:
                break

        if ev.lbtime > end_time:
            # reached the cutoff time
            break

        increment = 1 if ev.evtype == 1 else -1
        count[ev.mno] += increment
        # the count can be below zero temporarily,
        # when frees() and allocs() happen in the same second.
        #
        # assert count[ev.mno] >= 0, (ev.mno, count)

        if ev.lbtime < start_time:
            # only count max inside the interval
            continue

        if maxresult[ev.mno] < count[ev.mno]:
            lbtime_max[ev.mno] = ev.lbtime
            maxresult[ev.mno] = count[ev.mno]

    # add the last interval
    val = (count, maxresult, lbtime_max)
    result[(lower_interval_border, upper_interval_border)] = val
    return result


def count_lic_events_grouped(event_queue, measurement_points):
    """
    Count license events in the intervals given by measurement points.

    This uses the grouping key in the events.
    """
    result = OrderedDict()
    lbtime_max = {}
    count = {}
    maxresult = {}

    # copy, as we modify it
    measurement_points = measurement_points[:]
    assert len(measurement_points) >= 2

    start_time = measurement_points.pop(0)
    end_time = measurement_points[-1]
    assert start_time is not None
    assert end_time is not None
    assert start_time < end_time

    lower_interval_border = start_time
    upper_interval_border = measurement_points.pop(0)
    assert lower_interval_border <= upper_interval_border

    while event_queue:
        ev = heapq.heappop(event_queue)

        while 1:
            # loop until the event is inside the current interval
            if ev.lbtime > upper_interval_border:
                # interval completed, store result and shift to the next one
                val = (count, maxresult, lbtime_max)
                result[(lower_interval_border, upper_interval_border)] = val

                # reset the maximum to the value at the upper interval border
                lbtime_max = {}
                maxresult_new = {}
                for group in maxresult.keys():
                    maxresult_new[group] = defaultdict(int)
                    lbtime_max[group] = defaultdict(str)
                    for key in maxresult[group].keys():
                        maxresult_new[group][key] = count[group][key]
                        lbtime_max[group][key] = upper_interval_border

                maxresult = maxresult_new

                # keep the current value of the counter
                new_count = {}
                for group in count.keys():
                    new_count[group] = defaultdict(int)
                    new_count[group].update(count[group])
                count = new_count

                lower_interval_border = upper_interval_border
                if measurement_points:
                    # open next interval
                    upper_interval_border = measurement_points.pop(0)
                else:
                    break
            else:
                break

        if ev.lbtime > end_time:
            # reached the cutoff time
            break

        if ev.group not in count:
            count[ev.group] = defaultdict(int)

        count[ev.group][ev.mno] += 1 if ev.evtype == 1 else -1

        # the count can be below zero temporarily,
        # when frees() and allocs() happen in the same second.
        #
        # assert count[ev.mno] >= 0, (ev.mno, count)

        if ev.lbtime < start_time:
            # only count max inside the interval
            continue

        if ev.group not in maxresult:
            maxresult[ev.group] = defaultdict(int)
        if ev.group not in lbtime_max:
            lbtime_max[ev.group] = defaultdict(str)

        if maxresult[ev.group][ev.mno] < count[ev.group][ev.mno]:
            lbtime_max[ev.group][ev.mno] = ev.lbtime
            maxresult[ev.group][ev.mno] = count[ev.group][ev.mno]

    # add the last interval
    val = (count, maxresult, lbtime_max)
    result[(lower_interval_border, upper_interval_border)] = val
    return result


def is_read_lic(mno):
    """ Return true if the mno is a READ license"""
    # Handles -READ-Catia and other special cases...
    parts = mno.split('-')
    return bool(len(parts) > 2 and parts[2] == 'READ')


def get_full_lic_for_read(mno):
    """ Return the write license for a READ license"""
    # Handles -READ-Catia and other special cases...
    parts = mno.split('-')
    if len(parts) > 2 and parts[2] == 'READ':
        del parts[2]
    return "-".join(parts)


def condense_lics(licset):
    """ Handle special rules for READ licenses when counting

        READ licenses are eliminated from the set, if an identical
        full license was encountered in the set.

        E.g. if the set is ('CDB-040-READ', 'CDB-040') the result
        will be just ('CDB-040', ).
    """
    log = logging.getLogger('cdblic.condense_lics')
    lset = list(licset)
    new_licset = set()
    read_lics = [mno for mno in lset if is_read_lic(mno)]
    non_read_lics = set(mno for mno in lset if not is_read_lic(mno))
    for mno in read_lics:
        full_mno = get_full_lic_for_read(mno)
        if full_mno not in non_read_lics:
            new_licset.add(mno)
    for full_mno in non_read_lics:
        new_licset.add(full_mno)

    pre = len(lset)
    post = len(new_licset)
    if pre > post:
        log.debug("Condensed License Set Pre=%d Post=%d", pre, post)
    assert pre >= post
    return tuple(sorted(new_licset))


def count_license_sets(sessions):
    """ Count the license sets in the sessions
    """
    licsets = defaultdict(int)
    for session in sessions:
        lics = condense_lics(lic.mno for lic in session.included_licenses)
        licsets[lics] += 1
    return licsets


def count_license_sets_by_user(sessions):
    """ Count the license sets, grouped by users
    """
    user_sets = defaultdict(set)
    for session in sessions:
        lics = set(lic.mno for lic in session.included_licenses)
        user_sets[session.uname].update(lics)

    licsets = defaultdict(int)
    for values in user_sets.values():
        lics = condense_lics(values)
        licsets[lics] += 1
    return licsets


def count_license_sets_by_site_and_user(sessions, mapper):
    """ Count license sets per site, grouped by site and users
    """
    # collect unique user sets
    user_sets = defaultdict(set)
    for session in sessions:
        lics = set(lic.mno for lic in session.included_licenses)
        user_sets[session.uname].update(lics)

    # distribute by sites
    site_licsets = {}
    for uname, values in user_sets.items():
        lics = condense_lics(values)
        site = mapper(uname)
        if lics not in site_licsets:
            site_licsets[lics] = defaultdict(int)
        site_licsets[lics][site] += 1
    return site_licsets


# Howto count parallel sessions
#
# - pick a bucket interval
# - find the currently running sessions at the left
#   interval border as baseline
# - find all allocation and free events inside the interval
# - sort the alloc and free events by time
# - step through the list and add/subtract as needed
# - take note of the maximum and minimum values

def extract_sessions(start_time, end_time, tables, mapper=None):
    """ Extract the license sessions from the base table

        :Parameters:

            `start_time`: Datetime in Format 'yyyy.mm.dd hh:mm:ss'
            `end_time`: Datetime in Format 'yyyy.mm.dd hh:mm:ss'
    """
    log = logging.getLogger('cdblic.lsession')
    slog = logging.getLogger('cdblic.lsession.sessions')

    # pick the right iterator to use for this dataset
    cnt, iter = get_event_iter(start_time, end_time, tables)
    log.info("Found %d events to process between %s and %s",
             cnt, start_time, end_time)

    # Loop over lstatisics and aggregate lstatistics
    # events to license sessions.
    all_sessions = []
    open_sessions = []
    builder = SessionBuilder(pseudonymizer=mapper)
    for session in builder.process(iter):
        # Sessions with start and end time but zero duration can occur
        # if those sessions were allocated before the
        # beginning of the interval. Session.F() fixes those to identical timestamps.
        # Don't handle them for now (UGO).
        if session.start_time:
            slog.debug("Session: %s\tUser: %-20s\tStart: %s\t"
                       "End: %s\tDuration: %s\tLICS: %s",
                       session.pid, session.uname, session.start_time,
                       session.end_time, session.duration(),
                       ",".join(lic.mno for lic in session.included_licenses))
            all_sessions.append(session)
        else:
            open_sessions.append(session)
    leftover_sessions = builder.finalize()
    unique_pid_count = len(builder.all_pids)
    del iter
    del builder
    complete_sessions = len(all_sessions)
    slog.info("%d completed sessions with start and end time.",
              len(all_sessions))
    slog.info("%d unfinished sessions overlapping the start time.",
              len(open_sessions))
    slog.info("%d unfinished sessions overlapping the end time.",
              len(leftover_sessions))

    # Fixup licenses sessions that have no valid start or end date yet,
    # due to crashes or overlapping with the measurment interval
    usf = UnfinishedSessionFixer(start_time, end_time, tables['lstatistics'])
    for session in open_sessions + leftover_sessions:
        session = usf.process(session)
        slog.debug("Session: %s\tUser: %-20s\tStart: %s\t"
                   "End: %s\tDuration: %s\tLICS: %s",
                   session.pid, session.uname, session.start_time,
                   session.end_time, session.duration(),
                   ",".join(lic.mno for lic in session.included_licenses))
        all_sessions.append(session)

    log.info("Found %d complete sessions that needed no fixing.",
             complete_sessions)
    log.info("Fixed %d sessions that had no start time", usf.start_time_fix)
    log.info("  Fixed up %d sessions to start at interval begin",
             usf.start_interval_default)
    log.info("Fixed %d sessions that had no end time", usf.end_time_fix)
    log.info("  Fixed up %d zero-duration sessions to minimal duration.",
             usf.zero_duration_sessions)
    log.info("Found %d sessions in total", len(all_sessions))
    assert len(all_sessions) == unique_pid_count
    return all_sessions


def main(start_time, end_time):
    log = logging.getLogger('cdblic.lsession')

    # extract session data from lstatistics table
    all_sessions = extract_sessions(start_time, end_time)

    # Start frequency and maximum analysis

    # Convert the sessions into an event time stream that is countable
    log.info("Building event queue.")
    event_queue = build_event_queue(all_sessions)
    log.info("Built event queue with %d events", len(event_queue))

    points = [start_time, end_time]
    # and count a few things
    for time_key, counts in count_lic_events(event_queue, points).items():
        count, maxima, time_maxima = counts
        start_time, end_time = time_key
        # Global maxima inside the measurment interval
        maxima_items = sorted(
            ((k, v, time_maxima[k]) for k, v in maxima.items()),
            key=lambda x: x[1], reverse=True)
        maxima_table = "\n".join("%-30s\t%5d\t%s" % v for v in maxima_items)
        log.info("Maximum license allocations between %s and %s\n%s",
                 start_time, end_time, maxima_table)

        # License count at the end of the measurment interval
        current_items = sorted(
            ((k, v if v > 0 else 0) for k, v in count.items()),
            key=lambda x: x[1], reverse=True)
        current_table = "\n".join("%-30s\t%5d" % v for v in current_items)
        log.info("License state at %s\n%s",
                 end_time, current_table)


# Guard importing as main module
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING,
                        format='%(asctime)s %(message)s',
                        datefmt='%H:%M:%S')
    # start_time = '2013.07.01 00:00:00'
    # end_time = '2013.07.31 23:59:59'
    # start_time = '2014.10.21 06:00:00'
    # end_time = '2014.10.21 18:00:00'
    # sys.exit(main(start_time, end_time))
