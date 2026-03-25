#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module customizes the Elements REST view for Activity Stream Entries
"""
from cs.platform.web import permissions
from cs.platform.web.license import check_license
from cs.platform.web.rest.generic.main import App
from cs.platform.web.rest.generic.view import _object_file_view

from cs.activitystream.objects import ActivityEntry


@App.json(model=ActivityEntry, permission=permissions.ReadPermission)
@check_license
def object_default(self, request):
    # This hides "deleted" entries in the Elements REST API
    if self.is_deleted:
        return None
    return request.view(self, name="base_data")


@App.json(model=ActivityEntry, permission=permissions.ReadPermission, name="file")
def object_file_view(model, request):
    if model.is_deleted:
        return None
    return _object_file_view(model, request)
