#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module attributesaccessor

Operations for accessing PDM attributes of different workspace objects
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import defaultdict
import logging
import calendar

from cdb.i18n import default
from cdb import ue
from cdb import auth
from cdb.objects.cdb_file import cdb_file_base
from cdb.objects.fields import (
    JoinedMultiLangAttributeDescriptor,
    MappedMultiLangAttributeDescriptor,
    MappedAttributeDescriptor,
)
from cs.wsm.pkgs.pkgsutils import getCdbClassname
from cs.platform.web.rest import get_collection_app
from cs.platform.web import uisupport

reducedAttributeSets = {
    u"Document": [
        "cdb_classname",
        "cdb_object_id",
        "erzeug_system",
        "titel",
        "z_nummer",
        "z_index",
        "cdb_mdate",
        "wsm_is_cad",
        "standard_library",
        "generated_from",
    ],
    u"Variant": [
        "name",
        "cdb_object_id",
        "cdb_status_txt",
        "status",
        "joined_status_name",
        "category_name",
        "cdb_project_id",
        "cdb_objektart",
        "cdb_classname",
    ],
    u"WsDocument": ["json_object_attrs"],
    u"cdb_file": [
        "cdbf_name",
        "cdbf_type",
        "cdb_folder",
        "cdb_wspitem_id",
        "cdbf_blob_id",
        "cdb_belongsto",
        "cdbf_primary",
        "cdbf_hash",
        "cdbf_fdate",
    ],  # will be renamed to cdbf_blob_date
    u"cdb_link_item": ["cdbf_name", "cdb_folder", "cdb_wspitem_id", "cdb_link"],
    u"cdb_folder_item": ["cdbf_name", "cdb_folder", "cdb_belongsto", "cdb_wspitem_id"],
}
reducedAttributeSets[u"cdb_file_record"] = reducedAttributeSets[u"cdb_file"]


# together with the reduced attribute sets these attributes
# build the minimal set of attributes to transfer during
# a checkin/checkout
additionalAttributeSets = {
    u"Document": [
        "benennung",
        "erzeug_system",
        "t_index",
        "teilenummer",
        "z_format",
        "z_format_gruppe",
        "i18n_benennung",
        "z_art",
        "z_status",
        "joined_status_name",
        "additional_document_type",
    ],
    u"Variant": [
        "name",
        "cdb_object_id",
        "cdb_status_txt",
        "status",
        "joined_status_name",
        "category_name",
        "cdb_project_id",
        "cdb_objektart",
        "cdb_classname",
    ],
    u"cdb_file": ["cdbf_description"],
    u"cdb_link_item": ["cdb_mdate", "cdbf_type"],
    u"cdb_folder_item": ["cdb_mdate", "cdbf_type"],
}


# this attribute set is used to get a list of objects on the server quickly
reducedAttributeSetsSimplified = {
    u"Document": ["cdb_classname", "cdb_object_id", "erzeug_system"],
    u"Variant": [
        "name",
        "cdb_object_id",
        "cdb_status_txt",
        "status",
        "joined_status_name",
        "category_name",
        "cdb_project_id",
        "cdb_objektart",
        "cdb_classname",
    ],
    u"cdb_file": ["cdb_wspitem_id"],
    u"cdb_link_item": ["cdb_wspitem_id"],
    u"cdb_folder_item": ["cdb_wspitem_id"],
}

# this attribute set is used to get a list of objects on the server quickly
reducedAttributeSetsSimplifiedSupportingFilter = reducedAttributeSetsSimplified.copy()
reducedAttributeSetsSimplifiedSupportingFilter[u"cdb_file"] = [
    "cdb_wspitem_id",
    "cdbf_blob_id",
    "cdbf_name",
]


# attributes that can be skipped in itemlisttodict. They
# must not become xml elements (ATTRIBUTE) in the server reply bedause they
# are included in the corresponding xml elements attributes (e.g. WSCOMMANDS_OBJECT)
filteredCdbFileAttributes = set([u"cdb_object_id", u"cdb_classname", u"cdbf_object_id"])


