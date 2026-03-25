# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def setup():
    from cdb import testcase
    from cdb import rte
    import cdbwrapc

    @testcase.without_error_logging
    def run_level_setup():
        rte.ensure_run_level(rte.USER_IMPERSONATED,
                             prog="nosetests",
                             user="cs_threed_service")
        # Necessary for nosetest - powerscript did it on its own
        cdbwrapc.init_corbaorb()

    run_level_setup()
