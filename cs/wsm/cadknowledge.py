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
import six

WSM_RELTYPE = "WSM"

Appl2OccurrenceReltypes = {
    u"ProE": [u"ProE:Ref"],
    u"CatiaV5": [u"Catia:Ref", u"Catia:GRef"],
    u"inventor": [u"inventor:Ref", u"inventor:VRef"],
    u"SolidEdge": [u"SolidEdge:Ref"],
    u"SolidWorks": [
        u"SolidWorks:Ref",
        u"solidworks_direct",
        u"solidworks_part",
        u"solidworks_context",
        u"solidworks_archive",
    ],
    u"Unigraphics": [u"Unigraphics:Ref", u"Unigraphics"],
}

Appl2ClientNames = {
    u"acad": [u"acad", u"acad:dwt"],
    u"Catia:model": [u"Catia:model", u"Catia:session"],
    u"CatiaV5": [
        u"CatiaV5",
        u"CatiaV5:Part",
        u"CatiaV5:Prod",
        u"CatiaV5:Drawing",
        u"CatiaV5:cgr",
        u"CatiaV5:Process",
        u"CatiaV5:Processz",
        u"CatiaV5:Prodz",
    ],
    u"inventor": [
        u"inventor",
        u"inventor:prt",
        u"inventor:asm",
        u"inventor:dft",
        u"inventor:weld",
        u"inventor:psm",
        u"inventor:iprae",
    ],
    u"NESCAD": [u"NESCAD"],
    u"ProE": [
        u"ProE",
        u"ProE:Asmbly",
        u"ProE:Part",
        u"ProE:Drawing",
        u"ProE:Diagram",
        u"ProE:Format",
        u"ProE:Layout",
        u"ProE:Markup",
        u"ProE:Sketch",
        u"ProE:Report",
        u"ProE:Symbol",
        u"ProE:Table",
        u"ProE:Manufact",
    ],
    u"SolidEdge": [
        u"SolidEdge",
        u"SolidEdge:asm",
        u"SolidEdge:part",
        u"SolidEdge:draft",
        u"SolidEdge:psm",
        u"SolidEdge:pwd",
        u"SolidEdge:zip",
    ],
    u"SolidWorks": [
        u"SolidWorks",
        u"SolidWorks:asm",
        u"SolidWorks:part",
        u"SolidWorks:frm",
        u"SolidWorks:zip",
    ],
    u"Unigraphics": [
        u"Unigraphics",
        u"Unigraphics:prt",
        u"Unigraphics:drw",
        u"Unigraphics:zip",
    ],
}

Appl2PartType = {
    u"acad": u"acad:dwt",  # <-- which one is an acad part ??
    u"Catia:model": u"Catia:model",  # <-- which one is an catia part ??
    u"CatiaV5": u"CatiaV5:Part",
    u"inventor": u"inventor:prt",
    # u"NESCAD": [u"NESCAD"],
    u"ProE": u"ProE:Part",
    u"SolidEdge": u"SolidEdge:part",
    u"SolidWorks": u"SolidWorks:part",
    u"Unigraphics": u"Unigraphics:prt",
}


# applications that fill-out the fields t_nummer2/t_index2 of cdb_doc_rel
ApplWritesTNummer2 = {u"CatiaV5", u"inventor", u"acad", u"Unigraphics"}


def getApplByClientName(clientName):
    ret = None
    for appl, clientNames in six.iteritems(Appl2ClientNames):
        if clientName in clientNames:
            ret = appl
            break
    return ret
