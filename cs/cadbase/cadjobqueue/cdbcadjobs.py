# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module cdbcadjobs

This is the documentation for the cdbcadjobs module.
"""

import sys
import socket
from cdb import misc
from cdb import auth
from cdb import CADDOK
from cs.cadbase import cadjobqueue


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


# Starting Queue
if __name__ == "__main__":
    retVal = 1
    if auth.persno:
        misc.cdblog_exit("")
        misc.cdblog_init("CadJob-SERVER", "%s@%s" % (auth.login, socket.gethostname()), "0", "0")
        misc.log(2, "CadJob: running CadJob Server (%s)" % CADDOK)
        retVal = cadjobqueue.get_cad_convert_queue().cli([arg.decode("utf-8") for arg in sys.argv])
        misc.cdblog_exit("CadJob-SERVER terminated")
    sys.exit(retVal)
