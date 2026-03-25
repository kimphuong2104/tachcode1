#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module exceptions

This is the documentation for the exceptions module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports


class TaskCancelledException(Exception):
    """ Exception raised by tasks and task groups, to communicate to their
        parents that they have been cancelled before starting.
    """


class TaskClosedException(Exception):
    """ Exception raised by tasks and task groups, to communicate to their
        parents that they have been closed before starting.
    """
