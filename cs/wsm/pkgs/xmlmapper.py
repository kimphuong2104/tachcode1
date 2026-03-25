#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import six
import sys
import json

from lxml import etree as ElementTree

if six.PY2:
    NEWPARA = unichr(0x2029)
else:
    NEWPARA = chr(0x2029)

if six.PY2:
    NEWLINE = unichr(0x2028)
else:
    NEWLINE = chr(0x2028)


LINEBREAK = u"\n"
LINEBREAK_DOUBLE = u"\n\n"
WSM_IMPORT_ERROR = u"WSM_IMPORT_ERROR"
SERVER_REPLY_HASH_EQUAL = u"SERVER_REPLY_HASH_EQUAL"


def encodedNewlines(txt):
    return txt.replace(LINEBREAK_DOUBLE, NEWPARA).replace(LINEBREAK, NEWLINE)


def decodedNewlines(txt):
    return txt.replace(NEWPARA, LINEBREAK_DOUBLE).replace(NEWLINE, LINEBREAK)


class XmlMapper(object):

    """
    Abstract class. Mapper to marshall python objects to XML.
    """

    _objectAttrs = {}

    __slots__ = ["etreeElem", "_objAttrs", "_hashAttrs", "_accessAttrs"]

    def __init__(self, **kwArgs):
        """
        Initialize object.

        :Parameters:
            kwArgs : standard python keyword argument dict
                The keywords will be used to create the attributes of the
                class.
        """
        for k, v in six.iteritems(kwArgs):
            if v is not None:
                v = encodedNewlines(six.text_type(v))
                kwArgs[k] = v
            else:
                kwArgs[k] = u""
        self.etreeElem = ElementTree.Element(self.__class__.__name__, kwArgs)

        self._objAttrs = None
        self._hashAttrs = None
        self._accessAttrs = None

    def __getattr__(self, name):
        # prefer etree
        val = self.etreeElem.attrib.get(name, None)
        if val is None:
            # suche im dict
            if name not in self._objectAttrs:
                raise AttributeError
            return u""
        return decodedNewlines(six.text_type(val))

    def setAttr(self, name, value):
        if name in six.iterkeys(self._objectAttrs):
            value = encodedNewlines(value)
            self.etreeElem.attrib[name] = value
        else:
            raise AttributeError(name)

    def hasAttr(self, name):
        return name in self.etreeElem.attrib

    def toXmlTree(self):
        """
        Return an ElementTree.Element instance generated from self.

        The instances attributes are mapped to XML attributes, the
        contents of _children are serialized recursively.
        """
        return self.etreeElem

    def toEncodedString(self):
        """
        This method converts the ``etree.Element`` object from lxml
        into an XML representation as a string for Python 2 or
        a byte string for Python 3.

        :return: Returns the XML element as a string or byte string.
        :rtype: str | bytes
        """
        # return str or bytes, depends on Python version, see docstring
        return ElementTree.tostring(self.etreeElem, encoding="utf-8")

    def addChild(self, xmlMapperInst):
        """
        Add a child element to self.

        :Parameters:
            xmlMapperInst : XmlMapper instance
                a subelement to be added.
        """
        self.etreeElem.append(xmlMapperInst.etreeElem)

    def len(self):
        return len(self.etreeElem)

    def getChildren(self):
        ret = []
        for c in self.etreeElem.getchildren():
            ret.append(xmlTree2Object(c))
        return ret

    def getChildrenByName(self, name):
        """
        Return all direct children of self of type 'name'.

        :Parameters:
            name : string
                name of the type to search for
        :return:
            list of XmlMapper children of type 'name'
        """
        ret = []
        for c in self.etreeElem.findall(name):
            ret.append(xmlTree2Object(c))
        return ret

    def getFirstChildByName(self, name):
        """
        Return first direct children of self of type 'name'.

        :Parameters:
            name : string
                name of the type to search for
        :return:
            XmlMapper element of type 'name' or None
        """
        xmlMapperElem = None
        elem = self.etreeElem.find(name)
        if elem is not None:
            xmlMapperElem = xmlTree2Object(elem)
        return xmlMapperElem

    def initializeAttributes(self):
        pass

    def _getAttributesList(self, name):
        aTag = self.getFirstChildByName(name)
        if aTag is not None:
            attributes = aTag.attributes
        else:
            attributes = dict()
        return attributes

    def getObjectAttributes(self):
        if self._objAttrs is None:
            self._objAttrs = self._getAttributesList("ATTRIBUTES")
        return self._objAttrs

    def getHashAttributes(self):
        if self._hashAttrs is None:
            self._hashAttrs = self._getAttributesList("HASHES")
        return self._hashAttrs

    def getLinksStatus(self):
        linksStatus = {}
        cmdLinksStatusList = self.getChildrenByName("LINKSSTATUS")
        for cmdLinksStatus in cmdLinksStatusList:
            linkStatusList = cmdLinksStatus.getChildrenByName("LINKSTATUS")
            for linkStatus in linkStatusList:
                linksStatus[linkStatus.link_id] = int(linkStatus.relevant)
        return linksStatus

    def getAdditionalAttributes(self):
        docAttributes = set()
        fileAttributes = set()
        attrsLists = self.getChildrenByName("ADDITIONALATTRIBUTES")
        for attrsList in attrsLists:
            attrs = attrsList.getChildrenByName("ADDITIONALDOCATTRIBUTE")
            for attr in attrs:
                docAttributes.add(attr.name)
            attrs = attrsList.getChildrenByName("ADDITIONALFILEATTRIBUTE")
            for attr in attrs:
                fileAttributes.add(attr.name)
        additionalAttributes = (docAttributes, fileAttributes)
        return additionalAttributes

    def getAdditionalIndexAttributes(self):
        docAttributes = set()
        attrsLists = self.getChildrenByName("ADDITIONALINDEXATTRIBUTES")
        for attrsList in attrsLists:
            attrs = attrsList.getChildrenByName("ADDITIONALDOCATTRIBUTE")
            for attr in attrs:
                docAttributes.add(attr.name)
        return docAttributes

    def getBomAttrs(self):
        def _parseFields(elemWithFields):
            parsed = set()
            if elemWithFields:
                toParse = elemWithFields.fields
                if toParse:
                    fields = toParse.split(",")
                    for field in fields:
                        parsed.add(field.strip(",").strip(" "))
            return parsed

        itemAttrs = set()
        bomItemAttrs = set()
        itemAttrsElem = self.getFirstChildByName("ITEM_ATTRIBUTES")
        if itemAttrsElem is not None:
            itemAttrs = _parseFields(itemAttrsElem)

        bomItemAttrsElem = self.getFirstChildByName("BOM_ITEM_ATTRIBUTES")
        if bomItemAttrsElem is not None:
            bomItemAttrs = _parseFields(bomItemAttrsElem)
        return itemAttrs, bomItemAttrs

    def getRights(self):
        rightMap = {}
        cdbRightsElem = self.getFirstChildByName("RIGHTS")
        if cdbRightsElem is not None:
            for rightName, rightValue in six.iteritems(cdbRightsElem.attributes):
                rightMap[rightName] = rightValue
        return rightMap

    def getLockInfo(self):
        lockInfo = None
        lockInfoElem = self.getFirstChildByName("LOCKINFO")
        if lockInfoElem is not None:
            lockInfo = (
                lockInfoElem.status,
                lockInfoElem.locker,
                lockInfoElem.status_teamspace,
                lockInfoElem.locker_teamspace,
            )
        return lockInfo

    def getSearchReferrers(self):
        refs = {}
        searchRefs = self.getChildrenByName("SEARCH_REFERER")
        if searchRefs:
            for searchRef in searchRefs:
                targets = searchRef.getChildrenByName("TARGET")
                if targets:
                    for target in targets:
                        referrers = target.getChildrenByName("REFERER")
                        if referrers:
                            referrerIds = []
                            for referrer in referrers:
                                referrerIds.append(referrer.id)
                            refs[target.id] = referrerIds
        return refs


