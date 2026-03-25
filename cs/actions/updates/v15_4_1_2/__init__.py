#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

from .fix_collate import RebuildUserDefinedViews

pre = []

post = [RebuildUserDefinedViews]

all_modules_post = []
