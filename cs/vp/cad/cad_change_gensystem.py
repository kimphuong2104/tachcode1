#!/usr/bin/env powerscript
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import misc, util, ue
from cs.documents import Document

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class cadchangegensystem:
    context_name = "cadtalkstdinout"

    def readInput(self, ctx):
        """
        Read Userexits Input
        """
        z_nummer = ""
        z_index = ""
        destinationFiletype = ""
        lines = ctx.stdin
        ok = 1
        llen = len(lines)
        if llen < 3:
            ok = 0
            misc.cdblogv(misc.kLogErr, 0, "wrong count of input parameters: %s, %s" % (llen, ctx.stdin))
        else:
            z_nummer = lines[0]
            z_index = lines[1]
            destinationFiletype = lines[2]
            misc.cdblogv(misc.kLogMsg, 7, "input for change gen system ue: %s, %s, %s" % (z_nummer, z_index, destinationFiletype))
            if z_nummer == "":
                ok = 0
                misc.cdblogv(misc.kLogErr, 0, "parameter for z_nummer is empty")
            if destinationFiletype == "":
                ok = 0
                misc.cdblogv(misc.kLogErr, 0, "parameter for the new 'erzeug_system' is empty")

        return [ok, z_nummer, z_index, destinationFiletype]

    def writeResult(self, ctx, result):
        """
        Write result
        """
        ctx.writeln("%s" % result[0])
        ctx.writeln(result[1])

    def impl(self, ctx):
        result = [1010, "Component implementation error"]
        inp = self.readInput(ctx)
        if inp[0]:

            model = Document.ByKeys(inp[1], inp[2])
            if model:
                result = model.cad_change_gensystem(inp[3])

            else:
                result = [1011, str(util.ErrorMessage("drawing number2", inp[1], inp[2]))]
                misc.cdblogv(misc.kLogErr, 0, result[1])

        else:
            result = [1012, str(util.ErrorMessage("function2"))]

        self.writeResult(ctx, result)


ue.run(cadchangegensystem)
