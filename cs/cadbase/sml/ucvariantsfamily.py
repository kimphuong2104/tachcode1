# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucvariantsfamily

This is the documentation for the ucvariantsfamily module.
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"

import six
import logging
import os
from lxml import etree as ElementTree

from cdb.objects import ByID
from cdb.objects.operations import operation
from cdb import constants
from cs.cadbase import cadcommands
from cs.cadbase.sml import ucvariantssingle as ucs
from cs.cadbase.sml.ucvariantsbase import InvalidGenericError, InvalidItemError
from cs.cadbase.sml.ucvariantsbase import MissingModulError
from cs.cadbase.sml.ucvariantsbase import generics_for_item
from cs.cadbase.sml.ucvariantsbase import checkout_structure
from cs.cadbase.wsutils.variantconfig import VariantConfig
from cs.cadbase.appinfohandler import remove_rel_paths
from cs.cadbase.cadjobqueue import create_cad_job, JobCallBack

_import_valid = True
try:
    from cs.vp.items import Item
    from cs.wsm.pkgs.classification import get_familytable_for_class, add_additonal_property_infos
    from cs.wsm.pkgs.classification import get_classification_for_item
except ImportError as e:
    logging.error("cs.cadbase.ucvarinatsfamily: required module not found %s", str(e))
    _import_valid = False

# Exported objects
__all__ = []


def log(s):
    logging.debug(s)


