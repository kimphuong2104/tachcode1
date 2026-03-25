# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucvariantssingle

This module provided the baseclass  for callback for creating or updating a
sml based parameteric model.
This modul is based on the cad job services
It must derived for every cad and registered via an entry point
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import six

import collections
import json
import os
import shutil
import logging
from lxml import etree as ElementTree

from cdb import rte
from cdb import fls
from cdb.objects.operations import operation, prefix_args, form_input
from cdb import constants
from cdb.objects import ByID
from cdb.objects.cdb_file import CDB_File
from cs.cadbase.wsutils.variantconfig import VariantConfig
from cs.cadbase import cadcommands
from cs.cadbase.pdminfohelper import PdmInfoHelper
from cs.cadbase.cadjobqueue import create_cad_job, JobCallBack, loaded_job_execs
from cs.cadbase.appinfohandler import remove_rel_paths

from cs.cadbase.sml.ucvariantsbase import InvalidGenericError, AccessViolationError
from cs.cadbase.sml.ucvariantsbase import InvalidItemError, SCQueueError, MissingModulError
from cs.cadbase.sml.ucvariantsbase import generics_for_item, checkout_structure

_import_valid = True
try:
    from cs.vp.cad import Model
    from cs.documents import Document
    from cs.wsm.index_helper import getIndexes
    from cs.wsm.pkgs.classification import class_for_generic, get_classification_for_item
except ImportError as e:
    logging.error("cs.cadbase.sml.ucvariantssingle: Modul not installed: %s", str(e))
    _import_valid = False


# Exported objects
__all__ = []


def log(s):
    logging.debug(s)


