#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Module qc_engine


Quality character computation services.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import os

from cdb import misc
from cdb import rte
from cdb.platform.uberserver import Services
from cdb.uberserver.process import Process
from cdb.uberserver.mqsvc import MessageQueueService

# Exported objects
__all__ = ["QCAggregationEngine",
           "QCComputationEngine"]


class QCComputationEngine(Process):
    """ Uberserver service for computing quality character.
    """

    def __init__(self, site):
        toolname = rte.runtime_tool("powerscript")
        servicename = "Quality Characteristic Computation Engine"
        super(QCComputationEngine, self).__init__(site, servicename, None, toolname)

    def get_args(self):
        from cdb.comparch import modules
        mod_dir = modules.get_module_dir("cs.metrics")
        script = os.path.join(mod_dir, "services.py")
        args = super(QCComputationEngine, self).get_args()
        args.extend(["--nologin", script, "--compute"])
        return args

    @classmethod
    def install(cls, svcname, host, site, *args, **kwargs):
        """ Install configuration for this service.
        """
        if len(Services.get_services(svcname, None)) != 0:
            return  # Install me only once.
        super(QCComputationEngine, cls).install(svcname, host, site, *args, **kwargs)
        misc.cdblogv(misc.kLogMsg, 2,
                     "QC Engine: cls._create_basic_configuration(%s, autostart=True, options={})" % svcname)
        return cls._create_basic_configuration(svcname, host, site, arguments="",
                                               autostart=True, options={'--user': 'qccomputationengine'})

    def start(self):
        """ Starts the service
        """
        super(QCComputationEngine, self).start()
        return self

    def stop(self):
        """ Stops the service.
        """
        super(QCComputationEngine, self).stop()

    def __str__(self):
        return "%s is %s running" % (self.servicename,
                                     "" if self.is_alive() else "*NOT*")


class QCAggregationEngine(MessageQueueService):
    """ Service for computing aggregate values of quality character.
    """

    def __init__(self, site):
        servicename = "Quality Characteristic Aggregation Engine"
        super(QCAggregationEngine, self).__init__(
            site, servicename, None,
            "cs.metrics.aggregation_queue")

    @classmethod
    def install(cls, svcname, host, site, arguments="", options=None, *args, **kwargs):
        if not svcname:
            svcname = cls.fqpyname()

        # Set autostart
        kwargs["autostart"] = True

        if options is None:
            options = {'--user': 'qcaggregationengine'}
        else:
            options['--user'] = 'qcaggregationengine'
        return super(QCAggregationEngine, cls).install(svcname, host, site, arguments,
                                                       options, *args, **kwargs)

    @classmethod
    def get_service_user(cls):
        svcs = Services.get_services("%s.%s" % (cls.__module__, cls.__name__),
                                     site="default")
        if svcs:
            return svcs[0].get_option("--user")


if __name__ == '__main__':
    pass
