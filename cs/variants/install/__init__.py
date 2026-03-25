# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class DisableCsVpVariants:
    def run(self):
        from cs.variants.tools.disable_cs_vp_variants import disable_cs_vp_variants

        disable_cs_vp_variants()


pre = []
post = [DisableCsVpVariants]
