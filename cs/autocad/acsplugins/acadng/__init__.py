#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2003 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     acad/__init__.py
# Author:   Jürgen Worthmann
# Creation: 10.04.03

# pylint: disable-msg=C0103, C0301

from __future__ import absolute_import

import codecs
import io
import os
import six
import sys

from cdb import timeouts, cad, rte, mq
from cdb.acs import acslib, cadacsutils
from cdb.fls import allocate_license, LicenseError
from cdb.objects.pdd.Files import Sandbox
from cdb.objects.cdb_file import CDB_File
from cdb.plattools import killableprocess

from cs.autocad.jobexec.acadjobexec import AcadJobExec
from cs.cadbase.acsplugins.misc import CadJobException, get_target_list, get_appinfo_mode, \
    execute_cad_job, check_duplicate_files, transfer_converted_files, \
    check_converted_files, get_param_value

# ============================================================
# globales ...
# ============================================================

log = acslib.log

cPlgInRevision = "$Revision$"[11:-2]
cPlgInLocation = os.path.dirname(__file__)
cPlgInName = os.path.basename(cPlgInLocation)

cSetup = None  # hier ist der Namensraum der Konfiguration verfügbar

# hiermit wird dem Server mitgeteilt welche Dienste von
# diesem Plugin angeboten werden (wird weiter unten
# aus setup.py beladen)
Conversions = {}
acadPrimFormat = ["dwg"]
Format2Suffix = {}


def initPlgIn():
    global cSetup, Conversions, Format2Suffix

    log("initializing plugin %s\n" % cPlgInName)

    cSetup = acslib.getPluginsSetup(cPlgInName, {"nativeTargets": ["dwg", "DWG"]})
    Conversions = cSetup["Conversions"]
    Format2Suffix = cSetup["Format2Suffix"]

    return True


def testPlgIn():
    log("testing configuration of plugin %s\n" % cPlgInName)

    if sys.platform != "win32":
        err = "testing configuration of plugin %s (CAD Job Interface) only " \
              "on win32" % cPlgInName
    else:
        log("testing configuration of plugin %s "
            "(CAD Job Interface)\n" % cPlgInName)
        err, _, _, _, _, _ \
            = AcadJobExec().get_configuration()

    if err != "":
        raise Exception(err)

    return True


def convertCall(env):
    scriptFileName = u"acs_acad.scr"

    assert isinstance(scriptFileName, six.text_type)

    acad_options = []

    try:
        acad_options = cSetup["ACAD_EXE_OPTIONS"]
        acad_options.index("/p")
    except Exception:
        acad_options.extend(["/p", cSetup["PROFILE"]])

    with io.open(scriptFileName, "w", encoding="utf-8") as script_file:
        script_file.write(u"(setvar \"filedia\" 1)\n")
        script_file.write(u"cimdb_acs_convert\n")

        cmd = [("%s" % cSetup["ACAD_EXE"])] + acad_options + \
              ["/b", "%s" % os.path.join(os.getcwd(), scriptFileName)]

    timeout = cSetup["ACAD_TIMEOUT"]
    if not timeout or timeout <= 0:
        timeout = 600

    log("Command: %s\n" % killableprocess.list2cmdline(cmd))
    cmd = killableprocess.Popen(cmd, env=env)
    try:
        timeouts.run_with_timeout(
            lambda: timeouts.WaitResult(cmd.returncode, cmd.poll() is None),
            timeout)
    except timeouts.WaitTimeout:
        # hier ist etwas schief gegangen, Prozess abschiessen
        cmd.terminate()
        log("Job timeout reached. Acad was killed\n")
        return 1
    log(">> Command returned: %s\n" % cmd.returncode)
    return 0


