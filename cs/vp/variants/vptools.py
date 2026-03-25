#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module VPTools

This is the documentation for the VPTools module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class WithChangeLog(object):
    @classmethod
    def CreateWithChangeLog(cls, **args):
        args.update(cls.MakeChangeControlAttributes())
        return cls.Create(**args)

    def CopyWithChangeLog(self, **args):
        args.update(self.MakeChangeControlAttributes())
        return self.Copy(**args)
