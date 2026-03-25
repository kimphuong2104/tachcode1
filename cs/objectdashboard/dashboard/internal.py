#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import json
import logging

from cs.platform.web import PlatformApp
from cs.platform.web.rest.app import get_collection_app
from cs.platform.web.root import Internal, get_internal

from cs.objectdashboard.config import DashboardConfig


class InternalDashboardApp(PlatformApp):
    PATH = "cs-objdashboard-dashboard"

    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(cls.PATH)


@Internal.mount(app=InternalDashboardApp, path=InternalDashboardApp.PATH)
def _():
    return InternalDashboardApp()


class ContextObjectDashboardConfig:
    def __init__(self, context_object_id):
        self.context_object_id = context_object_id

    def get_config(self):
        # NOTE: Access and existence is checked in DashboardConfig.get_config
        return DashboardConfig.get_config(self.context_object_id)


@InternalDashboardApp.path(
    model=ContextObjectDashboardConfig, path="{context_object_id}"
)
def _(context_object_id):
    return ContextObjectDashboardConfig(context_object_id)


def _load_settings(config):
    """
    This method extracts and parses the settings of a given widget config.
    Raises an HTTPBadRequest if the settings are not JSON conform.

    :param config: dictionary containing the settings as JSON
    :type config: dict
    """
    value = config["settings"]

    if value is None or value == "":
        return {}
    try:
        returnValue = json.loads(value)
        return returnValue
    except ValueError as e:
        logging.exception("Error parsing dashboard configuration: %s %s", e, value)
        raise


@InternalDashboardApp.json(model=ContextObjectDashboardConfig)
def _(model, request):
    # result will contain the layout specified by the dashboard frame
    # config in settings and a list of all widgets, each a dictionary
    # with the specified atrributes in the config
    result = {
        "settings": {},
        "widgets": [],
        "isError": False,
    }

    config = model.get_config()
    collection_app = get_collection_app(request)

    # each pos in config is a entry for a widget
    for pos in config:
        # check for JSON errors
        isError = False
        try:
            settings = _load_settings(pos)
        except ValueError:
            settings = {}
            isError = True
        # if the widget is the dashboard frame
        if pos["component_name"] == "dashboard":
            # only get the layout in settings
            result["settings"] = settings
            # settings is semantical correct if
            # an entry 'layout' is there
            # and the value for layout is more than nothing
            hasSemanticalError = False
            try:
                hasSemanticalError = len(settings["layout"]) == 0
            except KeyError as e:
                logging.exception(
                    "Error parsing dashboard frame configuration: %s %s", e, settings
                )
                hasSemanticalError = True
            # if the config is faulty or semantical incorrect,
            # this is an error
            if isError or hasSemanticalError:
                result["isError"] = True
                # if the dashboard frame config is faulty, no widget
                # will be rendered, so we can skip loading their configs
                break
        else:
            # for every other widget get all parameters
            comp_config = {
                "@id": request.link(pos, app=collection_app),
                "name": pos["component_name"],
                "cdb_object_id": pos["cdb_object_id"],
                "xpos": pos["xpos"],
                "ypos": pos["ypos"],
                "settings": settings,
                "isError": isError,
            }
            result["widgets"].append(comp_config)

    return result
