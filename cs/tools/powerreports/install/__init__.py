# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module install

This is the documentation for the install module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class UpdateDecompositions(object):
    def run(self):
        from cdb.platform.gui import Decomposition

        d = Decomposition.ByKeys("CDB_LIC_FEATURE_ASSIGN")
        d.generate_decomposition()


__all__ = ["post", "pre"]

pre = []
post = [UpdateDecompositions]
