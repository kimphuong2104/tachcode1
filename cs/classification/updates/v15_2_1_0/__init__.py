# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi, util

from cdb.platform import PropertyDescription
from cdb.platform import PropertyValue


class UpdateMultiline(object):

    def run(self):
        for table_name in ['cs_property', 'cs_class_property']:
            sqlapi.SQLupdate(
                "{} SET multiline = 8 where multiline = 1".format(table_name)
            )
            sqlapi.SQLupdate(
                "{} SET multiline = 1 where multiline = 0 OR multiline is NULL".format(table_name)
            )


class UpdateMxcl(object):

    def run(self):
        mxcl = util.get_prop("mxcl")
        if not mxcl:
            # set mxcl to unlimited if it does not exist
            PropertyDescription.Create(
                attr="mxcl",
                helptext="Maximum number of data records for a single classification query",
                cdb_module_id="cs.classification"
            )
            PropertyValue.Create(
                attr="mxcl",
                value="-1",
                subject_type="Common Role",
                subject_id="public",
                cdb_module_id="cs.classification"
            )
        elif "10000" == mxcl:
            # udpate mxcl to unlimited if it has default value
            prop_value = PropertyValue.KeywordQuery(
                attr="mxcl",
                subject_type="Common Role",
                subject_id="public",
                cdb_module_id="cs.classification"
            )
            prop_value[0].value = "-1"


pre = []
post = [UpdateMxcl, UpdateMultiline]
