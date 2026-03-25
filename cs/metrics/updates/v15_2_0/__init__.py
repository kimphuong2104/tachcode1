#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb.comparch import protocol
from cdb.platform.acs import RelshipAccessProfile
from cdb.platform.mom.relships import Relship
from cdb.sqlapi import NULL
from cs.metrics.qualitycharacteristics import ClassAssociation


class MigrateUpdateClock(object):
    """ Fix for E035633:
        Set empty values to NULL
    """

    def run(self):
        condition = (ClassAssociation.update_clock == '')
        class_assos = ClassAssociation.Query(condition)
        class_assos.Update(update_clock=NULL)


class UpdateRelshipAccessProfiles(object):
    def run(self):
        self.update_rs_acc_prof()

    def update_rs_acc_prof(self):
        # cs.metrics
        self._update_rs_acc_prof("cdbqc: Delete Kennzahlen", "cdbqc: Delete KPI")
        self._update_rs_acc_prof("cdbqc: In Arbeit Kennzahlendefinition", "cdbqc:New KPIs")

    def _isEquivalent(self, old, new):

        def get_mapping(rs_acc_prof):
            mapping = [dict(x) for x in rs_acc_prof.AccessMapping]
            for x in mapping:
                del x["rs_acc_prof"]
            mapping.sort()
            return mapping

        return (old.mandatory == new.mandatory and
                get_mapping(old) == get_mapping(new))

    def _update_relships(self, old, new):
        Relship.KeywordQuery(rs_acc_prof=old).Update(rs_acc_prof=new)

    def _update_rs_acc_prof(self, old_name, new_name):
        old = RelshipAccessProfile.ByKeys(old_name)
        new = RelshipAccessProfile.ByKeys(new_name)

        if old and new:
            if self._isEquivalent(old, new):
                self._update_relships(old_name, new_name)
                old.Delete()
            else:
                protocol.logWarning(
                    "cdb_rs_acc_prof '%s' is not equivalent to '%s'. "
                    "Please check its usages manually."
                    % (old_name, new_name))


pre = [MigrateUpdateClock]
post = [UpdateRelshipAccessProfiles]


if __name__ == "__main__":
    MigrateUpdateClock().run()
