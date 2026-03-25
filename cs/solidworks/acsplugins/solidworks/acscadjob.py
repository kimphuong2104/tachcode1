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

from cs.cadbase import appinfohandler, cadcommands
from cs.cadbase.acsplugins.misc import get_job_parameter, get_bool, get_param_value
from cs.cadbase.pdminfohelper import PdmInfoHelper

from cs.solidworks.jobexec.swjobexec import SolidWorksJobExec

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []

# DCS job log
LOG = None


def joblog(msg):
    if LOG is not None:
        LOG(msg)


drawing_system = ["SolidWorks", "SolidWorks:DRW"]


def get_save_secondary_parameter(target, job_params, setup):
    retVal = {}
    dpi_dict = {}
    scale_dict = {}

    dst_frm = target["dstformat"].lower()

    # check specific format config
    if dst_frm in ["tif", "tiff"]:
        valid_formats = ["A0", "A1", "A2", "A3", "A4", "A4V"]
        for valid_format in valid_formats:
            param_value = get_param_value("tiff_dpi_%s" % valid_format.lower(), target, job_params,
                                          six.text_type, "CADDOK_ACS_TIFF_DPI_%s" % valid_format,
                                          setup, "")
            if param_value != "":
                dpi_dict[valid_format] = int(param_value)

            param_value = get_param_value("tiff_skalierung_%s" % valid_format.lower(), target,
                                          job_params, six.text_type,
                                          "CADDOK_ACS_TIFF_SKALIERUNG_%s" % valid_format, setup, "")
            if param_value != "":
                scale_dict[valid_format] = int(param_value)

        param_value = get_param_value("tiff_farbmodus", target, job_params, six.text_type,
                                      "CADDOK_ACS_TIFF_FARBMODUS", setup)
        if param_value is not None:
            if param_value.lower() == "rgb":
                retVal["colordepth"] = 1    # swTiffImageRGB
            else:
                retVal["colordepth"] = 0    # swTiffImageBlackAndWhite

        param_value = get_param_value("tiff_kompression", target, job_params, six.text_type,
                                      "CADDOK_ACS_TIFF_KOMPRESSION", setup, "")
        if param_value != "":
            retVal["compressiontype"] = int(param_value)

        param_value = get_param_value("tiff_medium", target, job_params, six.text_type,
                                      "CADDOK_ACS_TIFF_MEDIUM", setup)
        if param_value is not None:
            retVal["outputcapture"] = int(param_value)
    elif dst_frm in ["dwg", "dxf"]:
        param_value = get_param_value("dxf_dwg_fonts", target, job_params, six.text_type,
                                      "CADDOK_ACS_DXF_DWG_FONTS", setup)
        if param_value is not None:
            if "truetype" == param_value.lower():
                retVal["export_fonts"] = 1
            else:
                retVal["export_fonts"] = 0

        param_value = get_param_value("dxf_dwg_scale", target, job_params, six.text_type,
                                      "CADDOK_ACS_DXF_DWG_SCALE", setup)
        if param_value is not None:
            retVal["export_scale"] = int(param_value)

        param_value = get_param_value("dxf_dwg_linestyles", target, job_params, six.text_type,
                                      "CADDOK_ACS_DXF_DWG_LINESTYLES", setup)
        if param_value is not None:
            if "solidworksstyles" == param_value.lower():
                retVal["export_linestyles"] = 1
            else:
                retVal["export_linestyles"] = 0

        param_value = get_param_value("dxf_dwg_version", target, job_params, six.text_type,
                                      "CADDOK_ACS_DXF_DWG_VERSION", setup, "")
        if param_value != "":
            retVal["format_version"] = param_value

    # check common format config
    param_value = get_param_value("model_config", target, job_params, six.text_type,
                                  "CADDOK_ACS_PARAM_MODEL_CONFIG", setup, "")
    if param_value != "":
        retVal["modelconfig"] = param_value

    if len(dpi_dict) > 0:
        retVal["resolution"] = dpi_dict

    if len(scale_dict) > 0:
        retVal["scale"] = scale_dict

    return retVal


