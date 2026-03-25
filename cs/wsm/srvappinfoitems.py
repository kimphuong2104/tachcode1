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

import logging

import six

from cs.wsm.srvpoint3d import Point3D
from cs.wsm.srvmatrix import Matrix
from cs.wsm.srvwsitem import SrvWsItem

BBOX = u"bbox"
BOM = u"bom"
BOMS = u"boms"
BOMRELEVANT = u"bom-relevant"
CADREFERENCE = u"cadreference"
DIAMETER = u"diameter"
FRAMES = u"frames"
HEIGHT = u"height"
LENGTH = u"length"
LINKS = u"links"
NAME = u"name"
SORTVAL = u"sortval"
NUMBER = u"number"
OCCURRENCES = u"occurrences"
OCCURRENCE = u"occurrence"
DERVIED_SOUCRES = u"derivedsources"
DERVIED_SOUCRE = u"derivedsource"
PAPERSIZE = u"papersize"
PARAMETERS = u"parameters"
PARTNO = u"partno"
PARTVER = u"partver"
PATH = u"path"
PDMID = u"pdmid"
POSNO = u"posno"
PROJENV = u"projectenv"
PROPERTIES = u"properties"
QUANTITY = u"quantity"
SCALE = u"scale"
SHEETS = u"sheets"
STANDARD = u"standard"
SUPPRESSED = u"suppressed"
TMATRIX = u"tmatrix"
TYPE = u"type"
UNIT = u"unit"
VALUE = u"value"
VARIANTID = u"variantid"
VARIANTNAME = u"variantname"
VARIANTS = u"variants"
VIEWS = u"views"
WIDTH = u"width"
YES = u"yes"
APPOBJECTS = u"appobjects"
APPOBJECT = u"appobject"


LOC_BUILTIN = ""


class AppinfoItem(SrvWsItem):
    """
    Base class of all appinfo items. An instance of this class is taken for
    all xml tags for which a specialized implementation could not been found.
    """

    pluginType = u"AppinfoExtension"

    xmlTag = None

    # the following constants hold xml tag names from the appinfo-format
    #
    def __init__(self, itemType, attrs):
        """
        The WsItem constructor is overriden here, because for the appinfo elements,
        the wsitem name cannot be determined from outside. Usually, it corresponds to the id,
        but the subclasses should have the possibility to override this behavior using the
        attributes passed in by the caller.

        :Parameters:
            itemType : string
                The type of the WsItem. In the case of the appinfo items, it correspods
                to the xml tag
            attrs : dictionary
                dictionary holding xml properties
            wspath : unicode
                The path of the workspace
            mesh : Mesh
                Mesh to which this WsItem belongs
        """
        itemId = ""
        try:
            itemId = six.text_type(attrs.get(u"id"))
            del attrs[u"id"]
        except KeyError:
            itemId = u""

        SrvWsItem.__init__(self, itemId, itemType)

        # all xml properties become WsItem attributes
        #
        for name, value in six.iteritems(attrs):
            self.setAttribute(six.text_type(name), six.text_type(value))

    def _childrenOfContainerItem(self, itemType):
        children = []
        container = self.findChildById((itemType, ""))
        if container:
            children = container.getChildren()
        return children

    def _itemInContainer(self, containerType, itemId):
        container = self.findChildById((containerType, ""))
        return container.findChildById(itemId)