class XmlMapperWithAttrCache(XmlMapper):
    """
    Specialization for Xml elements containing arbitrary XML attributes.

    Cache the contents of the attributes in a dictionary.
    """

    __slots__ = ["etreeElem", "_objAttrs", "_hashAttrs", "_accessAttrs", "attributes"]

    def initializeAttributes(self):
        """
        Store contents of the ATTRIBUTE child elements in a dictionary.

        For each ATTRIBUTE child, the correspondent (name, value) pairs
        are stored in dictionary self.attributes.
        """
        self.attributes = dict()
        self.attributes.update(self.etreeElem.attrib)

    def setAttr(self, name, value):
        # overwritten to allow arbitrary attributes
        value = encodedNewlines(u"%s" % value)
        self.etreeElem.attrib[name] = value


class XmlMapperComparable(XmlMapperWithAttrCache):

    __slots__ = ["etreeElem", "_objAttrs", "_hashAttrs", "_accessAttrs", "attributes"]

    def __eq__(self, other):
        ret = False
        if other is not None:
            if (
                self.etreeElem.attrib["cdb_object_id"] != ""
                and other.etreeElem.attrib["cdb_object_id"] != ""
                and self.etreeElem.attrib["cdb_object_id"] is not None
                and other.etreeElem.attrib["cdb_object_id"] is not None
            ):

                ret = (
                    self.etreeElem.attrib["cdb_object_id"]
                    == other.etreeElem.attrib["cdb_object_id"]
                )
        return ret

    def __hash__(self):
        ret = ""
        if (
            self.etreeElem.attrib["cdb_object_id"] != ""
            and self.etreeElem.attrib["cdb_object_id"] is not None
        ):
            ret = self.etreeElem.attrib["cdb_object_id"]
        return hash(six.text_type(ret))


