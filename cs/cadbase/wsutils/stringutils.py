#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     stringutils.py
# Author:   ws
# Creation: 18.04.08
# Purpose:


"""
Module stringutils.py

Basic string manipulation utilities.
"""

__docformat__ = "restructuredtext en"


import re
import six
from ..wsutils.wslog import cdblogv, logClasses


class StringTransformer(object):

    """
    Class for string transformations.

    This class is used to mask/unmask special characters (e.g. path and field
    separators) in strings.
    """

    def __init__(self, tomask=[], separator=None, escaper=None):
        """
        Initialize self, optionally set mapping of strings to escape sequences

        :Parameters:
            separator : unicode character
                Character used to separate the fields in the string
        """
        self.__separator = separator
        self.__escaper = escaper
        self.__charsToMask = tomask

    def split(self, strToSplit, separator=None, escaper=None):
        """
        splits a string into tokens. Considers also, that the data
        may contain escaped separators

        :Parmeters:
            strToSplit : unicode
                The string to split
            separator : unicode character
                Character used to separate the fields in the string
            escaper : unicode character
                Character used for masking

        :rtype: list(unicode)
        :return: splitted string
        """
        if separator is None:
            separator = self.__separator
            if separator is None:
                raise TypeError("StringTransformer.split()"
                                " requires the separator to be given either"
                                " as method or as class parameter")

        if escaper is None:
            escaper = self.__escaper

        tokens = []
        skipnext = False
        begin = 0
        strlen = len(strToSplit)
        for i in range(strlen):
            curr = strToSplit[i]
            if i == strlen - 1:  # last character
                if curr == separator and not skipnext:
                    token = strToSplit[begin:i]
                    tokens.append(token)
                    tokens.append("")
                else:
                    token = strToSplit[begin:]
                    tokens.append(token)
                continue
            if skipnext:
                skipnext = False
                continue
            if curr == separator:
                token = strToSplit[begin:i]
                tokens.append(token)
                begin = i + 1
                continue
            if curr == escaper:
                skipnext = True  # the next char is masked
                continue
        return tokens

    def mask(self, string):
        """
        Masks all occurrences of the special characters with
        the escape character and returns the modified string.

        :Parameters:
           string : unicode
               the string where to mask

        :return: string with all special characters masked
        """
        escaper = self.__escaper
        if escaper is None:
            raise TypeError("StringTransformer.unmask()"
                            " requires the escaper to be given"
                            " as object parameter")
        tomask = self.__charsToMask

        escaper = self.__escaper
        result = ""
        for char in string:
            if char in tomask:
                result += escaper + char
            else:
                result += char
        return result

    def unmask(self, string):
        """
        Unmasks all special character in the given string and
        returns the modified version

        :Parameters:
           string : unicode
               the string where to unmask

        :return: string with all special characters unmasked
        """
        escaper = self.__escaper
        if escaper is None:
            raise TypeError("StringTransformer.unmask()"
                            " requires the escaper to be given"
                            " as object parameter")

        result = ""
        rest = string
        while True:
            pos = rest.find(escaper)
            if pos == -1:
                result += rest
                break
            else:
                result += rest[:pos] + rest[pos + 1]
                rest = rest[pos + 2:]
        return result

    def unmasksequence(self, maskstr, unmaskdict):
        """
        Parameters:
            maskstr: unicode string

            unmaskdict: dict of unicode strings
                maskcharsquence->unmaskchar
        """
        escaper = self.__escaper
        if escaper is None:
            raise TypeError("StringTransformer.unmask()"
                            " requires the escaper to be given"
                            " as object parameter")
        resStr = ""
        rest = maskstr
        while True:
            pos = rest.find(self.__escaper)
            if pos == -1:
                resStr += rest
                break
            else:
                resStr += rest[:pos]
                nextChars = rest[pos + 1:]
                found = False
                for k, v in list(unmaskdict.items()):
                    kpos = nextChars.find(k)
                    if kpos == 0:
                        resStr += v
                        found = True
                        rest = rest[pos + 1 + len(k):]
                        break
                if not found:
                    resStr += rest[pos]
                    rest = rest[pos + 1:]
        return resStr


