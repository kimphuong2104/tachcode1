#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.util import get_label
from cs.platform.web.root.main import Root
from cs.web.components.embedded_page import EmbeddedPageApp, EmbeddedPageModel
from webob.exc import HTTPNotFound

from cs.pcs.helpers import get_and_check_object
from cs.pcs.timeschedule import TimeSchedule

APP_LEGACY = "timeschedule_legacy"


class EmbeddedTimeScheduleApp(EmbeddedPageApp):
    pass


@Root.mount(app=EmbeddedTimeScheduleApp, path=APP_LEGACY)
def _mount_app():
    return EmbeddedTimeScheduleApp()


class EmbeddedTimeScheduleModel(EmbeddedPageModel):
    def __init__(self, cdb_object_id):
        super().__init__()
        kwargs = {"cdb_object_id": cdb_object_id}
        self.timeschedule_object = get_and_check_object(TimeSchedule, "read", **kwargs)
        if self.timeschedule_object is None:
            raise HTTPNotFound

    def get_timeschedule(self):
        return self.timeschedule_object

    def get_embedded_page_url(self):
        ts_obj = self.get_timeschedule()
        if ts_obj:
            return ts_obj.getLegacyProjectPlanURL()
        return ""


@EmbeddedTimeScheduleApp.path(path="{cdb_object_id}", model=EmbeddedTimeScheduleModel)
def _get_model(cdb_object_id):
    model = EmbeddedTimeScheduleModel(cdb_object_id)
    if model.get_timeschedule() is None:
        return None
    return model


@EmbeddedTimeScheduleApp.view(
    model=EmbeddedTimeScheduleModel, name="document_title", internal=True
)
def _get_document_title(model, request):
    label = get_label("cdbpcs_time_schedule")
    obj = model.get_timeschedule()
    return f"{label} {obj.name}" if obj else label
