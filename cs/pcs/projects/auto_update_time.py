#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.objects import Object


class AutoUpdateBase(Object):
    @classmethod
    def GetMapping(cls):
        # no read access check because class is not access controlled
        return {entry.auto_update_time: entry.description for entry in cls.Query()}


class AutoUpdateTime(AutoUpdateBase):
    __maps_to__ = "cdbpcs_auto_update_time"
    __classname__ = "cdbpcs_auto_update_time"


class ProjectAutoUpdateTime(AutoUpdateBase):
    __maps_to__ = "cdbpcs_proj_auto_update_time"
    __classname__ = "cdbpcs_proj_auto_update_time"
