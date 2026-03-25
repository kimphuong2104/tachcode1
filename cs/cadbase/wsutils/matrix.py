#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     matrix.py
# Author:   jro
# Creation: 21.07.08
# Purpose:

"""
Module matrix.py

This is the documentation for the matrix.py module.
"""

__docformat__ = "restructuredtext en"

from ..wsutils.wserrorhandling import WsmException
import copy


class MatrixOutOfRangeError(WsmException):
    pass


class Matrix(object):

    def __init__(self, cols, rows, typ):
        row = []
        for _i in range(rows):
            row.append(typ(0))
        self._array = []
        for _i in range(cols):
            self._array.append(copy.copy(row))

        self._cellType = typ
        self._cols = cols
        self._rows = rows

    def array(self):
        """
        raturns matrix as array[col][row]
        """
        return self._array

    def getCol(self, col):
        self._rangeCheck(col, None)
        return self._array[col]

    def getRow(self, row):
        self._rangeCheck(None, row)
        resRow = []
        for i in range(self._cols):
            resRow.append(self._array[i][row])
        return resRow

    def getElement(self, col, row):
        self._rangeCheck(col, row)
        return self._array[col][row]

    # for testing/debugging purposes...
    def initMatrixFromArray(self, array):
        cols = len(array)
        for c in range(len(array)):
            rows = len(array[c])
            self._sizeCheck(cols, rows)
            for r in range(rows):
                self._array[c][r] = self._cellType(array[c][r])

    def initToIdentity(self):
        minsize = min(self._rows, self._cols)
        for i in range(minsize):
            self._array[i][i] = self._cellType(1)

    def setValue(self, col, row, val):
        self._rangeCheck(col, row)
        self._array[col][row] = self._cellType(val)

    def getCols(self):
        return self._cols

    def getRows(self):
        return self._rows

    def _sizeCheck(self, cols, rows):
        if cols is not None:
            if not (cols >= 0 and cols <= self._cols):
                raise MatrixOutOfRangeError(
                    "Column out of range value:%d  max:%d",
                    (cols, self._cols - 1))
        if rows is not None:
            if not (rows >= 0 and rows <= self._rows):
                raise MatrixOutOfRangeError(
                    "Row out of range value:%d  max:%d",
                    (rows, self._rows - 1))

    def _rangeCheck(self, cols, rows):
        if cols is not None:
            if not (cols >= 0 and cols < self._cols):
                raise MatrixOutOfRangeError(
                    "Column out of range value:%d  max:%d",
                    (cols, self._cols - 1))
        if rows is not None:
            if not (rows >= 0 and rows < self._rows):
                raise MatrixOutOfRangeError(
                    "Row out of range value:%d  max:%d",
                    (rows, self._rows - 1))

    def compare(self, C):
        """
        compares self with Matrix C
        :returns: True if matrix is identical
        """
        ret = True
        cArray = C.array()
        if self._rows == C.getRows() and self._cols == C.getCols():
            for c in range(self._cols):
                for r in range(self._rows):
                    if self._array[c][r] != cArray[c][r]:
                        ret = False
                        break
                if not ret:
                    break
        else:
            ret = False
        return ret

    def multiply(self, B):
        """
        Multiply Matrix self x B = C

        :returns: Matrix C
        """
        a = self._array
        b = B.array()
        colsB = B.getCols()
        colsA = self._cols
        rowsA = self._rows
        resMatrix = Matrix(colsB, rowsA, self._cellType)
        C = resMatrix.array()

        for c in range(colsB):
            for r in range(rowsA):
                for cA in range(colsA):
                    res = a[cA][r] * b[c][cA]
                    C[c][r] += res
        return resMatrix
