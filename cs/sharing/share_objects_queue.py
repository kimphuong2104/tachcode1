#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import json
import logging
import os
import sys
import time
import traceback

from cdb import CADDOK, ddl, mq, rte, ue, util
from cdb.objects import Forward
from cdb.plattools import killableprocess

__all__ = ["NotificationJob", "share_objects_queue"]
__docformat__ = "restructuredtext en"

log = logging.getLogger(__name__)
fUser = Forward("cdb.objects.org.User")
fSharing = Forward("cs.sharing.Sharing")

JOB_ID_PREFIX = "job_id_"


class NotificationJob(mq.Job):
    def getEnqUser(self):
        # use rpartition instead of split to allow '@' signs in login name
        # e.g. for e-mail addresses
        login = self.get("cdbmq_enquser").rpartition("@")[0]
        for user in fUser.KeywordQuery(login=login):
            return user

    def log(self, txt):
        now = time.strftime("%d.%m.%Y %H:%M:%S", time.gmtime())
        util.text_append(
            "mq_share_objects_queue_txt",
            ["cdbmq_id"],
            ["%s" % self.id()],
            "[%s] %s\n" % (now, txt),
        )

    def run(self):
        """
        does not actually run the job, but starts a new subprocess running as
        the job's cdbmq_enquser.
        """
        user = self.getEnqUser()
        if user:
            cmd = [
                rte.runtime_tool("powerscript"),
                "--program-name=share_objects_queue",
                "--user=%s" % user.login,
            ]
            from cs.sharing.share_objects_server import ShareObjectsServer

            language = ShareObjectsServer.get_service_language()
            if language:
                cmd.append("--language=%s" % language)
            killableprocess.check_call(
                cmd + [__file__, "%s%s" % (JOB_ID_PREFIX, self.id())]
            )

    def runAsEnqUser(self):
        """
        actually run the job
        """
        try:
            if self.state() != "P":
                raise ue.Exception("cdb_sharing_inactive_job", self.id())

            sharing = fSharing.ByKeys(self.sharing_object_id)
            if self.sharing_subjects:
                sharing.addSubscriptions(json.loads(self.sharing_subjects))
                # if successful, prevent redundant subscription
                self.sharing_subjects = None

            sharing.sendNotificationSyncronously(None)
            self.done()
        except Exception:  # pylint: disable=W0703
            tb_str = "".join(traceback.format_exception(*sys.exc_info()))
            self.log(tb_str)
            self.fail(1, tb_str)


def ensure_payload_dir():
    if not share_objects_queue.payloaddir:
        share_objects_queue.payloaddir = os.path.join(
            CADDOK.TMPDIR, u"share_objects_queue_payload"
        )


share_objects_queue = mq.Queue(
    "share_objects_queue",
    NotificationJob,
    fieldlist=[
        ddl.Char("sharing_object_id", 40, True),
        ddl.Char("sharing_subject_list", 4000, True),
    ],
)
ensure_payload_dir()


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)-8s] [%(name)s] %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    job_id = None
    for arg in sys.argv:
        try:
            job_id = int(arg.split(JOB_ID_PREFIX, 1)[1])
            break
        except (ValueError, IndexError):
            log.debug("Failed to parse %s", arg)

    if isinstance(job_id, int):
        job = share_objects_queue.job_by_id(job_id)
        job.runAsEnqUser()
    else:
        sys.exit(share_objects_queue.cli(sys.argv))
