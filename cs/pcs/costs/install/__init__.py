# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module install

Installs the Project Cost Management Role if it is not already installed.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class CreateProjectRole(object):
    def run(self):
        from cdb import sqlapi

        cols = [
            "name",
            "description",
            "name_ml_de",
            "name_ml_en",
            "obsolete",
            "description_ml_en",
        ]
        german_label = "'Projektkostenmanagement'"
        english_label = "'Project Cost Management'"
        vals = [
            english_label,
            german_label,
            german_label,
            english_label,
            "0",
            english_label,
        ]
        try:
            sqlapi.SQLinsert(
                f"INTO cdbpcs_role_def ({', '.join(cols)}) VALUES ({', '.join(vals)})"
            )
        except:
            pass


__all__ = ["pre"]

pre = []
post = [CreateProjectRole]
