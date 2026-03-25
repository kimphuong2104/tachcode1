# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module variantconfig

This modules handle the content of variantconfig files
Variantconfig files contains information about
  * mapping of family table attributes to cdb attributes
  * rules for building variant names
  *
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import json
import io
import six
import logging

from cs.cadbase.wsutils.stringutils import VariableParser
# Exported objects
__all__ = []


# Wir koennen leider kein Result verwenden, da dieser Code auch auf dem Server benutzt werden soll
class VariantConfigError():
    ERROR_OK = 0
    ERROR_HEADER = 1
    ERROR_JSON = 2

    def __init__(self):
        self._lastError = self.ERROR_OK
        self._msgs = []

    def append(self, errorType, errorMessage):
        if errorType != self.ERROR_OK:
            self._lastError = errorType
        self._msgs.append((errorType, errorMessage))

    def isOk(self):
        return self._lastError == self.ERROR_OK

    def hasError(self):
        return not self.isOk()


class VariantConfig(object):

    _comments = """#variantconfig
                #
                # Default Variantconfig file
                """

    _default = {"filename": [["attribute", "part.teilenummer"],
                             ["const", "_"],
                             ["attribute", "z_nummer"]],
                "id": [["attribute", "part.teilenummer"],
                       ["const", "_"],
                       ["attribute", "z_nummer"]],
                "familytable2cadvariants": {"partnum": "teilenummer",
                                            "partvrs": "t_index"},
                "part2familytable": {"partnum": "teilenummer",
                                     "partvrs": "t_index"},
                "docattributes": {"generated_from": [["attribute", "cdb_object_id"]],
                                  "teilenummer": [["attribute", "part.teilenummer"]],
                                  "t_index": [["attribute", "part.t_index"]]},
                "cadpresetattributes": {},
                "itemattributes": {}
                }

    def __init__(self,
                 defaultFloatValue="${value}",
                 defaultUniquePartId=None,
                 defaultCadProperty=None):
        self._content = None
        self._json = self._default
        self.defaultFloatValue = defaultFloatValue
        self.defaultUniquePartId = defaultUniquePartId
        # this may be None in case of configuration error
        if defaultCadProperty is None:
            defaultCadProperty = "code"
        self.defaultCadProperty = defaultCadProperty

    def _verifyGetData(self):
        res = VariantConfigError()
        comments = []
        jsonList = []
        for element in self._content:
            ls = element.strip()
            if ls:
                if ls.startswith("#"):
                    comments.append(element.rstrip())
                else:
                    if six.PY2:
                        jsonList.append(element.decode("utf-8"))
                    else:
                        jsonList.append(element)
            else:
                comments.append(element)
        jsonText = "".join(jsonList)
        pyJson = None
        try:
            pyJson = json.loads(jsonText)
        except (ValueError, ) as e:
            res.append(VariantConfigError.ERROR_JSON,
                       "Invalid Json: %s" % six.text_type(e))
        if (not comments) or comments[0] != "#variantconfig":
            res.append(VariantConfigError.ERROR_HEADER,
                       "Invalid file header: '%s'" % (comments[0] if comments else "",))
        return res, pyJson, comments

    def verify(self):
        return self._verifyGetData()[0]

    def writeToDisk(self, filename):
        with io.open(filename, "w", encoding="utf-8") as f:
            f.write(self._comments)
        with open(filename, "a") as f:
            json.dump(self._json, f)

    def readFromDisk(self, filename):
        with io.open(filename, "r", encoding="utf-8") as f:
            self._content = f.readlines()
        res, jsonData, comments = self._verifyGetData()
        if (res.isOk()):
            self._json = jsonData
            self._comments = "\n".join(comments)
        return res

    def readFromBuffer(self, blobData):
        """
        param: blobData Unicode string
        """
        self._content = blobData.split("\n")
        res, jsonData, comments = self._verifyGetData()
        if (res.isOk()):
            self._json = jsonData
            self._comments = "\n".join(comments)
        return res

    def getIdRules(self):
        """
        return: list of (tuples with type (attr,const) and value
        """
        return self._json.get("id")

    def getFilenameRules(self):
        """
        return: list of (tuples with type (attr,const) and value
        """
        return self._json.get("filename")

    def _parseName(self, nameList, genericAttributes, itemAttributes):
        """
        returns the name as string if multiple elements are in nameList,
        else returns type of attribute or const.
        """
        retName = ""
        singleElement = len(nameList) == 1
        for element in nameList:
            typ = element[0]
            val = element[1]
            if typ == "const":
                if singleElement:
                    retName = val
                else:
                    retName += str(val)
            elif typ == "attribute":
                if val.startswith("part."):
                    attrVal = itemAttributes.get(val[5:], "")
                else:
                    attrVal = genericAttributes.get(val, "")
                if singleElement:
                    retName = attrVal
                else:
                    retName += str(attrVal)
        return retName

    def getIdName(self, genericAttributes, itemAttributes):
        """
        parameter: genericAttributes: dict  of string (name, value)
                   itemAttributes: dict  of string (name, value)

        return: string with id
        """
        idName = None
        idList = self._json.get("id")
        if idList is not None:
            idName = str(self._parseName(idList, genericAttributes, itemAttributes))
        return idName

    def getFilename(self, genericAttributes, itemAttributes):
        """
        parameter: genericAttributes: dict  of string (name, value)
                   itemAttributes: dict  of string (name, value)

        return: string basename for file
        """
        fName = None
        fList = self._json.get("filename")
        if fList is not None:
            fName = str(self._parseName(fList, genericAttributes, itemAttributes))
        return fName

    def getFamilytable2cadvariants(self):
        """
        :return dict with key value pairs
                key = destination (cadvaraints attribute name)
                value = family table column id
        """
        return self._json.get("familytable2cadvariants", None)

    def getPart2familytable(self):
        """
        :return dict with key value pairs
                key = destination (familytable column id)
                value = part attribute name
        """
        return self._json.get("part2familytable", None)

    def _getGeneralPresets(self, attrList, genericAttributes, itemAttributes):
        retList = dict()
        if attrList:
            for dstName, ruleList in list(attrList.items()):
                retVal = self._parseName(ruleList, genericAttributes,
                                         itemAttributes)
                if retVal is not None:
                    retList[dstName] = retVal
        return retList

    def getDocumentPresets(self, genericAttributes, itemAttributes):
        """
        parameter: genericAttributes: dict  of string (name, value)
                   itemAttributes: dict  of string (name, value)

        :return dict  name, value
        """
        attrList = self._json.get("docattributes", None)
        retList = self._getGeneralPresets(
            attrList, genericAttributes, itemAttributes)
        return retList

    def getCadPresetAttributes(self, genericAttributes, itemAttributes):
        """
        parameter: genericAttributes: dict  of string (name, value)
                   itemAttributes: dict  of string (name, value)

        :return dict  name, value
        """
        attrList = self._json.get("cadpresetattributes", None)
        retList = self._getGeneralPresets(
            attrList, genericAttributes, itemAttributes)
        return retList

    def getItemPresets(self, itemAttributes):
        """
        parameter: itemAttributes: dict  of string (name, value)

        :return dict  name, value
        """
        attrList = self._json.get("itemattributes", None)
        retList = self._getGeneralPresets(
            attrList, itemAttributes, {})
        return retList

    def getFloatFormat(self):
        """
        :returns VariableParser with float_format
        """
        float_format = self._json.get("float_format", self.defaultFloatValue)
        vp = VariableParser(float_format)
        for attr in vp.getRequiredAttrs():
            if attr.srcObj != "bo" or attr.srcAttr not in ("value", "unit"):
                logging.error("VariantConfig: Float definition is invalid %s", float_format)
                raise ValueError(
                    "VariantConfig: Float definition is invalid {}".format(float_format))
        return vp

    def getCadPropertyValue(self):
        """
        :returns Attribute name of property with name of property in CAD
        """
        return self._json.get("cadproperty_value", self.defaultCadProperty)

    def getUniquePartId(self, genBoAttrs):
        """
        :param genBoAttrs: dict of attributes from generic merged
                           with item attributes from new item.
        :returns the unique ID for i.e. CATProdPartNumber of Catia or None
        """
        unique_expression = self._json.get("unique_part_id", None)
        if unique_expression is None:
            unique_expression = self.defaultUniquePartId
            logging.debug("variantconfig: unique_part_id expression not defined, using default.")
        if unique_expression is not None:
            vp = VariableParser(unique_expression)
            unique_str = vp.replace(genBoAttrs, dict(), None, None)
        else:
            unique_str = None
        return unique_str
