#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb.platform import gui


class UpdateURLAttribute(object):
    """ Update the url attribute of mask configuration for SML-groups:
        the opContextID parameter is not added anymore to the url,
        so it should be added explicitly in the mask configuration
    """

    def run(self):
        attrs = gui.MaskAttribute\
            .KeywordQuery(url='"powerscript/cs.vp.classification.oplan/maskimages"')
        attrs.Update(url='"powerscript/cs.vp.classification.oplan/maskimages?opContextID="+opContextID')


pre = []
post = [UpdateURLAttribute]


# Guard importing as main module
if __name__ == "__main__":
    UpdateURLAttribute().run()
