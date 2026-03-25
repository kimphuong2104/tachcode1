#!/usr/bin/env python  # pylint: disable=C0302
# -*- python -*- coding: UTF-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     PowerReports.py
# Author:   aki
# Creation: 04.02.08
# Purpose:

# pylint: disable-msg=R0902,R0903,R0904,R0912,R0913,R0914,R0915,W0212,W0201,W0612,W0622,W0102  # noqa
import datetime
import os
import re
import sys
import time
import urllib
import zipfile
from io import StringIO
from io import open as io_open

from cdb import (
    CADDOK,
    auth,
    cdbuuid,
    cmsg,
    ddl,
    i18n,
    misc,
    sqlapi,
    tools,
    transaction,
    typeconversion,
    ue,
    util,
)

try:
    from cdb import client
except ImportError:
    # Seems to be CE 16
    pass
import logging

from cdb import version
from cdb.elink import isCDBPC
from cdb.objects import (
    Class,
    ClassNameBrowser,
    Forward,
    MappedAttributeDescriptor,
    Object,
    Reference_1,
    Reference_Methods,
    Reference_N,
    ReferenceMapping_N,
    ReferenceMethods_1,
    Rule,
)
from cdb.objects.cdb_file import CDB_File
from cdb.objects.core import object_from_handle
from cdb.objects.fields import (
    JoinedAttributeDescriptor,
    MultiLangAttributeDescriptor,
    VirtualAttributeDescriptor,
)
from cdb.objects.org import WithSubject
from cdb.platform.gui import CDBCatalog, I18nCatalogEntry
from cdb.platform.mom import SimpleArguments
from cdb.platform.mom.entities import CDBClassDef
from cdb.typeconversion import from_legacy_date_format
from cs.platform.web import get_root_url
from cs.tools.powerreports import report_sql_tools
from cs.tools.powerreports.utils import _get_error_msg, show_error_msg

fFile = Forward("cdb.objects.cdb_file.CDB_File")
fDialog = Forward("cdb.platform.gui.Dialog")

fXMLSource = Forward(__name__ + ".XMLSource")
fXMLDataProvider = Forward(__name__ + ".XMLDataProvider")
fXMLReport = Forward(__name__ + ".XMLReport")
fXMLReportGrant = Forward(__name__ + ".XMLReportGrant")
fXMLReportTemplate = Forward(__name__ + ".XMLReportTemplate")
fXMLProviderGrant = Forward(__name__ + ".XMLProviderGrant")
fXMLProviderParameter = Forward(__name__ + ".XMLProviderParameter")
fXMLReportParameter = Forward(__name__ + ".XMLReportParameter")

N = "N"
CARD_0 = "0"
CARD_1 = "1"
CARD_0_1 = "0,1"
CARD_N = "N"

DATETIME_MODE_UTC = "UTC"
DATETIME_MODE_LOCAL_TIME = "local time"
DATETIME_MODE_AS_CONFIGURED = "as configured"

REPORT_ID_ATTR = "cdbxml_report_id"
REPORT_ACTION_ATTR = "cdbxml_report_action"
REPORT_FORMAT_ATTR = "cdbxml_report_format"

REPORT_DOWNLOAD = "cdbxml_report_download"
REPORT_OPEN = "cdbxml_report_open"
REPORT_EMAIL = "cdbxml_report_email"

# http://office.microsoft.com/en-us/excel-help/file-formats-that-are-supported-in-excel-HP010014103.aspx  # noqa
SUPPORTED_FILETYPES = [
    ".xlsx",
    ".xlsm",
    ".xlsb",
    ".xltx",
    ".xltm",
    ".xlt",
    ".xls",
    ".xml",
    ".xlam",
    ".xla",
    ".xlw",
]

# https://www.w3.org/TR/xml/#NT-Char
# https://stackoverflow.com/questions/1707890/fast-way-to-filter-illegal-xml-unicode-chars-in-python
invalid_xml_chrs = [
    (0x00, 0x08),
    (0x0B, 0x0C),
    (0x0E, 0x1F),
    (0x7F, 0x84),
    (0x86, 0x9F),
    (0xFDD0, 0xFDDF),
    (0xFFFE, 0xFFFF),
]
if sys.maxunicode >= 0x10000:  # not narrow build
    invalid_xml_chrs.extend(
        [
            (0x1FFFE, 0x1FFFF),
            (0x2FFFE, 0x2FFFF),
            (0x3FFFE, 0x3FFFF),
            (0x4FFFE, 0x4FFFF),
            (0x5FFFE, 0x5FFFF),
            (0x6FFFE, 0x6FFFF),
            (0x7FFFE, 0x7FFFF),
            (0x8FFFE, 0x8FFFF),
            (0x9FFFE, 0x9FFFF),
            (0xAFFFE, 0xAFFFF),
            (0xBFFFE, 0xBFFFF),
            (0xCFFFE, 0xCFFFF),
            (0xDFFFE, 0xDFFFF),
            (0xEFFFE, 0xEFFFF),
            (0xFFFFE, 0xFFFFF),
            (0x10FFFE, 0x10FFFF),
        ]
    )
invalid_xml_char_ranges = [
    "%s-%s" % (chr(low), chr(high)) for (low, high) in invalid_xml_chrs
]
RE_INVALID_XML_CHRS = re.compile("[%s]" % "".join(invalid_xml_char_ranges))

RE_INVALID_XML_SCHEMA_NAME_CHRS = re.compile(r"^\d|\W")
# For Excel any XML attribute name mustn't start with anything else than [a-zA-Z_]
RE_VALID_XML_ATTR_NAME_CHRS = re.compile(r"^[a-zA-Z_]+[a-zA-Z0-9_-]*")

LOG = logging.getLogger(__name__)

# WORKAROUND: Post install update task workaround, remove when E073677 is implemented
table = ddl.Table("cdbxml_report")
if (
    table.hasColumn("cdbxml_rep_exec_type")
    and table.hasColumn("cdbxml_report_action")
    and table.hasColumn("cdbxml_report_format")
):
    query = """SELECT * from cdbxml_report WHERE
cdbxml_rep_exec_type='Server (synchron)'
or cdbxml_rep_exec_type='Server (asynchron)'"""
    rs = sqlapi.RecordSet2(sql=query)
    if rs:
        from cs.tools.powerreports.updates.v15_5_0 import AdjustReportActionAndFormat

        AdjustReportActionAndFormat().run()


def MakeReportURL(
    obj=None, action=None, text_to_display="", report_name=None, provider=None, **kwargs
):
    """
    Create a Report URL

    :param obj: The object for report generation.
                (For context-free reports can be `None` - only works on WebUI)
    :type obj: _ctx.Object
    :param action: (Optional) The action for the object.
                   If `report_name` is specified, the action is defaulted to `cdbxml_excel_report`;
                   otherwise, it fallback to the object default action.
    :type action: str
    :param text_to_display: (Optional) Text for the hyperlink in the Excel report.
                            If not set or empty string, defaulted to object description.
                            If the value is an attribute of the object, the value of the attribute will be used instead.
                            If explicitly set to `None`, the URL will not include the text to display.
    :type text_to_display: str
    :param report_name: Name of the report. (Corresponding to `cdbxml_report.title`)
    :type report_name: str
    :param provider: (Optional) The provider used for getting the parameter `Hyperlinks:Type`; otherwise, `auto` will be used.
    :type provider: str
    :param kwargs: (Optional) additional arguments. For system arguments, the prefix will be prepended automatically.
                   See :ref:`sys-args-table` below.

    :returns: str - `url` cdb:texttodisplay:`text_to_display`;
                    otherwise, just the `url` if `text_to_display` is `None`.

    .. _`sys-args-table`:
    .. table:: kwargs for system arguments

        +------------------------+----------------------------------+----------------------------------------------------------------------+
        | kwarg                  | value                            | description                                                          |
        +========================+==================================+======================================================================+
        | cdbxml_report_skip_dlg | "0" or "1"                       | "1" to skip the report selection dialog; otherwise "0".              |
        |                        |                                  | (Default: "1")                                                       |
        +------------------------+----------------------------------+----------------------------------------------------------------------+
        | cdbxml_report_lang     | "de", "en" ...                   | Report language. (Default: ISOLANG)                                  |
        +------------------------+----------------------------------+----------------------------------------------------------------------+
        | cdbxml_report_action   | "cdbxml_report_download",        | Report action.                                                       |
        |                        | "cdbxml_report_open",            | If not specified, defaults to the value in the report configuration. |
        |                        | "cdbxml_report_email"            | If the value is invalid, defaults to the FallbackAction.             |
        +------------------------+----------------------------------+----------------------------------------------------------------------+
        | cdbxml_report_format   | "Excel" "PDF",                   | Report format.                                                       |
        |                        | ("Excel && PDF" - if applicable) | If not specified, defaults to the value in the report configuration. |
        |                        |                                  | If the value is invalid, defaults to the first available format of   |
        |                        |                                  | the FallbackAction.                                                  |
        +------------------------+----------------------------------+----------------------------------------------------------------------+

    """  # noqa
    if obj and text_to_display is not None:
        if not text_to_display:
            text_to_display = obj.GetDescription()
        else:
            addtl_field_types = getAddtlFieldTypes(provider)
            if obj.HasField(text_to_display, addtl_field_type=addtl_field_types):
                text_to_display = obj[text_to_display]

    if action is None and obj and hasattr(obj, "__default_action__"):
        action = obj.__default_action__

    if report_name:
        action = "cdbxml_excel_report"

    if report_name:
        _build_sys_args_for_runreport_url(report_name, kwargs)

    url_type = (
        provider.getParameter("Hyperlinks:Type", "auto").lower() if provider else "auto"
    )
    if url_type == "auto":
        url_type = "win" if isCDBPC() else "web"

    if url_type == "web" and report_name:
        # web - react app
        object_id = obj.cdb_object_id if obj else None
        return _make_runreport_url(object_id, text_to_display, kwargs)

    if not obj and not report_name:
        raise Exception("Missing object!")  # pylint: disable=W0719

    msg = obj.MakeCdbcmsg(action, **kwargs)
    for keyname in obj.KeyNames():
        msg.add_item(keyname, obj.GetTableName(), obj[keyname])

    return _make_url(msg, url_type, text_to_display)


def MakeReportURLWithoutObj(
    class_name,
    action=None,
    text_to_display="",
    report_name=None,
    provider=None,
    **kwargs
):
    """
    Create a Report URL using the class name and cdb_object_id

    :param class_name: Class name of the object
    :type class_name: str
    :param action: (Optional) The action for the object.
                   If `report_name` is specified, the action is defaulted to `cdbxml_excel_report`;
                   otherwise, `CDB_ShowObject` will be used.
    :type action: str
    :param text_to_display: (Optional) Text for the hyperlink in the Excel report.
                            If explicitly set to `None`, the URL will not include the text to display.
    :type text_to_display: str
    :param report_name: Name of the report. (Corresponding to `cdbxml_report.title`)
    :type report_name: str
    :param provider: (Optional) The provider used for getting the parameter `Hyperlinks:Type`; otherwise, `auto` will be used.
    :type provider: str
    :param kwargs: Primary keys are required for finding the object.
                   For WebUI, `cdb_object_id` may be included, or the value will be fetched from the system.
                   Optionally, any other additional arguments may be used for the report generation.
                   For system arguments, the prefix will be prepended automatically.
                   See :ref:`sys-args-table`.

    :returns: str - `url` cdb:texttodisplay:`text_to_display`;
                    otherwise, just the `url` if `text_to_display` is `None`.

    """  # noqa
    if action is None:
        if report_name:
            action = "cdbxml_excel_report"
        else:
            action = "CDB_ShowObject"

    if report_name:
        _build_sys_args_for_runreport_url(report_name, kwargs)

    url_type = (
        provider.getParameter("Hyperlinks:Type", "auto").lower() if provider else "auto"
    )
    if url_type == "auto":
        url_type = "win" if isCDBPC() else "web"

    cdef = CDBClassDef(class_name)

    if url_type == "web" and report_name:
        # web - react app
        if "cdb_object_id" not in kwargs:
            kwargs["cdb_object_id"] = _get_object_id_from_table(
                cdef.getPrimaryTable(), kwargs
            )

        return _make_runreport_url(kwargs["cdb_object_id"], text_to_display, kwargs)

    msg = cmsg.Cdbcmsg(class_name, action, interactive=True)
    for k, v in kwargs.items():
        if k[:14] == "cdb::argument.":
            msg.add_sys_item(k[14:], v)
        else:
            msg.add_item(k, cdef.getPrimaryTable(), v)

    return _make_url(msg, url_type, text_to_display)


def _build_sys_args_for_runreport_url(report_name, kwargs):
    sys_args = [
        "cdbxml_report_skip_dlg",
        "cdbxml_report_subreport",
        "cdbxml_report_lang",
        "cdbxml_report_format",
        "cdbxml_report_action",
    ]
    for arg in sys_args:
        if arg in kwargs:
            kwargs["cdb::argument.%s" % arg] = kwargs[arg]
            del kwargs[arg]

    if "cdb::argument.cdbxml_report_skip_dlg" not in kwargs:
        kwargs["cdb::argument.cdbxml_report_skip_dlg"] = "1"
    if "cdb::argument.cdbxml_report_subreport" not in kwargs:
        kwargs["cdb::argument.cdbxml_report_subreport"] = report_name
    if "cdb::argument.cdbxml_report_lang" not in kwargs:
        kwargs["cdb::argument.cdbxml_report_lang"] = CADDOK.get("ISOLANG", "de")


def _make_url(msg, url_type, text_to_display):
    if url_type == "win":
        url = msg.cdbwin_url()  # "cdb://.."
    elif url_type == "web":
        url = msg.url()  # "http(s)://.."
    else:
        raise RuntimeError("Unsupported hyperlink type '%s'" % url_type)

    if text_to_display is not None:
        return "%s cdb:texttodisplay:%s" % (url, text_to_display)
    else:
        return url


def _make_runreport_url(object_id, text_to_display, kwargs):
    root_url = get_root_url()
    if not root_url.endswith("/"):
        root_url = "%s/" % root_url
    if object_id:
        url = "%scs-tools-powerreports/%s?%s" % (
            root_url,
            object_id,
            urllib.parse.urlencode(kwargs),
        )
    else:
        url = "%scs-tools-powerreports-context-free?%s" % (
            root_url,
            urllib.parse.urlencode(kwargs),
        )
    if text_to_display is not None:
        return "%s cdb:texttodisplay:%s" % (url, text_to_display)
    else:
        return url


def _get_object_id_from_table(relation, kwargs):
    ti = util.tables[relation]
    # check if relation table has object_id
    if ti.exists("cdb_object_id") == 0:
        raise RuntimeError("Table %s has no cdb_object_id" % relation)

    key_values = []
    for i in range(ti.number_of_keys()):
        if ti.key(i).name() in kwargs:
            key_values.append(kwargs[ti.key(i).name()])
        # if primary key is missing in kwargs
        else:
            raise Exception(  # pylint: disable=W0719
                "Missing primary key %s" % ti.key(i).name()
            )

    rs = sqlapi.RecordSet2(
        sql="SELECT * FROM " + relation + " WHERE %s" % ti.key_condition(key_values)
    )

    if len(rs) > 0:
        # expected 1 object to be found
        return rs[0].cdb_object_id
    else:
        # if rs is empty -> wrong value(s) in primary key(s)
        raise Exception(  # pylint: disable=W0719
            "Cannot find the object where %s in the table %s."
            % (ti.key_condition(key_values), relation)
        )


def _isSupportedUriPath(path):
    return (len(path) >= 5) and (path[:5] in ["file:", "http:"])


def MakeImageURL(fname, **kwargs):
    r"""
    If 'fname' is a recognized and supported URI type then it won't get
    included in the ZIP package in other parts of the PowerReports code.

    -ABSOLUTE/RELATIVE PATH: OfficeLink extracts the image from the ZIP (might be slow)
      in: 'c:\myimage.jpg'
      out: 'cdb://image/file:///myimage.jpg'
    -ABSOLUTE URI PATH: better performance, but OfficeLink need access to fname
      in: 'file:///Z:\company\imageresources\myimage.jpg'
      out: 'cdb://image/file:///Z:/company/imageresources/myimage.jpg'
    -HTTP ADDRESS: OfficeLink will download the image
      in: 'http://some.machine.de/imageresources/myimage.jpg'
      out: 'cdb://image/http://some.machine.de/imageresources/myimage.jpg'
    """
    prefix = "cdb://image/"
    if not _isSupportedUriPath(fname):
        fname = "file:///%s" % os.path.basename(fname)
    else:
        fname = fname.replace("\\", "/")
    return "%s%s" % (prefix, fname)


