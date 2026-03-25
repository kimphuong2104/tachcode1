#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
#  ----------------------------------------------------------------------------
#  File:    solidworks/__init__.py   --                                      --
#  Author:  Jens Rosebrock
#  mail:    jens.rosebrock@contact.de
#  www.contact.de
#  Copyright (C) 2006 Contact Software
#  All rights reserved
#  ----------------------------------------------------------------------------
#  Creation:    21.11.2005  8:00
#  Revision:    $Id$
#  Change Log:
#      2006-11-01 Anpassung an die neue Struktur
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#  ----------------------------------------------------------------------------
#
# pylint: disable-msg=R0912,R0914,R0915,W0212
"""Solidworks-Plugin zum ACS
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import io
import os
import six
import sys

from cdb import rte, mq
from cdb.acs import acslib, cadacsutils
from cdb.objects.pdd.Files import Sandbox
from cdb.fls import allocate_license
from cdb.fls import LicenseError
from cdb.objects.cdb_file import CDB_File

from cs.cadbase.acsplugins.misc import get_target_list, get_appinfo_mode, \
    get_file_type, execute_cad_job, check_duplicate_files, transfer_converted_files, \
    check_converted_files, get_param_value, get_bool, get_model_and_src_file

if sys.platform == "win32":
    from .acscadjob import create_cad_job
    from cs.cadbase.acsplugins.misc import CadJobException
    from cs.solidworks.jobexec.swjobexec import SolidWorksJobExec

# ============================================================
# globals ...
# ============================================================

log = acslib.log

cPlgInRevision = "$Revision$"[11:-2]
cPlgInLocation = os.path.dirname(__file__)
cPlgInName = os.path.basename(cPlgInLocation)

cSetup = {}
Conversions = {}
_DEBUG = 0


# ============================================================
# Funktionen zur Initialisierung und zum Test ...
# ============================================================
def initPlgIn():  # init setup
    """Initialisierung des Plugins
    """
    global cSetup, Conversions

    log("initing plugin %s\n" % cPlgInName)
    SOLIDWORKS_ENV = acslib.Container()
    nativeTargets = ["slddrw", "SLDDRW"]
    cSetup = acslib.getPluginsSetup(cPlgInName,
                                    {"SOLIDWORKS_ENV": SOLIDWORKS_ENV,
                                     "nativeTargets": nativeTargets})
    Conversions = cSetup["Conversions"]

    return True


def testPlgIn():
    log("testing configuration of plugin %s\n" % cPlgInName)

    if sys.platform != "win32":
        raise Exception("testing configuration of plugin %s "
                        "(CAD Job Interface) only on win32" % cPlgInName)

    err, _, _, _, _, _ = SolidWorksJobExec().get_configuration()

    if err != "":
        raise Exception(err)

    return True


def returnFile(job, model, srcFile, filename, suffix):
    """Rückgabe einer Datei an den Server

    <job>          : Job Objekt (acs.ACSJob)
    <model>        : Modelinstanz, ein Objekt vom Typ
                   : cdb.objects.pdd.Documents.Document
    <srcFile>      : cdb.objects.cdb_file.CDB_File-Instanz oder
                   : None, Originaldatei
    <filename>     : vollständige Pfadangabe zum Erzeugniss der
                   : Konvertierung
    <suffix>       : Mit diesem Suffix wird die Datei an den Server übergeben.

    Mit dieser Funktion wird eine Datei <filename> an den Server übergeben. Vor
    der Übergabe wird die Datei umbenannt und erhält einen CDB konformen Namen
    mit dem übergebenen <suffix>."""

    if not os.path.isfile(filename):
        raise Exception("missing file: '%s'" % filename)
    result_type = cSetup["ResultTypes"][job.target]

    if srcFile is not None and srcFile.cdbf_name == os.path.basename(filename):
        job.store_file(srcFile, filename, result_type, replace_original=True)

        updateVault_appInfo(job, srcFile, os.path.dirname(filename))
    else:
        if not suffix.startswith('.'):
            suffix = '.' + suffix
        if filename.endswith(suffix):
            cdbName = filename
        else:
            cdbName = os.path.splitext(filename)[0] + suffix

            job.log("rename file '%s' --> '%s'" % (filename, cdbName))
            # removing the file if it already exists
            if os.path.isfile(cdbName):
                os.remove(cdbName)
            os.rename(filename, cdbName)

        attach_to = srcFile if srcFile is not None else model

        # write native file?
        doSaveNativeBack = cSetup.get("SAVE_NATIVE_BACK", False)
        if doSaveNativeBack and model.erzeug_system == "SolidWorks":
            job.log("SAVE_NATIVE_BACK == True -> write native file\n")
            job.store_file(srcFile, srcFile.cdbf_name,
                           "SolidWorks", replace_original=True)
            job.store_file(attach_to, cdbName, result_type)

            # update .appinfo file
            updateVault_appInfo(job, srcFile, os.path.dirname(filename))
        else:
            job.store_file(attach_to, cdbName, result_type)


def updateVault_appInfo(job, srcFile, convPath):
    appInfName = appInfName = os.path.basename(srcFile.cdbf_name) + ".appinfo"
    objID = srcFile.cdbf_object_id
    appInfo_list = CDB_File.KeywordQuery(cdbf_object_id=objID,
                                         cdbf_name=appInfName)
    if appInfo_list:
        appInfoFile = appInfo_list[0]
        appInfoFullPath = os.path.join(convPath, appInfName)
        try:
            if os.path.isfile(appInfoFullPath):
                with io.open(appInfoFullPath, "a") as appinfoF:
                    appinfoF.write(u"\n")
                job.store_file(appInfoFile, appInfoFullPath,
                               ".appinfo", replace_original=True)
        except Exception as e:
            job.log("%s\n" % e)


def HandleJob(job):
    """Handle solidworks-Plugin Konvertierung

    Dieses  Handle  wird   vom Konvertierungsserver  für  die Bearbeitung eines
    Konvertierungsauftrags aufgerufen. Der Funktion wird  das 'Job' Objekt als
    einziger Parameter übergeben.

    """
    global log

    retVal = 0
    job_param = None

    # alle vom Handle aufgerufenen Funktionen in diesem Modul sollen das Log
    # vom Job verwenden ...
    log = job.log

    # Lizenzen abfragen
    try:
        log("Check license ....\n")
        allocate_license("SOLIDWORKS_003")
        log("License checked!!!!\n")
    except LicenseError as ex:
        log("Error occurred getting license for SOLIDWORKS DCS: %s\n" % ex.message)
        return 73

    # check plugin pre condition
    testPlgIn()

    # init env
    env = rte.environ.copy()

    # env: set all SOLIDWORKS_ENV container values
    for (k, v) in cSetup["SOLIDWORKS_ENV"].items():
        env[k] = v

    try:
        # Modeldaten auschecken ...
        model, srcFile = get_model_and_src_file(job)
    except CadJobException as e:
        job.log("%s\n" % e)
        return 1

    try:
        job_param = job.getParameters()
    except mq.NoPayloadDirectory:
        job.log("no acs-job param dict available\n")

    detached_drawing = get_bool(get_param_value("detached_drawing", None, job_param,
                                                six.text_type, "CADDOK_ACS_DETACHED_DRAWING",
                                                env, "False"))

    # get list of targets
    targets = get_target_list(job, cSetup, job_param)

    with Sandbox(job.getWorkspace()) as sb:
        accept_duplicates = get_param_value(None, None, None, None, "ACCEPT_DUPLICATE_FILENAMES",
                                            cSetup, False)

        # Should drawings be converted as detached drawings (without references)?
        if job.source in ["SolidWorks", "SolidWorks:DRW"] and detached_drawing:
            job.log("Checkout detached drawing without references\n")
            # checkout only srcFile
            sb.checkout_to_path(srcFile, os.path.join(sb.location, srcFile.cdbf_name))

            # ... and the associated appinfo file
            wspItemId = srcFile.cdb_wspitem_id
            rs = model.Files.KeywordQuery(cdb_belongsto=wspItemId,
                                          cdbf_type='Appinfo',
                                          cdb_classname='cdb_file')
            if len(rs) == 1:
                sb.checkout_to_path(rs[0], os.path.join(sb.location, ".wsm", ".info",
                                                        rs[0].cdbf_name))
            else:
                job.log("Drawing has no appinfo\n")
        else:
            # This is a normal conversion.
            # All referenced models will be checked out.
            cadacsutils.checkoutStructure(sb, model, ignoreDuplicates=accept_duplicates,
                                          use_subdir_for_appinfo=True)
        srcFPName = sb.pathname(srcFile)

        try:
            file_type = get_file_type(job, model)

            cad_job = None
            appinfo_mode, appinfo_fname, appinfo_subdir = get_appinfo_mode(srcFPName)
            for target in targets:
                cad_job = \
                    create_cad_job(model,
                                   srcFPName,
                                   sb.location,
                                   appinfo_mode == 2,
                                   target,
                                   cSetup,
                                   env,
                                   file_type,
                                   job_param,
                                   log,
                                   cad_job)
            check_duplicate_files(targets)
            job_result_info = execute_cad_job(cad_job)
            check_converted_files(targets, srcFPName, appinfo_fname, appinfo_subdir,
                                  sb.location, cSetup, job_result_info)
            transfer_converted_files(targets, job, model, srcFile, cSetup)
        except CadJobException as e:
            job.log("Error occured executing CADJobs:")
            job.log("%s \n" % e)
            retVal = 3

    # return to server ...
    return retVal
