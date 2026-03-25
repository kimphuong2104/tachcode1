#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2003 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# welche Konvertierungen werden von diesem Plugin abgedeckt:

Conversions = {
    "MS-Word": ["pdf"],
    "MS-Word:DOCX": ["pdf"],
    "MS-Word:DOCM": ["pdf"],
    "MS-Excel": ["pdf"],
    "MS-Excel:XLSX": ["pdf"],
    "MS-Excel:XLSM": ["pdf"],
    "MS-Excel:XLSB": ["pdf"],
    "MS-Outlook": ["pdf"],
    "MS-PowerPoint": ["pdf"],
    "MS-PowerPoint:PPTX": ["pdf"],
    "MS-PowerPoint:PPTM": ["pdf"],
    "MS-Project": ["pdf"],
    "MS-Visio": ["pdf"],
    "MS-Visio:VSDX": ["pdf"],
}

# maps the conversion targets to result filetypes
ResultTypes = {"pdf": "Acrobat"}
