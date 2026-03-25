#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8-*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class DataMigrations:

    # E045769: Set default values for new multilanguage field.

    def run(self):
        empty_db_string = "CHR(1)" if (sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE) else "''"
        sqlapi.SQLupdate(
            "cdb_folder SET name_de=name, name_en=name "
            f"WHERE (name_de IS NULL OR name_de={empty_db_string}) "
            f"AND (name_en IS NULL OR name_en={empty_db_string}) "
        )


pre = []
post = [DataMigrations]

if __name__ == "__main__":
    DataMigrations().run()
