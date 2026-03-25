# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module pdminfohelper

support creation of cadparameter and frame parameter
"""

import hashlib
import six
from .wsutils.stringutils import StringTransformer

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


def escapePdmInfo(val):
    rval = val.replace("\\", "\\\\")  # Escape Char
    rval = rval.replace("@", "\\{at}")  # Trennzeichen zwischen Type und Namen
    rval = rval.replace(":", "\\{colon}")
    rval = rval.replace("\n", "\\{newline}")
    return rval


class FrameElement(object):

    """
    This class describes one frame element
    """

    def __init__(self, attrname, value, ranks):
        self.name = attrname
        self.ranks = ranks
        self.value = value
        self.cnt = len(ranks) + 1


DEFAULT_CAD_ENCODING = "utf-8"


class PdmInfoHelper(object):

    def getCadParameterForJson(self, parameters):
        """
        :param parameters: dict with cadname->cad_value
        :return: json compatible python struct and parameterhash
        """
        jsonStruct = list()
        cadParams = []
        attrType = "string"
        keys = list(parameters.keys())
        keys.sort()
        for cadName in keys:
            value = parameters[cadName]
            escapedVal = escapePdmInfo(value)
            cadParams.append(":".join([cadName, attrType, escapedVal]))
            jsonStruct.append({"type": attrType,
                               "name": cadName,
                               "value": value})
        paramLine = "@".join(cadParams)
        paramLineHash = self._calculateLineHash(paramLine)
        return jsonStruct, paramLineHash

    def getCadParameterHash(self, parameter_json):
        """
        :param parameter_json: list of dicts with value name and value (type ignored)
        :return: parameter hash (string)
        """
        cadParams = []
        attrType = "string"
        sorted_parameter = sorted(parameter_json, key=lambda k: k["name"])
        for item in sorted_parameter:
            cadParams.append(":".join([item["name"], attrType, escapePdmInfo(item["value"])]))
        paramLine = "@".join(cadParams)
        return self._calculateLineHash(paramLine)

    def getFrameDataForJson(self, frame_layer, text_layer, cdb_format_data):
        """
        :param frame_layer: str CAD layer for frame
        :param text_layer: str CAD layer for title block text
        :param cdb_format_data: str result from cdb.cad.get_data()

        :return: json_data, hash value for format data
        """
        wsmFormatData = self._decodeFrameData(cdb_format_data)
        formatDataString, frameJsonData = self._convertFormatDataToString(wsmFormatData)
        jsonData = {"rahmenlayer": frame_layer,
                    "formatdatalayer": text_layer,
                    "data": frameJsonData}
        formatLineHash = self._calculateLineHash(formatDataString)
        return jsonData, formatLineHash

    def _calculateLineHash(self, line):
        md5 = hashlib.md5()
        md5.update(line.encode(DEFAULT_CAD_ENCODING))    # =UTF-8
        lineHash = six.text_type(md5.hexdigest())
        return lineHash

    def _decodeFrameData(self, frameValues):
        """
        Splits and parses the frame values.
        :param frameValues string
        :result list(FrameElement)
        """
        SEPARATOR = "@"
        ESCAPE = "\\"

        sf = StringTransformer(separator=SEPARATOR,
                               escaper=ESCAPE)
        splittedMsg = sf.split(frameValues,
                               SEPARATOR,
                               ESCAPE)
        decodedList = []
        for v in splittedMsg:
            decodedList.append(
                sf.unmasksequence(v, {"at": "@",
                                      "n": "\n",
                                      "\\": "\\"}))
        # den ersten Wert ingorieren ist noch mal der schriftfeldlayer
        decodedList = decodedList[1:]
        cnt = len(decodedList)
        # der erste Wert ist die Anzahl
        i = 0
        frameElements = []
        while i < cnt:
            # evtl. ist noch ein leerer eintrag am ende vorhanden
            if (decodedList[i]):
                cntRanks = int(decodedList[i])
                i += 1
                name = decodedList[i]
                i += 1
                value = decodedList[i]
                i += 1
                ranks = []
                for _j in range(cntRanks):
                    ranks.append(decodedList[i])
                    i += 1
                fe = FrameElement(name, value, ranks)
                frameElements.append(fe)
            else:
                i += 1
        return frameElements

    def _convertFormatDataToString(self, formatdata):
        """
        :returns unicode string and json compatible frame data structure
        """

        fDataList = []
        jsonData = []
        for rElement in formatdata:
            rElementStr = six.text_type(rElement.cnt) + ":" +\
                escapePdmInfo(rElement.name) + ":" +\
                escapePdmInfo(rElement.value)
            jsonRanks = []
            for rang in rElement.ranks:
                rElementStr = rElementStr + ":" +\
                    escapePdmInfo(rang)
                jsonRanks.append(rang)
            fDataList.append(rElementStr)
            jsonData.append({"cnt": int(rElement.cnt),
                             "name": rElement.name,
                             "value": rElement.value,
                             "ranks": jsonRanks})
        formatDataStr = "@".join(fDataList)
        if formatDataStr and formatDataStr[-1:] != "@":
            formatDataStr = formatDataStr + "@"
        return formatDataStr, jsonData


# Guard importing as main module
if __name__ == "__main__":
    pass
