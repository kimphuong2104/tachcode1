#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module project

This is the documentation for the project module.
"""

from __future__ import unicode_literals

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import sys
import traceback

from cdb import misc

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter


class ProjectConverterBase(object):
    """Base class for MS-Project converters"""

    __application_name__ = "MS-Project"
    __conversions__ = ['.mpp',
                       '.mpt']

    # minimum required Project and type library version
    __application_version_str__ = "Project 2010"
    __application_version__ = 14
    __tlb_clsid__ = "{A7107640-94DF-1068-855E-00DD01075445}"
    __tlb_lcid__ = 0
    __tlb_major_version__ = 4
    __tlb_minor_version__ = 7

    def __init__(self, filename, **kwargs):
        super(ProjectConverterBase, self).__init__(filename, **kwargs)

        self.project_application = None
        self.project_plan = None

        # overwrite default parameters, if defined
        try:
            self.window_timeout = self.conf_dict["projectconverter_window_timeout"]
        except Exception:
            pass
        try:
            self.conversion_timeout = self.conf_dict["projectconverter_conversion_timeout"]
        except Exception:
            pass
        # Dialog robot configuration
        if self.window_timeout != 0:
            self.application_name = self.get_conf_param("projectconverter_application_name", "")
            self.auto_confirmations = self.get_conf_param(
                "projectconverter_dialog_confirmations", {})

    def setup_application(self, application):
        application.Visible = self.get_conf_param("projectconverter_visible", False)

    def open_doc(self):
        import win32com.client
        results = self.callback_customizing("open_source_file")
        if any((r is True) for r in results):
            self.log("open_doc: Customizing signaled that it already opened the file")
        else:
            if self.get_conf_param("projectconverter_shellexecute", False):
                self.project_application, self.project_plan = self.open_office_file_indirectly(
                    self.filename, "MSProject.Application", "ActiveProject")
            else:
                self.project_application = win32com.client.Dispatch('MSProject.Application')
                self.setup_application(self.project_application)
                if self.project_application.FileOpen(Name=self.filename):
                    self.project_plan = self.project_application.ActiveProject

    def cleanup(self):
        try:
            # close without ever asking to save changes
            self.project_application.FileCloseEx(0)  # pjDoNotSave = 0
        except Exception:
            pass
        try:
            self.project_application.Quit()
        except Exception:
            pass
        if self.project_plan is not None:
            del self.project_plan
        if self.project_application is not None:
            del self.project_application

    def handle_timeout(self):
        # Kill Project Process
        self.kill_app("WINPROJ.EXE")


class Project2K10Converter(ProjectConverterBase, pdfconverter.O2K7PDFConverter):
    """Project 2010 built-in PDF converter"""

    # Note:
    # For some reason python's win32com can't generate a type lib from project 2013 (minor
    # version = 8), when the minimum minor version is defined with 7, so we can't use any project
    # api constants!

    def __init__(self, filename, **kwargs):
        super(Project2K10Converter, self).__init__(filename, **kwargs)

    def create_pdf(self):
        # first kill running Project processes
        self.kill_app("WINPROJ.EXE")
        try:
            self.open_doc()
            # Actually we would have called "self.project_plan.ExportAsFixedFormat()", but it always
            # fails with an exception (0x80020009: "Invalid argument"). Although calling
            # "self.project_application.DocumentExport" with the same arguments succeeds!
            results = self.callback_customizing("before_save_as_pdf")
            if any((r is True) for r in results):
                self.log("create_pdf: Customizing signaled that it already saved the file")
            else:
                self.save_as_pdf(self.targetfile)
        except Exception as exc:
            if hasattr(self, "log") and self.log:
                self.log("%s" % "\n".join(traceback.format_exception(*sys.exc_info())))
            else:
                misc.log_traceback("%s on %s" % (exc, self.filename))
            return False
        finally:
            self.cleanup()
        return True

    def save_as_pdf(self, filename):
        self.project_application.DocumentExport(
            Filename=filename,
            FileType=0,  # pjPDF
            # Setting following 2 arguments to False doesn't seem to work anyway, since the
            # properties and markups are always displayed nevertheless. So we don't export these
            # arguments into the .conf file.
            # IncludeDocumentProperties=True,
            # IncludeDocumentMarkup=True,
            ArchiveFormat=self.get_conf_param("projectconverter_create_pdf_a", False),
            # Always display the whole plan, so don't set following 2 arguments
            # FromDate=,
            # ToDate=,
        )
