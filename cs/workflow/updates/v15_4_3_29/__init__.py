#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.platform.mom.relations import DDUserDefinedView


class RemoveRespMappingColumns(object):
    """
    View is generated dynamically, so remove hard-coded column names,
    which may conflict with column order of the generator.
    """
    def run(self):
        view = DDUserDefinedView.ByKeys("cdbwf_resp_mapping")
        view.Update(uview_col_aliases="")
        view.rebuild(force=True)


pre = []
post = [RemoveRespMappingColumns]
