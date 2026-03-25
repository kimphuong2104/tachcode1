#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb import cad
from cdb import util
from cdb.comparch import protocol


class RemoveZVSTeilestatusAendern(object):

    def run(self):
        # Check the actual value and write a warning if the feature is active
        prop_is_active = cad.isTrue(util.get_prop("psds"))
        rset = sqlapi.RecordSet2("cad_konf_werte", condition="name='ZVS Teilestatus aendern'")
        prop_cads = []
        for rec in rset:
            if cad.isTrue(rec.wert):
                details_longtext = "The configuration was active for %s" % rec.cad_system
                protocol.logWarning("CAD-Configuration: 'ZVS Teilestatus aendern' has been removed with cdb.10",
                                    details_longtext)
            elif prop_is_active and rec.wert == "PROPERTY":
                prop_cads.append(rec.cad_system)
        if prop_cads:
            details_longtext = "The property was active for %s. " % ", ".join(prop_cads)
            protocol.logWarning("Property 'psds' has been removed with cdb.10", details_longtext)
        prop = 'psds'
        cad_konf = 'ZVS Teilestatus aendern'
        sqlapi.SQLdelete("FROM cad_konf_werte WHERE name = '%s'" % cad_konf)
        sqlapi.SQLdelete("FROM cad_konf_txt WHERE name = '%s'" % cad_konf)
        sqlapi.SQLdelete("FROM cdb_prop_desc WHERE attr = '%s'" % prop)
        sqlapi.SQLdelete("FROM cdb_prop WHERE attr = '%s'" % prop)

pre = []
post = [RemoveZVSTeilestatusAendern]
