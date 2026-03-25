# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Use this script to start a broker service, if you don't have an uberserver running
(e.g. in an edge site).
"""

from cs.threed.services import ThreeDBrokerService
from cdb.platform.uberserver import Services
from cdb.uberserver import usutil

if __name__ == "__main__":
    usutil.pick_platform_reactor()
    from twisted.internet import reactor

    threed_broker_svc = ThreeDBrokerService(Services.get_current_site())
    threed_broker_svc.start()
    try:
        reactor.run()
    finally:
        threed_broker_svc.shutdown()
