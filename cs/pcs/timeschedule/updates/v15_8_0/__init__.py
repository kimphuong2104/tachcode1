#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from cdb import sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class RemoveWebLibraryDependency:
    def run(self):
        table = "csweb_library_dependencies"
        library_name = "cs-pcs-projects-web"
        dependency = "cs-pcs-timeschedule-web"
        sqlapi.SQLdelete(
            f"FROM {table} WHERE library_name =  '{library_name}'"
            f"AND library_name_dependency = '{dependency}'"
        )


pre = []
post = [RemoveWebLibraryDependency]
