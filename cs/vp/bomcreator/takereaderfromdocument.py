#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
from cdb.objects import ByID
from cdb.tools import getObjectByName

from cs.documents import Document

from cs.vp.bomcreator.bomreader import BOMReader
from cs.vp.bomcreator.bomconfig import BOMMethod


class TakeReaderFromDocument(BOMReader):
    """
    A BOMReader that looks into the document to find out
    the actual reader method.

    If a document does not have a value for attribute "bom_method",
    this reader is not applicable, i.e. the implementation will fall
    back on the configuration with the next-lower priority.
    """
    @staticmethod
    def is_applicable_to(object_id):
        actual_reader = TakeReaderFromDocument.get_actual_reader(object_id)
        return actual_reader is not None

    @staticmethod
    def get_actual_reader(object_id):
        obj = ByID(object_id)
        if obj is None or not isinstance(obj, Document):
            return None
        bm = obj.bom_method
        if bm is None or len(bm) == 0:
            return None
        try:
            m = BOMMethod.ByKeys(bm)
            if m is None:  # doc-specific bom method not found
                return None
            actual_reader_class = getObjectByName(m.class_name)
            return actual_reader_class
        except ImportError:
            return None

    def __init__(self, bom_context, factory, custom_state):
        self.log("started on document %s, for part %s-%s" %
                 (bom_context.object_id,
                  bom_context.teilenummer,
                  bom_context.t_index))
        self.boms = []
        self.referenced_docs = []
        object_id = bom_context.object_id
        reader_type = TakeReaderFromDocument.get_actual_reader(object_id)
        # should always succeed, because tested by is_applicable_to:
        if reader_type is not None:
            reader = reader_type(bom_context, factory, custom_state)
            self.boms = reader.boms
            if hasattr(reader, 'referenced_docs'):
                self.referenced_docs = reader.referenced_docs