def _isContextCdbWeb():
    appinfo = misc.CDBApplicationInfo()
    return appinfo.rootIsa(misc.kAppl_HTTPServer)


def open_file_for_viewing(
    ctx, main_view_file, referenced_files=None, main_view_file_extern_filename=None
):
    # open the result in fileclient or workspaces desktop, if web ui
    if _isContextCdbWeb():
        use_file_client = util.get_prop("prfc")
        if use_file_client and use_file_client == "true":
            upload_to_file_client(
                ctx,
                main_view_file,
                referenced_files,
                main_view_file_extern_filename,
                delete_files_after_upload=True,
            )
        else:
            try:
                from cs.wsm.upload_to_client import viewonclient
            except ImportError:
                raise ue.Exception("powerreports_module_not_installed", "cs.workspaces")

            # view on Workspaces Desktop
            viewonclient(
                ctx, main_view_file, referenced_files, main_view_file_extern_filename
            )
            delete_temp_files(main_view_file, referenced_files)
    else:
        # copy report template file and set for viewing
        ctx.file(main_view_file)
        view_dir = os.path.normpath(client.viewDir.replace("\\", os.path.sep))
        if referenced_files:
            for rf in referenced_files:
                xml_clntfname = os.path.join(view_dir, os.path.basename(rf))
                ctx.upload_to_client(rf, xml_clntfname, delete_file_after_upload=1)


def download_to_browser(ctx, main_file):
    _, main_file_link = make_file_link_from_file(main_file)
    ctx.url(main_file_link)
    delete_temp_files(main_file, [])


def upload_to_file_client(
    ctx,
    main_file,
    referenced_files=None,
    main_file_extern_filename=None,
    delete_files_after_upload=True,
):
    """
    Uploads `main_file` and `referenced_files` from server to client machine by using the File
    Client. Afterwards `main_file` gets opened by the File Client, optionally named as
    `main_file_extern_filename`.
    """
    try:
        from cs.fileclient.links import make_upload_link
    except ImportError:
        raise ue.Exception("powerreports_module_not_installed", "cs.fileclient")

    main_filename, main_file_link = make_file_link_from_file(main_file)
    if main_file_extern_filename:
        main_filename = main_file_extern_filename

    files = [(main_filename, main_file_link)]

    if referenced_files:
        for ref_file in referenced_files:
            files.append(make_file_link_from_file(ref_file))

    delete_temp_files(main_file, referenced_files)

    cdbf_link = make_upload_link(files, main_filename)
    ctx.url(cdbf_link)


def delete_temp_files(main_file, referenced_files):
    from cs.tools.powerreports.xmlreportgenerator import DEBUG

    if not DEBUG:
        files_to_delete = [main_file]
        if referenced_files:
            files_to_delete.extend(referenced_files)
        for f in files_to_delete:
            if not isinstance(f, CDB_File):
                try:
                    os.remove(f)
                except IOError as ex:
                    misc.cdblogv(
                        misc.kLogErr,
                        0,
                        "Failed removing temporary file '%s': %s" % (f, ex),
                    )


def make_file_link_from_file(filepath_or_fileobj):
    """
    Creates either an `external temporary file` if `filepath_or_fileobj` is a filepath,
    or creates a REST link if `filepath_or_fileobj` is a `cdb_file` object.
    Returns a tuple of type (<filename>, <file URL>).
    """
    from cs.platform.web import external_tempfile
    from cs.platform.web.rest.support import get_restlink

    if isinstance(filepath_or_fileobj, CDB_File):
        filename = filepath_or_fileobj.cdbf_name
        file_link = get_restlink(filepath_or_fileobj)
    elif os.path.isfile(filepath_or_fileobj):
        filename = os.path.basename(filepath_or_fileobj)
        with external_tempfile.get_external_temp_file(name=filename) as proxy:
            proxy.copy_from_file(filepath_or_fileobj)
        file_link = proxy.get_url()
    else:
        raise Exception(  # pylint: disable=W0719
            "The file '%s' wasn't found or is no cdb_file object" % filepath_or_fileobj
        )

    return (filename, file_link)


def getAddtlFieldTypes(provider=None):
    addtl_field_types = [MappedAttributeDescriptor]
    if provider and provider.allAttributeTypesEnabled():
        addtl_field_types.extend(
            [
                JoinedAttributeDescriptor,
                MultiLangAttributeDescriptor,
                VirtualAttributeDescriptor,
            ]
        )
    return addtl_field_types


def getUniqueFields(fields):
    result = []
    seen_field_names = set()
    for f in fields:
        if f.name not in seen_field_names:
            result.append(f)
            seen_field_names.add(f.name)
    return result


def getExecutionTypes():
    pdfconverter_available = True
    try:
        from cs.office.acsplugins.office import (  # noqa # pylint: disable=W0611
            pdfconverter,
        )
    except ImportError:
        pdfconverter_available = False

    if pdfconverter_available:
        return {"synchron": ["Excel"], "asynchron": ["Excel", "PDF", "Excel && PDF"]}
    else:
        return {"synchron": ["Excel"], "asynchron": ["Excel"]}


def getReportActions():
    return {
        REPORT_DOWNLOAD: getExecutionTypes()["synchron"],
        REPORT_OPEN: getExecutionTypes()["synchron"],
        REPORT_EMAIL: getExecutionTypes()["asynchron"],
    }


def getFilteredActions():
    disabled_actions = [a.strip() for a in util.get_prop("prda").split(",")]
    return {
        action: format
        for action, format in getReportActions().items()
        if action not in disabled_actions
    }


def getFallbackAction():
    # use report download for webui and report open for windows client
    report_action = None
    if _isContextCdbWeb():
        report_action = REPORT_DOWNLOAD
    else:
        report_action = REPORT_OPEN
    # check if report action is filtered
    if report_action not in getFilteredActions().keys():
        # return first available action if filtered
        # use REPORT_DOWNLOAD as last resort
        return (
            list(getFilteredActions().keys())[0]
            if len(list(getFilteredActions().keys())) > 0
            else REPORT_DOWNLOAD
        )
    return report_action


class FileWriter:
    def __init__(self, filename, encoding):
        self.encoding = encoding

        assert isinstance(filename, str)  # nosec
        self.file = io_open(filename, "w", encoding=encoding)  # pylint: disable=R1732

    def close(self):
        self.file.close()

    def write(self, txt):  # txt MUST be unicode
        self.file.write(txt)


class ReportTemplateCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    @classmethod
    def Entries(cls, context_fqpynames, card):
        isolang = CADDOK.get("ISOLANG", "de")

        rs = report_sql_tools.get_template_records(context_fqpynames, card)
        reports = {}
        for r in rs:
            if r.cdbxml_report_id not in reports:
                reports[r.cdbxml_report_id] = {}
            if r.iso_code not in reports[r.cdbxml_report_id]:
                reports[r.cdbxml_report_id][r.iso_code] = [
                    r.tmpl_title,
                    r.cdbxml_report_id,
                ]

        template_titles = []
        languages = [isolang] + i18n.FallbackLanguages()
        for _, report in reports.items():
            for lang in languages:
                title_and_id = report.get(lang, None)
                if title_and_id:
                    template_titles.append(title_and_id)
                    break
            else:
                # neither ISOLANG nor FallbackLanguages is available
                # so let's take the 1st available report title
                template_titles.append(report[next(iter(report))])
        template_titles.sort()
        return template_titles

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        result = []
        object_handles = self.getInvokingOpObjects()

        card = ""
        fqpynames = []
        if object_handles:
            if len(object_handles) > 1:
                card = CARD_N
            obj = object_from_handle(object_handles[0])
            fqpynames = get_fqpynames(obj.__class__)
        templates = ReportTemplateCatalog.Entries(fqpynames, card)
        for template in templates:
            result.append(I18nCatalogEntry(template[1], template[0]))

        return result


class ReportLangCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        languages = set()
        rs = report_sql_tools.get_report_langs(
            self.getInvokingDlgValue("cdbxml_report_id")
        )
        for r in rs:
            languages.add(r.iso_code)
        return list(languages)


class ReportFormatCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        # Find Entries for Combobox (depending on report action)
        action = self.getInvokingDlgValue(REPORT_ACTION_ATTR)
        # Prevent UI Error if report_action is not set
        if not action:
            action = getFallbackAction()
        return getReportActions()[action]


class ReportActionCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        result = []
        for action in getFilteredActions().keys():
            result.append(I18nCatalogEntry(action, util.get_label(action)))

        # add empty field, except Report Selection Dialog
        if self.getInvokingOpName() != "cdbxml_excel_report":
            result.append(I18nCatalogEntry("", ""))

        return result


def get_object_from_hook(hook):
    result = None
    opInfo = hook.get_operation_state_info()
    if opInfo.get_objects():
        obj = opInfo.get_objects()[0]
        from cdb.objects import ByID

        result = ByID(obj.cdb_object_id)
    return result


def get_fieldname_from_attr(hook, attr):
    """
    get fieldname for object operation or meta class opertion
    """
    values = hook.get_new_values()
    field_cdbxml_report = "%s.%s" % ("cdbxml_report", attr)
    field = ".%s" % attr
    # only use field with cdbxml_report if exists, else use the given field
    return field_cdbxml_report if field_cdbxml_report in values.keys() else field


def cdbxml_excel_report_post_mask_hook(hook):
    obj = get_object_from_hook(hook)
    if obj:
        obj.cdbxml_excel_report_post_mask_hook(hook)
    else:
        XMLSource.cdbxml_excel_report_post_mask_hook(hook)


def cdbxml_excel_report_pre_mask_hook(hook):
    obj = get_object_from_hook(hook)
    if obj:
        obj.cdbxml_excel_report_pre_mask_hook(hook)
    else:
        XMLSource.cdbxml_excel_report_pre_mask_hook(hook)


def cdbxml_report_tmpl_post_mask_hook(hook):
    values = hook.get_new_values()
    source_name = values["cdbxml_report_tmpl.name"]
    tmpl_title = values["cdbxml_report_tmpl.title"]
    XMLReportTemplate.verify_tmpl_title(source_name, tmpl_title, hook)


def cdbxml_dataprovider_post_mask_hook(hook):
    XMLDataProvider.cdbxml_dataprovider_post_mask_hook(hook)


def cdbxml_excel_report_change_mask_hook(hook):
    values = hook.get_new_values()
    set_lang = values[".cdbxml_report_lang"]
    report = get_report_by_id(
        report_id=values[get_fieldname_from_attr(hook, REPORT_ID_ATTR)],
        iso_code=set_lang,
    )
    if report:
        set_action = (
            report[REPORT_ACTION_ATTR]
            if report[REPORT_ACTION_ATTR] in getReportActions()
            else getFallbackAction()
        )
        set_format = (
            report[REPORT_FORMAT_ATTR]
            if report[REPORT_FORMAT_ATTR] in getReportActions()[set_action]
            else getReportActions()[set_action][0]
        )
        if report.iso_code != set_lang:
            hook.set(".cdbxml_report_lang", report.iso_code)
        hook.set(get_fieldname_from_attr(hook, REPORT_ACTION_ATTR), set_action)
        hook.set(get_fieldname_from_attr(hook, REPORT_FORMAT_ATTR), set_format)


def get_fqpynames(cls):
    # reports can be inherited from base classes.
    # context_fqpynames will be filled with all fqpynames from
    # this class (cls) up to the root class.

    # set context
    context = ""
    context_fqpynames = []
    for c in cls.__mro__:
        if hasattr(c, "__maps_to__") and Object in c.__mro__:
            context_fqpynames.append(c.GetFQPYName())
            context = c.GetFQPYName()

    if context == "cs.tools.powerreports.XMLSource":
        context_fqpynames = []

    return context_fqpynames


def get_report_by_name(context_fqpynames, card, report_name, iso_code):
    templates = report_sql_tools.get_template_records(context_fqpynames, card)
    for template in templates:
        if template.report_title == report_name:
            return get_report_by_id(
                report_id=template.cdbxml_report_id, iso_code=iso_code
            )
    return None


def get_report_by_id(report_id, iso_code):
    """
    Get report record by id.
    If no iso_code specified, "ISOLANG" followed by "FallbackLanguages" will be used,
    If none are found, use the first language that is available for the report

    :return: RecordSet or None
    """
    isolang = CADDOK.get("ISOLANG", "de")

    reports = report_sql_tools.get_report_records(report_id)
    languages = [iso_code, isolang] + i18n.FallbackLanguages()

    for lang in languages:
        for report in reports:
            if lang and report.iso_code == lang:
                return report
    # neither iso_code, nor ISOLANG nor FallbackLanguages is found
    # so let's take the 1st available report
    if reports:
        return reports[0]
    else:
        return None


def cdbxml_excel_report_action_change_mask_hook(hook):
    values = hook.get_new_values()
    action_field = get_fieldname_from_attr(hook, REPORT_ACTION_ATTR)
    format_field = get_fieldname_from_attr(hook, REPORT_FORMAT_ATTR)

    # check if format exists for the selected action, else select the first available format
    set_action = values[action_field]
    set_format = values[format_field]
    if not set_action:
        set_action = getFallbackAction()
    if set_format not in getReportActions()[set_action]:
        hook.set(format_field, getReportActions()[set_action][0])


def cdbxml_dataprovider_source_change(hook):
    XMLDataProvider.cdbxml_dataprovider_source_change(hook)


