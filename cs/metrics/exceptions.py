#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
cs.metrics Exception module
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import ue


class OrphanedKPIException(ue.Exception):

    def __init__(self, *args, **kwargs):
        label = "cdbqc_orphaned_kpi_ex"
        super(OrphanedKPIException, self).__init__(label, *args, **kwargs)
