# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import defaultdict
from itertools import groupby
from operator import itemgetter
from urllib.parse import quote, urlencode

from cdb import rte, sig, ue
from cdb.lru_cache import lru_cache
from cdb.objects import Forward, IconCache, _LabelValueAccessor
from cs.taskmanager.mixin import WithTasksIntegration

from cs.pcs.projects.common import assert_team_member

fRatingValue = Forward("cs.pcs.checklists.RatingValue")


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def mytasks_add_cl_cards():
    from cs.taskmanager.web.main import TasksApp

    original_setup = TasksApp.update_app_setup

    def setup_checklist_cards(app, app_setup, model, request):
        original_setup(app, app_setup, model, request)
        from cs.pcs.checklists.web import setup_cards

        setup_cards(model, request, app_setup)

    TasksApp.update_app_setup = setup_checklist_cards


@lru_cache(maxsize=1, clear_after_ue=False)
def get_ratings():
    ratings = fRatingValue.Query(access="read", addtl="ORDER BY name, rating_id")
    result = defaultdict(dict)
    for (name, rating_id), rating in groupby(ratings, itemgetter("name", "rating_id")):
        result[name][rating_id] = list(rating)[0]
    return result


def get_rating(schema_name, rating_id):
    ratings = get_ratings()
    return ratings[schema_name][rating_id]


class ChecklistWithCsTasks(WithTasksIntegration):
    def getCsTasksContexts(self):
        return [self.Project]

    def csTasksDelegate_get_default(self):
        return self.csTasksDelegate_get_project_manager()

    def csTasksDelegate(self, ctx):
        prj_id = None
        for obj in ctx.objects:
            if not prj_id:
                prj_id = obj["cdb_project_id"]
            if prj_id and prj_id != obj["cdb_project_id"]:
                raise ue.Exception("cdbpcs_delegate")
        assert_team_member(ctx, self.cdb_project_id)
        self.Super(ChecklistWithCsTasks).csTasksDelegate(ctx)

    def preset_csTasksDelegate(self, ctx):
        prj_id = None
        for obj in ctx.objects:
            if not prj_id:
                prj_id = obj["cdb_project_id"]
            if prj_id and prj_id != obj["cdb_project_id"]:
                raise ue.Exception("cdbpcs_delegate")
        ctx.set("cdb_project_id", prj_id)
        self.Super(ChecklistWithCsTasks).preset_csTasksDelegate(ctx)


class ChecklistItemWithCsTasks(WithTasksIntegration):
    def getCsTasksContexts(self):
        return [self.Project]

    def csTasksDelegate_get_default(self):
        return self.csTasksDelegate_get_project_manager()

    def csTasksDelegate(self, ctx):
        prj_id = None
        for obj in ctx.objects:
            if not prj_id:
                prj_id = obj["cdb_project_id"]
            if prj_id and prj_id != obj["cdb_project_id"]:
                raise ue.Exception("cdbpcs_delegate")
        assert_team_member(ctx, self.cdb_project_id)
        self.Super(ChecklistItemWithCsTasks).csTasksDelegate(ctx)

    def preset_csTasksDelegate(self, ctx):
        prj_id = None
        for obj in ctx.objects:
            if not prj_id:
                prj_id = obj["cdb_project_id"]
            if prj_id and prj_id != obj["cdb_project_id"]:
                raise ue.Exception("cdbpcs_delegate")
        ctx.set("cdb_project_id", prj_id)
        self.Super(ChecklistItemWithCsTasks).preset_csTasksDelegate(ctx)

    def _getObjIcon(cls, icon_id, obj):
        return IconCache.getIcon(icon_id, None, _LabelValueAccessor(obj, True))

    def _getCustomRatingIcon(cls, icon_id, args_dict):
        return f'/resources/icons/byname/{quote(icon_id.encode("utf-8"))}?{urlencode(args_dict)}'

    def getCsTasksStatusData(self, rating=None):
        @lru_cache(maxsize=50, clear_after_ue=False)
        def _status_data(rating_schema, rating):
            _icon_id_ = "cdbpcs_cl_item_object"
            if rating:
                url_icon = self._getCustomRatingIcon(
                    _icon_id_,
                    {
                        "rating_id": (
                            "" if rating.rating_id == "clear" else rating.rating_id
                        ),
                        "rating_scheme": rating_schema,
                        "type": "Checklist",
                    },
                )
            else:
                url_icon = self._getObjIcon(_icon_id_, self)

            if rating:
                data = {
                    "label": rating.Value[""] if rating else "",
                    "dialog": {
                        "rating_id": rating.rating_id,
                        "rating_value_de": rating.rating_value_de,
                        "rating_value_en": rating.rating_value_en,
                    },
                    "icon": url_icon,
                    "priority": rating.position,
                }
            else:
                # no "clear" rating defined
                data = {
                    "label": "--",
                    "icon": url_icon,
                    "dialog": None,
                    "priority": None,
                }

            return data

        rating_schema = self.rating_scheme

        if rating is None:
            rating = get_rating(
                rating_schema, self.rating_id if self.rating_id else "clear"
            )

        return _status_data(rating_schema, rating)

    def getCsTasksNextStatuses(self):
        ratings_raw = get_ratings()[self.rating_scheme]
        ratings = sorted(
            [
                self.getCsTasksStatusData(ratings_raw[rid])
                for rid in ratings_raw
                if rid != self.rating_id
            ],
            key=lambda x: (x["priority"]),
        )
        return ratings