class WithPowerReports:
    """
    In order to activate PowerReports for a system's object class, one of the
    conditions is that it inherits :class:`WithPowerReports`.
    """

    def __init__(self):
        pass

    @classmethod
    def _get_template_from_context(cls, ctx):
        attrnames = ctx.sys_args.get_attribute_names()
        if (
            "cdbxml_report_tmpl_cdb_object_id" in attrnames
            and "cdbxml_report_cdb_file_cdb_object_id" in attrnames
        ):
            return (
                ctx.sys_args.cdbxml_report_tmpl_cdb_object_id,
                ctx.sys_args.cdbxml_report_cdb_file_cdb_object_id,
            )
        else:
            # if tmpl_cdb_object_id and cdb_file_cdb_object_id is not availble
            # attempt to fetch them using tmpl_title and lang
            lang = CADDOK.get("ISOLANG", "de")
            if "cdbxml_report_lang" in attrnames:
                lang = ctx.sys_args.cdbxml_report_lang
            # prioritize dialog language over sys_args
            if "cdbxml_report_lang" in ctx.dialog.get_attribute_names():
                lang = ctx.dialog.cdbxml_report_lang

            set_id = ctx.dialog.cdbxml_report_id
            rs = report_sql_tools.get_template_file_ids(report_id=set_id, iso_code=lang)

            if not rs:
                raise ue.Exception("powerreports_tmpl_file_not_found")
            return rs[0]["tmpl_cdb_object_id"], rs[0]["cdb_file_cdb_object_id"]

    @classmethod
    def on_cdbxml_excel_report_pre_mask(cls, ctx):
        if _isContextCdbWeb():
            # skip pre_mask in Web, use pre_mask_hook instead
            return

        # Set defaults for report specific dialog
        if ctx.sys_args.current_mask != "initial":
            if hasattr(ctx.dialog, "cdbxml_report_id"):
                report = XMLReport.ByKeys(cdb_object_id=ctx.dialog.cdbxml_report_id)
                if report:
                    for k, v in report.getParameters().items():
                        if k not in ctx.keynames:
                            ctx.set(k, v)
        else:
            context_fqpynames = get_fqpynames(cls)

            # set cardinality: multi or single select
            card = ""
            if len(ctx.objects) > 1:
                card = CARD_N

            # initial value / user input
            set_id = (
                ctx.dialog.cdbxml_report_id
                if hasattr(ctx.dialog, REPORT_ID_ATTR)
                else ""
            )
            set_lang = (
                ctx.sys_args.cdbxml_report_lang
                if hasattr(ctx.sys_args, "cdbxml_report_lang")
                else ""
            )
            set_action = (
                ctx.dialog.cdbxml_report_action
                if hasattr(ctx.dialog, REPORT_ACTION_ATTR)
                else ""
            )
            set_format = (
                ctx.dialog.cdbxml_report_format
                if hasattr(ctx.dialog, REPORT_FORMAT_ATTR)
                else ""
            )

            report = None
            if hasattr(ctx.sys_args, "cdbxml_report_subreport"):
                report_name = ctx.sys_args.cdbxml_report_subreport
                report = get_report_by_name(
                    context_fqpynames, card, report_name, set_lang
                )

                if not report:
                    raise ue.Exception("powerreports_tmpl_name_not_found", report_name)

                # Skip report selection dialog, if template is predefined.
                # Used for report to report navigations or report specific
                # context menu entries.
                if (
                    hasattr(ctx.sys_args, "cdbxml_report_skip_dlg")
                    and ctx.sys_args.cdbxml_report_skip_dlg == "1"
                ):
                    ctx.disable_registers(["cdbxml_select_report"])
            else:
                if not set_id:
                    # get first available template in the list
                    template_titles = ReportTemplateCatalog.Entries(
                        context_fqpynames, card
                    )
                    if template_titles:
                        set_id = template_titles[0][1]
                    if set_id:
                        report = get_report_by_id(report_id=set_id, iso_code=set_lang)
                        if not report:
                            raise ue.Exception("powerreports_report_not_found", set_id)
            if report:
                if not set_id:
                    set_id = report["cdbxml_report_id"]
                if set_lang != report["iso_code"]:
                    set_lang = report["iso_code"]
                if not set_action or set_action not in getReportActions():
                    set_action = (
                        report[REPORT_ACTION_ATTR]
                        if report[REPORT_ACTION_ATTR] in getReportActions()
                        else getFallbackAction()
                    )
                if not set_format or set_format not in getReportActions()[set_action]:
                    set_format = (
                        report[REPORT_FORMAT_ATTR]
                        if report[REPORT_FORMAT_ATTR] in getReportActions()[set_action]
                        else getReportActions()[set_action][0]
                    )

            # Presets
            ctx.set(REPORT_ID_ATTR, set_id)
            ctx.set("cdbxml_report_lang", set_lang)
            ctx.set(REPORT_ACTION_ATTR, set_action)
            ctx.set(REPORT_FORMAT_ATTR, set_format)

    @classmethod
    def on_cdbxml_excel_report_post_mask(cls, ctx):
        # Set follow-up dialog for report specific parameters
        if ctx.get_current_mask() == "initial":
            rep = XMLReport.ByKeys(cdb_object_id=ctx.dialog.cdbxml_report_id)

            if not rep:
                raise ue.Exception(
                    "powerreports_report_not_found", ctx.dialog.cdbxml_report_id
                )
            rep.prepare()

            if rep.dialog:
                ctx.next_mask(rep.dialog)

    @classmethod
    def cdbxml_excel_report_pre_mask_hook(cls, hook):
        opInfo = hook.get_operation_state_info()

        context_fqpynames = get_fqpynames(cls)

        # set cardinality: multi or single select
        card = ""
        if len(opInfo.get_objects()) > 1:
            card = CARD_N
        values = hook.get_new_values()
        # initial value / user input
        set_id = values[".cdbxml_report_id"]
        set_lang = values[".cdbxml_report_lang"]
        set_action = values[".cdbxml_report_action"]
        set_format = values[".cdbxml_report_format"]

        report = None
        if "cdb::argument.cdbxml_report_subreport" in values:
            report_name = values["cdb::argument.cdbxml_report_subreport"]

            report = get_report_by_name(context_fqpynames, card, report_name, set_lang)
            if not report:
                LOG.error(
                    _get_error_msg("powerreports_tmpl_name_not_found", report_name)
                )
                show_error_msg(hook, "powerreports_tmpl_name_not_found", report_name)
                return
        else:
            if not set_id:
                # get first available template in the list
                template_titles = ReportTemplateCatalog.Entries(context_fqpynames, card)
                if template_titles:
                    set_id = template_titles[0][1]
                if set_id:
                    report = get_report_by_id(report_id=set_id, iso_code=set_lang)
                    if not report:
                        LOG.error(
                            _get_error_msg("powerreports_report_not_found", set_id)
                        )
                        show_error_msg(hook, "powerreports_report_not_found", set_id)
                        return
        if report:
            if not set_id:
                set_id = report["cdbxml_report_id"]
            if set_lang != report["iso_code"]:
                set_lang = report["iso_code"]
            if not set_action or set_action not in getReportActions():
                set_action = (
                    report[REPORT_ACTION_ATTR]
                    if report[REPORT_ACTION_ATTR] in getReportActions()
                    else getFallbackAction()
                )
            if not set_format or set_format not in getReportActions()[set_action]:
                set_format = (
                    report[REPORT_FORMAT_ATTR]
                    if report[REPORT_FORMAT_ATTR] in getReportActions()[set_action]
                    else getReportActions()[set_action][0]
                )

        # Presets
        hook.set(".cdbxml_report_id", set_id)
        hook.set(".cdbxml_report_lang", set_lang)
        hook.set(".cdbxml_report_action", set_action)
        hook.set(".cdbxml_report_format", set_format)

        if len(opInfo.get_objects()) == 1:
            obj = opInfo.get_objects()[0]
            o = cls._FromObjectHandle(obj)
            obj_values = {}
            from cs.platform.web.rest.generic import convert

            for k in o.keys():
                if o[k]:
                    obj_values[k] = o[k]
            vals = convert.dump(obj_values, cls._getClassDef())
            for k in vals:
                hook.set(k, vals.get(k))

        wizard_progress = hook.get_wizard_progress()
        wizard_progress.append_step(
            util.get_label("report_select"),
            util.get_label("report_select"),
            None,
            util.get_label(wizard_progress.BUTTON_NEXT_LABEL),
        )
        wizard_progress.append_step(
            util.get_label("report_arg_optional"),
            util.get_label("report_arg_optional"),
            None,
            util.get_label("web.base.ok"),
        )
        wizard_progress.set_button_label(
            util.get_label(wizard_progress.BUTTON_NEXT_LABEL)
        )

    @classmethod
    def cdbxml_excel_report_post_mask_hook(cls, hook):
        values = hook.get_new_values()
        rep = XMLReport.ByKeys(cdb_object_id=values[".cdbxml_report_id"])
        if not rep:
            show_error_msg(
                hook, "powerreports_report_not_found", values[".cdbxml_report_id"]
            )
            return
        rep.prepare()
        if rep.dialog:
            hook.set_next_dialog(rep.dialog)
            hook.get_wizard_progress().set_button_label(util.get_label("web.base.ok"))

    @classmethod
    def cdbxml_excel_report_load_parameters_hook(cls, hook):
        values = hook.get_new_values()
        rep = XMLReport.ByKeys(cdb_object_id=values[".cdbxml_report_id"])
        if rep:
            for k, v in rep.getParameters().items():
                if k not in values:
                    ft = hook.get_fieldtype(k)
                    if ft != -1:
                        v = typeconversion.to_python_rep(ft, v)
                    hook.set(".%s" % k, v)

    @classmethod
    def on_cdbxml_excel_report_now(cls, ctx):
        if ctx.uses_webui and not ctx.classname and version.verstring(False) == "15.3":
            # Meta-Reports in Web-UI ==> Start the App
            # With 15.3 the dialog hooks run after the operation now call.
            # For this reason the wizard, which ist setup in the cdbxml_excel_report_pre_mask_hook
            # will come to late. As a workaround the App is startet here.
            ctx.url("/cs-tools-powerreports")
            return
        # get the report template
        tmpl_cdb_object_id, cdb_file_cdb_object_id = cls._get_template_from_context(ctx)

        # get report action and format and ensure default values
        if hasattr(ctx.dialog, REPORT_ACTION_ATTR):
            report_action = ctx.dialog.cdbxml_report_action
        elif hasattr(ctx.sys_args, REPORT_ACTION_ATTR):
            report_action = ctx.sys_args.cdbxml_report_action
        else:
            report_action = getFallbackAction()

        if hasattr(ctx.dialog, REPORT_FORMAT_ATTR):
            report_format = ctx.dialog.cdbxml_report_format
        elif hasattr(ctx.sys_args, REPORT_FORMAT_ATTR):
            report_format = ctx.sys_args.cdbxml_report_format
        else:
            report_format = getReportActions()[report_action][0]

        cls.generate_report(
            tmpl_cdb_object_id,
            ctx,
            report_action=report_action,
            report_format=report_format,
            view=True,
            tmpl_file_id=cdb_file_cdb_object_id,
        )

    @classmethod
    def generate_report(
        cls,
        report_tmpl,
        ctx=None,
        objects=[],
        report_action=None,
        report_format=None,
        view=False,
        tmpl_file_id=None,
        dlg_args={},
    ):
        """Generate a PowerReport and perform defined server actions on it or simply return its
        filled report files as a list of pathnames.

        :param report_tmpl: Either only the `cdb_object_id` or a dict with the key attributes
                            (`name`, `report_title`, `iso_code`) of an :class:`XMLReportTemplate`.
        :type report_tmpl: str or dict
        :param ctx: A ctx is only required if either no `objects` are given or `view` is True
        :type ctx: _ctx.Object
        :param objects: A list of persistent objects. If the list is empty and `ctx` is given and
                        the xml source has a context, then the objects are taken from `ctx`.
        :type objects: list
        :param report_action: See `ReportActions` below for possible values. Passing None or an
                              empty string defaults to the value in the report configuration, unless
                              the value is invalid, defaults to FallbackAction
        :type report_action: str
        :param report_format: See `ReportActions` below for possible values. Passing None or an
                              empty string defaults to the value in the report configuration, unless
                              the value is invalid, defaults to first available format of FallbackAction
        :type report_format: str
        :param view: If `view` is False then no further viewing action is performed on the report
                     files.
        :type view: bool
        :param tmpl_file_id: (Optionally) directly define the template file, else it gets
                             automatically selected from the given template (primary files first).
        :type tmpl_file_id: str
        :param dlg_args: (Optionally) define the arguments for a report dialog (if `ctx` is not
                         given).
        :type dlg_args: dict

        :returns: list -- the generated report files, if 'view' is False. Else None.

        :raises: ue.Exception, RuntimeError
        .. table:: ReportActions

           +--------------------------+------------------+-------------------------------------------------+
           | report_action            | description      | report_format                                   |
           +==========================+==================+=================================================+
           |"cdbxml_report_download"  | Download         | "Excel"                                         |
           +--------------------------+------------------+-------------------------------------------------+
           |"cdbxml_report_open"      | Open             | "Excel"                                         |
           +--------------------------+------------------+-------------------------------------------------+
           |"cdbxml_report_email"     | Email            | "Excel", ("PDF", "Excel && PDF" - if applicable)|
           +--------------------------+------------------+-------------------------------------------------+

        """
        # get the report template and source
        if isinstance(report_tmpl, str):
            tmpl = XMLReportTemplate.KeywordQuery(cdb_object_id=report_tmpl)
        else:
            tmpl = XMLReportTemplate.KeywordQuery(
                name=report_tmpl["name"],
                iso_code=report_tmpl["iso_code"],
                report_title=report_tmpl["report_title"],
            )
        if not tmpl:
            raise ue.Exception(
                "powerreports_tmpl_not_found_for_keys", ("%s" % report_tmpl)
            )
        tmpl = tmpl[0]
        source = tmpl.XMLSource
        if not source:
            raise RuntimeError(
                "powerreports_source_not_found_for_tmpl", tmpl.GetDescription()
            )

        # check if we have a supported Excel file
        try:
            cdbfile = None
            if tmpl_file_id is not None:
                cdbfile = CDB_File.ByKeys(cdb_object_id=tmpl_file_id)
                cdbfile = [
                    f
                    for f in [cdbfile]
                    if os.path.splitext(f.cdbf_name)[1].lower() in SUPPORTED_FILETYPES
                ][0]
            else:
                xls_list = [
                    f
                    for f in tmpl.Files
                    if os.path.splitext(f.cdbf_name)[1].lower() in SUPPORTED_FILETYPES
                ]
                cdbfile = (
                    [f for f in xls_list if int(f.cdbf_primary) == 1] or xls_list
                )[0]
        except Exception:  # pylint: disable=W0718,W0703
            if cdbfile is not None:
                raise ue.Exception(
                    "powerreports_tmpl_file_type_not_supported", cdbfile.cdbf_name
                )
            oid = "" if not tmpl_file_id else (" (OID=%s)" % tmpl_file_id)
            raise ue.Exception("powerreports_primary_tmpl_file_not_found", oid)

        # setup args: additional parameters defined by report specific dialogs
        # are passed as kwargs to the XMLSource and the assigned data providers
        report = tmpl.XMLReport
        args = report.getParameters()  # public and user specific defaults

        # Get report format and actions from report config when not given via method args (E046596)
        # else use fallback action
        if not report_action:
            if report.cdbxml_report_action in getReportActions():
                report_action = report.cdbxml_report_action
            else:
                report_action = getFallbackAction()

        if not report_format:
            if report.cdbxml_report_format in getReportActions()[report_action]:
                report_format = report.cdbxml_report_format
            else:
                report_format = getReportActions()[report_action][0]

        iso_code = tmpl.iso_code
        if ctx is not None:
            if (
                hasattr(ctx, "sys_args")
                and "cdbxml_report_lang" in ctx.sys_args.get_attribute_names()
            ):
                iso_code = ctx.sys_args.cdbxml_report_lang
            for attr in ctx.dialog.get_attribute_names():
                # skip if standard dlg attribute
                if attr in ["cdbxml_report_id"]:
                    # we need following values in 'MakeReportURL'
                    # "cdbxml_report_lang",
                    # "cdbxml_report_action",
                    # "cdbxml_report_format"
                    continue
                if (not source.context) or (attr not in cls.KeyNames()):
                    args[attr] = ctx.dialog[attr]
                # prioritize dialog language over sys_args
                if attr == "cdbxml_report_lang":
                    iso_code = ctx.dialog[attr]

        # overwrite with optional parameter
        args.update(dlg_args)

        # get context object(s) from ctx if required
        if ctx is not None and source.context and not objects:
            objects = cls.PersistentObjectsFromContext(ctx)

        # build report filename(s)
        timestamp = time.strftime("%a-%d-%b-%Y-%H-%M-%S", time.localtime(time.time()))
        fbasename = "%s_%s_%s%s" % (
            tmpl.title,
            timestamp,
            auth.persno,
            os.path.splitext(cdbfile.cdbf_name)[1],
        )
        fbasename = re.sub(r":|\\|/|<|>|:|\*|\?|\"|\|", "", fbasename)
        # extend args
        sys_args = {}
        oids = [obj.ID() for obj in objects]
        sys_args["objects"] = oids
        sys_args["persno"] = auth.persno
        sys_args["target"] = os.path.splitext(fbasename)[0]
        sys_args["source"] = source.ID()
        sys_args["report_action"] = report_action
        sys_args["report_format"] = report_format
        sys_args["rep_lang"] = iso_code

        # default arguments (see make_schema)
        excel_custom_props = {
            "Arguments": [
                "cdbxml_report_date",
                "cdbxml_report_datetime",
                "cdbxml_report_author",
                "cdbxml_report_lang",
            ]
        }
        providers = source.DataProviders
        for provider in providers:
            prov_params = provider.getParameter("KeepInExcelAsCustomProp")
            if prov_params:
                excel_custom_props[provider.xsd_name] = [
                    x.strip() for x in prov_params.split(",")
                ]
        sys_args["custom_props"] = excel_custom_props

        args["__sys_args__"] = sys_args
        from cs.tools.powerreports.reportserver.report_generator import ReportGenerator

        repgen = ReportGenerator(tmpl.cdb_object_id, cdbfile.cdb_object_id, **args)

        # check format
        if report_format not in getReportActions()[report_action]:
            raise ue.Exception("powerreports_unsupported_format", report_format)
        # perform synchronous actions
        if report_action in [REPORT_DOWNLOAD, REPORT_OPEN] or not view:
            ret = repgen.create_report(CADDOK.TMPDIR)
            if ret["status"] == "OK":
                excel_file = ret["xls"]
                if excel_file is not None and os.path.exists(excel_file):
                    if not view:
                        return [excel_file]
                    elif report_action == REPORT_OPEN:
                        open_file_for_viewing(
                            ctx, excel_file, [], os.path.basename(excel_file)
                        )
                    elif report_action == REPORT_DOWNLOAD:
                        download_to_browser(ctx, excel_file)
                else:
                    raise ue.Exception("powerreports_gen_report_not_found")
            else:
                raise ue.Exception("powerreports_server_error", ret["status"])
        # perform asynchronous actions
        elif report_action in [REPORT_EMAIL]:
            # send it queue-based as mail
            repgen.dispatch_report_job()


