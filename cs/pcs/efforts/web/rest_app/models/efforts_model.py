#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import logging
from collections import defaultdict

import cdbwrapc
import dateutil
import webob
from cdb import auth, util
from cdb.objects import operations
from cdb.objects.iconcache import IconCache
from cdb.objects.org import Person
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web import rest
from cs.platform.web.uisupport import get_webui_link
from cs.platform.web.uisupport.resttable import RestTableDefWrapper
from cs.web.components.configurable_ui import SinglePageModel

from cs.pcs.efforts import TimeSheet
from cs.pcs.efforts.stopwatch import Stopwatch

EFFORTS_CLASS_NAME = "cdbpcs_effort"
EFFORTS_APP_TABLE_DEF = "cdbpcs_tsheet_web"


def get_json_payload(request):
    if hasattr(request, "json"):
        return getattr(request, "json")
    else:
        logging.exception('The request has no attribute "json"')
        raise webob.exc.HTTPBadRequest()


class EffortsModel(SinglePageModel):
    def parse_date(self, date_str):
        """
        :param date_str: Datetime in ISO format.
        :type date_str: basestring

        :returns: Date object which represents the date_str.
        :rtype: date

        This method parses the date_str to a date object.
        """
        date = dateutil.parser.parse(date_str).date()
        return date

    def get_day_data(self, day, efforts, person_id):
        """
        :param day: Date object for which the booked hours and
                    booking status should be checked.
        :type day: date

        :param efforts: Efforts with their properties.
        :type efforts: dict

        :param person_id: Person ID of the currently logged in user.
        :type person_id: basestring

        :returns: Hours and variant of current day.
        :rtype: dict

        This method returns for a given day the already booked
        hours (hours) and the booking status (variant).
        """
        today = datetime.date.today()
        day_hours = 0
        for effort in efforts:
            day_hours += effort["hours"]
        day_hours = round(day_hours, 2)

        variant = "no-variant"

        if day < today and day_hours < TimeSheet.get_day_hours():
            variant = "unreached"
        elif day == today:
            variant = "inprogress"
        return {"hours": day_hours, "variant": variant}

    def get_days_data(self, days, efforts, person_id):
        """
        :param days: List of date objects for which the booked
                     hours and variant should be checked.
        :type days: list

        :param efforts: Efforts with their properties.
        :type efforts: dict

        :param person_id: Person ID of the current logged in user.
        :type person_id: basestring

        :returns: Information how many hours are booked and the
                  booking state for each day.
        :rtype: dict

        This method computes for all datetime objects the booked
        hours and the booking status.
        """
        days_efforts = defaultdict(list)
        for effort in efforts:
            parsed_day = self.parse_date(effort["day"])
            days_efforts[parsed_day].append(effort)
        day_data = defaultdict(dict)
        for day in days:
            day_data[day.isoformat()] = self.get_day_data(
                day, days_efforts[day], person_id
            )
        return day_data

    def get_columns_data(self, effort, col):
        """
        :param effort: Effort with its properties.
        :type effort: dict

        :param col: Table column with its properties.
        :type col: dict

        :returns: -
        :rtype: datetime/float/otherwise

        This method computes for a datetime object its ISO
        format representation, rounds float values to
        two digits, or returns the object itself.
        """
        attr = col["attribute"]
        if self._is_icon_column(col):
            return {"icon": {"src": IconCache.getIcon(attr), "title": col["label"]}}
        value = effort[attr]
        if isinstance(value, datetime.date):
            return value.isoformat()
        elif isinstance(value, float):
            return round(value, 2)
        else:
            return value

    def _is_icon_column(self, col):
        return col.get("kind", -1) == 100

    def get_row_data(self, effort, cols, request):
        """
        :param effort: Effort with its properties.
        :type effort: dict

        :param cols: Table columns with its properties.
        :type cols: dict

        :param request: HTML request information.
        :type request: HTML Request

        :returns: Effort with all its properties.
        :rtype: dict

        This method generates a dict of an effort and
        updates/add specific values which are needed in the
        frontend.
        """
        collection = rest.get_collection_app(request)
        effort_rest_obj = EffortsModel.__get_rest_object__(effort, collection, request)
        effort_rest_obj.update(
            {
                "webuiLink": get_webui_link(None, effort),
                "id": effort["cdb_object_id"],
                "restLink": effort_rest_obj["@id"]
                if "@id" in effort_rest_obj
                else effort["restLink"],
                "persistent_id": effort["cdb_object_id"],
                "columns": [self.get_columns_data(effort, col) for col in cols],
            }
        )
        return effort_rest_obj

    def get_default_cols_data(self, cols):
        """
        :param cols: Table columns with its properties.
        :type cols: dict

        :returns: Group by and index information.
        :rtype: dict

        This method generates a dict which contains the
        information by which attribute a table should be
        grouped by default and at which index the hour
        column can be found.
        """
        default_group_by = []
        hours_col_index = -1
        for i, col in enumerate(cols):
            if col["attribute"] == TimeSheet.get_hours_field():
                hours_col_index = i
            elif col["attribute"] in TimeSheet.get_default_groupby_fields():
                default_group_by.append(col["id"])
        return {"initGroupBy": default_group_by, "hoursColumnIndex": hours_col_index}

    def parse_stopwatch(self, stopwatch):
        return {
            "effort_id": stopwatch.effort_id,
            "start_time": (
                None if not stopwatch.start_time else stopwatch.start_time.isoformat()
            ),
            "end_time": (
                None if not stopwatch.end_time else stopwatch.end_time.isoformat()
            ),
            "booked": stopwatch.booked,
            "cdb_object_id": stopwatch.cdb_object_id,
            "is_virtual": stopwatch.is_virtual,
        }

    def get_stopwatch_data(self, efforts, person):
        effort_stopwatches = {}
        today = datetime.date.today()
        for effort in efforts:
            if effort.day != today:
                # No stopwatches for day other than today
                continue

            stopwatches = effort.Stopwatches

            # Take only those stopwatches which are not booked
            parsed = []
            if stopwatches:
                parsed = [
                    self.parse_stopwatch(sw) for sw in stopwatches if not sw.booked
                ]
            effort_stopwatches[str(effort.effort_id)] = parsed

        other_sws = Stopwatch.KeywordQuery(
            person_id=person.personalnummer,
            stopwatch_day=[today],
            booked=False,
            is_virtual=True,
            order_by="start_time desc",
        )

        other_stopwatches = defaultdict(list)
        for sw in other_sws:
            other_stopwatches[str(sw.effort_id)].append(self.parse_stopwatch(sw))

        return {
            "effortsStopwatches": effort_stopwatches,
            "otherStopwatches": other_stopwatches,
        }

    def get_efforts(self, request):
        """
        :param request: HTML request information.
        :type request: HTML Request

        :returns: Efforts which satisfy the conditions.
        :rtype: dict

        This method collects all efforts that satisfies the
        given conditions and returns them.
        """
        days = None
        specific_day = None
        result = {}
        if request.params:
            try:
                if request.params.get("fromDate") and request.params.get("toDate"):
                    from_date = self.parse_date(request.params.get("fromDate"))
                    to_date = self.parse_date(request.params.get("toDate"))
                    days = EffortsModel.__get_day_range__(from_date, to_date)
                if request.params.get("specificDay"):
                    specific_day = self.parse_date(request.params.get("specificDay"))
                if not days and not specific_day:
                    logging.exception("No date passed or wrong date format used.")
                    raise webob.exc.HTTPBadRequest()
            except ValueError as exc:
                logging.exception("No date passed or wrong date format used.")
                raise webob.exc.HTTPBadRequest() from exc
        else:
            days = EffortsModel.__get_week_days__()

        person = Person.ByKeys(personalnummer=auth.persno)
        cols = ColumnsModel.get_columns()["columns"]
        default_limit_hours = util.PersonalSettings().getValueOrDefaultForUser(
            "user.limit_hours_per_day", "", None, None
        )
        if days:
            efforts = [
                effort
                for effort in TimeSheet.KeywordQuery(
                    person_id=person.personalnummer, day=days, order_by="day desc"
                )
                if effort.CheckAccess("read")
            ]

            stopwatch_data = self.get_stopwatch_data(efforts, person)

            efforts = [self.get_row_data(obj, cols, request) for obj in efforts]
            days_data = self.get_days_data(days, efforts, person.personalnummer)
            day_hours = TimeSheet.get_day_hours()
            result = {
                "efforts": efforts,
                "daysData": days_data,
                "columns": cols,
                "defaultColumnsData": self.get_default_cols_data(cols),
                "stopwatchData": stopwatch_data,
                "defaultWeekdayHours": day_hours,
                "defaultWeekHours": day_hours * 5,
            }
        result["defaultLimitHours"] = default_limit_hours
        if specific_day:
            efforts_specific_day = [
                effort
                for effort in TimeSheet.KeywordQuery(
                    person_id=person.personalnummer, day=specific_day
                )
                if effort.CheckAccess("read")
            ]
            efforts_specific_day = [
                self.get_row_data(obj, cols, request) for obj in efforts_specific_day
            ]
            specific_day_data = self.get_days_data(
                [specific_day], efforts_specific_day, person.personalnummer
            )
            result["specificDayData"] = specific_day_data
        return result

    def validate_stopwatches(
        self, stopwatch_ids, effort_id, for_start=False, is_virtual=False
    ):

        """
        :param stopwatch_ids: List with the cdb_object_ids of stopwatches.
        :type stopwatch_ids: list

        :param effort_id: ID of an effort.
        :type effort_id: int

        :param for_start: Information if a stopwatch is already stopped.
        :type for_start: bool

        :returns: Stopwatch objects and the related person or and exception.
        :rtype: tuple

        This method checks if the given stopwatch are valid. If all given
        stopwatches are valid it will return the stopwatch objects with
        the related person. If not, then an error will be raised.
        """
        person = Person.ByKeys(personalnummer=auth.persno)

        # Get all the unbooked stopwatches for currently logged in person
        # and effort_id, since this method is only valid for stopwatches
        # belonging to today, we fetch today's stopwatches
        sws = [
            sw
            for sw in Stopwatch.KeywordQuery(
                effort_id=effort_id,
                stopwatch_day=datetime.date.today(),
                person_id=person.personalnummer,
                booked=False,
                is_virtual=is_virtual,
            )
            if sw.CheckAccess("read")
        ]

        stopwatch_ids = set(stopwatch_ids)
        is_valid = len(sws) == len(stopwatch_ids) and all(
            s.cdb_object_id in stopwatch_ids
            # Stopwatch has no end_time and for_start must be true
            and (for_start or s.end_time)
            for s in sws
        )

        if not is_valid:
            error = cdbwrapc.get_label("cdbpcs_efforts_stopwatch_refresh")
            logging.exception(error)
            raise webob.exc.HTTPConflict(error)
        return sws, person

    def start_stopwatch(self, request):
        """
        :param request: HTML request information.
        :type request: HTML Request

        :returns: Newly created stopwatch.
        :rtype: dict

        This method creates and returns a new stopwatch
        for the currently logged in user for a given start_time.
        """
        params = get_json_payload(request)
        try:
            effort_id = int(params["effort_id"])
            start_time = dateutil.parser.parse(params["start_time"])
            is_virtual = params["is_virtual"]

            # existing_stopwatches is the set of stopwatches available with
            # the client for a given effort (or for a new effort)
            existing_stopwatches = params["existing_stopwatches"]
        except (TypeError, ValueError, KeyError) as error:
            logging.exception(str(error))
            raise webob.exc.HTTPBadRequest()

        _, person = self.validate_stopwatches(
            existing_stopwatches, effort_id, True, is_virtual
        )
        # Note: Using the CDB_Create operation directly checks for access right
        kwargs = {
            "effort_id": effort_id,
            "stopwatch_day": start_time.date(),
            "start_time": start_time,
            "person_id": person.personalnummer,
            "booked": False,
            "is_virtual": is_virtual,
        }
        sw = operations.operation("CDB_Create", Stopwatch, **kwargs)

        return self.parse_stopwatch(sw)

    def stop_stopwatch(self, request):
        """
        :param request: HTML request information containing a json.
        :type request: HTML Request

        :returns: The stopped stopwatch.
        :rtype: dict

        This method updates the end_time of the stopwatch
        referenced by `cdb_object_id` of the stopwatch sent in request json.
        The end_time (in utc) should also be sent in the request.
        """
        params = get_json_payload(request)
        # Check if required fields 'stopwatch_ids' and 'end_time' are present
        # and of the required form
        try:
            stopwatch_ids = params["stopwatch_ids"]
            end_time = dateutil.parser.parse(params["end_time"])
            end_time = end_time.replace(tzinfo=None)
        except (TypeError, KeyError, ValueError) as error:
            logging.exception(str(error))
            raise webob.exc.HTTPBadRequest()

        # Get and check access for Stopwatches
        sws = [
            sw
            for sw in Stopwatch.KeywordQuery(
                cdb_object_id=stopwatch_ids, order_by="start_time desc"
            )
            if sw.CheckAccess("save")
        ]
        if sws:
            sw = sws[0]

            # If stopwatch is already stopped, then we have a object
            # state conflict
            if sw.end_time:
                logging.exception(
                    "Stopwatch is already stopped and the endtime is set!"
                )
                raise webob.exc.HTTPConflict(
                    "Stopwatch state not updated. Please refresh!"
                )

            sw.Update(end_time=end_time)
            if not sw.is_virtual:
                self.record_stopwatches_helper(sws, sw.effort_id, sw.is_virtual)

            return self.parse_stopwatch(sw)
        else:
            logging.exception(
                "Stop Stopwatches: '%s' has no save access on stopwatches: '%s'",
                auth.persno,
                stopwatch_ids,
            )
            raise webob.exc.HTTPNotFound()

    def valid_stopwatches(self, request):
        """
        :param request: HTML request information.
        :type request: HTML Request

        This method checks if the database and front-end stopwatch entries
        have the same state.
        """
        if hasattr(request, "params"):
            try:
                stopwatch_ids = []
                effort_id = None
                is_virtual = False
                for p, v in request.params.items():
                    if p == "stopwatch_ids":
                        # From the front-end stopwatch_ids list is transmitted
                        # as parameter, but in multidimensional dictionary
                        # it is not possible to access the whole list.
                        # When calling params['stopwatch_ids'] it only
                        # returns the last item of the list.
                        # So the value at the key 'stopwatch_ids' is only
                        # a string.
                        stopwatch_ids.append(v)
                    elif p == "effort_id" and v:
                        effort_id = int(v)
                    elif p == "is_virtual":
                        is_virtual = v in ("true", 1)
                _, _ = self.validate_stopwatches(
                    stopwatch_ids, effort_id, False, is_virtual
                )
                # If no exception is raised then return true
                return True
            except Exception as error:
                logging.exception(str(error))
                raise error
        else:
            logging.exception('The request has no attribute "params"!')
            raise webob.exc.HTTPBadRequest()

    def record_stopwatches(self, request):
        """
        :param request: HTML request information.
        :type request: HTML Request

        :returns: Only the object state is changed but nothing is returned.
        :rtype: None

        This method handles two cases:
            1) If there is an effort_id sent in request json, the hours for
               these stopwatches will be added to the hours of the effort
               referenced by effort_id.
            2) If there is no effort_id then the stopwatches are simply
               marked as booked.
        """
        params = get_json_payload(request)
        try:
            stopwatch_ids = params["stopwatch_ids"]
            effort_id = int(params["effort_id"])
            is_virtual = params["is_virtual"]

            sws, _ = self.validate_stopwatches(
                stopwatch_ids, effort_id, False, is_virtual
            )
            self.record_stopwatches_helper(sws, effort_id, is_virtual)
        except (TypeError, ValueError, KeyError) as error:
            logging.exception(str(error))
            raise webob.exc.HTTPBadRequest()

    def record_stopwatches_helper(self, sws, effort_id, is_virtual):
        # Compute total hours and mark each stopwatch as booked
        total_hours = 0
        for sw in sws:
            try:
                time_delta = sw.end_time - sw.start_time
                total_hours += time_delta.seconds / 3600.0
                # Update the stopwatch so that it cannot be booked again
                sw.Update(booked=True)
            except Exception as ex:
                logging.exception(str(ex))
                raise ex

        # If we have an effort id we assign the total_hours to this effort
        if not is_virtual:
            # round the recorded hours to two decimal places
            total_hours = round(total_hours, 2)
            try:
                effort_id = int(effort_id)
            except Exception as ex:
                logging.exception(str(ex))
                raise ex
            # Get the desired effort and check for save/write access
            effort = [
                effort
                for effort in TimeSheet.KeywordQuery(effort_id=effort_id)
                if effort.CheckAccess("save")
            ]
            if not effort:
                logging.exception(
                    "'%s' has no save access on effort: '%s'", auth.persno, effort_id
                )
                raise webob.exc.HTTPNotFound()

            # Take the first effort
            effort = effort[0]
            # Add hours to the effort
            effort.Update(hours=effort.hours + total_hours)

    def reset_stopwaches(self, request):
        """
        :param request: HTML request information.
        :type request: HTML Request

        :returns: Only the object state is changed but nothing is returned.
        :rtype: None

        Resets the stopwatches sent in the request. This method first validates
        the state of stopwatches and then performs an update for each stowatch.
        """
        params = get_json_payload(request)
        try:
            effort_id = params["effort_id"]
            stopwatch_ids = params["stopwatch_ids"]
            is_virtual = params["is_virtual"]

            sws, _ = self.validate_stopwatches(
                stopwatch_ids, effort_id, False, is_virtual
            )

            for s in sws:
                s.Update(booked=True)
        except (ValueError, KeyError) as error:
            logging.exception(str(error))
            raise webob.exc.HTTPBadRequest()

    @staticmethod
    def __get_rest_object__(obj, app, request):
        """
        :param obj: Object (effort) with its properties.
        :type obj: dict

        :type app: CollectionApp

        :param request: HTML request information.
        :type request: HTML Request

        :returns: Object information
        :rtype: dict

        This method converts an object to its rest data.
        """
        return request.view(obj, app=app)

    @staticmethod
    def __get_week_days__(day=None):
        """
        :param day: Day for which the other weekdays should be
                    calculated.
        :type day: date

        :returns: List of date objects
        :rtype: list

        This method calculates for a given day the other weekdays and
        returns them.
        """
        if day is None:
            day = datetime.date.today()
        day_of_week = day.isocalendar()[2]
        start_date = day - datetime.timedelta(days=(day_of_week - 1))
        week_days = []
        week_days.append(start_date)

        for i in range(1, 7, 1):
            week_days.append(start_date + datetime.timedelta(days=i))

        return week_days

    @staticmethod
    def __get_day_range__(from_date, to_date):
        """
        :param from_date: Day with which the date interval should start.
        :type from_date: date

        :param to_date: Day with which the date interval should end.
        :type to_date: date

        :returns: List of date objects
        :rtype: list

        This method calculates a day interval starting at the
        from_date and ending at the to_date.
        """
        if not from_date or not to_date:
            return []

        # cloning from_date as the first value
        days = [from_date + datetime.timedelta(days=0)]

        while from_date < to_date:
            from_date = from_date + datetime.timedelta(days=1)
            days.append(from_date)
        return days


class ColumnsModel(SinglePageModel):
    @classmethod
    def get_columns(cls):
        """
        :returns: JSON structure which contains the table definition.
        :rtype: dict

        This method returns the table definition for the efforts class.
        """
        class_def = CDBClassDef(EFFORTS_CLASS_NAME)
        tabledef = class_def.getProjection(EFFORTS_APP_TABLE_DEF, True)
        return RestTableDefWrapper(tabledef).get_rest_data()
