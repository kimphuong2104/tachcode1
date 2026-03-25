#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
An API to check license of an eLink application or a eLink page.
To be used as a decorator, e.g.::

    from cdb import elink
    from cs.shared.elink_plugins import check_license

    @elink.using_template_engine("chameleon")
    @check_license.check_license("<license no.>")
    class MyElinkApp(elink.Application):
        ...

or::

    from cdb import elink
    from cs.shared.elink_plugins import check_license

    @elink.using_template_engine("chameleon")
    class MyElinkApp(elink.Application):
        ...

    @check_license.check_license("<license no.>")
    class MySpecialPage(elink.Template):
        ...
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def check_license(license_no):
    """
    Changes the `handle_request` method of target object to check the license
    with the specified number given by `license_no`. Writes the error
    message back directly if the license check fails.
    """

    def _handle_request(self, req, path=None):
        from cdbwrapc import allocate_license
        from cdb.fls import LicenseError
        try:
            allocate_license(license_no)
        except LicenseError as e:
            import sys
            req.charset = "utf-8"
            msg = u"%s" % e.message
            req.write(msg.encode("utf-8"))
        else:
            self._handle_request_without_license(req, path)

    def wrapper(cls):
        cls._handle_request_without_license = cls.handle_request
        cls.handle_request = _handle_request
        return cls

    return wrapper
