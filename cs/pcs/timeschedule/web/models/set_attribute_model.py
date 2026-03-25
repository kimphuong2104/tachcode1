#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import ElementsError, ue, util
from cdb.constants import kOperationModify
from cdb.objects.operations import form_input, operation
from webob.exc import HTTPBadRequest, HTTPForbidden

from cs.pcs.projects.tasks_efforts import aggregate_changes
from cs.pcs.timeschedule.web.models.helpers import get_date, is_milestone
from cs.pcs.timeschedule.web.models.set_dates_model import adjust_milestone
from cs.pcs.timeschedule.web.models.update_model import UpdateModel

TS_API_DATE_ATTRS = [
    "start_time_fcast",
    "end_time_fcast",
    "start_time_plan",
    "end_time_plan",
    "start_time_act",
    "end_time_act",
]
ATTR_TO_USE_TS_API = TS_API_DATE_ATTRS + ["days_fcast", "days"]


class SetAttributeModel(UpdateModel):
    def __init__(self, context_object_id, cdb_object_id):
        """
        :param cdb_object_id: cdb_object_id of the object to modify.
        :type cdb_object_id: str

        :raises webob.exc.HTTPNotFound: if either the context object or its
            Project do not exist or are not readable by the logged-in user.
        """
        UpdateModel.__init__(self, context_object_id, True)
        self.cdb_object_id = cdb_object_id
        self.object = self.get_object_from_uuid(cdb_object_id)

        if not self.object.CheckAccess("save"):
            logging.error(
                "save access not granted on object '%s'",
                cdb_object_id,
            )
            raise HTTPForbidden

    def _ts_api_fcast(self, key, date_value):
        if is_milestone(self.object):
            adjust_milestone(self.object, date_value)
        else:
            if key == "start_time_fcast":
                self.object.setStartTimeFcast(start=date_value)
            else:
                self.object.setEndTimeFcast(end=date_value)

    def _ts_api_plan(self, key, date_value):
        updates = self.object.MakeChangeControlAttributes()
        updates[key] = date_value

        self.object.Update(**updates)

        if key == "start_time_plan":
            self.object.change_start_time_plan()
        else:
            self.object.change_end_time_plan()

    def _ts_api_act(self, key, date_value):
        start = self.object.start_time_act
        end = self.object.end_time_act

        if key == "start_time_act":
            start = date_value
            setter = self.object.change_start_time_act
        else:
            end = date_value
            setter = self.object.change_end_time_act

        if start and end and start > end:
            raise HTTPBadRequest(util.get_label("pcs_days_act_end_before_start"))

        if end and not start:
            raise HTTPBadRequest(util.get_label("pcs_start_act_present_when_end_act"))

        updates = self.object.MakeChangeControlAttributes()
        updates[key] = date_value

        self.object.Update(**updates)
        setter()

    def _ts_api_days(self, days_value):
        try:
            self.object.Update(
                days=days_value, **self.object.MakeChangeControlAttributes()
            )
            self.object.change_days()
        except ValueError as exc:
            raise HTTPBadRequest(f"'{days_value}' not valid") from exc

    def _ts_api_days_fcast(self, days_value):
        try:
            # setDaysFcast expects integer
            self.object.setDaysFcast(days=days_value)
        except ValueError as exc:
            raise HTTPBadRequest(f"'{days_value}' not valid") from exc

    def _set_attribute_by_TS_API(self, key, updates):
        """
        Changes value of given attribute (by key) with the corresponding
        timeschedule API.

        :param key: attribute name and key in updates
        :type key: string

        :param updates: contains attributes and values to update
        :type updates: dict

        :raises webob.exc.HTTPBadRequest: if the corresponding timeschedule
            API throws an exception.
        """
        if key in TS_API_DATE_ATTRS:
            # date is expected in legacy format
            date_value = get_date(updates, key, is_iso=False)

            if key in ("start_time_fcast", "end_time_fcast"):
                self._ts_api_fcast(key, date_value)
            elif key in ("start_time_plan", "end_time_plan"):
                self._ts_api_plan(key, date_value)
            elif key in ("start_time_act", "end_time_act"):
                self._ts_api_act(key, date_value)
            else:
                raise HTTPBadRequest(f"invalid key: '{key}'")
        elif key == "days":
            self._ts_api_days(updates[key])
        elif key == "days_fcast":
            self._ts_api_days_fcast(updates[key])
        else:
            raise HTTPBadRequest(f"invalid key: '{key}'")

        if hasattr(self.object, "task_id"):
            aggregate_changes(self.object.Project)
        else:
            aggregate_changes(self.object)

    def set_attribute(self, request):
        """
        Update a single object with simple values.

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: data for updated tasks
            (see ``get_changed_data`` for details).

        :raises webob.exc.HTTPBadRequest: if ``request`` is missing the
            ``updates`` key or if the timeschedule API used to update an
            attribute raises an exception (see ``_set_attribute_by_TS_API``
            for details).
        :raises webob.exc.HTTPForbidden: if the update fails.
        """

        try:
            updates = request.json["updates"]
        except KeyError as exc:
            raise HTTPBadRequest from exc

        self.verify_writable(self.object, list(updates.keys()))

        # NOTE: Some attributes have to be changed by the corresponding
        #       timeschedule API itself, so we have to filter them out
        #       and handle them seperately
        filtered_updates = {}
        for key, value in updates.items():
            if key in ATTR_TO_USE_TS_API:
                try:
                    self._set_attribute_by_TS_API(key, updates)
                except ue.Exception as ex:
                    logging.error(
                        "failed to set using TS API %s (%s, %s)",
                        self.cdb_object_id,
                        key,
                        updates,
                    )
                    raise HTTPBadRequest(ex.errp[0]) from ex
            else:
                filtered_updates[key] = value

        # if values to update remain, update them via operation
        if len(filtered_updates) > 0:
            user_input = form_input(self.object, **filtered_updates)

            try:
                operation(kOperationModify, self.object, user_input)
            except ElementsError as ex:
                raise HTTPForbidden(str(ex)) from ex

        return self.get_changed_data(request)
