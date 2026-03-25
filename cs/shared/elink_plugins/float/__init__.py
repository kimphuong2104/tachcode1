#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Number edit validator plug in for eLink applications.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


"""
To test the validateInput function in Firefox:

cdb.elink.decimal_separator = "";
cdb.elink.group_separator = "";
// non-numerical
console.assert(cdbFloatPlugin.validateInput("a") == false);
console.assert(cdbFloatPlugin.validateInput("a0") == false);
console.assert(cdbFloatPlugin.validateInput("0a0") == false);
console.assert(cdbFloatPlugin.validateInput("1-1") == false);
// integer
console.assert(cdbFloatPlugin.validateInput("0") == true);
console.assert(cdbFloatPlugin.validateInput("-1") == true);
console.assert(cdbFloatPlugin.validateInput("1234") == true);
// wrong separator
console.assert(cdbFloatPlugin.validateInput("-1,2") == false);
console.assert(cdbFloatPlugin.validateInput("-1.2") == false);
console.assert(cdbFloatPlugin.validateInput("-1,0", 0) == false);
console.assert(cdbFloatPlugin.validateInput("-1,0", 1, true) == false);
// decimal place & strict/nonstrict
console.assert(cdbFloatPlugin.validateInput("-1", 0) == true);
console.assert(cdbFloatPlugin.validateInput("1", 0) == true);
console.assert(cdbFloatPlugin.validateInput("-1", 1) == true);
console.assert(cdbFloatPlugin.validateInput("1", 1) == true);
console.assert(cdbFloatPlugin.validateInput("-1", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("1", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("-1", 1, true) == true);
console.assert(cdbFloatPlugin.validateInput("1", 1, true) == true);


cdb.elink.decimal_separator = ",";
cdb.elink.group_separator = "";
//non-numerical
console.assert(cdbFloatPlugin.validateInput("a") == false);
console.assert(cdbFloatPlugin.validateInput("a0") == false);
console.assert(cdbFloatPlugin.validateInput("0a0") == false);
console.assert(cdbFloatPlugin.validateInput("1-1") == false);
//integer
console.assert(cdbFloatPlugin.validateInput("0") == true);
console.assert(cdbFloatPlugin.validateInput("-1") == true);
console.assert(cdbFloatPlugin.validateInput("1234") == true);
//wrong separator
console.assert(cdbFloatPlugin.validateInput("-1.2") == false);
console.assert(cdbFloatPlugin.validateInput("-1.0", 1) == false);
console.assert(cdbFloatPlugin.validateInput("-1.2", 0) == false);
console.assert(cdbFloatPlugin.validateInput("-1.0", 1) == false);
//decimal place & strict/nonstrict
console.assert(cdbFloatPlugin.validateInput("-1,2") == false);
console.assert(cdbFloatPlugin.validateInput("1", 1) == false);
console.assert(cdbFloatPlugin.validateInput("1,234", 1) == false);
console.assert(cdbFloatPlugin.validateInput("-1,2", 1) == true);
console.assert(cdbFloatPlugin.validateInput("1", 1, true) == true);
console.assert(cdbFloatPlugin.validateInput("1,234", 1, true) == true);
console.assert(cdbFloatPlugin.validateInput("-1", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("1", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("-1,0", 0, true) == true);


cdb.elink.decimal_separator = ",";
cdb.elink.group_separator = ".";
//non-numerical
console.assert(cdbFloatPlugin.validateInput("a") == false);
console.assert(cdbFloatPlugin.validateInput("a0") == false);
console.assert(cdbFloatPlugin.validateInput("0a0") == false);
console.assert(cdbFloatPlugin.validateInput("1-1") == false);
//integer
console.assert(cdbFloatPlugin.validateInput("0") == true);
console.assert(cdbFloatPlugin.validateInput("-1") == true);
console.assert(cdbFloatPlugin.validateInput("1234") == false);
console.assert(cdbFloatPlugin.validateInput("1.234") == true);
//wrong separator
console.assert(cdbFloatPlugin.validateInput("-1.2") == false);
console.assert(cdbFloatPlugin.validateInput("-1.0", 1) == false);
console.assert(cdbFloatPlugin.validateInput("-1.2", 0) == false);
console.assert(cdbFloatPlugin.validateInput("-1.0", 1) == false);
console.assert(cdbFloatPlugin.validateInput("-1234,0", 1) == false);
console.assert(cdbFloatPlugin.validateInput("-1,234.0", 1) == false);
console.assert(cdbFloatPlugin.validateInput("1234.234") == false);
//decimal place & strict/nonstrict
console.assert(cdbFloatPlugin.validateInput("-1,2") == false);
console.assert(cdbFloatPlugin.validateInput("1", 1) == false);
console.assert(cdbFloatPlugin.validateInput("1,234", 1) == false);
console.assert(cdbFloatPlugin.validateInput("-1,2", 1) == true);
console.assert(cdbFloatPlugin.validateInput("1", 1, true) == true);
console.assert(cdbFloatPlugin.validateInput("1,234", 1, true) == true);
console.assert(cdbFloatPlugin.validateInput("-1", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("1", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("-1,0", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("-1.234,0", 1) == true);
console.assert(cdbFloatPlugin.validateInput("-1.234,0", 2) == false);
console.assert(cdbFloatPlugin.validateInput("-1.234,0", 2, true) == true);
console.assert(cdbFloatPlugin.validateInput("1234.234", 0, true) == false);
console.assert(cdbFloatPlugin.validateInput("1.234.23", 0, true) == false);
console.assert(cdbFloatPlugin.validateInput("1.234.234", 0, true) == true);
console.assert(cdbFloatPlugin.validateInput("1.234.234", 1, true) == true);
"""
