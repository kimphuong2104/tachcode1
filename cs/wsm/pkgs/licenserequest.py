#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module licenserequest

License processing
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import hmac
import hashlib
import six
import time
import logging

# Some imports
from cdb.fls import get_license, is_available

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.xmlmapper import LICENSE_INFO


class LicenseRequestHandler(CmdProcessorBase):
    """
    Handles a request for an offline license.
    """

    name = u"licenserequest"
    LIC_CAD = "WSM_005"
    LIC_OFFICE = "WSM_006"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        Return a license info object.
        """
        logging.info("LicenseRequestHandler start")
        currentTime = six.text_type(time.time())

        sh = hmac.new("AYBABTU".encode("utf-8"), digestmod=hashlib.md5)
        sh.update(currentTime.encode("utf-8"))

        # Check for base license of WSM
        # when we have more submodules also check for requested Plugins
        # Installed plugins must be requested by every Plugin
        main_lic = get_license("WSM_001")
        if not main_lic:
            logging.error("Requested WSM_001 Base Feature is not available")
        cad_lic = is_available(self.LIC_CAD)
        office_lic = is_available(self.LIC_OFFICE)
        if cad_lic or office_lic:
            cad_valid = get_license(self.LIC_CAD) and main_lic
            office_valid = get_license(self.LIC_OFFICE) and main_lic
        else:
            cad_valid = main_lic
            office_valid = main_lic
        cadLicAcquired = six.text_type(int(cad_valid))
        officeLicAcquired = six.text_type(int(office_valid))
        sh.update(cadLicAcquired.encode("utf-8"))
        signature = sh.hexdigest()
        sh.update(officeLicAcquired.encode("utf-8"))
        signature2 = sh.hexdigest()

        licenseInfo = LICENSE_INFO(
            current_time=currentTime,
            signature=signature,
            signature2=signature2,
            valid=cadLicAcquired,
            valid_office=officeLicAcquired,
        )
        xmlStr = licenseInfo.toEncodedString()
        resultStream.write(xmlStr)

        logging.info("LicenseRequestHandler end")
        return WsmCmdErrCodes.messageOk
