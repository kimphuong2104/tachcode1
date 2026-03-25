#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module cdbversion

Fetches version information
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from cdb import CADDOK, typeconversion, platform, i18n, fls, misc
from cdb.tokens import public_key_path
from cdb.rte import get_runtime


from cs.wsm.pkgs.xmlmapper import CDB_VERSION_DESC
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.wsmcompversion import WSM_COMPONENT_VERSION
from cdbwrapc import getVersionDescription, verstring, getApplicationName
from cdb.comparch.packages import Package
from lxml import etree as ElementTree


class GetCdbVersionProcessor(CmdProcessorBase):
    """
    Handler class for cdbversion command.
    """

    name = u"cdbversion"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        Return CDB version.

        :Return:
            errCode : integer indicating command success

        """
        cdbVersion, _, serviceLevel = verstring(True).rpartition(".")
        versionDesc = getVersionDescription()
        csWorkspacesVersion = self.getCsWorkspacesVersion()
        brandedName = getApplicationName()
        presignedBlobConfig = self.checkPresignedBlobConfig()
        sessionLang = i18n.default()

        versionDesc = CDB_VERSION_DESC(
            version=cdbVersion,
            service_level=serviceLevel,
            version_desc=versionDesc,
            wsm_component_vers=WSM_COMPONENT_VERSION,
            cs_workspaces_vers=csWorkspacesVersion,
            branded_name=brandedName,
            presigned_blob_configuration=presignedBlobConfig,
            session_lang=sessionLang,
        )
        cadPkgs = self.getRequiredCADPackages()
        cadResList = self.getInstalledCADPackages(cadPkgs)

        rootEl = versionDesc.etreeElem
        rootEl.append(cadResList)

        pkgs = self.getPackagesForVersionCheck()
        pkgVersions = self.getPackageVersions(pkgs)
        rootEl.append(pkgVersions)

        # use default encoding "utf-8" for first query
        xmlText = ElementTree.tostring(rootEl, encoding="utf-8")
        resultStream.write(xmlText)

        return WsmCmdErrCodes.messageOk

    def getCsWorkspacesVersion(self):
        """
        :return: string like "10.1.0.6", "10.1.dev", "trunk.dev" or "missing"
        """
        pkg = Package.ByKeys("cs.workspaces")
        if pkg:
            res = pkg.version
        else:
            logging.error("Unexpected error: cs.workspaces package missing")
            res = "missing"
        return res

    def getRequiredCADPackages(self):
        """
        Reads input, collects all cad package names
        Input:
            <CAD_PACKAGE_LIST>
                <CAD_PACKAGE name="" feature="">
                <CAD_PACKAGE name="">
                ...
            </CAD_PACKAGE_LIST>
        :return: list of cad package names
        """
        requiredCADPackages = []
        cadPkgList = self._rootElement.etreeElem.find("CAD_PACKAGE_LIST")
        if cadPkgList is not None:
            for cadPkg in cadPkgList:
                requiredCADPackages.append(
                    (cadPkg.attrib.get("name"), cadPkg.attrib.get("feature"))
                )
        return requiredCADPackages

    def getPackagesForVersionCheck(self):
        """
        Reads input, collects all cad package names
        Input:
              <PACKAGES_TO_CHECK>
                <PACKAGE name=""/>
                <PACKAGE name=""/>
                ...
              </PACKAGES_TO_CHECK>
        :return: list of package names
        """
        pkgs = []
        pkgRoot = self._rootElement.etreeElem.find("PACKAGES_TO_CHECK")
        if pkgRoot is not None:
            for pkg in pkgRoot:
                pkgs.append(pkg.attrib.get("name"))
        return pkgs

    def getInstalledCADPackages(self, cadPkgs):
        """
        Checks if cad packages of given list cadPkgs are installed,
        returns xml tree with installed cad packages
        :param: cadPkgs: list of cad package names
        :return: xml tree:
                    <CAD_PACKAGE_LIST>
                        <CAD_PACKAGE name="" licavailable="">
                        <CAD_PACKAGE name="">
                        ...
                    </CAD_PACKAGE_LIST>
        """
        xmlTree = ElementTree.Element("CAD_PACKAGE_LIST")
        for pkgname, feature in cadPkgs:
            pkg = Package.ByKeys(pkgname)
            if pkg:
                node = ElementTree.Element("CAD_PACKAGE")
                node.attrib[u"name"] = pkgname
                xmlTree.append(node)
            elif feature:
                node = ElementTree.Element("CAD_PACKAGE")
                node.attrib[u"name"] = pkgname
                node.attrib["licavailable"] = str(int(fls.is_available(feature)))
                xmlTree.append(node)
        return xmlTree

    def getPackageVersions(self, pkgs):
        """
        :param: pkgs: list of package names
        :return: xml tree:
                    <PACKAGES_TO_CHECK>
                        <PACKAGE name="" version="">
                        <PACKAGE name="" version="">
                        ...
                    </PACKAGES_TO_CHECK>
        """
        xmlTree = ElementTree.Element("PACKAGES_TO_CHECK")
        for pkgname in pkgs:
            pkg = Package.ByKeys(pkgname)
            if pkg:
                node = ElementTree.Element("PACKAGE")
                node.attrib[u"name"] = pkgname
                node.attrib[u"version"] = pkg.version
                xmlTree.append(node)
        return xmlTree

    @classmethod
    def checkPresignedBlobConfig(self):
        ret = 0
        # wenn PC-Client zu erst disable checken, um keine Lizenz fuer den Fall
        # zu ziehen
        appinfo = misc.CDBApplicationInfo()
        is_web = appinfo.rootIsa(misc.kAppl_HTTPServer)
        disable_direct_blob = False
        if not is_web:
            try:
                disable_direct_blob = typeconversion.to_bool(
                    CADDOK.WS_DISABLE_DIRECT_BLOB
                )
            except (AttributeError, KeyError) as _e:
                pass
        if disable_direct_blob:
            ret = CDB_VERSION_DESC.CADDOK_PRESIGNED_BLOB_DISABLED
        else:
            lic_available = fls.get_license("WSM_004")
            if not lic_available:
                ret = CDB_VERSION_DESC.PRESIGNED_NO_LICENSE
            # if the following property exists, it must have a value
            # if it does not exists, we assume it is not needed (as in 15.8)
            pubkey_endpoint_prop = platform.SystemSettings().ByKeys(
                name="pubkey_endpoint"
            )
            if pubkey_endpoint_prop is not None and not pubkey_endpoint_prop.wert:
                ret |= CDB_VERSION_DESC.PUBKEY_ENDPOINT_NOT_SET

            secrets = get_runtime().secrets
            secrets_available = False
            if secrets:
                kp = public_key_path("blob_access")
                secrets_available = bool(secrets.resolve(kp))
            if not secrets_available:
                ret |= CDB_VERSION_DESC.NO_CRYPTO_KEYS
        return ret
