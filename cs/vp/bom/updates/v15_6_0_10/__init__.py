# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import util

from cdb.platform import PropertyDescription
from cdb.platform import PropertyValue


class SetXbimProperty(object):
    def run(self):
        xbim = util.get_prop("xbim")
        if not xbim:
            # set xbim to "false" if it does not exist
            PropertyDescription.Create(
                attr="xbim",
                helptext="""Render images in the 3D preview of the xBOM Manager.

Values:
true: will render images
false: will immediately show the 3D preview""",
                cdb_module_id="cs.vp.bom"
            )
            PropertyValue.Create(
                attr="xbim",
                value="false",
                subject_type="Common Role",
                subject_id="public",
                cdb_module_id="cs.vp.bom"
            )


pre = []
post = [SetXbimProperty]

if __name__ == "__main__":
    SetXbimProperty().run()
