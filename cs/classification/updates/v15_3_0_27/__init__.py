# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi


class CreateIndex(object):

    def run(self):
        try:
            stmt = "CREATE INDEX cs_class_property_code_id_min ON cs_class_property (code,cdb_object_id)"
            sqlapi.SQL(stmt)
        except Exception:
            # index already exists
            pass

pre = []
post = [CreateIndex]
