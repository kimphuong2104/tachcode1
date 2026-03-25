#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.baselining import Baseline
from cs.platform.web import rest
from webob.exc import HTTPBadRequest

from cs.pcs.timeschedule.web.models.data_model import DataModel
from cs.pcs.timeschedule.web.models.helpers import get_oid_query_str

QUERY_PATTERN = """cdb_object_id IN (
    SELECT ce_baseline_id
    FROM cdbpcs_project
    WHERE ce_baseline_id > ''
        AND cdb_project_id IN (
            SELECT cdb_project_id
            FROM cdbpcs_project
            WHERE {}
        )
)"""


class BaselineModel:
    """
    Provides baseline related project data.
    """

    def load_baselines(self, request):
        """
        Initializes ``self.baselines`` as all baseline objects
        for given project UUIDs contained in ``request``.

        - Checks access on baseline objects (not the projects) and
        - orders baselines by descending creation time.

        :param request: HTTP request object
        :type request: morepath.Request
        """
        try:
            self.project_oids = request.json["projectOIDs"]
        except Exception as exc:
            raise HTTPBadRequest from exc

        query_str = get_oid_query_str(self.project_oids)
        self.baselines = [
            b
            for b in Baseline.Query(
                QUERY_PATTERN.format(query_str),
                addtl="ORDER BY ce_baseline_cdate DESC",
            )
            # does not check read access on the projects, just the baselines
            if b.CheckAccess("read")
        ]

    def get_baselines(self, request):
        """
        Gets all the baselines of a project.
        """
        self.load_baselines(request)
        collection = rest.get_collection_app(request)

        return [request.view(baseline, app=collection) for baseline in self.baselines]


class BaselineDataModel(DataModel):
    def get_data_with_baseline(self, request):
        # load complete data because it's not the first
        # time user is loading the timeschedule
        self.first_page_size = None
        return self.get_data(request)
