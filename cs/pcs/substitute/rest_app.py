# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST backend for `cs.pcs.substitute`, mounted at
``/internal/project_substitutes``
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import webob
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal

from cs.pcs.substitute.main import MOUNT
from cs.pcs.substitute.rest_app_model import (
    ProjectTeamModel,
    RoleComparisonModel,
    SubjectModel,
    SubstitutionInfoModel,
    UserSubstitutesModel,
)
from cs.pcs.substitute.util import get_rest_objects


def get_project_context_id(cdb_project_id):
    """
    :param cdb_project_id: The project's ID
    :type cdb_project_id: basestring

    :returns: Org. context data. See
        `cs.pcs.substitute.util.get_org_context_attributes` for
        details.
    :rtype: dict
    """
    return {"cdbpcs_prj_role": {"cdb_project_id": cdb_project_id, "ce_baseline_id": ""}}


class App(JsonAPI):
    @staticmethod
    def get_app(request):
        return get_internal(request).child(MOUNT)


@Internal.mount(app=App, path=MOUNT)
def _mount_app():
    return App()


@App.path(path="{rest_key}/team", model=ProjectTeamModel)
def get_team_model(request, rest_key):
    return ProjectTeamModel(rest_key)


@App.json(model=ProjectTeamModel)
def get_team(model, request):
    fromDate = request.params.get("fromDate", None)
    toDate = request.params.get("toDate", None)

    team_members = model.getProjectTeamMembers()

    result = get_rest_objects(team_members, request)
    info = SubstitutionInfoModel.getInfo(result, fromDate, toDate)

    return {
        "objects": result,
        "fullySubstituted": info,
    }


@App.path(path="substitutes/{persno}", model=UserSubstitutesModel)
def get_substitutes_model(request, persno):
    return UserSubstitutesModel(persno)


@App.json(model=UserSubstitutesModel)
def get_substitutes(model, request):
    fromDate = request.params.get("fromDate", None)
    toDate = request.params.get("toDate", None)

    substitutes, user_objs = model.getUserSubstitutes(fromDate, toDate)
    users = get_rest_objects(user_objs, request)

    return {
        "substitutes": get_rest_objects(substitutes, request),
        "users": users,
    }


@App.path(path="substitution_info/{cdb_project_id}", model=SubstitutionInfoModel)
def get_substitution_info_model(request, cdb_project_id):
    return SubstitutionInfoModel(cdb_project_id)


@App.json(model=SubstitutionInfoModel)
def get_substitution_info(model, request):
    fromDate = request.params.get("fromDate", None)
    toDate = request.params.get("toDate", None)
    team_members = get_rest_objects(model.getProjectTeamMembers(), request)
    result = model.getInfo(team_members, fromDate, toDate)
    return {"fullySubstituted": result}


@App.path(path="roles/{substitute_oid}/{cdb_project_id}", model=RoleComparisonModel)
def get_roles_model(request, substitute_oid, cdb_project_id):
    return RoleComparisonModel(substitute_oid, get_project_context_id(cdb_project_id))


@App.json(model=RoleComparisonModel)
def get_roles(model, request):
    result = model.getAllRoles(request)
    result["substitute_oid"] = model.substitute_oid
    return result


@App.path(path="role_assignment/{classname}/{role_id}/{persno}", model=SubjectModel)
def get_role_assignment_model(request, classname, role_id, persno):
    return SubjectModel(classname, role_id, persno)


@App.json(model=SubjectModel, request_method="POST")
def assign_role(model, request):
    substitute_oid = request.json.get("substitute_oid", None)
    cdb_project_id = request.json.get("cdb_project_id", None)

    if not substitute_oid or not cdb_project_id:
        raise webob.exc.HTTPBadRequest

    if model.role_context.role_classname == "cdbpcs_prj_role":
        model.setOrgContext({"cdb_project_id": cdb_project_id})

    if request.json["deleteAssignment"]:
        model.unassignRole()
    else:
        model.assignRole()

    team_model = ProjectTeamModel(cdb_project_id)
    team_members = get_rest_objects(team_model.getProjectTeamMembers(), request)

    roles_model = RoleComparisonModel(
        substitute_oid, get_project_context_id(cdb_project_id)
    )
    roles = roles_model.getAllRoles(request)

    return {
        "team": {
            "objects": team_members,
            # no fullySubstituted info because of missing dates
        },
        "roles": roles,
        "substitute_oid": substitute_oid,
        "cdb_project_id": cdb_project_id,
    }
