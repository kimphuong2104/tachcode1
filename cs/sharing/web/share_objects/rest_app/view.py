#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

from cdb import ElementsError
from cdb.elink import isCDBPC
from cdb.objects.core import ByID
from cdb.platform.gui import Message
from cdb.platform.mom.operations import OperationInfo
from cs.platform.web.root import get_v1
from morepath.error import LinkError

from cs.sharing import Sharing, errors
from cs.sharing.share_objects import OP_NAME
from cs.sharing.web.share_objects import GROUP_SIZE_LIMIT

from .main import ShareObjectsApp
from .model import (
    AttachmentData,
    DeleteModel,
    GetMembersModel,
    GroupSizeModel,
    NewSharingGroupModel,
    NewSharingModel,
    ObjectGroupModel,
    RecipientAccessCheckModel,
    RecipientsData,
    ResolveModel,
)

__docformat__ = "restructuredtext en"

from cs.sharing.web.share_objects.rest_app import util


def get_default_view(request, obj, app):
    try:
        return request.view(obj, app=app)
    except LinkError:
        raise Exception(
            errors.getMessage("cdb_sharing_rest_inactive") % obj.GetClassname()
        )


@ShareObjectsApp.json(model=NewSharingModel, request_method="POST")
def share_objects(model, request):
    with errors.ServerResult(errors.CreateSharingFailed, {"sharing": None}) as server:
        json = request.json
        recipients = model.getRecipients(json)

        attachments = model.getAttachments(json)
        checked = {}

        for attachment in attachments:
            access_check_result = util.check_attachment_recipient_access(
                attachment, recipients
            )
            if not access_check_result:
                raise ElementsError(
                    Message.GetMessage("share_objects.recipient_denied")
                )
            class_name = attachment.GetClassname()
            if class_name not in checked:
                op_info = OperationInfo(class_name, OP_NAME)
                result = bool(op_info and (op_info.offer_in_webui() or isCDBPC()))
                checked[class_name] = result
            else:
                result = checked[class_name]
            if not result:
                raise ElementsError(
                    Message.GetMessage(
                        "share_objects.missing_authorization",
                    )
                )
        if not recipients:
            server.result.update({"error": dict(errors.EmptyRecipientsList(""))})
        else:
            # model and Sharing handle parsing and escaping
            sharing = Sharing.createFromObjects(
                objects=attachments,
                subjects=recipients,
                text=model.getText(json),
            )
            rest_app = get_v1(request).child("collection")
            server.result = {"sharing": get_default_view(request, sharing, rest_app)}

    return server.result


@ShareObjectsApp.json(model=RecipientsData, request_method="GET")
def get_recipients(model, request):
    def common_role_json(role):
        result = dict(role)
        result["cdb_classname"] = "cdb_global_role"
        result["@type"] = "/api/v1/class/cdb_global_role"
        result["@id"] = role.role_id
        result["system:description"] = role.GetDescription()
        result["system:icon_link"] = role.GetObjectIcon()
        return result

    with errors.ServerResult(
        errors.GetRecipientsFailed, {"recipients": None}
    ) as server:
        rest_app = get_v1(request).child("collection")
        result = []
        recipients = model.getAllRecipients(
            request.params["query"], int(request.params["limit"]) + 1
        )

        has_more = len(recipients) > int(request.params["limit"])
        if has_more:
            del recipients[-1]

        for recipient in recipients:
            if not hasattr(recipient, "cdb_classname"):
                # custom JSON transformation for global roles
                recipient_json = common_role_json(recipient)
            else:
                recipient_json = get_default_view(request, recipient, rest_app)
                if recipient.GetClassname() == "angestellter":
                    if recipient.Organization:
                        recipient_json["org_name"] = recipient.Organization.name
                    else:
                        recipient_json["org_name"] = ""
                    recipient_json["first_last"] = "%s %s" % (
                        recipient.firstname,
                        recipient.lastname,
                    )
                    recipient_json["last_first"] = "%s %s" % (
                        recipient.lastname,
                        recipient.firstname,
                    )

            result.append(recipient_json)
        server.result = {"recipients": result, "has_more": has_more}

    return server.result


