# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi


class UpdateCopyClassification(object):

    def run(self):
       sqlapi.SQLupdate(
            "cs_classification_applicabilit SET copy_classification = 1 where copy_classification is NULL"
        )

pre = []
post = [UpdateCopyClassification]