class XMLSource(Object, WithPowerReports):
    __maps_to__ = "cdbxml_source"
    DataProviders = Reference_N(
        fXMLDataProvider, fXMLDataProvider.name == fXMLSource.name
    )

    def _get_context_provider(self):
        result = None
        for p in self.DataProviders:
            if p.source_type == "Context":
                result = p
        return result

    ContextProvider = ReferenceMethods_1(
        fXMLDataProvider, lambda self: self._get_context_provider()
    )

    def write_schema(self, fname):
        assert isinstance(fname, str)  # nosec
        try:
            with io_open(fname, "w", encoding="utf-8") as f:
                f.write(self.make_schema())
        except Exception as ex:
            misc.log_traceback("")
            if os.path.exists(fname):
                try:
                    os.remove(fname)
                except Exception as _ex:  # pylint: disable=W0718,W0703
                    misc.log_error("Error removing XSD file: %s" % _ex)
            raise ex

    def make_schema(self):
        def _add_virtual_schema(d, schema):
            for vd in d.virtualSubproviders():
                if vd.emit():
                    schema.add(vd.make_xsd_type(), vd.xsd_name)
                _add_virtual_schema(vd, schema)

        schema = XSDSchema()
        for d in self.DataProviders:
            if d.emit():
                schema.add(d.make_xsd_type(), d.xsd_name)
            _add_virtual_schema(d, schema)

        # Add arguments defined by the assigned data providers
        args = XSDType(1)
        for d in self.DataProviders:
            if hasattr(d, "getArgumentDefs"):
                for key, typ in d.getArgumentDefs().items():
                    args.add_attr("%s-%s" % (d.xsd_name, key), typ)
        # Add default arguments
        args.add_attr("cdbxml_report_date", sqlapi.SQL_DATE)
        args.add_attr("cdbxml_report_datetime", sqlapi.SQL_DATE)
        args.add_attr("cdbxml_report_author", sqlapi.SQL_CHAR)
        args.add_attr("cdbxml_report_lang", sqlapi.SQL_CHAR)
        if args:
            schema.add(args, "Arguments")
        return str(schema)

    def export(self, objects, filename, **kwargs):
        result_fname = "%s.cdbxml.zip" % filename
        myzip = None
        try:
            myzip = zipfile.ZipFile(  # pylint: disable=R1732
                result_fname, "w", zipfile.ZIP_DEFLATED
            )
            xml_fname = "%s.cdbxml" % filename

            parent_result = None
            context_provider = self.ContextProvider
            if context_provider:
                parent_result = context_provider._getData(objects, **kwargs)
            doc = XMLDocument()
            # Add data of assigned providers
            for d in self.DataProviders:
                if not d.parent_xsd_name:
                    d.export(parent_result, doc, filename, myzip, **kwargs)

            arg_defs = {}
            for d in self.DataProviders:
                if hasattr(d, "getArgumentDefs"):
                    for key, typ in d.getArgumentDefs().items():
                        arg_defs[("%s-%s" % (d.xsd_name, key)).lower()] = typ

            def _convert_argument_value(arg_defs, arg_name, arg_value):
                # Special value handler for converting date arguments (E016784)
                if (
                    arg_value
                    and (arg_name in arg_defs)
                    and (arg_defs[arg_name] == sqlapi.SQL_DATE)
                ):
                    # date arguments values always seem to come in the german format %d.%m.%Y
                    return from_legacy_date_format(arg_value).date()
                return arg_value

            # Add used arguments and keys of used root object
            args = ReportData(None)
            for k, v in kwargs.items():
                args[k] = _convert_argument_value(arg_defs, k, v)

            if context_provider:
                for k, v in context_provider.getArguments().items():
                    args[k] = _convert_argument_value(arg_defs, k, v)

            # Add default arguments
            args["cdbxml_report_datetime"] = (
                datetime.datetime.utcnow().isoformat().split(".")[0]
            )
            args["cdbxml_report_date"] = args["cdbxml_report_datetime"].split("T")[0]
            if "__sys_args__" in kwargs and "persno" in kwargs["__sys_args__"]:
                # happens on (asynchronous) server side report generation
                from cdb.objects.org import Person

                p = Person.ByKeys(kwargs["__sys_args__"]["persno"])
                args["cdbxml_report_author"] = p.name
            else:
                args["cdbxml_report_author"] = auth.name
            args["cdbxml_report_lang"] = kwargs.get(
                "cdbxml_report_lang", CADDOK.get("ISOLANG", "de")
            )
            args.to_xml(doc, "Arguments", **kwargs)
            try:
                myfile = FileWriter(xml_fname, "utf_8")
                doc.write(myfile)
            finally:
                myfile.close()
            if os.path.exists(xml_fname):
                myzip.write(xml_fname, os.path.basename(xml_fname))
                os.remove(xml_fname)
        except Exception as ex:
            if myzip and os.path.exists(result_fname):
                myzip.close()
                myzip = None
                os.remove(result_fname)
            misc.log_traceback("")
            raise ex
        finally:
            if myzip:
                myzip.close()
            # clear cached data:
            for p in self.DataProviders:
                p.cleanup()
        return result_fname

    def export_ex(
        self,
        objects,
        filename,
        tmpl_cdb_object_id,
        cdb_file_cdb_object_id,
        can_update,
        **kwargs
    ):
        result_fname = None
        try:
            result_fname = self.export(objects, filename, **kwargs)
            # add info file containing cdb_object_id/cdbf_object_id of used template file (cdb_file)
            info_fname = "%s.cdbinfo" % filename
            try:
                myfile = FileWriter(info_fname, "utf_8")
                myfile.write("<?xml version='1.0' encoding='utf-8'?>\n")
                myfile.write("<!--PowerReport info file-->\n")
                myfile.write('<doceditinfo version="298">\n')
                myfile.write('  <cdb_file_args classname="cdb_file">\n')
                myfile.write("    <cdb_file>\n")
                myfile.write(
                    "      <cdb_object_id>%s</cdb_object_id>\n"
                    % (cdb_file_cdb_object_id)
                )
                myfile.write("    </cdb_file>\n")
                myfile.write("  </cdb_file_args>\n")
                myfile.write(
                    '  <cdb_parent_args classname="cdbxml_report_tmpl" can_update="%s">\n'
                    % (can_update)
                )  # noqa
                myfile.write("    <cdbxml_report_tmpl>\n")
                myfile.write(
                    "      <cdb_object_id>%s</cdb_object_id>\n" % (tmpl_cdb_object_id)
                )
                # Legacy: Remove 'can_update' as a parent object key in any upcoming cs.powerreports
                #         version for CE >=15.5, since newer cs.officelink versions search it as a
                #         cdb_parent_args attribute (see above)
                myfile.write("      <can_update>%s</can_update>\n" % (can_update))
                myfile.write("    </cdbxml_report_tmpl>\n")
                myfile.write("  </cdb_parent_args>\n")
                myfile.write("</doceditinfo>\n")
            finally:
                myfile.close()
            try:
                myzip = zipfile.ZipFile(  # pylint: disable=R1732
                    result_fname, "a", zipfile.ZIP_DEFLATED
                )
                myzip.write(info_fname, os.path.basename(info_fname))
            finally:
                myzip.close()
                os.remove(info_fname)
        except Exception as ex:
            if result_fname and os.path.exists(result_fname):
                os.remove(result_fname)
            misc.log_traceback("")
            raise ex
        return result_fname

    def on_relship_copy_post(self, ctx):
        if ctx.relationship_name == "cdbxml_source2data_provider":
            self.DataProviders.Update(context=self.context)

    def create_context_provider(self, ctx):
        if self.context:
            xsd_name = XSDSchema.make_valid_xsd_name(
                "%s_%s" % (self.context.split(".")[-1], self.context_card)
            )
            p = XMLContextProvider.Create(
                name=self.name,
                source=self.context,
                xsd_name=xsd_name,
                source_type="Context",
                context=self.context,
                parent_xsd_name="",
            )
            p.create_parameters()
            p.add_public_grant()

    def set_fields_readonly(self, ctx):
        ctx.set_fields_readonly(["context", "context_card"])

    def scan(self, ctx):
        ClassNameBrowser.Scan(scan_props=True)

    def checkProviderName(self, ctx):
        self.name = self.name.strip()
        for c in self.name:
            if not c.isalnum() and not c.isspace():
                raise ue.Exception("powerreports_invalid_provider_name_char", c)

    event_map = {
        (("create"), "post"): "create_context_provider",
        (("modify"), "pre_mask"): "set_fields_readonly",
        (("create", "copy"), "pre_mask"): "scan",
        (("create", "copy"), "pre"): "checkProviderName",
    }


class Grant(WithSubject):
    def setSubjectName(self, ctx):
        if self.subject_id == "public":
            sn = "public"
        else:
            sn = self.getSubjectName()
        obj = self.getPersistentObject()
        if obj.subject_name != sn:
            obj.subject_name = sn
            ctx.set("subject_name", sn)
        ctx.refresh_tables([self.GetTableName()])

    def on_cdb_open_subject_now(self, ctx):
        self.setSubjectName(ctx)
        return self.openSubject()

    def check(self, **kwargs):
        if self.subject_id == "public":
            return True
        if "__sys_args__" in kwargs and "persno" in kwargs["__sys_args__"]:
            # happens on (asynchronous) server side report generation
            persno = kwargs["__sys_args__"]["persno"]
        else:
            persno = auth.persno
        return self.Subject.Match(persno)

    event_map = {(("copy", "modify", "info"), "pre_mask"): "setSubjectName"}


class XMLReportTemplate(Object, WithPowerReports):
    __maps_to__ = "cdbxml_report_tmpl"
    __classname__ = "cdbxml_report_tmpl"

    Files = Reference_N(fFile, fFile.cdbf_object_id == fXMLReportTemplate.cdb_object_id)
    XMLReport = Reference_1(
        fXMLReport, fXMLReportTemplate.name, fXMLReportTemplate.report_title
    )
    XMLSource = Reference_1(fXMLSource, fXMLReportTemplate.name)

    @classmethod
    def on_cdbxml_excel_report_dialogitem_change(cls, ctx):
        # analog to "cdbxml_excel_report_change_mask_hook" and "cdbxml_excel_report_action_change_mask_hook"
        if ctx.changed_item == REPORT_ID_ATTR:
            # if the user changed the report template, then adjust report action
            # and report format with the predefined values
            set_lang = ctx.dialog.cdbxml_report_lang
            report = get_report_by_id(
                report_id=ctx.dialog.cdbxml_report_id, iso_code=set_lang
            )
            if report:
                set_action = (
                    report[REPORT_ACTION_ATTR]
                    if report[REPORT_ACTION_ATTR] in getReportActions()
                    else getFallbackAction()
                )
                set_format = (
                    report[REPORT_FORMAT_ATTR]
                    if report[REPORT_FORMAT_ATTR] in getReportActions()[set_action]
                    else getReportActions()[set_action][0]
                )
                if report.iso_code != set_lang:
                    ctx.set("cdbxml_report_lang", report.iso_code)
                ctx.set(REPORT_ACTION_ATTR, set_action)
                ctx.set(REPORT_FORMAT_ATTR, set_format)
        # check if format exists for the selected action, else select the first available format
        elif ctx.changed_item == REPORT_ACTION_ATTR:
            set_action = ctx.dialog.cdbxml_report_action
            # if action is not set, use fallback action
            if not set_action:
                set_action = getFallbackAction()

            if ctx.dialog.cdbxml_report_format not in getReportActions()[set_action]:
                ctx.set(
                    REPORT_FORMAT_ATTR,
                    getReportActions()[set_action][0],
                )

    def presetTitle(self, ctx):
        if not self.title:
            self.title = self.XMLReport.title

    @staticmethod
    def create_xsd_schema(xml_src):
        timestamp = time.strftime("%a-%d-%b-%Y-%H-%M-%S", time.localtime(time.time()))
        schema_fname = os.path.join(
            CADDOK.TMPDIR, "%s_%s_xsd_schema.xsd" % (auth.persno, timestamp)
        )
        xml_src.write_schema(schema_fname)
        return schema_fname

    def on_cdbxml_tmpl_schema_import_now(self, ctx):
        schema_fname = self.create_xsd_schema(self.XMLSource)
        xls_list = [
            f
            for f in self.Files
            if os.path.splitext(f.cdbf_name)[1].lower() in SUPPORTED_FILETYPES
        ]
        cdbfile = ([f for f in xls_list if int(f.cdbf_primary) == 1] or xls_list)[0]

        template_fname = os.path.join(
            CADDOK.TMPDIR, "%s%s" % (os.path.splitext(cdbfile.cdbf_name))
        )
        cdbfile.checkout_file(template_fname)

        from cs.tools.powerreports.xmlreportgenerator.xsd_util import XSDUtil

        XSDUtil(
            template_fname, schema_fname, "CDB_" + self.XMLSource.name
        ).import_schema()

        cdbfile.checkin_file(template_fname)
        try:
            os.remove(schema_fname)
        except Exception as _ex:  # pylint: disable=W0718,W0703
            misc.log_error("Error removing XSD file: %s" % _ex)
        try:
            os.remove(template_fname)
        except Exception as _ex:  # pylint: disable=W0718,W0703
            misc.log_error("Error removing tempory template file: %s" % _ex)

    def verifyTitleUniqueness(self, ctx):
        source_name = ctx.dialog.name
        tmpl_title = ctx.dialog.title
        XMLReportTemplate.verify_tmpl_title(source_name, tmpl_title)

    @staticmethod
    def verify_tmpl_title(source_name, tmpl_title, hook=None):
        s = (
            "COUNT(*) FROM cdbxml_report_tmpl "
            "WHERE cdbxml_report_tmpl.name != '%s'"
            "  AND cdbxml_report_tmpl.title = '%s'" % (source_name, tmpl_title)
        )
        rs = sqlapi.SQLselect(s)
        if sqlapi.SQLinteger(rs, 0, 0):
            show_error_msg(hook, "powerreports_title_not_unique", tmpl_title)

    @classmethod
    def FindByObjectId(cls, cdb_object_id):
        obj = XMLReportTemplate.KeywordQuery(cdb_object_id=cdb_object_id)
        if len(obj) == 1:
            return obj[0]

    event_map = {
        (("copy", "create"), "pre_mask"): "presetTitle",
        (("copy", "create"), "post_mask"): "verifyTitleUniqueness",
    }


class XMLReportGrant(Grant):
    __maps_to__ = "cdbxml_report_grant"
    __classname__ = "cdbxml_report_grant"


class XMLProviderGrant(Grant):
    __maps_to__ = "cdbxml_prov_grant"
    __classname__ = "cdbxml_prov_grant"


class XMLReport(Object):
    __maps_to__ = "cdbxml_report"
    __classname__ = "cdbxml_report"

    XMLSource = Reference_1(fXMLSource, fXMLReport.name)
    ParametersByPersno = ReferenceMapping_N(
        fXMLReportParameter,
        fXMLReportParameter.name == fXMLReport.name,
        fXMLReportParameter.report_title == fXMLReport.title,
        indexed_by=fXMLReportParameter.persno,
    )
    Parameters = Reference_N(
        fXMLReportParameter,
        fXMLReportParameter.name == fXMLReport.name,
        fXMLReportParameter.report_title == fXMLReport.title,
    )

    ParametersForPublic = Reference_N(
        fXMLReportParameter,
        fXMLReportParameter.name == fXMLReport.name,
        fXMLReportParameter.report_title == fXMLReport.title,
        fXMLReportParameter.persno == "public",
    )

    Grants = Reference_N(
        fXMLReportGrant,
        fXMLReportGrant.name == fXMLReport.name,
        fXMLReportGrant.report_title == fXMLReport.title,
    )

    GrantsToRoles = Reference_N(
        fXMLReportGrant,
        fXMLReportGrant.name == fXMLReport.name,
        fXMLReportGrant.report_title == fXMLReport.title,
        fXMLReportGrant.subject_type != "Person",
    )

    Templates = Reference_N(
        fXMLReportTemplate,
        fXMLReportTemplate.name == fXMLReport.name,
        fXMLReportTemplate.report_title == fXMLReport.title,
    )

    Masks = Reference_Methods(fDialog, lambda self: fDialog.ByName(self.dialog))

    def onDialogitemChange(self, ctx):
        # analog to "cdbxml_excel_report_action_change_mask_hook"
        # check if format exists for the selected action, else select the first available format
        if ctx.changed_item == REPORT_ACTION_ATTR:
            set_action = ctx.dialog.cdbxml_report_action
            # if action is not set, use fallback action
            if not set_action:
                set_action = getFallbackAction()

            if ctx.dialog.cdbxml_report_format not in getReportActions()[set_action]:
                ctx.set(
                    REPORT_FORMAT_ATTR,
                    getReportActions()[set_action][0],
                )

    def getParameters(self):
        result = {}
        for p in self.ParametersByPersno["public"]:
            result[p.arg_name] = p.arg_value
        for p in self.ParametersByPersno[auth.persno]:
            result[p.arg_name] = p.arg_value
        return result

    def setDefaultGrant(self, ctx):
        args = {
            "name": self.name,
            "report_title": self.title,
            "subject_id": auth.persno,
            "subject_name": auth.name,
            "subject_type": "Person",
        }
        XMLReportGrant.Create(**args)

    def prepare(self):
        """
        Prepares the kernel for the upcomping queries
        """
        import cdbwrapc

        try:
            cdbwrapc.prepare_feature_call_by_args(
                SimpleArguments(report_name=self.name, cdb_module_id=self.cdb_module_id)
            )
        except RuntimeError as e:
            raise ue.Exception(1024, str(e))

    @classmethod
    def FindByNameAndTitle(cls, name, title):
        obj = XMLReport.KeywordQuery(name=name, title=title)
        return obj[0] if len(obj) == 1 else None

    event_map = {
        (("copy", "create"), "post"): "setDefaultGrant",
        (("copy", "create", "modify"), "dialogitem_change"): "onDialogitemChange",
    }


