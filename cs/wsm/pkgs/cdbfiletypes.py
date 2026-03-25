#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Module cdbfiletypes.py

Fetches filetype definitions from the PDM server
"""

from __future__ import absolute_import

import six

__docformat__ = "restructuredtext en"

import json
import logging
from collections import defaultdict

from lxml.etree import Element
from lxml import etree as ElementTree

from cdb import auth
from cdb import util
from cdb import sqlapi
from cdb.objects import NULL
from cdb.objects.cdb_filetype import CDB_FileType
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.olc import Workflow
from cs.web.components.ui_support.utils import ui_name_for_classname

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor
from cs.wsm.pkgs.supportedclasses import get_supported_classes
from cs.wsm.ws_cad_language import WsCadLanguage
from cs.wsm.wssrvutils import json_to_b64_str
from cs.wsm.pkgs.xmlmapper import (
    CDB_STATUS_DEFINITIONS,
    CDB_PERSNO,
    CDB_SYSKEYS,
    CDB_CLSS_KEYLISTS,
    CDB_CLSS_KEYLIST,
    CDB_CLSS_KEY,
    CDB_CLASS_HIERARCHY,
    CDB_CLASS_HIERARCHY_TYPE,
    CDB_CLASS_HIERARCHY_CLSS,
    CDB_ATTR_CLASS_TYPES,
    CDB_ATTR_CLASS,
    CDB_CLASS_ATTR,
)
from cs.wsm.pkgs.frame_data import load_frame_configuration
from cs.wsm.pkgs.classification import getUnitMapping


def _getSysKeySafe(sysKey, fallbackValue):
    """
    Retrieve a system key value in a safe way.

    Use a fallback value if the key is absent
    """
    value = fallbackValue
    try:
        value = util.getSysKey(sysKey)
    except KeyError:
        logging.info(
            "System key '%s' is not defined, falling back to " "preset: '%s'",
            sysKey,
            fallbackValue,
        )

    return value


class FileTypeProcessor(CmdProcessorBase):
    """
    Handler class for filetype command.

    This class is used to fetch the filetype definitions and other configuration data from the PDM server.
    """

    name = u"filetypes"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        # Configured wsp_class_name
        wspClassName = None
        rootEl = self.getRoot()
        if rootEl is not None:
            rootEtree = rootEl.etreeElem
            wspClassName = rootEtree.attrib.get("wsp_class_name", None)
        messages, classes = get_supported_classes(wspClassName)
        # only log messages here
        # in next cdb version return them to the client
        # but we like to be compatible in this moment
        for m in messages:
            if m[0]:
                logging.info(m[1], m[2])
            else:
                logging.error(m[1], m[2])
        # supportedObjectClasses is a dict to ClassDesctriptions
        self.supportedObjectClasses = {
            cname: cl for cname, cl in classes.items() if cl.supported_in_workspace
        }
        # here all the classes wee need the keys for
        self._classToConfiguredBaseClass = dict()
        self._classesToInspect = self._getAllDerivedClasses(classes.keys())

    def _getDerivedClasses(self, clss, baseClass=None):
        """
        :param clss: Class to search the derived class
        :param baseClass: baseClass for keeping self._classToConfiguredBaseClass
        """
        cldef = CDBClassDef(clss)
        derivedClasses = []
        for derivedClass in cldef.getSubClassNames(False):
            derivedClasses.append(derivedClass)
            derivedClasses.extend(self._getDerivedClasses(derivedClass, baseClass))
            if baseClass:
                self._classToConfiguredBaseClass[derivedClass] = baseClass
        return set(derivedClasses)

    def _getAllDerivedClasses(self, baseClasses):
        """Get all derived classes of the given 'baseClasses'.

        :return: A set of base classes and its derived classes.
        :rtype: set(str)
        """
        allClasses = set()
        for baseClass in baseClasses:
            allClasses.add(baseClass)
            allClasses.update(
                self._getDerivedClasses(
                    baseClass, baseClass if baseClass != "kCdbDoc" else None
                )
            )
        return allClasses

    def call(self, resultStream, request):
        """
        Retrieve file types from PDM system.

        :Returns: integer indicating command success
        """
        cmdResultElement = Element("WSCOMMANDRESULT")

        persno = self._getPersno()
        cmdResultElement.append(persno)

        sysKeys = self._getSysKeys()
        cmdResultElement.append(sysKeys)

        keyLists = self._getKeyLists()
        cmdResultElement.append(keyLists)

        classHierarchy = self._getCdbClassHierarchy()
        cmdResultElement.append(classHierarchy)

        attrClassTypes = self._getCdbAttrClassTypes()
        cmdResultElement.append(attrClassTypes)

        fileTypesElement = self._getFileTypes()
        cmdResultElement.append(fileTypesElement)

        cmdResultElement.append(self._licResult)

        statusDefinitions = self._getStatusDefinitions()
        cmdResultElement.append(statusDefinitions)

        frameDefinitions = self._loadFrameData(request)
        if frameDefinitions is not None:
            cmdResultElement.append(frameDefinitions)

        userSettings = self._getCDBUserSettings()
        cmdResultElement.append(userSettings)
        cmdResultElement.append(self._getUCUnits())

        cadLanguageFiles = self._getCadLanguageFiles()
        if cadLanguageFiles is not None:
            cmdResultElement.append(cadLanguageFiles)

        xmlStr = ElementTree.tostring(cmdResultElement, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def _getPersno(self):
        resultEl = CDB_PERSNO(persno=auth.persno, alias=auth.name)
        return resultEl.toXmlTree()

    def _getSysKeys(self):
        customer_id = _getSysKeySafe("customer_id", "")
        wsm_doc_change_detection_mode = _getSysKeySafe(
            "wsm_doc_change_detection_mode", "1"
        )
        resultEl = CDB_SYSKEYS(
            customer_id=customer_id,
            wsm_doc_change_detection_mode=wsm_doc_change_detection_mode,
        )
        return resultEl.toXmlTree()

    def _getKeyLists(self):
        resultEl = CDB_CLSS_KEYLISTS()
        for clss in self._classesToInspect:
            clssElem = CDB_CLSS_KEYLIST(classname=clss)
            cldef = CDBClassDef(clss)
            keys = cldef.getKeyNames()
            for key in keys:
                keyElem = CDB_CLSS_KEY(key=key)
                clssElem.addChild(keyElem)
            resultEl.addChild(clssElem)
        return resultEl.toXmlTree()

    def _getCdbClassHierarchy(self):
        resultEl = CDB_CLASS_HIERARCHY()
        # supported classes
        for supportedCls in self.supportedObjectClasses.keys():
            typeElem = CDB_CLASS_HIERARCHY_TYPE(type=supportedCls)
            # add element itself as subclass to stay compatible
            # with WSD Versions <= 15.5.2
            typeClssElem = CDB_CLASS_HIERARCHY_CLSS(classname=supportedCls)
            typeElem.addChild(typeClssElem)
            for subClass in self._getDerivedClasses(supportedCls, None):
                clssElem = CDB_CLASS_HIERARCHY_CLSS(classname=subClass)
                typeElem.addChild(clssElem)
            resultEl.addChild(typeElem)
        return resultEl.toXmlTree()

    def _getStatusDefinitions(self):
        # e.g.
        # {
        #   <objektart:"doc_approve">: {   # z_art/objektart, e.g. "cad_assembly"
        #     <status:"200">: {            # z_status, e.g. "200" as a string
        #       "rgb": "#FF0000",          # e.g. for red
        #       "names": {"de": "Freigegeben", "en": "Released", ...},
        #       "released": <bool:true>,
        #       "dststates": ["190", "0"]
        #     }
        #   }
        # }
        statusdefs = dict()
        classes = self._classesToInspect
        classes.add("wsm_settings")
        objektart = [olc.objektart for olc in Workflow.KeywordQuery(objclass=classes)]
        cond = "objektart in (%s)" % ", ".join(["'%s'" % o for o in objektart])

        sql = (
            "SELECT c.rot_anteil, c.gruen_anteil, c.blau_anteil,"
            " s.*"
            " FROM objektstati s, farben c "
            " WHERE s.statusfarbe = c.bezeichnung "
            " AND %s" % cond
        )
        rs = sqlapi.RecordSet2(sql=sql)

        for r in rs:
            objektart = r.objektart
            status = str(r.statusnummer)
            rgb = "#{0:02x}{1:02x}{2:02x}".format(
                r.rot_anteil, r.gruen_anteil, r.blau_anteil
            )
            if objektart not in statusdefs:
                statusdefs[objektart] = {}
            statusdefs[objektart][status] = {}
            statusdefs[objektart][status]["rgb"] = rgb
            statusdefs[objektart][status]["released"] = bool(r.statusrelease)
            names = {}
            for k, v in list(six.iteritems(r)):
                if v is not None and k.startswith("statusbez_"):
                    lang = k[10:]
                    names[lang] = v
            statusdefs[objektart][status]["names"] = names
            statusdefs[objektart][status]["dststates"] = []

        rs = sqlapi.RecordSet2(
            table="statiflow",
            condition=cond,
            columns=["objektart", "iststatus", "zielstatus"],
            addtl="ORDER BY objektart, iststatus",
        )

        if len(rs) > 0:
            for rec in rs:
                objektart = rec.objektart
                iststatus = str(rec.iststatus)
                zielstatus = str(rec.zielstatus)
                if objektart not in statusdefs:
                    statusdefs[objektart] = {}
                if iststatus not in statusdefs[objektart]:
                    statusdefs[objektart][iststatus] = {}
                if "dststates" not in statusdefs[objektart][iststatus]:
                    statusdefs[objektart][iststatus]["dststates"] = []
                statusdefs[objektart][iststatus]["dststates"].append(zielstatus)

        resultEl = CDB_STATUS_DEFINITIONS(statusdefs=json.dumps(statusdefs))
        return resultEl.toXmlTree()

    def _loadFrameData(self, request):
        """
        <WSMCOMMANDS cmd="frame_data">
          <FRAMEREQUEST>
            <CADSYSTEM name="Catia:CATDrawing">
            <CADSYSTEM name="ProE">
          <FRAMEREQUEST>
        </WSMCOMMANDS>
        Result:
        <WSMCOMMANDRESULT>
          <FRAMEDATA>
          base64codedframe data load_frame_configuration
          </FRAMEDATA>
        </WSMCOMMANDRESULT>
        """
        rootEl = self.getRoot().etreeElem
        cad_systems = set()
        fd = None
        frameRequest = rootEl.find("FRAMEREQUEST")
        if frameRequest is not None:
            for el in frameRequest:
                if el.tag == "CADSYSTEM":
                    val = el.attrib["name"]
                    if val:
                        cad_systems.add(val)
            frame_config = load_frame_configuration(cad_systems, request)
            b64 = json_to_b64_str(frame_config)
            fd = Element("FRAMEDATA")
            fd.text = b64
        return fd

    def _getCdbAttrClassTypes(self):
        resultEl = CDB_ATTR_CLASS_TYPES()
        clssToNameToType = defaultdict(dict)
        for clss in self._classesToInspect:
            cldef = CDBClassDef(clss)
            noSqlType = set()
            attrdefs = cldef.getAttributeDefs()
            for attrdef in attrdefs:
                name = attrdef.getName()
                typ = None
                identifier = attrdef.getIdentifier()
                try:
                    typ = attrdef.getSQLType()
                except Exception:
                    noSqlType.add(name)
                if typ is not None:
                    if typ == sqlapi.SQL_CHAR:  # 0
                        clssToNameToType[clss][name] = ("string", identifier)
                    elif typ == sqlapi.SQL_INTEGER:  # 1
                        clssToNameToType[clss][name] = ("integer", identifier)
                    elif typ == sqlapi.SQL_FLOAT:  # 2
                        clssToNameToType[clss][name] = ("float", identifier)
                    elif typ == sqlapi.SQL_DATE:  # 1
                        clssToNameToType[clss][name] = ("date", identifier)
            if noSqlType:
                logging.info(
                    "FileTypeProcessor._getCdbAttrClassTypes: "
                    "No SQL type could be retrieved for the following "
                    "attributes: %s",
                    " ".join(noSqlType),
                )

        for clss, nameToType in clssToNameToType.items():
            uiname = ui_name_for_classname(clss)
            restname = CDBClassDef(clss).getRESTName()
            for_workspaces = None
            has_files = None
            classDescFromBase = None
            baseclass = self._classToConfiguredBaseClass.get(clss, clss)
            if baseclass:
                classDescFromBase = self.supportedObjectClasses.get(baseclass)
            if classDescFromBase is not None:
                for_workspaces = classDescFromBase.for_workspaces
                has_files = classDescFromBase.has_files
            clssElem = CDB_ATTR_CLASS(
                classname=clss,
                uiname=uiname,
                restname=restname,
                for_workspaces=for_workspaces,
                has_files=has_files,
            )
            if classDescFromBase:
                clssElem.etreeElem.text = json.dumps(
                    {"labels": classDescFromBase.labels}
                )
            for name, (typ, identifier) in nameToType.items():
                attrElem = CDB_CLASS_ATTR(attr=name, type=typ, identifier=identifier)
                clssElem.addChild(attrElem)
            resultEl.addChild(clssElem)
        return resultEl.toXmlTree()

    def _getFileTypes(self):
        """
        :Returns: "CDBFILETYPES" Element
        """
        resultElement = Element("CDBFILETYPES")
        fileTypes = CDB_FileType.Query(lazy=0)
        for fileType in fileTypes:
            fileTypeNode = Element("CDBFILETYP")
            fileTypeNode.attrib["name"] = fileType.ft_name
            # offeronimport flag
            fileTypeNode.attrib["offeronimport"] = (
                "1" if fileType.ft_offeronimport else "0"
            )
            # std suffix
            std_suffix = fileType.ft_std_suffix
            fileTypeNode.attrib["standardsuffix"] = std_suffix
            # mime type
            mimeType = fileType.ft_mimetype
            if mimeType is NULL or mimeType is None:
                mimeType = ""
            fileTypeNode.attrib["mimetype"] = mimeType
            # subtype
            subtype = fileType.ft_subtype
            if subtype is NULL or subtype is None:
                subtype = ""
            fileTypeNode.attrib["subtype"] = subtype
            # suffixed
            suffixesNode = Element("ADDITIONALSUFFIXES")
            fileTypeNode.append(suffixesNode)
            for suffix in fileType.Suffixes:
                extension = suffix.ft_suffix
                if extension != std_suffix:
                    suffixNode = Element("SUFFIX")
                    suffixNode.attrib["ext"] = extension
                    suffixesNode.append(suffixNode)
            resultElement.append(fileTypeNode)
        return resultElement

    def _getCDBUserSettings(self):
        # for now, we only transfer a single setting:
        requiredSettingsWithDefault = [("gui.i18n.date_format", "DD.MM.YYYY hh:mm:ss")]
        resultElement = Element("CDBUSERSETTINGS")
        s = util.PersonalSettings()
        for settingName, default in requiredSettingsWithDefault:
            val = s.getValueOrDefault(settingName, "", default)
            settingNode = Element("CDBUSERSETTING")
            settingNode.attrib["name"] = settingName
            settingNode.attrib["value"] = val
            resultElement.append(settingNode)
        return resultElement

    def _getUCUnits(self):
        """
        reads units from classification
        """
        resultElement = Element("UCUNITS")
        resultElement.text = json.dumps(getUnitMapping())
        return resultElement

    def _getCadLanguageFiles(self):
        """
        Returns the information about the files of all WsCadLanguage objects that
        match the CAD systems given in the request.

        Request part:
          <CADLANGUAGES>
            <CADSYSTEM name="cs.catia">
            <CADSYSTEM name="cs.proe">
          <CADLANGUAGES>

        Result part:
          <CADLANGUAGES>
            <CADLANGUAGE cadsystem="cs.catia" langid="de">
              <FILE blobid="..." " blob_url="..." ...>
              <FILE blobid="..." " blob_url="..." ...>
            </CADLANGUAGE>
            <CADLANGUAGE cadsystem="cs.catia" langid="fr">
              <FILE blobid="..." " blob_url="..." ...>
              <FILE blobid="..." " blob_url="..." ...>
            </CADLANGUAGE>
            <CADLANGUAGE cadsystem="cs.proe" langid="fr">
              <FILE blobid="..." " blob_url="..." ...>
              <FILE blobid="..." " blob_url="..." ...>
            </CADLANGUAGE>
          </CADLANGUAGES>
        :return:
        """
        use_direct_blob = GetCdbVersionProcessor.checkPresignedBlobConfig() == 0
        rootEl = self.getRoot().etreeElem
        cadSystems = set()
        langs = None
        cadLangRequest = rootEl.find("CADLANGUAGES")
        if cadLangRequest is not None:
            for el in cadLangRequest:
                if el.tag == "CADSYSTEM":
                    val = el.attrib["name"]
                    if val:
                        cadSystems.add(val)

            langs = Element("CADLANGUAGES")
            wsCadLangs = WsCadLanguage.KeywordQuery(cadsystem=cadSystems)
            for wsCadLang in wsCadLangs:
                lang = Element(
                    "CADLANGUAGE",
                    {"cadsystem": wsCadLang.cadsystem, "langid": wsCadLang.langid},
                )
                for f in wsCadLang.Files:
                    blob_id = f.cdbf_blob_id
                    if blob_id is None:
                        blob_id = ""
                    accessible = f.CheckAccess("read_file")
                    attrs = {
                        "cdb_object_id": f.cdb_object_id,
                        "name": f.cdbf_name,
                        "blobid": blob_id,
                        "accessible": "1" if accessible else "0",
                    }
                    if use_direct_blob and hasattr(f, "presigned_blob_url"):
                        attrs["blob_url"] = f.presigned_blob_url(
                            check_access=False, emit_read_signal=False
                        )
                    fileEl = Element("FILE", attrs)
                    lang.append(fileEl)
                langs.append(lang)
        return langs
