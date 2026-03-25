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


from cs.wsm.lrucache import LRUCache


class AppInfoCache(object):
    def __init__(self, appInfoParser):
        self._lruCache = LRUCache(10000)
        self._appInfoParser = appInfoParser

    def getAppinfo(self, appinfoFileObject, raiseOnEmpty=False):
        """
        :raises NoAppinfoContentError if the appinfo file to parse is emtpy and raiseOnEmpty is True
        """
        revisionBlobId = appinfoFileObject.cdbf_hash
        found, appinfoData = self._lruCache.getObject(revisionBlobId)
        if not found:
            content = appinfoFileObject.get_content()
            if content:
                appinfoData = self._appInfoParser.parseAppInfo(content, raiseOnEmpty)
                self._lruCache.addObject(revisionBlobId, appinfoData)
        return appinfoData
