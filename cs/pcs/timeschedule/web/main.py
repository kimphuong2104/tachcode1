#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import os

from cdb import rte, sig
from cdb.platform.gui import Label
from cs.platform.web import static

from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.timeschedule.web.mapping import ColumnDefinition
from cs.pcs.timeschedule.web.models.app_model import AppModel
from cs.pcs.timeschedule.web.models.baseline_model import (
    BaselineDataModel,
    BaselineModel,
)
from cs.pcs.timeschedule.web.models.data_model import DataModel
from cs.pcs.timeschedule.web.models.elements_model import ElementsModel
from cs.pcs.timeschedule.web.models.read_only_model import ReadOnlyModel
from cs.pcs.timeschedule.web.models.set_attribute_model import SetAttributeModel
from cs.pcs.timeschedule.web.models.set_dates_model import SetDatesModel
from cs.pcs.timeschedule.web.models.set_relships_model import SetRelshipsModel
from cs.pcs.timeschedule.web.models.update_model import UpdateModel

APP = "cs-pcs-timeschedule-web"
VERSION = "15.4.4"


def get_app_url_patterns(request):
    """
    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: Link patterns (URLs with placeholders) indexed by names to be
        referenced by the frontend.
    :rtype: dict

    :raises morepath.error.LinkError: if any model class cannot be linked to.
    """
    from cs.pcs.timeschedule.web.rest_app import RestApp

    ctx_id = "context_object_id"
    models = [
        ("appData", AppModel, [ctx_id]),
        ("tableData", DataModel, [ctx_id]),
        ("elementsData", ElementsModel, [ctx_id]),
        ("readOnlyData", ReadOnlyModel, [ctx_id]),
        ("updateData", UpdateModel, [ctx_id]),
        ("setDates", SetDatesModel, [ctx_id, "content_object_id"]),
        ("setRelships", SetRelshipsModel, [ctx_id, "task_object_id", "relship_name"]),
        ("setAttribute", SetAttributeModel, [ctx_id, "cdb_object_id"]),
        ("getBaselines", BaselineModel, ["project_oid"]),
        ("getBaselineData", BaselineDataModel, [ctx_id]),
    ]
    return get_url_patterns(request, RestApp.get_app(request), models)


def get_reltypes():
    label_ids = [
        "web.timeschedule.taskrel-AA",
        "web.timeschedule.taskrel-AE",
        "web.timeschedule.taskrel-EA",
        "web.timeschedule.taskrel-EE",
    ]
    languages = ["d", "uk"]
    result = {}
    labels = Label.KeywordQuery(ausgabe_label=label_ids)

    for language in languages:
        for label in labels:
            result[label[language]] = label["d"]

    return result


def update_app_setup(model, request, app_setup):
    r"""
    Extends ``app_setup`` with link patterns used for asynchronous requests by
    the application frontend. Link patterns are relative URLs with
    placeholders matching this expression:

    .. code-block :: python

        import re
        re.compile(r"\$\{[a-z_\-]+\}")

    Placeholders are variables to be substituted by the frontend before
    accessing a URL.

    Also adds the following time schedule-specific data:
    - Task relationship labels

    :param model: The application's main model.

    :param request: The morepath request (used for link generation).

    :param app_setup: The application setup object.
    :type app_setup: cs.web.components.base.main.SettingDict

    :raises AttributeError: if ``model`` is missing the ``keys`` attribute
        (expected to contain the schedule's ``cdb_object_id``).
    """

    ColumnDefinition.ByGroup.cache_clear()
    app_setup.merge_in(
        [APP],
        {
            "reltype_labels": get_reltypes(),
        },
    )


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js")
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)
