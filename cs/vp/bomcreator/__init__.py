#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
import logging

from cdb.objects import ByID

from cs.vp.bomcreator.bom import msg, UserHintList, GeneratedBOM, \
    ReplaceDatetimeDecoder, clear_message_cache
from cs.vp.bomcreator.bomreader import create_bom, delete_unused_new_articles

__docformat__ = "restructuredtext en"


def log(txt):
    """internal logging shortcut"""
    logging.info(txt)


def log_error(txt):
    """internal logging shortcut"""
    logging.error(txt)


def get_object(**kwargs):
    """
    :param kwargs should contain cdb_object_id
    :return (Document or None, error message or None)
    """
    result = None
    cdb_object_id = kwargs.get('cdb_object_id')
    log("BOMCreator called for object %s" % cdb_object_id)
    if not cdb_object_id:
        log_error("BOMCreator: no cdb_object_id given")
    else:
        result = ByID(cdb_object_id)
        if result is None:
            log_error("BOMCreator: object not found")
        elif not result.CheckAccess("read"):
            log_error("BOMCreator: no 'read' right on object")
            result = None
    error = None
    if result is None:
        error = msg('WSM_BOM_object_not_found') % cdb_object_id
    return result, error
