# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb.objects.core import Object
from cdb.objects import expressions
from cdb.objects import references
from cdb.comparch import resolver_nodes
from cdb.platform.gui import CDBCatalog

from cs.threed.hoops.converter import CSCONVERT_NAME, HOOPS_CONVERTER_NAME

DELIMITER = '/'

# every filtype that is NOT listed here is HOOPS only
CONVERTER_FILETYPES = {
    CSCONVERT_NAME: [
        "JPG",
        "FBX"
    ],
    "all": [
        "Acrobat",
        "STL",
        "JT",
        "STEP",
        "PRC",
        "Hoops:SCZ"
    ]
}

all_configurations = None

fHoopsConverterConfiguration = expressions.Forward(
    "cs.threed.hoops.converter.configurations.HoopsConverterConfiguration")
fHoopsConverterConfigurationEntry = expressions.Forward(
    "cs.threed.hoops.converter.configurations.HoopsConverterConfigurationEntry")


def get_configurations():
    global all_configurations

    if not all_configurations:
        configs = HoopsConverterConfiguration.Query()

        if len(configs) > len(set([conf.ft_name for conf in configs])):
            raise RuntimeError("Found non unique configurations. Not Converting")

        unsupported_configs = []
        for conf in configs:
            if conf.ft_name not in CONVERTER_FILETYPES["all"]:

                if conf.converter in CONVERTER_FILETYPES.keys():
                    if conf.ft_name not in CONVERTER_FILETYPES[conf.converter]:
                        unsupported_configs.append(conf)
                else: 
                    if any(conf.ft_name in val for key, val in CONVERTER_FILETYPES.items() if key != "all"):
                        unsupported_configs.append(conf)

        if unsupported_configs:
            raise RuntimeError("".join("Unsupported filetype {ftype} for converter {converter}.\n".format(
                ftype=conf.ft_name, converter=conf.converter) for conf in unsupported_configs))

        all_configurations = configs

    return all_configurations


def get_csconvert_config_params(conf):
    from cs.threed.hoops.converter import csconvert

    std_mod_location, cust_mod_location = _get_module_location(conf.cdb_module_id)

    substitutions = {
        "$CADDOK_MODULE": std_mod_location,
        "$(CADDOK_MODULE)": std_mod_location
    }

    params = {}

    for param in conf.Parameters:
        if param.name and param.converter == conf.converter:

            for key in substitutions:
                if key in param.param_value:
                    cust_location_value = param.param_value.replace(param.param_value, cust_mod_location)

                    if os.path.exists(cust_location_value):
                        substitutions[key] = cust_mod_location
                    else:
                        substitutions[key] = std_mod_location

            split_param_name = param.name.rsplit(DELIMITER, 1)

            if len(split_param_name) > 1:

                if split_param_name[0] not in params:
                    params[split_param_name[0]] = {}

                params[split_param_name[0]][split_param_name[1]] = csconvert.apply_substitutions(param.param_value, substitutions)

            else:
                params[param.name] = csconvert.apply_substitutions(param.param_value, substitutions)

    return params


class HoopsConverterConfiguration(Object):
    __maps_to__ = "threed_hoops_configuration"
    __classname__ = "threed_hoops_configuration"

    Parameters = references.Reference_N(
        fHoopsConverterConfigurationEntry,
        fHoopsConverterConfigurationEntry.configuration_object_id == fHoopsConverterConfiguration.cdb_object_id
    )


class HoopsConverterConfigurationEntry(Object):
    __maps_to__ = "threed_hoops_configuration_ent"
    __classname__ = "threed_hoops_configuration_entry"


class HoopsConverterConfigurationNode(resolver_nodes.Node):
    __type_mapping__ = "threed_hoops_configuration"

    def getReferenced(self):
        return ["Parameters"]


class ThreedConverterCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        supported_converters = [HOOPS_CONVERTER_NAME]

        try:
            ft_name = self.getInvokingDlgValue("ft_name")
        except KeyError:
            ft_name = None

        if not ft_name or ft_name in CONVERTER_FILETYPES["all"]:
                supported_converters = [CSCONVERT_NAME, HOOPS_CONVERTER_NAME]
        else:
            for key in CONVERTER_FILETYPES:
                if ft_name in CONVERTER_FILETYPES[key] and key != "all":
                    supported_converters = [key]

        return supported_converters


def register():
    resolver_nodes.register_resolver_node(HoopsConverterConfigurationNode)


def _get_module_location(fqpyname):
    from cdb.comparch import modules

    customer_dir = ""
    std_dir = ""
    mod = modules.Module.ByKeys(fqpyname)

    if mod:
        customer_mod = mod.ModifiablePatchingModuleExt

        if customer_mod:
            customer_dir = customer_mod.module_dir

        std_dir = mod.module_dir

    return (std_dir, customer_dir)
