#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     xmlprettyfier.py
# Author:   jro
# Creation: 07.12.09
# Purpose:

"""
Module xmlprettyfier.py

This is the documentation for the xmlprettyfier.py module.
"""

__docformat__ = "restructuredtext en"


def xmlPrettyfier(xmlStr):
    """
    prettyfies xml (makes human readable)
    Comes from DumbXMLFormatter in: /erp/xgw/trunk/SchemaParser.py
    """
    xmltext = xmlStr.replace("><", ">\n<")
    lines = xmltext.split("\n")
    indent = 0
    formattedLines = []
    for line in lines:
        indent_incr = line.count("<")
        indent_decr = line.count("</") * 2 + line.count("/>")
        if indent_decr:
            indent = indent + indent_incr - indent_decr
            formattedLines.append(indent * " " + line)
        else:
            formattedLines.append(indent * " " + line)
            indent = indent + indent_incr - indent_decr
    return formattedLines