@ShareObjectsApp.json(model=ObjectGroupModel, request_method="GET")
def get_object_group(model, request):
    with errors.ServerResult(
        errors.GetObjectGroupFailed, {"recipients": None}
    ) as server:
        rest_app = get_v1(request).child("collection")
        result = model.getPersons(
            request.params["group_id"], request.params["attachment_id"]
        )
        server.result = {
            "recipients": [get_default_view(request, p, rest_app) for p in result],
            "error": None,
        }

    return server.result


@ShareObjectsApp.json(model=GroupSizeModel, request_method="POST")
def get_group_size(model, request):
    with errors.ServerResult(
        errors.ResolveGroupFailed, {"group": None, "size": -1}
    ) as server:
        size = model.getGroupSize(request.json["group"])
        server.result = {
            "size": size,
            "group": request.json["group"],
            "error": None,
            "size_limit": GROUP_SIZE_LIMIT,
        }

        if size == 0:
            server.result.update({"error": dict(errors.EmptyRecipientsList(""))})

        rest_app = get_v1(request).child("collection")
        result = ResolveModel().resolveGroupToUsers(request.json["group"])
        server.result["users"] = [
            get_default_view(request, p, rest_app) for p in result
        ]

    return server.result


@ShareObjectsApp.json(model=ResolveModel, request_method="POST")
def get_resolve(model, request):
    with errors.ServerResult(
        errors.ResolveGroupFailed, {"users": None, "group": None}
    ) as server:
        rest_app = get_v1(request).child("collection")
        result = model.resolveGroupToUsers(request.json["group"])
        server.result = {
            "users": [get_default_view(request, p, rest_app) for p in result],
            "group": request.json["group"],
            "error": None,
        }

    return server.result


@ShareObjectsApp.json(model=GetMembersModel, request_method="POST")
def get_members(model, request):
    with errors.ServerResult(errors.ResolveGroupFailed, {"members": None}) as server:
        rest_app = get_v1(request).child("collection")
        result = model.getGroupMembers(request.json["group"])
        server.result = {
            "members": [get_default_view(request, m, rest_app) for m in result],
            "group": request.json["group"],
            "index": request.json["index"],
            "error": None,
        }

    return server.result


@ShareObjectsApp.json(model=AttachmentData, request_method="GET")
def get_attachments(attachments, request):
    with errors.ServerResult(
        errors.GetAttachmentsFailed, {"attachments": None}
    ) as server:
        rest_app = get_v1(request).child("collection")
        result = []
        for attachment, groups in attachments.loadObjects(request):
            attachment_json = get_default_view(request, attachment, rest_app)
            attachment_json["object_groups"] = [
                get_default_view(request, group, rest_app) for group in groups
            ]
            result.append(attachment_json)
        server.result = {"attachments": result}

    return server.result


@ShareObjectsApp.json(model=NewSharingGroupModel, request_method="POST")
def save_recipients(model, request):
    with errors.ServerResult(
        errors.SaveRecipientsFailed, {"sharing_group": None}
    ) as server:
        newGroup = model.createSharingGroup(request.json)
        rest_app = get_v1(request).child("collection")
        server.result = {"sharing_group": get_default_view(request, newGroup, rest_app)}

    return server.result


@ShareObjectsApp.json(model=DeleteModel, request_method="POST")
def delete_object(model, request):
    with errors.ServerResult(errors.DeleteFailed, request.json) as server:
        model.delete(request.json)
        server.result = request.json

    return server.result


@ShareObjectsApp.json(model=RecipientAccessCheckModel, request_method="POST")
def check_recipient_access(model, request):
    request_json = request.json
    recipients = request_json.get("recipients", [])
    entered_attachments = request_json.get("attachments", [])
    attachments = [
        ByID(attachment.get("cdb_object_id")) for attachment in entered_attachments
    ]
    result = []
    for recipient in recipients:
        if isinstance(recipient, dict):
            recipient_result = model.check_group_access(recipient, attachments)
            result.append(
                {
                    "group_id": recipient.get("cdb_object_id", None),
                    "result": recipient_result,
                }
            )
        else:
            recipient_result = model.check_access(recipient, attachments)
            result.append({"id": recipient, "result": recipient_result})
    return {"result": result}