class UcCallBackFamTabBase(JobCallBack):
    """
    Handles variantconfig (familytable modifications for proe)
    """

    def pre(self, job):
        """
        checkout generic model and references for assemblies
        create jobs for static attributes, sc attribute, appinfo generation
        """
        job.log("PRE_START*")
        self._job = job
        parameter = job.get_parameter()
        genericDoc = ByID(parameter["genericdocument"])
        genericFile = ByID(parameter["genericfile"])
        appinfoFile = ByID(parameter["appinfofile"])
        ucClass = ByID(parameter["ucclass"])
        item = ByID(parameter["item"])
        complete_table = parameter["complete_table"]
        cadJobFilename = os.path.join(cadcommands.CadCommand.CAD_ROOT_DIR,
                                      genericFile.cdbf_name)

        workingDir = job.get_workspace()
        checkout_structure(workingDir, genericDoc)
        genericFilePath = os.path.join(workingDir, genericFile.cdbf_name)
        appinfoFileDir = os.path.join(workingDir, ".wsm", ".info")
        appinfoFilePath = os.path.join(appinfoFile.cdbf_name)
        if not os.path.isdir(appinfoFileDir):
            os.makedirs(appinfoFileDir)

        integrationSystem = genericDoc.erzeug_system.split(":")[0].lower()
        jobRunner = cadcommands.JobRunner(integrationSystem)
        cadJob = jobRunner.create_job()
        genericAttributes = {k: six.text_type(genericDoc[k]) for k in genericDoc.keys()}
        itemAttributes = {k: six.text_type(item[k]) for k in item.keys()}

        vcContent = parameter["variantconfigcontent"]
        vc = VariantConfig()
        res = vc.readFromBuffer(vcContent)
        if res.hasError():
            raise InvalidItemError("Invalid content in file %s" % parameter["variantconfigname"])

        familyTableParams, tableDef = self._getFamiliyTableValues(appinfoFilePath)
        cadNameToId = dict()
        if tableDef is not None:
            for cid, (typ, name) in tableDef.items():
                cadNameToId[name.lower()] = cid
        else:
            job.log("Generic file needs a least a family table with one row")
            logging.error("Generic file needs a least a family table with one row")
        clInfos = dict()
        add_additonal_property_infos(ucClass, clInfos)
        propNames = clInfos["_prop_names_"]
        ucClassCode = ucClass.code
        cadvariantTable = dict()  # dict instname to dict key value of parameters
        if familyTableParams:
            cadKey = vc.getCadPropertyValue()
            floatFormat = vc.getFloatFormat()
            cadvariantTable = dict()
            if complete_table:
                famtabinfo = get_familytable_for_class(ucClass.code, Item)
            else:
                clInfo = get_classification_for_item(ucClass, item)
                famtabinfo = [(item, clInfo)]
            for item, ucClassInformation in famtabinfo:
                itemAttributes = {k: six.text_type(item[k]) for k in item.keys()}
                instName = vc.getIdName(
                            genericAttributes,
                            itemAttributes)
                if instName:
                    cadParameters = cadvariantTable.get(instName)
                    if cadParameters is None:
                        cadParameters = dict()
                        # initiliasing with empty values
                        # differs from wsm. Wsm uses first column
                        for colId, colInfo in tableDef.items():
                            colType = colInfo[0]
                            if colType == float:
                                cadParameters[colId] = 0.0
                            elif colType == bool:
                                cadParameters[colId] = False
                            else:
                                cadParameters[colId] = ""
                    clsInfo = ucClassInformation["metadata"]["classes"][ucClassCode]
                    cadPropIdsToVal = dict()
                    for propCode, prop in clsInfo["properties"].items():
                        if cadKey in ("code", "catalog_code"):
                            cadPropName = prop[cadKey]
                        elif cadKey.startswith("name_"):
                            cadPropName = propNames.get(propCode, "")
                            if not cadPropName:
                                logging.error(
                                    "_getCadValuesFromUCClassInformation: "
                                    "cadproperty name is empty for  code: %s. and key: %s"
                                    "Perhaps misconfigured variantconfig", propCode, cadKey)
                        if cadPropName:
                            if (cadPropName.lower() in cadParameters or
                                    cadPropName.lower() in cadNameToId):
                                propInfo = ucClassInformation["properties"][propCode][0]
                                value = propInfo["value"]
                                if propInfo["property_type"] == "float":
                                    # we assume that the base value is SI,
                                    # so we always use the base value.
                                    if value["float_value"] is not None:
                                        cadVars = {"value": str(value["float_value_normalized"]),
                                                   "unit": prop["base_unit_symbol"]}
                                        cadValue = floatFormat.replace(cadVars, dict()).strip()
                                    else:
                                        cadValue = None
                                else:
                                    # we only handle int and text
                                    cadValue = str(value)
                                if cadValue is not None:
                                    cadPropIdsToVal[self.adjustVariantColname(cadPropName)] =\
                                        cadValue
                        else:
                            logging.debug("_getCadValuesFromUCClassInformation: ignoring value for "
                                          "cadPropName %s. Not in generic", cadPropName)
                    if cadPropIdsToVal:
                        cadvariantTable[instName] = cadPropIdsToVal
                    additionalParams = self._getAdditionalVariantParams(vc, dict(item), False)
                    additionalCadParams = dict()
                    for p, v in additionalParams.items():
                        additionalCadParams[self.adjustVariantColname(p)] = v
                    cadvariantTable[instName].update(additionalCadParams)

            job.log("SMLVALUES: %s" % cadvariantTable)
            cmds = self.cadUpdateFamilyTable(genericFilePath, cadvariantTable)
            for cmd in cmds:
                cadJob.append(cmd)
            cmdSaveAppinfo = cadcommands.CmdSaveAppInfo(
                cadJobFilename,
                [],
                "SINGLE",
                flags=[cadcommands.processingFlags.CloseWorkFileAfterAction,
                       cadcommands.processingFlags.StopOnError])
            cadJob.append(cmdSaveAppinfo)
            job.save_cad_jobs(jobRunner)
        return []  # nothing

    def post(self, job, job_runner):
        """
        removes absolute path from appinfo
        """
        parameter = job.get_parameter()
        appinfoFile = ByID(parameter["appinfofile"])
        appinfoPath = os.path.join(job.get_workspace(),
                                   ".wsm",
                                   ".info",
                                   appinfoFile.cdbf_name)
        if os.path.isfile(appinfoPath):
            remove_rel_paths(appinfoPath)
        else:
            appinfoPath = None
        return [appinfoPath]

    def done(self, job):
        """
        add or overwrite files to generated document
        """
        parameter = job.get_parameter()
        genericDoc = ByID(parameter["genericdocument"])
        appinfoFile = ByID(parameter["appinfofile"])
        genericFile = ByID(parameter["genericfile"])

        genFilePath = os.path.join(job.get_workspace(), genericFile.cdbf_name)
        # perhaps find max proe filename and rename it to standard name
        self.handle_renamed_files(genFilePath)
        appinfoFilepath = job.postResult[0]
        integrationSystem = genericDoc.erzeug_system.split(":")[0]
        genericFile.checkin_file(genFilePath,
                                 {"cdb::argument.active_integration": integrationSystem,
                                  "cdb::argument.activecad": integrationSystem})
        if appinfoFilepath:
            appinfoFile.checkin_file(appinfoFilepath,
                                     {"cdb::argument.active_integration": integrationSystem,
                                      "cdb::argument.activecad": integrationSystem})

    def fail(self, job):
        """
        remove generated index or generated doc if cad job failed
        """
        log("**FAILED**")
        job.log("FAIL CALLED")
        parameter = job.get_parameter()
        deleteOnFail = parameter["deleteonfail"]
        if deleteOnFail:
            workDoc = ByID(parameter["workdocument"])
            operation(constants.kOperationDelete, workDoc)

    def cadUpdateFamilyTable(self, genericFilePath, cadvariantTable):
        """
        generates cad commands for updating family table
        :return list of cadCommands
        """
        cmds = []
        cmdUpdateFamilyTable = cadcommands.CmdUpdateVariantTable(
            genericFilePath,
            variant_information=cadvariantTable,
            keep_local_new=True,
            flags=[cadcommands.processingFlags.SaveWorkFileAfterAction,
                   cadcommands.processingFlags.CloseWorkFileAfterAction])
        cmds = [cmdUpdateFamilyTable]
        return cmds

    def adjustVariantColname(self, colname):
        return colname

    def handle_renamed_files(self, genFilePath):
        pass

    def _getFamiliyTableValues(self, appinfoFilename):
        """
        Gets values from current appinfo (for merge)
        :returns dict(rowsid -> dict(name, value)
                 tableDef: dict col->(type of Attr or None, column name)
        """
        famTableValues = dict()
        tableDef = None
        tree = ElementTree.parse(appinfoFilename)
        rootEl = tree.getroot()
        if rootEl.tag != "appinfo":
            return None, None
        variants = rootEl.findall("variants")
        if not variants:
            return None, None
        updateTableDef = False
        for var in variants[0].findall("variant"):
            varid = var.attrib.get("id")
            parameters = var.findall("parameters")
            if parameters:
                rowDict = dict()
                if tableDef is None:
                    tableDef = dict()
                    updateTableDef = True
                for par in parameters[0].findall("parameter"):
                    parid = par.attrib.get("id")
                    colName = par.attrib.get("name")
                    t = par.attrib.get("type")
                    svalue = par.attrib.get("value")
                    if t in ["double", "float"]:
                        v = float(svalue)
                        if updateTableDef:
                            tableDef[parid] = (float, colName)
                    elif t == "int":
                        v = int(svalue)
                        if updateTableDef:
                            tableDef[parid] = (int, colName)
                    elif t == "bool":
                        v = svalue.lower() == "true"
                        if updateTableDef:
                            tableDef[parid] = (bool, colName)
                    else:
                        v = svalue
                        if updateTableDef:
                            tableDef[parid] = (six.text_type, colName)
                    rowDict[parid] = v
                updateTableDef = False
                famTableValues[varid] = rowDict
        self._job.log("family table values %s  tableDef: %s" % (famTableValues, tableDef))
        return famTableValues, tableDef

    def _getAdditionalVariantParams(self, vc, boItemAttrs, convertToUpperCase=False):
        """
        Use the .variantconfig to retrieve the additional parameters from
        the given item and document attributes.

        :param vc: VariantConfig
        :param boItemAttrs: dict(string: string)
            A merge of item and document attributes.
        :return: dict(string: string)
            The additional variant parameters, that are configured by the
            .variantconfig.
        """
        additionalVariantParams = {}
        part2fam = vc.getPart2familytable()
        if part2fam is not None:
            if isinstance(part2fam, dict):
                for famColumnId, boItemAttrName in part2fam.items():
                    if convertToUpperCase:
                        famColumnId = famColumnId.upper()
                    if boItemAttrName in boItemAttrs:
                        additionalVariantParams[famColumnId] = boItemAttrs[
                            boItemAttrName
                        ]
                    else:
                        logging.debug(
                            "DefaultCAD._getAdditionalVariantParams: "
                            "The parameter '%s' "
                            "does not exists.",
                            boItemAttrName
                        )
            else:
                logging.debug(
                    "DefaultCAD._getAdditionalVariantParams: "
                    "The part to family table configuration is not of type "
                    "dictionary"
                )
        else:
            logging.debug(
                "DefaultCAD._getAdditionalVariantParams: "
                "The part2fam mapping is empty"
            )
        return additionalVariantParams


