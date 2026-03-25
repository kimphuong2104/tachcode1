#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
import datetime
import io
import os
import six
from pytz import utc as utc_tz

from cdb import CADDOK
from cdb import misc
from cdb import sqlapi
from cdb import transaction
from cdb import ue
from cdb import typeconversion
from cdb import sig

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import OBJECT_STORE
from cdb.objects.operations import operation
from cdb.constants import kOperationNew, kOperationDelete  # @UnresolvedImport


__all__ = ['CalendarProfile', 'CalendarException',
           'CalendarEntry', 'CalendarDayType']

# Forward declare some classes
fCalendarEntry = Forward(__name__ + ".CalendarEntry")
fCalendarProfile = Forward(__name__ + ".CalendarProfile")
fCalendarException = Forward(__name__ + ".CalendarException")
fCalendarDayType = Forward(__name__ + ".CalendarDayType")
fPerson = Forward("cdb.objects.org.Person")

weekdays = {0: 'mo', 1: 'tu', 2: 'we', 3: 'th', 4: 'fr', 5: 'sa', 6: 'su'}

DAY_TYPE_WORK = 0
DAY_TYPE_OFF = 1


def lose_time_info(date_or_datetime):
    """
    :param date_or_datetime: Date object with or without time
    :type date_or_datetime: datetime.date or datetime.datetime

    :returns: Date object without time
    :rtype: datetime.date

    :raises ValueError: if ``date_or_datetime`` is no date object
    """
    if not isinstance(date_or_datetime, datetime.date):
        raise ValueError("not a date: {}".format(date_or_datetime))
    if type(date_or_datetime) is datetime.datetime:
        return date_or_datetime.date()
    return date_or_datetime


def make_sql_date(some_date):
    """
    :param some_date: Date object to convert to SQL literal.
        If it's a string, assume it's in CE legacy format.
    :type some_date: str, datetime.date or datetime.datetime

    :returns: SQL date literal without time information
    :rtype: str

    :raises ValueError: if ``some_date`` is no str or date or
        a str, but not in CE legacy format.
    """
    if isinstance(some_date, six.string_types):
        date_only = typeconversion.from_legacy_date_format(some_date).date()
    else:
        date_only = lose_time_info(some_date)
    return sqlapi.SQLdbms_date(date_only)


def date2weekday(date):
    """
    Take a datetime or date object and return the weekday as a two letter
    English abbreviation. Eg: date2weekday(datetime.date(2010,1,1)) = 'fr'.
    """
    return weekdays[date.weekday()]


def date_range(start, end):
    """Return a list of datetime.datetime objects in between start and end"""
    r = (end + datetime.timedelta(days=1) - start).days
    return [start + datetime.timedelta(days=i) for i in six.moves.range(r)]


def _getNextDate(calendar_oid, myDate, distance, field):
    if not myDate:
        return myDate
    d = make_sql_date(myDate)
    sql = """ SELECT a.day
              FROM cdb_calendar_entry a, cdb_calendar_entry c
              WHERE c.day = {0} AND c.{4} = a.{4} - {1}
              AND a.calendar_profile_id = '{2}'
              AND a.personalnummer IS NULL AND a.cdb_project_id IS NULL
              AND c.calendar_profile_id = '{3}'
              AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
              AND a.day_type_id = '1'
          """.format(d, distance, calendar_oid, calendar_oid, field)
    result = sqlapi.RecordSet2(sql=sql)
    if not len(result):
        raise ue.Exception("cdb_cal_out_of_date")
    return lose_time_info(result[0]["day"])


def getNextStartDate(calendar_oid, myDate, distance=0):
    return _getNextDate(calendar_oid, myDate, distance, "late_work_idx")


def getNextEndDate(calendar_oid, myDate, distance=0):
    return _getNextDate(calendar_oid, myDate, distance, "early_work_idx")


def getDistance(calendar_oid, old_date, new_date):
    if not old_date or not new_date:
        return 0
    od = make_sql_date(old_date)
    nd = make_sql_date(new_date)
    sql = """SELECT day, early_work_idx, late_work_idx
             FROM cdb_calendar_entry c
             WHERE (day = %s OR day = %s)
             AND c.calendar_profile_id = '%s'
             AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
             ORDER BY day
          """ % (od, nd, calendar_oid)
    result = sqlapi.RecordSet2(sql=sql)
    return int(result[1]["early_work_idx"]) - int(result[0]["early_work_idx"])


def getWorkdays(calendar_oid, start_date, end_date):
    if not start_date or not end_date:
        return 0
    sd = make_sql_date(start_date)
    ed = make_sql_date(end_date)
    sql = """SELECT day, day_type_id,
             CASE WHEN day = %s THEN late_work_idx ELSE early_work_idx END AS value
             FROM cdb_calendar_entry c
             WHERE (day = %s OR day = %s)
             AND c.calendar_profile_id = '%s'
             AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
             ORDER BY day
          """ % (sd, sd, ed, calendar_oid)
    result = sqlapi.RecordSet2(sql=sql)
    value = 0
    if len(result) == 2:
        value = max(0, int(result[1]["value"]) - int(result[0]["value"]))
        if value or int(result[0]["day_type_id"]) == 1 or int(result[1]["day_type_id"]) == 1:
            value += 1
    elif len(result) == 1:
        if int(result[0]["day_type_id"]) == 1:
            value += 1
    return value


def getPersonalWorkdays(list_of_persno, start_date=None, end_date=None):
    """
    Return a dictionary of lists of (datetime, daytype_name) pairs for all
    workdays in the [start_date, end_date] interval for each person
    in the input list_of_persno.
    """
    return _getPersonDays(list_of_persno, start_date, end_date, DAY_TYPE_WORK)


def getPersonalDaysOff(list_of_persno, start_date=None, end_date=None):
    """
    Return a dictionary of lists of (datetime, daytype_name) pairs for all
    days off in the [start_date, end_date] interval for each person
    in the input list_of_persno.
    """

    return _getPersonDays(list_of_persno, start_date, end_date, DAY_TYPE_OFF)


