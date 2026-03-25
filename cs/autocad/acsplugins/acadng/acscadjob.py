# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module acscadjob

This is the documentation for the acscadjob module.
"""
from __future__ import absolute_import

import os
import six
import uuid

from cdb import cad
from cdb import sqlapi
from cs.autocad.jobexec.acadjobexec import AcadJobExec
from cs.cadbase.acsplugins.misc import get_job_parameter, get_param_value
from cs.cadbase import appinfohandler, cadcommands
from cs.cadbase.pdminfohelper import PdmInfoHelper


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []

# DCS job log
LOG = None


def joblog(msg):
    if LOG is not None:
        LOG(msg)


class CadJobException(Exception):
    pass


def build_sheet_names(work_file, sheet, name_affix, extension, dst_filenames):
    """
    work_file: name of cad_file
    sheet: ElementTree Element
    extension: dst extension with starting dot
    dst_filenames : set of file filename for duplicate elimination
    """
    work_file_dir = os.path.dirname(work_file)
    work_file_base = os.path.basename(work_file)
    work_file_root = os.path.splitext(work_file_base)[0]
    sheetname = sheet.attrib.get("number")
    normalized_name = sheetname
    i = 0
    t_name = normalized_name
    while t_name in dst_filenames:
        t_name = u"%s_%s" % (normalized_name, i)
        i += 1
    normalized_name = t_name
    dst_filenames.add(normalized_name)
    dstfile_name = os.path.join(work_file_dir, "%s_%s%s%s" %
                                (work_file_root, normalized_name, name_affix, extension))

    return dstfile_name


def get_plot_param_json(dst_frm, cSetup, doc, configParam, target):
    retVal = {}

    valid_JobParams = ["SHEET_HANDLING_CATALOG", "DXF_FORMAT", "DXF_PRECISION",
                       "PLOTTER", "FORMAT_LIST", "CDB_ATTR_BLOCKNAME",
                       "CONST_BLOCKNAME", "DELTA", "MERGE_FILENAME",
                       "PLOT_STYLE", "NAME_AFFIX"]

    joblog("list of attached job param(s):\n")
    for param in list(configParam):
        joblog("   configParam['%s']=%s\n" % (param, configParam[param]))
        if param in valid_JobParams:
            cSetup[param] = configParam[param]
        else:
            joblog("warning: '%s' isn't a valid job param. "
                   "Valid job params are: %s\n" % (param,
                                                   ", ".join(valid_JobParams)))

    joblog("\nlist of active config params:\n")
    for param in list(cSetup):
        if param != "__builtins__":
            joblog("   cSetup['%s']=%s\n" % (param, cSetup[param]))

    # check specific format config
    if "dxf" == dst_frm.lower():
        val = get_param_value("DXF_FORMAT", target, configParam, six.text_type,
                              None, cSetup)
        if val is not None:
            retVal["version"] = val
        else:
            retVal["version"] = "CURRENT"

        val = get_param_value("DXF_PRECISION", target, configParam, int,
                              None, cSetup)
        if val is not None:
            retVal["precision"] = val
        else:
            retVal["precision"] = 16
    elif dst_frm.lower() in ["pdf", "pdfm", "hpgl", "postscript",
                             "enc. postscript"]:
        val = get_param_value(None, None, None, None, "PLOTTER", cSetup)
        retVal["plottername"] = val[dst_frm]
        val = get_param_value(None, None, None, None, "FORMAT_LIST", cSetup)
        retVal["formatlist"] = val[dst_frm]

        val = get_param_value(None, None, None, None, "CONST_BLOCKNAME", cSetup, "")
        if val != "":
            retVal["blockname"] = val
        else:
            val = get_param_value(None, None, None, None, "CDB_ATTR_BLOCKNAME", cSetup, "")
            if val != "":
                cdb_attr_blk = val
            else:
                cdb_attr_blk = "Z_FORMAT"

            rset = sqlapi.RecordSet2("zeichnung_v",
                                     "z_nummer='%s' and z_index='%s'" % (doc.z_nummer, doc.z_index),
                                     [cdb_attr_blk])
            if rset is not None:
                val = rset[0].values()[0]
                retVal["blockname"] = val

        delta = 0
        val = get_param_value("DELTA", target, configParam, int,
                              None, cSetup)
        if val is not None:
            delta = val
        retVal["delta"] = delta

        val = get_param_value("PLOT_STYLE", target, configParam, six.text_type,
                              None, cSetup)
        if val is not None:
            retVal["plotstyle"] = val

    return retVal


def create_cad_job(doc, work_file, appinfo_in_subdir, target,
                   destination_format, dst_extension, cSetup, jobParams,
                   log, cad_env, job):
    """
    No single sheet export is necessary
    But we must handle multiple sheets from one document.
    For PS, PDF in Drawing we generate jobs for a single and multiple output files.

    Don't forget to change the checkout-routine call in dcs.__init__ to checkout
    appinfos in .wsm/.info/

    :param doc: Document to convert
    :param work_file: string, src filename with full path
    :param appinfo_in_subdir: bool, appinfo file in .wsm/.info ?
    :param target: dict, conversion param(s) for target
    :param destination_format: string, cad destination format
    :param dst_extension: string extension with dot of destination filename
    :param cSetup: full config param from setup.py
    :param jobParams: custom job params
    :param log: dcs job log to use for logging
    :param cad_env: cad environ starting cad
    :param job: cad job

    :returns: cad job (new job with first target)
    """
    global LOG
    LOG = log

    first_pass = job is None

    native_formats = ["dwg"]
    drawing_system = ["acad", "acad:sht"]
    needs_frame_data = doc.erzeug_system in drawing_system \
        and doc.z_format \
        and doc.z_format_gruppe
    native_target = destination_format.lower() in native_formats
    merge_xrefs = destination_format.lower() in ["resolvedwg"]
    project_env = None
    dst_files = []

    # check if nothing went wrong (implementation of plugin or get_target_list())
    if native_target and not first_pass:
        raise CadJobException("native target '%s' is not the first target" % destination_format)

    work_file_dir = os.path.dirname(work_file)
    work_file_base = os.path.basename(work_file)
    appinfo_subdir = os.path.join(work_file_dir, ".wsm", ".info", work_file_base + ".appinfo")

    flags_stop_error = [cadcommands.processingFlags.StopOnError]

    if appinfo_in_subdir:
        appinfo_fname = appinfo_subdir
    else:
        # old platform doesnt' support checkout in .wsm\info subir
        appinfo_fname = work_file + ".appinfo"

    sheet_handling_catalog = get_param_value(None, None, None, None,
                                             "SHEET_HANDLING_CATALOG", cSetup)

    # first: create job / set parameter / fill frame / save + opt. regenerate
    if first_pass:
        job_dir = os.path.abspath(os.path.join(work_file_dir, u".jobs%s" % uuid.uuid4()))

        if not os.path.exists(job_dir):
            os.makedirs(job_dir)

        if os.path.isfile(os.path.join(work_file_dir, "output.txt")):
            os.unlink(os.path.join(work_file_dir, "output.txt"))

        if doc.getProjectValue():
            project_env = doc.getProjectValue()

        set_param = get_job_parameter(jobParams, "SET_PARAMETER", list)
        set_param_with_hash = get_job_parameter(jobParams, "SET_PARAMETER_WITH_HASH", list)
        is_param_cmd = set_param is not None or set_param_with_hash is not None
        is_save_regenerate = is_param_cmd and get_job_parameter(jobParams,
                                                                "SET_PARAMETER_REGENERATE",
                                                                bool, False)
        needs_save_cmd = native_target or is_save_regenerate or is_param_cmd

        job_runner = cadcommands.JobRunner("autocad",
                                           AcadJobExec(None, cad_env),
                                           job_dir,
                                           project_env)
        job = job_runner.create_job()

        # set parameter command(s)
        if set_param is not None:
            cmd_param = cadcommands.CmdSetParameter(work_file,
                                                    [],
                                                    set_param,
                                                    parameter_hash=None,
                                                    regenerate=False,
                                                    flags=flags_stop_error)
            job.append(cmd_param)

        if set_param_with_hash is not None:
            parameter_hash = PdmInfoHelper().getCadParameterHash(set_param_with_hash)
            cmd_param = cadcommands.CmdSetParameter(work_file,
                                                    [],
                                                    set_param_with_hash,
                                                    parameter_hash,
                                                    regenerate=False,
                                                    flags=flags_stop_error)

        if needs_frame_data:
            frame_data_flags = [cadcommands.processingFlags.StopOnError]
            if not needs_save_cmd:
                frame_data_flags.append(cadcommands.processingFlags.SaveWorkFileAfterAction)
            cdb_frame_data = cad.get_data(doc.z_nummer, doc.z_index)
            frame_layer = ""
            textfield_layer = ""

            frame_data, frame_hash = PdmInfoHelper().getFrameDataForJson(
                frame_layer, textfield_layer, cdb_frame_data)

            cmd_fill_frame = cadcommands.CmdFillFrame(work_file, [],
                                                      frame_data, frame_hash,
                                                      frame_data_flags)
            job.append(cmd_fill_frame)

        if needs_save_cmd:
            cmd_save_appinfo = cadcommands.CmdSaveAppInfo(work_file, [], "SINGLE",
                                                          regenerate=is_save_regenerate,
                                                          flags=flags_stop_error)
            job.append(cmd_save_appinfo)
            if native_target:
                dst_files.append(work_file)
                dst_files.append(appinfo_fname)

    sheetHandlingValue = ""
    if merge_xrefs:
        val = get_param_value("MERGE_FILENAME", target, jobParams, six.text_type, None, cSetup, "")
        if val != "":
            dst_name = u"%s.dwg" % val
        else:
            dst_name = u"%s-merged.dwg" % os.path.splitext(work_file_base)[0]
        dst_name = os.path.join(work_file_dir, dst_name)
        cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                     destination_format,
                                                     dst_name,
                                                     sheet_id="0",
                                                     parameter={},
                                                     flags=flags_stop_error)
        job.append(cmd_secondary)
        dst_files.append(dst_name)

    if not native_target and not merge_xrefs:
        parameter = get_plot_param_json(destination_format, cSetup,
                                        doc, jobParams, target)
        param_name_affix = get_param_value("NAME_AFFIX", target, jobParams, six.text_type,
                                           "CADDOK_ACS_PARAM_NAME_AFFIX", cSetup, "")
        if "acad:sht" == doc.erzeug_system:
            sheetHandlingValue = int(doc.blattnr) - 1
            sheetHandlingValue = six.text_type(sheetHandlingValue)
        else:
            if sheet_handling_catalog is not None and \
               sheet_handling_catalog[destination_format] is not None:
                sheetHandlingValue = sheet_handling_catalog[destination_format]

        if "dxf" == destination_format.lower():
            # dfx supports all sheets in
            # one file only
            sheetHandlingValue = ""

        dst_file_names = set()
        if "-1" == sheetHandlingValue or "-0" == sheetHandlingValue:
            # plot all layouts
            sorted_sheets = appinfohandler.AppinfoHandler(appinfo_fname).get_sheets_by_sort_value()
            for _, sheet in six.iteritems(sorted_sheets):
                if "-0" == sheetHandlingValue and "0" == sheet.attrib["number"]:
                    continue

                dst_name = build_sheet_names(work_file, sheet, param_name_affix,
                                             dst_extension, dst_file_names)
                dst_name = os.path.join(work_file_dir, os.path.basename(dst_name))
                cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                             destination_format,
                                                             dst_name,
                                                             sheet_id=sheet.attrib["number"],
                                                             parameter=parameter,
                                                             flags=flags_stop_error)
                job.append(cmd_secondary)
                dst_files.append(dst_name)
        else:
            if "acad:sht" == doc.erzeug_system:
                dst_name = os.path.join(work_file_dir, doc.z_nummer + doc.z_index + dst_extension)
            else:
                dst_name = os.path.basename(work_file)
                dst_name = os.path.splitext(dst_name)[0] + param_name_affix + dst_extension
                dst_name = os.path.join(work_file_dir, dst_name)

            if "" == sheetHandlingValue:
                # plot current layout
                cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                             destination_format,
                                                             dst_name,
                                                             parameter=parameter,
                                                             flags=flags_stop_error)
            else:
                # plot specific layout
                cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                             destination_format,
                                                             dst_name,
                                                             sheet_id=sheetHandlingValue,
                                                             parameter=parameter,
                                                             flags=flags_stop_error)
            job.append(cmd_secondary)
            dst_files.append(dst_name)

    target["int_dst_files"] = dst_files
    target["int_cmd_flags"] = flags_stop_error

    return job
