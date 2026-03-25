#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb import util


class Init(object):

    def run(self):
        # initialisierung cdb_counter cdbvp_view_id: must NOT start with 0
        util.set_min_counter_value("cdbvp_view_id", 1)

        # Initialisierung teile_stamm.configurable
        sqlapi.SQLupdate("teile_stamm set configurable = 0 where configurable is null")

        # Initialisierung einzelteile.cdbvp_positionstyp
        # Hinweis: Keine korrekte Initialisierung für bereits vorhandene Stücklistenalternativen und Optionen.
        sqlapi.SQLupdate("einzelteile set cdbvp_positionstyp = 'position' where cdbvp_positionstyp is null")

pre = []
post = [Init]
