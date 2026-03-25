#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import os
import logging

from cdb import cdbuuid

from cs.documents import Document

from cs.cad_wsm_synchronizer.synchronize_links import synchronizeLinks
from cs.cad_wsm_synchronizer.create_appinfo import (
    createAppinfoFileForDoc,
    getAppinfoWriter,
)


def needsAppinfo(doc):
    """
    Return false if there exists an appinfo file which is up to date.

    Check if appinfo files were already written by the classic integration

    :Parameters:
        doc : cs.documents.Document
    :return:
        False if there exists an appinfo file which is up to date

    :raises: ValueError if there is no primary file or there do exist multiple
        primary files
    """
    logging.info("start needsAppinfo on doc (%s-%s)", doc.z_nummer, doc.z_index)

    appinfoNeeded = True
    primFiles = doc.Files.KeywordQuery(cdbf_primary=1)
    if len(primFiles) == 1:
        primFile = primFiles[0]
    elif len(primFiles) == 0:
        raise ValueError(
            'synchronizeDocuments: no primary file found for document "%s-%s")'
            % (doc.z_nummer, doc.z_index)
        )
    else:  # more than one primary file
        raise ValueError(
            "synchronizeDocuments: more than one primary file found for "
            'document "%s-%s")' % (doc.z_nummer, doc.z_index)
        )

    logging.info("primary file identified: %s", primFile.cdbf_name)

    # get the associated appinfo file
    wspItemId = primFile.cdb_wspitem_id

    rs = doc.Files.KeywordQuery(
        cdb_belongsto=wspItemId, cdbf_type="Appinfo", cdb_classname="cdb_file"
    )

    logging.info("found %d appinfo files", len(rs))

    if len(rs):
        appinfoRec = rs[0]
        logging.info("cdbf_fdate of content file: %s", primFile.cdbf_fdate)
        logging.info("cdbf_fdate of appinfo file: %s", appinfoRec.cdbf_fdate)

        if appinfoRec.cdbf_fdate >= primFile.cdbf_fdate:
            appinfoNeeded = False

    logging.info(
        "end needsAppinfo on doc (%s-%s): %s", doc.z_nummer, doc.z_index, appinfoNeeded
    )

    return appinfoNeeded


def synchronizeDocuments(pairs):
    """
    Raises an exception if any of the documents cannot be found.

    @param pairs: list of pairs of z_nummer, z_index;
                  for example [("D04711", "a"), ("D01138", "")]
    """
    for z_nummer, z_index in pairs:
        doc = Document.ByKeys(z_nummer, z_index)
        if doc is None:
            raise ValueError(
                'synchronizeDocuments: unknown document "%s-%s")' % (z_nummer, z_index)
            )
        synchronizeLinks(doc)

        if needsAppinfo(doc):
            createAppinfoFileForDoc(doc)
        handleSecondaryFiles(doc)
        doc.wsm_is_cad = 1


def handleSecondaryFiles(doc):
    # set belongs_to of previews
    for primary in doc.Files:
        if not primary.cdbf_derived_from and not primary.cdb_belongsto:
            if getAppinfoWriter(primary.cdbf_type):
                if not primary.cdb_wspitem_id:
                    primary.Update(cdb_wspitem_id=cdbuuid.create_uuid())

                primaryWithoutExt, _ = os.path.splitext(primary.cdbf_name)
                for secondary in doc.Files:
                    if secondary != primary:
                        secondaryWithoutExt, ext = os.path.splitext(secondary.cdbf_name)
                        if secondaryWithoutExt == primaryWithoutExt:
                            # be careful not to change primary files, e.g. .cgr

                            # FIXME: find a proper way to determine what is a
                            # preview file
                            if ext.upper in ["JPG", "PNG", "STL"]:  # FIXME
                                secondary.Update(cdb_belongsto=primary.cdb_wspitem_id)