def _getPersonDays(list_of_persno, start_date=None, end_date=None,
                   day_type=DAY_TYPE_OFF):
    """
    Return a dictionary of lists of (datetime, daytype_name) pairs for all
    days off or workdays in the [start_date, end_date] interval for each person
    in the input list_of_persno.
    """
    MAX_ELEMS_IN_CLAUSE = 500
    start_limit = end_limit = ''
    if start_date is not None:
        start_limit = (" AND %s <= day " % make_sql_date(start_date))
    if end_date is not None:
        end_limit = (" AND day <= %s " % make_sql_date(end_date))
    # Split the input list_of_persno into smaller lists of maximum size
    # MAX_ELEMS_IN_CLAUSE.
    list_of_groups = []
    if list_of_persno:
        # Filter out duplicates and split into distinct groups.
        list_of_persno = list(set(list_of_persno))
        cutoffs = list(six.moves.range(0, len(list_of_persno), MAX_ELEMS_IN_CLAUSE)) + [len(list_of_persno)]
        for n in six.moves.range(len(cutoffs) - 1):
            list_of_groups.append(list_of_persno[cutoffs[n]:cutoffs[n + 1]])
    else:
        return {}
    # Keep a dictionary of day types and their names in the current language.
    dayTypes = CalendarDayType.Query()
    dayTypeMap = {}
    for day_t in dayTypes:
        dayTypeMap[day_t.day_type_id] = day_t['name']
    day_dict = {}
    # Send SELECT queries for each group of persons and add up the day types of
    # the resulting records into the day dictionary.
    for pers_group in list_of_groups:
        persno_str = ", ".join(["'%s'" % sqlapi.quote(pers) for
                                pers in pers_group])
        sqlStatement1 = ("SELECT personalnummer, day, day_type_id "
                         "FROM   cdb_person_calendar_v "
                         "WHERE  personalnummer IN ( %s ) "
                         "  AND  day_off = %s "
                         " %s %s "
                         "ORDER BY day" %
                        (persno_str, day_type, start_limit, end_limit))
        # The 2nd query is to determine the valid personalnummer and fill up
        # the (at first) empty dictionary lists
        sqlStatement2 = ("SELECT personalnummer FROM angestellter "
                         "WHERE  personalnummer IN ( %s ) " % persno_str)
        pers_days = sqlapi.RecordSet2(sql=sqlStatement1)
        valid_pers_rec = sqlapi.RecordSet2(sql=sqlStatement2)
        valid_pers = [x.personalnummer for x in valid_pers_rec]
        for persno in valid_pers:
            day_dict[persno] = []
        if pers_days:
            for rec in pers_days:
                day_dict[rec.personalnummer].append(
                    (lose_time_info(rec.day), dayTypeMap[rec.day_type_id]))
    return day_dict


def getPersonalCapacities(start_date, end_date,
                          list_of_orgs=None, list_of_persnr=None):
    """
    Take a list of organization ids and a list of personalnummer strings and
    return a dictionary containing the daily capacities for each person that
    belongs to the organizations in list_of_orgs or is listed under
    list_of_persnr in the time interval [start_date, end_date].
    Only the persons who have a calendar profile and are marked as a resource
    are listed in the dictionary, with their personalnummer as keys.
    """
    if not list_of_orgs and not list_of_persnr:
        return {}
    # A limit on the number of elements allowed in the SQL 'WHERE IN' clause.
    MAX_ELEMS_IN_CLAUSE = 500
    start_date_sql = make_sql_date(start_date)
    end_date_sql = make_sql_date(end_date)
    list_of_groups = []
    # Split the input list_of_persnr into smaller lists of maximum size
    # MAX_ELEMS_IN_CLAUSE.
    if list_of_persnr:
        # Filter out duplicates.
        list_of_persnr = list(set(list_of_persnr))
        cutoffs = list(six.moves.range(0, len(list_of_persnr), MAX_ELEMS_IN_CLAUSE)) + [len(list_of_persnr)]
        for n in six.moves.range(len(cutoffs) - 1):
            list_of_groups.append(list_of_persnr[cutoffs[n]:cutoffs[n + 1]])
    capacity_dict = {}
    daymap = {}
    empty_template = []
    for i in six.moves.range((end_date - start_date).days + 1):
        daymap[(start_date + datetime.timedelta(days=i)).strftime("%d.%m.%Y")] = i
        empty_template.append(0)
    # Following, we perform SELECT queries to gather the capacities per day for
    # each person. They are then stored in the capacity dictionary.
    # The first SELECT query will gather all the persons that belong to the
    # orgs given in the list_of_orgs and the first MAX_ELEMS_IN_CLAUSE persons
    # from list_of_persnr. The second, third, etc. SELECT queries will gather
    # the remaining persons grouped in list_of_groups. It is assumed that
    # len(list_of_orgs) < MAX_ELEMS_IN_CLAUSE.
    idx = 0
    while(idx < len(list_of_groups) or list_of_orgs):
        if list_of_orgs:
            orgs_str = ", ".join(["'%s'" % sqlapi.quote(org) for
                                  org in list_of_orgs])
            sql_org = " org_id in ( %s ) " % orgs_str
        else:
            sql_org = " 0 = 1 "
        if idx < len(list_of_groups):
            persno_str = ", ".join(["'%s'" % sqlapi.quote(pers) for
                                    pers in list_of_groups[idx]])
            sql_pers = " personalnummer in ( %s ) " % persno_str
        else:
            sql_pers = " 0 = 1"
        sqlStatement = ("SELECT personalnummer, capacity, day "
                        "FROM   cdb_person_calendar_v "
                        "WHERE  %s <= day AND day <= %s "
                        "  AND  is_resource = 1 "
                        "  AND  ( %s OR %s ) "
                        "ORDER BY day" % (start_date_sql, end_date_sql,
                                          sql_pers, sql_org))
        capacityRecords = sqlapi.RecordSet2(sql=sqlStatement)
        for rset in capacityRecords:
            if rset.personalnummer not in capacity_dict:
                capacity_dict[rset.personalnummer] = list(empty_template)
            rset_day = rset.day.strftime("%d.%m.%Y")
            capacity_dict[rset.personalnummer][daymap[rset_day]] = rset.capacity
        idx += 1
        # All organization members are returned after the first SELECT
        list_of_orgs = []
    return capacity_dict


# pylint:disable=too-many-arguments
def utc_datetime(year, month, day, hour=0, minute=0, second=0, microsecond=0):
    # type: (...) -> AwareDateTime
    """
    Same API as datetime, but setting UTC as TZ-Info

    """
    return datetime.datetime(tzinfo=utc_tz, **locals())


