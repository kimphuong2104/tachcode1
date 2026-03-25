#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import os
import shutil
from cdb import CADDOK
from cdb.comparch import protocol

class InitWFQueueConfigFile(object):
    def run(self):
        conf = "wfqueue.conf"
        destination = os.path.join(CADDOK.BASE, "etc", conf)

        if os.path.exists(destination):
            protocol.logMessage(
                "Configuration file '{}' already exists".format(destination))
        else:
            source = os.path.join(os.path.dirname(__file__), conf)
            shutil.copyfile(source, destination)
            protocol.logMessage(
                "Configuration file '{}' successfully written".format(
                    destination))
