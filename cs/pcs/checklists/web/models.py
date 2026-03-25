#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import os

from cdb import auth, i18n, sqlapi
from cdb import util as cdb_util
from cdb.objects import _LabelValueAccessor
from cdb.objects.iconcache import IconCache
from cdb.platform import gui, mom, olc
from cs.platform.web import rest
from webob.exc import HTTPBadRequest, HTTPForbidden, HTTPNotFound

from cs.pcs.checklists import Checklist, ChecklistItem, RatingValue
from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects.common.lists.helpers import (
    _generateDisplayConfig,
    _generateListItems,
)
from cs.pcs.projects.common.lists.list import ListItemConfig
from cs.pcs.projects.common.webdata import util

RATING_VALUE_TABLE_NAME = RatingValue.__maps_to__
CHECKLIST_ITEM_CLASS_NAME = "cdbpcs_cl_item"
RATING_VALUE_CLASS_NAME = "cdbpcs_rat_val"


class RatingsModel:
    def _get_rating_val_icon(self, icon_id, rv):
        """
        Get the icon for a given rating.

        :param icon_id: The icon id which should be used to get the icon.
        :param rv: Rating value for evaluating the identifier of a given icon.

        :returns: Icon URL
        :rtype: str
        """
        return IconCache.getIcon(icon_id, accessor=_LabelValueAccessor(rv))

    def get_rating_values(self):
        """
        Get all active (e.g. non-obsolete) rating values in the system.

        :returns: Rating value dictionaries where each dictionary contains
            the keys `label`, `position`, `irrelevant`, `icon` and `color`.
            Rating values are indexed in a top-level dict
            by `name` (of its rating scheme) and `id`, where the innermost
            dictionaries (the leaves) are stored in lists.

        :rtype: dict

        .. rubric :: Example Return Value

        .. code-block :: python

            {
                "Grades": {
                    1: [{
                        "label": "Uno",
                        "position": 0L,
                        "irrelevant": True,
                        "color": None,
                        "icon": "/resources/icons/byname/foo"
                    }],
                },
                "RedGreenYellow": {
                    "rot": [{
                        "label": "Rouge",
                        "position": 1L,
                        "irrelevant": False,
                        "color": "elements-primary",
                        "icon": "/resources/icons/byname/bar"
                    }],
                },
            }
        """
        condition = util.get_sql_condition(RATING_VALUE_TABLE_NAME, ["obsolete"], [[0]])

        rating_cdef, _ = util.get_classinfo(RATING_VALUE_CLASS_NAME)
        icon_id = rating_cdef.getObjectIconId()

        current_language = i18n.default()
        label = f"rating_value_{current_language}"

        def serialize_rating(rating_value):
            return {
                "label": rating_value[label],
                "position": rating_value["position"],
                "irrelevant": bool(rating_value["irrelevant"]),
                "color": rating_value["color"],
                "mandatory_remark": bool(rating_value["mandatory_remark"]),
                "icon": self._get_rating_val_icon(icon_id, rating_value),
            }

        return util.get_grouped_data(
            RATING_VALUE_TABLE_NAME,
            condition,
            "name",
            "rating_id",
            transform_func=serialize_rating,
        )


class ModelWithChecklist:
    def __init__(self, cdb_project_id, checklist_id):
        kwargs = {"cdb_project_id": cdb_project_id, "checklist_id": checklist_id}
        checklist = get_and_check_object(Checklist, "read", **kwargs)

        if not checklist:
            raise HTTPNotFound()
        self.checklist = checklist


