#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module for SemanticLink management
"""

from __future__ import absolute_import
from cdb import CADDOK
from cdb import dotlib
from cdb.lru_cache import lru_cache

import glob
import logging
import os
from cs.tools.semanticlinks.linkgraph import renderer

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


LOG = logging.getLogger(__name__)


@lru_cache(clear_after_ue=False)
def get_graphviz_dot_path():
    possible_path = dotlib.graphviz_path()
    if possible_path:
        dot_paths = glob.glob(os.path.join(possible_path, 'dot.exe'))
    else:
        dot_paths = glob.glob(os.path.join(CADDOK.RUNTIME, 'dot'))
    if len(dot_paths) == 1 and os.path.isfile(dot_paths[0]):
        dot_path = os.path.abspath(dot_paths[0])
        LOG.info('using graphviz dot path: %s', dot_path)
        return dot_path
    else:
        LOG.error('failed to locate graphviz dot')
