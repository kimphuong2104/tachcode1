# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Additional data for the Requirement Overview report
Lists all the RQM_RATING_VALUEs

"""

from __future__ import unicode_literals
from cdb import sqlapi
from cs.tools import powerreports as PowerReports
from cs.classification.tools import get_active_classification_languages

import logging

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ["RequirementRating"]

LOG = logging.getLogger(__name__)


class RequirementRating(PowerReports.CustomDataProvider):
    """ Data provider for comment and ragings of a requirement"""
    # Output is a N list containing all possible ratings
    CARD = PowerReports.N
    # Does not depend on other results
    CALL_CARD = PowerReports.CARD_0

    def __init__(self):
        self.languages = get_active_classification_languages()

    def getSchema(self):
        # Not linked to a relation name or cdb.objects class so no further parameter needed
        schema = PowerReports.XSDType(self.CARD)
        # Add all suported language sources for the classification
        for lan in self.languages:
            language_field = "rqm_evaluation_source_" + str(lan)
            schema.add_attr(language_field, sqlapi.SQL_CHAR)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        rset = sqlapi.RecordSet2("cs_property", "code = 'RQM_RATING_VALUE'")
        if not rset:
            # In case the table is not there, return an empty power report data list
            return result
        set_ratings = sqlapi.RecordSet2("cs_property_value", "property_object_id = '%s' AND is_active=1" % rset[0].cdb_object_id)
        # Not waiting on parent result, empty list
        for sr in set_ratings:
            rd = PowerReports.ReportData(self)  # Add gui languages support
            # Add data for all language fields
            for lan in self.languages:
                field = "rqm_evaluation_source_" + str(lan)
                rd[field] = getattr(sr, "multilang_value_" + lan)
            result.append(rd)
        return result