class UcCallBackBase(JobCallBack):
    """
    Handles variantmodel generation from SC items
    """

    def _getUCAttributes(self, workDir, genericDoc, item, view, cadKey, floatFormat):
        """
        :returns name/value dict for attributes to update in cad

        In sml all attributes were transferred to the cad model.
        In UC we may more attributes in class, so we have to reduce
        the attributes to the exiting attributes in CAD.
        see: _cadValuesFromUCClassInformation in WSM
        """
        uc_class = class_for_generic(genericDoc, view)
        ucClassInformation = get_classification_for_item(uc_class, item)
        cad_attributes = self.getCadAttributes(workDir, genericDoc)
        ucClassCode = uc_class.code
        idsToCadParam = dict()
        for paramId, paramTuple in cad_attributes.items():
            idsToCadParam[paramId.lower()] = paramTuple
        clsInfo = ucClassInformation["metadata"]["classes"][ucClassCode]
        propnames = ucClassInformation.get("_prop_names_", dict())
        cadPropIdsToVal = dict()
        clsInfo = ucClassInformation["metadata"]["classes"][ucClassCode]
        propnames = ucClassInformation.get("_prop_names_", dict())
        for propCode, prop in clsInfo["properties"].items():
            if cadKey in ("code", "catalog_code"):
                cadPropName = prop[cadKey]
            elif cadKey.startswith("name_"):
                cadPropName = propnames.get(propCode, "")
                if not cadPropName:
                    logging.debug("_getUCAttributes: "
                                  "cadproperty name is empty for  code: %s. and key: %s"
                                  "Perhaps misconfigured variantconfig", propCode, cadKey)
            if cadPropName:
                if cadPropName.lower() in idsToCadParam:
                    # lookup property value and set it in CAD.
                    # preferred ID before name:
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
                        cadValue = six.text_type(value)
                    if cadValue is not None:
                        cadPropIdsToVal[self.adjustVariantColname(cadPropName)] = cadValue
                else:
                    logging.debug("_getUCAttributes: "
                                  "ignoring value for cadPropName %s. Not in generic",
                                  cadPropName)
        return cadPropIdsToVal

    def adjustVariantColname(self, colname):
        """
        maybe ovewriten for case convertion
        """
        return colname

    def getCadAttributes(self, workdir, doc):
        """
        :returns dict with id-> (value, type, unit)
                 type and unit may be None
        """
        props = dict()
        primFile = doc.getPrimaryFile()
        appinfo_docs = doc.Files.KeywordQuery(cdbf_type="Appinfo",
                                              cdb_belongsto=primFile.cdb_wspitem_id)
        if appinfo_docs:
            appinfo_doc = appinfo_docs[0]
            appinfo_filename = os.path.join(workdir, appinfo_doc.cdbf_name)
            tree = ElementTree.parse(appinfo_filename)
            root = tree.getroot()
            properties = root.findall("properties/property")
            for p in properties:
                props[p.attrib["id"]] = (p.attrib["value"],
                                         p.attrib.get("type"),
                                         p.attrib.get("unit"))
        return props

    def _check_license(self, integrationSystem, job):
        """
        we have no special family table commands for this cad. So emulate the license we need
        throws fls.LicenseError
        """
        jobExecs = loaded_job_execs()
        jobExec = jobExecs.get(integrationSystem.lower())
        if jobExec is not None:
            licInfos = jobExec().getLicInfos()
            features = licInfos.getOperationFeatures("UPDATE_CADVARIANT_TABLE")
            if features is not None:
                for f in features:
                    fls.allocate_license(f)
                job.log("LICENSE CHECK PASSED")
                return
        log("LICENSE CHECK FAILED")
        job.log("LICENSE CHECK FAILED")
        raise fls.LicenseError("No License Infos for System:%s Op: %s" %
                               (integrationSystem, "UPDATE_CADVARIANT_TABLE"), "NO_APP_FEATURE")

    def pre(self, job):
        """
        checkout generic model and references for assemblies
        create jobs for static attributes, sc attribute, appinfo generation
        """
        log("UCVariantsSingle: *PRE_START*")
        parameter = job.get_parameter()
        genericDoc = ByID(parameter["genericdocument"])
        integrationSystem = genericDoc.erzeug_system.split(":")[0].lower()
        self._check_license(integrationSystem, job)
        genericFile = ByID(parameter["genericfile"])
        workDoc = ByID(parameter["workdocument"])
        workFilename = parameter["workfilename"]
        cad_view = parameter["view"]
        cadJobFilename = os.path.join(cadcommands.CadCommand.CAD_ROOT_DIR,
                                      os.path.basename(workFilename))

        workingDir = job.get_workspace()
        checkout_structure(workingDir, genericDoc)
        genericFilePath = os.path.join(workingDir, genericFile.cdbf_name)
        genericFile.checkout_file(genericFilePath)
        # Think about: better use a rename command?
        # but external referances are illegal in that case, or?
        shutil.copy2(genericFilePath, os.path.join(workingDir, workFilename))
        jobRunner = cadcommands.JobRunner(integrationSystem)
        cadJob = jobRunner.create_job()
        genericAttributes = {k: six.text_type(genericDoc[k]) for k in genericDoc.keys()}
        item = workDoc.Item
        itemAttributes = {k: six.text_type(item[k]) for k in item.keys()}

        vcContent = parameter["variantconfigcontent"]
        vc = VariantConfig()
        vc.readFromBuffer(vcContent)
        presetAttrs = vc.getCadPresetAttributes(genericAttributes, itemAttributes)
        if presetAttrs:
            jsonData, presetHash = PdmInfoHelper().getCadParameterForJson(presetAttrs)
            cmdSetParameter =\
                cadcommands.CmdSetParameter(
                    cadJobFilename,
                    [],
                    parameter_json=jsonData,
                    parameter_hash=presetHash,
                    regenerate=False,
                    flags=[cadcommands.processingFlags.SaveWorkFileAfterAction,
                           cadcommands.processingFlags.StopOnError])
            cadJob.append(cmdSetParameter)
        ucAttrs = self._getUCAttributes(workingDir,
                                        genericDoc,
                                        item,
                                        cad_view,
                                        vc.getCadPropertyValue(),
                                        vc.getFloatFormat())
        cmdSetUcParameter = self.generateUcParamCommand(cadJobFilename, ucAttrs)
        cadJob.append(cmdSetUcParameter)
        cmdSaveAppinfo =\
            cadcommands.CmdSaveAppInfo(cadJobFilename,
                                       [],
                                       "SINGLE",
                                       flags=[cadcommands.processingFlags.CloseWorkFileAfterAction,
                                              cadcommands.processingFlags.StopOnError])
        cadJob.append(cmdSaveAppinfo)
        job.save_cad_jobs(jobRunner)
        log("UCVariantsSingle: *PRE_END*")
        return []  # nothing

    def generateUcParamCommand(self, cadJobFilename, ucAttrs):
        """
        generates the command for updating the uc paremeters in model.
        this may depend on the cadsystem.
        The default implementatiosn just treats them as normal properties
        """
        jsonData, _ = PdmInfoHelper().getCadParameterForJson(ucAttrs)
        cmdSetParameterUc =\
            cadcommands.CmdSetParameter(cadJobFilename,
                                        [],
                                        parameter_json=jsonData,
                                        parameter_hash=None,
                                        regenerate=True,
                                        flags=[cadcommands.processingFlags.SaveWorkFileAfterAction,
                                               cadcommands.processingFlags.StopOnError])
        return cmdSetParameterUc

    def post(self, job, job_runner):
        """
        removes absolute path from appinfo
        """
        log("UCVariantsSingle: *POST_START*")
        parameter = job.get_parameter()
        workFilename = parameter["workfilename"]
        appinfoPath = os.path.join(job.get_workspace(),
                                   ".wsm",
                                   ".info",
                                   os.path.basename(workFilename) + u".appinfo")
        if os.path.isfile(appinfoPath):
            remove_rel_paths(appinfoPath)
        else:
            appinfoPath = None
        log("UCVariantsSingle: *POST_END*")
        return [appinfoPath]

    def done(self, job):
        """
        add or overwrite files to generated document
        """
        log("UCVariantsSingle: *DONE_START*")
        parameter = job.get_parameter()
        workDoc = ByID(parameter["workdocument"])
        workFilename = parameter["workfilename"]
        wfPath = os.path.join(job.get_workspace(), workFilename)
        appinfoFilepath = job.postResult[0]
        dstFile = None
        # wir erwarten genau eine oder keine primaere Datei
        # mit dem Zielnamen
        genericDoc = ByID(parameter["genericdocument"])
        integrationSystem = genericDoc.erzeug_system.split(":")[0]
        for pF in workDoc.PrimaryFiles:
            if pF.cdbf_name == workFilename:
                dstFile = pF
                break
        # reset locks. because index may have locked
        # the file to another user
        workDoc.Files.Update(cdb_lock="")
        if dstFile:
            dstFile.checkin_file(wfPath, {"cdb::argument.active_integration": integrationSystem,
                                          "cdb::argument.activecad": integrationSystem})
        else:
            dstFile = CDB_File.NewFromFile(workDoc.cdb_object_id,
                                           wfPath,
                                           True,
                                           {"cdbf_type": genericDoc.erzeug_system,
                                            "cdb::argument.active_integration": integrationSystem,
                                            "cdb::argument.activecad": integrationSystem})
        if appinfoFilepath:
            appinfoFileName = os.path.basename(appinfoFilepath)
            aiFile = None
            for aF in workDoc.Files:
                if aF.cdbf_name == appinfoFileName:
                    aiFile = aF
            if aiFile:
                aiFile.checkin_file(appinfoFilepath,
                                    {"cdb::argument.active_integration": integrationSystem,
                                     "cdb::argument.activecad": integrationSystem})
            else:
                aiFile = CDB_File.NewFromFile(
                    workDoc.cdb_object_id,
                    appinfoFilepath,
                    False,
                    {"cdb_belongsto": dstFile.cdb_wspitem_id,
                     "cdbf_type": "Appinfo",
                     "cdb::argument.active_integration": integrationSystem,
                     "cdb::argument.activecad": integrationSystem})
                aiFile.Update(cdb_lock="")
            log("UCVariantsSingle: *DONE_END*")

    def fail(self, job):
        """
        remove generated index or generated doc if cad job failed
        """
        log("UCVariantsSingle: **FAILED**")
        job.log("FAIL CALLED")
        parameter = job.get_parameter()
        deleteOnFail = parameter["deleteonfail"]
        if deleteOnFail:
            workDoc = ByID(parameter["workdocument"])
            operation(constants.kOperationDelete, workDoc)
        log("UCVariantsSingle: **FAILED** END")