def convertUcItemForFamCad(item,
                           cadsystem,
                           cad_modul,
                           cad_class,
                           view,
                           preset_callback=None,
                           complete_table=False):
    """
    :param item: vs.vp.items.Item
    :param cadsystem: str. the given System with out filtype specification like CatiaV5
    :param cad_modul: str. Name of python cad modul to load for execution
    :param cad_cls: str. Classname for class derived from UcCallBackBase
    :param viewname: str. cad_view in Modelassignments
    :param preset_callback: Callable

    This functions inserts the item into the conversion queue and creates the result document.

    Before adding the job to the queue a few base checks are running:
      * item belongs to sml group
      * for the given view "3DVIEW" and cadsystem a generic model in "ansicht" must exist

    If a variantmodel derived from the generic model exists for the given item the save access
    rights are checked. If no save access is possible for the current user index is checked.
    if index is possible a new index of the variant model is created.
    if no index access right is given. an AccessViolation is raised. No model will be converted

    The convertion is based on the variantconfig-file that belongs to generic model.
    Default values for document creations must be specified in CADDOK_BASE/etc/systemdefaults.json

    If preset_callback is given. This must be a function with the parameters (item, generic_doc).
    This function returns a dictionary with attribute-name -> value.

    This preset_callback updates/overwrites the parameter given by systemdefaults.json. It ca be
    used for generating special filenames or othe values in the document which depend on the item
    and generic values. This is mainly usefull to calculate the document number where a static
    mapping from the variantconfig is not sufficient.

    presets are only use when the system works in single document mode with disabled
    familytable functionaliy by setting variantconfig. part2familytable to null.


    documentPresets have the following priority (ascendig)
        ChangeControlAttributes
        variantconfig-Documentpresets
        systemdefaults
        preset_callback

    If the documentnumer is "#". then document.makenumber() will be called to genereat a new number.

    """
    if not _import_valid:
        raise MissingModulError("Modul cs.vp or cs.workspaces not found")
    generic_models = generics_for_item(item)
    ucClass, genericDoc = generic_models.get((cadsystem, view), (None, None))
    if not genericDoc or not ucClass:
        raise InvalidGenericError("Invalid generic Document (generic doesn't exists "
                                  "for cad and views: Generics:{}".format(generic_models))

    genericFiles = genericDoc.PrimaryFiles
    if len(genericFiles) != 1:
        raise InvalidGenericError("Invalid generic Document (No unique primaryfiles) %s %s" %
                                  (genericDoc.z_nummer, genericDoc.z_index))
    genericFile = genericFiles[0]
    genericName = genericFile.cdbf_name
    variantconfigname = genericName + ".variantconfig"
    variantconfigs = genericDoc.Files.KeywordQuery(cdbf_name=variantconfigname)
    if len(variantconfigs) != 1:
        raise InvalidGenericError("Invalid generic Document (variantconfig) %s %s %s" %
                                  (genericDoc.z_nummer, genericDoc.z_index, variantconfigname))
    variantConfigFile = variantconfigs[0]
    vc = VariantConfig()
    vcContent = variantConfigFile.get_content()
    res = vc.readFromBuffer(vcContent)
    if res.hasError():
        raise InvalidItemError("Invalid content in file %s" % variantconfigname)
    if vc.getPart2familytable() is None:
        # use single file mode for this generic
        return ucs.convertUcItem(item,
                                 cadsystem,
                                 cad_modul,
                                 cad_class,
                                 view,
                                 preset_callback,
                                 complete_table)
    else:
        # now continue in familytable mode
        appinfoFilename = genericName + ".appinfo"
        appinfoFiles = genericDoc.Files.KeywordQuery(cdbf_name=appinfoFilename)
        if len(appinfoFiles) != 1:
            raise InvalidGenericError("Invalid generic Document (appinfos) %s %s %s" %
                                      (genericDoc.z_nummer, genericDoc.z_index, appinfoFilename))
        appinfoFile = appinfoFiles[0]

        workDocument = genericDoc
        deleteOnFail = False
        # set this at the end callback
        # workDocument.generated_from = genericDoc.cdb_object_id
        parameters = {"deleteonfail": deleteOnFail,
                      "workdocument": workDocument.cdb_object_id,
                      "genericdocument": genericDoc.cdb_object_id,
                      "genericfile": genericFile.cdb_object_id,
                      "variantconfigname": variantconfigname,
                      "variantconfigcontent": vcContent,
                      "appinfofile": appinfoFile.cdb_object_id,
                      "item": item.cdb_object_id,
                      "ucclass": ucClass.cdb_object_id,
                      "complete_table": complete_table}

        job = create_cad_job(parameters, None, cad_modul, cad_class)
        return job