class ChecklistItemsModel(ModelWithChecklist):
    def get_checklist_items(self, request):
        condition = (
            f"cdb_project_id='{self.checklist.cdb_project_id}' "
            f"AND checklist_id='{self.checklist.checklist_id}'"
        )
        checklist_items = ChecklistItem.Query(
            condition,
            access="read",
            addtl="ORDER BY position",
        )
        collection = rest.get_collection_app(request)
        return [request.view(item, app=collection) for item in checklist_items]

    def _get_sql_patterns(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            mapping_pattern = "SELECT {}, {} FROM dual"
            fname = "change_cli_position_oracle.sql"
        else:
            mapping_pattern = "SELECT {}, {}"
            fname = "change_cli_position.sql"

        fpath = os.path.join(os.path.dirname(__file__), fname)

        with open(fpath, "r", encoding="utf8") as sqlf:
            return mapping_pattern, sqlf.read()

    def _update_positions(self, cli_ids):
        """
        Update checklist item positions with a single SQL statement.
        New positions will be steps of 10 in order of appearance in `cli_ids`.

        Positions of items not in that list are pushed back so they appear
        after items in that list.
        """
        step = 10
        mapping_pattern, stmt_pattern = self._get_sql_patterns()
        mapping_stmt = "\n    UNION ALL ".join(
            [
                mapping_pattern.format((index + 1) * step, cli_id)
                for index, cli_id in enumerate(cli_ids)
            ]
        )
        stmt = stmt_pattern.format(
            offset=len(cli_ids) * step,
            cl=self.checklist,
            changed_ids=", ".join([str(x) for x in cli_ids]),
            changemap=mapping_stmt,
        )
        sqlapi.SQL(stmt)

    def set_checklist_item_positions(self, request):
        # SQL injection shouldn't be possible via integer values
        if any(not isinstance(x, int) for x in request.json):
            logging.error("non-integer checklist item ID: %s", request.json)
            raise HTTPBadRequest

        if self.checklist.CheckAccess("save"):
            self._update_positions(request.json)
        else:
            raise HTTPForbidden


class RuleReferenceModel(ModelWithChecklist):
    def get_rule_references(self, request):
        return self.checklist.RuleReferences  # return rule_ref objs


# Helper method
def _is_evaluated_rating(rating_id):
    # Return True if given rating value is not "", Null, None or "clear".
    if rating_id:
        return rating_id != "clear"
    else:
        return False


class ChecklistsProgressModel:
    def get_checklists_progress(self, request):
        """
        :param request: the request to retrieve the checklist progress.

        :returns: dict of values indexed by each pair of project ids and
                  checklist id given by the request

        :raises HTTPBadRequest: if the key 'checklist_keys' is not present in
                                json-payload of the request or the value for
                                this key is not a list.

        Calls get_checklist_progress for each pair of project id and checklist
        id given by the request to determine values for frontend to render
        checklist progress. Utilizes RatingsModel.
        """

        if "checklist_keys" not in request.json:
            logging.error("No Keys for Checklists")
            raise HTTPBadRequest

        checklist_progress = {}
        checklist_keys = request.json["checklist_keys"]

        if not isinstance(checklist_keys, list):
            logging.error("Keys for Checklist not a list")
            raise HTTPBadRequest

        # NOTE: If no checklist_keys are given, the request basically asks
        #       for no checklists, so an empty list can be returned.
        if len(checklist_keys) > 0:
            # create a single SQL condition for all key pairs
            conditions = []
            for key_pair in checklist_keys:
                pid = sqlapi.quote(key_pair["cdb_project_id"])
                cid = sqlapi.quote(key_pair["checklist_id"])
                c = f"(cdb_project_id='{pid}' AND checklist_id='{cid}')"
                conditions.append(c)

            condition = " OR ".join(conditions)
            checklists = Checklist.Query(condition, access="read")
            if not checklists:
                # If no checklists where found we can return an empty result early.
                logging.exception(
                    "ChecklistProgressModel - '%s' has no read access on checklists: '%s'",
                    auth.persno,
                    checklist_keys,
                )
                return checklist_progress
            # get all checklist items for all checklists and group them by
            # cdb_project_id and checklist_id
            grouped_cl_items = util.get_grouped_data(
                "cdbpcs_cl_item", condition, "cdb_project_id", "checklist_id"
            )
            # retrieve all ratings via RatingsModel
            # NOTE: This retrieves the rating icons used for ChecklistItems
            #       which are the intended icons to use in this case
            ratings_model = RatingsModel()
            rating_values = ratings_model.get_rating_values()

            # determine progress values for each checklist
            for cl in checklists:
                pid = cl.cdb_project_id
                cid = cl.checklist_id
                cl_items = []
                if pid in grouped_cl_items and cid in grouped_cl_items[pid]:
                    cl_items = grouped_cl_items[pid][cid]
                progress_values = self.get_checklist_progress(
                    request, cl, rating_values, cl_items
                )
                if pid not in checklist_progress:
                    checklist_progress.update({pid: {}})
                checklist_progress[pid][cid] = progress_values
        return checklist_progress

    def get_checklist_progress(self, request, cl, rating_values, checklist_items):
        # pylint: disable=too-many-locals
        """
        :param request: the Request to retrieve the checklist progress.
        :param cl: checklist to retrieve progress for
        :param rating_values: dict of with ratings, return value of
            RatingsModel.get_rating_values
        :param checklist_items: list of ChecklistItem of given Checklist

        :returns: Dict of values:
                status, string - status of checklist,
                rating, string - rating of checklist,
                icon, string - url for corresponding rating icon,
                color, string - css-color variable for rating
                max_items, int - total amount of checklist items of checklist
                evaluated_items, int - amount of evaluated checklist items
                max_objects, int - total amount of expected work objects,
                    0 if Checklist is not of type 'Deliverable'
                evaluated_objects, int - amount of added work objects,
                    0 if Checklist is not of type 'Deliverable'
        :rtype: dict

        Determines several values needed in the frontend to render the progress
        of the Checklist. Utilizes RuleReferenceModel.
        """

        # init return values
        rating = ""
        icon = ""
        color = ""
        max_items = 0
        evaluated_items = 0
        max_objects = 0
        evaluated_objects = 0

        isDeliverable = cl.type == "Deliverable"
        status = olc.StateDefinition.ByKeys(
            statusnummer=cl.status, objektart=cl.cdb_objektart
        ).StateText[""]
        cdb_project_id = cl.cdb_project_id
        checklist_id = cl.checklist_id

        # get current rating icon and color
        rating_id = cl.rating_id if _is_evaluated_rating(cl.rating_id) else "clear"
        rating_scheme = cl.rating_scheme
        icon = rating_values[rating_scheme][rating_id][0]["icon"]
        color = rating_values[rating_scheme][rating_id][0]["color"]
        rating = rating_values[rating_scheme][rating_id][0]["label"]

        # determine max and evaluated cl_items
        max_items += len(checklist_items)

        evaluated_items += len(
            [
                cl_item
                for cl_item in checklist_items
                if _is_evaluated_rating(cl_item["rating_id"])
            ]
        )

        # Get work objects if cl is a deliverable
        if isDeliverable:
            # overwrite icon and color for deliverable
            color = ""
            icon = ""
            # get also rule references
            rule_ref_model = RuleReferenceModel(cdb_project_id, checklist_id)
            rule_refs = rule_ref_model.get_rule_references(request)
            objs = cl.Collection
            max_objects += len(rule_refs)
            # evaluate rules
            evaluated_objects += len(
                [
                    rule_ref
                    for rule_ref in rule_refs
                    if len(rule_ref.Rule.match(objs)) > 0
                ]
            )

        return {
            "status": status,
            "rating": rating,
            "icon": icon,
            "color": color,
            "max_items": max_items,
            "evaluated_items": evaluated_items,
            "max_objects": max_objects,
            "evaluated_objects": evaluated_objects,
            "isDeliverable": isDeliverable,
        }


class WorkObjectsModel:
    def check_work_objects(self, request):
        """
        :param request: the request to retrieve the work objects status.

        :returns: dict of values indexed by each pair of project ids and
                  checklist id given by the request

        :raises HTTPBadRequest: if the key 'checklist_keys' is not present in
                                json-payload of the request or the value for
                                this key is not a list.
        """

        if "checklist_keys" not in request.json:
            logging.error("No Keys for Checklists")
            raise HTTPBadRequest

        result = {}
        checklist_keys = request.json["checklist_keys"]

        if not isinstance(checklist_keys, list):
            logging.error("Keys for Checklist not a list")
            raise HTTPBadRequest

        # NOTE: If no checklist_keys are given, the request basically asks
        #       for no checklists, so an empty list can be returned.

        if len(checklist_keys) > 0:
            cids = []
            # Note: We assume that all Checklists are of the same project
            cdb_project_id = None
            for key_pair in checklist_keys:
                try:
                    cdb_project_id = key_pair["cdb_project_id"]
                    checklist_id = key_pair["checklist_id"]
                except IndexError as exc:
                    raise HTTPBadRequest(
                        "WorkObjectsModel: Malformed payload."
                    ) from exc
                cids.append(checklist_id)

            checklists = [
                cl
                for cl in Checklist.KeywordQuery(
                    cdb_project_id=cdb_project_id, checklist_id=cids
                )
                if cl.CheckAccess("read")
            ]

            for checklist in checklists:
                for ref in checklist.RuleReferences:
                    rule = ref.Rule

                    if not rule:
                        logging.error(
                            "WorkObjectsModel: invalid rule reference: '%s'",
                            dict(ref),
                        )
                        continue
                    pid = checklist.cdb_project_id
                    cid = checklist.checklist_id
                    matching_objects = rule.match(checklist.Collection)
                    if pid not in result:
                        result[pid] = {}
                    if cid not in result[pid]:
                        result[pid][cid] = {}
                    result[pid][cid][rule.name] = bool(matching_objects)
        return result

    def _get_list_items_and_config_entries(
        self, list_item_config, obj_handles_dict, class_name, config_name, request
    ):
        # check if list_item_config is valid
        if not list_item_config.isValid():
            logging.exception(
                gui.Message.GetMessage(
                    "cdbpcs_list_list_item_config_invalid", config_name
                )
            )
            return {}, [], True

        # get all display_config entries
        list_of_config_entries = list_item_config.AllListItemConfigEntries
        # generate Display config
        (
            display_config,
            dict_of_attribute_functions,
            isDisplayConfigError,
        ) = _generateDisplayConfig(list_of_config_entries, class_name)
        if isDisplayConfigError:
            return {}, [], True

        list_of_items, isListError = _generateListItems(
            config_name,
            dict_of_attribute_functions,
            obj_handles_dict,
            obj_handles_dict.keys(),
            request,
        )
        if isListError:
            return {}, [], True
        return display_config, list_of_items, False

    def get_work_objects_documents(self, request):
        class_name = "documents"

        try:
            rule_name = request.json["rule_name"]
            config_name = request.json["configName"]
            cdb_project_id = request.json["cdb_project_id"]
            checklist_id = request.json["checklist_id"]
        except KeyError as exc:
            raise HTTPBadRequest from exc
        # get checklist and check access right
        checklist = Checklist.ByKeys(
            cdb_project_id=cdb_project_id, checklist_id=checklist_id
        )
        if not (checklist and checklist.CheckAccess("read")):
            raise HTTPNotFound()

        # check if work object belongs to deliverable
        try:
            rule = [
                ref.Rule
                for ref in checklist.RuleReferences
                if ref.Rule and ref.Rule.name == rule_name
            ][0]
        except IndexError as exc:
            raise HTTPBadRequest(f"Provided rule '{rule_name}' not found.") from exc
        # find all docs matching the rule
        matching_object_ids = [
            obj.cdb_object_id for obj in rule.match(checklist.Collection)
        ]
        # get objectHandles of found objects if read access is granted upon
        # by calling getObjectHandlesFromObjectIDs with check_read_access=True
        obj_handles_dict = mom.getObjectHandlesFromObjectIDs(
            matching_object_ids, False, True
        )
        result = {}
        if obj_handles_dict and len(obj_handles_dict) > 0:
            # get ListItemConfig of given name
            try:
                list_item_config = ListItemConfig.KeywordQuery(name=config_name)[0]
            except IndexError as exc:
                raise HTTPBadRequest(
                    f"ListItemConfig '{config_name}' not found."
                ) from exc

            (
                display_config,
                list_of_items,
                isError,
            ) = self._get_list_items_and_config_entries(
                list_item_config,
                obj_handles_dict,
                class_name,
                config_name,
                request,
            )
            errorMsg = ""
            if isError:
                errorMsg = cdb_util.get_label(
                    "cs.pcs.projects.common.lists.list.config_error_list_item_config"
                ).format(config_name)
            result = {
                "title": "",
                "items": list_of_items,
                "displayConfigs": {config_name: display_config},
                "configError": errorMsg,
            }

        checklist_rest_key = f"{checklist.cdb_project_id}@{checklist.checklist_id}"

        return {
            "restKey": checklist_rest_key,
            "ruleName": rule.name,
            "data": result,
        }