def registerClasses(theModule):
    """
    Register all subclasses of XmlMapper in this module.
    """
    moduleDict = sys.__dict__["modules"][theModule].__dict__

    localClassDict = {}
    for key in moduleDict.keys():
        obj = moduleDict[key]
        if type == type(obj):
            if issubclass(obj, XmlMapper):
                localClassDict[obj.__name__] = obj
    return localClassDict


# ---------------------------RNC-COMPONENTS---------------------------
class PARAMETERS(XmlMapperWithAttrCache):
    __slots__ = []


class WSCOMMANDS_CONTEXTOBJECT(XmlMapperComparable):
    # RNC DEFINITION
    # attribute cdb_object_id { text },
    # CommandStatusList?,
    # Attributes?,
    # Variants?,
    # Command?,
    # Hashes?,
    # Rights?,
    # Relationships?,
    # WsCommands_Object*,
    # LockInfo?
    __slots__ = []
    _objectAttrs = dict(
        cdb_object_id=None,
        numberkey=None,
        indexsortval=None,
        file_count=None,
        new_docs_ratio=None,  # float; extra info for optimizations
        incomplete=None,  # int; 1 if link items have been cut off
        teamspace_obj=None,  # cdb_object_id of WsDocuments if requested and it exists
        json_object_attrs=None,  # ""|json dump; attrs for TS only docs
        commit_mode=None,  # "pdm"|"teamspace"|"prepare_publish"|"publish
        initial_publish=None,  # int; whether this teamspace object is published for the first time
        commit_action=None,
        cdb_classname=None,  # str with classname
    )  # str; the bobject commit action from client


class WSCOMMANDS_OBJECT(XmlMapperComparable):
    # e.g. u"cdb_file" u"cdb_folder_item" u"cdb_link_item"
    # attribute class { text },
    # attribute cdb_object_id { text },
    # id assigned locally before PDM id is assigned
    # attribute local_id { text },
    # Hashes,
    # LockInfo,
    # Command,
    # Attributes,
    # Relationships
    __slots__ = []
    _objectAttrs = dict(
        cdb_classname=None,
        cdb_object_id=None,
        local_id=None,
        # cdb_folder = None,
        # cdb_link = None,
        # cdb_belongsto = None
    )