class XMLReportParameter(Object):
    __maps_to__ = "cdbxml_report_arg"
    __classname__ = "cdbxml_report_arg"


class XMLProviderParameter(Object):
    __maps_to__ = "cdbxml_provider_arg"
    __classname__ = "cdbxml_provider_arg"


class XMLDataProvider(Object):
    """Base class for xml data providers"""

    __maps_to__ = "cdbxml_dataprovider"
    __classname__ = "cdbxml_dataprovider"

    XMLSource = Reference_1(fXMLSource, fXMLSource.name)
    Grants = Reference_N(
        fXMLProviderGrant,
        fXMLProviderGrant.name == fXMLDataProvider.name,
        fXMLProviderGrant.xsd_name == fXMLDataProvider.xsd_name,
    )

    GrantsToRoles = Reference_N(
        fXMLProviderGrant,
        fXMLProviderGrant.name == fXMLDataProvider.name,
        fXMLProviderGrant.xsd_name == fXMLDataProvider.xsd_name,
        fXMLProviderGrant.subject_type != "Person",
    )

    Parameters = Reference_N(
        fXMLProviderParameter,
        fXMLProviderParameter.name == fXMLDataProvider.name,
        fXMLProviderParameter.xsd_name == fXMLDataProvider.xsd_name,
    )
    ParentProvider = Reference_1(
        fXMLDataProvider, fXMLDataProvider.name, fXMLDataProvider.parent_xsd_name
    )
    SubProviders = Reference_N(
        fXMLDataProvider,
        fXMLDataProvider.name == fXMLDataProvider.name,
        fXMLDataProvider.parent_xsd_name == fXMLDataProvider.xsd_name,
    )

    GroupedDataProvider = property(lambda self: self._buildGroupedDataProvider())

    def getCallCard(self):
        # To be implemented by concrete provider.
        # Must return one of the following cardinalities: CARD_0, CARD_1, CARD_N
        # This cardinality defines the required number of objects to be passed as first parameter
        # to the getData(...) call of the provider. Contextless toplevel providers must return
        # CARD_0. Subproviders may work with 1 or N result objects of the parent provider.
        pass

    def is_multi_export(self):
        if self.card() == N:
            # If at least one subprovider works on single objects, e.g. Relationships,
            # multi export mode is used. Subproviders working on all result objects of
            # the parent provider, e.g. GroupBy Providers, are exported to the overall export file
            # anyway.
            for p in self.SubProviders + self.virtualSubproviders():
                if p.getCallCard() in (CARD_1, CARD_0_1):
                    return True
        return False

    def accessGranted(self, **kwargs):
        # returns true, if the user is allowed to retrieve data from this provider
        if self.source_type == "virtual":
            return True
        for g in self.Grants:
            if g.check(**kwargs):
                return True
        return False

    def _getData(self, parent_result, **kwargs):
        if not hasattr(self, "_data"):
            args = {}
            prefix = self.arg_prefix()
            for k, v in kwargs.items():
                if k.startswith(prefix):
                    key = k.replace(prefix, "")
                    args[key] = v
            self._data = self.getData(  # pylint: disable=E1128
                parent_result, kwargs, **args
            )
            self.addHyperlinks(self._data, kwargs)
            self.addImagelinks(self._data, kwargs)
        return self._data

    def cleanup(self):
        # deletes cached data
        if hasattr(self, "_data"):
            del self._data

    def getData(self, parent_result, source_args, **kwargs):
        # To be implemented by concrete provider.
        # Must return a ReportData Object or ReportDataList depending on self.card.
        return None

    def export(self, parent_result, xml_doc, fname, myzip, **kwargs):
        if self.accessGranted(**kwargs):
            if self.is_multi_export():
                self._multi_export(parent_result, fname, myzip, xml_doc, **kwargs)
            else:
                self._export(parent_result, xml_doc, fname, myzip, **kwargs)

    def _export(
        self, parent_result, xml_doc, fname, myzip, in_multi_export=False, **kwargs
    ):
        if self.accessGranted(**kwargs):
            data = self._getData(parent_result, **kwargs)
            if data:
                if self.emit():
                    data.to_xml(xml_doc, self.xsd_name, **kwargs)
                    if "__updating_report__" not in list(kwargs):
                        # don't try to reload images in a filled report
                        if hasattr(data, "export_images"):
                            data.export_images(fname, myzip)
                for p in self.SubProviders + self.virtualSubproviders():
                    if in_multi_export:
                        p._export(data, xml_doc, fname, myzip, True, **kwargs)
                        p.cleanup()
                    else:
                        p.export(data, xml_doc, fname, myzip, **kwargs)

    def _multi_export(self, parent_result, fname, myzip, xml_doc, **kwargs):
        if not self.accessGranted(**kwargs):
            return
        data = self._getData(parent_result, **kwargs)
        if data and isinstance(data, ReportDataList):
            for i in range(len(data)):  # pylint: disable=C0200
                xml_fname = "%s%s.cdbxml" % (fname, i + 1)
                doc = XMLDocument()
                if self.emit():
                    data[i].to_xml(doc, self.xsd_name, **kwargs)
                # Export subproviders working on single result objects of the parent provider
                # to single xml files. (e.g. Relship Provider)
                for p in self.SubProviders + self.virtualSubproviders():
                    if p.getCallCard() in (CARD_1, CARD_0_1):
                        p._export(data[i], doc, fname, myzip, True, **kwargs)
                        p.cleanup()
                try:
                    myfile = FileWriter(xml_fname, "utf_8")
                    doc.write(myfile)  # FIXME: should write directly to zip file
                finally:
                    myfile.close()
                if os.path.exists(xml_fname):
                    myzip.write(xml_fname, os.path.basename(xml_fname))
                    os.remove(xml_fname)
            # Export subproviders working with all result objects of the parent provider
            # to the overall xml export. (e.g. GroupBy Provider)
            for p in self.SubProviders:
                if p.getCallCard() == CARD_N:
                    p.export(data, xml_doc, fname, myzip, **kwargs)

    def make_xsd_type(self):
        if not hasattr(self, "_xsd_type"):
            t = self.getSchema()
            if type(t) in (str, Class):
                # automatic schema construction from relation name or cdb.objects Class.
                t = XSDType(self.schema_card(), t, provider=self)
            if not t or not isinstance(t, XSDType):
                raise RuntimeError("No schema for data provider: %s" % self)
            t.provider = self
            if hasattr(self, "extend_schema"):
                self.extend_schema(t)
            t.card = self.schema_card()
            self._xsd_type = t
        return self._xsd_type

    def arg_prefix(self):
        return "%s-" % self.xsd_name.lower()

    def setContext(self, ctx):
        if self.ParentProvider:
            parent_cls = self.ParentProvider.getClass()
            if parent_cls:
                self.context = "%s.%s" % (parent_cls.__module__, parent_cls.__name__)
        else:
            if self.XMLSource:
                self.context = self.XMLSource.context
            else:
                raise ue.Exception("powerreports_context_not_found")

    def check_xsd_name(self, ctx):
        if (
            "xsd_name" in ctx.dialog.get_attribute_names()
            and not XSDSchema.is_valid_xsd_name(ctx.dialog.xsd_name)
        ):
            raise ue.Exception("powerreports_invalid_xsd_name", ctx.dialog.xsd_name)

    def preset_xsd_name(self, ctx):
        if ctx.changed_item == "source":
            xsd_name = ""
            if self.source_type in ("Relationship", "Rule"):
                xsd_name = ctx.dialog.source
            elif self.source_type == "CustomCode":
                xsd_name = ctx.dialog.source.split(".")[-1]
            self.xsd_name = XSDSchema.make_valid_xsd_name(xsd_name)

    @classmethod
    def cdbxml_dataprovider_source_change(cls, hook):
        op_names = ["CDB_Create", "CDB_Copy"]
        if hook.get_operation_name() in op_names:
            source = hook.get_new_values()["cdbxml_dataprovider.source"]
            source_type = hook.get_new_values()["cdbxml_dataprovider.source_type"]
            xsd_name = ""
            if source_type in ("Relationship", "Rule"):
                xsd_name = source
            elif source_type == "CustomCode":
                xsd_name = source.split(".")[-1]
            xsd_name = XSDSchema.make_valid_xsd_name(xsd_name)
            hook.set("cdbxml_dataprovider.xsd_name", xsd_name)

    @classmethod
    def cdbxml_dataprovider_post_mask_hook(cls, hook):
        values = hook.get_new_values()
        kwargs = {}
        for value in values:
            if value.startswith("cdbxml_dataprovider."):
                kwargs[value.split(".")[1]] = values[value]
        leaf_cls = cls._FindLeafClass(kwargs)
        obj = leaf_cls(**kwargs)
        obj.check_card(hook=hook)
        xsd_name = values["cdbxml_dataprovider.xsd_name"]
        if not XSDSchema.is_valid_xsd_name(xsd_name):
            show_error_msg(hook, "powerreports_invalid_xsd_name", xsd_name)

    def add_public_grant(self, ctx=None):
        XMLProviderGrant.Create(
            name=self.name,
            xsd_name=self.xsd_name,
            subject_id="public",
            subject_type="Common Role",
            subject_name="public",
        )

    def create_parameters(self, ctx=None):
        for k, v in self.getDefaultParameters().items():
            XMLProviderParameter.Create(arg_name=k, arg_value=v, **self.KeyDict())

    def getParameter(self, name, dflt=None):
        for p in self.Parameters:
            if p.arg_name.lower() == name.lower():
                return p.arg_value
        return dflt

    def getDefaultParameters(self):
        result = {}
        if self.getClass():
            result = {
                "AccessControl:CheckedRight": "read",
                "AccessControl:FailBehavior": "skip row",
                "AccessControl:FailBehaviorJoinedObjects": "",
                "AllAttributeTypes": "False",
                "LongTexts": "",
                "Hyperlinks:Enabled": "True",
                "Hyperlinks:Type": "auto",
                "Hyperlinks:Action": "",
                "Hyperlinks:SubReport": "",
                "Hyperlinks:TextToDisplay": "",
                "MaxRowsTruncate": 64000,
                "DateTimeMode": DATETIME_MODE_UTC,
            }  # UTC, local time, as configured
        classes = list(self.__class__.__mro__)
        classes.reverse()
        for clazz in classes:
            if hasattr(clazz, "__parameters__"):
                result.update(clazz.__parameters__)
        return result

    def getArgumentDefs(self):
        result = {}
        for a in self.getGroupByArgNames():
            result[a] = sqlapi.SQL_CHAR
        return result

    def getGroupByArgs(self):
        result = []
        for p in self.getGroupByArgNames():
            v = self.getParameter(p, dflt="")
            if v:
                result.append(v)
        return result

    def getGroupByArgNames(self):
        def to_int(s):
            if s:
                try:
                    return int(s)
                except ValueError:
                    pass
            return None

        result = []
        for p in self.Parameters:
            if p.arg_name.startswith("Group_By"):
                c = to_int(p.arg_name[len("Group_By") :])
                if c is not None:
                    result.append("group_by%s" % c)
        result.sort()
        return result

    def _buildGroupedDataProvider(self):
        _provider_key = "bb31a731-08ab-11de-8344-f944eb36b4b2"
        if _provider_key in self._refcache:
            p = self._refcache[_provider_key]
        else:
            p = None
            if self.source_type != "GroupBy" and self.getGroupByArgNames():
                p = VirtualGroupedDataProvider(
                    name=self.name,
                    xsd_name=self.xsd_name + "_GroupHeaders",
                    source_type="virtual",
                    parent_xsd_name=self.xsd_name,
                )
                p._setup(self)
            self._refcache[_provider_key] = p
        return p

    def virtualSubproviders(self):
        if self.GroupedDataProvider:
            return [self.GroupedDataProvider]
        else:
            return []

    def emit(self):
        if self.getGroupByArgNames():
            return False
        else:
            return True

    def schema_card(self):
        if self.is_multi_export():
            return 1
        else:
            return self.card()

    def scan(self, ctx):
        if self.source_type == "CustomCode":
            XMLProviderRegistry.Scan()
        ClassNameBrowser.Scan(scan_props=True)

    def check_card(self, ctx=None, hook=None):
        if ctx and ctx.action == "modify" and not self.ParentProvider:
            # see E019094 and E029836
            return
        if (
            hook
            and hook.get_operation_name() == "CDB_Modify"
            and not self.ParentProvider
        ):
            # see E019094 and E029836 for web
            return
        type_name = self.source_type
        if self.source_type == "CustomCode":
            if not self.source:
                return
            else:
                type_name = self.source
        if self.getCallCard() == CARD_0 and self.ParentProvider:
            show_error_msg(hook, "powerreports_invalid_subprovider_type", type_name)
            return
        if self.getCallCard() in (CARD_1, CARD_N) and not self.ParentProvider:
            show_error_msg(hook, "powerreports_only_subprovider_type", type_name)
            return
        if (
            self.ParentProvider
            and (self.ParentProvider.card() == CARD_N)
            and (self.ParentProvider.getCallCard() in (CARD_1, CARD_0_1))
            and self.ParentProvider.ParentProvider
            and (self.ParentProvider.ParentProvider.card() == CARD_N)
        ):
            if self.getCallCard() != CARD_N:
                show_error_msg(hook, "powerreports_invalid_subprovider_nested_list")
                return
        if (
            self.source_type == "GroupBy"
            and self.ParentProvider
            and self.ParentProvider.card() in (CARD_1, CARD_0_1)
        ):
            show_error_msg(hook, "powerreports_invalid_groupby_assignment")

    def getSchema(self):
        return self.getClass()

    def getClass(self):
        self.setup()
        return self._cls

    def getRelation(self):
        """Returns the relation (table or view if exists) of the
        class the provider is working on."""
        objects_cls = self.getClass()
        if objects_cls:
            cldef = objects_cls._getClassDef()
            if cldef:
                return cldef.getRelation()

    def getJoinedFields(self, join_name):
        """Returns the names of all joined attributes, that belong
        to the join specified by join_name."""
        result = []
        objects_cls = self.getClass()
        if objects_cls:
            from cdb.platform.mom import entities, fields

            cls = entities.Class.ByKeys(objects_cls._getClassname())
            result = [
                f.field_name
                for f in cls.DDAllFields
                if isinstance(f, fields.DDJoinedField) and f.join_alias == join_name
            ]
        return result

    def getVirtualFields(self):
        """Returns all virtual fields of the class the provider
        is working on."""
        result = []
        objects_cls = self.getClass()
        if objects_cls:
            from cdb.platform.mom import entities, fields

            cls = entities.Class.ByKeys(objects_cls._getClassname())
            result = [
                f.field_name
                for f in cls.DDAllFields
                if isinstance(f, fields.DDVirtualField)
            ]
        return result

    def setup(self):
        # To be implemented by subclass. Subclass must specify self._cls
        self._cls = None

    def getLongTexts(self):
        result = []
        longtexts = self.getParameter("LongTexts", "")
        if longtexts:
            result = [s.strip() for s in longtexts.split(",")]
        return result

    def allAttributeTypesEnabled(self):
        add_joined_attrs = self.getParameter("AllAttributeTypes")
        return add_joined_attrs and add_joined_attrs.lower() in ("true", "1")

    def hyperlinksEnabled(self):
        add_hyperlinks = self.getParameter("Hyperlinks:Enabled")
        return add_hyperlinks and add_hyperlinks.lower() in ("true", "1")

    def getMaxRowsTruncation(self):
        max_rows_truncate = self.getParameter("MaxRowsTruncate")
        if max_rows_truncate and int(max_rows_truncate) > 0:
            return int(max_rows_truncate)
        return None

    def addHyperlinks(self, data, args):
        if self.hyperlinksEnabled():
            action = self.getParameter("Hyperlinks:Action")
            report_name = self.getParameter("Hyperlinks:SubReport")
            if report_name == "":
                report_name = None
            if action == "":
                action = None  # default action of cdb.objects class will be used
            text = self.getParameter("Hyperlinks:TextToDisplay")
            if isinstance(data, ReportData):
                data.add_hyperlink(text, action=action, report_name=report_name, **args)
            else:
                data.add_hyperlinks(
                    text, action=action, report_name=report_name, **args
                )

    def getEnabledImageTypes(self):
        image_types_dict = {}
        for p in self.Parameters:
            if p.arg_name.startswith("Image") and p.arg_value:
                image_types = []
                for image_type in p.arg_value.split(","):
                    image_types.append(image_type.strip().lower())
                if image_types[0] in ["objecticon", "classicon", "statusicon"]:
                    attr_name = "cdbxml_%s" % image_types[0]
                else:
                    attr_name = re.sub(
                        r":|\\|/|<|>|\*|\?|\"|\||\.|,|;", "", p.arg_name
                    ).lower()
                    str_types = re.sub(
                        r":|\\|/|<|>|\*|\?|\"|\||\.|,|;", "", "_".join(image_types)
                    ).lower()
                    attr_name = "cdbxml_%s_%s" % (attr_name, str_types)
                image_types_dict[attr_name] = image_types
        return image_types_dict

    def addImagelinks(self, data, args):
        image_types_dict = self.getEnabledImageTypes()
        if image_types_dict:
            args["__image_types_dict__"] = image_types_dict
            if isinstance(data, ReportData):
                data.add_image(**args)
            else:
                data.add_images(**args)

    def extend_schema(self, t):
        for lt in self.getLongTexts():
            t.add_attr(lt, sqlapi.SQL_CHAR)
        if self.hyperlinksEnabled():
            t.add_attr("cdbxml_hyperlink", sqlapi.SQL_CHAR)
        for attr_name in list(self.getEnabledImageTypes()):
            t.add_attr(attr_name, sqlapi.SQL_CHAR)

    def accRight(self):
        # checked right on object level during export
        return self.getParameter("AccessControl:CheckedRight", "")

    def accFailBehavior(self):
        # behavior, if acc check fails. remove or obfuscate data.
        return self.getParameter("AccessControl:FailBehaviorJoinedObjects", "skip")

    def accMainObjectFailBehavior(self):
        return self.getParameter("AccessControl:FailBehavior", "skip row")

    def get_date_time_mode(self):
        """
        Returns the date time mode which can be defined by the provider parameter ``DateTimeMode``.
        Possible values are: ``UTC``, ``local time``, ``as configured``
        """
        return self.getParameter("DateTimeMode", DATETIME_MODE_UTC)

    event_map = {
        (("create", "copy"), "pre_mask"): ("setContext", "scan"),
        (("create", "modify", "copy"), "post_mask"): ("check_xsd_name", "check_card"),
        (("create", "copy"), "dialogitem_change"): "preset_xsd_name",
        (("create", "copy"), "post"): "create_parameters",
        (("create"), "post"): "add_public_grant",
    }