class AppInfo(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"

    xmlTag = u"appinfo"

    def getLinks(self):
        return self._childrenOfContainerItem(LINKS)

    def getDerivedSources(self):
        return self._childrenOfContainerItem(DERVIED_SOUCRES)

    def getDerivedSource(self, sourceId):
        return self._itemInContainer(DERVIED_SOUCRES, (DERVIED_SOUCRE, sourceId))

    def getSheets(self):
        return self._childrenOfContainerItem(SHEETS)

    def getOccurrences(self):
        return self._childrenOfContainerItem(OCCURRENCES)

    def getOccurrence(self, occId):
        return self._itemInContainer(OCCURRENCES, (OCCURRENCE, occId))

    def getParameters(self):
        return self._childrenOfContainerItem(PARAMETERS)

    def getProperties(self):
        return self._childrenOfContainerItem(PROPERTIES)

    def getVariants(self):
        return self._childrenOfContainerItem(VARIANTS)

    def getBoundingBox(self):
        return self.findChildByType(BBOX)

    def getBOM(self):
        return self.findChildByType(BOM)

    def getBOMs(self):
        return self.findChildByType(BOMS)

    def getProjEnv(self):
        ret = None
        prjEnv = self.findChildByType(PROJENV)
        if prjEnv is not None:
            ret = prjEnv.findAttributeByName("value")
        return ret

    def getAppObjects(self):
        return self._childrenOfContainerItem(APPOBJECTS)

    def isIncomplete(self, category):
        res = False
        incomplete = self.findAttributeByName(u"incomplete-nodes")
        if incomplete:
            for categ in incomplete.split(","):
                if categ == category:
                    res = True
                    break
        return res


class BOMSClass(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"boms"

    def getBOMs(self):
        return self.getChildren()


class BOMClass(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"bom"

    def getPartNumber(self):
        return self.findAttributeByName(PARTNO)

    def getPartVersion(self):
        return self.findAttributeByName(PARTVER)

    def getCadReference(self):
        return self.findChildByType(CADREFERENCE)

    def getPositions(self):
        return self.findChildrenByType(BOMPosition.xmlTag)


class BOMPosition(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"bomposition"

    def getPosNumber(self):
        return self.findAttributeByName(POSNO)

    def getPartNumber(self):
        return self.findAttributeByName(PARTNO)

    def getPartVersion(self):
        return self.findAttributeByName(PARTVER)

    def getQuantity(self):
        return self.findAttributeByName(QUANTITY)

    def getUnit(self):
        return self.findAttributeByName(UNIT)

    def getLength(self):
        return self.findAttributeByName(LENGTH)

    def getWidth(self):
        return self.findAttributeByName(WIDTH)

    def getHeight(self):
        return self.findAttributeByName(HEIGHT)

    def getDiameter(self):
        return self.findAttributeByName(DIAMETER)

    def getProperties(self):
        return self._childrenOfContainerItem(PROPERTIES)

    def getCadReference(self):
        return self.findChildByType(CADREFERENCE)


class PathHoldingItem(SrvWsItem):
    """
    Base class for items which do hold an fs path and have to normalize it
    """

    def getPath(self):
        return self.findAttributeByName(PATH)

    def _setPath(self, newPath):
        self.setAttribute(PATH, newPath)


class CadReference(AppinfoItem, PathHoldingItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"cadreference"

    def __init__(self, itemType, attrs):
        """
        :Parameters:
            itemType : string
                The type of the WsItem. In the case of the appinfo items, it correspods
                to the xml tag
            attrs : dictionary
                dictionary holding xml properties
            wspath : unicode
                The path of the workspace
            mesh : Mesh
                Mesh to which this WsItem belongs
        """
        AppinfoItem.__init__(self, itemType, attrs)

    def getVariantId(self):
        return self.findAttributeByName(VARIANTID)

    def getVariantName(self):
        return self.findAttributeByName(VARIANTNAME)


class TMatrix(AppinfoItem):
    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"tmatrix"

    def __init__(self, itemType, attrs):
        """
        :Parameters:
            itemType : string
                The type of the WsItem. In the case of the appinfo items, it correspods
                to the xml tag
            attrs : dictionary
                dictionary holding xml properties
            wspath : unicode
                The path of the workspace
            mesh : Mesh
                Mesh to which this WsItem belongs
        """
        AppinfoItem.__init__(self, itemType, attrs)

    def getMatrix(self):
        """
        :returns: Matrix the matrix in as 4 x 4 -Vector

        """
        # das zeugs kommt zeilenweise an.
        # 1 = links oben
        # Wir moechten aber gerne Spalten
        # haben.
        # findChildById
        # typeNamePair = (child._itemType, child._itemName)

        matrix = Matrix(4, 4, float)
        for row in six.moves.range(4):
            for col in six.moves.range(4):
                pos = col + 1 + row * 4
                itemId = (u"entry", six.text_type(pos))
                valItem = self.findChildById(itemId)
                if valItem is not None:
                    val = valItem.findAttributeByName(u"value")
                    if val is not None:
                        matrix.setValue(col, row, val)
                    else:
                        logging.error(
                            u"Matrix entry has no value attribute (col:%s row:%s) assuming 0.0 value",
                            col,
                            row,
                        )
                else:
                    logging.error(
                        u"Matrix not complete missing col:%s row:%s assuming 0.0 value",
                        col,
                        row,
                    )
        return matrix

    def getMatrixAsString(self):
        """
        :return: a string
        """
        m = self.getMatrix()
        entries = []
        for colNr in six.moves.range(4):
            col = m.getCol(colNr)
            entries.extend(col)
        entries = six.moves.map(repr, entries)
        ret = " ".join(entries)
        return ret


class BBox(AppinfoItem):
    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"bbox"

    def getValueForName(self, pItem, n):
        val = pItem.findAttributeByName(n)
        if val is not None:
            val = float(val)
        return val

    def getPoint(self, number):
        itemId = (u"point", six.text_type(number))
        pItem = self.findChildById(itemId)
        x = self.getValueForName(pItem, u"x")
        y = self.getValueForName(pItem, u"y")
        z = self.getValueForName(pItem, u"z")
        return Point3D(x, y, z)

    def getMinPoint(self):
        return self.getPoint(1)

    def getMaxPoint(self):
        return self.getPoint(2)


class Frame(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"frame"

    def getCadId(self):
        return self.getItemName()

    def getPdmId(self):
        return self.findAttributeByName(PDMID)

    def getFrameReference(self):
        return self.findChildByType(CADREFERENCE)


class Link(AppinfoItem, PathHoldingItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"link"

    def __init__(self, itemType, attrs):
        """
        :Parameters:
            itemType : string
                The type of the WsItem. In the case of the appinfo items, it correspods
                to the xml tag
            attrs : dictionary
                dictionary holding xml properties
            wspath : unicode
                The path of the workspace
            mesh : Mesh
                Mesh to which this WsItem belongs
        """
        AppinfoItem.__init__(self, itemType, attrs)

    def getPath(self):
        return self.findAttributeByName(PATH)

    def getType(self):
        return self.findAttributeByName(TYPE)


class DerivedSource(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"derivedsource"

    def getCadReference(self):
        return self.findChildByType(CADREFERENCE)


class Occurrence(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"occurrence"

    def getName(self):
        return self.findAttributeByName(NAME)

    def isSuppressed(self):
        attrValue = self.findAttributeByName(SUPPRESSED)
        return attrValue == YES

    def isBomRelevant(self):
        attrValue = self.findAttributeByName(BOMRELEVANT)
        return attrValue == YES

    def getCadReference(self):
        return self.findChildByType(CADREFERENCE)

    def getTMatrix(self):
        return self.findChildByType(TMATRIX)

    def getProperties(self):
        return self._childrenOfContainerItem(PROPERTIES)

    def getSortValue(self):
        return self.findAttributeByName(SORTVAL)

    def getQuantity(self):
        ret = self.findAttributeByName(QUANTITY)
        if ret is not None:
            try:
                ret = int(ret)
            except ValueError:
                logging.warning(
                    "Wrong format for quantity of occurrence '%s': %s",
                    self.getName(),
                    ret,
                )
                ret = None
        return ret


class Parameter(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"parameter"

    def getCadId(self):
        return self.getItemName()

    def getName(self):
        return self.findAttributeByName(NAME)

    def getValue(self):
        return self.findAttributeByName(VALUE)

    def getUnit(self):
        return self.findAttributeByName(UNIT)


class Property(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"property"

    def getValue(self):
        return self.findAttributeByName(VALUE)

    def getUnit(self):
        return self.findAttributeByName(UNIT)

    def getType(self):
        return self.findAttributeByName(TYPE)


class Sheet(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"sheet"

    def getName(self):
        return self.findAttributeByName(NAME)

    def getNumber(self):
        return self.findAttributeByName(NUMBER)

    def getScale(self):
        return self.findAttributeByName(SCALE)

    def getFrames(self):
        return self._childrenOfContainerItem(FRAMES)

    def getViews(self):
        return self._childrenOfContainerItem(VIEWS)

    def getPaperSize(self):
        return self.findChildByType(PAPERSIZE)

    def getAppObjects(self):
        return self._childrenOfContainerItem(APPOBJECTS)


class Variant(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"variant"

    def getName(self):
        return self.findAttributeByName(NAME)

    def getLinks(self):
        return self._childrenOfContainerItem(LINKS)

    def getOccurrences(self):
        return self._childrenOfContainerItem(OCCURRENCES)

    def getParameters(self):
        return self._childrenOfContainerItem(PARAMETERS)

    def getProperties(self):
        return self._childrenOfContainerItem(PROPERTIES)

    def getVariants(self):
        return self._childrenOfContainerItem(VARIANTS)

    def getBoundingBox(self):
        return self.findChildByType(BBOX)

    def getBOM(self):
        return self.findChildByType(BOM)

    def getAppObjects(self):
        return self._childrenOfContainerItem(APPOBJECTS)


class AppObject(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"appobject"

    def getType(self):
        return self.findAttributeByName(TYPE)

    def getName(self):
        return self.findAttributeByName(NAME)

    def getProperties(self):
        return self._childrenOfContainerItem(PROPERTIES)

    def getAppObjects(self):
        return self._childrenOfContainerItem(APPOBJECTS)


class View(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"view"

    def getScale(self):
        return self.findAttributeByName(SCALE)

    def getProperties(self):
        return self._childrenOfContainerItem(PROPERTIES)

    def getCadReference(self):
        return self.findChildByType(CADREFERENCE)


class PaperSize(AppinfoItem):
    """ """

    pluginType = u"AppinfoExtension"
    pluginLocation = LOC_BUILTIN
    xmlTag = u"papersize"

    def getWidth(self):
        return self.findAttributeByName(WIDTH)

    def getHeight(self):
        return self.findAttributeByName(HEIGHT)

    def getUnit(self):
        return self.findAttributeByName(UNIT)

    def getStandard(self):
        return self.findAttributeByName(STANDARD)
