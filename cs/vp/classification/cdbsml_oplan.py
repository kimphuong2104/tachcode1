#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
SML Objektplan
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb import ue
from cs.vp.classification import oplan
from cs.vp.classification.oplan import sml

# Exported objects
__all__ = ['handle_request', ]


handle_request = oplan.handle_request


class ServerUE:
    context_name = "cdbscript"

    def impl(self, ctx):
        # If there is an SC we will use it
        pset_id = ""
        if "sachgruppe" in ctx.dialog.get_attribute_names():
            pset_id = ctx.dialog["sachgruppe"]
        if pset_id:
            ctx.url(sml.getPSetInfoURL(pset_id))
        else:
            # Maybe the server told us the path
            path = ""
            try:
                if "cdb::argument.cdbsml_path" in ctx.ue_args.get_attribute_names():
                    path = ctx.ue_args["cdb::argument.cdbsml_path"] + "/"
            except Exception:
                pass
            ctx.url("powerscript/cs.vp.classification.oplan/%s/%s" % (sml.ELINK_OPLAN_TEMPLATE_NAME, path))

# When running as a userexit, set url ...
if __name__ == '__main__':
    ue.run(ServerUE)