_encoding = "utf-8"


def unicode2latin1(toConvert):
    """
    converts the passed unicode string to latin1 and returns the result
    """
    # TODO: it is planned to do such things mainly in the
    # swigged code... so this function
    # will be maybe replaced in not so near future ;-)
    # Im sWig-Code wird die entsprechende Einstellung ausgewandelt.
    # Der Coding-Type muesste dem talkapi-Encoding entsprechen.
    # Das sollten wir hier auch tun.
    global _encoding
    if type(toConvert) == six.text_type:
        return toConvert.encode(_encoding)
    return toConvert


def getMultiLanguagePair(lang, colHeadStr):
    """
    Zerlegt ein colHeadStr in seine Bestandteile und gibt
    fuer die aktuelle Sprache den Titel zurueck
    Jeder Eintrag on der Liste besteht aus einem String
    <Sprache1>@<Bezeichnung1>@<Sprache n>@<Bezeichnung n>:<cdb-attribut>.

    Beinhaltet der String kein ":" wird der String
    als Attributname betrachtet. Wird die aktuelle Sprache nicht gefunden,
    dann wird die erste im String stehende Sprache verwendet

    :returns tuple (colTitle,cdbAttr)
    """
    cdbCol = colHeadStr
    colTitle = None
    if ":" in colHeadStr:
        tmpList = colHeadStr.split(":")
        if len(tmpList) == 2:
            langPart = tmpList[0]
            cdbCol = tmpList[1]
            langList = langPart.split("@")
            i = 0
            langListLen = len(langList) - 1
            while i < langListLen:
                line = langList[i]
                v = langList[i + 1]
                if line == lang:
                    colTitle = v
                    break
                else:
                    i += 2
            # Wenn Sprache nicht gefunden, dann die erste nehmen
            if colTitle is None and langListLen > 1:
                colTitle = langList[1]
    if colTitle is None:
        # Wenn keine Sprache vorhanden, dann das Attribut nehmen
        colTitle = cdbCol
    return colTitle, cdbCol


def getMultiLanguageString(lang, multiLanguageStr):
    """
    :Parameter:
          lang: unicode
              iso language id

        multiLanguageStr: unicode
              isocode@val@..@iscode@val

    :returns: unicode string in language lang or default first language
    """
    langList = multiLanguageStr.split("@")
    i = 0
    colTitle = None
    langListLen = len(langList) - 1
    while i < langListLen:
        line = langList[i]
        v = langList[i + 1]
        if line == lang:
            colTitle = v
            break
        else:
            i += 2
    # Wenn Sprache nicht gefunden, dann die erste nehmen
    if colTitle is None and langListLen > 1:
        colTitle = langList[1]
    if colTitle is None:
        colTitle = multiLanguageStr
    return colTitle


def parseVariables(inputString, boAttributes, foAttributes):
    """
    Replaces ${<var>} by attributes from boAttributes or foAttributes
    Syntax of input string
    ${[<obj>.]<attribute>}:
    obj: bo | fo. Defaults to bo
    Expample
    ${bo.z_nummer}-${bo.z_index}-${fo.cdb_object_id}
    """
    varParser = VariableParser(inputString)
    retStr = varParser.replace(boAttributes, foAttributes)
    return retStr


class VarAttrDesc():

    def __init__(self, varName, srcObj, srcAttr, lastSync=False):
        self.varName = varName
        self.srcObj = srcObj
        self.srcAttr = srcAttr
        # if true, use attributes from lastsync revision
        self.useLastSync = lastSync