def create_cad_job(doc,
                   work_file,
                   work_dir,
                   appinfo_in_subdir,
                   target,
                   cSetup,
                   setup,
                   file_type,
                   job_params,
                   log,
                   job):
    """
    No single sheet export is necessary
    But we must handle multiple sheets from one document.
    For PS, PDF in Drawing we generate jobs for a single and multiple output files. The return
    files are depending on settings in SolidWorks.

    Don't forget to change the checkout-routine call in dcs.__init__ to
    checkout appinfos in .wsm/.info/

    :param doc: Document to convert
    :param work_file: string, src filename with full path
    :param work_dir: string, working directory
    :appinfo_in_subdir: bool, true if app info file is in .wsm/.info sub dir
    :param destination_format: string, cad destination format
    :param dst_extension: string extension with dot of destination filename
    :param nativeTarget: list of native targets
    :param setup: solidworks container (SOLIDWORKS.xxx) dict
    :param file_type: string, src file type
    :param job_params: job parameters
    :param log: dcs job log to use for logging
    :param job: acs job

    :returns: List of generated files
    """
    global LOG
    LOG = log

    first_pass = job is None

    dst_extension = target["dstformat"]
    destination_format = cSetup["SuffixMap"][dst_extension]

    is_pdf_sheet_target = dst_extension in ["pdf"] and \
        get_bool(get_param_value("multisheet_pdf", target, job_params, six.text_type,
                                 "CADDOK_ACS_PARAM_MULTISHEET_PDF", setup, "False"))

    is_dxf_dwg_sheet_target = dst_extension in ["dxf", "dwg"] and \
        get_bool(get_param_value("multisheet_dwg_dxf", target, job_params, six.text_type,
                                 "CADDOK_ACS_PARAM_MULTISHEET_DWG_DXF", setup, "False"))

    is_tif_sheet_target = dst_extension in ["tif", "tiff"] and \
        get_bool(get_param_value("multisheet_tif", target, job_params, six.text_type,
                                 "CADDOK_ACS_PARAM_MULTISHEET_TIF", setup, "False"))

    is_edrw_sheet_target = dst_extension in ["edrw"] and \
        get_bool(get_param_value("multisheet_edrw", target, job_params, six.text_type,
                                 "CADDOK_ACS_PARAM_MULTISHEET_EDRW", setup, "False"))

    is_multi_sheet_target = is_pdf_sheet_target or is_dxf_dwg_sheet_target or \
        is_tif_sheet_target or is_edrw_sheet_target

    needs_frame_data = file_type in drawing_system \
        and doc.z_format is not None and doc.z_format != "" \
        and doc.z_format_gruppe is not None \
        and doc.z_format_gruppe != ""

    is_native_target = destination_format in cSetup["nativeTargets"]

    set_param = get_job_parameter(job_params, "SET_PARAMETER", list)
    set_param_with_hash = get_job_parameter(job_params, "SET_PARAMETER_WITH_HASH", list)
    is_param_cmd = set_param is not None or set_param_with_hash is not None
    is_save_regenerate = is_param_cmd and get_job_parameter(job_params,
                                                            "SET_PARAMETER_REGENERATE",
                                                            bool, False)
    needs_save_cmd = is_native_target or is_save_regenerate or is_param_cmd

    project_env = None
    cmds_secondary = []
    dst_files = []

    work_file_dir = os.path.dirname(work_file)
    work_file_base = os.path.basename(work_file)
    appinfo_subdir = os.path.join(work_file_dir, ".wsm", ".info", work_file_base + ".appinfo")

    if appinfo_in_subdir:
        appinfo_fname = appinfo_subdir
    else:
        # old platform doesnt' support checkout in .wsm\info subir
        appinfo_fname = work_file + ".appinfo"

    project_env = doc.getProjectValue()

    if first_pass:
        job_dir = os.path.abspath(os.path.join(work_dir, u".jobs%s" % uuid.uuid4()))
        os.makedirs(job_dir)
        job_runner = cadcommands.JobRunner("SolidWorks",
                                           SolidWorksJobExec(),
                                           job_dir,
                                           project_env)
        job = job_runner.create_job()

        cmd_change_workingdir = cadcommands.CmdCD(work_dir)
        job.append(cmd_change_workingdir)

    flags_stop_error = [cadcommands.processingFlags.StopOnError]

    # set parameter command(s)
    if set_param is not None and first_pass:
        cmd_param = cadcommands.CmdSetParameter(work_file,
                                                [],
                                                set_param,
                                                parameter_hash=None,
                                                regenerate=False,
                                                flags=flags_stop_error)
        job.append(cmd_param)

    if set_param_with_hash is not None and first_pass:
        parameter_hash = PdmInfoHelper().getCadParameterHash(set_param_with_hash)
        cmd_param = cadcommands.CmdSetParameter(work_file,
                                                [],
                                                set_param_with_hash,
                                                parameter_hash,
                                                regenerate=False,
                                                flags=flags_stop_error)
        job.append(cmd_param)

    if needs_frame_data and first_pass:
        frame_data_flags = [cadcommands.processingFlags.StopOnError]
        if not needs_save_cmd:
            frame_data_flags.append(cadcommands.processingFlags.SaveWorkFileAfterAction)
        cdb_frame_data = cad.get_data(doc.z_nummer, doc.z_index)
        frame_layer = ""
        textfield_layer = ""

        # we need a job per sheet and in special multi_sheet a job for all sheets
        sheets = appinfohandler.AppinfoHandler(appinfo_fname).get_sheet_ids()

        frame_data, frame_hash = PdmInfoHelper().getFrameDataForJson(
            frame_layer, textfield_layer, cdb_frame_data)

        cmd_fill_frame = cadcommands.CmdFillFrame(work_file,
                                                  [],
                                                  frame_data,
                                                  frame_hash,
                                                  frame_data_flags)
        job.append(cmd_fill_frame)

    if is_native_target:
        cmd_save_appinfo = cadcommands.CmdSaveAppInfo(work_file, [], "SINGLE",
                                                      flags=flags_stop_error)
        job.append(cmd_save_appinfo)
        dst_files.append(work_file)
        dst_files.append(appinfo_fname)
    else:
        is_drawing = file_type in drawing_system
        parameter = get_save_secondary_parameter(target, job_params, setup)

        if is_drawing:
            is_control_layers = get_bool(get_param_value("control_layers", target, job_params,
                                         six.text_type, "CADDOK_ACS_PARAM_CONTROL_LAYOUT", setup,
                                         "False"))

            if is_control_layers:
                # All layers are made visible if required.
                # All others layers will be explicitly suppressed.
                # This parameter has priority over visible_layers and invisible_layers.
                param_displayed_layers = get_param_value("displayed_layers", target, job_params,
                                                         six.text_type,
                                                         "CADDOK_ACS_PARAM_SHOW_LAYERS", setup, "")

                # All layers to be suppressed if necessary.
                param_invisible_layers = get_param_value("invisible_layers", target, job_params,
                                                         six.text_type,
                                                         "CADDOK_ACS_PARAM_SUPPRESS_LAYERS", setup,
                                                         "")

                # All layers are made visible if required.
                param_visible_layers = get_param_value("visible_layers", target, job_params,
                                                       six.text_type,
                                                       "CADDOK_ACS_PARAM_UNSUPPRESS_LAYERS",
                                                       setup, "")

                displayed_layers_list = None
                visible_layers_list = None
                invisible_layers_list = None

                if param_displayed_layers != "":
                    displayed_layers_list = param_displayed_layers.split(",")
                if param_visible_layers != "":
                    visible_layers_list = param_visible_layers.split(",")
                if param_invisible_layers != "":
                    invisible_layers_list = param_invisible_layers.split(",")

                cmd_Set2DVisibility = \
                    cadcommands.CmdSet2DVisibility(work_file,
                                                   # parameter,
                                                   displayed_layers=displayed_layers_list,
                                                   visible_layers=visible_layers_list,
                                                   invisible_layers=invisible_layers_list,
                                                   element_filter="",
                                                   flags=flags_stop_error)

                cmds_secondary.append(cmd_Set2DVisibility)

        param_name_affix = get_param_value("name_affix", target, job_params, six.text_type,
                                           "CADDOK_ACS_PARAM_NAME_AFFIX", setup, "")
        if is_drawing:
            # we need a job per sheet and in special multi_sheet a job for all sheets
            sheets = appinfohandler.AppinfoHandler(appinfo_fname).get_sheet_ids()
            if sheets:
                if len(sheets) == 1:
                    dst_name = os.path.splitext(work_file)[0] + \
                        param_name_affix + u"." + destination_format
                    cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                                 dst_extension,
                                                                 dst_name,
                                                                 parameter=parameter,
                                                                 flags=flags_stop_error)
                    cmds_secondary.append(cmd_secondary)
                    dst_files.append(dst_name)
                else:
                    if is_multi_sheet_target:
                        # generate a job for all sheets in one document
                        dst_name = os.path.splitext(work_file)[0] + param_name_affix + \
                            u"." + destination_format
                        cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                                     dst_extension,
                                                                     dst_name,
                                                                     parameter=parameter,
                                                                     flags=flags_stop_error)
                        cmds_secondary.append(cmd_secondary)
                        dst_files.append(dst_name)
                    else:
                        app_info_handler = appinfohandler.AppinfoHandler(appinfo_fname)
                        sort_sheets = app_info_handler.get_sheets_by_sort_value()
                        items = six.iteritems(sort_sheets)
                        for _, sheet in items:
                            sheet_num = sheet.attrib["number"]
                            if sheet_num == "1":
                                dst_name = os.path.splitext(work_file)[0] + "_Sheet_" + \
                                    sheet_num + u"." + destination_format
                            else:
                                dst_name = os.path.splitext(work_file)[0] + "_Sheet_" + \
                                    sheet_num + "." + sheet_num + u"." + destination_format

                            cmd_secondary = \
                                cadcommands.CmdSaveSecondary(work_file,
                                                             dst_extension,
                                                             dst_name,
                                                             sheet_id=sheet.attrib["id"],
                                                             parameter=parameter,
                                                             flags=flags_stop_error)
                            cmds_secondary.append(cmd_secondary)
                            dst_files.append(dst_name)
        else:
            # plot part/assembly
            dst_name = os.path.splitext(work_file)[0] + param_name_affix + u"." + destination_format
            cmd_secondary = cadcommands.CmdSaveSecondary(work_file,
                                                         dst_extension,
                                                         dst_name,
                                                         parameter=parameter,
                                                         flags=flags_stop_error)
            cmds_secondary.append(cmd_secondary)
            dst_files.append(dst_name)

        for cmd in cmds_secondary:
            job.append(cmd)

    target["int_dst_files"] = dst_files
    target["int_cmd_flags"] = flags_stop_error

    return job
