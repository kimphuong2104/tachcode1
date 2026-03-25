#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module visio

This is the documentation for the visio module.
"""

from __future__ import unicode_literals

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import sys
import traceback

from cdb import misc

if sys.platform == "win32":
    from cs.office.acsplugins.office import pdfconverter


class VisioConverterBase(object):
    """Base class for MS-Visio converters"""

    __application_name__ = "MS-Visio"
    __conversions__ = ['.vdw',  # Visio 2010-
                       '.vdx',  # Visio 2003-2010
                       '.vsd',
                       '.vsdm',  # Visio 2013-
                       '.vsdx',  # Visio 2013-
                       '.vsx',  # Visio 2003-2010
                       '.vss',
                       '.vssm',  # Visio 2013-
                       '.vssx',  # Visio 2013-
                       '.vst',
                       '.vstm',  # Visio 2013-
                       '.vstx',  # Visio 2013-
                       '.vtx']  # Visio 2003-2010

    # minimum required Visio and type library version
    __application_version_str__ = "Visio 2007"
    __application_version__ = 12
    __tlb_clsid__ = "{F1A8DFE4-BC61-48BA-AFDA-96DF10247AF0}"
    __tlb_lcid__ = 0
    __tlb_major_version__ = 1
    __tlb_minor_version__ = 1

    def __init__(self, filename, **kwargs):
        super(VisioConverterBase, self).__init__(filename, **kwargs)

        # overwrite default parameters, if defined
        try:
            self.window_timeout = self.conf_dict["visioconverter_window_timeout"]
        except Exception:
            pass
        try:
            self.conversion_timeout = self.conf_dict["visioconverter_conversion_timeout"]
        except Exception:
            pass
        # Dialog robot configuration
        if self.window_timeout != 0:
            self.application_name = self.get_conf_param("visioconverter_application_name", "")
            self.auto_confirmations = self.get_conf_param("visioconverter_dialog_confirmations", {})

    def setup_application(self, application):
        # Visio always opens up visible, even if started as a service
        application.Visible = self.get_conf_param("visioconverter_visible", False)

    def open_doc(self):
        import win32com.client
        # first kill running Visio processes
        self.kill_app("VISIO.EXE")
        results = self.callback_customizing("open_source_file")
        if any((r is True) for r in results):
            self.log("open_doc: Customizing signaled that it already opened the file")
        else:
            if self.get_conf_param("visioconverter_shellexecute", False):
                self.office_app_obj, self.office_doc_obj = self.open_office_file_indirectly(
                    self.filename, "Visio.Application", "ActiveDocument")
            else:
                self.office_app_obj = win32com.client.DispatchEx('Visio.Application')
                self.setup_application(self.office_app_obj)
                self.office_doc_obj = self.office_app_obj.Documents.Open(self.filename)

    def get_document_variables(self):
        doc_vars = {}
        for page in self.office_doc_obj.Pages:
            for shape in page.Shapes:
                index = 242  # VisSectionIndices.visSectionUser = 242
                if shape.SectionExists(index, 0) != 0:  # VisExistsFlags.visExistsAnywhere = 0
                    section = shape.Section(index)
                    row_count = shape.RowCount(index)
                    row_index = 0
                    inner_break = False
                    while row_index < row_count:
                        cell_count = shape.RowsCellCount(index, row_index)
                        if cell_count == 0:
                            row_index += 1
                            cell_count = shape.RowsCellCount(index, row_index)
                        cell_index = 0
                        while cell_index < cell_count:
                            cell = section(row_index)(cell_index)
                            var_name = cell.FormulaU.replace("\"", "")
                            if var_name.startswith("cdb."):
                                doc_vars[var_name] = None
                                inner_break = True
                                break
                            cell_index += 1
                        if inner_break:
                            break
                        row_index += 1
        return doc_vars

    def modify_document_variable_name(self, old_doc_var_name, new_doc_var_name):
        num_modified_vars = 0
        for page in self.office_doc_obj.Pages:
            for shape in page.Shapes:
                index = 242  # VisSectionIndices.visSectionUser = 242
                if shape.SectionExists(index, 0) != 0:  # VisExistsFlags.visExistsAnywhere = 0
                    section = shape.Section(index)
                    row_count = shape.RowCount(index)
                    row_index = 0
                    inner_break = False
                    while row_index < row_count:
                        cell_count = shape.RowsCellCount(index, row_index)
                        if cell_count == 0:
                            row_index += 1
                            cell_count = shape.RowsCellCount(index, row_index)
                        cell_index = 0
                        while cell_index < cell_count:
                            cell = section(row_index)(cell_index)
                            var_name = cell.FormulaU.replace("\"", "")
                            if var_name == old_doc_var_name:
                                cell.FormulaU = '"%s"' % new_doc_var_name
                                num_modified_vars += 1
                                inner_break = True
                                break
                            cell_index += 1
                        if inner_break:
                            break
                        row_index += 1
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
        # Kill Visio Process
        self.kill_app("VISIO.EXE")


class Visio2K7Converter(VisioConverterBase, pdfconverter.O2K7PDFConverter):
    """Visio 2007 built-in PDF converter"""

    # Note:
    # The visio api constants don't appear in the python type library, thus aren't accessible via
    # win32com.client.constants!

    def __init__(self, filename, **kwargs):
        super(Visio2K7Converter, self).__init__(filename, **kwargs)

    def create_pdf(self):
        try:
            self.open_doc()
            if self.update_document_variables():
                self.store_source_file_changes = True
                self.office_doc_obj.Save()
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
        self.office_doc_obj.ExportAsFixedFormat(
            FixedFormat=1,  # visFixedFormatPDF,
            OutputFileName=filename,
            Intent=1,  # visDocExIntentPrint  (quality of export)
            PrintRange=0,  # visPrintAll (pages to export)
            IncludeDocumentProperties=True)
