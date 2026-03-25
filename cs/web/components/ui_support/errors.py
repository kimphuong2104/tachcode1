# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This module implements the infrastructure for getting the
internal error log implemented in the backend.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import misc
from . import App


class LogBookModel(object):
    def get_messages(self):
        return misc.get_error_logs()


@App.path(path="error_log", model=LogBookModel)
def _log_book_path():
    return LogBookModel()


@App.json(model=LogBookModel, request_method='GET')
def _log_book_view(self, request):
    return {
        "messages": self.get_messages()
    }
