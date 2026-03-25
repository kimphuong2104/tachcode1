#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module officewsjobexec.py

This module serves as a wrapper to access the platform specific implementation.
"""
from __future__ import absolute_import

import pythoncom
import pywintypes
import win32com.client
import six

from cs.cadbase.jobexecbase import JobExecBase
from cs.cadbase.wsutils.wssingleton import Singleton
from cs.cadbase import cadcommands
from cs.cadbase.wsutils.wserrorhandling import WsmException


__docformat__ = "restructuredtext en"


class VisioWSJobExec(JobExecBase, Singleton):
    CAD_SYSTEM = "MS-Visio"
    VISIO_EXE = "VISIO.EXE"
    VISIO_ADDIN_NAME = "CONTACT MS Office Link (MS-Visio)"

    def is_cad_running(self):
        """
        Try to obtain a COM object of the WORD Integration and check if
        CAD is running.

        :return: True if CAD is running, otherwise False
        """
        ret_val = False
        pythoncom.CoInitialize()

        try:
            office_addin = self.get_office_addin()
            ret_val = office_addin is not None
        finally:
            pythoncom.CoUninitialize()

        return ret_val

    def get_office_addin(self, uninitializeCOM=True):
        """
        Try to find a running instance of WORD and then obtain the
        Integration AddIn object from that instance.

        :return: WORD AddIn object. None if no AddIn is found or if there
                 is no running instance of WORD
        """
        visioAddin = None
        visioClient = None
        addInObject = None

        pythoncom.CoInitialize()
        try:
            # Disable the Office start screen for Visio.
            # Otherwise, 'Start Screen' blocks Visio and Visio waits for input from user
            # Set REG_KEY:
            # SOFTWARE\Microsoft\Office\16.0\Visio\Application\DisableBootToOfficeStart -> 1
            key = six.moves.winreg.OpenKey(six.moves.winreg.HKEY_CURRENT_USER,
                                           r"SOFTWARE\Microsoft\Office\16.0\Visio\Application",
                                           0, six.moves.winreg.KEY_READ)
            try:
                value = six.moves.winreg.QueryValueEx(key, "DisableBootToOfficeStart")
            except WindowsError:
                value = None
            if value is None or value[0] == 0:
                key = six.moves.winreg.OpenKey(six.moves.winreg.HKEY_CURRENT_USER,
                                               r"SOFTWARE\Microsoft\Office\16.0\Visio\Application",
                                               0, six.moves.winreg.KEY_WRITE)
                six.moves.winreg.SetValueEx(key, "DisableBootToOfficeStart", 0,
                                            six.moves.winreg.REG_DWORD, int("1"))
        except WindowsError:
            print(r"Couldn't set REG_KEY: \
                   SOFTWARE\Microsoft\Office\16.0\Visio\Application\DisableBootToOfficeStart -> 1")

        try:
            visioClient = win32com.client.GetObject(None, "Visio.Application")

            if visioClient is not None:
                try:
                    for visioAddin in visioClient.COMAddIns:
                        description = visioAddin.Description
                        if(description == self.VISIO_ADDIN_NAME):
                            try:
                                addInObject = visioAddin.Object
                                break
                            except BaseException:
                                print("Exception: Couldn't get the COM object for '%s'"
                                      % self.VISIO_ADDIN_NAME)
                except BaseException:
                    print("Exception: unable to determine the COM object for '%s'"
                          % self.VISIO_ADDIN_NAME)
                    addInObject = None
        except (pywintypes.com_error):
            print("Couldn't get com object for Visio.Application")

        if uninitializeCOM:
            pythoncom.CoUninitialize()
        if addInObject is not None:
            print("The COM Object for '%s' was found successfully" % self.VISIO_ADDIN_NAME)
        return addInObject

    def call(self, app_job):
        """
        Execute the app job.

        :param app_job: App job
        :return: 0 on success or error code on Failure
        """

        rc = 0
        if not self.is_cad_running():
            raise WsmException(u"VISIO is not running, cannot execute command!")

        pythoncom.CoInitialize()

        try:
            office_addin = self.get_office_addin()
            if office_addin is None:
                rc = JobExecBase.CAD_START_FAILED
            office_addin.runWSJobFunction(app_job.jobDir)
        except (AttributeError, pywintypes.com_error) as e:
            # Ignore communication errors if shutdown has been initiated
            if self.shutdown_initiated:
                pass
            else:
                raise e
        finally:
            pythoncom.CoUninitialize()

        return rc

    def shutdown(self, job_work_dir):
        """
        Send a SHUTDOWN command to Visio

        :param job_work_dir: Job working directory
        """
        self.shutdown_initiated = True
        cmd = cadcommands.CmdShutdown()
        cmd.execute(self.CAD_SYSTEM, self, job_work_dir)

    def get_cad_binary_path(self, version):
        """
        Get cad_binary_path from the registry
        """
        key = six.moves.winreg.OpenKey(six.moves.winreg.HKEY_LOCAL_MACHINE,
                                       r"SOFTWARE\Microsoft\Office\%s\Visio\InstallRoot"
                                       % version)
        value = six.moves.winreg.QueryValueEx(key, "Path")
        cad_binary_path = r"%s\%s" % (value[0], self.VISIO_EXE)
        return cad_binary_path
