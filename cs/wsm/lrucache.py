#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     lrucache.py
# Author:   jro
# Creation: 21.05.10
# Purpose:

"""
Module lrucache.py

This is the documentation for the lrucache.py module.
"""

__docformat__ = "restructuredtext en"


class LRUEntry(object):
    def __init__(self, key, accessTime, data):
        self.key = key
        self.accesstime = accessTime
        self.data = data
        self.accessToData = dict()


class LRUCache(object):
    """
    Das ist jetzt einigermassen schnell.
    Jedenfalls besser als die heapq implementierung, die bei grossen caches
    mit 10000 eintragen leider sehr lange brauchte bei einem Update
    der accessTime fuer ein Objekt.

    Beim Zugriff auf ein Objekt wird nur die Accesstime in _data und _accessToData aktualisiert.
    Bei AddObjekt mit erreichter Obergrenze wird in accessTimeList das kleinste gueltige Objekt
    gesucht (d.h. welches in accessToData enthalten ist). Dieses wird dann accessToData und _data geloescht


    :ivar _data:    -> Dict von Key-> LRU Entry
    :ivar accessTime: Zahler fuer die Accestime
    :ivar _currentSize: Groesse des Caches
    :ivar accessTimeList: Geordnete Liste mit den vergebene Accesstimes. Nicht
                         alle Eintrage in der Liste sind gueltig. Die Liste enthaelt
                         auch alte Eintrage von aktualisierten Items
    :ivar accessToData: Dict: accessTime zu key

    """

    def __init__(self, maxSize):
        self._maxSize = maxSize
        self._data = dict()  # key->LRUEntry
        self.accessTime = 0
        self._currentSize = 0
        self.accessTimeList = []
        self.accessToData = dict()

    def getObject(self, key):
        data = None
        found = False
        lruEntry = self._data.get(key, None)
        if lruEntry is not None:
            data = lruEntry.data
            self.accessTime = self.accessTime + 1
            del self.accessToData[lruEntry.accesstime]
            self.accessToData[self.accessTime] = key
            lruEntry.accesstime = self.accessTime
            self.accessTimeList.append(self.accessTime)
            found = True
        return found, data

    def addObject(self, key, data):
        self.accessTime = self.accessTime + 1
        if self._currentSize < self._maxSize:
            lruEntry = LRUEntry(key, self.accessTime, data)
            self._data[key] = lruEntry
            self.accessToData[self.accessTime] = key
            self._currentSize = self._currentSize + 1
            self.accessTimeList.append(self.accessTime)
        else:
            minAccessTime = self.accessTimeList.pop(0)
            keyToRemove = self.accessToData.get(minAccessTime, None)
            while keyToRemove is None and len(self.accessTimeList):
                minAccessTime = self.accessTimeList.pop(0)
                keyToRemove = self.accessToData.get(minAccessTime, None)
            if keyToRemove is not None:
                del self._data[keyToRemove]
                del self.accessToData[minAccessTime]

            lruEntry = LRUEntry(key, self.accessTime, data)
            self._data[key] = lruEntry
            self.accessToData[self.accessTime] = key
            self.accessTimeList.append(self.accessTime)

    def __len__(self):
        return self._currentSize