class COMMAND(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(action=None, force=u"no")  # u"yes" or u"no"


class NEWINDEXVERSIONS(XmlMapper):
    # 0..n NEWINDEX object(s) goes here
    __slots__ = []


class NEWINDEX(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(cdb_object_id=None)


class LOCKINFO(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        status=None,  # = u"not|self|other|other ws"
        locker=None,  # "Sperrender"
        status_teamspace=None,  # = u"not|self|other|other ws" (optional)
        locker_teamspace=None,
    )  # "Sperrender" in the teamspace (optional)


class HASHES(XmlMapperWithAttrCache):
    __slots__ = []


class VARIANTPROPERTIES(XmlMapperWithAttrCache):
    __slots__ = []


class RELATIONSHIPS(XmlMapper):
    # n RELATION object(s) goes here
    __slots__ = []


class RELATIONSHIP(XmlMapper):
    __slots__ = []
    name = None


class RIGHTS(XmlMapperWithAttrCache):
    __slots__ = []


class FILES(XmlMapper):
    # n OBJECT object(s) goes here
    __slots__ = []


class LINKS(XmlMapper):
    # n OBJECT object(s) goes here
    __slots__ = []


class DIRECTORIES(XmlMapper):
    # n OBJECT object(s) goes here
    __slots__ = []


class ATTRIBUTES(XmlMapperWithAttrCache):
    __slots__ = []


class SEARCH_REFERER(XmlMapper):
    __slots__ = []


class SEARCH_REFERER_RESULT(XmlMapper):
    __slots__ = []


class TARGET(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(id=None)


class REFERER(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(id=None)


class VARIANTS(XmlMapper):
    # n VARIANT object(s) goes here
    __slots__ = []


class VARIANT(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(id=None, name=None, parameters=None)


class SHEETS(XmlMapper):
    # n OBJECT object(s) goes here
    __slots__ = []


class SHEET(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(id=None, number=None, cdb_object_id=None)


class LINKSSTATUS(XmlMapper):
    __slots__ = []
    # n LINKSTATUS object(s) goes here


class LINKSTATUS(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(link_id=None, relevant=None)


class PARTNERNAME(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(organization_id=None, filename=None)


class ADDITIONALATTRIBUTES(XmlMapper):
    # pdm attributes needed by wsm (-settings)
    # n ADDITIONALATTRIBUTE object(s) goes here
    __slots__ = []


class ADDITIONALINDEXATTRIBUTES(XmlMapper):
    # pdm attributes needed by wsm (-settings) for server indexes
    # n ADDITIONALATTRIBUTE object(s) goes here
    __slots__ = []


class ADDITIONALDOCATTRIBUTE(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(name=None)


class ADDITIONALFILEATTRIBUTE(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(name=None)


class INCOMPLETE_CONTEXTOBJECTS(XmlMapper):
    __slots__ = []


class INCOMPLETE_CONTEXTOBJECT(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(id=None)


class WSCOMMANDS(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        lang=None,
        cmd=None,
        transfermode=u"standard",
        wsplock_id=None,
        index_update_rule=None,
        only_command_bos=None,
        simplified_rights_check=None,
        index_filter_rule=None,
        # for commands that need to identify the server process
        mac_address=None,
        windows_session_id=None,
        # for cmd == pdmpostprocessing:
        store_variants_on_server=None,
        combine_model_layout=None,
        index_load_rule=None,
        force_checkout=None,
        filter_filename=None,
        file_counter_only=None,
        trigger_replication=None,
        # for customer export
        for_generating_names=None,
        export_partner_id=None,
        timestamp=None,
        export_title=None,
        # lock command
        lock_mode=u"lock",
        # if given, consider teamspace contents
        ws_id=u"",
        autovariant_config=None,
        lock_pdm_objects_for_teamspace=None,
    )


class COMMANDSTATUSLIST(XmlMapper):
    __slots__ = []
    # COMMANDSTATUS object(s) goes here


class EXISTINGFILES(XmlMapper):
    __slots__ = []

    def addFileList(self, relFilePathes):
        """ """
        self.etreeElem.text = json.dumps(relFilePathes)


class COMMANDSTATUS(XmlMapper):
    __slots__ = []
    # ERROR and INFO objects go here
    # action in { u"checkin" | u"checkout" | u"add" | u"delete" | u"modify" | u"replace" }
    _objectAttrs = dict(
        cdb_object_id=None, local_id=None, action=None, value=None
    )  # u"ok" or u"error" or "info"


class ERROR(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(msg=None)


class INFO(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(msg=None)


class TRANSLATIONARGLIST(XmlMapper):
    __slots__ = []


class TRANSLATIONARG(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(trArg=None)


class WSCOMMANDRESULT(XmlMapper):
    # CommandStatusList
    # WsCommands_ContextObject+
    __slots__ = []
    _objectAttrs = dict(primary_object=None)


class FRAMEDATA(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        cdb_object_id=None,
        cdb_classname=None,
        framedata=None,
        bomdata=None,
        textlayer=None,
        framelayer=None,
    )


class CDB_VERSION_DESC(XmlMapper):
    __slots__ = []

    PRESIGNED_NO_LICENSE = 1
    PUBKEY_ENDPOINT_NOT_SET = 2
    CADDOK_PRESIGNED_BLOB_DISABLED = 4
    NO_CRYPTO_KEYS = 8

    _objectAttrs = dict(
        version=None,
        service_level=None,
        version_desc=None,
        cs_workspaces_vers=None,
        branded_name=None,
        # bitwise encoded configuration problems
        # 0: ok
        # PRESIGNED_NO_LICENSE
        # PUBKEY_ENDPOINT_NOT_SET
        # CADDOK_PRESIGNED_BLOB_DISABLED
        # NO_CRYPTO_KEYS
        # None: not checked by server (older version)
        presigned_blob_configuration=None,
        session_lang=None,
    )


class LICENSE_INFO(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        current_time=None,  # current time
        signature=None,
        signature2=None,
        valid=None,
        valid_office=None,
    )


class LIC_FEATURES(XmlMapperWithAttrCache):
    """
    Requested lic features
    """

    __slots__ = []


class CAD_FEATURE(XmlMapper):
    """
    Request from CAD-Clients (1st part of erzeug_system)
    """

    __slots__ = []
    _objectAttrs = dict(mandatory="1", cadsystem=None, subfeature="0")


class GENERAL_FEATURE(XmlMapper):
    """
    Request for real feature IDs in post 10.1 systems
    """

    __slots__ = []
    _objectAttrs = dict(mandatory="1", feature_id=None)


class LIC_FEATURE_REPLY(XmlMapper):
    """
    Reply for Licfeatures,
    contains list of FEATURE_STATUS
    """

    __slots__ = []
    _objectAttrs = dict(licensechecksum=None)


class FEATURE_STATUS(XmlMapper):
    """ """

    __slots__ = []
    _objectAttrs = dict(feature_id=None, granted=None, subfeature="0")


class CDB_PERSNO(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(persno=None, alias=None)


class CDB_SYSKEYS(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        customer_id=None, wsm_doc_change_detection_mode=None  # kSysKeyCust
    )


class CDB_CLSS_KEYLISTS(XmlMapper):
    __slots__ = []


class CDB_CLSS_KEYLIST(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(keys=None)


class CDB_CLSS_KEY(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(keys=None)


class CDB_CLASS_HIERARCHY(XmlMapper):
    __slots__ = []


class CDB_CLASS_HIERARCHY_TYPE(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(type=None)  # model or document classes


class CDB_CLASS_HIERARCHY_CLSS(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(classname=None)


class CDB_STATUS_DEFINITIONS(XmlMapper):
    __slots__ = []
    # statusdefs:
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
    _objectAttrs = dict(statusdefs=None)  # json dump of status dict


class CDB_ATTR_CLASS_TYPES(XmlMapper):
    __slots__ = []
    _objectAttrs = dict()


class CDB_ATTR_CLASS(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        classname=None, uiname=None, restname=None, for_workspaces=None, has_files=None
    )


class CDB_CLASS_ATTR(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(attr=None, type=None, identifier=None)


# Elements to transfer bill of material
class BOMLIST(XmlMapper):
    # BOMLIST object(s) goes here
    __slots__ = []


class BOM(XmlMapperWithAttrCache):
    # entry from CDB teile_stamm
    # contains n BOM_ITEM objects
    __slots__ = []


class BOM_ITEM(XmlMapperWithAttrCache):
    # entry from CDB einzelteile
    # contains n BOM_ITEM_OCCURRENCE objects
    __slots__ = []


class BOM_ITEM_OCCURRENCE(XmlMapperWithAttrCache):
    # entry from CDB bom_item_occurence
    __slots__ = []


# Elements to transfer BOM attributes names
# configured in Workspaces Desktop to get values for from CDB's
# teile_stamm and einzelteile
class ITEM_ATTRIBUTES(XmlMapper):
    __slots__ = []
    # attributes for teile_stamm
    _objectAttrs = dict(fields="")


class BOM_ITEM_ATTRIBUTES(XmlMapper):
    __slots__ = []
    # attributes for einzelteile
    _objectAttrs = dict(fields="")


# -------------------------------------------------------------------


class SEARCH_QUERY(XmlMapper):
    __slots__ = []
    # has SEARCH_ATTRIBUTES as child
    _objectAttrs = dict(query_id=None)


class SEARCH_ATTRIBUTES(XmlMapperWithAttrCache):
    __slots__ = []


class SEARCH_RESULT(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        query_id=None, number_of_hits=None, unique_result=None  # id from SEARCH_QUERY
    )  # cdb_object_id if unique


class CATALOG_QUERY(XmlMapper):
    __slots__ = []
    # has SEARCH_ATTRIBUTES as child
    _objectAttrs = dict(catalog=None, maxHits=None)


class EXPORTED_FILE(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(
        cdb_object_id=None, exported_hash=None, rel_path=None  # of file
    )


class IMPORT_FILE(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(rel_path=None, hash=None)


class LOCK_ITEM(XmlMapper):
    __slots__ = []
    _objectAttrs = dict(cdb_object_id=None, error=None)


class PRIOBLOBS(XmlMapper):
    # e.g. edger server replicated blobs that should be loaded first
    __slots__ = []


classDict = registerClasses(__name__)


def xmlTree2Object(xmlTree):
    """
    Unmarshall xmlTree to object tree.

    :Parameters:
        xmlTree : ElementTree.Element instance.
    :Returns:
        object tree.
    """
    global classDict
    instanceClassName = xmlTree.tag
    theClass = classDict.get(instanceClassName, None)
    if theClass:
        obj = theClass()
        obj.etreeElem = xmlTree
        obj.initializeAttributes()
    else:
        msg = u"class '%s' not defined in xmlmapper.py" % instanceClassName
        raise Exception(msg)
    return obj