class XMLRuleBasedProvider(XMLDataProvider):
    __match__ = XMLDataProvider.source_type == "Rule"

    __parameters__ = {"OrderBy": ""}

    def getOrderBy(self):
        result = []
        order_by = self.getParameter("OrderBy", "")
        if order_by:
            result = [s.strip() for s in order_by.split(",")]
        return result

    def getArgumentDefs(self):
        args = self.Super(XMLRuleBasedProvider).getArgumentDefs()
        addtl_field_types = getAddtlFieldTypes(self)
        for fd in getUniqueFields(
            self.getClass().GetFields(addtl_field_type=addtl_field_types)
        ):
            args[fd.name] = fd.type
        order_by = self.getOrderBy()
        for i in range(len(order_by)):
            args["order_by%s" % (i + 1)] = sqlapi.SQL_CHAR
        return args

    def getData(self, parent_result, source_args, **kwargs):
        root_obj = None
        if isinstance(parent_result, ReportData):
            root_obj = parent_result.getObject()

        r = Rule.ByKeys(self.source)
        for v in r.getVariableNames(unknown_only=True):
            if v not in kwargs:
                if not root_obj or not root_obj.HasField(v):
                    kwargs[v] = root_obj[v]
                else:
                    raise RuntimeError(
                        "Variable %s defined in rule %s is not specified."
                        % (v, self.source)
                    )

        cls = self.getClass()
        order_by = []
        for o in self.getOrderBy():
            # FIXME: Sortierung aus kwargs hat Vorrang: order_by1, order_by2 ...
            if o[0] == "-":
                order_by.append(-cls.GetFieldByName(o[1:]))
            else:
                order_by.append(cls.GetFieldByName(o))

        maxrows_truncate = self.getMaxRowsTruncation()
        objs = r.getObjects(
            cls=cls, max_result=maxrows_truncate, order_by=order_by, **kwargs
        )
        result = ReportDataList(self, objs)
        return result

    def setup(self):
        if hasattr(self, "_cls"):
            return
        r = Rule.ByKeys(self.source)
        classes = r.getClasses()
        if len(classes) > 1:  # pylint: disable=R1720
            raise RuntimeError("Rule returns different types")
        elif len(classes) == 0:  # pylint: disable=R1720
            raise RuntimeError("Rule is empty")
        clazz = classes[0]
        self._cls = clazz

    def card(self):
        return N

    def getCallCard(self):
        return CARD_0_1


class XMLContextProvider(XMLDataProvider):
    __match__ = XMLDataProvider.source_type == "Context"

    def getData(self, objects, source_args, **kwargs):  # pylint: disable=W0237
        self._objects = objects
        if self.card() == 1:
            if len(objects) != 1:
                raise RuntimeError("Invalid cardinality")
            result = ReportData(self, objects[0])
        else:
            maxrows_truncate = self.getMaxRowsTruncation()
            if maxrows_truncate:
                objects = objects[:maxrows_truncate]
            result = ReportDataList(self, objects)
        return result

    def cleanup(self):
        self.Super(XMLContextProvider).cleanup()
        if hasattr(self, "_objects"):
            del self._objects

    def setup(self):
        if hasattr(self, "_cls"):
            return
        try:
            self._cls = tools.getObjectByName(self.source)
        except ImportError:
            raise RuntimeError("'%s' is not a valid cdb.objects class." % self.source)
        self._card = self.XMLSource.context_card
        if self._card == "1":
            self._card = 1
        elif self._card in ("N", "n"):
            self._card = N

    def card(self):
        self.setup()
        return self._card

    def getCallCard(self):
        return CARD_N

    def getArgumentDefs(self):
        args = self.Super(XMLContextProvider).getArgumentDefs()
        if self.card() == 1:
            cls = self.getClass()
            for k in cls.KeyNames():
                args[k] = cls.GetFieldByName(k).type
        return args

    def getArguments(self):
        args = {}
        if self.card() == 1:
            if not hasattr(self, "_objects"):
                raise RuntimeError("ContextProvider not initialized")
            if len(self._objects) == 1:
                for k, v in self._objects[0].KeyDict().items():
                    args["%s-%s" % (self.xsd_name.lower(), k)] = v
        return args


class XMLReferenceBasedProvider(XMLDataProvider):
    """
    Bei Verwendung von Beziehungen muss ein Kontext in cdbxml_source.context angegeben sein.
    """

    __match__ = XMLDataProvider.source_type == "Relationship"

    def getData(self, parent_result, source_args, **kwargs):
        root_obj = None
        if isinstance(parent_result, ReportData):
            root_obj = parent_result.getObject()
        if not root_obj:
            raise RuntimeError(
                "ReferenceBased providers need exactly one object as source object."
            )

        if not hasattr(root_obj, self.source):
            raise RuntimeError(
                "Invalid reference name '%s' for context '%s'"
                % (self.source, self.XMLSource.context)
            )
        result = None
        rs_result = getattr(root_obj, self.source)
        if self.card() == 1:
            result = ReportData(self, rs_result)
        else:
            maxrows_truncate = self.getMaxRowsTruncation()
            if maxrows_truncate:
                rs_result = rs_result[:maxrows_truncate]
            result = ReportDataList(self, rs_result)
        return result

    def setup(self):
        if hasattr(self, "_cls"):
            return
        clsname = self.context
        cls = tools.getObjectByName(clsname)
        ref = cls.GetReferences().get(self.source, None)
        if ref:
            self._cls = ref.GetTarget()
            self._card = ref.CARD
        else:
            raise RuntimeError(
                "Invalid reference name '%s' for context '%s'"
                % (self.source, self.XMLSource.context)
            )

    def card(self):
        if self.source:
            self.setup()
            return self._card
        else:
            return None

    def getCallCard(self):
        return CARD_1


class VirtualGroupedDataProvider(XMLDataProvider):
    __match__ = XMLDataProvider.source_type == "virtual"

    class GroupedData(XMLDataProvider):
        __match__ = XMLDataProvider.source_type == "virtual"

        def getCallCard(self):
            return CARD_1

        def card(self):
            return N

        def getSchema(self):
            return self._parent.make_xsd_type()

        def getData(self, parent_result, source_args, **kwargs):
            return self._grouped_data_dict[parent_result]

        def _setup(self, parent_provider):
            self._parent = parent_provider

        def setData(self, data, group_by):
            self._grouped_data = data.group(group_by)
            self._grouped_data_dict = {}
            for k, v in self._grouped_data:
                self._grouped_data_dict[k] = v
            return self._grouped_data

    _GroupedDataProvider = property(lambda self: self._buildVirtualSub())

    def getCallCard(self):
        return CARD_N

    def card(self):
        return N

    def getSchema(self):
        return self._schema

    def getData(self, parent_result, source_args, **kwargs):
        # group_by aus source_args hat Vorrang
        group_by = []
        for a in self._parent.getGroupByArgNames():
            addressed_name = "%s-%s" % (self._parent.xsd_name.lower(), a)
            if (addressed_name in source_args) and source_args[addressed_name]:
                group_by.append(source_args[addressed_name])
        if not group_by:
            group_by = self._parent.getGroupByArgs()

        grouped_data = self._GroupedDataProvider.setData(parent_result, group_by)
        groups = ReportDataList(self)
        for group, group_data in grouped_data:
            groups.append(group)
        return groups

    def _setup(self, parent_provider):
        self._parent = parent_provider
        self._schema = XSDType(N, provider=self)
        for a in parent_provider.getGroupByArgNames():
            self._schema.add_attr(a, sqlapi.SQL_CHAR)

    def virtualSubproviders(self):
        if self._GroupedDataProvider:
            return [self._GroupedDataProvider]
        else:
            return []

    def _buildVirtualSub(self):
        _provider_key = "a057c609-08ab-11de-8344-f944eb36b4b2"
        if _provider_key in self._refcache:
            p = self._refcache[_provider_key]
        else:
            p = self.GroupedData(
                name=self.name,
                xsd_name=self._parent.xsd_name + "_Grouped",
                source_type="virtual",
                parent_xsd_name=self.xsd_name,
            )
            p._setup(self._parent)
            self._refcache[_provider_key] = p
        return p


class XMLSimpleQueryProvider(XMLDataProvider):
    __match__ = XMLDataProvider.source_type == "SimpleQuery"

    __parameters__ = {"MaxRows": "0", "OrderBy": ""}

    def getOrderBy(self):
        result = []
        order_by = self.getParameter("OrderBy", "")
        if order_by:
            result = [s.strip() for s in order_by.split(",")]
        return result

    def getArgumentDefs(self):
        args = self.Super(XMLSimpleQueryProvider).getArgumentDefs()
        addtl_field_types = getAddtlFieldTypes(self)
        for fd in getUniqueFields(
            self.getClass().GetFields(addtl_field_type=addtl_field_types)
        ):
            args[fd.name] = fd.type
        order_by = self.getOrderBy()
        for i in range(len(order_by)):
            args["order_by%s" % (i + 1)] = sqlapi.SQL_CHAR
        return args

    def getData(self, parent_result, source_args, **kwargs):
        import cdbwrapc

        def build_expression(ti, name, value):
            if not value or name not in ti.attrname_list().split(","):
                return None
            if value == '=""':
                value = ""
            return cdbwrapc.build_statement(
                self.getClass().GetTableName(), name, value, 1
            )

        def build_cond(ti, **kwargs):
            exprs = []
            for name, value in kwargs.items():
                cond = build_expression(ti, name, value)
                if cond:
                    exprs.append(cond)
            cond = " and ".join(exprs)
            if not cond:
                cond = "1=1"
            return cond

        # build query condition
        cls = self.getClass()
        ti = util.tables[cls.GetTableName()]
        cond = build_cond(ti, **kwargs)

        # check MaxRows parameter
        maxrows = self.getParameter("MaxRows")
        if maxrows and int(maxrows) > 0:
            count = len(cls.Query(cond))
            if count > int(maxrows):
                raise ue.Exception("powerreports_max_rows_exceeded", count, maxrows)

        order_by = []
        for o in self.getOrderBy():
            # FIXME: Sortierung aus kwargs hat Vorrang: order_by1, order_by2 ...
            if o[0] == "-":
                order_by.append(-cls.GetFieldByName(o[1:]))
            else:
                order_by.append(cls.GetFieldByName(o))

        objs = cls.Query(cond, order_by=order_by)

        maxrows_truncate = self.getMaxRowsTruncation()
        if maxrows_truncate:
            objs = objs[: int(maxrows_truncate)]

        return ReportDataList(self, objs)

    def setup(self):
        if hasattr(self, "_cls"):
            return
        try:
            self._cls = tools.getObjectByName(self.source)
        except ImportError:
            raise RuntimeError("'%s' is not a valid cdb.objects class." % self.source)

    def card(self):
        return N

    def getCallCard(self):
        return CARD_0


class XMLGroupByProvider(XMLDataProvider):
    __match__ = XMLDataProvider.source_type == "GroupBy"

    __parameters__ = {"Group_By1": "", "Group_By2": "", "Group_By3": ""}

    def getArgumentDefs(self):
        result = {}
        for a in self.getGroupByArgNames():
            result[a] = sqlapi.SQL_CHAR
        return result

    def getGroupFuncs(self):
        """
        Get the group function definitions of the provider.
        At least the count(*) function must exist. For migration purposes
        this function is automatically defined when missing.
        """

        funcs = []
        for p in self.Parameters:
            if p.arg_name[0:8] == "Function" and p.arg_value:
                fct, attr = p.arg_value.split(":")
                if fct and attr:
                    funcs.append((fct, attr))
        if not funcs:
            funcs.append(("count", "*"))
        return funcs

    def getData(self, parent_result, source_args, **kwargs):
        group_by = []
        # group by aus kwargs hat Vorrang
        prefix = "group_by"
        for attr, value in kwargs.items():
            if attr.startswith(prefix) and value:
                group_by.append(value)
        if not group_by:
            for p in self.getGroupByArgNames():
                v = self.getParameter(p, dflt="")
                if v:
                    group_by.append(v)
        result = parent_result.group(group_by, self.getGroupFuncs())
        if self.card() == "N":
            maxrows_truncate = self.getMaxRowsTruncation()
            if maxrows_truncate:
                result._data = result._data[:maxrows_truncate]
        return result

    def card(self):
        return N

    def getCallCard(self):
        return CARD_N

    def getSchema(self):
        t = XSDType(N, provider=self)
        for a in self.getGroupByArgNames():
            t.add_attr(a, sqlapi.SQL_CHAR)

        for f in self.getGroupFuncs():
            if f[1] == "*":
                t.add_attr("%s" % f[0], sqlapi.SQL_INTEGER)
            else:
                t.add_attr("%s_%s" % (f[0], f[1]), sqlapi.SQL_INTEGER)

        return t

    def emit(self):
        return True


class XMLCustomProvider(XMLDataProvider):
    """Class for custom providers"""

    __match__ = XMLDataProvider.source_type == "CustomCode"

    XMLSource = Reference_1(fXMLSource, fXMLSource.name)

    def __impl(self):
        if not hasattr(self, "__impl__"):
            self.__impl__ = tools.getObjectByName(self.source)()
            self.__impl__.provider = self
        return self.__impl__

    def getData(self, parent_result, source_args, **kwargs):
        result = self.__impl().getData(parent_result, source_args, **kwargs)
        if self.card() == "N":
            maxrows_truncate = self.getMaxRowsTruncation()
            if maxrows_truncate:
                result._data = result._data[:maxrows_truncate]
        return result

    def getClass(self):
        if hasattr(self.__impl(), "getClass"):
            return self.__impl().getClass()
        else:
            return None

    def getSchema(self):
        if hasattr(self.__impl(), "getSchema"):
            return self.__impl().getSchema()
        else:
            return self.getClass()

    def getDefaultParameters(self):
        result = self.Super(XMLCustomProvider).getDefaultParameters()
        if hasattr(self.__impl(), "getDefaultParameters"):
            result.update(self.__impl().getDefaultParameters())
        return result

    def getArgumentDefs(self):
        args = self.Super(XMLCustomProvider).getArgumentDefs()
        if hasattr(self.__impl(), "getArgumentDefinitions"):
            args.update(self.__impl().getArgumentDefinitions())
        return args

    def card(self):
        if self.source:
            if hasattr(self.__impl(), "CARD"):
                card = self.__impl().CARD
                if card == "1":
                    card = 1
                return card
            else:
                raise RuntimeError("Cardinality not specified for custom data provider")
        else:
            return None

    def getCallCard(self):
        if hasattr(self.__impl(), "CALL_CARD"):
            return self.__impl().CALL_CARD
        else:
            # return CARD_0 ???
            raise RuntimeError(
                "Call cardinality not specified for custom data provider"
            )


