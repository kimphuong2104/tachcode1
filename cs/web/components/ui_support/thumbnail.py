# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import absolute_import
from cdb.platform.mom.operations import OperationInfo
from cs.platform.web.uisupport import get_uisupport


def get_thumbnail_upload(obj, request):
    classname = obj.GetClassname()
    opinfo = OperationInfo(classname, "ce_set_thumbnail")
    if opinfo and obj.CheckAccess("ce_set_thumbnail"):
        result = request.view(opinfo, app=get_uisupport(request))
        return result
    return None