class CalendarProfile(Object):
    __maps_to__ = "cdb_calendar_profile"
    __classname__ = "cdb_calendar_profile"

    Calendar = Reference_N(fCalendarEntry,
                           fCalendarEntry.calendar_profile_id ==
                           fCalendarProfile.cdb_object_id)

    Exceptions = Reference_N(fCalendarException,
                             fCalendarException.calendar_profile_id ==
                             fCalendarProfile.cdb_object_id)

    Persons = Reference_N(fPerson, fPerson.calendar_profile_id ==
                          fCalendarProfile.cdb_object_id)

    def date2day_type_id(self, date):
        """
        Take a datetime/date object and return the type of day associated to
        this day of the week (mo - su) in this calendar profile.
        """
        return self[weekdays[date.weekday()] + "_type_id"]

    def _reset_workday_index(self, ctx):
        self.generateWorkdayIndex(start=self.valid_from)

    def generateWorkdayIndex(self, start=None):
        CalendarException.reset_workday_index(
            calendar_profile_id=self.cdb_object_id,
            start_date=start,
        )

    def generateBaseCalendar(self, start=None, end=None):
        """
        Generate CalendarEntries for the base calendar associated to
        this calendar profile, from start until end.
        """
        if start is None:
            start = self.valid_from
        if end is None:
            end = self.valid_until
        s = start
        e = end
        if not isinstance(s, datetime.datetime):
            s = datetime.datetime.combine(s, datetime.time.min)
        if not isinstance(e, datetime.datetime):
            e = datetime.datetime.combine(e, datetime.time.min)

        # Create a list of datetime.datetime days, which are to be generated
        days_in_profile = date_range(s, e)
        # Create a dictionary of exceptions hashed by day
        exception_days = {}
        for exc in self.Exceptions:
            exception_days[exc.day] = exc
        # Go through the list of days in the profile and generate all the
        # corresponding CalendarEntries. If the day corresponds to
        # an exception, then create an exception day_type_id instead.
        for cal_day in days_in_profile:
            if cal_day in exception_days:
                dti = exception_days[cal_day].day_type_id
                desc = exception_days[cal_day].description
            else:
                dti = self.date2day_type_id(cal_day)
                desc = ''
            chg_ctrl = CalendarEntry.MakeChangeControlAttributes()
            CalendarEntry.Create(day=cal_day,
                                 day_type_id=dti,
                                 description=desc,
                                 calendar_profile_id=self.cdb_object_id,
                                 weekday=date2weekday(cal_day),
                                 cdb_cpersno=chg_ctrl['cdb_cpersno'],
                                 cdb_mpersno=chg_ctrl['cdb_mpersno'],
                                 cdb_cdate=chg_ctrl['cdb_cdate'],
                                 cdb_mdate=chg_ctrl['cdb_mdate'])

    def deleteBaseCalendarEntries(self, from_date=None, to_date=None,
                                  invert=False):
        """
        Delete all calendar entries in the date range from the base calendar
        """
        if from_date is not None and to_date is not None:
            if from_date <= to_date:
                if invert:
                    day_clause = " AND (day >= %s OR day <= %s) " % \
                        (make_sql_date(to_date),
                         make_sql_date(from_date))
                else:
                    day_clause = " AND (day >= %s AND day <= %s) " % \
                        (make_sql_date(from_date),
                         make_sql_date(to_date))

            else:
                raise ValueError("Can not delete Calendar Entries: Date "
                                 "inconsistency. From_date:%s > To_date:%s." %
                                 (from_date, to_date))
        elif from_date is not None:
            day_clause = " AND day >= %s " % make_sql_date(from_date)
        elif to_date is not None:
            day_clause = " AND day <= %s " % make_sql_date(to_date)
        else:
            day_clause = ''

        with transaction.Transaction():
            # delete
            sqlapi.SQLdelete("FROM cdb_calendar_entry "
                             "WHERE (cdb_project_id = '' OR "
                             "       cdb_project_id is NULL)"
                             "  AND (personalnummer = '' OR "
                             "       personalnummer is NULL)"
                             "  AND calendar_profile_id = '%s' %s" %
                             (self.cdb_object_id, day_clause))
            # cleanup
            sqlapi.SQLdelete("FROM cdb_object "
                             "WHERE relation = 'cdb_calendar_entry' AND "
                             "      id NOT IN (SELECT cdb_object_id "
                             "                 FROM cdb_calendar_entry)")

    def insertException(self, calException):
        """ Insert an Exception into the base calendar. """
        date = calException.day
        if isinstance(date, datetime.datetime):
            date = date.date()
        valid_from = self.valid_from
        if isinstance(valid_from, datetime.datetime):
            valid_from = valid_from.date()
        valid_to = self.valid_to
        if isinstance(valid_to, datetime.datetime):
            valid_to = valid_to.date()
        if (calException is None or
                date < valid_from or
                date > valid_to):
            return
        # First delete the old CalendarEntry, then add the new corresponding one
        self.deleteBaseCalendarEntries(from_date=date, to_date=date)
        chg_ctrl = CalendarEntry.MakeChangeControlAttributes()
        CalendarEntry.Create(day=calException.day,
                             day_type_id=calException.day_type_id,
                             description=calException.description,
                             calendar_profile_id=self.cdb_object_id,
                             weekday=date2weekday(date),
                             cdb_cpersno=chg_ctrl['cdb_cpersno'],
                             cdb_mpersno=chg_ctrl['cdb_mpersno'],
                             cdb_cdate=chg_ctrl['cdb_cdate'],
                             cdb_mdate=chg_ctrl['cdb_mdate'])

    def importFromICS(self, filename):
        """
        Insert holiday exceptions into the calendar profile from icalendar
        format. Creates CalendarException objects with day_type holiday and
        updates the base calendar of this profile. Currently only supports
        events recurring on a yearly basis (or every N years).
        """
        import icalendar

        # filename shoud be unicode and file content should be utf8
        assert isinstance(filename, six.text_type)
        with io.open(filename, 'rU', encoding="utf8") as f:
            cal = icalendar.Calendar.from_ical(f.read())

        # keep the maximum event date in order to compute the last year of the
        # recurring yearly events
        max_date = self.valid_from
        if isinstance(max_date, datetime.datetime):
            max_date = exc_day.date()
        yearly_events = []
        one_time_events = []
        for event in cal.walk('VEVENT'):
            if 'DTSTART' in event:
                date = event.decoded('DTSTART')
                if date > max_date:
                    max_date = date
                if 'SUMMARY' in event:
                    summary = event.decoded('SUMMARY')
                else:
                    summary = ''
                if ('RRULE' in event and
                        event.decoded('RRULE').get('FREQ', [''])[0] == 'YEARLY'):
                    interval = event.decoded('RRULE').get('INTERVAL', [1])[0]
                    yearly_events.append((date, summary, interval))
                else:
                    one_time_events.append((date, summary))
        self._insertOneTimeEventsFromICS(one_time_events)
        self._insertRecurringEventsFromICS(yearly_events, max_date)

    def _insertOneTimeEventsFromICS(self, events):
        # Creates CalendarExceptions to current profile if the event days are
        # within the validity period [self.valid_from, self.valid_until]
        for date, summary in events:
            if self.valid_from <= date <= self.valid_until:
                exc_day = date
                if isinstance(exc_day, datetime.datetime):
                    exc_day = exc_day.date()
                chg_ctrl = CalendarException.MakeChangeControlAttributes()

                # If there is already an existing CalendarException for
                # this day, then first delete the old one
                # FIXME: Object.ByKeys should handle date/datetime object
                oldExc = CalendarException.ByKeys(self.cdb_object_id, exc_day)
                if oldExc:
                    operation(kOperationDelete, oldExc)
                    misc.cdblogv(misc.kLogMsg, 7,
                                 "cdbcalendar.CalendarProfile"
                                 ".importFromICS: CalendarException "
                                 "(%s - %s) overwritten." %
                                 (self.cdb_object_id, exc_day))
                    OBJECT_STORE.clear()
                operation(kOperationNew,
                          CalendarException,
                          day=exc_day,
                          calendar_profile_id=self.cdb_object_id,
                          day_type_id='3',  # Standard Holiday
                          description=summary,
                          cdb_cpersno=chg_ctrl['cdb_cpersno'],
                          cdb_mpersno=chg_ctrl['cdb_mpersno'],
                          cdb_cdate=chg_ctrl['cdb_cdate'],
                          cdb_mdate=chg_ctrl['cdb_mdate'])

    def _insertRecurringEventsFromICS(self, events, max_date):
        # Generate a list of single events based on the recurrence information
        # and the maximum date in the ics file and then generate them with the
        # method for one time events
        single_events = []
        for date, summary, interval in events:
            for year_cnt in six.moves.range(date.year, max_date.year + 1, interval):
                single_events.append((date.replace(year=year_cnt), summary))
        self._insertOneTimeEventsFromICS(single_events)

    # pre
    def _saveProfileChanges(self, ctx):
        # Check the changes performed in the mask and save the changed items
        # 9706: The scope (%s - %s) is not valid!
        if typeconversion.from_legacy_date_format(ctx.dialog.valid_from).date() > \
                typeconversion.from_legacy_date_format(ctx.dialog.valid_until).date():
            raise ue.Exception("cdb_cal_prof_chg", ctx.dialog.valid_from,
                               ctx.dialog.valid_until)
        if ctx.action == 'modify':
            if (ctx.dialog.valid_from != ctx.object.valid_from or
                    ctx.dialog.valid_until != ctx.object.valid_until):
                ctx.keep('old_valid_from', ctx.object.valid_from)
                ctx.keep('old_valid_until', ctx.object.valid_until)
            for day in ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']:
                if (ctx.dialog[day + '_type_id'] !=
                        ctx.object[day + '_type_id']):
                    ctx.keep('old_' + day + '_type_id',
                        ctx.object[day + '_type_id'])

    def _profileChangeDelete(self, old_start, old_end, new_start, new_end):
        # Delete entries from the base calendar depending on the changed dates
        one_day = datetime.timedelta(days=1)

        o_start = old_start
        o_end = old_end
        n_start = new_start
        n_end = new_end
        if not isinstance(o_start, datetime.datetime):
            o_start = datetime.datetime.combine(o_start, datetime.time.min)
        if not isinstance(o_end, datetime.datetime):
            o_end = datetime.datetime.combine(o_end, datetime.time.min)
        if not isinstance(n_start, datetime.datetime):
            n_start = datetime.datetime.combine(n_start, datetime.time.min)
        if not isinstance(n_end, datetime.datetime):
            n_end = datetime.datetime.combine(n_end, datetime.time.min)
        # -----<o_s---[n_s---n_e]---o_e>----------------------
        if o_start <= n_start and n_end <= o_end:
            self.deleteBaseCalendarEntries(from_date=n_start - one_day,
                                           to_date=n_end + one_day,
                                           invert=True)
        # -----[n_s---n_e]-------<o_s---o_e>-----------------  OR
        # -----<o_s---o_e>-------[n_s---n_e]-----------------
        elif n_end <= o_start or o_end <= n_start:
            self.deleteBaseCalendarEntries()
        # -----[n_s---<o_s---n_e]---o_e>---------------------
        elif n_start < o_start and o_start < n_end and \
            n_end <= o_end:
            self.deleteBaseCalendarEntries(from_date=n_end + one_day)
        # -----<o_s---[n_s---o_e>---n_e]-------------------
        elif o_start <= n_start and n_start < o_end and \
            o_end < n_end:
            self.deleteBaseCalendarEntries(to_date=n_start - one_day)
        # -----[n_s---<o_s---o_e>---n_e]-------------------
        # DO NOTHING

    def _profileChangeGenerate(self, old_start, old_end, new_start, new_end):
        # Generate entries in the base calendar depending on the changed dates
        one_day = datetime.timedelta(days=1)
        o_start = old_start
        o_end = old_end
        n_start = new_start
        n_end = new_end
        if not isinstance(o_start, datetime.datetime):
            o_start = datetime.datetime.combine(o_start, datetime.time.min)
        if not isinstance(o_end, datetime.datetime):
            o_end = datetime.datetime.combine(o_end, datetime.time.min)
        if not isinstance(n_start, datetime.datetime):
            n_start = datetime.datetime.combine(n_start, datetime.time.min)
        if not isinstance(n_end, datetime.datetime):
            n_end = datetime.datetime.combine(n_end, datetime.time.min)
        # -----[n_s---n_e]-------<o_s---o_e>-----------------  OR
        # -----<o_s---o_e>-------[n_s---n_e]-----------------
        if n_end <= o_start or o_end <= n_start:
            self.generateBaseCalendar(n_start, n_end)
        # -----[n_s---<o_s---n_e]---o_e>---------------------
        elif n_start < o_start and o_start < n_end and \
            n_end <= o_end:
            self.generateBaseCalendar(n_start, o_start - one_day)
        # -----<o_s---[n_s---o_e>---n_e]-------------------
        elif o_start <= n_start and n_start < o_end and \
            o_end < n_end:
            self.generateBaseCalendar(o_end + one_day, n_end)
        # -----[n_s---<o_s---o_e>---n_e]-------------------
        elif n_start < o_start and o_end < n_end:
            # TODO: just one function call - doesn't matter atm, since the
            # generation is performed with many Create() calls
            self.generateBaseCalendar(n_start, o_start - one_day)
            self.generateBaseCalendar(o_end + one_day, n_end)
        # -----<o_s---[n_s---n_e]---o_e>----------------------
        # DO NOTHING

    # post
    def _generateOwnCalendar(self, ctx):
        self.generateBaseCalendar()

    # post
    def _updateProfile(self, ctx):
        # Update the calendar profile accroding to the changes made in the mask
        ue_args_attrs = ctx.ue_args.get_attribute_names()
        # 1. DELETE old entries which lie outside of the new date interval
        if 'old_valid_from' in ue_args_attrs:
            self._profileChangeDelete(
                typeconversion.from_legacy_date_format(ctx.ue_args['old_valid_from']).date(),
                typeconversion.from_legacy_date_format(ctx.ue_args['old_valid_until']).date(),
                self.valid_from,
                self.valid_until)
        # 2. UPDATE already existing entries which are in the new interval
        for day in ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']:
            if 'old_' + day + '_type_id' in ue_args_attrs:
                sqlapi.SQLupdate("cdb_calendar_entry SET day_type_id = '%s' "
                                 "WHERE weekday = '%s' AND "
                                 "      calendar_profile_id = '%s' AND "
                                 "     (cdb_project_id = '' OR "
                                 "      cdb_project_id is NULL) AND "
                                 "     (personalnummer = '' OR "
                                 "      personalnummer is NULL)" %
                                 (self[day + '_type_id'], day,
                                  self.cdb_object_id))
        # 3. GENERATE new entries to fill up the interval using the new profile
        if 'old_valid_from' in ue_args_attrs:
            self._profileChangeGenerate(
                typeconversion.from_legacy_date_format(ctx.ue_args['old_valid_from']).date(),
                typeconversion.from_legacy_date_format(ctx.ue_args['old_valid_until']).date(),
                self.valid_from,
                self.valid_until)

    # post
    def _deleteBaseEntries(self, ctx):
        self.deleteBaseCalendarEntries()

    # now
    def _importHolidaysFromICS(self, ctx):
        # 9710: The .ics file could not be imported. Error:\n%s.
        server_filename = os.path.join(CADDOK.TMPDIR, "download.ics")
        if ctx.mode == "now":
            ctx.download_from_client(ctx.dialog.ics_file, server_filename, 0)
        elif ctx.mode == "post":
            try:
                self.importFromICS(server_filename)
            except Exception as e:
                raise ue.Exception("cdb_cal_prof_imp", six.text_type(e))

    event_map = {
        (('create', 'copy', 'modify'), 'pre'): ('_saveProfileChanges'),
        (('create', 'relship_copy'), 'post'): ('_generateOwnCalendar', '_reset_workday_index'),
        (('modify'), 'post'): ('_updateProfile', '_reset_workday_index'),
        (('delete'), 'post'): ('_deleteBaseEntries'),
        (('cdb_cal_prof_imp'), ('now', 'post')): ('_importHolidaysFromICS')
        }


