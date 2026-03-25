# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module jobexecbase
"""

from .wsutils.wserrorhandling import WsmException
import os
import json
import logging
from cdb import rte

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class JobExecLicenseInfo(object):
    BASE = "BASE"
    MODIFY = "MODIFY"
    FAMILY_TABLE = "FAMILY_TABLE"
    DRAWING = "DRAWING"
    ASSEMBLE_3D = "ASSEMBLE_3D"
    SAVE_SECONDARY = "SAVE_SECONDARY"

    OP_LIST = {BASE: ["SET_PARAMETER",
                      "SAVEAPPINFO",
                      "LISTOFFILES",
                      "TOPFILES",
                      "LOAD",
                      "CLOSE",
                      "CLOSE_ALL",
                      "ENSURE_NOT_LOADED",
                      "PWD",
                      "CD",
                      "SAVE_STATE",
                      "RESTORE_STATE",
                      "SAVEAPPINFO_MODIFIED_IN_TRANSACTION"],
               DRAWING: ["FILL_FRAME",
                         "LOAD_FRAME",
                         "FILL_BOMPOS",
                         "SET_2D_VISIBILITY",
                         "REMOVE_FRAME"],
               MODIFY: ["RENAME",
                        "REPLACE"],
               FAMILY_TABLE: ["SET_PARAMETRIC",
                              "UPDATE_CADVARIANT_TABLE",
                              "RENAME_VARIANT",
                              "SET_CADVARIANT_TABLE_DEF",
                              "GET_CADVARIANT_TABLE_DEF",
                              "SET_GEO_PARAMETER"],
               ASSEMBLE_3D: ["CREATE_FILE",
                             "CREATE_FROM",
                             "ADD_COMPONENT",
                             "DELETE_COMPONENT",
                             "POSITION_COMPONENT",
                             "HIDE_COMPONENTS"],
               SAVE_SECONDARY: ["SAVE_SECONDARY"]}

    FEATURE_3D_SIMPLE = "SIMPLE_3D"
    FEATURE_3D_EXCHANGE = "EXCHANGE_3D"
    FEATURE_2D_SIMPLE = "SIMPLE_2D"
    FEATURE_2D_PDF = "2D_PDF"
    FEATURE_2D_EXCHANGE = "EXCHANGE_2D"
    FEATURE_3D_PDF = "3D_PDF"
    FEATURE_3D_JT = "3D_JT"

    # Feature to LIST of CAD featurenames
    FEATURE_DEFINFIONS = {}

    # FEATURE to CAD featurename for format
    FORMAT_FEATURES = {}

    # FEATURE to list of formats,  Format names unique for 2D, 3D
    SUPPORTED_FORMATS = {}

    def __init__(self):
        self._op_features = {}
        self._format_features = {}
        for feature_def, operations in self.OP_LIST.items():
            feature = self.FEATURE_DEFINFIONS.get(feature_def)
            if feature:
                for op in operations:
                    op_list = self._op_features.get(op)
                    # Kein defaultdict, da wir bei der Verwendung auch None erhalten wollen
                    if op_list is None:
                        op_list = []
                        self._op_features[op] = op_list
                    op_list.append(feature)

        for feature_def, format_list in self.SUPPORTED_FORMATS.items():
            for format in format_list:
                feature = self.FORMAT_FEATURES[feature_def]
                self._format_features[format] = feature

    def getOperationFeatures(self, opname):
        """
        :returns List of features (strings) needed for the given CAD operation
        """
        return self._op_features.get(opname)

    def getFormatFeatures(self, secFormat):
        """
        :param secFormat: string format name

        :returns Feature (string)
        """
        return self._format_features.get(secFormat)


class LiAutomationTests(JobExecLicenseInfo):
    """
    Mapping of internal features to CONTACT ELEMENTS license features
    This is a dummy class for automation tests with SOEDs.
    The FEATURE must not exist in any license files
    """
    TEST_FEATURE = "AUTOTEST_001"
    # List of opname to list of features
    FEATURE_DEFINFIONS = {JobExecLicenseInfo.BASE: TEST_FEATURE,
                          JobExecLicenseInfo.DRAWING: TEST_FEATURE,
                          JobExecLicenseInfo.FAMILY_TABLE: TEST_FEATURE,
                          JobExecLicenseInfo.MODIFY: TEST_FEATURE,
                          JobExecLicenseInfo.ASSEMBLE_3D: TEST_FEATURE,
                          JobExecLicenseInfo.SAVE_SECONDARY: TEST_FEATURE}

    FORMAT_FEATURES = {JobExecLicenseInfo.FEATURE_3D_SIMPLE: TEST_FEATURE,
                       JobExecLicenseInfo.FEATURE_3D_EXCHANGE: TEST_FEATURE,
                       JobExecLicenseInfo.FEATURE_2D_SIMPLE: TEST_FEATURE,
                       JobExecLicenseInfo.FEATURE_2D_EXCHANGE: TEST_FEATURE,
                       JobExecLicenseInfo.FEATURE_2D_PDF: TEST_FEATURE,
                       JobExecLicenseInfo.FEATURE_3D_PDF: TEST_FEATURE}

    # Format names must be unique for 2D, 3D
    SUPPORTED_FORMATS = {JobExecLicenseInfo.FEATURE_2D_SIMPLE: ["tif", "cgm", "hpgl", "png",
                                                                "jpg", "bmp"],
                         JobExecLicenseInfo.FEATURE_2D_EXCHANGE: ["dwg", "dxf", "ig2"],
                         JobExecLicenseInfo.FEATURE_3D_SIMPLE: ["cgr", "stl", "wrl", "hcg", "txt"],
                         JobExecLicenseInfo.FEATURE_3D_EXCHANGE: ["3dxml", "step", "iges3d",
                                                                  "model"],
                         JobExecLicenseInfo.FEATURE_3D_PDF: ["3dpdf"],
                         JobExecLicenseInfo.FEATURE_2D_PDF: ["pdf", "ps"]}


class JobExecBase(object):
    """
    Base class for job execution. Every CAD integration must provide an
    implementation derived from this abstract class. At least call() and
    ist_cad_running() methods must be overridden.
    """
    CAD_START_FAILED = 333
    LIC_INFOS = LiAutomationTests()

    def call(self, app_job):
        """
        Execute a CAD Job. Must be overridden by real CAD implementations.
        NOTICE: A real implementation of this method MUST return an error code
        (usually 0)!

        :param app_job: AppJob, instance of cs.cadbase.appjobs.appjob.AppJob

        :return: 0 on success, otherwise execution error code.
        """
        raise WsmException("JobExecBase not implemented")

    def is_cad_running(self):
        """
        Check if the corresponding CAD system is running. Must be overridden
        by real CAD implementation.

        for exe calls cad is ever running
        for attaching to a running cad this method must be overwritten

        :return: True if CAD is running, False otherwise
        """
        return True

    @staticmethod
    def get_notification_dir():
        """
        Retrieve CAD notification directory.

        :returns string path to the CAD notification directory or None if
                 APPDATA is not available (on non-Windows systems)
        """
        notification_dir = None
        appdata = rte.environ.get("APPDATA")
        if appdata:
            notification_dir = os.path.join(appdata, "Contact", "CDB_WSM", "cadcommunication")
        return notification_dir

    @staticmethod
    def get_config_value(configuration, key, default_value, project_name=None):
        """
        Get configuration value by the specified key or the default value,
        if the key does not exist in the configuration.

        :param configuration: Configuration (dictionary)
        :param key: Key (string)
        :param default_value: Default value
        :param project_name: project name (string)
               for a project dependent configuration

        :return: Configuration value, priority:
                 1. project dependent configuration (project_name not None)
                 2. configuration
                 3. default value
        """
        conf_value = None
        if project_name is not None:
            project_dict_all = configuration.get("projectconfiguration")
            if project_dict_all is not None:
                project_dict = project_dict_all.get(project_name)
                if project_dict is not None:
                    conf_value = project_dict.get(key)
        if conf_value is None:
            conf_value = configuration.get(key)
        if conf_value is not None:
            return conf_value
        return default_value

    @staticmethod
    def get_last_save_file(base_filename):
        """
        get newest file for systems like Creo Parametric.
        Other system just return base_filename.

        :param base_filename: path version counter without .<n>
        :return: string with filename
        """
        return base_filename

    def getAsyncError(self):
        """
        Stub, necessary for compatibility with AppJob (method "wait")
        """
        return None

    def read_configuration(self, config_file=None):
        """
        Read the configuration file for the current jobexec.

        :param config_file: Name of the configuration file. If
                            not specified, the configuration is read from
                            $CADDOK_BASE/etc/jobexec/<JobExecClass>.jsonconf
        """
        if not config_file:
            caddok_base = rte.environ.get("CADDOK_BASE")
            if not caddok_base:
                logging.info("JobExec: Cannot determine the configuration "
                             "file location, because CADDOK_BASE is not set")
                return {}
            config_file = os.path.join(caddok_base, "etc", "jobexec",
                                       self.__class__.__name__ + ".jsonconf")
        if not os.path.exists(config_file):
            logging.info("JobExec: Configuration file '%s' does not exists", config_file)
            return {}
        logging.info("JobExec: Using configuration file '%s'", config_file)
        lines = []
        with open(config_file, "r") as f:
            for line in f:
                # Ignore comment lines. comment lines starts with a "#"
                if not line.strip().startswith("#"):
                    lines.append(line.strip())
        config = json.loads(" ".join(lines))
        return config

    def getLicInfos(self):
        return self.LIC_INFOS


# Guard importing as main module
if __name__ == "__main__":
    pass
