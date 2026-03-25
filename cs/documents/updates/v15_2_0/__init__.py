#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb.comparch import content, modules, protocol
from cdb.platform.acs import RelshipAccessProfile
from cdb.platform.mom.relships import Relship

MODULE_ID = "cs.documents"


class UpdateCatalogs(object):
    def run(self):  # pylint: disable=no-self-use
        self.update_catalogs()

    def update_catalogs(self):
        self.reset_catalog(
            classname="cdb_mod_event", attrs_to_update=["event_de", "event_en"]
        )
        self.reset_catalog(
            classname="cdb_mod_kind", attrs_to_update=["kind_de", "kind_en"]
        )
        self.reset_catalog(
            classname="cdb_mod_source", attrs_to_update=["source_de", "source_en"]
        )

    def reset_catalog(self, classname, attrs_to_update):  # pylint: disable=no-self-use
        # load module content
        m = modules.Module.ByKeys(MODULE_ID)
        content_filter = content.ModuleContentFilter([classname])
        mc = content.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

        # update data as defined by module content
        for item in mc.getItems(classname).values():
            rec = item._getPersistentRecord()  # pylint: disable=protected-access
            if rec:
                updates = dict(
                    [
                        (attr, item.getAttr(attr))
                        for attr in attrs_to_update
                        if not rec[attr]
                    ]
                )
                if updates:
                    rec.update(**updates)


class UpdateRelshipAccessProfiles(object):
    def run(self):  # pylint: disable=no-self-use
        self.update_rs_acc_prof()

    def update_rs_acc_prof(self):
        # cs.documents
        self._update_rs_acc_prof("Änderungsmitteilung", "Change Notification")

    def _isEquivalent(self, old, new):  # pylint: disable=no-self-use
        def get_mapping(rs_acc_prof):
            mapping = [dict(x) for x in rs_acc_prof.AccessMapping]
            for x in mapping:
                del x["rs_acc_prof"]
            mapping.sort()
            return mapping

        return old.mandatory == new.mandatory and get_mapping(old) == get_mapping(new)

    def _update_relships(self, old, new):  # pylint: disable=no-self-use
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
                    "Please check its usages manually." % (old_name, new_name)
                )


pre = []
post = [UpdateCatalogs, UpdateRelshipAccessProfiles]
