#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import logging

from cdb.objects import Object, Rule
from cs.documents import Document
from cdb import sqlapi
from cdb import util

from cs.wsm.pkgs.pkgsutils import grouper, toStringTuple


class IndexInfo(object):
    __slots__ = ["verObj", "number_key", "sort_value", "is_default", "status_text"]

    def __init__(self, verObj, number_key, sort_value, is_default, status_text):
        self.verObj = verObj
        self.number_key = number_key
        self.sort_value = sort_value
        self.is_default = is_default
        self.status_text = status_text

    def __getattr__(self, name):
        """
        Lazy access document attributes that can be slow for joined attributes.
        """
        val = ""
        if name in self.__slots__:
            val = getattr(self, name)
        else:
            if name == "object_id":
                # compatibility
                name = "cdb_object_id"
            try:
                val = self.verObj[name]
            except AttributeError:
                pass
        return val

    def __iter__(self):
        """
        Support unpacking, like a tuple. For compatibility reasons only.
        """
        try:
            return iter(
                (
                    self.object_id,
                    self.number_key,
                    self.sort_value,
                    self.verObj.z_index,
                    self.is_default,
                    self.verObj.z_status,
                    self.status_text,
                )
            )
        except AttributeError:
            # e.g. Frames
            return iter(
                (
                    self.object_id,
                    self.number_key,
                    self.sort_value,
                    "",
                    self.is_default,
                    "",
                    self.status_text,
                )
            )


class IndexInformationList(list):
    """
    List using the index sort value for getItem access

    For compatibility reasons only
    """

    def __getitem__(self, key):
        for entry in self:
            if type(entry) == tuple:
                # in entry contains Document object as well,
                # only if created in getIndexes with withRecords=True
                indexInfo = entry[0]
            else:
                indexInfo = entry
            if key == indexInfo.sort_value:
                return indexInfo
        return None


def _getNumberKey(classId, number):
    return "%s_%s" % (classId, number)


def getSortCriteria():
    sortCriteria = util.get_prop("ixsm")
    if not sortCriteria:
        sortCriteria = "z_index"
    return sortCriteria


def getIndexOrder(zNummerList):
    """
    Retrieve the index order for all indexes of a document, identified by the
    z_nummer attribute.

    :param zNummerList: List of z_nummer.
    :type zNummerList: list(str)
    :return: A dict that contains z_nummer to z_index to index order.
    :rtype: dict(str: dict(str: int))
    """
    zNummerToIndexAndIndexOrder = {}  # z_nummer -> z_index -> index order
    zNummerIndexOrderCounter = {}  # z_nummer -> index order counter
    sortCriteria = getSortCriteria()
    for chunk in grouper(250, zNummerList):
        drwDocs = Document.Query(
            condition="z_nummer IN %s" % toStringTuple(chunk),
            addtl="order by %s" % sortCriteria,
            lazy=0,
        ).Execute()
        for drwDoc in drwDocs:
            drwZNumber = drwDoc.z_nummer
            if drwZNumber not in zNummerIndexOrderCounter:
                zNummerIndexOrderCounter[drwZNumber] = 0
            indexOrder = zNummerIndexOrderCounter[drwZNumber]
            if drwZNumber not in zNummerToIndexAndIndexOrder:
                zNummerToIndexAndIndexOrder[drwZNumber] = {}
            zNummerToIndexAndIndexOrder[drwZNumber][drwDoc.z_index] = indexOrder
            zNummerIndexOrderCounter[drwZNumber] = (
                zNummerIndexOrderCounter[drwZNumber] + 1
            )

    return zNummerToIndexAndIndexOrder