class ReducedAttributes(object):
    ALL_ATTRIBUTES = 0
    # reduces set for status update and similar
    REDUCED_ATTRIBUTES = 1
    # smallest set of identifying attributes
    LEAST_ATTRIBUTES = 2
    # like LEAST_ATTRIBUTES with some attributes added, see E037779 (request is similar to
    # status update for some specific files, used in some type of assignPDMObjects-operation)
    FILTER_ATTRIBUTES = 3


class AttributesCollector(object):
    def __init__(self, lang=None, webrequest=None):
        # object type to ignored/inaccessible attributes
        self._ignored = defaultdict(set)
        # additional attributes requested by by wsm (-settings)
        self._requestedDocAttributes = None
        self._requestedFileAttributes = None
        # is used for caching multi language attribute descriptor fields
        # like joned_status_name
        self.lang = lang or default()
        # maps string with object type, e.g. Document or cdb_file
        # to set of multi language attribute names
        self.multiLangAttributeFields = {}
        self._presignedBlobsEnabled = False
        self.checkInMode = False  # Attribute accessor is used for checkin or checkout
        # limit generation of presigned blobs urls to this file ids
        self._checkinObjIds = set()
        self._persno = auth.persno
        self._webrequest = webrequest
        if webrequest is not None:
            self._coll_app = get_collection_app(webrequest)

    def setRequestedDocAttributes(self, docAttributes):
        self._requestedDocAttributes = docAttributes

    def setRequestedFileAttributes(self, fileAttributes):
        self._requestedFileAttributes = fileAttributes

    def getIgnoredAttributes(self):
        return self._ignored

    def setPresignedBlobsEnabled(self, enabled):
        self._presignedBlobsEnabled = enabled

    def setCheckinObjIds(self, checkinObjIds):
        self._checkinObjIds = checkinObjIds

    def getDocumentAttributes(
        self, obj, reducedAttributes=ReducedAttributes.ALL_ATTRIBUTES, objType=None
    ):
        logging.debug(
            "+++ getDocumentAttributes start (reducedAttributes: %s)", reducedAttributes
        )
        nameValDict = None
        if objType is None:
            objType = u"Document"
        minimalAttributes = self._getMinimalNeededAttributes(
            reducedAttributes, obj, objType
        )
        self._cacheMultiLangAttributeFields(obj, objType)

        if reducedAttributes in (
            ReducedAttributes.LEAST_ATTRIBUTES,
            ReducedAttributes.FILTER_ATTRIBUTES,
        ):
            nameValDict = self._getDefaultAndMappedAttributes(obj, minimalAttributes)
        else:
            neededAttributes = set(minimalAttributes)

            # add default additional attributes
            neededAttributes.update(additionalAttributeSets.get(objType))
            if self._requestedDocAttributes:
                neededAttributes.update(self._requestedDocAttributes)

            nameValDict = self._getDocumentAttributes(obj, objType, neededAttributes)
        if self._webrequest is not None:
            nameValDict["_rest_id_"] = self._webrequest.link(obj, app=self._coll_app)
            nameValDict["_system_ui_link_"] = uisupport.get_webui_link(
                self._webrequest, obj
            )
        logging.debug("+++ getDocumentAttributes end")
        return nameValDict

    def getStatusRelevantFileAttributes(self):
        neededAttributes = set()
        for subType in (u"cdb_file", u"cdb_link_item", u"cdb_folder_item"):
            neededAttributes.update(reducedAttributeSets.get(subType))
            neededAttributes.update(additionalAttributeSets.get(subType))
        if self._requestedFileAttributes:
            neededAttributes.update(self._requestedFileAttributes)
        # always needed
        neededAttributes.update(
            (
                "cdb_object_id",
                "cdbf_object_id",
                "cdb_classname",
                "cdb_lock",
                "cdb_lock_id",
            )
        )

        unvalidatedAttrs = neededAttributes - set(cdb_file_base.GetFieldNames())
        multiLangTypes = [
            MappedMultiLangAttributeDescriptor,
            JoinedMultiLangAttributeDescriptor,
        ]
        unknownAttrs = []
        for attr in unvalidatedAttrs:
            try:
                field = cdb_file_base.GetFieldByName(attr)
                fieldType = type(field)
                if fieldType == MappedAttributeDescriptor:
                    if attr == "mapped_cdb_lock_name":
                        # we get this attribute later via sql
                        neededAttributes.remove(attr)
                    else:
                        # yet unsupported
                        return None

                elif type(field) in multiLangTypes:
                    neededAttributes.remove(attr)

                    langDependentFieldName = field.getLanguageField(self.lang).name
                    if langDependentFieldName is not None:
                        neededAttributes.add(langDependentFieldName)

            except AttributeError:
                neededAttributes.remove(attr)
                unknownAttrs.append(attr)

        if unknownAttrs:
            unknownAttrsStr = ", ".join(unknownAttrs)
            logging.warning("Inaccessible file attributes: %s", unknownAttrsStr)

        return neededAttributes

    def getFileAttributes(
        self, obj, reducedAttributes=ReducedAttributes.ALL_ATTRIBUTES
    ):
        """
        Get attributes for cdb_file based objects, also cdb_link_items
        """
        logging.debug(
            "+++ getFileAttributes start (reducedAttributes: %s)", reducedAttributes
        )
        nameValDict = None
        objType = obj.cdb_classname
        minimalAttributes = self._getMinimalNeededAttributes(
            reducedAttributes, obj, objType
        )
        self._cacheMultiLangAttributeFields(cdb_file_base, objType)

        if reducedAttributes in (
            ReducedAttributes.LEAST_ATTRIBUTES,
            ReducedAttributes.FILTER_ATTRIBUTES,
        ):
            nameValDict = self._getDefaultAndMappedAttributes(obj, minimalAttributes)
        else:
            neededAttributes = set(minimalAttributes)

            # always use reduced attribute sets for preview and appinfo files
            if not getattr(obj, "cdb_belongsto", None):
                # add default additional attributes
                additionalAttributes = additionalAttributeSets.get(objType)
                if additionalAttributes:
                    neededAttributes.update(additionalAttributes)

                if self._requestedFileAttributes:
                    neededAttributes.update(self._requestedFileAttributes)

                neededAttributes -= filteredCdbFileAttributes

            nameValDict = self._getAttributes(obj, objType, neededAttributes)
            fdate = nameValDict.pop("cdbf_fdate", None)
            if fdate:
                nameValDict["cdbf_blob_date"] = calendar.timegm(fdate.timetuple())

        # The following Code is more a prototype
        # CDB_File- method may change
        # We must think about access check
        if self._presignedBlobsEnabled:
            try:
                if self.checkInMode:
                    # checkin. server reply contains all document files
                    # but only new/modified files need a blob url (performance)
                    if (obj.cdbf_object_id, obj.cdb_wspitem_id) in self._checkinObjIds:
                        # if locked by other user dont generate the url to force
                        # talkapi transfer with comprehensible error message
                        cdbLock = obj.cdb_lock
                        if not cdbLock or cdbLock == self._persno:
                            if objType in [u"cdb_file", u"cdb_file_record"] and hasattr(
                                obj, "presigned_blob_write_url"
                            ):
                                nameValDict["blob_url"] = obj.presigned_blob_write_url(
                                    check_access=False
                                )
                else:
                    # checkout
                    if objType == u"cdb_file" and hasattr(obj, "presigned_blob_url"):
                        nameValDict["blob_url"] = obj.presigned_blob_url(
                            check_access=False, emit_read_signal=True
                        )
            except IOError:
                logging.exception("access to presigned_blob_url failed: ")
            except ue.Exception as e:
                logging.exception("access to presigned_blob_url failed: ")
                # If presigned blob mode is enabled, we want to load blobs via
                # generated url here. If an error occurs due to UE, then the
                # UE decided to not load this blob. That's why we re-raise the
                # exception here. In the layers above, we want to skip the
                # loading of this blob and the corresponding document.
                raise e
        logging.debug("+++ getFileAttributes end")
        return nameValDict

    def getFrameAttributes(
        self, obj, reducedAttributes=ReducedAttributes.ALL_ATTRIBUTES
    ):
        logging.debug(
            "+++ getFrameAttributes start (reducedAttributes: %s)", reducedAttributes
        )
        nameValDict = None
        objType = type(obj)
        minimalAttributes = self._getMinimalNeededAttributes(
            reducedAttributes, obj, objType
        )
        self._cacheMultiLangAttributeFields(obj, objType)

        if reducedAttributes in (
            ReducedAttributes.LEAST_ATTRIBUTES,
            ReducedAttributes.FILTER_ATTRIBUTES,
        ):
            nameValDict = self._getDefaultAndMappedAttributes(obj, minimalAttributes)
        else:
            nameValDict = self._getAttributes(obj, objType, set(minimalAttributes))

        nameValDict["cdb_classname"] = "cdb_frame"
        if self._webrequest is not None:
            nameValDict["_rest_id_"] = self._webrequest.link(obj, app=self._coll_app)
            nameValDict["_system_ui_link_"] = uisupport.get_webui_link(
                self._webrequest, obj
            )
        logging.debug("+++ getFrameAttributes end")
        return nameValDict

    def _getMinimalNeededAttributes(self, reducedAttributes, obj, objType):
        minimalAttributes = None
        if reducedAttributes == ReducedAttributes.REDUCED_ATTRIBUTES:
            minimalAttributes = reducedAttributeSets.get(objType)

        elif reducedAttributes == ReducedAttributes.LEAST_ATTRIBUTES:
            minimalAttributes = reducedAttributeSetsSimplified.get(objType)

        elif reducedAttributes == ReducedAttributes.FILTER_ATTRIBUTES:
            minimalAttributes = reducedAttributeSetsSimplifiedSupportingFilter.get(
                objType
            )

        if minimalAttributes is None:
            # fallback for other object type, e.g. frames
            minimalAttributes = set(obj.keys())
            minimalAttributes -= filteredCdbFileAttributes
        return minimalAttributes

    def _getDefaultAndMappedAttributes(self, obj, attributes):
        """
        Get easily accessable default and mapped attributes only
        """
        nameValDict = {}
        for k in attributes:
            nameValDict[k] = obj[k]
        return nameValDict

    def _getDocumentAttributes(self, obj, objType, attributes):
        """
        Access object attributes

        :Parameters:
           attributes: iterable of attribute names
        """
        # handle/selection on zeichnung_v is needed anyway, e.g.
        # for accessing "t_bereich" from document object
        hdl = obj.ToObjectHandle()
        return self._getAttributes(hdl, objType, attributes)

    def _getAttributes(self, obj, objType, attributes):
        """
        Access object attributes

        :Parameters:
           attributes: iterable of attribute names
        """
        nameValDict = {}
        className = getCdbClassname(obj)
        ignoredAttributes = self._ignored[className]
        attributes -= ignoredAttributes
        multiLangFields = self.multiLangAttributeFields[objType]

        for attribute in attributes:
            try:
                langDepName = multiLangFields.get(attribute, attribute)
                nameValDict[attribute] = obj[langDepName]

            except (AttributeError, KeyError):
                ignoredAttributes.add(attribute)
        return nameValDict

    def _cacheMultiLangAttributeFields(self, obj, objType):
        """
        Pre-Cache all fields of the given object which are multi language
        fields by object type.
        """
        if objType not in self.multiLangAttributeFields:
            fields = {}
            multiLangTypes = [
                MappedMultiLangAttributeDescriptor,
                JoinedMultiLangAttributeDescriptor,
            ]
            for f in obj.GetFields(any):
                if type(f) in multiLangTypes:
                    langDependentFieldName = None
                    langDependentField = f.getLanguageField(self.lang)
                    if langDependentField is not None:
                        langDependentFieldName = langDependentField.name
                        if langDependentFieldName is not None:
                            fields[f.name] = langDependentFieldName
                    else:
                        logging.debug(
                            "Unable to determine language dependent field "
                            "for language: '%s' for field: '%s'",
                            self.lang,
                            f.name,
                        )

                    if langDependentFieldName is None:
                        self._ignored[getCdbClassname(obj)].add(f.name)
                    else:
                        fields[f.name] = langDependentFieldName

            self.multiLangAttributeFields[objType] = fields
