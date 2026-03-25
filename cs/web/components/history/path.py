#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath path declaration for Web UI history
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from webob.exc import HTTPBadRequest

from .main import HistoryApp
from .model import HistoryCollection
from . import get_history_size


@HistoryApp.path(model=HistoryCollection, path='')
def _get_history_collection(classname=None, amount=-1, as_table=None):
    if as_table is not None and not classname:
        return HTTPBadRequest(detail='as_table not allowed without classname')
    if amount == -1:
        amount = get_history_size()
    return HistoryCollection(classname, amount, as_table)
