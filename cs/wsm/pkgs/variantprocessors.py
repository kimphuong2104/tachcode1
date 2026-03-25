# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module variantprocessors

This is the documentation for the variantprocessors module.
"""
from __future__ import absolute_import

import six

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from lxml import etree as ElementTree

from cdb import cad, sqlapi
from cs.documents import Document
from cs.vp.items import Item
from cs.vp.classification import PropertySet, sml

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.pkgsutils import tr


def createErrorElement(msg, args):
    """
    Creates an error element.

    :param msg: string
    :param args: tuple
    :return: ElementTree.Element
    """
    error = ElementTree.Element("ERROR")
    error.attrib["msg"] = msg
    if args:
        trArgList = ElementTree.Element("TRANSLATIONARGLIST")
        for arg in args:
            trArg = ElementTree.Element("TRANSLATIONARG")
            trArg.attrib["trArg"] = arg
            trArgList.append(trArg)
        error.append(trArgList)
    return error


class GetDrawingInformationProcessor(CmdProcessorBase):
    """
    Retrieves the drawing from the generic group of the item of the document,
    which is found within the cad views of the generic group. For now, it can
    just be used for CatiaV5 documents, that consist of a variant as main file.
    """

    name = u"getdrawinginformation"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
            <WSCOMMANDS
                cmd="getdrawinginformation"
                z_nummer="<z_nummer of variant>"
                z_index="<z_index of variant>"
                view_name="<view_name to determine drawing for>">
            </WSCOMMANDS>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
            <DRAWINGINFORMATION cdb_object_id="<cdb_object_id of the drawing>">
                <ERRORS>
                    <ERROR msg="<error msg>">
                        <TRANSLATIONARGLIST>
                            <TRANSLATIONARG trArg="<argument for the message>"/>
                        </TRANSLATIONARGLIST>
                    </ERROR>
                </ERRORS>
             </DRAWINGINFORMATION>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("DRAWINGINFORMATION")
        errors = ElementTree.Element("ERRORS")
        root.append(errors)
        cdbObjectId = self._rootElement.cdb_object_id
        viewName = self._rootElement.view_name
        # get the document of the variant
        genericDoc = Document.ByKeys(cdb_object_id=cdbObjectId)
        if genericDoc:
            cadViews = sqlapi.RecordSet2(
                "cdbsml_pset_view",
                "z_nummer='%s' and "
                "z_index='%s' and "
                "view_name='3DVIEW'"
                % (sqlapi.quote(genericDoc.z_nummer), sqlapi.quote(genericDoc.z_index)),
            )
            if len(cadViews) > 0:
                cadView = cadViews[0]
                genericGroup = cadView.pset_id  # pylint: disable=no-member

                drwCadViews = sqlapi.RecordSet2(
                    "cdbsml_pset_view",
                    "pset_id='%s' and "
                    "view_name='%s'"
                    % (sqlapi.quote(genericGroup), sqlapi.quote(viewName)),
                )
                if len(drwCadViews) > 0:
                    drwCadView = drwCadViews[0]
                    drwZNummer = drwCadView.get("z_nummer")  # pylint: disable=no-member
                    drwZIndex = drwCadView.get("z_index")  # pylint: disable=no-member
                    drwDoc = Document.ByKeys(z_nummer=drwZNummer, z_index=drwZIndex)
                    if drwDoc:
                        root.attrib["cdb_object_id"] = drwDoc.cdb_object_id
                    else:
                        error = createErrorElement(
                            tr("The drawing document '%1-%2' was " "not found."),
                            (drwZNummer, drwZIndex),
                        )
                        errors.append(error)
                else:
                    error = createErrorElement(
                        tr(
                            "The drawing document with view name '%1' was "
                            "not found within the generic group '%2'."
                        ),
                        (viewName, genericGroup),
                    )
                    errors.append(error)
            else:
                error = createErrorElement(
                    tr(
                        "The document '%1-%2' of the generic model was "
                        "not found within the cad views with the view name "
                        "'3DVIEW'. The function is not allowed."
                    ),
                    (genericDoc.z_nummer, genericDoc.z_index, viewName),
                )
                errors.append(error)
        else:
            error = createErrorElement(
                tr(
                    "Could not determine the document of the generic model "
                    "with CDB object id '%1'"
                ),
                (cdbObjectId,),
            )
            errors.append(error)

        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)
        return 0


class SmlAttr(object):
    """
    Represents an SML attribute with with DIN attributes as well.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.dinAttrs = dict()

    def addDinAttr(self, name, value):
        self.dinAttrs[name] = value


