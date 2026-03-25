#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import inspect
import os
import sys
import traceback
import logging

import six

from cdb import cdbuuid
from cdb.objects.cdb_file import CDB_File

from cdb import cad
from cs.wsm.cadknowledge import Appl2OccurrenceReltypes


appInfoWriters = None


class AppinfoCreationException(Exception):
    pass


def createAppinfoFileForDoc(doc):
    logging.info('createAppinfoFile for document "%s-%s"', doc.z_nummer, doc.z_index)
    for rec in doc.Files:
        if not rec.cdbf_derived_from and not rec.cdb_belongsto:
            createAppinfoFile(doc, rec)


def createAppinfoFile(doc, rec):
    appInfoWriter = getAppinfoWriter(rec.cdbf_type)
    if appInfoWriter:
        erzeug_system = rec.cdbf_type.split(":")[0]
        occurrenceTypes = Appl2OccurrenceReltypes.get(erzeug_system, None)
        appInfoWriter.setRelevantOccurrenceTypes(occurrenceTypes)
        appinfoFName = appInfoWriter.makeAppInfoName(rec.cdbf_name)

        # check if cdb_wspitem_id is set
        if not rec.cdb_wspitem_id:
            rec.Update(cdb_wspitem_id=cdbuuid.create_uuid())

        logging.info('writing appinfo file "%s"', appinfoFName)
        config = getAppInfoConfig(rec.cdbf_type)
        appinfoFile = appInfoWriter.writeFile(doc, appinfoFName, config)
        if not appinfoFile:
            appinfoCreationFailed(doc, appinfoFName)
        else:
            existingAppinfo = None
            for rec2 in doc.Files:
                if rec2 != rec and rec2.cdbf_name == appinfoFName:
                    existingAppinfo = rec2
                    break

            if existingAppinfo:
                changeExistingAppinfo(rec, existingAppinfo, appinfoFile)
            else:
                uploadNewAppinfo(doc, rec, appinfoFile)


def getAppInfoConfig(cadSystem):
    res = {}
    val = cad.getCADConfValue(u"CAD WSM AppInfo Config", cadSystem)
    if val:
        pairs = val.split(";")
        for pair in pairs:
            parts = pair.split(":")
            if len(parts) != 2:
                log_error("invalid syntax for cad conf value 'CAD WSM AppInfo Config'")
                log_error("CAD System: %s" % cadSystem)
                log_error("value: %s" % val)
                log_error("error part: %s" % pair)
            else:
                pdmAttr = parts[0]
                cadAttr = parts[1]
                if pdmAttr in res:
                    log_error(
                        "cad conf value 'CAD WSM AppInfo Config' has more"
                        " than one entry for PDM attribute %s; the last one"
                        " will be used" % pdmAttr
                    )
                res[pdmAttr] = cadAttr
    return res


def getAppinfoWriter(filetype):
    global appInfoWriters
    if appInfoWriters is None:
        appInfoWriters = collectAppInfoWriters()

    res = appInfoWriters.get(filetype)
    return res


def appinfoCreationFailed(doc, appinfoFName):
    log_error('cad_wsm_synchronizer: creating appinfo file "%s" failed.' % appinfoFName)
    txt = "Error occurred creating .appinfo file '%s' " "for document '%s-%s' " % (
        appinfoFName,
        doc.z_nummer,
        doc.z_index,
    )
    raise AppinfoCreationException(txt)


def changeExistingAppinfo(rec, existingFile, filename):
    logging.info("check in to existing file record")
    existingFile.checkin_file(filename)
    logging.info("Appinfo file checked-in")
    os.remove(filename)
    if not existingFile.cdb_belongsto:
        existingFile.Update(cdb_belongsto=rec.cdb_wspitem_id)


def uploadNewAppinfo(doc, rec, appinfoFile):
    logging.info("upload to new file record")
    # upload new file
    additional_args = {
        "cdb_belongsto": rec.cdb_wspitem_id,
        "cdb_folder": "",
        "cdb_wspitem_id": cdbuuid.create_uuid(),
    }
    if hasattr(CDB_File, "cdbf_hidden"):
        additional_args["cdbf_hidden"] = 1

    # upload file without changing the document meta data
    cm2date = doc.cdb_m2date
    m2persno = doc.cdb_m2persno
    newCdbFile = CDB_File.NewFromFile(
        doc.cdb_object_id, appinfoFile, 0, additional_args
    )

    doc.Update(cdb_m2persno=m2persno, cdb_m2date=cm2date)
    os.remove(appinfoFile)

    if newCdbFile:
        logging.info("Appinfo file saved to the server.")
    else:
        appinfoUploadFailed(doc, appinfoFile)


def appinfoUploadFailed(doc, appinfoFile):
    log_error('Saving appinfo "%s" to server failed.' % appinfoFile)
    txt = "Error occurred uploading .appinfo file '%s' " "for document '%s-%s' " % (
        appinfoFile,
        doc.z_nummer,
        doc.z_index,
    )
    raise AppinfoCreationException(txt)


def log(msg):
    logging.info(msg)


def log_error(msg):
    logging.error("cad_wsm_synchronizer: %s", msg)


def collectAppInfoWriters():
    """
    Collect appinfowriter plugins.

    All modules in the subdirectory 'appinfowriters' are searched
    for classes subclassing 'AppInfoWriterBase'.

    :return:
        clientName2appInfoWriter : dict {String: object}
            dictionary mapping cdb client names to the appropriate
            appinfowriter instance, e.g.
            {"CatiaV5:CATPart" : CatiaV5PrtAppInfoWriter instance}
    """
    clientName2appInfoWriter = dict()

    pluginDir = os.path.join(os.path.dirname(__file__), "appinfowriters")
    sysPathOrig = sys.path[:]
    sys.path.append(pluginDir)
    try:
        from cs.cad_wsm_synchronizer.appinfowriters.appinfowriter import (
            AppInfoWriterBase,
        )
    except ImportError as e:
        log_error("Unable to import module: '%s'" % six.text_type(e))
    else:
        allEntries = os.listdir(pluginDir)
        prefixes = set()
        for f in allEntries:
            if os.path.isfile(os.path.join(pluginDir, f)):
                prefix, ext = os.path.splitext(f)
                if ext in (".py", ".pyc"):
                    if prefix != "appinfowriter":
                        prefixes.add(prefix)

        for m in prefixes:
            try:
                x = __import__(m)
                allNames = dir(x)
                for n in allNames:
                    isAppInfoWriterClass = False
                    try:
                        cls = getattr(x, n)
                        if inspect.isclass(cls):
                            if cls.__name__ != "AppInfoWriterBase":
                                isAppInfoWriterClass = issubclass(
                                    cls, AppInfoWriterBase
                                )
                    except TypeError:
                        log_error(
                            "appinfowriter import failure:\n%s" % traceback.format_exc()
                        )

                    if isAppInfoWriterClass:
                        cls = getattr(x, n)
                        if cls.CAD_System is not None:
                            if cls.CDB_CLIENTNAME is not None:
                                clientName2appInfoWriter[cls.CDB_CLIENTNAME] = cls(log)

            except Exception:
                log_error("unable to import module: '%s'" % m)
                log_error("reason:\n%s" % traceback.format_exc())
    finally:
        sys.path = sysPathOrig[:]

    return clientName2appInfoWriter