def _wrap_CustomDataProvider(method):
    def callit(self, *args):
        return getattr(self.provider, method)(*args)

    return callit


class CustomDataProvider(object):
    # Base class for custom data provider implementations
    accRight = _wrap_CustomDataProvider("accRight")
    accFailBehavior = _wrap_CustomDataProvider("accFailBehavior")
    accMainObjectFailBehavior = _wrap_CustomDataProvider("accMainObjectFailBehavior")
    getParameter = _wrap_CustomDataProvider("getParameter")
    getLongTexts = _wrap_CustomDataProvider("getLongTexts")
    hyperlinksEnabled = _wrap_CustomDataProvider("hyperlinksEnabled")
    addHyperlinks = _wrap_CustomDataProvider("addHyperlinks")
    make_xsd_type = _wrap_CustomDataProvider("make_xsd_type")
    getRelation = _wrap_CustomDataProvider("getRelation")
    getJoinedFields = _wrap_CustomDataProvider("getJoinedFields")
    getVirtualFields = _wrap_CustomDataProvider("getVirtualFields")
    allAttributeTypesEnabled = _wrap_CustomDataProvider("allAttributeTypesEnabled")
    get_date_time_mode = _wrap_CustomDataProvider("get_date_time_mode")


# #### Classes for building report data


class ReportData(object):
    def __init__(self, provider, obj_or_record=None, longtexts=[], prefix=""):
        self._object = None
        self._record = None
        self._longtexts = longtexts
        self._single_attributes = {}
        self._prefix = prefix
        self._more_data = []
        self._granted = None
        self._provider = provider
        self._addtl_field_types = getAddtlFieldTypes(self._provider)
        self._parent_data = None
        self._image_files = []
        if self._provider:
            # add longtexts here by default if defined in provider arguments
            self._longtexts = list(set(self._longtexts + self._provider.getLongTexts()))
        if obj_or_record:
            if isinstance(obj_or_record, Object):
                self._object = obj_or_record
            else:
                self._record = obj_or_record
                if self._longtexts:
                    raise RuntimeError(
                        "Long texts cannot be resolved for record set based report "
                        "data."
                    )

    def access_granted(self, **kwargs):
        if self._granted is None:
            if not self._object:
                self._granted = True
            else:
                acc_right = ""
                if self._provider:
                    acc_right = self._provider.accRight()
                check_access_user = ""
                if "__sys_args__" in kwargs and "persno" in kwargs["__sys_args__"]:
                    # happens on (asynchronous) server side report generation
                    check_access_user = kwargs["__sys_args__"]["persno"]
                if not acc_right or self._object.CheckAccess(
                    acc_right, check_access_user
                ):
                    self._granted = True
                else:
                    # configured right not granted
                    self._granted = False
        return self._granted

    def isMainObject(self):
        return self._object is not None and not self._parent_data

    def getObject(self):
        return self._object

    def get_attr(self, k):
        result = None
        try:
            result = self[k]
        except KeyError:
            for d in self._more_data:
                result = d.get_attr(k)
                if result:
                    break
        return result

    def __add__(self, other):
        # usefull for combined data, e.g. joined queries
        self._more_data.append(other)
        other._parent_data = self
        return self

    def has_data(self):
        return (
            self._object or self._record or self._single_attributes or self._more_data
        )

    def _get_attributes(self, **kwargs):
        def add(k, v):
            if v not in [None, ""]:
                attrs[k.lower()] = v  # lowercase convention (E023618)

        attrs = {}
        if self._object:
            obfuscate = self._obfuscate(**kwargs)
            fds = getUniqueFields(
                self._object.GetFields(addtl_field_type=self._addtl_field_types)
            )
            for fd in fds:
                add(self._prefix + fd.name, self._obj_value(fd, obfuscate))
            if not obfuscate:
                for lt in self._longtexts:
                    add(self._prefix + lt, self._object.GetText(lt))
        if self._record:
            for k, v in self._record.items():
                add(self._prefix + k, v)
        for k, v in self._single_attributes.items():
            add(k, v)
        for d in self._more_data:
            attrs.update(d._get_attributes(**kwargs))
        return attrs

    def to_xml(self, parent, xsd_name=None, **kwargs):
        if not self.has_data() or (
            self.isMainObject()
            and self._provider
            and self._provider.accMainObjectFailBehavior() == "skip row"
            and not self.access_granted(**kwargs)
        ):
            return
        xsd_schema = None
        if self._provider:
            xsd_schema = self._provider.make_xsd_type()
        XMLObject(
            parent, xsd_name, self._get_attributes(**kwargs), xsd_schema
        )  # xml_obj =

    def _obfuscate(self, **kwargs):
        obfuscate = False
        if not self.access_granted(**kwargs):
            behavior = None
            if self._provider:
                if self.isMainObject():
                    behavior = self._provider.accMainObjectFailBehavior()
                else:
                    behavior = self._provider.accFailBehavior()
            if not behavior or behavior == "skip object":
                return
            else:
                obfuscate = True
        return obfuscate

    def _obj_value(self, fd, obfuscate):
        if fd.name not in self._object.KeyNames() and obfuscate:
            val = None
            if fd.type == sqlapi.SQL_CHAR:
                val = "####"
        else:
            val = self._object[fd.name]
        return val

    def __unicode__(self):
        s = ""
        if self._object:
            s = str(self._object)
        elif self._record:
            s = str(self._record)
        if self._single_attributes:
            s += "Single Attributes: %s" % ",".join(
                ["%s=%s" % (k, v) for k, v in self._single_attributes.items()]
            )
        if self._more_data:
            s += "More Data: %s" % ",".join([str(d) for d in self._more_data])
        return s

    def __str__(self):  # pylint: disable=E0307
        return str(self).encode("utf-8")

    def add_hyperlink(
        self,
        text_to_display,
        attr_name="cdbxml_hyperlink",
        action=None,
        report_name=None,
        **args
    ):
        if self._object:
            kwargs = {}
            if report_name:
                kwargs = {
                    "cdb::argument.cdbxml_report_skip_dlg": "1",
                    "cdb::argument.cdbxml_report_subreport": report_name,
                    "cdb::argument.cdbxml_report_lang": args.get(
                        "cdbxml_report_lang", CADDOK.get("ISOLANG", "de")
                    ),
                }
                if REPORT_FORMAT_ATTR in args:
                    kwargs["cdb::argument.cdbxml_report_format"] = args[
                        REPORT_FORMAT_ATTR
                    ]
                if REPORT_ACTION_ATTR in args:
                    kwargs["cdb::argument.cdbxml_report_action"] = args[
                        REPORT_ACTION_ATTR
                    ]

            self[attr_name] = MakeReportURL(
                self._object,
                action,
                text_to_display,
                report_name,
                self._provider,
                **kwargs
            )

    def add_image(self, image=None, attr_name="cdbxml_image", **args):
        if image:
            if isinstance(image, CDB_File):
                self[attr_name] = MakeImageURL(image.cdbf_name, **args)
                if image not in self._image_files:
                    self._image_files.append(image)
            elif False:  # TODO: image == cdb_object_id  # pylint: disable=W0125
                fobj = CDB_File.ByKeys(cdb_object_id=image)
                self[attr_name] = MakeImageURL(fobj.cdbf_name, **args)
                if fobj not in self._image_files:
                    self._image_files.append(fobj)
            elif _isSupportedUriPath(image):
                # URI types ('file:', 'http:') allow to NOT
                # include the file in the zip (performance boost?)
                self[attr_name] = MakeImageURL(image, **args)
            elif os.path.exists(image):
                self[attr_name] = MakeImageURL(image, **args)
                if image not in self._image_files:
                    self._image_files.append(image)
            else:
                raise Exception(  # pylint: disable=W0719
                    "Unsupported image type: %s" % image
                )
        elif (  # pylint: disable=R1702
            "__image_types_dict__" in list(args)
        ) and self._object:
            image_types_dict = args["__image_types_dict__"]
            for (
                attr_name,  # pylint: disable=R1704
                image_types,
            ) in image_types_dict.items():
                if "objecticon" in image_types:
                    # TODO?
                    #  "self._object.GetObjectIcon()" would return something like:
                    #  'BASE_URI/byname/icon/OLE Application Icon/?erzeug_system=MS-Word'
                    #  ..but officelink would need to log in via cdbgate to get the stuff
                    # TEST-HACK:
                    # if hasattr(self._object, 'erzeug_system'):
                    #     ico_bname = '%s.png' % self._object.erzeug_system
                    #     ico_fname = os.path.join(CADDOK.HOME, 'design', 'icons', 'erzeug_system',
                    #                              ico_bname)
                    #     if os.path.exists(ico_fname):
                    #         self[attr_name] = MakeImageURL(ico_bname, **args)
                    #         if not ico_fname in self._image_files:
                    #            self._image_files.append(ico_fname)
                    pass
                elif "classicon" in image_types:
                    # TODO?
                    pass
                elif "statusicon" in image_types:
                    # TODO?
                    pass
                elif hasattr(self._object, "Files") or hasattr(
                    self._object, "Documents"
                ):
                    if hasattr(self._object, "Files"):
                        for fobj in self._object.Files:
                            if (
                                os.path.splitext(fobj.cdbf_name)[1].lower()
                                in image_types
                            ):
                                self[attr_name] = MakeImageURL(fobj.cdbf_name, **args)
                                if fobj not in self._image_files:
                                    self._image_files.append(fobj)
                                break
                    else:
                        for doc in self._object.Documents:
                            _break = False
                            for fobj in doc.Files:
                                if (
                                    os.path.splitext(fobj.cdbf_name)[1].lower()
                                    in image_types
                                ):
                                    self[attr_name] = MakeImageURL(
                                        fobj.cdbf_name, **args
                                    )
                                    if fobj not in self._image_files:
                                        self._image_files.append(fobj)
                                    _break = True
                                    break
                            if _break:
                                break
                else:
                    raise Exception(  # pylint: disable=W0719
                        "Unsupported image type: %s" % image_types
                    )

    def export_images(self, bname, myzip):
        if self._image_files:
            for f in self._image_files:
                if isinstance(f, CDB_File):
                    target = "%s.%s" % (bname, f.cdbf_name)
                    f.checkout_file(target)
                    myzip.write(target, os.path.basename(target))
                    os.remove(target)
                elif os.path.exists(f):
                    target = "%s.%s" % (bname, os.path.basename(f))
                    myzip.write(f, os.path.basename(target))

    def add_joined_fields(self, join_name):
        if self._object:
            for f in self._provider.getJoinedFields(join_name):
                self[f] = self._object[f]

    def add_virtual_fields(self):
        if self._object:
            for f in self._provider.getVirtualFields():
                self[f] = self._object[f]

    # Dictionary behaviour
    def has_key(self, k):
        return k in self.keys()

    def keys(self):
        keys = []
        if self._object:
            keys += self._object.GetFieldNames(addtl_field_type=self._addtl_field_types)
        if self._record:
            keys += list(self._record)
        keys += list(self._single_attributes)
        return keys

    def values(self):
        values = []
        if self._object:
            values += self._object.values(addtl_field_type=self._addtl_field_types)
        if self._record:
            values += list(self._record.values())
        values += list(self._single_attributes.values())
        return values

    def items(self):
        items = []
        if self._object:
            items += self._object.items(addtl_field_type=self._addtl_field_types)
        if self._record:
            items += list(self._record.items())
        items += list(self._single_attributes.items())
        return items

    def __getitem__(self, k):
        result = None
        if self._object and self._object.HasField(
            k, addtl_field_type=self._addtl_field_types
        ):
            result = self._object[k]
        elif self._record and k in self._record.keys():
            result = self._record[k]
        elif k in self._single_attributes:
            result = self._single_attributes[k]
        else:
            raise KeyError(k)
        if result is None:
            result = ""
        return result

    def __setitem__(self, k, v):
        self._single_attributes[k] = v


def _wrap_ReportDataList(method):
    def callit(self, *args, **kwargs):
        return getattr(self._data, method)(*args, **kwargs)

    return callit


