# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module cs.licreport.errors

Exceptions
"""

__all__ = [
    'NoDataError'
]

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class NoDataError(Exception):
    """Raised when no protocol data was found"""
    def __init__(self, table, *args):
        self.table = table
        super(NoDataError, self).__init__(*args)


class InvalidTablesError(Exception):
    """Raised when the given tables are broken/missing."""
    pass


class DataFormatError(Exception):
    """License protocol data is malformed."""
    pass
