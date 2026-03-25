# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This creates the property rmil if needed
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.platform import PropertyDescription
from cdb.platform import PropertyValue


class UpdateSystemProperties(object):

    def create_prop(self, attr, value, helptext):
        prop = PropertyDescription.ByKeys(attr)
        if not prop:
            PropertyDescription.Create(
                attr=attr, helptext=helptext, cdb_module_id="cs.requirements"
            )
            PropertyValue.Create(
                attr=attr,
                value=value,
                subject_type="Common Role",
                subject_id="public",
                cdb_module_id="cs.requirements"
            )

    def run(self):
        self.create_prop("rmil", "info", "Requirements Management (Export/Import) Interface Log Level")


pre = []
post = [UpdateSystemProperties]
