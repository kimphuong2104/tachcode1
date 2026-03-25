# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module office_config_processor

This is the documentation for the office_config_processor module.
"""

from __future__ import absolute_import

import hashlib
import json
import logging
import six
from lxml.etree import Element
from lxml import etree

from cdb import cad
from cdb import ElementsError, sqlapi
from cdb.platform.mom.entities import CDBClassDef
from cdb.sqlapi import SQL_CHAR, SQL_INTEGER, SQL_FLOAT, SQL_DATE

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


sqlTypeToReadableType = {
    SQL_CHAR: u"str",
    SQL_INTEGER: u"int",
    SQL_FLOAT: u"float",
    SQL_DATE: u"date",
    "char": u"str",
    "integer": u"int",
}


class OfficeConfigProcessor(CmdProcessorBase):
    name = "get_office_config"
    format_version = "15.4.1.1"
    secret = "c3ea0b29-8734-418f-817c-941b9981d3ca"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        self.classes = dict()
        self.classDefCache = dict()  # name -> CDBClassDef

    def call(self, resultStream, request):
        """
        :return: integer indicating command success
        """
        cmdResultElement = self.get_config()
        xmlStr = etree.tostring(cmdResultElement, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def get_class_infos(self, cdb_class_name, depth=1):
        """
        :param cdb_class_name: string. CDB classname to
                fetch relationship information for.
        :param depth: how deep relationships have to be traversed
        """
        clsDef = self.get_cls_def(cdb_class_name)
        if clsDef and not self.class_already_fully_calculated(cdb_class_name):
            depth -= 1
            clsInfo = dict()
            # get class attributes
            clsName, attrs = self.get_cls_attributes_data(clsDef)
            clsInfo["attributes"] = attrs
            # get relationships definitions
            relationshipNames = clsDef.getRelationshipNames()
            relationships = list()
            if len(relationshipNames) and depth >= 0:
                for relationshipName in relationshipNames:
                    relationshipData = self.get_relationship_data(
                        clsDef, relationshipName
                    )
                    relationships.append(relationshipData)
            clsInfo["relationships"] = relationships
            self.classes[clsName] = clsInfo
            # get references classes only if relationships
            # were collected by depth >= 0
            if relationships:
                for rel in relationships:
                    referencedClassName = rel["referenced_class"]
                    # do not traverse circular relationships
                    if referencedClassName != clsName:
                        self.get_class_infos(referencedClassName, depth)

    def get_cls_def(self, cdb_class_name):
        # look up class definition in cache or build new one
        clsDef = self.classDefCache.get(cdb_class_name, None)
        if not clsDef:
            clsDef = CDBClassDef(cdb_class_name)
        return clsDef

    def class_already_fully_calculated(self, class_name):
        return (
            class_name in list(self.classes)
            and len(self.classes[class_name]["relationships"]) > 0
        )

    def get_relationship_data(self, parentClsDef, relationshipName):
        # for every relationship get:
        # name without CDBRelship prefix, cardinality
        # and referenced class name
        CDBRelshipPrefix = "CDBRelship"
        relationshipData = dict()
        relDef = parentClsDef.getRelationship(relationshipName)
        # get relationship cardinality
        if relDef.is_one_on_one():
            relationshipData["cardinality"] = "1"
        else:
            relationshipData["cardinality"] = "N"
        # get relationship name without CDB specific prefix
        if relationshipName.startswith(CDBRelshipPrefix):
            relationshipName = relationshipName.split(":")[1]
        relationshipData["name"] = relationshipName
        # get referenced class name and attributes
        # and store them in self.classes dict
        relationshipData["referenced_class"] = ""
        referencedClsDef = relDef.get_reference_cldef()
        if referencedClsDef:
            referencedClassName = referencedClsDef.getClassname()
            relationshipData["referenced_class"] = referencedClassName
            self.classDefCache[referencedClassName] = referencedClsDef
        return relationshipData

    def get_tables_with_z_num(self):
        """
        :return: dict:
            <table_name>: [(<column_name>, '', <column_type>), ...]
        """
        tablesData = dict()
        try:
            getTablesNames = (
                "SELECT DISTINCT table_name FROM cdb_columns WHERE"
                " column_name = 'z_nummer' ORDER BY table_name "
            )
            rs = sqlapi.RecordSet2(sql=getTablesNames)
            for r in rs:
                tab_name = r.table_name
                if tab_name not in list(self.classes):
                    tablesData[tab_name] = list()
                    getColumns = (
                        "SELECT column_name, type FROM cdb_columns WHERE"
                        " table_name = '%s' ORDER BY column_name" % tab_name
                    )
                    columnsRs = sqlapi.RecordSet2(sql=getColumns)
                    for colRs in columnsRs:
                        tablesData[tab_name].append(
                            (
                                colRs.column_name,
                                "",  # we have no description here
                                sqlTypeToReadableType.get(colRs.type, colRs.type),
                            )
                        )
        except ElementsError as e:
            logging.info(
                "OfficeConfigProcessor.get_tables_with_z_num: "
                "exception occurred: '%s'.",
                str(e),
            )
        return tablesData

    @staticmethod
    def get_cls_attributes_data(clsDef):
        """
        :return: tuple: (str, list)
            class_name, [{"attr_name": <attr_name>,
                          "ui_name": <attr_label>,
                          "type": <attr_type>}, ...]
        """
        attrs = clsDef.getAttributeDefs()
        clsName = clsDef.getClassname()
        clsAttrs = list()
        for attrDef in attrs:
            name = attrDef.getName()
            try:
                attrType = sqlTypeToReadableType.get(attrDef.getSQLType(), "str")
            except ElementsError as e:
                logging.info(
                    "OfficeConfigProcessor.get_cls_attributes_data: "
                    "exception: '%s' occurred while calculation"
                    " of attribute type. Using 'str' instead.",
                    str(e),
                )
                attrType = "str"
            # label of the attribute that is
            # configured in the sessions language.
            attrLabel = attrDef.getLabel()
            clsAttrs.append({"attr_name": name, "ui_name": attrLabel, "type": attrType})
        return clsName, clsAttrs

    def get_config(self):
        """
        returns:
        <WSMCOMMANDRESULT>
          <ERROR>text</ERROR> if error occurred
          <CONFIG>
            {"version": <format_version>,
             "checksum": <hash over sorted json as string + secret>
             "classes":
                {
                <class_name>:
                   {
                     "relationships":
                       [
                         {"name": <relationship_name>,
                          "referenced_class_attrs": <class_name>,
                          "cardinality": "1" || "N"},
                         ...
                       ] || [] empty if depth is exceeded,
                     "attributes":
                       [
                         {"attr_name": <attr_name>,
                          "ui_name": <attr_label>,
                          "type": <attr_type>},
                         ...
                       ]
                   },
                  ...
               },
               "system_dependent": {
                 "MS-Word" || "MS-PowerPoint" || "MS-Visio" || "MS-Excel": {
                   "access_info":
                     {"allow_meta_data_write": True || False,
                      "allow_meta_data_manage": True || False,
                      "auto_metadata_write": "SILENT" || True || False}
                },
                 "MS-outlook": {
                   "cad_conf":{"preset_new_list_cad2cdb": "<config>",
                               "disable_attach_document": True || False,
                               "disallow_delete_attachment": True || False}
            }
          </CONFIG>
        </WSMCOMMANDRESULT>
        """
        cmdResultElement = Element("WSCOMMANDRESULT")
        cdbClsNames, depth = self.get_class_names_and_depth()
        if cdbClsNames:
            try:
                configData = dict()
                configData["version"] = self.format_version
                # fill up self.classes
                for cdbClsName in cdbClsNames:
                    self.get_class_infos(cdbClsName, depth=depth)
                configData["classes"] = self.classes
                # implemented just for legacy support of
                # BY_ZNUM_ZIDX_FROM_ only. might not be needed in future.
                # configData["z_num_tables"] = self.get_tables_with_z_num()
                cad_conf = self.get_cad_conf()
                if cad_conf:
                    configData["system_dependent"] = cad_conf
                configData["checksum"] = self.get_checksum(configData)
                config = Element("CONFIG")
                config.text = json.dumps(configData, sort_keys=True)
                cmdResultElement.append(config)
            except ElementsError as e:
                errorEl = Element("ERROR")
                errorEl.text = six.text_type(e)
                cmdResultElement.append(errorEl)
        return cmdResultElement

    @staticmethod
    def get_cad_conf(cadSystems=None):
        if cadSystems is None:
            cadSystems = [
                "MS-Excel",
                "MS-PowerPoint",
                "MS-Visio",
                "MS-Word",
                "MS-Outlook",
            ]
        ret = dict()
        officeSwitches = {
            "Allow Metadata Manage": "allow_meta_data_manage",
            "Allow Metadata Write": "allow_meta_data_write",
            "Auto Metadata Write": "auto_meta_data_write",
            "Force Metadata Write": "force_meta_data_write",
        }
        outlookSwitches = {
            "Preset new list CAD2CDB": "preset_new_list_cad2cdb",
            "Disable Attach Document": "disable_attach_document",
            "Disallow Delete Attachment": "disallow_delete_attachment",
        }
        nonBoolean = ["preset_new_list_cad2cdb", "auto_meta_data_write"]
        for cadSys in cadSystems:
            info = dict()
            info_key = "access_info"
            dbNameToKey = officeSwitches
            if cadSys == "MS-Outlook":
                info_key = "cad_conf"
                dbNameToKey = outlookSwitches
            for name, key in dbNameToKey.items():
                try:
                    val = cad.getCADConfValue(name, cadSys)
                    # convert all "boolean" strings to real boolean
                    if (
                        key not in nonBoolean
                        or key == "auto_meta_data_write"
                        and val != "SILENT"
                    ):
                        val = cad.isTrue(val)
                    info[key] = val
                except ElementsError as e:
                    logging.info(
                        "OfficeConfigProcessor.get_cad_conf: "
                        "exception: '%s' occurred while reading"
                        " value of '%s' for '%s'",
                        str(e),
                        name,
                        cadSys,
                    )
            ret[cadSys] = {info_key: info}
        return ret

    def get_checksum(self, data):
        dataAsJsonStr = json.dumps(data, sort_keys=True)
        data = dataAsJsonStr + self.secret
        if six.PY3:
            data = data.encode("utf-8")
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def get_file_based_classes():
        names = set()
        sql = "SELECT DISTINCT classname FROM switch_tabelle WHERE has_files = 1"
        rs = sqlapi.RecordSet2(sql=sql)
        for r in rs:
            names.add(r.classname)
        return names

    def get_class_names_and_depth(self):
        names = self.get_file_based_classes()
        rootElement = self.getRoot().etreeElem
        depth = rootElement.attrib.get("depth", "")
        depth = int(depth) if depth.isdigit() else 1
        for child in rootElement:
            if child.tag == "CLASSNAME":
                className = child.attrib.get("cdb_class_name")
                if className:
                    names.add(className)
        return names, depth