def retrieveSmlAttributes(item, currentcad):
    """
    Reads the SML attributes from the given item.

    :param item: cs.vp.items.Item
    :param currentcad: string
    :return: dict(string: SmlAttr)
    """
    dinMerkmal = None
    smlData = None
    smlValues = dict()
    if item:
        if item.sachgruppe:
            oldcad = cad.get_cad_system()
            try:
                cad.set_cad_system(currentcad)
                smlData = cad.get_sml_data(
                    "", "", item.teilenummer, item.t_index, ".", currentcad
                )
            finally:
                cad.set_cad_system(oldcad)

    if smlData is not None:
        logging.info("variantprocessors: sml data is '%s'", smlData)

        smlAttrList = cad.getCADConfValue("SML Attributliste", currentcad)
        smlDataList = smlData.split("@")[1:]

        logging.info(
            "variantprocessors: " "sml attribute list is '%s'", " ".join(smlAttrList)
        )

        i = 0
        dinMerkmal = cad.getCADConfValue("SML Attribut CAD parameter name", currentcad)

        logging.info("variantprocessors: din attribute is '%s'", dinMerkmal)

        while i < len(smlDataList) - 2:
            # beginnt immer mit einem Attributenamen
            # gefolgt vom Wert und evtl. DIN Attribut
            smlAttr = SmlAttr(smlDataList[i], smlDataList[i + 1])
            i += 2
            while i < len(smlDataList) - 2:
                name = smlDataList[i]
                isDinAttr = name.startswith("mm_") or name in smlAttrList
                value = smlDataList[i + 1]
                if isDinAttr:
                    smlAttr.addDinAttr(name, value)
                    i += 2
                else:
                    break
            if dinMerkmal and smlAttr.dinAttrs.get(dinMerkmal):
                smlValues[smlAttr.dinAttrs.get(dinMerkmal)] = smlAttr
            else:
                smlValues[smlAttr.name] = smlAttr
    else:
        logging.info("variantprocessors: no sml data given")
    return smlValues, dinMerkmal


class GetAttrIdentifierProcessor(CmdProcessorBase):
    """
    Retrieves the attribute identifier for given attributes and
    the given generic group.
    """

    name = u"getattridentifier"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
            <WSCOMMANDS
                cmd="getattridentifier"
                pset_id="<id of the generic group>">
                <ATTRIBUTES>
                    <ATTRIBUTE prop_id="<prop_id of the attribute>"/>
                </ATTRIBUTES>
            </WSCOMMANDS>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
            <GETSMLATTRIDENTIFIER>
                <ATTRIBUTEIDENTIFIERS>
                    <ATTRIBUTEIDENTIFIER
                        prop_id="<prop id of the attribute>"
                        attr_ident="<identifier of the attribute>"/>
                </ATTRIBUTEIDENTIFIERS>
             </GETSMLATTRIDENTIFIER>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("GETSMLATTRIDENTIFIER")
        psetId = self._rootElement.pset_id
        propIds = []
        attributeElems = self._rootElement.etreeElem.findall("ATTRIBUTES/ATTRIBUTE")
        for attributeElem in attributeElems:
            propId = attributeElem.attrib.get("prop_id")
            if propId:
                propIds.append(propId)

        attrIdentifiersElem = ElementTree.Element("ATTRIBUTEIDENTIFIERS")
        for propId in propIds:
            attrIdent = sml.getSMLAttrIdentifier(psetId, propId)
            if attrIdent:
                attrIdentifierElem = ElementTree.Element("ATTRIBUTEIDENTIFIER")
                attrIdentifierElem.attrib["prop_id"] = propId
                attrIdentifierElem.attrib["attr_ident"] = attrIdent
                attrIdentifiersElem.append(attrIdentifierElem)
        root.append(attrIdentifiersElem)

        xmlStr = ElementTree.tostring(root, encoding="utf-8", pretty_print=True)
        xmlLines = xmlStr.split("\n")
        for l in xmlLines:
            resultStream.write(l)
        return 0


