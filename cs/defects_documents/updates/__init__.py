#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"


def _get_upgrades():
    try:
        from cdb.comparch.pk_upgrade import PKUpgrade
        return [PKUpgrade("cs.defects",
                      "cdb_defect_type",
                      "cdb_defect_type",
                      ["cdb_object_id"], ["name"]),
            PKUpgrade("cs.defects",
                      "cdb_defect_priority",
                      "cdb_defect_priority",
                      ["cdb_object_id"], ["priority"]),
            PKUpgrade("cs.defects",
                      "cdb_defect_source",
                      "cdb_defect_source",
                      ["cdb_object_id"], ["name"]),
            PKUpgrade("cs.defects",
                      "cdb_defect_categ",
                      "cdb_defect_categ",
                      ["cdb_object_id"], ["name"])]
    except ImportError:
        # For platform service level compatibility <SL16 (CE15)
        # PKUpgrade is new with SL16.
        return []

upgrades = _get_upgrades()
