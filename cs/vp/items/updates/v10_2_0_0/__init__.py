# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class MBOMUpdate(object):

    def run(self):
        # Initialisierung is_mbom Flag
        sqlapi.SQLupdate("teile_stamm set is_mbom = 0 where is_mbom is null")

pre = []
post = [MBOMUpdate]
