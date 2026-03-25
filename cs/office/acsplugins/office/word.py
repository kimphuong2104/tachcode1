#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module word

This is the documentation for the word module.
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


class WordConverterBase(object):
    """
    Base class for MS-Word converters
    """

    __conversions__ = ['.doc', '.docm', '.docx', '.dot', '.dotm', '.dotx',
                       '.htm', '.html', '.rtf', '.tml', '.txt']
    __application_name__ = "MS-Word"

    # minimum required word and type library versions
    __application_version_str__ = "Word 2007"
    __application_version__ = 12
    __tlb_clsid__ = "{00020905-0000-0000-C000-000000000046}"
    __tlb_lcid__ = 0
    __tlb_major_version__ = 8
    __tlb_minor_version__ = 4

    def __init__(self, filename, **kwargs):
        super(WordConverterBase, self).__init__(filename, **kwargs)

        try:
            self.conversion_timeout = self.conf_dict["wordconverter_conversion_timeout"]
        except Exception:
            pass
        try:
            self.window_timeout = self.conf_dict["wordconverter_window_timeout"]
        except Exception:
            pass
        # Dialog robot configuration
        if self.window_timeout != 0:
            self.application_name = self.get_conf_param("wordconverter_application_name", "")
            self.auto_confirmations = self.get_conf_param("wordconverter_dialog_confirmations", {})

    def setup_application(self, application):
        if not self.get_conf_param("wordconverter_shellexecute", False):
            application.Visible = self.get_conf_param("wordconverter_visible", False)
        application.DisplayAlerts = 0

    def open_doc(self):
        import win32com.client
        # first kill running word processes
        self.kill_app("WINWORD.EXE")
        results = self.callback_customizing("open_source_file")
        if any((r is True) for r in results):
            self.log("open_doc: Customizing signaled that it already opened the file")
        else:
            if self.get_conf_param("wordconverter_shellexecute", False):
                self.office_app_obj, self.office_doc_obj = self.open_office_file_indirectly(
                    self.filename, "Word.Application", "ActiveDocument")
            else:
                self.office_app_obj = win32com.client.DispatchEx('Word.Application')
                self.office_app_obj.AutomationSecurity = self.get_conf_param(
                    "wordconverter_AutomationSecurity", 3)
                self.setup_application(self.office_app_obj)
                self.office_doc_obj = self.office_app_obj.Documents.Open(
                    self.filename, False, False, False)
                self.office_doc_obj.MapPaperSize = self.get_conf_param(
                    "wordconverter_MapPaperSize", False)
                # Set Automation security lebvel back to default as suggested from Microsoft
                # https://learn.microsoft.com/en-us/office/vba/api/
                # word.application.automationsecurity
                self.office_app_obj.AutomationSecurity = 1

    def get_document_variables(self):
        doc_vars = {}
        for var in self.office_doc_obj.Variables:
            name = var.Name
            if self.is_reading_document_variable(name):
                doc_vars[name] = None
        return doc_vars

    def modify_document_variable_name(self, old_doc_var_name, new_doc_var_name):
        num_modified_vars = 0
        old_var = None
        for var in self.office_doc_obj.Variables:
            name = var.Name
            if name == old_doc_var_name:
                old_var = var
                break
        if old_var:
            old_value = old_var.Value
            old_var.Delete()
            new_var = self.office_doc_obj.Variables.Item(new_doc_var_name)
            new_var.Value = old_value
        all_fields = []
        for story_range in self.office_doc_obj.StoryRanges:
            for field in story_range.Fields:
                all_fields.append(field)
            next_story_range = story_range.NextStoryRange
            while next_story_range:
                for field in next_story_range.Fields:
                    all_fields.append(field)
                next_story_range = next_story_range.NextStoryRange
            if story_range.ShapeRange:
                for shape_range in story_range.ShapeRange:
                    if shape_range.Type not in [11, 13]:  # msoLinkedPicture=11, msoPicture=13
                        if shape_range.TextFrame and shape_range.TextFrame.HasText:
                            for field in shape_range.TextFrame.ContainingRange.Fields:
                                all_fields.append(field)
        for field in all_fields:
            if old_doc_var_name in field.Code.Text:
                field.Code.Text = field.Code.Text.replace(old_doc_var_name, new_doc_var_name)
                num_modified_vars += 1
        return num_modified_vars

    def cleanup(self):
        try:
            self.office_app_obj.Activate()
        except Exception:
            pass
        try:
            self.office_doc_obj.Close(0)  # 0 ==> Word.WdSaveOptions.wdDoNotSaveChanges
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
        wordtmpfile = os.path.join(self.workdir, '~$' + self.basename[2:] + self.suffix)
        if (os.path.exists(wordtmpfile)):
            try:
                os.remove(wordtmpfile)
            except Exception:
                pass

    def handle_timeout(self):
        # Kill Word Process
        self.kill_app("WINWORD.EXE")


class Word2K7Converter(WordConverterBase, pdfconverter.O2K7PDFConverter):
    """
    Word 2007 built-in PDF converter
    """

    def __init__(self, filename, **kwargs):
        super(Word2K7Converter, self).__init__(filename, **kwargs)

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
        # Include document markups into PDF ?
        WdExportItem = win32com.client.constants.wdExportDocumentContent
        if self.get_conf_param("wordconverter_show_markups", 0):
            WdExportItem = win32com.client.constants.wdExportDocumentWithMarkup
        self.office_doc_obj.ExportAsFixedFormat(
            OutputFileName=self.targetfile,
            ExportFormat=win32com.client.constants.wdExportFormatPDF,
            OpenAfterExport=False,
            OptimizeFor=win32com.client.constants.wdExportOptimizeForPrint,
            Range=win32com.client.constants.wdExportAllDocument,
            From=1, To=1,
            Item=WdExportItem,
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=win32com.client.constants.wdExportCreateHeadingBookmarks,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=self.get_conf_param("wordconverter_create_pdf_a", False))
