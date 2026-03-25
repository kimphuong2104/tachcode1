#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Register activity stream plugin.
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import util
from cdb.objects.rules import Rule
from cs.activitystream.rest_app.model import SubscriptionCategoryBase

from cs.pcs.projects import Project

__all__ = []


PROJECT_RULE = "cdbpcs: Kosmodrom: My Objects"


class MyProjectSubscriptions(SubscriptionCategoryBase):

    priority = 1

    @property
    def title(self):
        return util.Labels()["pcs_projects"]

    def get_objects(self):
        rule = Rule.ByKeys(name=PROJECT_RULE)
        if rule:
            return [
                proj
                for proj in rule.getObjects(
                    Project, add_expr=self.additional_condition, order_by="project_name"
                )
                if proj.CheckAccess("read")
            ]
        return []
