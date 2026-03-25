#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

from cs.workflow import briefcases

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class UpdateIOType(object):
    """ Update the iotype of briefcase links. This is necessary because
        the iotype "create" does not exist anymore.
    """
    def run(self):
        condition = "iotype != %s" % briefcases.IOType.info.value  # @UndefinedVariable
        brlinks = briefcases.BriefcaseLink.Query(condition)
        brlinks.Update(iotype=briefcases.IOType.edit.value)  # @UndefinedVariable


pre = []
post = [UpdateIOType]

# Guard importing as main module
if __name__ == "__main__":
    UpdateIOType().run()
