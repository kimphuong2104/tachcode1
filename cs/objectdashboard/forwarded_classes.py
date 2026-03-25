#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb.objects import Forward


def fwd(name):
    return Forward("cs.objectdashboard." + name)


DashboardConfig = fwd("config.DashboardConfig")
DashboardDefaultConfig = fwd("config.DashboardDefaultConfig")
Widget = fwd("config.Widget")
DashboardDefault = fwd("dashboard_setup.DashboardDefault")
