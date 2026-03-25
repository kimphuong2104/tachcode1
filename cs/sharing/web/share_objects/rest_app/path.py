#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"


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


@ShareObjectsApp.path(path="", model=NewSharingModel)
def get_object(request):
    return NewSharingModel()


@ShareObjectsApp.path(path="recipients", model=RecipientsData)
def get_recipients(request):
    return RecipientsData()


@ShareObjectsApp.path(path="object_group", model=ObjectGroupModel)
def get_object_group(request):
    return ObjectGroupModel()


@ShareObjectsApp.path(path="group_size", model=GroupSizeModel)
def get_group_size(request):
    return GroupSizeModel()


@ShareObjectsApp.path(path="resolve_group", model=ResolveModel)
def get_resolve(request):
    return ResolveModel()


@ShareObjectsApp.path(path="get_group_members", model=GetMembersModel)
def get_members(request):
    return GetMembersModel()


@ShareObjectsApp.path(path="attachments", model=AttachmentData)
def get_attachments(request):
    return AttachmentData()


@ShareObjectsApp.path(path="save_recipients", model=NewSharingGroupModel)
def save_recipients(request):
    return NewSharingGroupModel()


@ShareObjectsApp.path(path="delete_object", model=DeleteModel)
def delete_object(request):
    return DeleteModel()


@ShareObjectsApp.path(path="check_recipient", model=RecipientAccessCheckModel)
def check_recipient_access(request):
    return RecipientAccessCheckModel()
