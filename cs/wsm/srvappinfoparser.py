#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#


from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import sys
import traceback
import logging

from xml.etree import cElementTree as ElementTree

import six

from cs.wsm import srvappinfoitems


class WsItemFactory(object):
    def __init__(self):
        self._itemNameToType = dict()
        validNames = dir(srvappinfoitems)
        for clname, cl in six.iteritems(srvappinfoitems.__dict__):
            if clname in validNames:
                try:
                    if issubclass(cl, srvappinfoitems.AppinfoItem):
                        xmlTag = cl.xmlTag
                        self._itemNameToType[xmlTag] = cl
                except TypeError:
                    # ALle INTS, usw. ausschliessen
                    pass

    def getWsItemClass(self, wsItemType):
        if wsItemType is not None:
            wsItemType.strip()

        nodeClass = self._itemNameToType.get(wsItemType, None)
        if nodeClass is None:
            logging.debug(
                "WsItemFactory: no class registered for appinfo tag '%s'; "
                "using default item class instead",
                wsItemType,
            )
            nodeClass = srvappinfoitems.AppinfoItem

        return nodeClass


class AppinfoParseError(Exception):
    """
    Represents a parse error while parsing an appinfo file
    """

    pass


class NoAppinfoContentError(Exception):
    """
    Error indicating a trial to parse an empty appinfo file
    """

    pass


class AppInfoParser(object):
    """
    Parser for appinfo-files

    The appinfo-file determines the structure of the docObjects in the workspace

    """

    def __init__(self):
        self._wsItemFactory = WsItemFactory()

    def parseAppInfo(self, appinfoContent, raiseOnEmpty=False):
        """
        Parses the given appinfo file following the RNC, creates and returns an WsItem tree
        representing the content ot the appinfo file

        :Parameters:
             appInfoContent :String

        :raises AppinfoParseError if the appinfo file could not be parsed
        :raises NoAppinfoContentError if the appinfo file to parse is emtpy

        :returns: WsItem: The root of the WsItem tree representing the content of the appinfo file
        """
        logging.debug("*** start parsing appinfo")

        if not six.PY2 and type(appinfoContent) == six.binary_type:
            appinfoContent = appinfoContent.decode("utf-8")

        fd = six.StringIO(appinfoContent)
        wsItem = None
        tree = None
        try:
            tree = ElementTree.parse(fd)
        except Exception:
            excStr = "".join(traceback.format_exception(*sys.exc_info()))
            logging.error("unable to parse appinfo file: , details:%s", excStr)
        finally:
            fd.close()
        if tree is not None:
            root = tree.getroot()  # <appinfo>
            if len(root):
                wsItem = self._processTree(root)
            else:
                logging.error("unable to parse appinfo file: no content")
                if raiseOnEmpty:
                    raise NoAppinfoContentError()
        logging.debug("*** end parsing appinfo")
        return wsItem

    def _processTree(self, node):
        nodeType = node.tag

        wsItem = self._wsItemFactory.getWsItemClass(nodeType)(nodeType, node.attrib)
        if wsItem:
            for subNode in node:
                subTree = self._processTree(subNode)
                if subTree:
                    wsItem.appendChild(subTree)
        else:
            logging.error(u"cannot get a WsItem from the factory, tag '%s'", nodeType)

        return wsItem