class ReportDataList(object):
    def __init__(self, provider, rset_or_objects=None, longtexts=[]):
        self._data = []
        self._provider = provider
        if self._provider:
            # add longtexts here by default if defined in provider arguments
            longtexts = list(set(longtexts + self._provider.getLongTexts()))
        if rset_or_objects:
            for x in rset_or_objects:
                self.append(ReportData(self._provider, x, longtexts))

    def to_xml(self, parent, xsd_name, **kwargs):
        if not self._data:
            return ""
        the_list = XMLList(parent, xsd_name)
        for d in self._data:
            d.to_xml(the_list, "List", **kwargs)

    def __add__(self, other):
        # other may be another ReportDataList, a ReportData Object, a sqlapi.Record,
        # a cdb.objects Object, a sqlapi.RecordSet2 or a list of cdb.object Objects.
        if isinstance(other, ReportDataList):
            for d in other._data:
                self.append(d)
        elif isinstance(other, ReportData):  # pylint: disable=R1701
            self.append(other)
        elif isinstance(other, Object) or isinstance(  # pylint: disable=R1701
            other, sqlapi.Record
        ):
            self.append(ReportData(self._provider, other))
        else:
            # RecordSet2 or list of cdb.object Objects
            for o in other:
                self.append(ReportData(self._provider, o))
        return self

    def getObjects(self):
        return [d._object for d in self._data if d._object]

    # For cdb.objects based providers only, if group_by contains rules.
    # Returns a new ReportDataList containing grouped data.
    # Grouping is defined by a given attribute list.
    # Thinkabout: bei hierarchischen Daten mglichkeit einbauen, dass nur TopLevel gruppiert wird.
    def group(self, group_by, group_funcs=None):
        def add(data, k, sort=""):

            if k not in group_dict:
                group_dict[k] = ReportDataList(None)
                if not sort:
                    sort = k
                sort_dict[sort] = k
            group_dict[k].append(data)

        def match_rules(rule_names, data, start_index=0):
            match = False
            curr_index = start_index
            for r in rule_names[start_index:]:
                rule = Rule.ByKeys(r)
                if data._object.MatchRule(rule):
                    val = rule.description.split("\n")[
                        0
                    ]  # 1. Zeile der Beschreibung der Rule
                    sort = "%d" % curr_index
                    match = True
                    break
                curr_index += 1
            if not match:
                val = "Other"
                sort = "999"
            return (val, sort, curr_index + 1)

        def group_by_rules(data):
            for d in data:
                more_rules = True
                rule_index = 0
                while more_rules:
                    attrs = []
                    sort_str = ""
                    for a in groups:
                        if isinstance(a, str):
                            val = d.get_attr(a)
                            attrs.append(val)
                            sort_str += val
                        else:
                            attr, sort, rule_index = match_rules(a, d, rule_index)
                            attrs.append(attr)
                            sort_str += sort
                            if rule_index >= len(a):
                                more_rules = False
                    add(d, tuple(attrs), sort_str)

        def group_by_attributes(data):
            for d in data:
                add(d, tuple([d.get_attr(a) for a in groups]))  # pylint: disable=R1728

        def to_float(x):
            result = None
            try:
                result = float(x)
            except Exception:  # pylint: disable=W0718,W0703 #nosec
                pass
            return result

        if not group_by:
            return None
        # a group_by element can be an attribute or a list of rules defining data ranges
        groups = []
        with_rules = False

        for a in group_by:
            if a.startswith("("):
                a = a.replace("(", "").replace(")", "")
                rule_names = [s.strip() for s in a.split(",")]
                for name in rule_names:
                    rule = Rule.ByKeys(name)
                    if not rule:
                        misc.cdblogv(
                            misc.kLogMsg,
                            1,
                            "Invalid rule name in group by expression: " "'%s'" % name,
                        )
                        return None
                    rule.Lock()
                groups.append(rule_names)
                with_rules = True
            else:
                groups.append(a)
        # build grouping
        group_dict = {}
        sort_dict = {}
        if with_rules:
            group_by_rules(self._data)
        else:
            group_by_attributes(self._data)

        if group_funcs:
            # build ReportDataList sorted by group_by definition
            result = ReportDataList(None)
            keys = list(sort_dict)
            keys.sort()
            for k in keys:
                values = sort_dict[k]
                d = ReportData(None)
                # group by ...
                for i in range(len(values)):  # pylint: disable=C0200
                    d["group_by%s" % (i + 1)] = values[i]
                # group functions
                for f in group_funcs:
                    fct = f[0]
                    attr = f[1]
                    fresult = 0.0
                    if fct == "count":
                        fresult = len(group_dict[values])
                    else:
                        flist = [
                            to_float(i[attr])
                            for i in group_dict[values]
                            if to_float(i[attr]) is not None
                        ]
                        if fct == "sum":
                            fresult = sum(flist)
                        elif fct == "max":
                            fresult = max(flist)
                        elif fct == "min":
                            fresult = min(flist)
                        elif fct == "average":
                            fresult = sum(flist) / len(flist)
                    if attr == "*":
                        d[fct] = fresult
                    else:
                        d["%s_%s" % (fct, attr)] = fresult
                result.append(d)
        else:
            # build a sorted list of tuples containg a ReportData object with the group by
            # attributes and values and a ReportDataList with the matching objects.
            result = []
            keys = list(sort_dict)
            keys.sort()
            for k in keys:
                group_key = sort_dict[k]
                data_list = group_dict[group_key]
                d = ReportData(None)
                for i in range(len(group_key)):  # pylint: disable=C0200
                    d["group_by%s" % (i + 1)] = group_key[i]
                result.append((d, data_list))
        return result

    def add_hyperlinks(
        self,
        text_to_display,
        attr_name="cdbxml_hyperlink",
        action=None,
        report_name=None,
        **args
    ):
        for d in self._data:
            d.add_hyperlink(text_to_display, attr_name, action, report_name, **args)

    def add_images(self, image=None, attr_name="cdbxml_image", **args):
        for d in self._data:
            d.add_image(image, attr_name, **args)

    def export_images(self, fname, myzip):
        for d in self._data:
            d.export_images(fname, myzip)

    def add_joined_fields(self, join_name):
        for d in self._data:
            d.add_joined_fields(join_name)

    def add_virtual_fields(self):
        for d in self._data:
            d.add_virtual_fields()

    def __str__(self):
        return "\n".join([str(d) for d in self._data])

    # __add__ = _wrap_ReportDataList('__add__')
    # __str__ = _wrap_ReportDataList('__str__')
    __contains__ = _wrap_ReportDataList("__contains__")
    __delitem__ = _wrap_ReportDataList("__delitem__")
    __delslice__ = _wrap_ReportDataList("__delslice__")
    __eq__ = _wrap_ReportDataList("__eq__")
    __ge__ = _wrap_ReportDataList("__ge__")
    __getitem__ = _wrap_ReportDataList("__getitem__")
    __getslice__ = _wrap_ReportDataList("__getslice__")
    __gt__ = _wrap_ReportDataList("__gt__")
    __imul__ = _wrap_ReportDataList("__imul__")
    __le__ = _wrap_ReportDataList("__le__")
    __lt__ = _wrap_ReportDataList("__lt__")
    __mul__ = _wrap_ReportDataList("__mul__")
    __ne__ = _wrap_ReportDataList("__ne__")
    __repr__ = _wrap_ReportDataList("__repr__")
    __rmul__ = _wrap_ReportDataList("__rmul__")
    __setitem__ = _wrap_ReportDataList("__setitem__")
    __setslice__ = _wrap_ReportDataList("__setslice__")
    __len__ = _wrap_ReportDataList("__len__")
    append = _wrap_ReportDataList("append")
    count = _wrap_ReportDataList("count")
    extend = _wrap_ReportDataList("extend")
    index = _wrap_ReportDataList("index")
    insert = _wrap_ReportDataList("insert")
    pop = _wrap_ReportDataList("pop")
    remove = _wrap_ReportDataList("remove")
    reverse = _wrap_ReportDataList("reverse")
    sort = _wrap_ReportDataList("sort")


# ##### XML Classes
class XMLElement(object):
    def __init__(self, parent):
        self._elements = []
        self.parent = parent
        if self.parent:
            self.lev = self.parent.lev + 1
            self.parent.add(self)
        else:
            self.lev = 0

    def add(self, xml_element):
        self._elements.append(xml_element)

    def __str__(self):
        f = StringIO()
        self.write(f)
        s = f.getvalue()
        f.close()
        return s


class XMLDocument(XMLElement):
    def __init__(self):
        super(XMLDocument, self).__init__(None)

    def write(self, f):
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
        f.write('<Root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n')
        for e in self._elements:
            e.write(f)
        f.write("</Root>\n")


class XMLList(XMLElement):
    def __init__(self, parent, name):
        super(XMLList, self).__init__(parent)
        self.name = name

    def write(self, f):
        f.write("%s<%s>\n" % (self.lev * "  ", self.name))
        for e in self._elements:
            e.write(f)
        f.write("%s</%s>\n" % (self.lev * "  ", self.name))


class XMLObject(XMLElement):
    def __init__(self, parent, name, attributes, schema):
        super(XMLObject, self).__init__(parent)
        self.name = name
        self.attrs = {}
        for k, v in attributes.items():
            # lowercase convention (E023618)
            self.attrs[k.lower()] = v
        self.schema = schema

    def write(self, f):
        def value(k, v):
            if self.schema:
                t = self.schema.getType(k)
                # convert dates to XSD date formats
                if t == "date":
                    if isinstance(v, str):
                        v = from_legacy_date_format(v)
                    v = v.isoformat().split("T")[0]  # "%Y-%m-%d"
                elif t == "dateTime":
                    if isinstance(v, str):
                        v = from_legacy_date_format(v)
                    if self.schema.use_local_time(k):
                        v = v + datetime.timedelta(minutes=misc.getClientUTCOffset())

                    v = v.isoformat().split(".")[0]  # "%Y-%m-%dT%H:%M:%S"

            if isinstance(v, str):
                # FIXME: Workaround for E019017: 'Probleme mit PowerReports und
                # Sonderzeichen': Invalid Characters (because we have read an
                # undefined binary stream from the database) will be replaced
                # with the official Unicode replacement character, U+FFFD.
                # Try it character wise, maybe the user can guess the
                # missing characters.
                #
                # errors='replace' works only with string objects, otherwise we
                # get an TypeError. :-(
                result = ""
                for c in v:
                    try:
                        result += str(c)
                    except UnicodeDecodeError:
                        result += str(c, errors="replace")
                v = result
            else:
                v = str(v)
            v = RE_INVALID_XML_CHRS.sub("", v)
            return (
                v.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace("\n", "&#xA;")
                .replace("\r", "&#xD;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
                .replace("\t", "&#x9;")
            )

        f.write(
            "%s<%s %s/>\n"
            % (
                self.lev * "  ",
                self.name,
                " ".join(
                    ['%s="%s"' % (k, value(k, v)) for k, v in list(self.attrs.items())]
                ),
            )
        )


# #### XSD Schema Classes


class XSDSchema(object):

    SCHEMA = """<?xml version='1.0' encoding='UTF-8'?>
<xsd:schema elementFormDefault=\"unqualified\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\">
    <xsd:element name=\"Root\" type=\"RootType\"/>
    <xsd:complexType name=\"RootType\">
        <xsd:all>%s
        </xsd:all>
    </xsd:complexType>%s
</xsd:schema>
"""

    def __init__(self):
        self._xsd_types = {}
        self._elements = []

    def __str__(self):
        return self.SCHEMA % (
            " ".join([str(x) for x in self._elements]),
            " ".join([str(x) for x in list(self._xsd_types.values())]),
        )

    def add(self, xsd_type, element_name):
        if xsd_type.id not in self._xsd_types:
            self._xsd_types[xsd_type.id] = xsd_type
        self._elements.append(XSDElement(element_name, xsd_type.id))

    @classmethod
    def is_valid_xsd_name(cls, name):
        # Returns true, if the passed name is a valid xsd element name
        return not RE_INVALID_XML_SCHEMA_NAME_CHRS.search(name)

    @classmethod
    def make_valid_xsd_name(cls, name):
        return re.sub(r"^(\d|\W)*|\W", "", name)


class XSDElement(object):
    def __init__(self, xsd_name, xsd_type_id):
        self.xsd_name = xsd_name
        self.xsd_type_id = xsd_type_id

    def __str__(self):
        return '\n%s<xsd:element name="%s" type="%s"/>' % (
            12 * " ",
            self.xsd_name,
            self.xsd_type_id,
        )


class XSDType(object):
    XSD_TYPE_NEW = {
        N: """
    <xsd:complexType name=\"%s\">
        <xsd:sequence>
            <xsd:element name=\"List\" minOccurs=\"0\" maxOccurs=\"unbounded\">
                <xsd:complexType>%s
                </xsd:complexType>
            </xsd:element>
        </xsd:sequence>
    </xsd:complexType>
    """,
        1: """
    <xsd:complexType name=\"%s\">%s
    </xsd:complexType>
    """,
    }

    XSD_TYPE = {
        N: """
    <xsd:complexType name=\"%s\">
        <xsd:sequence>
            <xsd:element name=\"List\" minOccurs=\"0\" maxOccurs=\"unbounded\">
                <xsd:complexType>
                    <xsd:sequence>%s
                    </xsd:sequence>
                </xsd:complexType>
            </xsd:element>
        </xsd:sequence>
    </xsd:complexType>
    """,
        1: """
    <xsd:complexType name=\"%s\">
        <xsd:sequence>%s
    </xsd:sequence>
    </xsd:complexType>
    """,
    }

    # SQL to XSD type mapping
    SQL_TO_XSD_TYPE = {
        sqlapi.SQL_INTEGER: "integer",
        sqlapi.SQL_FLOAT: "float",
        sqlapi.SQL_DATE: "date",
        sqlapi.SQL_CHAR: "string",
    }

    XSD_TYPES = ["string", "integer", "float", "date", "dateTime"]

    def __init__(self, card, cls_or_rel=None, prefix="", provider=None):
        import cdbwrapc

        myid = cdbuuid.create_uuid()
        self.id = "cdb_%s" % (myid.replace("-", ""))
        self.prefix = prefix
        self.provider = provider
        self.card = card
        if self.card == "1":
            self.card = 1

        self.__fields = {}
        self._datefields_with_local_time = []

        if cls_or_rel:  # pylint: disable=R1702
            if isinstance(cls_or_rel, str):
                ti = util.tables[cls_or_rel]
                for ci in ti:
                    with_time = False
                    if ci.type() == sqlapi.SQL_DATE:
                        adef = cdbwrapc.getAttributeDefByTableAndColumn(
                            cls_or_rel, ci.name()
                        )
                        if adef:
                            with_time = adef.display_time()
                            if with_time and adef.use_local_time():
                                self._datefields_with_local_time.append(ci.name())
                    self.add_attr(
                        "%s%s" % (self.prefix, ci.name()),
                        self.sql_to_xsd_type(ci.type(), with_time),
                    )
            else:
                addtl_field_types = getAddtlFieldTypes(self.provider)
                fields = getUniqueFields(
                    cls_or_rel.GetFields(addtl_field_type=addtl_field_types)
                )
                for fd in fields:
                    with_time = False
                    if fd.type == sqlapi.SQL_DATE:
                        cdef = cls_or_rel._getClassDef()
                        if cdef:
                            adef = cdef.getAttributeDefinition(fd.name)
                            if adef:
                                with_time = adef.display_time()
                                if with_time and adef.use_local_time():
                                    self._datefields_with_local_time.append(fd.name)
                    self.add_attr(
                        "%s%s" % (self.prefix, fd.name),
                        self.sql_to_xsd_type(fd.type, with_time),
                    )

        self.joined = []

    def sql_to_xsd_type(self, sql_type, date_with_time=False):
        xsd_type = self.SQL_TO_XSD_TYPE[sql_type]
        if sql_type == sqlapi.SQL_DATE and date_with_time:
            xsd_type = "dateTime"
        return xsd_type

    def use_local_time(self, datefield_name):
        date_time_mode = DATETIME_MODE_UTC
        if self.provider:
            date_time_mode = self.provider.get_date_time_mode()
        return date_time_mode == DATETIME_MODE_LOCAL_TIME or (
            date_time_mode == DATETIME_MODE_AS_CONFIGURED
            and datefield_name in self._datefields_with_local_time
        )

    def has_key(self, k):
        return k in self.keys()

    def keys(self):
        return list(self.__fields)

    def getType(self, k):
        ret = self.__fields.get(k)
        if not ret:
            for j in self.joined:
                ret = j.getType(k)
                if ret:
                    break
        return ret

    def __add__(self, other):
        for k in other.keys():
            if k in self.keys():
                raise ue.Exception("powerreports_xsd_name_not_unique", k)
        self.joined.append(other)
        return self

    def add_attr(self, name, mytype):
        name = name.lower()  # lowercase convention (E023618)
        if not RE_VALID_XML_ATTR_NAME_CHRS.search(name):
            raise ue.Exception("powerreports_invalid_xsd_name", name)
        if name in self.keys():
            raise RuntimeError("Name '%s' is not unique within xsd schema." % name)
        mytype = self.SQL_TO_XSD_TYPE.get(mytype, mytype)
        if mytype not in self.XSD_TYPES:
            raise RuntimeError(
                "Unsupported XSD type '%s'. Supported XSD types are: %s"
                % (mytype, ", ".join(self.XSD_TYPES))
            )
        self.__fields[name] = mytype

    def add_joined_fields(self, provider, join_name):
        for field_name in provider.getJoinedFields(join_name):
            f = provider.getClass().GetFieldByName(field_name)
            self.add_attr(f.name, f.type)

    def add_virtual_fields(self, provider):
        for field_name in provider.getVirtualFields():
            f = provider.getClass().GetFieldByName(field_name)
            self.add_attr(f.name, f.type)

    def __elements(self):
        def make_element(key, mytype):
            if self.card == 1:
                indent = 12
            else:
                indent = 24
            return '\n%s<xsd:attribute name="%s" type="xsd:%s" form="unqualified"/>' % (
                indent * " ",
                key,
                mytype,
            )

        rows = ""
        keys = list(self.keys())
        keys.sort()
        for k in keys:
            rows += make_element(k, self.getType(k))

        for t in self.joined:
            rows += t.__elements()
        return rows

    def __str__(self):
        return self.XSD_TYPE_NEW[self.card] % (self.id, self.__elements())


class XMLProviderRegistry(Object):
    __maps_to__ = "cdbxml_provider_reg"

    _scanned = False

    @classmethod
    def _Scan(cls):
        names = cls.Query().fqpyname
        found_names = []
        for modname in list(sys.modules):
            mod = tools.getModuleHandle(modname)
            if not mod:
                continue

            items = [
                (name, value, "%s.%s" % (modname, name))
                for name, value in mod.__dict__.items()
                if hasattr(value, "__module__")
                and value.__module__ == modname
                and hasattr(value, "__class__")
                and value.__class__ == type
                and CustomDataProvider in value.__mro__
            ]
            for name, obj, longname in items:
                if longname not in found_names:
                    found_names.append(longname)
                    if longname not in names and name != "CustomDataProvider":
                        XMLProviderRegistry.Create(fqpyname=longname)
        if found_names:
            for n in names:
                if n not in found_names:
                    sqlapi.SQLdelete(
                        "from cdbxml_provider_reg where fqpyname = '%s'" % (n)
                    )

    @classmethod
    def Scan(cls):
        if cls._scanned:
            return
        with transaction.Transaction():
            cls._Scan()
            cls._scanned = True


if __name__ == "__main__":

    # some tests
    # preconditions:
    # -default demo data is installed
    # -both report servers are running

    # "Mitarbeiterauslastung" (synchronous as xlsx)
    print(
        WithPowerReports.generate_report(
            {
                "name": "PersonnelLoad",
                "report_title": "Mitarbeiterauslastung",
                "iso_code": "de",
            },
            dlg_args={"personnelloadmonthly-start_date": "12.12.2012"},
        )
    )

    # "Stücklistenreport" (asynchronous as pdf via email)
    from cs.vp.items import Item

    items = Item.Query("benennung='Sitz_Unterkonstruktion'")
    print(
        WithPowerReports.generate_report(
            {
                "name": "HierarchicalBOM",
                "report_title": "Strukturstückliste",
                "iso_code": "de",
            },
            report_action=REPORT_EMAIL,
            report_format="PDF",
            objects=items,
            dlg_args={"hierarchicalbom-depth": "1"},
        )
    )
