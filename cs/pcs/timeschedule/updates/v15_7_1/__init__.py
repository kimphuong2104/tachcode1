#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.comparch.updutils import install_objects


class InsertWebLibraryDependency:
    """This script reverts deleted patch of Library Dependency
    between projects-web and timeschedule-web"""

    def run(self):
        install_objects(
            module_id="cs.pcs.timeschedule",
            objects=[
                (
                    "csweb_library_dependencies",
                    {
                        "library_name": "cs-pcs-projects-web",
                        "library_name_dependency": "cs-pcs-timeschedule-web",
                    },
                )
            ],
        )


pre = []
post = [InsertWebLibraryDependency]
