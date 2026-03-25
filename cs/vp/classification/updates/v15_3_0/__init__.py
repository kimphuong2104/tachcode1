# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi

ATTRIBUTES = [("cdbsml_doc_purpose", "purpose", "text_de"),
              ("cdbsml_cg_types", "cgroup_type", "name_de")]


class MigrateI18nAttributes(object):
    """ Copy the content of an old not yet internationalised attribute
        into the new german attribute
    """

    def __init__(self):
        self.attributes = ATTRIBUTES

    def run(self):
        for relation, old_attribute, new_attribute in self.attributes:
            stmt = "{relation} SET {new_attribute}={old_attribute} " \
                   "WHERE {new_attribute} IS NULL"\
                .format(relation=relation,
                        old_attribute=old_attribute,
                        new_attribute=new_attribute)
            sqlapi.SQLupdate(stmt)


pre = []
post = [MigrateI18nAttributes]


if __name__ == '__main__':
    for ut in post:
        ut().run()
