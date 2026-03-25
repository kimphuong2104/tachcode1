#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
"""
from cdb.comparch import protocol


class CheckInstalledService(object):
    def run(self):
        from cdb.platform import uberserver

        # Check old service configuration
        powerreports_server_service = uberserver.Services.get_local_service(
            "cs.tools.powerreports.powerreports_server.PowerReportsServer", None
        )
        # Check installed service and further check its arguments
        if powerreports_server_service:
            if len(powerreports_server_service.arguments) == 0:
                # No arguments configured, nothing to update
                powerreports_server_service = None
        if powerreports_server_service is not None:
            protocol.logMessage("Updating PowerReportsServer service")
            self._update_service(powerreports_server_service)
        else:
            protocol.logMessage("No PowerReportsServer service need to be updated")

    def _update_service(self, service):
        # Update service arguments
        service.Update(arguments="")