class CalendarEntry(Object):
    """
    A calendar entry object corresponds to a day in the calendar. There are two
    types of calendar entries: neutral entries and personal/project entries.

    Neutral calendar entries have empty 'personalnummer' and 'cdb_project_id'
    fields and have a non-empty 'calendar_profile_id' field, according to
    the calendar profile they belong to. Neutral calendar entries are created
    from profile start_date until profile end_date at the creation time of a
    calendar profile. They constitute the "base calendar" associated to a
    calendar profile. Base calendar entries are only created/deleted from code
    and never from the GUI.

    Personal/project calendar entries have an empty 'calendar_profile_id' field
    and either a non-empty 'personalnummer' or a non-empty 'cdb_project_id'
    field, showing that they belong to either a person or a project. These
    calendar entries are created manually by the users / project administrators
    to manage their personal or project calendars, respectively. A calendar
    entry can never have both non-empty personalnummer and cdb_project_id
    fields at the same time.
    """
    __maps_to__ = "cdb_calendar_entry"
    __classname__ = "cdb_calendar_entry"

    CalendarProfile = Reference_1(fCalendarProfile,
                                  fCalendarEntry.calendar_profile_id)

    Person = Reference_N(fPerson, fPerson.personalnummer ==
                         fCalendarEntry.personalnummer)

    DayType = Reference_1(fCalendarDayType, fCalendarEntry.day_type_id)

    # pre_mask
    def _checkOwner(self, ctx):
        # A calendar entry belongs to either a person, a project or neither.
        # Disallow owner changes to calendar entries which have an owner.
        if self.personalnummer != '' or self.cdb_project_id != '':
            ctx.set_fields_readonly(['mapped_pers_name', 'mapped_proj_name'])
        # Project CalendarEntries have undefined capacity.
        if self.cdb_project_id != '':
            ctx.set('capacity', '')
            ctx.set_readonly('capacity')
        # Personal CalendarEntries wih a is_day_off_type of 1 have 0 capacity
        elif self.personalnummer != '' and self.day_type_id != '':
            day_type = CalendarDayType.ByKeys(self.day_type_id)
            if day_type.is_day_off_type == 1:
                ctx.set('capacity', '0')
                ctx.set_readonly('capacity')

    # pre_mask
    @classmethod
    def _presetOwner(cls, ctx):
        # Set personalnummer or cdb_project_id in the mask for multi calendar
        # entry and make them read only when there is a parent owner.
        if 'angestellter' in ctx.parent_keys:
            ctx.set('personalnummer', ctx.parent['personalnummer'])
            ctx.set_fields_readonly(['mapped_pers_name', 'mapped_proj_name'])
        elif 'cdbpcs_project' in ctx.parent_keys:
            ctx.set('capacity', '')
            ctx.set_readonly('capacity')
            ctx.set('cdb_project_id', ctx.parent['cdb_project_id'])
            ctx.set_fields_readonly(['mapped_pers_name', 'mapped_proj_name'])

    # pre
    @classmethod
    def _assureOneOwner(cls, ctx):
        # Disallow the manual creation of CalendarEntries without owners
        # 9705: The calendar entry must be assigned to
        #       either a person or a project.
        if ctx.dialog.mapped_pers_name == '' and \
                ctx.dialog.mapped_proj_name == '':
            if 'mapped_calendar_profile' in ctx.dialog.get_attribute_names():
                if ctx.dialog.mapped_calendar_profile == '':
                    raise ue.Exception("cdb_cal_owner")
            else:
                raise ue.Exception("cdb_cal_owner")

    # pre
    @classmethod
    def _checkDates(cls, ctx):
        # 9706: The scope (%s - %s) is not valid!
        if typeconversion.from_legacy_date_format(ctx.dialog.day_from).date() > \
                typeconversion.from_legacy_date_format(ctx.dialog.day_until).date():
            raise ue.Exception("cdb_cal_prof_chg", ctx.dialog.day_from,
                               ctx.dialog.day_until)

    # post-mask
    def _keepOldDay(self, ctx):
        ctx.keep('old_day', ctx.object.day)

    # dialogitem_change
    def _disallowMultipleOwners(self, ctx):
        # On selecting an owner person, empty the project fields in the mask;
        # on selecting an owner project, empty the person fields and capacity.
        if ctx.changed_item == 'mapped_pers_name' and \
                ctx.dialog.mapped_pers_name != '':
            ctx.set('mapped_proj_name', '')
            ctx.set('cdb_project_id', '')
        elif ctx.changed_item == 'mapped_proj_name' and \
                 ctx.dialog.mapped_proj_name != '':
            ctx.set('mapped_pers_name', '')
            ctx.set('personalnummer', '')
            ctx.set('capacity', '')
            ctx.set_readonly('capacity')

    # dialogitem_change
    def _setCapacityOnDayTypeChange(self, ctx):
        # When the day type is changed, find out whether it is a day off or not
        # and set the capacity according to the owner of the CalendarEntry
        if ctx.changed_item == 'day_type_id' and \
                ctx.dialog.day_type_id != '':
            day_type = CalendarDayType.ByKeys(ctx.dialog.day_type_id)
            if day_type.is_day_off_type == 1:
                if ctx.dialog.mapped_pers_name == '' and \
                        ctx.dialog.mapped_proj_name != '':
                    ctx.set('capacity', '')
                    ctx.set_readonly('mapped_pers_name')
                elif ctx.dialog.mapped_pers_name != '' and \
                         ctx.dialog.mapped_proj_name == '':
                    ctx.set('capacity', '0')
                else:
                    ctx.set('capacity', '0')
                ctx.set_readonly('capacity')
            else:
                if ctx.dialog.mapped_pers_name == '' and \
                        ctx.dialog.mapped_proj_name != '':
                    ctx.set('capacity', '')
                    ctx.set_readonly('mapped_pers_name')
                elif ctx.dialog.mapped_pers_name != '' and \
                         ctx.dialog.mapped_proj_name == '':
                    from cdb.objects.org import Person
                    pers = Person.Query("name = '%s'" %
                                        ctx.dialog.mapped_pers_name)
                    ctx.set('capacity', pers[0].capacity)
                    ctx.set_writeable('capacity')

    # post
    def _updateWeekday(self, ctx):
        day = self.day
        if isinstance(day, datetime.datetime):
            day = day.date()
        sqlapi.SQLupdate("cdb_calendar_entry SET weekday = '%s' "
                         "WHERE cdb_object_id = '%s'" %
                         (date2weekday(day),
                          self.cdb_object_id))

    # now
    @classmethod
    def _makeMultiEntryPerson(cls, ctx):
        # Multi entry operation for calendar entries.
        if ctx.dialog.personalnummer != '':
            cls._multiEntryPersonalCalendar(ctx)
        ctx.refresh_tables(['cdb_calendar_entry'])

    @classmethod
    def _multiEntryPersonalCalendar(cls, ctx):
        # Go through the date range entered in the mask and check against
        # already existing entries. Then, if the day_off_type has changed, or
        # capacity has changed, delete the old entries and enter new ones.
        cal_day_type = CalendarDayType.ByKeys(ctx.dialog.day_type_id)
        new_day_off = cal_day_type.is_day_off_type
        try:
            new_capactity = float(ctx.dialog.capacity)
        except ValueError:
            new_capactity = 0
        day_rec = sqlapi\
            .RecordSet2(sql="SELECT day, day_type_id, capacity "
                        "FROM   cdb_person_calendar_v "
                        "WHERE  personalnummer = '%s' "
                        "  AND  %s <= day AND day <= %s "
                        "ORDER BY day " %
                        (sqlapi.quote(ctx.dialog.personalnummer),
                         make_sql_date(ctx.dialog.day_from),
                         make_sql_date(ctx.dialog.day_until)))
        chg_ctrl = CalendarEntry.MakeChangeControlAttributes()
        for rec in day_rec:
            if ((rec.day_type_id != new_day_off) or
                    rec.capacity != new_capactity):
                # Create a new one with mask attributes
                param = {'day': rec.day,
                         'personalnummer': ctx.dialog.personalnummer,
                         'cdb_project_id': '',
                         'calendar_profile_id': '',
                         'day_type_id': ctx.dialog.day_type_id,
                         'description': ctx.dialog.description,
                         'capacity': new_capactity,
                         'weekday': date2weekday(rec.day.date()),
                         'cdb_cpersno': chg_ctrl['cdb_cpersno'],
                         'cdb_mpersno': chg_ctrl['cdb_mpersno'],
                         'cdb_cdate': chg_ctrl['cdb_cdate'],
                         'cdb_mdate': chg_ctrl['cdb_mdate']}
                cal_entry = CalendarEntry(**param)
                if cal_entry.CheckAccess('create'):
                    # Delete the old one (if exists)
                    # 9711: You don't have permission to create new calendar
                    #       entries.
                    oldEntry = CalendarEntry\
                        .Query("personalnummer = '%s' AND day = %s" %
                               (sqlapi.quote(ctx.dialog.personalnummer),
                                make_sql_date(rec.day)))
                    if oldEntry:
                        oldEntry.Delete()
                    CalendarEntry.Create(**param)
                else:
                    raise ue.Exception("cdb_cal_entry_new")

    event_map = {
        (('create', 'copy', 'modify'), 'pre_mask'): ('_checkOwner'),
        (('cdb_cal_entry_multi_new'), 'pre_mask'): ('_presetOwner'),
        (('create', 'copy', 'modify', 'cdb_cal_entry_multi_new'),
         'dialogitem_change'): ('_disallowMultipleOwners',
                                '_setCapacityOnDayTypeChange'),
        (('create', 'copy', 'modify', 'cdb_cal_entry_multi_new'),
            'pre'): ('_assureOneOwner'),
        (('modify'), 'pre'): ('_keepOldDay'),
        (('cdb_cal_entry_multi_new'), 'pre'): ('_checkDates'),
        (('create', 'copy', 'modify'), 'post'): ('_updateWeekday'),
        (('cdb_cal_entry_multi_new'), 'now'): ('_makeMultiEntryPerson'),
        }


