# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from datetime import datetime, timedelta

from cdb.util import get_label
from webob.exc import HTTPBadRequest, HTTPForbidden

from cs.pcs.timeschedule.web.models import DataModel
from cs.pcs.timeschedule.web.models.read_only_model import ReadOnlyModel


class UpdateModel(DataModel):
    TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, context_object_id, use_current_timestamp=None):
        """ """
        DataModel.__init__(self, context_object_id)
        if use_current_timestamp:
            self.baseline = datetime.utcnow() - timedelta(seconds=1)
        else:
            self.baseline = None

    def _set_baseline(self, request):
        """
        Sets ``self.baseline`` to the datetime represented by the
        "lastUpdated" value of ``request``'s json payload (``None`` if not
        given).
        One second will be subtracted from the datetime to ensure positive
        filtering after really fast operations.

        :raises HTTPBadRequest: when encountering an illegal (non-empty)
            lastUpdated value or ``request`` does not include JSON payload.
        """
        if self.baseline is None:
            try:
                timestamp = request.json.get("lastUpdated", None)
            except ValueError as exc:
                # No JSON object could be decoded
                raise HTTPBadRequest from exc

            if timestamp:
                try:
                    parsed = datetime.strptime(
                        timestamp,
                        self.TIMESTAMP_FORMAT,
                    )
                except ValueError as exc:
                    # timestamp is malformed (does not match TIMESTAMP_FORMAT)
                    raise HTTPBadRequest from exc

                self.baseline = parsed - timedelta(seconds=1)
            else:
                self.baseline = None

    def _get_full_data_first_page(
        self, tree_nodes, ts_records, bl_records, relevant_baselines, request
    ):
        def is_updated(mdate):
            if self.baseline:
                return mdate is None or mdate > self.baseline

            # no baseline? just return everything
            return True

        all_oids = []
        updated_records = []

        for ts_record in ts_records:
            all_oids.append(ts_record.record.cdb_object_id)

            if is_updated(ts_record.record.get("cdb_mdate", None)) or is_updated(
                ts_record.record.get("cdb_adate", None)
            ):
                updated_records.append(ts_record)

        return self.get_full_data(
            all_oids,  # load all relations and subjects
            None,
            updated_records,  # but only updated REST objects
            [],  # baseline data isn't updated
            request,
        )

    def get_changed_data(self, request):
        """
        1. Parses JSON "timestamp" value as ``self.baseline``
        2. Resolve changed data just like ``DataModel`` does, but instead of
           returning full objects for the first page, return full objects that
           were changed after ``self.baseline`` (all if ``self.baseline`` is
           ``None``).

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: See ``DataModel.get_data``.
        :rtype: dict
        """
        self._set_baseline(request)
        return self.get_data(request)

    def verify_writable(self, obj, fields):
        """
        Verifies if the fields are not read only.

        :param obj: The object for which the verification is needed.
        :type object: cdb.objects.Object

        :param fields: List of fields which need to be checked.
        :type fields: list

        :raises webob.exc.HTTPForbidden: If any of the field is write protected.
        """

        read_only_model = ReadOnlyModel(self.context_object_id)
        read_only_data = read_only_model.get_read_only_data([obj.cdb_object_id])
        by_class = read_only_data["byClass"].get(
            obj._getClassname(), []  # pylint: disable=protected-access
        )
        by_object = read_only_data["byObject"].get(obj.cdb_object_id, [])
        for field in fields:
            if field in by_class or field in by_object:
                raise HTTPForbidden(get_label("outdate_timeschedule"))
