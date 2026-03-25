#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


import os
import re
import socket
import sys

from cdb import acs, auth, CADDOK, misc, fls
from cdb.uberserver.mqsvc import MessageQueueService

from cs.threed.services.installation_fix import fix_installation
from cs.threed.services.utils import cleanup_orphaned_job_params

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class ThreedConversionServer(MessageQueueService):

    def __init__(self, site):
        service_number = re.search("[0-9]*$", self.__class__.__name__).group(0)
        service_name = "3D Conversion Server %s" % service_number
        super(ThreedConversionServer, self).__init__(
            site, service_name.strip(), None, "cs.threed.services.threedcs")

    @classmethod
    def install(cls, svcname, host, site, *args, **kwargs):
        if not svcname:
            svcname = cls.fqpyname()
        cfgfile = os.path.join("$CADDOK_BASE", "etc", "acs", "acs_threed.conf")
        # cls.isfile([cfgfile])  # TODO: activate again when E043793 is solved
        clsname = svcname.split(".")[-1]
        options = {
            "--config": cfgfile,
            "--classname": clsname,
            "--user": "cs_threed_service"
        }
        if (clsname == "ThreedConversionServer") and ("autostart" not in kwargs):
            kwargs["autostart"] = 1  # by default only autostart 1 service
        return super(ThreedConversionServer, cls).install(
            svcname, host, site, options=options, *args, **kwargs)


class ThreedConversionServer2(ThreedConversionServer):
    pass


class ThreedConversionServer3(ThreedConversionServer):
    pass


class ThreedConversionServer4(ThreedConversionServer):
    pass


class ThreedConversionServer5(ThreedConversionServer):
    pass


class ThreedConversionServer6(ThreedConversionServer):
    pass


class ThreedConversionServer7(ThreedConversionServer):
    pass


class ThreedConversionServer8(ThreedConversionServer):
    pass


class ThreedConversionServer9(ThreedConversionServer):
    pass


class ThreedConversionServer10(ThreedConversionServer):
    pass


class ThreedConversionServer11(ThreedConversionServer):
    pass


class ThreedConversionServer12(ThreedConversionServer):
    pass


class ThreedConversionServer13(ThreedConversionServer):
    pass


class ThreedConversionServer14(ThreedConversionServer):
    pass


class ThreedConversionServer15(ThreedConversionServer):
    pass


class ThreedConversionServer16(ThreedConversionServer):
    pass


if __name__ == "__main__":
    fls.allocate_server_license("3DSC_010")

    cleanup_orphaned_job_params()

    # workaround for E048622
    fix_installation()

    retVal = 1
    if auth.persno:
        misc.cdblog_exit("")
        args = [arg for arg in sys.argv]
        service_subname = ""
        if "--classname" in args:
            i = args.index("--classname")
            args.pop(i)
            service_subname = args.pop(i)
        misc.cdblog_init("THREEDCS", "%s@%s@%s" %
                         (service_subname, auth.login, socket.gethostname()), "0", "0")
        misc.log(2, "Running 3D Conversion Server (%s)" % CADDOK)
        retVal = acs.getQueue().cli(args)
        misc.cdblog_exit("3D Conversion Server terminated\n")
    sys.exit(retVal)
