#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module outlook

This is the documentation for the outlook module.
"""

from __future__ import unicode_literals

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import sys
import traceback

from cdb import misc

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter
    from cs.office.acsplugins.office.word import Word2K7Converter


class OutlookConverterBase(object):
    """Base class for MS-Outlook converters"""

    __application_name__ = "MS-Outlook"
    __conversions__ = ['.msg', '.eml']

    # minimum required Outlook and type library version
    __application_version_str__ = "Outlook 2007"
    __application_version__ = 12
    __tlb_clsid__ = "{00062FFF-0000-0000-C000-000000000046}"
    __tlb_lcid__ = 0
    __tlb_major_version__ = 9
    __tlb_minor_version__ = 3

    def __init__(self, filename, **kwargs):
        super(OutlookConverterBase, self).__init__(filename, **kwargs)

        self.outlook_application = None
        self.mail_item = None

        # overwrite default parameters, if defined
        try:
            self.window_timeout = self.conf_dict["outlookconverter_window_timeout"]
        except Exception:
            pass
        try:
            self.conversion_timeout = self.conf_dict["outlookconverter_conversion_timeout"]
        except Exception:
            pass

        # Dialog robot configuration
        if self.window_timeout != 0:
            self.application_name = self.get_conf_param("outlookconverter_application_name", "")
            self.auto_confirmations = self.get_conf_param(
                "outlookconverter_dialog_confirmations", {})

    def setup_application(self, application):
        pass

    def open_doc(self):
        import win32com.client
        results = self.callback_customizing("open_source_file")
        if any((r is True) for r in results):
            self.log("open_doc: Customizing signaled that it already opened the file")
        else:
            # 1) now do NOT just open the msg file like this:
            #    self.mail_item = self.outlook_application.Session.OpenSharedItem(self.filename)
            #    .. but indirectly open it like below instead, else we won't be able to retrieve the
            #    WordEditor afterwards:
            os.startfile('"%s"' % os.path.normpath(self.filename))
            # 2) first open the msg file and then create the outlook process afterwards, else the
            #    code might continue running when the mail isn't fully accessible yet, thus we would
            #    fail
            # 3) "self.open_office_file_indirectly" doesn't work, since "GetActiveObject" always
            #    returns None for Outlook)
            self.outlook_application = win32com.client.DispatchEx('Outlook.Application')
            self.setup_application(self.outlook_application)
            self.mail_item = self.outlook_application.ActiveInspector().CurrentItem
            # 4) there doesn't seem to be a way to get the filepath of an opened mail item, so we
            #    can't double-check if we're holding the correct mail object now

    def cleanup(self):
        try:
            self.outlook_application.Quit()
        except Exception:
            pass
        if self.outlook_application is not None:
            del self.outlook_application
        if self.mail_item is not None:
            del self.mail_item

    def handle_timeout(self):
        # Kill Outlook process
        self.kill_app("OUTLOOK.EXE")


class Outlook2K7Converter(OutlookConverterBase, pdfconverter.O2K7PDFConverter):
    """Converts using the Word 2007 built-in PDF converter"""
    # The approach to save a mail as pdf as suggested by Microsoft:
    # The SaveAsPDF-AddIn doesn't support Outlook, but when it is installed
    # we can copy the mail body and paste it into an empty word document and
    # save it as pdf

    def __init__(self, filename, **kwargs):
        super(Outlook2K7Converter, self).__init__(filename, **kwargs)
        # also generate the python type library of the word object model, in order to
        # 1) be sure that word is installed, since a word document object is used for exporting the
        #    mail to pdf
        # 2) be able to use the word api constants below
        Word2K7Converter.ensure_type_library()

    def create_pdf(self):
        # first kill running Outlook processes
        self.kill_app("OUTLOOK.EXE")
        try:
            self.open_doc()
            # now switch to the Word view and simply save it as if we opened up a word document:
            self.word_doc = self.mail_item.GetInspector.WordEditor
            # note: If outlook shows a security warning dialog after executing the line above,
            #       then this might happen due to the system's virus scanner not being up-to-date!
            #       On the other side you can permanently disable this behavior by adding following
            #       registry key (example für Outlook 2013):
            #       [HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Office\15.0\Outlook\Security]
            #       "ObjectModelGuard"=dword:00000002
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
        import win32com.client
        self.word_doc.ExportAsFixedFormat(
            OutputFileName=filename,
            ExportFormat=win32com.client.constants.wdExportFormatPDF,
            OpenAfterExport=False,
            OptimizeFor=win32com.client.constants.wdExportOptimizeForPrint,
            Range=win32com.client.constants.wdExportAllDocument,
            From=1,
            To=1,
            Item=0,
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=win32com.client.constants.wdExportCreateHeadingBookmarks,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=self.get_conf_param("wordconverter_create_pdf_a", False))
