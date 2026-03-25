#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module pdfconverter

This is the documentation for the pdfconverter module.
"""

from __future__ import unicode_literals

import ctypes
import io
import os
import sys
import threading
import time

import six

if six.PY2:  # noqa
    import thread
else:
    import _thread as thread

from cdb import CADDOK, misc
from cdb.objects.core import ByID
from cdb.sig import emit

from cs.office.documentvariables import DocumentVariables

if sys.platform == "win32":
    # don't order imports below alphabetically!
    import win32ui
    import win32com.client
    import win32gui
    import win32con
    import win32api
    import win32process
    from pywin.dialogs.status import ThreadedStatusProgressDialog
    from cs.office.acsplugins.office.taskutil import terminate_process

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Return Codes
kSuccess = 0
kConfigurationError = 10
kErrorCreatingPostScript = 20
kErrorPostScriptFileMissing = 30
kErrorGhostScript = 40
kErrorTimeOut = 50
kErrorFileTypeNotSupported = 60
kErrorConfigurationFileNotFound = 70
kErrorO2K7AddinFailed = 80

# Error Descriptions
__error_desc = {
    kConfigurationError: "Mandatory configuration parameter missing or syntax error in "
    "configuration file.",
    kErrorCreatingPostScript: (
        "Postscript file could not be created. The document"
        "could not be opened and printed with "
        "it's corresponding application."
    ),
    kErrorPostScriptFileMissing: "PDF creation not possible because the Postscript "
    "file is missing.",
    kErrorGhostScript: "GhostScript Error",
    kErrorTimeOut: (
        "Conversion discarded by timeout. Possible reasons are application "
        "specific dialogs that have been displayed during the conversion. "
        "For huge documents the conversion timeout parameter may be to "
        "small."
    ),
    kErrorFileTypeNotSupported: "Unable to convert the specified file to pdf. The file"
    "type is not supported.\n",
    kErrorConfigurationFileNotFound: "Configuration file not found",
    kErrorO2K7AddinFailed: "Failed converting to PDF directly via Office.",
}


class TerminationFailure(Exception):
    pass


def get_error_desc(code):
    if code in __error_desc:
        return __error_desc[code]
    else:
        return ""


class ConverterFactory(object):
    def createConverter(
        self, filename, cfgfile=None, dstfname=None, log=None, job=None
    ):
        (basename, suffix) = os.path.splitext(os.path.basename(filename))
        suffix = suffix.lower()

        # setup and read configuration file
        if not cfgfile:
            # look for configuration file in CADDOK_BASE\etc
            cfgfilename = "pdfconverter.conf"
            cfgfile = os.path.join(CADDOK.BASE, "etc", cfgfilename)
            if not os.path.exists(cfgfile):
                # use standard configuration file from CADDOK_HOME
                cfgfile = os.path.join(os.path.dirname(__file__), cfgfilename)
        misc.log(5, "PDFConverter::init: Using configuration file: '%s'" % cfgfile)
        conf_dict = {}
        try:
            assert isinstance(cfgfile, six.text_type)
            with io.open(cfgfile, "r", encoding="utf_8_sig") as cfg:
                exec(cfg.read(), globals(), conf_dict)
        except Exception:
            misc.log_traceback(
                "PDFConverter::init: " "Error reading configuration file '%s'" % cfgfile
            )
            return

        if dstfname:
            conf_dict["dstfname"] = dstfname

        conf_dict["log"] = log
        conf_dict["job"] = job

        if sys.platform == "win32":
            from cs.office.acsplugins.office import GetConverter

        converter = GetConverter(suffix)
        if converter is None:
            misc.log(
                5, "ConverterFactory: No converter found for file suffix '%s'" % suffix
            )
        else:
            misc.log(
                5,
                "ConverterFactory: Using '%s' for file suffix '%s'"
                % (converter, suffix),
            )
            return converter(filename, **conf_dict)


class PDFConverterBase(object):
    """
    Base class for all pdf converters
    """

    # Definition of the minimum required application and type library version.
    # To be specified by concrete converter implementations.
    __application_version__ = None
    __application_version_str__ = None
    __tlb_major_version__ = None
    __tlb_minor_version__ = None
    __tlb_clsid__ = None
    __tlb_lcid__ = None

    def __init__(self, filename, **kwargs):
        self.valid = 1
        self.timeout = False
        self.conf_dict = kwargs

        # COM objects
        self.office_app_obj = None
        self.office_doc_obj = None

        # optional additional logging (e.g. for acs/dcs)
        self.log = kwargs.get("log")

        # For compatibility reasons expect that the job param might be None
        self.job = kwargs.get("job")

        # build filenames
        self.filename = filename
        (self.basename, self.suffix) = os.path.splitext(os.path.basename(filename))
        self.workdir = os.path.dirname(filename)
        self.targetfile = kwargs.get(
            "dstfname", os.path.join(self.workdir, self.basename) + ".pdf"
        )
        misc.log(5, "PDFConverter::init:Working Directory: '%s'" % self.workdir)
        misc.log(5, "PDFConverter::init:File to convert: '%s'" % self.filename)
        misc.log(5, "PDFConverter::init:Converted PDF file: '%s'" % self.targetfile)

        # Dialog robot settings
        self.window_timeout = self.get_conf_param("default_window_timeout", 0)
        self.auto_confirmations = {}  # converter specific settings
        # Conversion Timeout
        self.conversion_timeout = self.get_conf_param("default_conversion_timeout", 0)
        # Debugging
        self.delete_temporary_files = self.get_conf_param("delete_temporary_files", 1)
        self.ensure_type_library()

    def log_doubled(self, msg):
        """Writes to global acs log and to local job log aswell"""
        misc.log(7, msg)
        if hasattr(self, "log") and self.log:
            self.log(msg + "\n")

    def get_conf_param(self, attr, default=None):
        if attr in self.conf_dict:
            return self.conf_dict[attr]
        elif default is not None:
            misc.log(
                1,
                "PDFConverter::get_conf_param: "
                "Parameter '%s' not found in configuration file. Using default value '%s'."
                % (attr, default),
            )
            return default
        else:
            misc.log_error(
                "PDFConverter::get_conf_param: "
                "Mandatory configuration parameter '%s' not defined "
                "in configuration file. "
                "Setting converter invalid." % (attr)
            )
            self.valid = 0
            return None

    @classmethod
    def ensure_type_library(cls):
        if (
            cls.__tlb_clsid__ is not None
            and cls.__tlb_lcid__ is not None
            and cls.__tlb_major_version__ is not None
            and cls.__tlb_minor_version__ is not None
        ):

            mod = win32com.client.gencache.EnsureModule(
                cls.__tlb_clsid__,
                cls.__tlb_lcid__,
                cls.__tlb_major_version__,
                cls.__tlb_minor_version__,
            )
            if mod is None:
                misc.log_error(
                    "Unable to build required type library for %s (%s):\n"
                    "  clsid: %s\n"
                    "  lcid: %s\n"
                    "  major version: %s\n"
                    "  minor version: %s\n"
                    "Please check the installed office version (at least %s is required) and "
                    "ensure, that the windows user, who is "
                    "running the conversion process, has write access to the cache directory for "
                    "generated type libraries: %s"
                    % (
                        cls.__application_version_str__,
                        cls.__application_version__,
                        cls.__tlb_clsid__,
                        cls.__tlb_lcid__,
                        cls.__tlb_major_version__,
                        cls.__tlb_minor_version__,
                        cls.__application_version_str__,
                        win32com.client.gencache.GetGeneratePath(),
                    )
                )

    def __wait(self):
        self.timeout = False
        time_waited = 0

        if not self.window_timeout:
            if not self.conversion_timeout:
                # no timeout and no dialog robot
                return
            else:
                waittime = self.conversion_timeout
        else:
            waittime = self.window_timeout

        self.condition.acquire()
        try:
            while not self.__ready:
                self.condition.wait(waittime)
                if self.__ready:
                    break
                time_waited += waittime
                if self.conversion_timeout and time_waited >= self.conversion_timeout:
                    misc.log(
                        5,
                        "PDFConverter::__wait: Converter timeout reached: %s Seconds "
                        "- Conversion will be discarded" % self.conversion_timeout,
                    )
                    self.timeout = True
                    self.handle_timeout()
                    break
                elif self.window_timeout:
                    misc.log(
                        9, "PDFConverter::__wait: Trying confirmation of known Dialogs"
                    )
                    self.__ConfirmDialogs()
                    self.dialogs_confirmed()
        finally:
            self.condition.release()

    def start_monitoring_thread(self):
        self.__ready = False
        self.condition = threading.Condition()
        thread.start_new_thread(self.__wait, ())

    def stop_monitoring_thread(self):
        self.condition.acquire()
        self.__ready = True
        self.condition.notify()
        self.condition.release()

    def setup_application(self, application):
        pass

    def find_window_by_title(self, window_title):
        def enumWindowsCallback(hwnd, params):
            try:
                wnd_title = win32gui.GetWindowText(hwnd)
                if wnd_title.find(params["window_title"]) >= 0:
                    params["window_handle"] = hwnd
            except Exception as ex:
                params["error"] = "EnumWindows: %s" % ex
            return True

        params = {"window_title": window_title, "window_handle": None, "error": None}
        win32gui.EnumWindows(enumWindowsCallback, params)
        return (params["window_handle"], params["error"])

    def get_office_app(self, application_com_name):
        ret = None
        tries = 30
        dlg = None
        hwnd_office = None
        try:
            while not ret:
                tries -= 1
                time.sleep(0.5)
                try:
                    self.log_doubled("Calling GetActiveObject..")
                    ret = win32com.client.GetActiveObject(application_com_name)
                    self.log_doubled(".. GetActiveObject called!")
                    self.log_doubled("Office COM object 'Visible'=%s" % ret.Visible)
                    self.setup_application(ret)
                    self.log_doubled("setup_application() successfully called")
                except Exception as ex:
                    ret = None
                    if not tries:
                        self.log_doubled(
                            "Aborting GetActiveObject loop with: %s" % repr(ex)
                        )
                        raise ex
                    self.log_doubled(
                        "Office not accessible by plugin yet: %s" % repr(ex)
                    )

                    # At least wait until the Office window can be found
                    if not hwnd_office:
                        hwnd_office, error = self.find_window_by_title(
                            self.application_name
                        )
                        if not hwnd_office:
                            self.log_doubled("Office window not yet found: %s" % error)
                        continue

                    # https://support.microsoft.com/de-de/help/238610/
                    # getobject-or-getactiveobject-cannot-find-a-running-office-application
                    try:
                        # Create a focused dialog in order to inactivate the office window
                        if not dlg:
                            dlg = ThreadedStatusProgressDialog(
                                "MSO Conversion Helper Dialog", "Converting.."
                            )
                            self.log_doubled("Focus helper dialog created")

                        # https://github.com/pywinauto/pywinauto/issues/117
                        # When we directly try a "dlg.SetForegroundWindow()" right now, as suggested
                        # by Microsoft, then we often get a "'SetForegroundWindow', 'No error
                        # message is available'". Thus use an additional hack from
                        # pywinauto/controls/HwndWrapper.py
                        hwnd_cur_foreground = win32gui.GetForegroundWindow()
                        cur_fore_wnd_title = win32gui.GetWindowText(hwnd_cur_foreground)
                        self.log_doubled(
                            "ForegroundWindow title: %s" % cur_fore_wnd_title
                        )
                        cur_fore_thread = win32process.GetWindowThreadProcessId(
                            hwnd_cur_foreground
                        )[0]
                        if cur_fore_thread != dlg.threadid:
                            office_wnd_title = win32gui.GetWindowText(hwnd_office)
                            self.log_doubled(
                                "Office window title: %s" % office_wnd_title
                            )
                            office_thread = win32process.GetWindowThreadProcessId(
                                hwnd_office
                            )[0]
                            win32process.AttachThreadInput(
                                dlg.threadid, office_thread, 1
                            )
                            dlg.SetForegroundWindow()
                            self.log_doubled("Focus helper dialog set to foreground")
                        else:
                            try:
                                win32gui.SetForegroundWindow(hwnd_office)
                                self.log_doubled("Office window set to foreground")
                            except Exception as ex:
                                self.log_doubled(
                                    "Error setting Office window to foreground: %s"
                                    % repr(ex)
                                )

                    except Exception as ex:
                        self.log_doubled(
                            "Error handling focus helper dialog: %s" % repr(ex)
                        )
        finally:
            if dlg:
                try:
                    dlg.Close()
                except Exception as ex:
                    misc.log_error("Error closing focus helper dialog: %s" % ex)
        return ret

    def open_office_file_indirectly(
        self, file_path, application_com_name, ret_com_object
    ):
        os.startfile('"%s"' % os.path.normpath(file_path))
        ret_application = self.get_office_app(application_com_name)
        ret_object = None
        tries = 10
        while not ret_object:
            tries -= 1
            time.sleep(0.3)
            try:
                ret_object = getattr(ret_application, ret_com_object)
            except Exception as ex:
                if not tries:
                    raise ex
        if ret_object.FullName.lower() != file_path.lower():
            raise Exception(
                "Currently focused file (%s) differs from source file (%s)"
                % (ret_object.FullName.lower(), file_path.lower())
            )
        return ret_application, ret_object

    def get_document_variables(self):
        return {}

    def modify_document_variable_name(self, old_doc_var_name, new_doc_var_name):
        self.log(
            "***Warning***: No implementation for updating document variable names"
        )
        return 0  # num_modified_vars

    def is_reading_document_variable(self, name):
        if name.startswith("cdb."):
            access_mode = name.split(".")[1]
            return "r" in access_mode
        return False

    def update_document_variables(self):
        """Returns true if document variables are found and updated."""
        from cdb.objects.cdb_file import CDB_File

        obj = None
        if self.cdb_object_id:
            obj = ByID(self.cdb_object_id)
            if isinstance(obj, CDB_File):
                if obj.cdb_lock:
                    self.log_doubled("File is locked by '%s', thus not updating any document "
                                     "variables" % obj.cdb_lock)
                    return False
                obj = obj.ParentObject
        if not obj:
            if self.doc_z_nummer and self.doc_z_index:
                from cs.documents import Document

                obj = Document.ByKeys(
                    z_nummer=self.doc_z_nummer, z_index=self.doc_z_index
                )
        if not obj:
            # Currently this expectedly happens for PowerReport PDFs
            self.log_doubled(
                "Not found any object keys, thus not updating any document variables"
            )
            return False

        if getattr(obj, "vorlagen_kz", None) == 1:
            self.log_doubled(
                "Object is a template document, "
                "thus not updating any document variables"
            )
        else:
            # fake officelink component context object
            ctx = lambda: None  # noqa
            ctx.log = self.log_doubled
            ctx.object = {attr: obj[attr] for attr in obj.KeyNames()}
            ctx.object["cdb_classname"] = obj.GetClassname()
            ctx.document_variables = self.get_document_variables()

            if ctx.document_variables:
                emit("officelink_metadata_read")(self, ctx)
            # again check if ctx.document_variables isn't empty to allow fully disabling
            # following functionality by clearing ctx.document_variables in the signal above
            if ctx.document_variables:
                DocumentVariables.auto_fill(ctx, self.conversion_user_login)

                DocumentVariables.write_metadata_xml(
                    ctx, self.filename + ".metadata.cdbxml"
                )

                result = False
                office_addin = None
                try:
                    # Get the right plugin object e.g.: 'CONTACT MS Office Link (MS-Word)'
                    # from the office application
                    if self.application_name == "Word":
                        from cs.office.automation.wordwsjobexec import WordWSJobExec

                        office_addin = WordWSJobExec().get_office_addin(
                            uninitializeCOM=False
                        )
                    elif self.application_name == "Excel":
                        from cs.office.automation.excelwsjobexec import ExcelWSJobExec

                        office_addin = ExcelWSJobExec().get_office_addin(
                            uninitializeCOM=False
                        )
                    elif self.application_name == "Visio":
                        from cs.office.automation.visiowsjobexec import VisioWSJobExec

                        office_addin = VisioWSJobExec().get_office_addin(
                            uninitializeCOM=False
                        )
                    elif self.application_name == "PowerPoint":
                        from cs.office.automation.powerpointwsjobexec import (
                            PowerPointWSJobExec,
                        )

                        office_addin = PowerPointWSJobExec().get_office_addin(
                            uninitializeCOM=False
                        )
                    elif self.application_name == "MSProject":
                        from cs.office.automation.msprojectwsjobexec import (
                            MSProjectWSJobExec,
                        )

                        office_addin = MSProjectWSJobExec().get_office_addin(
                            uninitializeCOM=False
                        )

                    # Update the CDBDocumentVariables with the call of the function
                    # updateCDBDocumentVariablesDCS at the right office plugin
                    if office_addin is not None:
                        result = office_addin.updateCDBDocumentVariablesDCS()
                except Exception as ex:
                    self.log_doubled(
                        "ERROR: 'CONTACT MS Office Link' must be installed for updating document "
                        "variables when converting to PDF. "
                        "If it already is installed and activated(!), please "
                        "check the 'CONTACT MS Office Link' log for further informations.\n"
                        "Raised Exception: %s" % repr(ex)
                    )
                if result:
                    misc.log(
                        7,
                        "'CONTACT MS Office Link'.updateCDBDocumentVariablesDCS succeeded",
                    )
                    return True
                else:
                    raise Exception(
                        "'CONTACT MS Office Link'.updateCDBDocumentVariablesDCS failed"
                    )
        return False

    def kill_app(self, name):
        if terminate_process(name) == 2:
            raise TerminationFailure("Failed to terminate {}".format(name))

    def handle_timeout(self):
        # to be implemented by concrete converter
        pass

    def dialogs_confirmed(self):
        # to be implemented by concrete converter
        pass

    # --------------Dialog Robot -----------------

    def __ConfirmDialogs(self):
        for windowname in self.auto_confirmations.keys():
            windowname, windowtexts = (
                (windowname, None)
                if isinstance(windowname, six.string_types)
                else windowname
            )
            try:
                Window = win32ui.FindWindow(None, windowname)
                if windowtexts:
                    # don't check the parent window (below) in this case, since we need a way
                    # finding target windows w/o checking parent windows (e.g. VBA message boxes
                    # don't have a parent window sometimes!)
                    _windowtexts = (
                        list(windowtexts)
                        if isinstance(windowtexts, tuple)
                        else [windowtexts]
                    )
                    _ChildWindowTexts = self.GetChildWindowTexts(Window)
                    if not all([txt in _ChildWindowTexts for txt in _windowtexts]):
                        # window is not the expected one
                        continue
                else:
                    # check title of parent window
                    pWindow = Window.GetParent()
                    if pWindow:
                        pwindow_text = pWindow.GetWindowText()
                        if pwindow_text.find(self.application_name) == -1:
                            # parent window is not the expected one
                            continue
                    else:
                        # no parent window found, do not confirm/close the dialog
                        continue
                self.__ConfirmOrCloseDialog(Window, windowname, windowtexts)
                break
            except Exception:
                continue

    def __ConfirmOrCloseDialog(self, Window, windowname, windowtexts):
        key = windowname if not windowtexts else (windowname, windowtexts)
        default_button = self.auto_confirmations[key]
        if default_button == "":
            # Close Dialog, no default Button specified
            self.__CloseDialog(Window)
        else:
            # Confirm dialog with configured default button
            self.__ConfirmDialog(Window, default_button)

    def __ConfirmDialog(self, Window, BName, Delay=1):
        Caption = Window.GetWindowText()
        # Find button with name BName in Window and simulate a button activation.
        try:
            Button = win32ui.FindWindowEx(Window, None, "Button", BName)
        except Exception:
            misc.log(
                8,
                "PDFConverter::__ConfirmDialog: "
                "Unable to confirm dialog '%s' with simulated button click. "
                "Button '%s' not found." % (Window.GetWindowText(), BName),
            )
            return
        # Simulate button press to confirm window
        hButton = Button.GetSafeHwnd()
        if win32gui.IsWindowVisible(hButton):
            (x, y, _x, _y) = win32gui.GetWindowRect(hButton)
            x = 65536 * x / ctypes.windll.user32.GetSystemMetrics(0) + 1
            y = 65536 * y / ctypes.windll.user32.GetSystemMetrics(1) + 1
            MOUSEEVENTF_MOVE = 0x0001  # mouse move
            MOUSEEVENTF_ABSOLUTE = 0x8000  # absolute move
            MOUSEEVENTF_MOVEABS = MOUSEEVENTF_MOVE + MOUSEEVENTF_ABSOLUTE
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVEABS, x + 5, y + 5, 0, 0)
            MOUSEEVENTF_LEFTDOWN = 0x0002  # left button down
            MOUSEEVENTF_LEFTUP = 0x0004  # left button up
            MOUSEEVENTF_CLICK = MOUSEEVENTF_LEFTDOWN + MOUSEEVENTF_LEFTUP
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_CLICK, 0, 0, 0, 0)
        else:
            # this approach does not always work (e.g. on Outlook security dialogs)
            Button.SendMessage(win32con.BM_SETSTATE, 1, 0)
            time.sleep(Delay)  # Window should show up at least for a second.
            idButton = Button.GetDlgCtrlID()
            Window.SendMessage(
                win32con.WM_COMMAND,
                win32api.MAKELONG(idButton, win32con.BN_CLICKED),
                hButton,
            )
        misc.log(
            5,
            "PDFConverter::__ConfirmDialog: "
            "Dialog '%s' confirmed with simulated '%s' button click."
            % (Caption, BName),
        )

    def __CloseDialog(self, Window):
        misc.log(
            5,
            "PDFConverter::__ConfirmDialog: "
            "Dialog '%s' closed by sending WM_CLOSE message."
            % (Window.GetWindowText()),
        )
        Window.SendMessage(win32con.WM_CLOSE)

    def GetChildWindowTexts(self, Window):
        """Get the text of each child window and return all texts concatenated."""

        def _winEnumCallback(hwnd, texts):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd)
                    if text:
                        texts.append(text)
            except Exception as ex:
                misc.log_error(ex)

        texts = []
        try:
            win32gui.EnumChildWindows(Window.GetSafeHwnd(), _winEnumCallback, texts)
        except Exception as ex:
            misc.log_error(ex)
        return " ".join(texts)

    def callback_customizing(self, signal, **kwargs):
        """
        Wrapper for customizing entry points without having to overwrite the whole plug-in.
        Currently supported OfficeLink DCS signals:
        - 'officelink_dcs_open_source_file':
            Can be used to open specific file types (e.g. Excel XML files) in a different way.
            Must return 'True' if the callee decides to open the office file, else the base
            method tries to opens it.
        - 'officelink_dcs_before_save_as_pdf':
            Can be used to modify the office file before it gets saved as PDF,
            for example, for adding mail header infos into mail bodies.
            Can also be used to additionally save and store the office file in different PDF
            versions, for example, for saving Excel files with different regional settings.
            Must return 'True' if the callee decides to also save as the primary target PDF file,
            which automatically gets stored when the conversion job finshes, else the base method
            tries to save as primary target PDF file.
        """
        signal = "officelink_dcs_%s" % signal
        self.log_doubled("Calling customizing callback: %s" % signal)
        result = emit(signal)(self, **kwargs)
        self.log_doubled("Customizing callback returned: %s" % result)
        return result

    def store_additional_file(self, filename, cdbf_type, replace_original=False):
        """
        For storing additional conversion results, other than the main secondary PDF file
        (e.g. PDFs with differing regional settings).
        """
        if not hasattr(self, "job") or not self.job:
            raise Exception(
                "The plug-in is missing the converter 'job' object. Probably due to "
                "an outdated 'HandleJob' method in the customizing of this plug-in."
            )
        self.job.store_file(self.job.get_file(), filename, cdbf_type, replace_original)

    def store_source_file_modifications(self):
        """
        For instance called, after updating document variables. This method needs to be called
        before storing any additional files via 'store_additional_file', because by default
        updating the source file object always results in removing all secondary conversion files.
        """
        self.store_additional_file(
            self.filename, self.job.get_file().cdbf_type, replace_original=True
        )


class O2K7PDFConverter(PDFConverterBase):
    """
    Base class for Office 2007 built-in PDF converters
    """

    def __init__(self, filename, **kwargs):
        super(O2K7PDFConverter, self).__init__(filename, **kwargs)

    def convert(
        self, znum=None, zidx=None, cdb_object_id=None, conversion_user_login=None
    ):
        self.doc_z_nummer = znum
        self.doc_z_index = zidx
        self.cdb_object_id = cdb_object_id
        self.conversion_user_login = conversion_user_login
        # start monitoring thread
        self.start_monitoring_thread()
        result = self.create_pdf()
        # stop monitoring thread
        self.stop_monitoring_thread()
        if not result:
            if self.timeout:
                return kErrorTimeOut
            else:
                misc.log_error(
                    "PDFConverter::convert: "
                    "Failed converting to PDF directly via Office."
                )
                return kErrorO2K7AddinFailed
        return kSuccess


def compareBookmarkStartPosition(bookmark1, bookmark2):
    return bookmark1.compareStartPosition(bookmark2)


def pdfmarkstring(s):
    s = s.replace("\\", "\\\\")
    s = s.replace("(", "\\(")
    s = s.replace(")", "\\)")
    s = s.replace("]", "\\]")
    s = s.replace("[", "\\[")
    s = s.strip()
    return s


class Bookmark:
    def __init__(self, count, page, title, level, start):
        self.count = count
        self.page = page
        self.title = title
        if isinstance(self.title, six.text_type):
            replacement_char = "?"
            # remember occurences of replacement character
            counter = 0
            indexes = []
            for i in six.moves.range(len(self.title)):
                if self.title[i] == replacement_char:
                    indexes.append(i)
                counter += 1
            # encode
            self.title = self.title.encode("latin1", "replace").decode("latin-1")
            # replace replacement characters by whitespace
            new_title = ""
            for i in six.moves.range(len(self.title)):
                if self.title[i] == replacement_char and i not in indexes:
                    new_title += " "
                else:
                    new_title += self.title[i]
            self.title = new_title
        self.title = pdfmarkstring(self.title)
        if len(self.title) >= 128:
            self.title = self.title[:124] + " ..."
        self.level = level
        self.start = start

    def compareStartPosition(self, bookmark):
        if self.start < bookmark.start:
            return -1
        elif self.start > bookmark.start:
            return 1
        elif self.start == bookmark.start:
            return 0

    def to_ps(self, page_offset):
        result = "[ "
        if self.count > 0:
            result += "/Count -%s " % (self.count)
        result += "/Title (%s) /Page %s /View [ /Fit ] " "/OUT pdfmark\n" % (
            self.title,
            self.page + page_offset,
        )
        return result


class MergeConverter:
    def __init__(self, cfgfile, target_pdf, files_to_convert, znum_zidx_tuples=None):
        self.cfgfile = cfgfile
        self.target_pdf = target_pdf
        self.files_to_convert = files_to_convert
        self.znum_zidx_tuples = znum_zidx_tuples

        # build filenames
        (self.target_basename, self.target_suffix) = os.path.splitext(
            os.path.basename(target_pdf)
        )
        self.workdir = os.path.dirname(target_pdf)
        self.psfile = os.path.join(
            self.workdir,
            "%s_bookmarks_%s.ps" % (self.target_basename, int(round(time.time()))),
        )
        self.psprintfile = os.path.join(
            self.workdir, "%s%s.ps" % (self.target_basename, int(round(time.time())))
        )
        misc.log(5, "MergeConverter::init:Working Directory: '%s'" % self.workdir)
        misc.log(5, "MergeConverter::init:Target PDF File: '%s'" % self.target_pdf)
        misc.log(
            5, "MergeConverter::init:Printed Postscript file '%s' " % self.psprintfile
        )
        misc.log(
            5,
            "MergeConverter::init:Postscript file for Bookmarks and Links: '%s'"
            % self.psfile,
        )

    # returns the number of pages contained in file psfile and
    # corrects the page numbers: (%%[Page: x]%%)
    def __update_pages(self, psfile):
        pages = 0
        new_ps_filename = os.path.join(
            self.workdir,
            "%s_tmp_%s.ps" % (self.target_basename, int(round(time.time()))),
        )
        assert isinstance(new_ps_filename, six.text_type)
        with io.open(new_ps_filename, "wb") as new_ps:
            assert isinstance(psfile, six.text_type)
            with io.open(psfile, "rb") as ps:
                for line in ps.readlines():
                    index = line.find("(%%[Page:")
                    if index != -1:
                        endindex = line.find("]%%", index)
                        if endindex != -1:
                            pages += 1
                            line = line.replace(
                                line[index:endindex], "(%%[Page: %s" % (pages)
                            )
                    new_ps.write(line)
        os.remove(psfile)
        os.rename(new_ps_filename, psfile)
        return pages

    def __append_doc_view(self, psfile):
        result_lines = [
            "[ /PageMode /UseOutlines",
            "  /Page  1",
            "  /View [/XYZ null null null]",
            "/DOCVIEW pdfmark",
        ]
        assert isinstance(psfile, six.text_type)
        with io.open(psfile, "ab") as ps:
            for line in result_lines:
                ps.write(line + "\n")

    def convert(self):
        converterFactory = ConverterFactory()
        page_offset = 0
        file_counter = 0
        for myfile in self.files_to_convert:
            converter = converterFactory.createConverter(myfile, self.cfgfile)
            converter.setup_for_merge_mode(self.psprintfile, self.psfile, page_offset)
            znum_zidx_tuple = None
            if self.znum_zidx_tuples is not None:
                try:
                    znum_zidx_tuple = self.znum_zidx_tuples[file_counter]
                except IndexError:
                    # filename will be used as bookmark text
                    pass
            converter.convert(znum_zidx_tuple[0], znum_zidx_tuple[1])
            page_offset = self.__update_pages(self.psprintfile)
            file_counter += 1
        # append docview to psfile
        self.__append_doc_view(self.psfile)
        # generate pdf from ps file
        converter = converterFactory.createConverter(self.psprintfile, self.cfgfile)
        converter.psfile = self.psfile
        converter.targetfile = self.target_pdf
        converter.convert()


def run_tests(testfilepath=None, cfgfile=None):

    if not testfilepath:
        testfilepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "tests"))
    if not os.path.exists(testfilepath):
        six.print_("Testfile path %s does not exist." % testfilepath)
        return

    # convert each supported file in the directory to PDF
    testfiles = os.listdir(testfilepath)
    for testfile in testfiles:
        convert(os.path.join(testfilepath, testfile), cfgfile)


def convert(
    myfile,
    cfgfile=None,
    znum=None,
    zidx=None,
    dstfname=None,
    log=None,
    cdb_object_id=None,
    conversion_user_login=None,
    job=None,
):
    converterFactory = ConverterFactory()
    converter = converterFactory.createConverter(myfile, cfgfile, dstfname, log, job)
    if converter:
        return converter.convert(znum, zidx, cdb_object_id, conversion_user_login)
    else:
        return kErrorFileTypeNotSupported


if __name__ == "__main__":

    testfilepath = None
    cfgfile = None
    runtests = 0
    filetoconvert = None

    counter = 0
    for arg in sys.argv:
        if arg == "-runtests":
            runtests = 1
        elif arg == "-cfg":
            cfgfile = sys.argv[counter + 1]
        elif arg == "-testfilepath":
            testfilepath = sys.argv[counter + 1]
        elif arg == "-file":
            filetoconvert = sys.argv[counter + 1]
        counter += 1

    if runtests:
        run_tests(testfilepath, cfgfile)
    else:
        retVal = convert(filetoconvert, cfgfile)
        if int(retVal) != kSuccess:
            error_desc = get_error_desc(int(retVal))
            six.print_(
                "Conversion failed with return code %s: %s\n" % (retVal, error_desc)
            )
