# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi


class UpdatePartNames(object):
    """ Copy the content of worter.wort into the new attribute worter.de,
    """

    def run(self):
        sqlapi.SQLupdate("woerter SET de=wort WHERE de IS NULL")


pre = []
post = [UpdatePartNames]
