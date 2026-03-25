#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import logging

from cdb import ue
from webob.exc import HTTPBadRequest, HTTPNotFound

from cs.pcs.timeschedule.web.models.helpers import get_date, is_milestone
from cs.pcs.timeschedule.web.models.update_model import UpdateModel


def adjust_milestone(milestone, new_date):
    """
    Adjusting milestones in context of setting a new date value.
    For milestones start and end dates are always identical.
    0 = As soon as possible
    1 = As late as possible
    2 = Must start on...
    3 = Must end on...
    4 = Start no earlier than...
    5 = Start no later than...
    6 = End no earlier than...
    7 = End no later than...
    """
    constraint = int(getattr(milestone, "constraint_type", 0))
    milestone.constraint_date = new_date
    if constraint in [0, 1]:
        # If no constraint date is set yet, the user now has set
        # a date by moving the task manually.
        # Therefore a contraint is set now by default to value 4.
        milestone.constraint_type = "4"
        milestone.setStartTimeFcast(start=new_date)
    elif constraint in [2, 4, 5]:
        milestone.setStartTimeFcast(start=new_date)
    elif constraint in [3, 6, 7]:
        milestone.setEndTimeFcast(end=new_date)


class SetDatesModel(UpdateModel):
    def __init__(self, context_object_id, content_object_id):
        """
        :raises webob.exc.HTTPNotFound: if save access for object identified
            by ``content_object_id`` is denied. Access is checked because the
            internal API skips access checks even though using ``CDB_Modify``.
        """
        UpdateModel.__init__(self, context_object_id, True)
        self.content_obj = self.get_object_from_uuid(content_object_id)

        if not self.content_obj.CheckAccess("save"):
            logging.error(
                "save access not granted on object '%s'",
                content_object_id,
            )
            raise HTTPNotFound

    def _verify_and_set_start(self, start):
        self.verify_writable(self.content_obj, ["start_time_fcast"])
        try:
            if is_milestone(self.content_obj):
                adjust_milestone(self.content_obj, start)
            else:
                self.content_obj.setStartTimeFcastByBar(start=start)
        except ue.Exception as ex:
            raise HTTPBadRequest(ex.errp[0]) from ex

    def _verify_and_set_end(self, end):
        self.verify_writable(self.content_obj, ["end_time_fcast"])
        try:
            if is_milestone(self.content_obj):
                adjust_milestone(self.content_obj, end)
            else:
                self.content_obj.setEndTimeFcastByBar(end=end)
        except ue.Exception as ex:
            raise HTTPBadRequest(ex.errp[0]) from ex

    def set_start(self, request):
        """
        Updates a single task's scheduled start time.

        :param request: The request sent from the frontend. Validated by
            ``_parse_update_payload``.
        :type request: morepath.Request

        :returns: data for updated tasks (see ``get_data`` for details).

        :raises webob.exc.HTTPBadRequest: if the key ``startDate`` is missing
            in request's JSON payload or contains an invalid value.
        :raises webob.exc.HTTPInternalServerError: if the update fails.
        """
        start = get_date(request.json, "startDate")
        self._verify_and_set_start(start)
        return self.get_changed_data(request)

    def set_end(self, request):
        """
        Updates a single task's scheduled end time.

        :param request: The request sent from the frontend. Validated by
            ``_parse_update_payload``.
        :type request: morepath.Request

        :returns: data for updated tasks (see ``get_data`` for details).

        :raises webob.exc.HTTPBadRequest: if the key ``endDate`` is missing
            in request's JSON payload or contains an invalid value.
        :raises webob.exc.HTTPInternalServerError: if the update fails.
        """
        end = get_date(request.json, "endDate")
        self._verify_and_set_end(end)
        return self.get_changed_data(request)

    def set_start_and_end(self, request):
        """
        Updates a single task's scheduled start and end time simultaneously.

        :param request: The request sent from the frontend. Validated by
            ``_parse_update_payload``.
        :type request: morepath.Request

        :returns: data for updated tasks
            (see ``get_changed_data`` for details).

        :raises webob.exc.HTTPBadRequest: if any of the keys ``startDate`` or
            ``endDate`` is missing in request's JSON payload or contains an
            invalid value.
        :raises webob.exc.HTTPInternalServerError: if the update fails.
        """
        start = get_date(request.json, "startDate")
        end = get_date(request.json, "endDate")

        # Note: For milestones, we get the same value for start and end.
        # Depending on start_is_early we're only allowed to change either
        # start or end, so we've to check that in advance
        if getattr(self.content_obj, "milestone", None):
            # if start_is_early, we've to change the start date,
            # else the end date of the milestone
            if self.content_obj.start_is_early:
                self._verify_and_set_start(start)
            else:
                self._verify_and_set_end(end)
        else:
            self.verify_writable(
                self.content_obj, ["start_time_fcast", "end_time_fcast"]
            )

            try:
                self.content_obj.moveTimeframe(start=start, end=end)
            except ue.Exception as ex:
                raise HTTPBadRequest(ex.errp[0]) from ex
        return self.get_changed_data(request)
