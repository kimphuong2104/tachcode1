#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
from cdb import cdbuuid
from cdb.classbody import classbody

from cdb.objects import Object
from cdb.objects import Reference_N

from cs.costing.calculations import Calculation


class Calculation2Doc(Object):
    """
    Calculations to document relationships
    """
    __maps_to__ = "cdbpco_calc2doc"
    __classname__ = "cdbpco_calc2doc"

    def copy_to(self, newcalc):
        """
        Copy the document assignment to a new calculation.
        """
        newdata = {"calc_object_id": newcalc.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        self.Copy(**newdata)


@classbody
class Calculation(object):

    DocumentAssignments = Reference_N(Calculation2Doc,
                                      Calculation2Doc.calc_object_id == Calculation.cdb_object_id)