class GetCadVariantTableProcessor(CmdProcessorBase):
    """
    Retrieves the cad variants of the given document.
    """

    name = u"getcadvarianttable"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
            <WSCOMMANDS
                cmd="getcadvarianttable"
                sachgruppe=""
                cad_system="">
                    [ <ITEM key=value /> ]
            </WSCOMMANDS>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
            <GENERICGROUPTABLE>
                <ERRORS>
                    <ERROR msg="<error msg>">
                        <TRANSLATIONARGLIST>
                            <TRANSLATIONARG trArg="<argument for the message>"/>
                        </TRANSLATIONARGLIST>
                    </ERROR>
                </ERRORS>
                <ROW id="<variant id>">
                    <PARAMETER id="<column id>" value="<column value>"/>
                </ROW>
             </GENERICGROUPTABLE>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("GENERICGROUPTABLE")
        errors = ElementTree.Element("ERRORS")
        root.append(errors)
        genericGroup = self._rootElement.sachgruppe
        cadSys = self._rootElement.cad_system
        eTreeRoot = self._rootElement.etreeElem
        itemEl = eTreeRoot.find("ITEM")
        specialItem = None
        if itemEl is not None:
            itemKeys = itemEl.attrib
            specialItem = Item.ByKeys(**itemKeys)
            if specialItem is not None:
                genericGroup = specialItem.sachgruppe
        if genericGroup:
            propertySet = PropertySet.ByKeys(pset_id=genericGroup)
            if propertySet:
                if specialItem is None:
                    items = propertySet.Items
                else:
                    items = [specialItem]
                for item in items:
                    smlValues, dinMerkmal = retrieveSmlAttributes(item, cadSys)
                    if smlValues:
                        outVariantsElem = ElementTree.Element("variants")
                        outVariantElem = ElementTree.Element("variant")
                        outVariantElem.attrib["teilenummer"] = item.teilenummer
                        outVariantElem.attrib["t_index"] = item.t_index
                        outVariantElem.attrib["sml_prop"] = dinMerkmal or ""
                        for column, smlAttr in smlValues.items():
                            outParametersElem = ElementTree.Element("parameters")
                            outParameterElem = ElementTree.Element("parameter")
                            mmProp = "mm_mk"  # default
                            mmVal = ""
                            if dinMerkmal is not None:
                                mmVal = smlAttr.dinAttrs.get(dinMerkmal, "")
                            outParameterElem.attrib[mmProp] = mmVal
                            outParameterElem.attrib["id"] = column
                            outParameterElem.attrib["value"] = smlAttr.value
                            outParametersElem.append(outParameterElem)
                            outVariantElem.append(outParametersElem)
                        outVariantsElem.append(outVariantElem)
                        root.append(outVariantsElem)
                    else:
                        error = createErrorElement(
                            tr(
                                "The SML values of the item '%1-%2' "
                                "could not be retrieved."
                            ),
                            (item.teilenummer, item.t_index),
                        )
                        errors.append(error)
            else:
                error = createErrorElement(
                    tr("The generic group '%1' was not found."), genericGroup
                )
                errors.append(error)
        else:
            error = createErrorElement(tr("No generic group was given."), "")
            errors.append(error)

        xmlStr = ElementTree.tostring(root, encoding="utf-8", pretty_print=True)
        xmlLines = xmlStr.split("\n")
        for l in xmlLines:
            resultStream.write(l)
        return 0
