# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.platform import PropertyDescription
from cdb.platform import PropertyValue


class UpdateSystemProperties(object):

    def create_prop(self, attr, value, helptext):
        prop = PropertyDescription.ByKeys(attr)
        if not prop:
            PropertyDescription.Create(
                attr=attr, helptext=helptext, cdb_module_id="cs.classification"
            )
            PropertyValue.Create(
                attr=attr,
                value=value,
                subject_type="Common Role",
                subject_id="public",
                cdb_module_id="cs.classification"
            )

    def run(self):
        self.create_prop("qcla", "1", "Case sensitive classification search (0=never, 1=always).\nChanging requires reindex of solr core for classification.")
        self.create_prop("adpr", "1", "Enable additional classification properties (0=never, 1=always).")
        self.create_prop("mxcl", "10000", "Maximum number of data records for a single classification query")


pre = []
post = [UpdateSystemProperties]
