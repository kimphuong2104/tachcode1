# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class Init(object):

    def run(self):
        # initialize the new attribute occurence_id
        sqlapi.SQLupdate("einzelteile set occurence_id = '' where occurence_id is null")

pre = []
post = [Init]

if __name__ == '__main__':
    Init().run()
