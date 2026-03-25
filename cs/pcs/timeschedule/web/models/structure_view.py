# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb import sig

from cs.pcs.projects import Project
from cs.pcs.projects.project_structure import util, views
from cs.pcs.timeschedule.web.baseline_helpers import (
    get_requested_baseline,
    merge_with_baseline_proj,
)


@sig.connect(views.GET_VIEWS)
def _register_view(register_callback):
    register_callback(TimeScheduleProjectView)


class TimeScheduleProjectView(views.TreeTableView):
    view_name = "timeschedule_project"

    LICENSE_FEATURE_ID = "TIMESCHEDULE_004"

    def resolve_structure(self):
        """
        Resolves the structure of `self.root_project`
        with or without subprojects (depending on `self.subprojects`).

        Calls
        `cs.pcs.projects.project_structure.util.resolve_structure`
        and applies the result to the instance variables
        `self.pcs_levels`.

        In case baseline data is also requested, the baseline data
        is merged into the original project structure.
        """
        self.pcs_levels = util.resolve_structure(
            self.root_oid,
            "cdbpcs_project",
            self.subprojects,
        )

        ce_baseline_id = get_requested_baseline(self.root_oid, self.request)
        if ce_baseline_id:
            # merge the baseline project data
            baseline_project = Project.Query(f"ce_baseline_id='{ce_baseline_id}'")
            baseline_project.Execute()
            if baseline_project:
                baseline_project = baseline_project[0]
                baseline_pcs_levels = util.resolve_structure(
                    baseline_project.cdb_object_id,
                    "cdbpcs_project",
                    False,  # no subprojects
                )
                self.pcs_levels = merge_with_baseline_proj(
                    self.pcs_levels, baseline_pcs_levels, baseline_project
                )

    def get_full_data(self, first=None):
        """
        Unused since plugins and data_model load the full data.
        """
        pass

    def format_response(self):
        """
        :returns: Resolved structure entries including level information.
        :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`
        """
        return self.pcs_levels
