#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2029 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
from cdb import constants
from cdb.objects import operations
from cdb.objects import Object
from cs.audittrail import WithAuditTrail
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Forward

fVolumeCurve = Forward(__name__ + ".VolumeCurve")
fVolumeCurveEntry = Forward(__name__ + ".VolumeCurveEntry")
fComponent = Forward("cs.costing.calculations.Component")
fCalculation = Forward("cs.costing.calculations.Calculation")
fDelivery = Forward("cs.costing.components.Delivery")


class VolumeCurve(Object, WithAuditTrail):
    __maps_to__ = "cdbpco_volume_curve"
    __classname__ = "cdbpco_volume_curve"

    Calculation = Reference_1(fCalculation,
                              fCalculation.cdb_object_id == fVolumeCurve.calc_object_id)
    Object = Reference_1(fComponent,
                         fComponent.cdb_object_id == fVolumeCurve.object_object_id)
    Entries = Reference_N(fVolumeCurveEntry,
                          fVolumeCurveEntry.volume_curve_object_id == fVolumeCurve.volume_curve_object_id)

    def referencedAuditTrailObjects(self):
        results = [self, self.Calculation]
        if not self.Object.parent_object_id:
            results.append(self.Object)
        return results

    def set_volume_curve_values(self, ctx=None):
        import numpy
        amounts = VolumeCurveEntry.KeywordQuery(volume_curve_object_id=self.volume_curve_object_id).amount
        self.Update(mean_amount=numpy.mean(amounts),
                    peak_amount=max(amounts),
                    minimal_amount=min(amounts))


class VolumeCurveEntry(Object, WithAuditTrail):
    __maps_to__ = "cdbpco_volume_curve_entries"
    __classname__ = "cdbpco_volume_curve_entries"

    VolumeCurves = Reference_N(fVolumeCurve,
                               fVolumeCurve.volume_curve_object_id == fVolumeCurveEntry.volume_curve_object_id)
    Delivery = Reference_1(fDelivery,
                           fDelivery.calc_object_id == fVolumeCurveEntry.calc_object_id,
                           fDelivery.sales_year == fVolumeCurveEntry.sales_year)
    event_map = {
        (('create', 'copy', 'modify', 'delete'), 'post'): 'set_volume_curve_values',
        (('create', 'copy', 'modify'), 'post'): 'create_modify_delivery'
    }

    def referencedAuditTrailObjects(self):
        results = [self]
        for vc in self.VolumeCurves:
            if not vc.Object.parent_object_id:
                results.append(vc.Object)
                results.append(vc.Calculation)
        return results

    def set_volume_curve_values(self, ctx):
        import numpy
        amounts = VolumeCurveEntry.KeywordQuery(volume_curve_object_id=self.volume_curve_object_id).amount
        self.VolumeCurves.Update(mean_amount=numpy.mean(amounts),
                                 peak_amount=max(amounts),
                                 minimal_amount=min(amounts))

    def create_modify_delivery(self, ctx):
        from cs.costing.components import Delivery
        from cs.costing.components import Component2Delivery
        if not self.Delivery:
            new_delivery = operations.operation(constants.kOperationNew,
                                                Delivery,
                                                calc_object_id=self.calc_object_id,
                                                sales_year=self.sales_year,
                                                **Delivery.MakeChangeControlAttributes())
            Component2Delivery.Create(calc_object_id=self.calc_object_id,
                                      comp_object_id=self.primary_component_object_id,
                                      amount=self.amount,
                                      delivery_object_id=new_delivery.cdb_object_id)
        else:
            ids = self.Delivery.ComponentAssignments.comp_object_id
            if self.primary_component_object_id in ids:
                Component2Delivery.KeywordQuery(calc_object_id=self.calc_object_id,
                                                comp_object_id=self.primary_component_object_id,
                                                delivery_object_id=self.Delivery.cdb_object_id) \
                                  .Update(amount=self.amount)
            else:
                Component2Delivery.Create(calc_object_id=self.calc_object_id,
                                          comp_object_id=self.primary_component_object_id,
                                          amount=self.amount,
                                          delivery_object_id=self.Delivery.cdb_object_id)
