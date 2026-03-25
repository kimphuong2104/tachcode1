#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


from cdb import sqlapi, util
from cdb.comparch import protocol


class InitCategCounter(object):
    def run(self):  # pylint: disable=no-self-use
        # Initialize the cdb_counter for the document categories to the
        # highest value currently in use.
        # The field cdb_doc_categ.categ_id is a char field in the DB -> must
        # convert to int to get the correct max.
        rset = sqlapi.RecordSet2("cdb_doc_categ", columns=["categ_id"])
        if rset:
            categ_ids = []
            for rec in rset:
                try:
                    categ_ids.append(int(rec.categ_id))
                except Exception:  # noqa E722 # nosec # pylint: disable=W0703
                    pass
            max_id = max(categ_ids)
            protocol.logMessage("Set counter 'doc_categ_id' to %d" % max_id)
            util.set_min_counter_value("doc_categ_id", max_id)


post = [InitCategCounter]