class VariableParser():

    def __init__(self, inputString):
        self._cadattrs = []  # Liste von
        self._inputString = inputString
        # get all '$(cadattr)' in list
        cadattr_list = re.findall(r"\${.*?}", inputString)
        for cadattr in cadattr_list:
            useLastSync = False
            attributeName = cadattr[2: -1]
            splittedName = attributeName.split(".")
            lSplit = len(splittedName)
            if lSplit == 2:
                obj = splittedName[0]
                attribute = splittedName[1]
            else:
                obj = "bo"
                attribute = attributeName
                if lSplit == 1:
                    cdblogv(logClasses.kLogMsg, 9,
                            "no obj specified in %s. using bo as default:" %
                            cadattr)
                elif lSplit == 3 and splittedName[0] == "lastsync":
                    useLastSync = True
                    obj = splittedName[1]
                    attribute = splittedName[2]
                else:
                    cdblogv(logClasses.kLogErr, 0,
                            "unexpected . in %s (%s)" %
                            (cadattr, inputString))

            if obj not in ["bo", "fo", "cad"]:
                cdblogv(logClasses.kLogErr, 0,
                        "parsing variables: unknown object type:"
                        " '%s' in (%s)" % (obj, inputString))
            self._cadattrs.append(VarAttrDesc(cadattr, obj, attribute, useLastSync))

    def replace(self, boAttrs, foAttrs, docItem=None, revision=None):
        """
        das mit dem docItem und Revision ist hier eher unschoen.
        Aber hilft erst mal...
        """
        retStr = self._inputString
        for attr in self._cadattrs:
            retStr = self._replaceAttr(retStr, attr, boAttrs, foAttrs, docItem, revision)
        return retStr

    def replaceUsingLastSync(self, boAttrs, foAttrs, lsBoAttrs, lsFoAttrs,
                             docItem=None, revision=None, lsDocItem=None, lsRevision=None):
        """
        Same as replace but can use last sync objects
        """
        retStr = self._inputString
        for attr in self._cadattrs:
            if attr.useLastSync:
                retStr = self._replaceAttr(retStr, attr, lsBoAttrs, lsFoAttrs,
                                           lsDocItem, lsRevision)
            else:
                retStr = self._replaceAttr(retStr, attr, boAttrs, foAttrs, docItem, revision)
        return retStr

    def _replaceAttr(self, inputString, attr, boAttrs, foAttrs, docItem=None, revision=None):
        attrVal = ""
        if attr.srcObj == "bo":
            attrVal = boAttrs.get(attr.srcAttr, "")
        elif attr.srcObj == "fo":
            attrVal = foAttrs.get(attr.srcAttr, "")
        elif attr.srcObj == "cad" and docItem is not None and revision is not None:
            attrVal = docItem.getCadAttrValue(attr.srcAttr, revision)
            if attrVal is None:
                attrVal = ""
        inputString = inputString.replace(attr.varName, six.text_type(attrVal))
        return inputString

    def getRequiredAttrs(self):
        return self._cadattrs


def enumMultiLineStr(multiLineStr):
    """
    Enumerates given multi line string (string with multiple \n).
    Useful for enumerating source code.

    :Parameters:
        multiLineStr: string
            String, e.g. Python code, with multiple line breaks
    """
    lines = multiLineStr.splitlines()
    enumerated = ["%s\t%s" % (i, l) for i, l in enumerate(lines, 1)]
    enumerated = "\n".join(enumerated)
    return enumerated


def splitAttributeName(attributeName):
    """
    Splits string into object and attributeName.

    Expects a string with bo.<attrname>, fo.<attrname>
     or just <attrname>

    :returns srcObj, attrname
    """
    splittedName = attributeName.split(".")
    lSplit = len(splittedName)
    if lSplit == 2:
        obj = splittedName[0]
        attribute = splittedName[1]
    else:
        if lSplit == 1:
            cdblogv(logClasses.kLogMsg, 9,
                    "stringutils.splitAttributeName:"
                    " no obj specified in %s. using bo as default:" %
                    attributeName)
        else:
            cdblogv(logClasses.kLogErr, 0,
                    "stringutils.splitAttributeName:"
                    "unexpected . in %s " % attributeName)
        obj = "bo"
        attribute = attributeName
    return obj, attribute