def getIndexes(
    doc,
    indexUpdateRuleId="",
    indexFilterRuleId="",
    wsObjectCache=None,
    withRecords=False,
    compatibilityMode=True,
    optimizeGivenObjectChecks=False,
):
    """
    Creates a list of available indexes for the given Document object.

    Considers the "ixsm"/"ixsp" properties.

    Removes indexes that do not match the optional index filter rule.

    If the optional index update rule is given and an index matches this rule,
    the index is marked as default.

    doc: Document, Workspace or derived

    indexUpdateRuleId: string
        cdb_object_id of the currently selected index_update_rule OR
        index_load_rule or empty string

    indexFilterRuleId: string
        cdb_object_id of the currently selected filter index rule
        or empty string

    wsObjectCache: WsObjectCache
        optional cache to avoid database access

    withRecords: bool
        if True, the returned list contains pairs of IndexInfo and Document object (for access to all attributes).

    compatibilityMode: bool
        if True, the returned sortvalue of given doc can be used with the returned indexinfo list
        using the index operator, e.g. IndexInfos[ownSortValue]. Only used in 'GetBoForFilenameProcessor'.

    optimizeGivenObjectChecks: bool
        if True use optimizations for given object, e.g. skip default index calculation and object handle caching
    """
    indexInfos = IndexInformationList() if compatibilityMode else []

    ownSortValue = None

    # Workspace or Document
    if isinstance(doc, Document):
        classId = "Document"
        sortCriteria = getSortCriteria()

        number = doc.z_nummer
        externalNumber = _getNumberKey(classId, number)
        indexFilterResult = None
        if wsObjectCache:
            # assume the filter rule never changes for same cache instance
            indexFilterResult = wsObjectCache.getIndexFilterResult(number)
            if indexFilterResult is None:
                indexes = wsObjectCache.indexesOfDocument(doc)
                indexFilterResult = applyIndexFilter(indexes, indexFilterRuleId)
                wsObjectCache.setIndexFilterResult(number, indexFilterResult)

        if indexFilterResult is None:
            condition = "z_nummer='%s'" % sqlapi.quote(number)
            indexes = Document.Query(
                condition=condition, addtl="order by %s" % sortCriteria, lazy=0
            ).Execute()
            indexFilterResult = applyIndexFilter(indexes, indexFilterRuleId)

        # reduce index list but calculate sort values based on complete index list
        filteredIndexesWithSortValue = []
        for sortVal, (version, filterMatch) in enumerate(indexFilterResult):
            if version.cdb_object_id == doc.cdb_object_id:
                # always consider own version
                filterMatch = True
                ownSortValue = sortVal

            if filterMatch:
                indexEntry = (sortVal, version)
                filteredIndexesWithSortValue.append(indexEntry)

        defaultSortVal = None
        if filteredIndexesWithSortValue:
            # if the only entry is the own version, skip it
            if (
                optimizeGivenObjectChecks
                and ownSortValue is not None
                and len(filteredIndexesWithSortValue) == 1
            ):
                (sortVal, _version) = filteredIndexesWithSortValue[0]
                if sortVal == ownSortValue:
                    filteredIndexesWithSortValue = []

        defaultSortVal = None
        if filteredIndexesWithSortValue:
            defaultSortVal = get_default_index(
                filteredIndexesWithSortValue, indexUpdateRuleId
            )
            # optimization: own version must not be considered during default index calculation
            # but not returned
            if optimizeGivenObjectChecks and ownSortValue is not None:
                filteredIndexesWithSortValue = [
                    i for i in filteredIndexesWithSortValue if i[0] != ownSortValue
                ]

        for (sortVal, version) in filteredIndexesWithSortValue:
            numberKey = _getNumberKey(classId, version.z_nummer)
            isDefault = defaultSortVal is not None and sortVal == defaultSortVal

            # get i18n status text efficiently
            if wsObjectCache is not None:
                status_text = wsObjectCache.get_status_name(
                    version.z_status, version.z_art
                )
            else:
                status_text = (
                    version.z_status_txt
                )  # really old WSM versions don't get i18n

            indexInfo = IndexInfo(version, numberKey, sortVal, isDefault, status_text)
            if withRecords:
                indexInfos.append((indexInfo, version))
            else:
                indexInfos.append(indexInfo)

    else:
        # e.g. Frames
        dummyIndex = IndexInfo(doc, doc.cdb_object_id, 0, False, "")
        if withRecords:
            indexInfos.append((dummyIndex, None))
        else:
            indexInfos.append(dummyIndex)
        externalNumber = doc.cdb_object_id

    if ownSortValue is None:
        ownSortValue = 0

    return indexInfos, externalNumber, ownSortValue


