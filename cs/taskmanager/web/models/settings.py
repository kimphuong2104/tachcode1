#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb.util import get_label
from cs.taskmanager.conf import get_cache
from cs.taskmanager.web.models import ModelWithUserSettings, offer_admin_ui
from cs.taskmanager.web.models.views import ViewBaseModel
from cs.taskmanager.web.util import get_class_rest_id

STATUS_CHANGE = "statusChange"
OUTLET_NAMES = "detailOutletNames"


class Settings(ModelWithUserSettings):
    """
    Serves administrative settings such as

    - refreshInterval,
    - table columns (defaults) and
    - mapping.

    Usually, these are just served once.
    """

    def _get_refresh_interval(self):
        return self._get_setting("refreshInterval")

    def _get_columns(self):
        def to_json(coldef):
            return {
                "id": coldef.name,
                "contentRenderer": coldef.plugin_component,
                "label": get_label(coldef.name) if coldef.name else "",
                "tooltip": coldef.resolve_tooltip(),
                "width": "{}px".format(coldef.width),
                "position": coldef.col_position,
                "visible": bool(coldef.visible),
                "kind": 1,
            }

        json_columns = [
            to_json(coldef)
            for coldef in sorted(
                get_cache().columns.values(),
                key=lambda x: (
                    x.col_position is None,
                    x.col_position,
                ),
            )
        ]
        return json_columns

    def _get_task_classes_data(self):
        cache = get_cache()
        data = {STATUS_CHANGE: {}, OUTLET_NAMES: {}}
        for task_class in cache.classes.values():
            data[STATUS_CHANGE][
                task_class.name
            ] = task_class.get_status_change_operation()
            data[OUTLET_NAMES][task_class.name] = task_class.details_outlet_name
        return data

    def get_tasks_settings(self, request):
        cache = get_cache()
        cache.initialize()

        result = {}
        view_model = ViewBaseModel()

        # might raise cdb.util.ErrorMessage
        result["views"] = view_model.get_all_views(request)

        task_classes_data = self._get_task_classes_data()

        result["settings"] = {
            "offerAdminUI": offer_admin_ui(),
            "refreshInterval": self._get_refresh_interval(),
            "types": [
                get_class_rest_id(classname, request)
                for classname in sorted(cache.classnames)
            ],
            "contexts": cache.context_classnames,
            "columns": self._get_columns(),
            "mapping": cache.mapping,
            "statusChange": task_classes_data[STATUS_CHANGE],
            "detailOutletNames": task_classes_data[OUTLET_NAMES],
        }
        return result
