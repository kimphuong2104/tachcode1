#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import os
import signal
from win32com.client import GetObject

from cdb import misc
from cdb import rte
from cdb import timeouts
from cdb.plattools import killableprocess

from cs.cadbase.jobexecbase import JobExecBase, JobExecLicenseInfo


def log(msg):
    print(msg)
    misc.cdblogv(misc.kLogMsg, 5, log)


class JobExecLicenseInfoOffice(JobExecLicenseInfo):
    """
    Mapping of internal features to CONTACT ELEMENTS license features
    """
    # List of opname to list of features
    FEATURE_DEFINFIONS = {JobExecLicenseInfo.BASE: "MS-OFFICE_011",
                          JobExecLicenseInfo.DRAWING: "MS-OFFICE_012",
                          JobExecLicenseInfo.MODIFY: "MS-OFFICE_013",
                          JobExecLicenseInfo.SAVE_SECONDARY: "MS-OFFICE_014",
                          JobExecLicenseInfo.ASSEMBLE_3D: "MS-OFFICE_015"}

    FORMAT_FEATURES = {JobExecLicenseInfo.FEATURE_2D_SIMPLE: "MS-OFFICE_019",
                       JobExecLicenseInfo.FEATURE_2D_EXCHANGE: "MS-OFFICE_020",
                       JobExecLicenseInfo.FEATURE_2D_PDF: "MS-OFFICE_021"}

    # Format names must be unique for 2D, 3D
    SUPPORTED_FORMATS = {JobExecLicenseInfo.FEATURE_2D_SIMPLE: ["jpg", "tif"],
                         JobExecLicenseInfo.FEATURE_2D_EXCHANGE: [""],
                         JobExecLicenseInfo.FEATURE_2D_PDF: ["pdf"]}


class OfficeJobExec(JobExecBase):
    """
    Start job with configured Office in batch

    Configuration can be done by optional configuration file
    $CADDOK_BASE/etc/jobexec/OfficeJobExec.jsonconf

    Supported parameters in OfficeJobExec.jsonconf:
        { "converterCmd": "<program to call for conversion>"
          "timeout": <max time in seconds for conversion> | optional, standard -1 for unlimit
          "catsettingsfile": "<path to exportsettings file> |optional"
          "language": "<integration language de-de, en-us> |optional"
        }

    """
    LIC_INFOS = JobExecLicenseInfoOffice()

    def __init__(self, config=None, env=None):
        self.config = config
        self.env = env
        JobExecBase.__init__(self)

    @staticmethod
    def _get_config_value_with_default(configuration, key, default_value):
        """
        Use default value if configuration value is empty
        """
        ret = default_value
        conf_value = configuration.get(key)
        if conf_value:
            ret = conf_value
        return ret

    def call(self, app_job):
        """
        :parameter: app_job AppJob
        """

        rc = JobExecBase.CAD_START_FAILED

        err, dcs_converter, timeout, cad_settings_file, language \
            = self.get_configuration()

        if err != "":
            misc.cdblogv(misc.kLogErr, 0, "OfficeJobExec: '%s'" % err)
        else:
            jobdir = app_job.jobDir
            if jobdir.find(" ") != -1:
                jobdir = "\"%s\"" % jobdir
            args = [dcs_converter, "--job=%s" % jobdir]

            if len(cad_settings_file) != 0 and os.path.isfile(cad_settings_file):
                if cad_settings_file.find(" ") != -1:
                    cad_settings_file = "\"%s\"" % cad_settings_file
                args.extend(["--cadsettings=%s" % cad_settings_file])
            if language != "":
                args.extend(["--lang=%s" % language])
            log("OfficeJobExec: start (with timeout %d): %s" % (timeout, args))

            if not os.path.isfile(args[0]):
                log("ERROR Office PATH: '%s'" % args[0])

            try:
                if -1 == timeout:
                    env = rte.environ.copy()
                    rc = killableprocess.Popen(args, env=env).wait(timeout)
                else:
                    cmd = killableprocess.Popen(args)
                    timeouts.run_with_timeout(
                        lambda: timeouts.WaitResult(cmd.returncode, cmd.poll() is None),
                        timeout)
                    rc = cmd.returncode
            except timeouts.WaitTimeout:
                # something goes wrong -> kill office process
                cmd.terminate()
                rc = JobExecBase.CAD_START_FAILED

                # kill all office processes
                wmi = GetObject('winmgmts:')
                for p in wmi.InstancesOf('Win32_Process'):
                    if "WINWORD.EXE" == p.Properties_("Name").Value.lower():
                        pid = p.Properties_("ProcessID").Value
                        os.kill(pid, signal.SIGILL)
                raise Exception("error: timeout (%d seconds) expired" % timeout)

            log("Office finished: %s" % rc)
            if 0 == rc:
                log("ok")
            elif -1 == rc:
                log("error: Couldn't connect to Office")
            elif -2 == rc:
                log("error: Couldn't determine conversion mode")
            else:
                log("error: something goes wrong -> see dcs log "
                    "(CONDCS_office.log) for further information")

        return rc

    def get_configuration(self):
        """
        get execution configuration

        :return: err, configuration, dcs_converter, timeout, cad_settings_file,
                 language
        """
        err = ""
        configuration = self.read_configuration(self.config)

        dcs_converter = self.get_config_value(configuration,
                                              "converterCmd", "")
        timeout = self.get_config_value(configuration, "timeout", 600)
        cad_settings_file = self.get_config_value(configuration,
                                                  "cadsettingsfile", "")
        language = self.get_config_value(configuration, "language", "1033")

        if 0 == len(dcs_converter):
            err = "convertCmd is empty -> define valid converterCmd"
        elif not os.path.isfile(dcs_converter):
            err = "convertCmd '%s' doesn't exists!" % dcs_converter

        return err, dcs_converter, timeout, cad_settings_file, language
