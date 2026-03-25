#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     translate.py
# Author:   wen
# Creation: 28.03.08
# Purpose:

"""
Module translate.py

This is the documentation for the translate.py module.
"""

__docformat__ = "restructuredtext en"


import six


# default argument for translation if placeholder cannot be dissolved
DEFAULTARG = "??"


def tr(errmsg):
    """
    dummy translate routine. Enables the the qt
    translator to extract the (to translate)
    message strings from the source codes.
    I.e. every string that should be available to the
    localisation infrastructure, should be marked in the code like this:

    tr("lala")

    have fun
    """
    return six.text_type(errmsg)


def translate(ctx, errmsg):
    """
    dummy translate routine with context.
    """
    return ctx, six.text_type(errmsg)