def rename_converted_files(targets, work_dir, cSetup, job_params, handling_multisheet):
    output_file = os.path.join(work_dir, "output.txt")
    rename_files = {}

    sheet_handling_catalog = get_param_value(None, None, None, None,
                                             "SHEET_HANDLING_CATALOG", cSetup)

    # rename files that were created using CURRENT_LAYOUT
    if os.path.isfile(output_file) and not handling_multisheet:
        with io.open(output_file, "r", encoding="utf-8", newline="\n") as f:
            line = f.readline()
            while line:
                original_dst_filename = line.split('@')[1]
                renamed_dst_filename = line.split('@')[2].strip()
                rename_files[original_dst_filename] = renamed_dst_filename
                line = f.readline()

        for target in targets:
            if target["dstformat"].lower() == "resolvedwg":
                continue

            if "" == sheet_handling_catalog[target["dstformat"]]:
                for i, dst_file in enumerate(target["int_dst_files"]):
                    if os.path.isfile(rename_files[dst_file]):
                        os.unlink(rename_files[dst_file])
                    os.rename(dst_file, rename_files[dst_file])
                    target["int_dst_files"][i] = rename_files[dst_file]


def merge_converted_pdf(targets, srcFile):
    for target in targets:
        if "pdfm" == target["dstformat"].lower():
            from PyPDF2 import PdfFileMerger
            pdf_merger = PdfFileMerger(strict=False)
            dst_extension = os.path.splitext(target["int_dst_files"][0])[1]
            work_dir = os.path.dirname(target["int_dst_files"][0])

            merge_filename = os.path.basename(srcFile)
            merge_filename = os.path.splitext(merge_filename)[0] + dst_extension
            merge_filename = os.path.join(work_dir, merge_filename)

            for dst_file in target["int_dst_files"]:
                pdf_merger.append(dst_file)

            with open(merge_filename, 'wb') as fileobj:
                pdf_merger.write(fileobj)
            pdf_merger.close()

            target["int_dst_files"] = [merge_filename]


