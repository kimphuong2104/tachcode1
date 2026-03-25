# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module wsmconnects

This is the documentation for the wsmconnects module.
"""

from __future__ import absolute_import

# Exported objects
__all__ = []

__docformat__ = "restructuredtext en"
__revision__ = "$Id: python_template 4042 2019-08-27 07:30:13Z js $"

import json
import logging
from cdb import sig
from cdb import auth
from lxml import etree as ET
from cs.office.documentvariables import OfficeLinkContent, DocumentVariables
from cs.wsm.pkgs.pkgsutils import getAppinfoContent

_Logger = logging.getLogger(__name__)


@sig.connect("ws_office_write")
def ws_office_write_handler(doc, office_vars):
    """
    This function analyses the office_vars and writes given values
    into relation objects. Values for this (the current document)
    are returned to the caller

    :param doc: Document Object
    :param office_vars: dict with id, value of existing office_vars in document
    :return dict with values for current document
    """
    ctx = OfficeLinkContent(doc, office_vars)
    # First parameter is originially the called component.
    # This is not available here.
    sig.emit("officelink_metadata_write")(None, ctx)
    retDocVars = DocumentVariables.auto_write(ctx, auth.login)
    if retDocVars is None:
        retDocVars = dict()
    return retDocVars


@sig.connect("ws_office_read_from_appinfo")
def ws_office_read_from_appinfo(doc, office_file=None):
    if office_file is None:
        primary_files = doc.getPrimaryFiles()
        if primary_files:
            for prim in primary_files:
                if prim.cdbf_type == doc.erzeug_system:
                    office_file = prim
                    break
            # may be container, so take first one
            if office_file is None:
                office_file = primary_files[0]
                _Logger.debug("Multiple primary files. Using : %s", office_file.cdbf_name)

    if office_file is not None:
        office_vars = _read_office_vars_from_appinfo(doc, office_file)
        _Logger.debug("Office-Vars from appinfo : %s", office_vars)
    else:
        office_vars = dict()

    ctx = OfficeLinkContent(doc, office_vars)
    sig.emit("officelink_metadata_read")(None, ctx)
    DocumentVariables.auto_fill(ctx, auth.login)
    res_vars = ctx.document_variables
    _Logger.debug("Office-Vars from auto_fill: %s", res_vars)
    # create talkapi message
    talk_msg = _create_talkapi_msg(res_vars)
    return talk_msg


@sig.connect("ws_office_read")
def readOfficeVars(doc, office_read_vars):
    """
    Read values for given variable config from given document
    INPUT: office_read_vars = {u'cdb.r.this.titel.1.string': None,
                               u'cdb.r.this.z_bemerkung.1.string': None}
    OUTPUT: u'office2@1@office_vars@{"cdb.r.this.titel.1.string": ["TEST_TITEL"], \
                               "cdb.r.this.z_bemerkung.1.string": ["TEST_BEMERKUNG"]}@OFFICEVARS'
             assuming doc.titel == TEST_TITEL and doc.z_bemerkung == TEST_BEMERKUNG
    :param doc: Document instance
    :param office_read_vars: dict office variable config => value
    :return:
    """
    ctx = OfficeLinkContent(doc, office_read_vars)
    sig.emit("officelink_metadata_read")(None, ctx)
    DocumentVariables.auto_fill(ctx, auth.login)
    res_vars = ctx.document_variables
    # create talkapi message
    talk_msg = _create_talkapi_msg(res_vars)
    return talk_msg


def _read_office_vars_from_appinfo(doc, office_file):
    """
    get appinfo for officeFile and read office parameter
    only returns read-variables
    """
    office_vars = dict()
    content = getAppinfoContent(doc.Files)
    if content:
        root = ET.fromstring(content)
        for officeVar in root.findall("officeconfig/officeparam"):
            var_id = officeVar.get("id").strip()
            if var_id:
                as_list = var_id.split(".")
                if len(as_list) > 3 and as_list[0] == "cdb":
                    if as_list[1].find("r") >= 0:
                        office_vars[var_id] = None
    return office_vars


def _create_talkapi_msg(office_vars):
    """
    create @21-Talkapi Message for Office
    Transfer json in single value
    office2@1@office_vars@json.dumps(office_vars)@OFFICEVARS@
    office_vars dict id to values:
    values = string fuer cardinality 1 or list for N
    """
    talk_list = [u"office2",
                 u"1",
                 u"office_vars",
                 json.dumps(office_vars),
                 u"OFFICEVARS"]
    return u"@".join(talk_list)
