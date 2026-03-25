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

from cdb.comparch import constants
from cdb import util
from cs.web.components import outlet_config
from cs.web.components.ui_support.utils import class_available_in_ui


class ModuleProtOutletCallback(outlet_config.OutletPositionCallbackBase):
    """
    A callback that generates outlet positions for protocol actions
    that provide additional info.
    """
    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        """
        This callback allows you to manipulate the configuration of the
        position. You may change `pos_config` or return a list of dictionaries
        that should be used instead of this configuration.
        """
        result = []
        if obj and obj.action == constants.ProtocolAction.Update:
            cfg = deepcopy(pos_config)
            cfg["title"] = util.get_label("cdb_module_prot_change_log")
            url = "/powerscript/cdb.comparch.elink_apps.comparch/update_details?module_id=" + \
                six.moves.urllib.parse.quote(obj.module_id) + "&protocol_id=" + \
                six.text_type(obj.protocol_id)
            cfg["properties"].update({"url": url})
            result.append(cfg)
        if obj and obj.action in (constants.ProtocolAction.Update,
                                  constants.ProtocolAction.Patch):
            cfg = deepcopy(pos_config)
            cfg["title"] = util.get_label("cdb_module_prot_opt_mc_log")
            url = "/powerscript/cdb.comparch.elink_apps.comparch/update_details_opt_mc?module_id=" + \
                six.moves.urllib.parse.quote(obj.module_id) + \
                "&protocol_id=" + \
                six.text_type(obj.protocol_id)
            cfg["properties"].update({"url": url})
            result.append(cfg)
        return result

# Guard importing as main module
if __name__ == "__main__":
    pass
