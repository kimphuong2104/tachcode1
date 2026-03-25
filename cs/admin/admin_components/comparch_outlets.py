# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Provider for additional eLink-like-registers
"""

from __future__ import absolute_import

from copy import deepcopy
import six

from cs.web.components import outlet_config


class ModulePatchOutletCallback(outlet_config.OutletPositionCallbackBase):
    """
    A callback that generates outlet positions for patches.
    """
    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        """
        This callback allows you to manipulate the configuration of the
        position. You may change `pos_config` or return a list of dictionaries
        that should be used instead of this configuration.
        """
        result = []
        if obj:
            cfg = deepcopy(pos_config)
            cfg["title"] = "Patch"
            url = "/powerscript/cdb.comparch.elink_apps.comparch/module_patch?module_id=%s&customized_module_id=%s&patch_type=%s&hide_ce_buttons=1" % (
                six.text_type(obj.module_id),
                six.text_type(obj.customized_module_id),
                six.text_type(obj.patch_type))
            cfg["properties"].update({"url": url})
            result.append(cfg)
        return result
