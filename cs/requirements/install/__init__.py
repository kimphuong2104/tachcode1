# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module install

This is the documentation for the install module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class RemoveDuplicatedCatalogValues(object):
    def run(self):
        from cdb import sqlapi
        sqlapi.SQLdelete(u"FROM cdbrqm_requirement_category WHERE name IN ('Header', 'Function', 'Requirement', 'Use Case', 'User Story')")


class InstallRQMClassification(object):
    def run(self):
        import os
        from cs.classification.scripts.import_tool import run
        data_path = os.path.join(os.path.abspath(os.path.dirname(os.path.join(__file__))), 'rqm_classification')
        run(data_path)


__all__ = ['pre']

pre = [RemoveDuplicatedCatalogValues]
post = [InstallRQMClassification]
