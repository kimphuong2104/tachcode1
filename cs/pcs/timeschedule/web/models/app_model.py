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
from cdbwrapc import CDBClassDef
from cs.platform.web.rest import get_collection_app
from webob.exc import HTTPBadRequest, HTTPInternalServerError

from cs.pcs.timeschedule.web.mapping import ColumnDefinition, ColumnMapping
from cs.pcs.timeschedule.web.models.base_model import ScheduleBaseModel


class AppModel(ScheduleBaseModel):
    """
    Application settings are persisted per user and time schedule.
    They include these keys:

    collapsedRows
        Object with keys rowNumber of rows the user has collapsed.
        Values are usually all ``True``, but don't matter much.
    """

    def _serialize_column(self, column):
        """
        :param column: Column definition to serialize.
        :type column: cs.pcs.timeschedule.web.mapping.ColumnDefinition

        :returns: JSON-serialized column definition for frontend use.
        :rtype: dict

        :raises AttributeError: if ``column`` is missing attributes.
        :raises TypeError: if ``column.label`` is not a ``str``, but truthy.
        """
        label = ""
        if column.label:
            label = util.get_label(column.label)
        return {
            "visible": column.visible,
            "position": column.col_position,
            "width": column.width,
            "id": column.id,
            "label": label,
            "contentRenderer": column.component,
            "showBaselineData": column.show_baseline_data,
        }

    def _get_table_settings(self):
        """
        :returns: Settings for gantt table.
        :rtype: dict

        :raises webob.exc.HTTPInternalServerError: if any mapping for
            ``self.column_group`` is invalid.

        :raises TypeError: if table columns are not iterable.

        .. warning ::

            See ``_serialize_column`` for other possible exceptions.

        """
        columns = ColumnDefinition.ByGroup(self.column_group)
        try:
            mapping = ColumnMapping.ByColumns(
                self.column_group, [column.id for column in columns]
            )
        except ValueError as exc:
            raise HTTPInternalServerError from exc
        # iterate over self.plugins to construct mapping
        # {classname: {classLabel: string, rootClassName: string}, ...}
        plugins = {}
        for _, plugin in self.plugins.items():
            class_def = CDBClassDef(plugin.classname)
            plugins[plugin.classname] = {
                "label": class_def.getDesignation(),
                "rootClassName": plugin.classname,
                "olcFieldName": plugin.olc_attr,
            }
            # check if plugin class has subclasses
            sub_class_names = class_def.getSubClassNames([])
            if sub_class_names:
                for sub_class_name in sub_class_names:
                    plugins[sub_class_name] = {
                        "label": CDBClassDef(sub_class_name).getDesignation(),
                        "rootClassName": plugin.classname,
                        "olcFieldName": plugin.olc_attr,
                    }

        return {
            # FixedColumns default value is set by the frontEnd component Schedule.jsx
            "columns": [self._serialize_column(column) for column in columns],
            "mapping": mapping,
            "plugins": plugins,
        }

    def get_app_data(self, request):
        """
        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Application settings for the frontend.
        :rtype: dict

        :raises TypeError: if user settings don't support ``__getitem__``.
        """
        user_settings = self.get_user_settings(self.context_object_id)
        return {
            "contextObject": request.view(
                self.context_object,
                app=get_collection_app(request),
                name="relship-target",
            ),
            "collapsedRows": user_settings["collapsedRows"],
            "table": self._get_table_settings(),
        }

    def _update_user_settings(self, **updates):
        """
        Merge existing user settings in the database with ``updates``.

        :param updates: Data to update in existing user settings.
        :type updates: dict

        :returns: Resulting user settings.
        :rtype: dict

        :raises AttributeError: if old settings is not a ``dict``.
        :raises RuntimeError: if user is not allowed to store the settings.
        :raises ValueError: if any setting ID is ``None``.
        :raises TypeError: if any setting ID contain non-string values
            or updates settings are not JSON-serializable.
        """
        old_settings = self.get_user_settings(self.context_object_id)
        old_settings.update(updates)
        new_settings = json.dumps(old_settings)
        util.PersonalSettings().setValue(
            self.setting_id1,
            self.context_object_id,
            new_settings,
        )
        return old_settings

    def update_app_data(self, request):
        """
        Updates application-level settings.

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :raises webob.exc.HTTPBadRequest: if ``request`` does not contain
            the key "collapsedRows".

        .. warning ::

            See ``_update_user_settings`` for other possible exceptions.

        """
        try:
            collapsedRows = request.json["collapsedRows"]
            self._update_user_settings(
                collapsedRows=collapsedRows,
            )
        except KeyError as exc:
            logging.error(
                "update_app_data: invalid JSON payload: %s",
                request.json,
            )
            raise HTTPBadRequest from exc
