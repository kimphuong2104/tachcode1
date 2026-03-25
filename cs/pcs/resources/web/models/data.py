#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from collections import defaultdict

from webob.exc import HTTPBadRequest, HTTPForbidden, HTTPInternalServerError

from cdb import fls
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cs.pcs.projects import TeamMember
from cs.pcs.resources import DAY, MONTH, QUARTER, WEEK, format_in_condition
from cs.pcs.resources.new_resource_chart.helper import ResourceScheduleHelper
from cs.pcs.resources.web.models.helpers import get_prj_ids, get_timeframe

RESOURCE_SCHEDULE_LICENCE = "RESOURCES_001"
DEMAND_CLASSNAME = "cdbpcs_prj_demand"
ASSIGNMENT_CLASSNAME = "cdbpcs_prj_alloc"
RESOURCE_POOL_CLASSNAME = "cdbpcs_resource_pool"
ORGANIZATION_CLASSNAME = "cdb_organization"
PERSON_CLASSNAME = "cdb_person"
RESOURCE_POOL_ASSIGNMENT = "cdbpcs_pool_assignment"


def resolveRSContentObj(base_classname, handle, all_persons_ids):
    result = None
    if base_classname == DEMAND_CLASSNAME:
        result = {
            "classname": base_classname,
            "isDemand": True,
            'cdb_demand_id': handle.cdb_demand_id,
            'task_id': handle.task_id,
            'project_id': handle.cdb_project_id,
            'assignment_oid': handle.assignment_oid,
            'pool_oid': handle.pool_oid,
        }
    elif base_classname == ASSIGNMENT_CLASSNAME:
        result = {
            "classname": base_classname,
            "isAlloc": True,
            'cdb_demand_id': handle.cdb_demand_id,
            'task_id': handle.task_id,
            'project_id': handle.cdb_project_id,
            'assignment_oid': handle.assignment_oid,
            'pool_oid': handle.pool_oid,
        }
    elif base_classname == RESOURCE_POOL_CLASSNAME:
        result = {
            "classname": base_classname,
            'cdb_object_id': handle.cdb_object_id,
            'parent_oid': handle.parent_oid,
        }
    elif base_classname in (ORGANIZATION_CLASSNAME, PERSON_CLASSNAME):
        result = {
            "classname": base_classname,
            'cdb_object_id': handle.cdb_object_id,
        }
    elif base_classname == RESOURCE_POOL_ASSIGNMENT:
        person_id = handle.person_id
        all_persons_ids.append(person_id)
        result = {
            "classname": base_classname,
            'pool_oid': handle.pool_oid,
            'person_id': person_id,
        }
    else:
        # Note: Unexpected elements are not resolved, i.e. do not appear in the schedule,
        # but also do not crash the schedule
        logging.error("Unsupported base classname '%s' for resource schedule content", base_classname)
    return result


class ResourceScheduleDataModel(object):
    ZOOM_LEVELS = [DAY, WEEK, MONTH, QUARTER]

    def __init__(self, schedule_oid):
        if not fls.get_license(RESOURCE_SCHEDULE_LICENCE):
            logging.error("Missing license feature %s", RESOURCE_SCHEDULE_LICENCE)
            raise HTTPForbidden

        self.schedule_oid = schedule_oid
        self.schedule = ResourceScheduleHelper.get_schedule(self.schedule_oid)

        if not self.schedule:
            logging.error("No schedule found for id: '%s'", schedule_oid)
            raise HTTPBadRequest

        if not self.schedule.CheckAccess("read"):
            logging.error("No read access on schedule: '%s'", schedule_oid)
            raise HTTPForbidden

    def get_object_data(self, uuids):
        """
        :param uuids: ``cdb_object_id`` values
        :type uuids: list

        :param timeframe_start: Lower-bound date
        :type timeframe_start: datetime.date

        :param timeframe_end: Upper-bound date
        :type timeframe_end: datetime.date

        :returns: tuple:
            1. ``objs_data`` as required by
                :py:meth:`cs.pcs.resources.new_resource_chart.helper.ResourceScheduleHelper.get_chart_data`
            2. UUIDs filtered out due to them not matching the time frame
        :rtype: tuple(dict, set)

        :raises webob.exc.HTTPInternalServerError:
            if encountering unsupported schemas for resolved resource schedule elements
        """
        handles_by_id = getObjectHandlesFromObjectIDs(uuids, True, True)
        result = {}
        all_persons_ids = []
        errors = []
        for uuid, handle in handles_by_id.items():
            # get root classname
            classname = handle.getClassDef().getRootClass().getClassname()
            try:
                resolved_rs_content_obj = resolveRSContentObj(classname, handle, all_persons_ids)
                if resolved_rs_content_obj:
                    result[uuid] = resolved_rs_content_obj

            except Exception as ex:  # pylint: disable=W0703
                # collect errors, e.g. unsupported schemas
                errors.append(str(ex))

        if errors:
            # log all collected errors as one and raise Error
            logging.error("\n".join(errors))
            raise HTTPInternalServerError

        project_team = defaultdict(list)
        condition = format_in_condition("cdb_person_id", list(set(all_persons_ids)))

        for team_member in TeamMember.Query(condition):
            project_team[team_member.cdb_person_id].append(team_member.cdb_project_id)

        for value in result.values():
            if 'person_id' in value:
                value['mapped_projects'] = project_team[value['person_id']]

        return result

    def get_resource_schedule_data(self, uuids, request):
        """
        Calculates resource schedule grid data for a given time frame.
        The time frame is defined by the ``request`` under key 'extraDataProps'.
        The schedule elements in this time frame are resolved by the caller
        and passed as ``uuids``.

        :param uuids: ``cdb_object_id`` of schedule elements in given time frame
        :type uuids: list

        :param request: The request made by the frontend.
            Its JSON payload is expected to have the following keys:
            - timeFrameStart: start date in milliseconds since epoch
            - timeFrameEnd: end date in milliseconds since epoch
            - evaluate_project_ids (optional): Project IDs (defaults to [])
        :type request: morepath.Request

        :returns: Grid data for given IDs and time frame for all zoom levels.
            Data is indexed by zoom level, then UUID.
        :rtype: dict

        :raises webob.exc.HTTPBadRequest:
            if a key is missing in ``request.json`` or contains an invalid value.
        """
        timeframe_start, timeframe_end = get_timeframe(request)
        evaluate_project_ids = get_prj_ids(request.json)
        object_data = self.get_object_data(uuids)
        result = {"data": object_data}

        for zoom_level in self.ZOOM_LEVELS:
            contents, start_date, end_date = ResourceScheduleHelper.get_chart_data(
                schedule=self.schedule,
                ids=uuids,
                scale=zoom_level,
                start=timeframe_start,
                end=timeframe_end,
                evaluate_project_ids=evaluate_project_ids,
            )
            if zoom_level == self.ZOOM_LEVELS[0]:
                result.update({
                    "start_date": start_date,
                    "end_date": end_date,
                })
            result[zoom_level] = contents

        return {
            "grid": result,
            # "keysWithDuplicates" makes sure de-duplication is skipped in the frontend;
            # this would break grid values otherwise, since duplicates are to be expected
            "keysWithDuplicates": self.ZOOM_LEVELS,
        }
