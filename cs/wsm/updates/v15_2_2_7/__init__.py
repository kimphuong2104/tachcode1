#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import six

from cdb import sqlapi
from cdb.comparch import modules, content


class UpdateVariantConfigFileExtension(object):
    def run(self):
        # see E059553
        # we need to do this in code
        # because the module update policy of cad_konf_werte is "NEVER UPDATED"
        sqlapi.SQLupdate(
            "cad_konf_werte"
            " SET wert='.variantconfig' "
            " WHERE cdb_module_id='cs.wsm'"
            " AND name = 'ZVS Zeichnung Endung'"
            " AND cad_system='Variantconfig'"
        )


pre = []
post = [UpdateVariantConfigFileExtension]
