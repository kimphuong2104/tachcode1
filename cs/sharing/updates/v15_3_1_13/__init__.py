#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import logging
import os
import shutil

from cdb import CADDOK
from cdb.comparch import protocol

log = logging.getLogger(__name__)

__revision__ = "$Id$"


class CreateShareObjectsQueueConfTask(object):
    def run(self):
        conf = "share_objects_queue.conf"
        try:
            conf_path = os.path.join(CADDOK.BASE, "etc", conf)
            if os.path.exists(conf_path):
                protocol.logMessage("{} already exists".format(conf_path))
                return
            protocol.logMessage("Creating default {}".format(conf_path))
            source = os.path.abspath(
                os.path.join(__file__, "..", "..", "..", "templates", "etc", conf)
            )
            shutil.copyfile(source, conf_path)
        except Exception as exc:  # pylint: disable=W0703
            protocol.logError(
                "Failed to copy %s to %s" % (source, conf_path), "%s" % exc
            )


post = [CreateShareObjectsQueueConfTask]
