#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import auth, sqlapi, util
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common.lists.list import ListConfig
from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.projects.common.webdata.util import get_classinfo_REST, get_sql_condition
from cs.pcs.projects.indicators import ResolveIndicators

APP = "cs-pcs-indicators"


def get_app_url_patterns(request):
    app = IndicatorsApp.get_app(request)
    models = [
        ("indicator_overlay", IndicatorOverlayModel, []),
        ("indicator", IndicatorModel, []),
    ]
    return get_url_patterns(request, app, models)


class IndicatorModel:
    def ensure_contains(self, request, key):
        if key not in request.json:
            logging.exception(
                "IndicatorModel: JSON does not include '%s'",
                key,
            )
            raise HTTPBadRequest()
        return request.json[key]

    def resolve_indicators(self, request):

        indicator_names = self.ensure_contains(request, "indicators")
        rest_name = self.ensure_contains(request, "rest_name")

        cldef, table = get_classinfo_REST(rest_name)

        if not cldef or not table:
            logging.exception("IndicatorModel: JSON contains invalid rest_name")
            raise HTTPBadRequest()

        table_keys = cldef.getKeyNames()
        requested_ids = request.json["keys"] if "keys" in request.json else None

        if requested_ids:
            condition = get_sql_condition(
                table,
                table_keys,
                [_id.split("@") for _id in requested_ids],
            )
            allowed_ids = [
                [record[key] for key in table_keys]
                for record in sqlapi.RecordSet2(table, condition, access="read")
            ]
            if not allowed_ids:
                logging.warning(
                    "IndicatorModel - Either '%s' has no read access on '%s': '%s'"
                    "or the objects do not exist.",
                    auth.persno,
                    rest_name,
                    requested_ids,
                )
                return {}
            result_iterator = filter(
                lambda x: x, ResolveIndicators(rest_name, allowed_ids, indicator_names)
            )
            result = list(result_iterator)
            if len(result) > 1:
                logging.exception(
                    "IndicatorModel: More than one type of indicators returned."
                )
                raise HTTPBadRequest()
            return result[0] if result else {}
        else:
            return {}


class IndicatorOverlayModel:
    def get_overlay(self, request):
        try:
            list_config_name = request.json["list_config_name"]
            restKey = request.json["restKey"]

            if not list_config_name:
                raise ValueError
            if not restKey:
                raise ValueError
        except (KeyError, ValueError) as exc:
            logging.exception("get_overlay, request: %s", request)
            raise HTTPBadRequest() from exc

        list_configs = [
            lc
            for lc in ListConfig.KeywordQuery(name=list_config_name)
            if lc.CheckAccess("read")
        ]
        if not list_configs:
            logging.warning(
                "IndicatorOverlayModel - Either '%s' has no read access on ListConfig '%s'"
                " or the ListConfig does not exists.",
                auth.persno,
                list_config_name,
            )
            # return an empty list result
            return {
                "title": util.get_label("web.cs-pcs-widgets.list_widget_error_title"),
                "items": [],
                "displayConfigs": {},
                "configError": util.get_label(
                    "cs.pcs.projects.common.lists.list_access_error"
                ).format(list_config_name),
            }
        else:
            list_config = list_configs[0]
            return list_config.generateListJSON(request, restKey)


class IndicatorsApp(JsonAPI):
    @staticmethod
    def get_app(request):
        "Try to look up /internal/cs.pcs.projects"
        return get_internal(request).child(APP)


@Internal.mount(app=IndicatorsApp, path=APP)
def _mount_app():
    return IndicatorsApp()


@IndicatorsApp.path(path="indicator", model=IndicatorModel)
def get_indicator_model():
    return IndicatorModel()


@IndicatorsApp.json(model=IndicatorModel, request_method="POST")
def _(model, request):
    return model.resolve_indicators(request)


@IndicatorsApp.path(path="indicator/overlay", model=IndicatorOverlayModel)
def get_indicator_overlay_model():
    return IndicatorOverlayModel()


@IndicatorsApp.json(model=IndicatorOverlayModel, request_method="POST")
def _(model, request):
    return model.get_overlay(request)
