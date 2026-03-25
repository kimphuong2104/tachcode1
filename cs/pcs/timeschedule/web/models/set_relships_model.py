#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import ElementsError, transaction, util
from cdb.constants import kOperationDelete
from cdb.objects.operations import operation
from webob.exc import HTTPBadRequest, HTTPForbidden

from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.timeschedule.web.models.update_model import UpdateModel


class SetRelshipsModel(UpdateModel):
    def __init__(self, context_object_id, task_object_id, relship_name):
        """
        :raises webob.exc.HTTPBadRequest: if ``relship_name`` is neither
            "predecessors" nor "successors".
        """
        UpdateModel.__init__(self, context_object_id, True)

        if relship_name not in ["predecessors", "successors"]:
            logging.error(
                "SetRelshipsModel: unknown relship_name '%s'",
                relship_name,
            )
            raise HTTPBadRequest

        self.task_object_id = task_object_id
        self.relship_name = relship_name

        self.task = self.get_object_from_uuid(self.task_object_id)

    def get_relships(self):
        field_name = {
            "predecessors": "succ_task_oid",
            "successors": "pred_task_oid",
        }[self.relship_name]

        return TaskRelation.KeywordQuery(**{field_name: self.task_object_id})

    def delete_old_relships(self, new_relships, existing_relships):
        for old_relship in existing_relships:
            if not SetRelshipsModel.relationship_exists(old_relship, new_relships):
                operation(kOperationDelete, old_relship)

    def assert_is_task(self, obj):
        if not isinstance(obj, Task):
            msg = util.ErrorMessage("cdbpcs_taskrel_tasks_only")
            raise ElementsError(f"{msg}")

    @staticmethod
    def relationships_identical(obj1, obj2):
        attrs = ["pred_task_oid", "succ_task_oid"]
        for attr in attrs:
            if obj1[attr] != obj2[attr]:
                return False
        return True

    @staticmethod
    def relationships_gap_identical(obj1, obj2):
        return (
            obj1["minimal_gap"] == obj2["minimal_gap"]
            and obj1["rel_type"] == obj2["rel_type"]
        )

    @staticmethod
    def relationship_exists(relationship, existing_relationships):
        for rs in existing_relationships:
            if SetRelshipsModel.relationships_identical(relationship, rs):
                return rs
        return None

    def create_new_relships(self, new_relships, existing_relships):
        result = []
        for new_relship in new_relships:
            if self.relship_name == "predecessors":
                predecessor = self.get_object_from_uuid(new_relship["pred_task_oid"])
                self.assert_is_task(predecessor)
                obj_ids = {
                    "cdb_project_id2": predecessor.cdb_project_id,
                    "task_id2": predecessor.task_id,
                    "cdb_project_id": self.task.cdb_project_id,
                    "task_id": self.task.task_id,
                }
            else:
                successor = self.get_object_from_uuid(new_relship["succ_task_oid"])
                self.assert_is_task(successor)
                obj_ids = {
                    "cdb_project_id2": self.task.cdb_project_id,
                    "task_id2": self.task.task_id,
                    "cdb_project_id": successor.cdb_project_id,
                    "task_id": successor.task_id,
                }

            new_relship.update(obj_ids)
            db_relship = SetRelshipsModel.relationship_exists(
                new_relship, existing_relships
            )
            if db_relship and not self.relationships_gap_identical(
                new_relship, db_relship
            ):
                db_relship.modifyRelation(
                    minimal_gap=new_relship["minimal_gap"],
                    rel_type=new_relship["rel_type"],
                )
            if db_relship:
                result.append(db_relship)
            else:
                result.append(TaskRelation.createRelation(**new_relship))
        return result

    def set_relships(self, request):
        """
        Replaces a single task's predecessors or successors (depends on the
            value of ``self.relship_name``).

        :param request: The request sent from the frontend. Validated by
            ``_parse_update_payload``.
        :type request: morepath.Request

        :returns: resulting predecessors or successors of the task.

        :raises webob.exc.HTTPBadRequest: if the key ``relships`` is missing
            in request's JSON payload or contains an invalid value.
        :raises webob.exc.HTTPInternalServerError: if the update fails.
        """
        try:
            relships = request.json["relships"]
        except KeyError as exc:
            logging.error(
                "set_relships: 'relships' missing in request JSON: %s",
                request.json,
            )
            raise HTTPBadRequest from exc

        self.verify_writable(self.task, ["predecessors", "successors"])

        try:
            self.assert_is_task(self.task)

            with transaction.Transaction():
                rs_in_db = self.get_relships()
                # create relationships, that not yet exist
                new_rs = self.create_new_relships(relships, rs_in_db)
                # delete relationships, that no longer exist
                self.delete_old_relships(new_rs, rs_in_db)
        except ElementsError as e:
            logging.exception("set_relships failed")
            # we just guess it's forbidden at this point
            raise HTTPForbidden(str(e)) from e

        return self.get_changed_data(request)
