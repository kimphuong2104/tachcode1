# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Morepath path definitions for the search application
"""

__revision__ = "$Id: path.py 164371 2017-09-01 12:01:39Z mbr $"

from .main import InternalSearchApp
from .model import FullTextSearchModel, TermSearchModel, HighlightSearchModel


@InternalSearchApp.path(model=FullTextSearchModel, path="fulltext")
def _get_es_result(searchtext, extra_parameters):
    return FullTextSearchModel(searchtext, extra_parameters)


@InternalSearchApp.path(model=TermSearchModel, path="term")
def _get_es_term_result(searchtext):
    return TermSearchModel(searchtext)


@InternalSearchApp.path(model=HighlightSearchModel, path="highlight")
def _get_es_highlight_result(searchtext, object_id):
    return HighlightSearchModel(searchtext, object_id)
