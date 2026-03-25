# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module oulets

A module for Outlet implementations
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.web.components.outlet_config import OutletPositionCallbackBase


# Exported objects
__all__ = []


class LicenseOutletPositionRelationshipsCallback(OutletPositionCallbackBase):

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        # Do not display the AuthorizedRoles relationship tab for licenses
        # that are not of kind ``float``
        if not obj or \
           obj.lstat == "float" or \
           pos_config["properties"].get("relshipName") != "AuthorizedRoles":
            return [pos_config]
        return []


# Guard importing as main module
if __name__ == "__main__":
    pass
