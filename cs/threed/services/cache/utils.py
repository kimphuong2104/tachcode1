# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module utils

This is the documentation for the utils module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import hashlib

from cdb import i18n
from cdb import util
from cdb.platform import gui
from cdb.objects import core
from cdb.objects import fields
from cdb.objects import cdb_file


class _BomItemAttributeAccessor(object):
    def __init__(self, bom_item, item):
        self.bom_item = bom_item
        self.item = item

    def __getitem__(self, name):
        fd = self.bom_item.GetFieldByName(name)
        if isinstance(fd, fields.JoinedAttributeDescriptor) and \
                fd.source_adef.getClassDef().getPrimaryTable() == 'teile_stamm':
            v = self.item.__getitem__(fd.source_adef.getName())
        else:
            v = self.bom_item.__getitem__(name)
        if v is None:
            return ""
        else:
            if isinstance(v, str):
                return str(v)
            return v


def hash(message):
    h = hashlib.sha1()
    h.update(message)
    return h.hexdigest()


def get_message(name, lang=None):
    result = None
    if lang is None:
        lang = i18n.default()

    msg = gui.Message.ByKeys(name)
    if msg:
        result = core.parse_raw(msg.Text[lang])
    return result


def checkin_conversion_result(model, file_path, cdbf_type):
    additional_args = {
        "cdbf_hidden": 1,
        "cdbf_type": cdbf_type,
        "cdbf_derived_from": model.getPrimaryFile().cdb_object_id
    }

    cdb_file.CDB_File.NewFromFile(
        model.cdb_object_id,
        file_path,
        primary=False,
        additional_args=additional_args
    )
