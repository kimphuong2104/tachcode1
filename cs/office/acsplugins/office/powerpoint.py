#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module powerpoint

This is the documentation for the powerpoint module.
"""

from __future__ import unicode_literals

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import sys
import traceback

from cdb import misc

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter


class PowerPointConverterBase(object):
    """
    Base class for MS-PowerPoint converters
    """
    __conversions__ = ['.ppt', '.pptx', '.pptm', '.pot', '.potm', '.potx']
    __application_name__ = "MS-PowerPoint"

    # minimum required PowerPoint and type library version
    __application_version_str__ = "PowerPoint 2007"
    __application_version__ = 12
    __tlb_clsid__ = "{91493440-5A91-11CF-8700-00AA0060263B}"
    __tlb_lcid__ = 0
    __tlb_major_version__ = 2
    __tlb_minor_version__ = 9

    def __init__(self, filename, **kwargs):
        super(PowerPointConverterBase, self).__init__(filename, **kwargs)

        # overwrite default parameters, if defined
        try:
            self.conversion_timeout = self.conf_dict["powerpointconverter_conversion_timeout"]
        except Exception:
            pass
        # Dialog robot configuration
        if self.window_timeout != 0:
            self.application_name = self.get_conf_param("powerpointconverter_application_name", "")
            self.auto_confirmations = self.get_conf_param(
                "powerpointconverter_dialog_confirmations", {})

    def setup_application(self, application):
        if not self.get_conf_param("powerpointconverter_shellexecute", False):
            _visible = self.get_conf_param("powerpointconverter_visible", False)
            if application.Visible and not _visible:
                application.Visible = 0
            elif not application.Visible and _visible:
                application.Visible = -1  # Office.MsoTriState.msoTrue = -1
        application.AutomationSecurity = self.get_conf_param(
            "powerpointconverter_AutomationSecurity", 3)

    def open_doc(self):
        import win32com.client
        # first kill running PowerPoint processes
        self.kill_app("POWERPNT.EXE")
        results = self.callback_customizing("open_source_file")
        if any((r is True) for r in results):
            self.log("open_doc: Customizing signaled that it already opened the file")
        else:
            if self.get_conf_param("powerpointconverter_shellexecute", False):
                self.office_app_obj, self.office_doc_obj = self.open_office_file_indirectly(
                    self.filename, "Powerpoint.Application", "ActivePresentation")
            else:
                self.office_app_obj = win32com.client.DispatchEx('Powerpoint.Application')
                self.setup_application(self.office_app_obj)
                self.office_doc_obj = self.office_app_obj.Presentations.Open(
                    self.filename, False, False, False)
                # Set Automation security lebvel back to default as suggested from Microsoft
                # https://learn.microsoft.com/de-de/office/vba/api/
                # powerpoint.application.automationsecurity
                self.office_app_obj.AutomationSecurity = 1

    def get_document_variables(self):
        doc_vars = {}
        if self.get_conf_param("powerpointconverter_shellexecute", False):
            shapes = []
            for slide in self.office_doc_obj.Slides:
                shapes.extend(slide.Shapes)
            for design in self.office_doc_obj.Designs:
                shapes.extend(design.SlideMaster.Shapes)
                for layout in design.SlideMaster.CustomLayouts:
                    shapes.extend(layout.Shapes)
            for shape in shapes:
                if shape.HasTextFrame == -1:  # MsoTriState.msoTrue
                    name = shape.Tags.Item("cdb_docvar")
                    if name and self.is_reading_document_variable(name):
                        doc_vars[name] = None
        else:
            # For PowerPoint updating the document variables doesn't work
            # when starting PowerPoint as a service process!
            self.log("Warning: Updating document variables before converting doesn't work "
                     "when 'powerpointconverter_shellexecute' is set to False")
        return doc_vars

    def modify_document_variable_name(self, old_doc_var_name, new_doc_var_name):
        num_modified_vars = 0
        if self.get_conf_param("powerpointconverter_shellexecute", False):
            shapes = []
            for slide in self.office_doc_obj.Slides:
                shapes.extend(slide.Shapes)
            for design in self.office_doc_obj.Designs:
                shapes.extend(design.SlideMaster.Shapes)
                for layout in design.SlideMaster.CustomLayouts:
                    shapes.extend(layout.Shapes)
            for shape in shapes:
                if shape.HasTextFrame == -1:  # MsoTriState.msoTrue
                    name = shape.Tags.Item("cdb_docvar")
                    if name == old_doc_var_name:
                        shape.Tags.Add("cdb_docvar", new_doc_var_name)
                        num_modified_vars += 1
        else:
            # For PowerPoint updating the document variables doesn't work
            # when starting PowerPoint as a service process!
            self.log("***ERROR***: Modifying document variable names doesn't work for PowerPoint "
                     "files when 'powerpointconverter_shellexecute' is set to False!")
        return num_modified_vars

    def cleanup(self):
        try:
            self.office_doc_obj.Saved = True  # close without ever asking to save changes
            self.office_doc_obj.Close()
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
        # Kill PowerPoint Process
        self.kill_app("POWERPNT.EXE")


class PowerPoint2K7Converter(PowerPointConverterBase, pdfconverter.O2K7PDFConverter):
    """
    PowerPoint 2007 built-in PDF converter
    """

    def __init__(self, filename, **kwargs):
        super(PowerPoint2K7Converter, self).__init__(filename, **kwargs)

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
        self.office_doc_obj.ExportAsFixedFormat(
            Path=filename,
            FixedFormatType=win32com.client.constants.ppFixedFormatTypePDF,
            Intent=win32com.client.constants.ppFixedFormatIntentPrint,
            UseISO19005_1=self.get_conf_param("powerpointconverter_create_pdf_a", False),
            PrintRange=None)