def applyIndexFilter(versions, indexFilterRuleId):
    """
    Calculates filter results for given index versions using the given IndexUpdateRule.
    (We need to know the OF class in order to use object rules.)

    @param versions list of Document
    @param indexFilterRuleId string cdb_object_id of a IndexUpdateRule or ""
    @return list of tuple with (Document, bool (True if filter matched))
    """
    result = None

    if indexFilterRuleId:
        filterRule = IndexUpdateRule.getIndexRuleByName(indexFilterRuleId)
        if not filterRule:
            filterRule = IndexUpdateRule.getIndexRuleById(indexFilterRuleId)

        if filterRule:
            result = []
            for version in versions:
                # if the filter matches, the version is relevant
                result.append((version, filterRule.match(version)))

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                numOriginal = len(versions)
                numRemaining = len(result)
                ruleName = filterRule.get_name()
                logging.debug(
                    "Removed %d of %d indexes, using index filter rule '%s'",
                    numOriginal - numRemaining,
                    numOriginal,
                    ruleName,
                )
        else:
            logging.error(
                "Could not find index filter rule with cdb_object_id '%s'. Indexes are not filtered.",
                indexFilterRuleId,
            )
    if result is None:
        result = [(bo, True) for bo in versions]
    return result


def get_default_index(indexesWithSortValue, indexUpdateRuleId):
    """
    parameters:
      indexesWithSortValue: list of (int (sort value), Document) in ascending order

    returns: sort value of the default index according to the given index update rule or None
    """
    rulesTested = set()
    while indexUpdateRuleId:
        indexUpdateRule = IndexUpdateRule.getIndexRuleByName(indexUpdateRuleId)
        if not indexUpdateRule:
            indexUpdateRule = IndexUpdateRule.getIndexRuleById(indexUpdateRuleId)
        if not indexUpdateRule or indexUpdateRule.name in rulesTested:
            break
        rulesTested.add(indexUpdateRule.name)
        # find the newest index that matches
        for (sortVal, version) in reversed(indexesWithSortValue):
            if indexUpdateRule.match(version):
                return sortVal

        # otherwise try fallback rule
        indexUpdateRuleId = indexUpdateRule.fallback_rule

    return None


class IndexUpdateRule(Object):
    """
    Specialized object rules for selecting and filtering indexes.
    They have a user-visible name and may have a fallback rule.
    """

    __maps_to__ = "index_update_rule"
    __classname__ = "index_update_rule"

    _indexRuleByNameCache = {}
    _indexRuleByIdCache = {}

    @staticmethod
    def getIndexRuleByName(indexRuleName):
        """
        Return the index rule associated with indexRuleName, None if not existing.

        :Parameters:
            indexRuleName : string
                name of the index rule
        """
        cached = IndexUpdateRule._indexRuleByNameCache.get(indexRuleName, "CACHEMISS")
        if cached != "CACHEMISS":
            return cached

        rule = None
        rules = IndexUpdateRule.Query(
            "name='%s'" % sqlapi.quote(indexRuleName), lazy=0
        ).Execute()
        for rule in rules:
            break
        IndexUpdateRule._indexRuleByNameCache[indexRuleName] = rule
        return rule

    @staticmethod
    def getIndexRuleById(indexRuleId):
        cached = IndexUpdateRule._indexRuleByIdCache.get(indexRuleId, "CACHEMISS")
        if cached != "CACHEMISS":
            return cached

        rule = IndexUpdateRule.ByKeys(indexRuleId)
        IndexUpdateRule._indexRuleByIdCache[indexRuleId] = rule
        return rule

    def get_name(self):
        # self.name is the internal name (ID)
        # self.designation is the user-visible name (multi-language)
        return self.designation

    def get_names(self):
        defaultName = self.designation
        namesByLang = {}
        for attr in self.GetFieldNames():
            if attr.startswith("designation_"):
                _, lang = attr.split("_")
                name = getattr(self, attr)
                if name:
                    namesByLang[lang] = name
        return defaultName, namesByLang

    def match(self, obj):
        # cache the object rule
        if (
            not hasattr(self, "_object_rule")
            or self._object_rule
            is None  # pylint: disable=access-member-before-definition
            or self._object_rule.name  # pylint: disable=access-member-before-definition
            != self.object_rule
        ):  # pylint: disable=access-member-before-definition
            self._object_rule = Rule.ByKeys(self.object_rule)
        if self._object_rule is None:
            logging.error(
                "Index update rule without object rule: '%s', %s",
                self.name,
                self.object_rule,
            )
            return False
        return self._object_rule.match(obj)


if "__main__" == __name__:
    import sys

    if "--test" == sys.argv[-1]:
        import doctest

        doctest.testmod()
