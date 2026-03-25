#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.platform.mom.entities import Class


class CompileAggregationQueue(object):
    """ Compiles class mq_aggregation_queue as predefined field length has changed
    """
    def run(self):
        Class.ByKeys("mq_aggregation_queue").compile(force=True)


pre = []
post = [CompileAggregationQueue]

# Guard importing as main module
if __name__ == "__main__":
    CompileAggregationQueue().run()
