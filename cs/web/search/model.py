# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Model classes for the search app
"""

from __future__ import absolute_import
__revision__ = "$Id$"


from cs.web.components.base.main import BaseModel


class SearchModel(BaseModel):
    """ UI model. The purpose of his model class is to represent the search
        application itself, not a specific search.
    """
    def __init__(self, absorb=''):
        super(SearchModel, self).__init__()
        self.absorb = absorb
