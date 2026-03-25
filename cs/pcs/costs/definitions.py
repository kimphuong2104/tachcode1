#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.objects import Forward, Object, Reference_1

fCurrency = Forward("cs.currency.Currency")
fCostCenter = Forward(__name__ + ".CostCenter")
fCostSignificance = Forward(__name__ + ".CostSignificance")


class CostCenter(Object):
    __maps_to__ = "cdbpcs_cost_center"
    __classname__ = "cdbpcs_cost_center"

    Currency = Reference_1(fCurrency, fCostCenter.currency_object_id)


class CostSignificance(Object):
    __maps_to__ = "cdbpcs_cost_significance"
    __classname__ = "cdbpcs_cost_significance"


class CostType(Object):
    __maps_to__ = "cdbpcs_cost_type"
    __classname__ = "cdbpcs_cost_type"

    def isGatheredAsEffort(self):
        return self.gathered_as_effort == 1
