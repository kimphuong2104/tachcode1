#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import absolute_import

import io
import logging
import six
import os

from cdb import rte
from cdb.plattools import killableprocess
from cdb import timeouts
from cs.cadbase.jobexecbase import JobExecBase, JobExecLicenseInfo


LOGGER = logging.getLogger(__name__)


class JobExecLicenseInfoAutoCAD(JobExecLicenseInfo):
    """
    Mapping of internal features to CONTACT ELEMENTS license features
    """

    # List of opname to list of features
    FEATURE_DEFINFIONS = {JobExecLicenseInfo.BASE: "AUTOCAD_011",
                          JobExecLicenseInfo.DRAWING: "AUTOCAD_012",
                          JobExecLicenseInfo.FAMILY_TABLE: "AUTOCAD_013",
                          JobExecLicenseInfo.MODIFY: "AUTOCAD_014",
                          JobExecLicenseInfo.ASSEMBLE_3D: "AUTOCAD_015",
                          JobExecLicenseInfo.SAVE_SECONDARY: "AUTOCAD_016"}

    FORMAT_FEATURES = {JobExecLicenseInfo.FEATURE_2D_SIMPLE: "AUTOCAD_019",
                       JobExecLicenseInfo.FEATURE_2D_EXCHANGE: "AUTOCAD_020",
                       JobExecLicenseInfo.FEATURE_2D_PDF: "AUTOCAD_021"}

    # Format names must be unique for 2D, 3D
    SUPPORTED_FORMATS = {JobExecLicenseInfo.FEATURE_2D_SIMPLE: ["HPGL", "hpgl"
                                                                "PostScript", "postscript",
                                                                "Enc. PostScript",
                                                                "enc. postscript",
                                                                "RESOLVEDWG", "resolvedwg"],
                         JobExecLicenseInfo.FEATURE_2D_EXCHANGE: ["DXF", "dxf"],
                         JobExecLicenseInfo.FEATURE_2D_PDF: ["PDF", "pdf", "PDFM", "pdfm"]}


class AcadJobExec(JobExecBase):
    """
    Start job with configured AutoCAD in batch

    Configuration can be done by optional configuration file
    $CADDOK_BASE/etc/jobexec/ACADJobExec.jsonconf

    Supported parameters in ACADJobExec.jsonconf:
      {
         "language": "<integration language de-de, en-us> | optional"
      }
    """
    LIC_INFOS = JobExecLicenseInfoAutoCAD()

    def __init__(self, config=None, env=None):
        self.config = config
        self.env = env
        JobExecBase.__init__(self)

    @staticmethod
    def _get_config_value(configuration, key, default_value):
        """
        :param configuration: Configuration (dictionary)
        :param key: Key
        :param default_value Default value

        :return: Configuration value using the specified default value if the
                 configuration value is empty
        """
        ret = default_value
        conf_value = configuration.get(key)
        if conf_value:
            ret = conf_value
        return ret

    def get_configuration(self):
        """
        get execution configuration

        :return: err, configuration, dcs_converter, dcs_converter_options,
                 timeout, cad_settings_file, language
        """
        configuration = self.read_configuration(self.config)

        dcs_converter = self.get_config_value(configuration,
                                              "converterCmd", "")
        dcs_converter_options = self.get_config_value(configuration,
                                                      "converterOptions", [])
        timeout = self.get_config_value(configuration, "timeout", 600)
        cad_settings_file = self.get_config_value(configuration,
                                                  "cadsettingsfile", None)
        language = self.get_config_value(configuration, "language", "1033")

        err = ""
        if not os.path.isfile(dcs_converter):
            err = "Converter program didn't found! " \
                  "Converter program='%s'" % dcs_converter
        elif 0 == len(dcs_converter_options):
            err = "Converter options emtpy. Specify the appropriate " \
                  "AutoCAD converter options"

        return err, configuration, dcs_converter, dcs_converter_options, \
            timeout, cad_settings_file, language

    def call(self, app_job):
        """
        Execute the app job

        :param app_job: App job
        """
        rc = JobExecBase.CAD_START_FAILED

        err, configuration, dcs_converter, dcs_converter_options, timeout, \
            cad_settings_file, language = self.get_configuration()

        if err != "":
            LOGGER.error("ACADJobExec: '%s'" % err)
            return rc
        else:
            scriptFileName = six.text_type(os.path.abspath("acs_acad.scr"))
            with io.open(scriptFileName, "w", encoding="utf-8") as script_file:
                script_file.write(u"cimdb_acs_convert\n")
            dcs_converter_options.append("/b")
            dcs_converter_options.append(scriptFileName)
            env = self.env
            if env is None:
                env = rte.environ.copy()
            env["CADDOK_ACS_PARAM_JOB_PATH"] = app_job.jobDir
            env["CADDOK_ACS_PARAM_LANGUAGE"] = language
            env["CADDOK_ACS_DCS_MODE"] = "CADJOBS"

            if cad_settings_file is not None and cad_settings_file != "":
                env["CADDOK_ACS_PARAM_CAD_SETTINGS"] = cad_settings_file
            args = [dcs_converter] + dcs_converter_options
            LOGGER.info("ACADJobExec: start (with timeout %d): %s" % (timeout, args))

            rc = 0
            try:
                if -1 == timeout:
                    killableprocess.Popen(args, env=env).wait(timeout)
                else:
                    cmd = killableprocess.Popen(args, env=env)
                    timeouts.run_with_timeout(
                        lambda: timeouts.WaitResult(cmd.returncode,
                                                    cmd.poll() is None),
                        timeout)
            except timeouts.WaitTimeout:
                # something goes wrong -> kill autocad process
                cmd.terminate()
                rc = JobExecBase.CAD_START_FAILED
                raise Exception("error: timeout (%d secs) expired" % timeout)

            LOGGER.info("ACADJobExec: finished: %s" % rc)

        return rc
