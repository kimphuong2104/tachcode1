# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module mq_service

Register cs.designpush.mq as a service
"""

from cdb.uberserver.mqsvc import MessageQueueService


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class CadJobQueueService(MessageQueueService):
    """
    Queue for running designpush
    """
    def __init__(self, site):
        super(CadJobQueueService, self).__init__(
            site, "CAD Job Service", None,
            "cs.cadbase.cadjobqueue.cdbcadjobs")
