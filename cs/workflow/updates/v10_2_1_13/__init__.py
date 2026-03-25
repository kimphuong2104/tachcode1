#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb.platform.mom.entities import Class

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class CompileWFQueue(object):
    """ Compiles class mq_wfqueue as predefined field length has changed
    """
    def run(self):
        Class.ByKeys("mq_wfqueue").compile(force=True)


pre = []
post = [CompileWFQueue]

# Guard importing as main module
if __name__ == "__main__":
    CompileWFQueue().run()
