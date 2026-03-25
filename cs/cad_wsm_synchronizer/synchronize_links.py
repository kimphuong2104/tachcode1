#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import logging

import six

from cdb import cdbuuid
from cs.documents import DocumentReference
from cdb.objects.cdb_file import cdb_link_item
from cs.wsm.cadknowledge import Appl2OccurrenceReltypes, getApplByClientName


def synchronizeLinks(doc):
    logging.info(
        'synchronizeFromDocRel for document "%s-%s")', doc.z_nummer, doc.z_index
    )
    appl = getApplByClientName(doc.erzeug_system)
    occurrenceReltypes = Appl2OccurrenceReltypes.get(appl)
    if occurrenceReltypes:
        link_items_by_dst = {}
        link_items = cdb_link_item.KeywordQuery(cdbf_object_id=doc.cdb_object_id)
        for link_item in link_items:
            link_items_by_dst[link_item.cdb_link] = link_item
        link_items_to_delete = link_items_by_dst.copy()

        doc_rels = DocumentReference.Query(
            condition="z_nummer = '%s' AND z_index = '%s' AND reltype <> 'WSM'"
            % (doc.z_nummer, doc.z_index)
        )
        for doc_rel in doc_rels:
            if doc_rel.reltype in occurrenceReltypes:
                logging.info(
                    "synchronizeLinks: Found CDB_DOC_REL entry of type %s"
                    " referencing document %s-%s (cdb_link='%s').",
                    doc_rel.reltype,
                    doc_rel.z_nummer2,
                    doc_rel.z_index2,
                    doc_rel.cdb_link,
                )
                referenced_doc = doc_rel.ReferencedDocument
                if referenced_doc:
                    dst = referenced_doc.cdb_object_id
                    if dst in link_items_by_dst:
                        logging.info("reusing existing cdb_link_item")
                        link_items_to_delete.pop(dst, None)
                    else:
                        logging.info("creating new cdb_link_item")
                        cdb_link_item.Create(
                            cdbf_object_id=doc.cdb_object_id,
                            cdb_wspitem_id=cdbuuid.create_uuid(),
                            cdb_folder="",
                            cdb_link=dst,
                            cdbf_blob_id="",
                            cdb_link_condition="",
                        )
                    # there is now a cdb_link_item representing the same
                    # information as the docrel entry
                    # ==> prevent DCS from using the docrel entry
                    doc_rel.owner_application = "WSM"
                else:
                    logging.error(
                        'synchronizeLinks: Document "%s-%s" does not exist, but is referenced '
                        'by document "%s-%s". No cdb_link_item created.',
                        doc_rel.z_nummer2,
                        doc_rel.z_index2,
                        doc.z_nummer,
                        doc.z_index,
                    )

        logging.info(
            "synchronizeLinks: %d link items to delete", len(link_items_to_delete)
        )
        for link_item in six.itervalues(link_items_to_delete):
            link_item.Delete()