class CalendarException(Object):
    __maps_to__ = "cdb_cal_prof_exc"
    __classname__ = "cdb_cal_prof_exc"

    CalendarProfile = Reference_1(fCalendarProfile,
                                  fCalendarException.calendar_profile_id)

    def _remember_value(self, ctx):
        sd = make_sql_date(self.day)
        base_where = """calendar_profile_id = '%s' AND personalnummer IS NULL
                       AND cdb_project_id IS NULL""" % self.calendar_profile_id
        where = "day = %s AND %s" % (sd, base_where)
        old_idx = sqlapi.RecordSet2(
            sql="SELECT early_work_idx FROM cdb_calendar_entry WHERE %s" %
            (where))[0]["early_work_idx"]
        ctx.keep("old_early_work_idx", int(old_idx))

    def _adjust_workday_index(self, ctx):
        if "old_early_work_idx" in ctx.ue_args.get_attribute_names():
            old_idx = int(ctx.ue_args["old_early_work_idx"])
            CalendarException.adjust_workday_index(calendar_profile_id=self.calendar_profile_id, start_date=self.day, old_idx=old_idx)

    @classmethod
    def adjust_workday_index(cls, calendar_profile_id, start_date, old_idx):
        with transaction.Transaction():
            sd = make_sql_date(start_date)
            base_where = """calendar_profile_id = '%s' AND personalnummer IS NULL
                           AND cdb_project_id IS NULL""" % calendar_profile_id
            where = "day = %s AND %s" % (sd, base_where)

            upd0 = """
                   cdb_calendar_entry SET early_work_idx = (SELECT count(*)
                   FROM cdb_calendar_entry a
                   WHERE cdb_calendar_entry.day >= a.day
                   AND a.day_type_id = '1' AND a.calendar_profile_id = '%s'
                   AND a.personalnummer IS NULL AND a.cdb_project_id IS NULL)
                   WHERE %s
                   """ % (calendar_profile_id, where)
            sqlapi.SQLupdate(upd0)
            new_idx = sqlapi.RecordSet2(
                sql="SELECT early_work_idx FROM cdb_calendar_entry WHERE %s" %
                (where))[0]["early_work_idx"]
            modification = int(old_idx) - int(new_idx)

            where = "day > %s AND %s" % (sd, base_where)
            upd1 = "cdb_calendar_entry SET early_work_idx = early_work_idx - %s WHERE %s" % (modification, where)
            where = "day >= %s AND %s" % (sd, base_where)
            if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
                upd2 = "cdb_calendar_entry SET late_work_idx = CASE WHEN day_type_id::int > 1 THEN early_work_idx +1 ELSE early_work_idx END WHERE %s" % (
                    where)
            else:
                upd2 = "cdb_calendar_entry SET late_work_idx = CASE WHEN day_type_id> 1 THEN early_work_idx +1 ELSE early_work_idx END WHERE %s" % (where)

            sqlapi.SQLupdate(upd1)
            sqlapi.SQLupdate(upd2)

    @classmethod
    def reset_workday_index(cls, calendar_profile_id, start_date=None):
        with transaction.Transaction():
            where = """calendar_profile_id = '%s' AND personalnummer IS NULL
                       AND cdb_project_id IS NULL""" % calendar_profile_id
            if start_date:
                sd = make_sql_date(start_date)
                where += " AND day >= %s" % sd
            if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
                # the SQL statement below executes extremely slow in an SQLite db
                idx = 1
                for entry in CalendarEntry.Query(where, order_by="day"):
                    if entry.day_type_id == "1":
                        entry.early_work_idx = idx
                        entry.late_work_idx = idx
                        idx += 1
                    else:
                        entry.early_work_idx = idx - 1
                        entry.late_work_idx = idx
            elif sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
                upd1 = """
                       cdb_calendar_entry SET early_work_idx = (SELECT count(*)
                       FROM cdb_calendar_entry a
                       WHERE cdb_calendar_entry.day >= a.day
                       AND a.day_type_id::Int = 1 AND a.calendar_profile_id = '%s'
                       AND a.personalnummer IS NULL AND a.cdb_project_id IS NULL)
                       WHERE %s
                       """ % (calendar_profile_id, where)

                upd2 = "cdb_calendar_entry SET late_work_idx = early_work_idx WHERE %s" % (where)
                where += " AND day_type_id::Int > 1"
                upd3 = "cdb_calendar_entry SET late_work_idx = late_work_idx+1 WHERE %s" % (where)

                sqlapi.SQLupdate(upd1)
                sqlapi.SQLupdate(upd2)
                sqlapi.SQLupdate(upd3)
            else:
                upd1 = """
                       cdb_calendar_entry SET early_work_idx = (SELECT count(*)
                       FROM cdb_calendar_entry a
                       WHERE cdb_calendar_entry.day >= a.day
                       AND a.day_type_id = 1 AND a.calendar_profile_id = '%s'
                       AND a.personalnummer IS NULL AND a.cdb_project_id IS NULL)
                       WHERE %s
                       """ % (calendar_profile_id, where)

                upd2 = "cdb_calendar_entry SET late_work_idx = early_work_idx WHERE %s" % (where)
                where += " AND day_type_id > 1"
                upd3 = "cdb_calendar_entry SET late_work_idx = late_work_idx+1 WHERE %s" % (where)

                sqlapi.SQLupdate(upd1)
                sqlapi.SQLupdate(upd2)
                sqlapi.SQLupdate(upd3)

    # pre
    def _saveChanges(self, ctx):
        # Check changes made in the mask and save modified fields in ue_args
        smth_changed = False
        attrs_to_check = ['calendar_profile_id', 'day',
                          'day_type_id', 'description']
        for attribute in attrs_to_check:
            if (ctx.dialog[attribute] != ctx.object[attribute]):
                smth_changed = True
        if smth_changed:
            ctx.keep('smth_changed', 'yes')
        ctx.keep('old_calendar_profile_id', ctx.object.calendar_profile_id)
        ctx.keep('old_day', ctx.object.day)

    # post
    def _updateCalendarEntry(self, ctx):
        # If in 'modify', check what was changed in the mask and update the
        # corresponding CalendarEntry in the base calendar. If in 'copy' or
        # 'create', just create a new entry.
        prof_start = self.CalendarProfile.valid_from
        prof_end = self.CalendarProfile.valid_until
        exc_day = self.day
        if isinstance(exc_day, datetime.datetime):
            exc_day = exc_day.date()
        if ctx.action == 'modify':
            if 'smth_changed' in ctx.ue_args.get_attribute_names():
                day = make_sql_date(ctx.ue_args['old_day'])
                cal_prof = ctx.ue_args['old_calendar_profile_id']
            else:
                return
        else:
            day = make_sql_date(self.day)
            cal_prof = self.calendar_profile_id
        # If in 'modify', then first delete the old CalendarEntry.
        res = CalendarEntry.Query("day = %s AND calendar_profile_id = '%s'"
                                  % (day, cal_prof))
        if len(res) >= 1:
            cal_entry = res[0]
            cal_entry.Delete()
        if prof_start <= exc_day and exc_day <= prof_end:
            chg_ctrl = CalendarEntry.MakeChangeControlAttributes()
            CalendarEntry\
                .Create(day=self.day,
                        day_type_id=self.day_type_id,
                        description=self.description,
                        calendar_profile_id=self.calendar_profile_id,
                        weekday=date2weekday(exc_day),
                        cdb_cpersno=chg_ctrl['cdb_cpersno'],
                        cdb_mpersno=chg_ctrl['cdb_mpersno'],
                        cdb_cdate=chg_ctrl['cdb_cdate'],
                        cdb_mdate=chg_ctrl['cdb_mdate'])

    # post
    def _deleteCalendarEntry(self, ctx):
        # When the CalendarException is deleted, delete the corresponding
        # CalendarEntry in the base calendar and replace it with a standard one
        res = CalendarEntry.Query("day = %s AND calendar_profile_id = '%s'" %
                                  (make_sql_date(ctx.object.day),
                                   ctx.object.calendar_profile_id))
        if len(res) >= 1:
            cal_entry = res[0]
            cal_entry.Delete()
        cal_prof = CalendarProfile.ByKeys(ctx.object.calendar_profile_id)
        cal_prof.generateBaseCalendar(
            start=typeconversion.from_legacy_date_format(ctx.object.day).date(),
            end=typeconversion.from_legacy_date_format(ctx.object.day).date())

    # pre
    def _checkInterval(self, ctx):
        prof_start = self.CalendarProfile.valid_from
        prof_end = self.CalendarProfile.valid_until
        exc_day = self.day
        if isinstance(exc_day, datetime.datetime):
            exc_day = exc_day.date()
        if prof_start > exc_day or exc_day > prof_end:
            raise ue.Exception("cdb_cal_outside_range")

    # pre
    @classmethod
    def _check_multi_entry_interval(cls, ctx):
        calendar_profile = CalendarProfile.ByKeys(ctx.dialog.calendar_profile_id)
        prof_start = calendar_profile.valid_from
        prof_end = calendar_profile.valid_until
        exc_day = typeconversion.from_legacy_date_format(ctx.dialog.day).date()
        end_day = typeconversion.from_legacy_date_format(ctx.dialog.end_day).date()
        if isinstance(exc_day, datetime.datetime) and isinstance(end_day, datetime.datetime):
            exc_day = exc_day.date()
            end_day = end_day.date()
        if exc_day > end_day:
            raise ue.Exception("cdb_cal_end_before_start")
        if prof_start > exc_day or exc_day > prof_end and prof_start > end_day or end_day > prof_end:
            raise ue.Exception("cdb_cal_outside_range")

    @classmethod
    def _multi_entry_calendar(cls, ctx):
        exc_day_sql = sqlapi.SQLdbms_date(ctx.dialog.day)
        end_day_sql = sqlapi.SQLdbms_date(ctx.dialog.end_day)
        exc_day = typeconversion.from_legacy_date_format(ctx.dialog.day).date()
        end_day = typeconversion.from_legacy_date_format(ctx.dialog.end_day).date()
        day_rec = sqlapi\
            .RecordSet2(sql="SELECT day , day_type_id "
                        "FROM cdb_cal_prof_exc "
                        "WHERE %s <= day AND day <= %s "
                        "AND calendar_profile_id='%s'"
                        "ORDER BY day " %
                        (exc_day_sql,
                        end_day_sql,
                        ctx.dialog.calendar_profile_id))
        chg_ctrl = CalendarEntry.MakeChangeControlAttributes()
        for rec in day_rec:
            if rec.day_type_id != ctx.dialog.day_type_id:
                # Delete the old one (if exists)
                old_entry = CalendarException\
                    .Query("day = %s and calendar_profile_id = '%s'" %
                        (make_sql_date(rec.day), ctx.dialog.calendar_profile_id))
                if old_entry:
                    old_entry.Delete()
        for day in date_range(exc_day, end_day):
            param_exception = { 'day': day,
                                'day_type_id': ctx.dialog.day_type_id,
                                'description': ctx.dialog.description,
                                'calendar_profile_id': ctx.dialog.calendar_profile_id,
                                'cdb_cpersno': chg_ctrl['cdb_cpersno'],
                                'cdb_cdate': chg_ctrl['cdb_cdate'],
                                'cdb_mpersno': chg_ctrl['cdb_mpersno'],
                                'cdb_mdate': chg_ctrl['cdb_mdate'],
                                }
            CalendarException.Create(**param_exception)
            CalendarException._remember_value_multi(ctx=ctx, day=day)
            param_entry = { 'day': day,
                            'calendar_profile_id': ctx.dialog.calendar_profile_id,
                            'day_type_id': ctx.dialog.day_type_id,
                            'description': ctx.dialog.description,
                            'weekday': date2weekday(day),
                            'cdb_cpersno': chg_ctrl['cdb_cpersno'],
                            'cdb_cdate': chg_ctrl['cdb_cdate'],
                            'cdb_mpersno': chg_ctrl['cdb_mpersno'],
                            'cdb_mdate': chg_ctrl['cdb_mdate']
                            }
            old_entry = CalendarEntry \
                .Query("day = %s and calendar_profile_id = '%s'" %
                       (make_sql_date(day), ctx.dialog.calendar_profile_id))
            if old_entry:
                old_entry.Delete()
            CalendarEntry.Create(**param_entry)
            CalendarException._adjust_workday_index_multi(ctx=ctx,day=day)

        sig.emit(CalendarException, "cpe_adjust_tasks")(cls,
                                                        ctx,
                                                        calendar_profile_id=ctx.dialog.calendar_profile_id,
                                                        day=ctx.dialog.day,
                                                        end_day=ctx.dialog.end_day)

    @classmethod
    def _remember_value_multi(cls, ctx, day):
        sd = sqlapi.SQLdbms_date(day)
        base_where = """calendar_profile_id = '%s' AND personalnummer IS NULL
                       AND cdb_project_id IS NULL""" % ctx.dialog.calendar_profile_id
        where = "day = %s AND %s" % (sd, base_where)
        old_idx = sqlapi.RecordSet2(
            sql="SELECT early_work_idx FROM cdb_calendar_entry WHERE %s" %
            (where))[0]["early_work_idx"]
        ctx.keep("old_early_work_idx", int(old_idx))

    @classmethod
    def _adjust_workday_index_multi(cls, ctx, day):
        if "old_early_work_idx" in ctx.ue_args.get_attribute_names():
            old_idx = int(ctx.ue_args["old_early_work_idx"])
            CalendarException.adjust_workday_index(calendar_profile_id= ctx.dialog.calendar_profile_id, start_date = day, old_idx= old_idx)

    @classmethod
    def predefine(cls, ctx):
        if ctx.relationship_name == 'cdb_cal_prof2cal_exc':
            calendar_profile = CalendarProfile.ByKeys(ctx.parent["cdb_object_id"])
            ctx.set("calendar_profile_id", calendar_profile.cdb_object_id)
            ctx.set("mapped_calendar_profile", calendar_profile.name)
            ctx.set_fields_readonly("mapped_calendar_profile")
        if ctx.relationship_name == 'cdb_person2calendar_entry':
            calendar_profile = CalendarProfile.ByKeys(ctx.parent["calendar_profile_id"])
            ctx.set("calendar_profile_id", calendar_profile.cdb_object_id)

    event_map = {
        (('modify'), 'pre'): ('_saveChanges'),
        (('create'), 'pre'): ('_checkInterval'),
        (('create', 'copy', 'modify', 'delete'), 'pre'): ('_remember_value'),
        (('create', 'copy', 'modify'), 'post'): ('_updateCalendarEntry', '_adjust_workday_index'),
        (('delete'), 'post'): ('_deleteCalendarEntry', '_adjust_workday_index'),
        (('cdb_cal_entry_multi_new'), 'pre_mask'): ('predefine'),
        (('cdb_cal_entry_multi_new'), 'now'): ('_check_multi_entry_interval', '_multi_entry_calendar')
        }

class CalendarDayType(Object):
    __maps_to__ = "cdb_day_type"
    __classname__ = "cdb_day_type"
