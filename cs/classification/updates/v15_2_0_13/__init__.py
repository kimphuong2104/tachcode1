# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi


class UpdateNormalizedFloats(object):

    def run(self):
        sqlapi.SQLupdate(
            "cs_object_property_value set float_value_normalized = 0.0 where property_type = 'float' and float_value = 0.0 and float_value_normalized is null"
        )


pre = []
post = [UpdateNormalizedFloats]
