#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
This module defines the streaming cache publishing service which encapsules
the HOOPS Communicator streaming cache broker server.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import os
import sys
import json

import cs.threedlibs.environment as threedlibs


# Exported objects
__all__ = ['HOOPSConfigGenerator']

FILE_LOCATION = os.path.dirname(__file__)

CONFIG_TEMPLATE_PATH = os.path.join(
    FILE_LOCATION, "resources", "server_config_template.js"
)
CONFIG_TEMPLATE_LOCATION_PLACEHOLDER = "[[config_placeholder]]"

CONFIG_TEMPLATE_SPAWNER_TYPES_PATH_PLACEHOLDER = "[[config_spawner_types_placeholder]]"

ADDITIONAL_CACHE = os.path.join(os.path.dirname(__file__), "models")

LOG = logging.getLogger()

win32 = (sys.platform == "win32")

class HOOPSConfigGenerator(object):

    def __init__(self, sid, config_dir, log_dir, cache_dir, tmp_dir,
                 base_port=None, max_spawn_count=0, spawn_start_port=None,
                 csr_enabled=False, ssr_enabled=False):
        self.config_dir = config_dir
        self.log_dir = log_dir
        self.cache_dir = cache_dir
        self.tmp_dir = tmp_dir
        self.cfg_filename = "server_%s.js" % (sid,)
        self.broker_port = base_port + 1
        self.broker_host = "127.0.0.1"
        self.csr_enabled = csr_enabled
        self.ssr_enabled = ssr_enabled

        spawn_start_port = int(spawn_start_port) if spawn_start_port else 11200

        LOG.info("Broker Service (id=%s) port usage on localhost:", sid)
        LOG.info("Broker Service        HTTP/WebSocket: %s", base_port)
        LOG.info("Hoops Broker          HTTP: %s", self.broker_port)

        self.server_path = self.build_server_config(
            self.cfg_filename,
            max_spawn_count,
            spawn_start_port,
        )

    def check_dirs(self):
        for d in [self.config_dir, self.log_dir, self.cache_dir, self.tmp_dir]:
            try:
                os.makedirs(d)
            except OSError as e:
                if not os.path.exists(d):
                    LOG.exception("Failed to create temporary Broker Service "
                                  "directories: %s" % (e,))

    def build_server_config(self, filename, max_spawn_count, spawn_start_port):
        self.check_dirs()

        config = JSConfig()
        config.set("spawnServerPort", self.broker_port)
        config.set("publicHostname", None)

        config.set("spawnMaxSpawnCount", max_spawn_count)
        config.set("spawnWebsocketPortsBegin", spawn_start_port)

        config.set("modelDirs", [
            ADDITIONAL_CACHE,
            self.cache_dir
        ])
        config.set("workspaceDir", self.tmp_dir)
        config.set("logDir", self.log_dir)

        config.set("csrEnabled", self.csr_enabled)
        config.set("ssrEnabled", self.ssr_enabled)

        # TODO config flags for this?
        config.set("ssrGpuCount", None)
        if not win32:
            config.set("ssrUseEgl", True)
        else:
            config.set("ssrUseEgl", False)

        # The server will always run as a subprocess
        config.set("disableConsoleEnterToShutdown", True)

        # Disable the file server
        config.set("fileServerPort", 0)

        # This should fix SSR when running as a windows service, when set to true
        # Caution: setting this to `True` when not running within a windows service environment
        # results in the ts3d_sc_server.exe not being able to start
        config.set("windowsServiceRespawnEnabled", False)

        config.set("license", threedlibs.SERVER_LICENSE)

        config.set("communicatorDir", threedlibs.COMMUNICATOR_DIR)
        config.set("streamCacheExeFile", threedlibs.STREAM_CACHE_EXECUTABLE_LOCATION)

        return config.build(os.path.join(self.config_dir, filename))


class JSConfig(object):
    def __init__(self):
        self.content = {}

    def set(self, key, value):
        self.content[key] = value

    def get_formatted_config(self):
        return json.dumps(self.content, indent=4, sort_keys=True)

    def build(self, config_file_path):
        with open(CONFIG_TEMPLATE_PATH, "r") as template_file:
            with open(config_file_path, "w") as config_file:
                for template_line in template_file:
                    if CONFIG_TEMPLATE_LOCATION_PLACEHOLDER in template_line:
                        template_line = template_line.replace(
                            CONFIG_TEMPLATE_LOCATION_PLACEHOLDER,
                            self.get_formatted_config()
                        )
                    if CONFIG_TEMPLATE_SPAWNER_TYPES_PATH_PLACEHOLDER in template_line:
                        template_line = template_line.replace(
                            CONFIG_TEMPLATE_SPAWNER_TYPES_PATH_PLACEHOLDER,
                            json.dumps(threedlibs.CONFIG_SPAWNER_TYPES_PATH)
                        )
                    config_file.write(template_line)
        return config_file_path
