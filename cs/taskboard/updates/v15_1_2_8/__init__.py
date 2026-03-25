#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import time
from cdb import sqlapi
from cdb import dberrors
from datetime import datetime
from cdb.storage.index.tesjobqueue_utils import Job


class IndexExistingTaskbaords(object):
    def run(self):
        try:
            stmt = "INSERT INTO cdbes_jobs " \
                "(job_id, enqueued, cdb_jobject_id, relation_name, obj_deleted," \
                " job_state, initial_phase, prevent_associated_obj_update)" \
                " SELECT" \
                " cdb_object_id %s '-%s', %s, cdb_object_id, 'cs_taskboard_board', 0, '%s', 0, 0" \
                " FROM cs_taskboard_board" % (sqlapi.SQLstrcat(),
                                              hex(int(time.time()))[2:],
                                              sqlapi.SQLdbms_date(datetime.now()),
                                              Job.waiting)
            sqlapi.SQL(stmt)
        except dberrors.DBConstraintViolation:
            pass


pre = []
post = [IndexExistingTaskbaords]
