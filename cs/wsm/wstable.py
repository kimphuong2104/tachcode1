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

import copy

import six


class TableDataRow:
    def __init__(self):
        pass

    def getKeys(self):
        raise NotImplementedError("getKeys is not implemented.")


class DataClass(TableDataRow):
    def __init__(self, data):
        TableDataRow.__init__(self)
        self.data = data

    def getKeys(self):
        return self.data


class RawTable(object):
    def __init__(self, columns, caseInsensitiveColumns=frozenset()):
        """
        :param columns: list of column names
        :param caseInsensitiveColumns: set of columns names;
               must be a subset of 'columns';
               names of columns which should be treated case-insensitively in search;
               the column values must be strings
        """
        self.colnames = set(columns)
        self.caseInsensitiveColnames = caseInsensitiveColumns
        self.columns = dict()
        self._len = 0
        self.clear()

    def clear(self):
        self.columns = dict()  # dict-> list of values
        for col in self.colnames:
            self.columns[col] = dict()
        self._len = 0

    def _addVal(self, index, val, data):
        indexList = index.get(val, None)
        if indexList is None:
            indexList = set([data])
            index[val] = indexList
        else:
            indexList.add(data)

    def __len__(self):
        return self._len

    def addRow(self, tableDataRowExt, copyObject=True):
        """
        rowDict: key,val pairs
        """
        if copyObject:
            tableDataRow = copy.deepcopy(tableDataRowExt)
        else:
            tableDataRow = tableDataRowExt

        rowDict = tableDataRow.getKeys()

        for k, v in six.iteritems(rowDict):
            index = self.columns[k]
            if k in self.caseInsensitiveColnames:
                v = v.lower()
            self._addVal(index, v, tableDataRow)
        self._len = self._len + 1

    def searchExactData(self, conditions):
        rSet = None
        if conditions:
            for k, v in six.iteritems(conditions):
                if k in self.caseInsensitiveColnames:
                    v = v.lower()
                s = self.columns[k].get(v, None)
                if s is not None:
                    if rSet is None:
                        rSet = copy.copy(s)
                    else:
                        rSet = rSet.intersection(s)
                else:
                    rSet = set()
                    break
        return rSet

    def searchExact(self, conditions):
        """
        conditions: key,val pairs of conditions
        Ohne Bedingung alle Zurueckgeben
        """
        rSet = None
        if conditions:
            rSet = self.searchExactData(conditions)
            rList = []
            if rSet:
                rList = list(rSet)
        else:
            rList = self._fullTable()
        return rList

    def delRows(self, conditions):
        deletedRows = 0
        rowsToDelete = copy.copy(self.searchExactData(conditions))
        if rowsToDelete:
            for row in rowsToDelete:
                for col in self.colnames:
                    index = self.columns[col]
                    dataVal = row.getKeys()[col]
                    setObj = index[dataVal]
                    setObj.remove(row)
                    if len(setObj) == 0:
                        del index[dataVal]
            deletedRows = len(rowsToDelete)

        self._len = self._len - deletedRows
        return deletedRows

    def _fullTable(self):
        i1 = self.columns[list(self.columns)[0]]
        retList = []
        for s in six.itervalues(i1):
            retList.extend(list(s))
        return retList

    def fullTable(self):
        return self._fullTable()


class WsTable(RawTable):
    def __init__(self, columns):
        RawTable.__init__(self, columns)

    def addRow(self, rowDict, copyObject=True):
        if len(self.colnames.symmetric_difference(set(rowDict.keys()))) > 0:
            raise ValueError()

        internalRow = DataClass(copy.deepcopy(rowDict))
        RawTable.addRow(self, internalRow, copyObject)

    def searchExact(self, conditions):
        rows = RawTable.searchExact(self, conditions)
        rList = [d.data for d in rows]
        return rList

    def fullTable(self):
        rows = RawTable.fullTable(self)
        retList = [d.data for d in rows]
        return retList