def HandleJob(job):
    global log

    log = job.log
    job._workdir = six.text_type(job._workdir)

    # check license
    try:
        log("Check license ....\n")
        allocate_license("AUTOCAD_003")
        log("License checked!!!!\n")
    except LicenseError as ex:
        log("Error occurred getting license for AUTOCAD DCS: %s\n" % ex.message)
        return 73

    # checkout the drawing and its references
    model = job.get_document()

    if model is None:
        job.log("Could not get document\n")
        return 1

    with Sandbox(job.getWorkspace()) as sb:
        cadjob_conversion = (0 == get_param_value(None, None, None, None, "FORCE_LEGACY",
                                                  cSetup, 0))
        if cadjob_conversion:
            env = rte.environ.copy()
            env[six.text_type("CADDOK_ACS_PARAM_SANDBOX_DIR")] = six.text_type(job.getWorkspace())
        srcFile = job.get_file()

        if srcFile is None:
            try:
                srcFile = model.getPrimaryFile()
            except Exception as e:
                job.log("%s\n" % e)

        if srcFile is None:
            file_name = model.getExternalFilename()
            job.log("Use file with name '%s'\n" % file_name)
            srcFilesByName = model.Files.KeywordQuery(cdbf_name=file_name)
            if srcFilesByName:
                srcFile = srcFilesByName[0]

        if srcFile is None:
            job.log("Could not get file\n")
            return 1

        srcFPName = sb.pathname(srcFile)

        application = model.erzeug_system
        appinfo_mode = 0  # 0 no appinfo, 1 = in workdir, 2 = in .wsm/.info
        work_file_dir = os.path.dirname(srcFPName)
        work_file_base = os.path.basename(srcFPName)
        appinfo_fname = srcFPName + ".appinfo"
        appinfo_subdir = os.path.join(work_file_dir, ".wsm", ".info", work_file_base + ".appinfo")

        accept_duplicates = get_param_value(None, None, None, None, "ACCEPT_DUPLICATE_FILENAMES",
                                            cSetup, False)
        cadacsutils.checkoutStructure(sb, model,
                                      ignoreDuplicates=accept_duplicates,
                                      use_subdir_for_appinfo=cadjob_conversion)

        if os.path.isfile(appinfo_subdir):
            appinfo_mode = 2
        elif os.path.isfile(appinfo_fname):
            appinfo_mode = 1

        if appinfo_mode == 0:
            job.log("Couldn't find the appinfo for the souce file: %s.\n"
                    % srcFPName)
            return 1

        cadjob_conversion = cadjob_conversion and (0 != appinfo_mode)
        if not cadjob_conversion:
            # "Classic" conversion mode
            # prepare the environment
            rte.environ["CADDOK_ACS_DCS_MODE"] = "LEGACY"
            suffix = Format2Suffix[job.target]
            result_type = cSetup["ResultTypes"][job.target]
            (cadReturn, _, _) = cadacsutils.prepareEnvironment(
                srcFPName,      # pathname of the drawing to convert
                suffix,         # target format
                model,          # this model
                job,            # the current job instance
                0,              # do _not_ checkout the frame file
                1,              # do load the frame data
                ".dwg",         # frame file suffix
                acadPrimFormat  # acad's primary formats
            )

            # the list of valid titles and valid borders is neccessary for reliable
            # recognizing of mechanical frames
            val = cad.getCADConfValue("Genius valid title names", application)
            rte.environ["CADDOK_ACS_VALID_TITLES"] = val
            val = cad.getCADConfValue("Genius valid border names", application)
            rte.environ["CADDOK_ACS_VALID_BORDERS"] = val
            rte.environ["CADDOK_ACS_PARAM_RAHMENFORMAT"] = "%s" % (model.z_format)

            #
            # pass the right sheet value dependend on the type of the document
            sheetHandlingValue = "0"                     # means: plot Modelspace
            if application in ["acad", "acad_mechanical"]:
                if cSetup.get("SHEET_HANDLING_CATALOG") is not None:
                    jt = job.target
                    if cSetup["SHEET_HANDLING_CATALOG"].get(jt) is not None:
                        sheetHandlingValue = cSetup["SHEET_HANDLING_CATALOG"][jt]
            elif application in ["acad:sht", "acad_mechanical:sht"]:
                # means: plot layout with this sheet number
                sheetHandlingValue = model.blattnr
            else:
                raise Exception("Conversion failed: cannot handle documents of "
                                "the application '%s'" % application)

            rte.environ["CADDOK_ACS_PARAM_SHEET"] = sheetHandlingValue
            zvs_multisheetmode = rte.environ["CADDOK_ACS_PARAM_SHEET"] != "-1"
            if zvs_multisheetmode:
                rte.environ["CADDOK_ACS_PARAM_MULTISHEET"] = "AN"
            else:
                rte.environ["CADDOK_ACS_PARAM_MULTISHEET"] = "AUS"

            # check setting for vintage frame migration
            val = cSetup.get("MIGRATE_VINTAGE_FRAME_SETTINGS")
            if val is not None:
                rte.environ["CADDOK_ACS_PARAM_MIGRATION"] = val

            val = cSetup.get("DXF_FORMAT", None)
            if val is not None:
                rte.environ["CADDOK_DXF_VERSION"] = val
            else:
                rte.environ["CADDOK_DXF_VERSION"] = "CURRENT"

            val = cSetup.get("DXF_PRECISION", None)
            if val is not None:
                rte.environ["CADDOK_DXF_PRECISION"] = str(val)
            else:
                rte.environ["CADDOK_DXF_PRECISION"] = "16"

            # call the cad system
            rc = convertCall(rte.environ)

            # check converter's return code
            if rc != 0:
                raise Exception("Conversion failed: received error from converter "
                                "for details look at %s\n" % job.getWorkspace())

            # check the existence of the result file
            if not os.path.isfile(cadReturn):
                raise Exception("Conversion failed: no feedback file from "
                                "converter, for details look at "
                                "%s\n" % job.getWorkspace())

            #
            # parse the report file
            # check converter's error code
            #
            (cadRC, cadMap) = cadacsutils.readCadAnswer(cadReturn)
            if cadRC != 0:
                raise Exception("Conversion failed with return-code '%s', "
                                "for details look at: %s\n" % (cadRC, cadReturn))

            # save the drawing back into the evault, if configured
            if cSetup["SAVE_DWG_FILE"] or job.target.lower() == "dwg":
                log("Storing file %s...\n" % srcFPName)
                job.store_file(srcFile, srcFPName, application,
                               replace_original=True)
                log("... done\n")

            # check for corresponding appinfo and
            # modify it to get it up to date
            if srcFile and ("dwg" == job.target.lower() or 1 == cSetup["SAVE_DWG_FILE"]):
                appinfoBasename = os.path.basename(srcFPName) + ".appinfo"
                appInfoFiles_list = CDB_File.KeywordQuery(cdbf_object_id=srcFile.cdbf_object_id,
                                                          cdbf_name=appinfoBasename)
                if appInfoFiles_list:
                    convPath = os.path.dirname(srcFPName)
                    appInfoFile = appInfoFiles_list[0]
                    log("expand appInfoFile for CRLF\n")
                    appInfoFullPath = convPath + "\\" + appinfoBasename

                    try:
                        if os.path.isfile(appInfoFullPath):
                            with io.open(appInfoFullPath, "a",
                                         encoding="utf-8") as appinfoF:
                                appinfoF.write(u"\n")
                            job.store_file(appInfoFile, appInfoFullPath,
                                           ".appinfo",
                                           replace_original=True)
                            log("appInfo would be rewritten to keep it "
                                "up to date\n")
                        else:
                            log("warning: appinfo file doesn't exists!\n")
                    except Exception as e:
                        log("%s \n" % e)

            # process the cadMap and checkin all files.
            #
            if "dwg" != job.target.lower() and srcFile is not None:
                convSheets = list(cadMap)
                convSheets.sort()

                if len(convSheets) == 1:
                    if "acad:sht" == application:
                        job.store_file(model, cadMap[convSheets[0]][3],
                                       result_type)
                    else:
                        job.store_file(srcFile, cadMap[convSheets[0]][3],
                                       result_type)
                else:
                    for sheetNo in convSheets:
                        sheetsuffix = "%s" % (suffix)
                        orig_fname = cadMap[sheetNo][3]
                        sheet_fname = os.path.splitext(orig_fname)[0] + sheetsuffix

                        if orig_fname != sheet_fname:
                            os.rename(orig_fname, sheet_fname)

                        job.store_file(srcFile, sheet_fname, result_type)
        else:
            # Workspaces conversion mode
            if sys.platform == "win32":
                from .acscadjob import create_cad_job

            if "acad:sht" == application and "dwg" == job.target.lower():
                job.log("DWG conversion not allowed for sheets\n")
                return -2

            env["CADDOK_ACS_DCS_MODE"] = "CADJOBS"
            try:
                try:
                    jobParams = job.getParameters()
                    if jobParams is None:
                        jobParams = {}
                except mq.NoPayloadDirectory:
                    job.log("no acs-job param dict available\n")
                    jobParams = {}

                targets = get_target_list(job, cSetup, jobParams)
                cad_job = None
                _, appinfo_fname, appinfo_subdir = get_appinfo_mode(srcFPName)
                handling_multisheet = ("acad:sht" == model.erzeug_system)

                for target in targets:
                    destination_format = target["dstformat"]
                    dst_extension = six.text_type(Format2Suffix[destination_format])
                    cad_job = create_cad_job(model,
                                             srcFPName,
                                             2 == appinfo_mode,
                                             target,
                                             destination_format,
                                             dst_extension,
                                             cSetup,
                                             jobParams,
                                             log,
                                             env,
                                             cad_job)
                check_duplicate_files(targets, True)
                job_result_info = execute_cad_job(cad_job)

                # post processing after execute cad job(s)
                merge_converted_pdf(targets, srcFPName)
                check_duplicate_files(targets, True)

                rename_converted_files(targets, job._workdir, cSetup, jobParams,
                                       handling_multisheet)
                check_duplicate_files(targets, True)

                check_converted_files(targets, srcFPName, appinfo_fname, appinfo_subdir,
                                      sb.location, cSetup, job_result_info)
                transfer_converted_files(targets, job, model, srcFile, cSetup)
            except CadJobException as e:
                errmsg = six.text_type(e)
                error_log_file = os.path.join(env["CADDOK_ACS_PARAM_SANDBOX_DIR"],
                                              "error.log")
                if os.path.isfile(error_log_file):
                    content = []
                    with codecs.open(error_log_file, "r", "utf-8") as f:
                        content = f.readlines()
                    errmsg = "\n" + errmsg + "\n".join(content)

                job.log("Error occurred executing CADJobs: %s\n" % errmsg)

                return -1

    # return to server ...
    return 0
