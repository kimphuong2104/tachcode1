#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import dberrors
from cdb import sqlapi
from cdb import util
from cdb.comparch import protocol


class Init(object):

    def run(self):
        # Initialisierung teile_stamm.configurable
        sqlapi.SQLupdate(
            "cdbvp_bom_predicate SET cdb_classname = 'cdbvp_bom_predicate_term' "
            "WHERE cdb_classname='cdbvp_bom_predicate' "
            "OR cdb_classname IS null OR cdb_classname=''")


class DropObsoleteVariantAttribute(object):
    """
    Drops the attribute cdbvp_variant.cdbvp_variant_info_txt.
    This attribute is starting from 15.3.1.0 a multilanguage attribute
    and must not exist in the database.
    """

    def run(self):
        try:
            sqlapi.SQL("""
                ALTER TABLE cdbvp_variant DROP COLUMN cdbvp_variant_info_txt
            """)
        except dberrors.DBError:
            # column probably already dropped
            protocol.logMessage(
                "Cannot drop column cdbvp_variant_info_txt from table cdbvp_variant. "
                "Probably it has been already dropped"
            )

pre = [DropObsoleteVariantAttribute]
post = [Init]


if __name__ == "__main__":
    DropObsoleteVariantAttribute().run()
    Init().run()
