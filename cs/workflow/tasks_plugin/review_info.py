# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import webob.exc

from cdb.objects.org import User

from cs.platform.web.rest.support import get_restlink
from cs.platform.web.root import Internal
from cs.platform.web.uisupport import get_ui_link
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

from cs.workflow.protocols import MSGDONE
from cs.workflow.protocols import MSGREFUSE
from cs.workflow.tasks import ApprovalTask
from cs.workflow.tasks import ExaminationTask
from cs.workflow.tasks_plugin import PLUGIN
from cs.workflow.tasks_plugin import VERSION

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

MOUNT = "{}/reviews".format(PLUGIN)


class ReviewInfoApp(BaseApp):
    pass


class ReviewInfoModel(object):
    def __init__(self, cdb_process_id, task_id):
        self.task = ApprovalTask.ByKeys(
            cdb_process_id=cdb_process_id,
            task_id=task_id,
        )

        if not self.task:
            raise webob.exc.HTTPNotFound()

    def _get_user(self, review):
        return User.ByKeys(review.personalnummer)

    def _get_review(self, request, task):
        if task.status == task.COMPLETED.status:
            msgtype = MSGDONE
        elif task.status == task.REJECTED.status:
            msgtype = MSGREFUSE
        else:
            raise ValueError(
                "unsupported task status: {}".format(
                    task.status
                )
            )

        protocols = task.Protocols.KeywordQuery(msgtype=msgtype)

        for review in reversed(protocols):  # latest first
            user = self._get_user(review)
            picture = user.GetThumbnailFile()
            return {
                "user_link": get_ui_link(request, user),
                "user_name": user.GetDescription(),
                "user_picture": get_restlink(picture, request),
                "timestamp": review.timestamp.isoformat(),
                "comment": review.description.split("\n", 1)[-1],
            }

        return {}

    def _review_task2json(self, request, task):
        result = {
            "task": {
                "description": task.GetDescription(),
                "status": task.status,
                "status_name": task.joined_status_name,
            },
            "review": self._get_review(request, task),
        }
        return result

    def get_reviews(self, request):
        review_tasks = ExaminationTask.KeywordQuery(
            cdb_process_id=self.task.cdb_process_id,
            status=[
                self.task.COMPLETED.status,
                self.task.REJECTED.status,
            ],
        )
        return [
            self._review_task2json(request, review_task)
            for review_task in review_tasks
            if review_task.CheckAccess("read")
        ]


@Internal.mount(app=ReviewInfoApp, path=MOUNT)
def _mount_app():
    return ReviewInfoApp()


@ReviewInfoApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(PLUGIN, VERSION)
    return "{}-ReviewInfoApp".format(PLUGIN)


@ReviewInfoApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@ReviewInfoApp.path(path="{cdb_process_id}/{task_id}", model=ReviewInfoModel)
def _get_model(cdb_process_id, task_id):
    return ReviewInfoModel(cdb_process_id, task_id)


@ReviewInfoApp.json(model=ReviewInfoModel)
def get_review_info(model, request):
    return {
        "reviews": model.get_reviews(request),
    }
