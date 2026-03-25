#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module excel

This is the documentation for the excel module.
"""

from __future__ import unicode_literals

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import sys
import traceback

from cdb import misc

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter


class ExcelConverterBase(object):
    """
    Base class for MS-Excel converters
    """
    __conversions__ = ['.xls', '.xlsx', '.xlsm', '.xlsb',
                       '.xlt', '.xltx', '.xltm',
                       '.csv', '.xml', '.ods']
    __application_name__ = "MS-Excel"

    # minimum required excel and type library versions
    __application_version_str__ = "Excel 2007"
    __application_version__ = 12
    __tlb_clsid__ = "{00020813-0000-0000-C000-000000000046}"
    __tlb_lcid__ = 0
    __tlb_major_version__ = 1
    __tlb_minor_version__ = 6

    def __init__(self, filename, **kwargs):
        super(ExcelConverterBase, self).__init__(filename, **kwargs)

        # overwrite default parameters, if defined
        try:
            self.conversion_timeout = self.conf_dict["excelconverter_conversion_timeout"]
        except Exception:
            pass

        try:
            self.print_cell_errors = self.get_conf_param("excelconverter_print_cell_errors", 0)
        except Exception:
            self.print_cell_errors = 0

        # Dialog robot configuration
        if self.window_timeout != 0:
            self.application_name = self.get_conf_param("excelconverter_application_name", "")
            self.auto_confirmations = self.get_conf_param("excelconverter_dialog_confirmations", {})

    def setup_application(self, application):
        if not self.get_conf_param("excelconverter_shellexecute", False):
            application.Visible = self.get_conf_param("excelconverter_visible", False)
        application.AskToUpdateLinks = 0
        application.Interactive = 0
        application.DisplayAlerts = 0
        application.EnableLargeOperationAlert = self.get_conf_param(
            "excelconverter_EnableLargeOperationAlert", False)
        application.AutomationSecurity = self.get_conf_param(
            "excelconverter_AutomationSecurity", 3)

    def open_doc(self):
        import win32com.client
        # first kill running excel processes
        self.kill_app("EXCEL.EXE")
        results = self.callback_customizing("open_source_file")
        if any((r is True) for r in results):
            self.log("open_doc: Customizing signaled that it already opened the file")
        else:
            if self.get_conf_param("excelconverter_shellexecute", False):
                self.office_app_obj, self.office_doc_obj = self.open_office_file_indirectly(
                    self.filename, "Excel.Application", "ActiveWorkbook")
            else:
                self.office_app_obj = win32com.client.DispatchEx('Excel.Application')
                self.setup_application(self.office_app_obj)
                self.office_doc_obj = self.office_app_obj.Workbooks.Open(self.filename, 0, False, 2)
                self.office_doc_obj.Calculation = self.get_conf_param(
                    "excelconverter_Calculation", -4135)
                self.office_doc_obj.CalculateBeforeSave = self.get_conf_param(
                    "excelconverter_CalculateBeforeSave", False)
                self.office_app_obj.MapPaperSize = self.get_conf_param(
                    "excelconverter_MapPaperSize", False)
                # Set Automation security lebvel back to default as suggested from Microsoft
                # https://learn.microsoft.com/de-de/office/vba/api/
                # excel.application.automationsecurity
                self.office_app_obj.AutomationSecurity = 1

    def get_document_variables(self):
        doc_vars = {}
        for name in self.office_doc_obj.Names:
            name = name.Name.split("!")[-1]  # remove sheet name prefix
            if self.is_reading_document_variable(name):
                doc_vars[name] = None
        return doc_vars

    def modify_document_variable_name(self, old_doc_var_name, new_doc_var_name):
        num_modified_vars = 0
        for name in self.office_doc_obj.Names:
            name_stripped = name.Name.split("!")[-1]  # remove sheet name prefix
            if name_stripped == old_doc_var_name:
                name.Name = new_doc_var_name
                num_modified_vars += 1
        return num_modified_vars

    def cleanup(self):
        try:
            self.office_doc_obj.Close(False)  # False => Don't ask to save changes
        except Exception:
            pass
        try:
            self.office_app_obj.Quit()
        except Exception:
            pass
        if self.office_doc_obj is not None:
            del self.office_doc_obj
        if self.office_app_obj is not None:
            del self.office_app_obj

    def handle_timeout(self):
        # Kill Excel Process
        self.kill_app("EXCEL.EXE")


class Excel2K7Converter(ExcelConverterBase, pdfconverter.O2K7PDFConverter):
    """
    Excel 2007 built-in PDF converter
    """

    def __init__(self, filename, **kwargs):
        super(Excel2K7Converter, self).__init__(filename, **kwargs)

    def create_pdf(self):
        try:
            self.open_doc()
            if self.update_document_variables():
                self.office_doc_obj.Save()
                self.store_source_file_modifications()
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
        for sheet in self.office_doc_obj.Worksheets:
            sheet.PageSetup.PrintErrors = self.print_cell_errors
        try:
            self.office_app_obj.ActivePrinter = self.printer
        except Exception:
            pass

        self.office_doc_obj.ExportAsFixedFormat(
            Type=win32com.client.constants.xlTypePDF,
            Filename=filename,
            Quality=win32com.client.constants.xlQualityStandard,
            IncludeDocProperties=True,
            IgnorePrintAreas=self.get_conf_param("excelconverter_ignore_print_areas", 1),
            OpenAfterPublish=False)
