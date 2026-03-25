# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


class RegisterHoopsPlugin(object):

    def run(self):
        from cdb.acs.acstools import cli_register
        cli_register("hoops")


class UnregisterHoopsPlugin(object):

    def run(self):
        from cdb.acs.acstools import cli_unregister
        cli_unregister("hoops")


class SetConverterConfigurations(object):
    """
    Set Default Converter Configurations and Parameters
    """

    def run(self):
        from cdb import sqlapi
        from cdb.comparch import modules
        from cdb.comparch import content

        config_classname = "threed_hoops_configuration"
        config_param_classname = "threed_hoops_configuration_ent"

        conf_update_rule = {
            "target_format": "pdf",
            "pyrule": "3DC Converter Documents",
            "ft_name": "Acrobat",
            "converter": "CSConvert"
        }
        updated_config_id = None
        config_id_to_overwrite = None

        m = modules.Module.ByKeys('cs.threed.hoops')
        content_filter = content.ModuleContentFilter([config_classname, config_param_classname])
        mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

        existing_configs = sqlapi.RecordSet2(table=config_classname)
        old_configs = [conf for conf in existing_configs if all(hasattr(conf, attr) for attr in ["pyrule", "target_format"])]

        for mc_item in mc.getItems(config_classname).values():

            if mc_item.getAttr("ft_name") == conf_update_rule["ft_name"] and old_configs:

                configs_for_rule = [conf for conf in old_configs if conf.target_format == conf_update_rule["target_format"]]

                if configs_for_rule:
                    # delete the configs where the conf_update_rule does not apply for pyrule but for target_format
                    configs_to_delete = [conf for conf in configs_for_rule if conf.pyrule != conf_update_rule["pyrule"]]

                    if configs_to_delete:
                        sqlapi.SQLdelete(
                            "FROM threed_hoops_configuration WHERE cdb_object_id IN (%s)" % (", ".join(["'%s'" % conf.cdb_object_id for conf in configs_to_delete])))
                        sqlapi.SQLdelete("FROM threed_hoops_configuration_ent WHERE configuration_object_id IN (%s)" % (
                            ", ".join(["'%s'" % conf.cdb_object_id for conf in configs_to_delete])))

                    configs_to_update = [conf for conf in configs_for_rule if conf.pyrule == conf_update_rule["pyrule"]]

                    if configs_to_update:
                        conf_to_update = configs_to_update[0] # there should be only one anyway
                        conf_to_update.update(ft_name=conf_update_rule["ft_name"], converter=conf_update_rule["converter"])

                        updated_config_id = conf_to_update.cdb_object_id
                        config_id_to_overwrite = mc_item.getAttr("cdb_object_id")

                        # skip insert if updated
                        continue

            try:
                mc_item.insertIntoDB()
            except:
                # Already there
                pass

        existing_config_params = sqlapi.RecordSet2(table="threed_hoops_configuration_ent")
        existing_param_tuples = [(p.name, p.configuration_object_id) for p in existing_config_params]

        for mc_item in mc.getItems(config_param_classname).values():

            if updated_config_id and (mc_item.getAttr("name"), updated_config_id) in existing_param_tuples:
                sqlapi.SQLupdate("threed_hoops_configuration_ent SET converter = '%s' WHERE configuration_object_id = '%s' AND name = '%s'" % (
                    conf_update_rule["converter"], updated_config_id, mc_item.getAttr("name")))
            else:
                try:
                    mc_item.insertIntoDB()
                except:
                    # Already there
                    pass

                if config_id_to_overwrite and mc_item.getAttr("configuration_object_id") == config_id_to_overwrite:
                    sqlapi.SQLupdate("threed_hoops_configuration_ent SET configuration_object_id = '%s' WHERE configuration_object_id = '%s' AND name = '%s'" % (
                        updated_config_id, mc_item.getAttr("configuration_object_id"), mc_item.getAttr("name")))


class RemoveBcfpProp(object):

    def run(self):
        from cdb import sqlapi
        prop = "bcfp"
        sqlapi.SQLdelete("FROM cdb_prop_desc WHERE attr = '%s'" % prop)
        sqlapi.SQLdelete("FROM cdb_prop WHERE attr = '%s'" % prop)


pre = []
post = [UnregisterHoopsPlugin, RegisterHoopsPlugin, SetConverterConfigurations, RemoveBcfpProp]

if __name__ == "__main__":
    UnregisterHoopsPlugin().run()
    RegisterHoopsPlugin().run()
    SetConverterConfigurations().run()
    RemoveBcfpProp().run()
