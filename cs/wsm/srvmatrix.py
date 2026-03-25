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


class MatrixOutOfRangeError(Exception):
    pass


class Matrix(object):
    @staticmethod
    def createIdentityMatrix(size, typ):
        matrix = Matrix(size, size, typ)
        matrix.initToIdentity()
        return Matrix

    def __init__(self, cols, rows, typ):
        row = []
        for _ in six.moves.range(rows):
            row.append(typ(0))
        self._array = []
        for _ in six.moves.range(cols):
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
        for i in six.moves.range(self._cols):
            resRow.append(self._array[i][row])
        return resRow

    def getElement(self, col, row):
        self._rangeCheck(col, row)
        return self._array[col][row]

    def initMatrixFromArray(self, array):
        cols = len(array)

        for c in six.moves.range(len(array)):
            rows = len(array[c])
            self._sizeCheck(cols, rows)
            for r in six.moves.range(rows):
                self._array[c][r] = self._cellType(array[c][r])

    def initToIdentity(self):
        minsize = min(self._rows, self._cols)
        for i in six.moves.range(minsize):
            self._array[i][i] = self._cellType(1)

    def getCellType(self):
        return self._cellType

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
                    u"Column out of range value:%d max:%d" % (cols, self._cols - 1)
                )
        if rows is not None:
            if not (rows >= 0 and rows <= self._rows):
                raise MatrixOutOfRangeError(
                    u"Row out of range value:%d max:%d" % (rows, self._rows - 1)
                )

    def _rangeCheck(self, cols, rows):
        if cols is not None:
            if not (cols >= 0 and cols < self._cols):
                raise MatrixOutOfRangeError(
                    u"Column out of range value:%d max:%d" % (cols, self._cols - 1)
                )
        if rows is not None:
            if not (rows >= 0 and rows < self._rows):
                raise MatrixOutOfRangeError(
                    u"Row out of range value:%d max:%d" % (rows, self._rows - 1)
                )

    def compare(self, C):
        """
        compares self with Matrix C
        :returns: True if matrix is identical
        """
        ret = True
        cArray = C.array()
        if self._rows == C.getRows() and self._cols == C.getCols():
            for c in six.moves.range(self._cols):
                for r in six.moves.range(self._rows):
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

        for c in six.moves.range(colsB):
            for r in six.moves.range(rowsA):
                for cA in six.moves.range(colsA):
                    res = a[cA][r] * b[c][cA]
                    # print("c[%s][%s], cA:%s  a[cA][r]:%s , b[c][cA]: %s, res:%s" % (c,r,cA,a[cA][r],b[c][cA],res))
                    C[c][r] += res
                # print("C[c][r] = %s" % C[c][r])
        return resMatrix
