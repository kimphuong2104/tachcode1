#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json
import logging

from cdb import util
from cdb.objects import ByID
from webob.exc import HTTPNotFound

from cs.pcs.timeschedule.web.plugins import WithTimeSchedulePlugin

DEFAULT_SETTING_ID2 = "settings"
DEFAULT_SETTINGS = {
    "collapsedRows": {},
}


class ScheduleBaseModel(WithTimeSchedulePlugin):
    def __init__(self, context_object_id):
        """
        :param context_object_id: cdb_object_id of the context object (should
            be a ``cs.pcs.timeschedule.TimeSchedule`` object, but only
            requires a ``Project`` reference or cardinality 1).
        :type context_object_id: str

        :raises webob.exc.HTTPNotFound: if either the context object or its
            Project do not exist or are not readable by the logged-in user.
        """
        self.context_object_id = context_object_id
        self.context_object = self.get_object_from_uuid(context_object_id)

        # cannot check read access if context object has no project
        if self.context_object.Project:
            self.context_project = self._check_read(self.context_object.Project)
        else:
            self.context_project = None
            logging.warning(
                "base_model: context object '%s' has no Project assigned",
                context_object_id,
            )

        self._setup_scheduling_attributes()  # init self.content_table...
        self.collect_plugins(self.plugin_signal)  # init self.plugins

    def _setup_scheduling_attributes(self):
        # mandatory attrs
        try:
            self.column_group = self.context_object.schedule_column_group
            self.plugin_signal = self.context_object.schedule_plugin_signal
            self.content_table = self.context_object.schedule_content_table
            self.setting_id1 = self.context_object.schedule_setting_id1
        except AttributeError as exc:
            logging.exception(
                "scheduling attributes not found on object '%s'",
                self.context_object.cdb_object_id,
            )
            raise HTTPNotFound from exc

        # optional attrs
        self.content_classname = getattr(
            self.context_object, "schedule_content_classname", self.content_table
        )  # fall back to DB table name
        self.first_page_size = getattr(
            self.context_object, "schedule_first_page_size", 100
        )
        self.with_baselines = getattr(
            self.context_object, "schedule_with_baselines", False
        )

    def _check_read(self, obj):
        """
        :param obj: The object to check "read" access for
        :type obj: cdb.objects.core.Object

        :returns: ``obj``
        :rtype: cdb.objects.core.Object

        :raises AttributeError: if ``obj`` has no attribute ``CheckAccess``.
        :raises TypeError: if ``obj.CheckAccess`` is not callable.
        :raises webob.exc.HTTPNotFound: if ``obj`` does not exist or is not
            readable by the logged-in user.
        """
        readable = obj and obj.CheckAccess("read")
        if not readable:
            logging.error(
                "_check_read failed: obj %s, readable %s",
                obj,
                readable,
            )
            raise HTTPNotFound
        return obj

    def get_object_from_uuid(self, uuid):
        """
        :param uuid: cdb_object_id of object to return
        :type uuid: str

        :returns: The object identified by ``uuid``.
        :rtype: cdb.objects.core.Object

        :raises webob.exc.HTTPNotFound: if object cannot be found or is not
            readable by the logged-in user.
        """
        result = ByID(uuid)
        if not result:
            logging.error("get_object_from_uuid failed: uuid %s", uuid)
            raise HTTPNotFound
        return self._check_read(result)

    def get_user_settings(self, setting_id2):
        """
        :param setting_id2: The secondary ID of the setting to retrieve.
        :type setting_id2: str

        :returns: The deserialized user settings identified by both
            ``self.setting_id1`` and ``setting_id2``
            ("settings IDs").
            Returns safe default if settings can't be read from database:
                1. Either the default setting with setting_id2 "settings"
                   (value of ``DEFAULT_SETTING_ID2``)
                   or - if that fails, too -
                2. hard-coded ``DEFAULT_SETTINGS``
        :rtype: dict
        """
        try:
            # raises KeyError if user settings cannot be found.
            # raises ValueError if any of the settings IDs is None
            # raises NotImplementedError if any of the settings IDs is
            # something other than None or str
            settings_str = util.PersonalSettings().getValue(
                self.setting_id1,
                setting_id2,
            )
            # raises TypeError if user settings are no str
            # raises ValueError if user settings cannot be JSON-deserialized
            return json.loads(settings_str)
        except (KeyError, ValueError, NotImplementedError, TypeError):
            if setting_id2 == DEFAULT_SETTING_ID2:
                return DEFAULT_SETTINGS
            else:
                return self.get_user_settings(DEFAULT_SETTING_ID2)
