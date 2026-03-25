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
        self.create_prop("sclt", "0", "Show Class Tree (0=only for not classified objects, 1=always).")


pre = []
post = [UpdateSystemProperties]
