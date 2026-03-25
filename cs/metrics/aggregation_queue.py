#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Module aggregation_queue

This is the documentation for the aggregation_queue module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import sys

from cdb import mq
from cdb import ddl

from cs.metrics import qualitycharacteristics


class AggregationQueueJob(mq.Job):
    def run(self):
        qc = qualitycharacteristics.ObjectQualityCharacteristic\
            .ByKeys(cdb_object_id=self.qc_object_id)
        if qc:
            qc.aggregate_up_structure(force=True)
            self.done()
        else:
            self.fail(10,
                      "cannot find quality characteristic "
                      "%s" % self.cdb_object_id)


queue = mq.Queue("aggregation_queue", AggregationQueueJob,
                 fieldlist=[
                     ddl.Char("qc_object_id",
                              qualitycharacteristics.ObjectQualityCharacteristic
                              .cdb_object_id.length)])

if __name__ == "__main__":
    sys.exit(queue.cli(sys.argv))
