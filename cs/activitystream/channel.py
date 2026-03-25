#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import warnings

from cs.activitystream.objects import Channel

__docformat__ = "restructuredtext en"
__all__ = ["Channel"]


warnings.warn(
    "Module cs.activitystream.channel is deprecated and will be "
    "removed in a future release. Please use "
    "cs.activitystream.objects.",
    DeprecationWarning,
    stacklevel=2,
)