def convertUcItem(item,
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

    documentPresets have the following priority (ascendig)
        ChangeControlAttributes
        variantconfig-Documentpresets
        systemdefaults
        preset_callback

    If the documentnumer is "#". then document.makenumber() will be called to genereat a new number.

    """
    if not _import_valid:
        raise MissingModulError("One of the expected moduls cs.vp, cs.documents or "
                                "cs.workspaces not found")
    generic_models = generics_for_item(item)
    ucClass, genericDoc = generic_models.get((cadsystem, view))
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
    genericAttributes = {k: six.text_type(genericDoc[k]) for k in genericDoc.keys()}
    itemAttributes = {k: six.text_type(item[k]) for k in item.keys()}
    _, extension = os.path.splitext(genericName)
    dstFilename = vc.getFilename(genericAttributes, itemAttributes) + extension
    # welche Dokumente gibt es, die nicht obsolete sind und deren Dateinamen
    # dem Zieldateinamen entspricht

    existingDocs = Document.KeywordQuery(cdb_obsolete=0,
                                         teilenummer=item.teilenummer,
                                         t_index=item.t_index,
                                         erzeug_system=genericDoc.erzeug_system)
    existingDocs = _filterGenericDocs(existingDocs, dstFilename)
    if len(existingDocs) > 1:
        raise InvalidItemError("No unique variant document found")
    workDocument = None
    deleteOnFail = False
    if existingDocs:
        existingDoc = existingDocs[0]
        # check access and try index or save directly
        if existingDoc.CheckAccess("save"):
            workDocument = existingDoc
        elif existingDoc.CheckAccess("index"):
            workDocument = _createIndex(existingDoc)
            deleteOnFail = True
        else:
            raise AccessViolationError("")
    else:
        workDocument = _createNewDocument(vc, genericDoc, item, preset_callback)
        deleteOnFail = True
    if not workDocument:
        raise SCQueueError("Workdocument failed")
    # set this at the end callback
    # workDocument.generated_from = genericDoc.cdb_object_id
    parameters = {"workdocument": workDocument.cdb_object_id,
                  "deleteonfail": deleteOnFail,
                  "genericdocument": genericDoc.cdb_object_id,
                  "genericfile": genericFile.cdb_object_id,
                  "variantconfigcontent": vcContent,
                  "workfilename": dstFilename,
                  "view": view}

    job = create_cad_job(parameters, None, cad_modul, cad_class)
    return job


def _readSystemDefaults():
    """
    """
    caddokBase = rte.environ["CADDOK_BASE"]
    systemDefaults = os.path.join(caddokBase, "etc", "systemdefaults.json")
    defaultValues = {}
    with open(systemDefaults, "r") as f:
        defaultValues = json.load(f)
    return defaultValues


def _createIndex(doc):
    """
    creates a document index with copy of relations
    """
    cad = doc.erzeug_system.split(":")[0]
    indexDoc = operation(constants.kOperationIndex,
                         doc,
                         prefix_args("cdb::argument.",
                                     create_part_index="0",
                                     activecad=cad,
                                     active_integration=cad,
                                     max_part_index="0"))
    return indexDoc


def _createNewDocument(vc, genericDoc, item, preset_callback):
    """
    """
    systemDefaultValues = _readSystemDefaults()
    genericAttributes = {k: six.text_type(genericDoc[k]) for k in genericDoc.keys()}
    itemAttributes = {k: six.text_type(item[k]) for k in item.keys()}
    presetValues = dict()
    presetValues.update(vc.getDocumentPresets(genericAttributes, itemAttributes))
    presetValues.update(systemDefaultValues)
    if preset_callback is not None:
        presetValues.update(preset_callback(genericDoc, item))
    presetValues[constants.kArgumentSkipFileCopy] = "1"
    cadSystem = genericDoc.erzeug_system.split(":")[0]
    presetValues[constants.kArgumentActiveCAD] = cadSystem
    presetValues[constants.kArgumentActiveIntegration] = cadSystem
    log("PRESET: %s" % presetValues)
    doc = operation(constants.kOperationCopy, genericDoc, form_input(Model, **presetValues))
    return doc


def _filterGenericDocs(existingDocs, dstFilename):
    """
    returns a list of documents with different z_number where
    the file matches and in cases of not unique index the largest
    index for the number (based on ixsm property)
    """
    filteredDocs = []
    docsByNumber = collections.defaultdict(list)
    for ed in existingDocs:
        for existingFile in ed.PrimaryFiles:
            if existingFile.cdbf_name == dstFilename:
                docsByNumber[ed.z_nummer].append(ed)
    # jetzt das aktuellste Dokument pro nummer ermitteln.
    # wir hatten schon einen filter auf cdb_obsolete. Es sollte
    # daher das Dokument mit dem hoechsten Index verwendet werden.
    for docList in docsByNumber.values():
        maxIndex = -1
        maxDoc = None
        for doc in docList:
            _, _, myIndex = getIndexes(doc)
            if myIndex > maxIndex:
                maxDoc = doc
                maxIndex = myIndex
        filteredDocs.append(maxDoc)
    return filteredDocs
