#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import absolute_import

import logging
import os
import signal

from win32com.client import GetObject

from cdb import rte
from cdb import timeouts
from cdb.plattools import killableprocess

from cs.cadbase.jobexecbase import JobExecBase, JobExecLicenseInfo

LOGGER = logging.getLogger(__name__)


def quoteParam(inParam):
    if inParam.find(" ") != -1:
        return "\"" + inParam + "\""
    else:
        return inParam


class JobExecLicenseInfoSolidWorks(JobExecLicenseInfo):
    """
    Mapping of internal features to CONTACT ELEMENTS license features
    """

    # List of opname to list of features
    FEATURE_DEFINFIONS = {JobExecLicenseInfo.BASE: "SOLIDWORKS_011",
                          JobExecLicenseInfo.DRAWING: "SOLIDWORKS_012",
                          JobExecLicenseInfo.FAMILY_TABLE: "SOLIDWORKS_013",
                          JobExecLicenseInfo.MODIFY: "SOLIDWORKS_014",
                          JobExecLicenseInfo.ASSEMBLE_3D: "SOLIDWORKS_015",
                          JobExecLicenseInfo.SAVE_SECONDARY: "SOLIDWORKS_016"}

    FORMAT_FEATURES = {JobExecLicenseInfo.FEATURE_3D_SIMPLE: "SOLIDWORKS_017",
                       JobExecLicenseInfo.FEATURE_3D_EXCHANGE: "SOLIDWORKS_018",
                       JobExecLicenseInfo.FEATURE_2D_SIMPLE: "SOLIDWORKS_019",
                       JobExecLicenseInfo.FEATURE_2D_EXCHANGE: "SOLIDWORKS_020",
                       JobExecLicenseInfo.FEATURE_2D_PDF: "SOLIDWORKS_021",
                       JobExecLicenseInfo.FEATURE_3D_PDF: "SOLIDWORKS_022"}

    SUPPORTED_FORMATS = {JobExecLicenseInfo.FEATURE_2D_SIMPLE: ["tif", "jpg", "edrw", "png"],
                         JobExecLicenseInfo.FEATURE_2D_EXCHANGE: ["dxf", "dwg", "drw", "ai"],
                         JobExecLicenseInfo.FEATURE_3D_SIMPLE: ["wrl", "eprt", "easm", "smg",
                                                                "stl", "ply", "x_b", "x_t", "xaml",
                                                                "hcg", "cgr"],
                         JobExecLicenseInfo.FEATURE_3D_EXCHANGE: ["igs", "step_ap203",
                                                                  "step_ap214", "sldlfp", "prt",
                                                                  "asm", "hsf", "sldftp", "amf",
                                                                  "sat", "3dxml", "ifc", "3mf",
                                                                  "vda"],
                         JobExecLicenseInfo.FEATURE_3D_PDF: ["3dpdf"],
                         JobExecLicenseInfo.FEATURE_2D_PDF: ["pdf", "psd"]}

    def __init__(self):
        """
        For custom operation we need a feature to every cadcommand operation
        """
        JobExecLicenseInfo.__init__(self)
        self.add_custom_operation("MIGRATE_SEMI_FINISHED_PART", ["SOLIDWORKS_011"])

    def add_custom_operation(self, function, feature_list):
        self._op_features[function] = feature_list


class SolidWorksJobExec(JobExecBase):
    """
    Start job with configured Solid Edge in batch

    Configuration can be done by optional configuration file
    $CADDOK_BASE/etc/jobexec/SolidWorksJobExec.jsonconf

    Supported parameters in SolidWorksJobExec.jsonconf:
      {
         "language": "<integration language de-de, en-us> | optional"
      }
    """
    LIC_INFOS = JobExecLicenseInfoSolidWorks()

    def __init__(self, config=None, env=None):
        self.config = config
        self.env = env
        JobExecBase.__init__(self)

    def get_configuration(self):
        """
        get execution configuration

        :return: err, configuration, dcs_converter, timeout, cad_settings_file,
                 language
        """
        err = ""
        configuration = self.read_configuration(self.config)
        dcs_converter = self.get_config_value(configuration, "converterCmd", "")
        timeout = self.get_config_value(configuration, "timeout", 600)
        cad_settings_file = self.get_config_value(configuration,
                                                  "cadsettingsfile", "")
        frame_settings_file = self.get_config_value(configuration,
                                                    "framesettingsfile", "")
        language = self.get_config_value(configuration, "language", "english")

        if 0 == len(dcs_converter):
            err = "convertCmd is empty -> define valid converterCmd"
        elif not os.path.isfile(dcs_converter):
            err = "convertCmd '%s' doesn't exists!" % dcs_converter
        elif len(cad_settings_file) > 0 and not os.path.isfile(cad_settings_file):
            err = "CAD settings file '%s' not found" % cad_settings_file
        elif len(frame_settings_file) > 0 and not os.path.isfile(frame_settings_file):
            err = "Frame settings file '%s' not found" % frame_settings_file

        return err, dcs_converter, timeout, cad_settings_file, frame_settings_file, language

    def call(self, app_job):
        """
        Execute the app job

        :param app_job: App job
        """
        rc = JobExecBase.CAD_START_FAILED

        _, dcs_converter, timeout, cad_settings_file, frame_settings_file, \
            language = self.get_configuration()

        # start program
        env = rte.environ.copy()
        args = [dcs_converter]
        args.extend(["--job=%s" % app_job.jobDir])

        # optional arguments
        if cad_settings_file != "" and os.path.isfile(cad_settings_file):
            args.append(quoteParam("--cadsettings=" + cad_settings_file))

        if frame_settings_file != "" and os.path.isfile(frame_settings_file):
            args.append(quoteParam("--cadframesettings=" + frame_settings_file))

        args.append("--lang=" + language)

        try:
            LOGGER.info("SolidWorksJobExec: start (with timeout %d): %s" % (timeout, args))
            if -1 == timeout:
                rc = killableprocess.Popen(args, env=env).wait(timeout)
            else:
                cmd = killableprocess.Popen(args)
                timeouts.run_with_timeout(
                    lambda: timeouts.WaitResult(cmd.returncode, cmd.poll() is None),
                    timeout)
                rc = cmd.returncode
        except timeouts.WaitTimeout:
            # something goes wrong -> kill condcs_solidworks.exe and
            # SOLIDWORKS process
            cmd.terminate()
            rc = JobExecBase.CAD_START_FAILED

            # kill all sldworks.exe processes
            WMI = GetObject('winmgmts:')
            for p in WMI.InstancesOf('Win32_Process'):
                if "sldworks.exe" == p.Properties_("Name").Value.lower():
                    pid = p.Properties_("ProcessID").Value
                    os.kill(pid, signal.SIGILL)

            raise Exception("error: timeout (%d seconds) expired" % timeout)

        LOGGER.info("SolidWorksJobExec: finished: %s" % rc)

        return rc
