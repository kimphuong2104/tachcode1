# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class MigrateWrongAttributes(object):
    """ Copy the content of the missspelled attributes [lang]_bennenung
        in the correct attributes [lang]_benennung.

        The following languages are involved: cs, ja, ko, pl, pt, tr, zh.
    """

    def run(self):
        from cs.vp import items
        keys = [key.name for key in items.Item.GetTableKeys()]

        languages = ["cs", "ja", "ko", "pl", "pt", "tr", "zh"]
        for language in languages:
            if "%s_bennenung" % language in keys:
                stmt = "teile_stamm SET " \
                       "{0}_benennung = {0}_bennenung " \
                       "where {0}_benennung is NULL".format(language)
                sqlapi.SQLupdate(stmt)


pre = []
post = [MigrateWrongAttributes]


if __name__ == '__main__':
    MigrateWrongAttributes().run()
