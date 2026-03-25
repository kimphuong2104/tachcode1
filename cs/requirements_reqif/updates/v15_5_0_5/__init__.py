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


class FillReqIFProfileAttributeClassname(object):

    def run(self):
        from cdb import sqlapi
        sqlapi.SQLupdate("cdbrqm_reqif_profile_attrs SET cdb_classname='cdbrqm_reqif_profile_attrs' WHERE cdb_classname IS NULL")
        sqlapi.SQLupdate("cdbrqm_reqif_profile_attrs SET cdb_classname='cdbrqm_reqif_profile_enum_attr' WHERE data_type='enumeration'")


pre = []
post = [FillReqIFProfileAttributeClassname]
