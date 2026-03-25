#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.projects.project_structure.views import TreeTableView


class ResourcesTreeTableView(TreeTableView):
    view_name = "resource_schedule"
    LICENSE_FEATURE_ID = "RESOURCES_001"  # TODO
