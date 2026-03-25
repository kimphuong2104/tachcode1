#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.threed.hoops.updates.v15_5_1 import UpdateDefaultSettings


class UpdateDefaultSettingsForNewMeasurementSetting(UpdateDefaultSettings):
    pass


pre = []
post = [UpdateDefaultSettingsForNewMeasurementSetting]
