# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Helper methods for workspaces server package
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import itertools
import logging
from lxml import etree as ElementTree

from cdb import ue
from cdb.objects import NULL

from cdb.objects.cdb_file import cdb_folder_item

# for backwards-compatible export


def grouper(n, iterable):
    """
    Yields n length chunks from given iterable

    https://docs.python.org/2/library/itertools.html
    https://stackoverflow.com/questions/8991506/iterate-an-iterator-by-chunks-of-n-in-python
    """
    it = iter(iterable)
    if n is not None:
        n = int(n)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


def toStringTuple(iterable):
    """
    Makes sql string tuple
    """
    strTuple = "','".join(iterable)
    strTuple = "('%s')" % strTuple
    return strTuple


def null2EmptyString(val):
    """
    Convert a NULL value to an empty string.

    Return an empty string, if val is cdb.objects.NULL, else return val.
    """
    return val if val is not NULL else ""


def getCdbClassname(obj):
    """
    Return the cdb classname for the passed object.

    This has to be handled differently since Frame
    objects do not have an attribute "cdb_classname".
    """
    try:
        cdbClassname = obj.cdb_classname
    except (AttributeError, KeyError):
        try:
            cdbClassname = obj.__classname__
        except (AttributeError, KeyError):
            # e.g. WsDocuments object handle
            cdbClassname = obj.getClassDef().getClassname()
    return cdbClassname


def tr(msg):
    """
    Dummy translate routine. Enables qt translator to
    extract the message strings from the source codes.
    """
    return msg


def createErrorElement(msg, args=None):
    """
    Creates an XML-error element.

    :param msg: label for message
    :param args: tuple
    :return: ElementTree.Element
    """
    logging.info("Returning Error: %s %s", msg, args)
    return createResultElement("ERROR", msg, args)


def createResultElement(msgType, msg, args=None):
    if args is None:
        args = []
    error = ElementTree.Element(msgType)
    msgEx = ue.Exception(msg, *args)
    error.text = u"{}".format(msgEx)
    return error


def createInfoElement(msg, args=None):
    """
    Creates an XML info element.

    :param msg: label for message
    :param args: tuple
    :return: ElementTree.Element
    """
    logging.info("Returning Info: %s %s", msg, args)
    return createResultElement("INFO", msg, args)


def getAppinfoContent(files):
    """
    If the document has exactly one primary file and this file has a .appinfo
    file: return its content.

    :param files: cdb_file_base-derived objects of document
    :return: byte string or None
    """
    content = None
    appinfos = dict()
    primary = None
    for f in files:
        if f.cdbf_type == "Appinfo":
            appinfos[f.cdb_belongsto] = f

        elif f.cdbf_primary == "1":
            if primary is None:
                primary = f
            else:
                return None
    if primary is not None and primary.cdb_classname == "cdb_file":
        appinfo = appinfos.get(primary.cdb_wspitem_id)
        if appinfo:
            content = appinfo.get_content()
    return content


def getAppinfoContentForFile(files, primary_file):
    """
    If given file has a .appinfo file return its content.

    :param files: cdb_file_base-derived objects of document
    :param primary_file: CDB_File object to obtain appinfo content for
    :return: byte string or None
    """
    content = None
    appinfo = None
    for f in files:
        if f.cdbf_type == "Appinfo" and f.cdb_belongsto == primary_file.cdb_wspitem_id:
            appinfo = f
            break
    if appinfo:
        content = appinfo.get_content()
    return content


def getRelPath(f):
    """
    Returns relative path for file record. Uses unix separators.
    """
    relPath = f.cdbf_name
    parentId = f.cdb_folder
    if parentId:
        parent = cdb_folder_item.KeywordQuery(
            cdb_wspitem_id=parentId, cdbf_object_id=f.cdbf_object_id
        ).Execute()
        if parent:
            relPath = getRelPath(parent[0]) + "/" + relPath
        else:
            logging.error(
                "cdb_folder_item does not exist (cdb_wspitem_id='%s', cdbf_object_id='%s')",
                parentId,
                f.cdbf_object_id,
            )
    return relPath
