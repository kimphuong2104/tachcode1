#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     srvpoint3d.py
# Author:   jro
# Creation: 18.11.08
# Purpose:

"""
Module srvpoint3d.py

This is the documentation for the point3d.py module.
"""

__docformat__ = "restructuredtext en"


class PointOutOfRangeError(Exception):
    pass


class Point3D(object):
    """
    represents a floating point in 3D coordinate system
    """

    def __init__(self, x, y, z):
        self._x = None
        self._y = None
        self._z = None
        self.setX(x)
        self.setY(y)
        self.setZ(z)

    def initFromList(self, l):
        if len(l) == 3:
            self.setX(l[0])
            self.setY(l[1])
            self.setZ(l[2])
        else:
            raise PointOutOfRangeError()

    def getX(self):
        return self._x

    def getY(self):
        return self._y

    def getZ(self):
        return self._z

    def setX(self, x):
        if x is not None:
            self._x = float(x)
        else:
            self._x = None

    def setY(self, y):
        if y is not None:
            self._y = float(y)
        else:
            self._y = None

    def setZ(self, z):
        if z is not None:
            self._z = float(z)
        else:
            self._z = None
