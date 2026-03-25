# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.comparch import content
from cdb.comparch import modules
from cdb.comparch import protocol
from cdb.platform.acs import RelshipAccessProfile
from cdb.platform.mom.relships import Relship


class UpdateCatalogs(object):
    def run(self):
        self.update_catalogs()

    def update_catalogs(self):
        self.reset_catalog(module_id='cs.vp.items', classname='cdb_part_categ', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.items', classname='cdb_part_surfac', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.items', classname='cdb_part_usab', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.items', classname='cdb_units', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.classification', classname='cdbsml_cg_types', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.classification', classname='cdbsml_cgroup', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.classification', classname='cdbsml_doc_purpose', attrs_to_update=['text_de', 'text_en'])
        self.reset_catalog(module_id='cs.vp.classification', classname='cdbsml_propcat', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.variants', classname='cdbvp_catalogue_folder', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.variants', classname='cdbvp_enums', attrs_to_update=['enum_text_de', 'enum_text_en'])
        self.reset_catalog(module_id='cs.vp.products', classname='cdbvp_maturity', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(module_id='cs.vp.classification', classname='sml_mm_state', attrs_to_update=['description', 'description_i18n_en'])

    def reset_catalog(self, module_id, classname, attrs_to_update):
        # load module content
        m = modules.Module.ByKeys(module_id)
        content_filter = content.ModuleContentFilter([classname])
        mc = content.ModuleContent(m.module_id, m. std_conf_exp_dir, content_filter)

        # update data as defined by module content
        for item in mc.getItems(classname).values():
            rec = item._getPersistentRecord()
            if rec:
                updates = dict([(attr, item.getAttr(attr)) for attr in attrs_to_update if not rec[attr]])
                if updates:
                    rec.update(**updates)


class UpdateRelshipAccessProfiles(object):
    def run(self):
        self.update_rs_acc_prof()

    def update_rs_acc_prof(self):
        # cs.vp.bom
        self._update_rs_acc_prof("Stücklistenpositionen", "BOM Items")

        # cs.vp.cad
        self._update_rs_acc_prof("Dokument der Variante", "The variant's document")

    def _isEquivalent(self, old, new):

        def get_mapping(rs_acc_prof):
            mapping = [dict(x) for x in rs_acc_prof.AccessMapping]
            for x in mapping:
                del x["rs_acc_prof"]
            mapping.sort()
            return mapping

        return (old.mandatory == new.mandatory and
                get_mapping(old) == get_mapping(new))

    def _update_relships(self, old, new):
        Relship.KeywordQuery(rs_acc_prof=old).Update(rs_acc_prof=new)

    def _update_rs_acc_prof(self, old_name, new_name):
        old = RelshipAccessProfile.ByKeys(old_name)
        new = RelshipAccessProfile.ByKeys(new_name)

        if old and new:
            if self._isEquivalent(old, new):
                self._update_relships(old_name, new_name)
                old.Delete()
            else:
                protocol.logWarning(
                    "cdb_rs_acc_prof '%s' is not equivalent to '%s'. "
                    "Please check its usages manually."
                    % (old_name, new_name))


pre = []
post = [UpdateCatalogs, UpdateRelshipAccessProfiles]
