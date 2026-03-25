#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.comparch import protocol
from cdb.platform.acs import RelshipAccessProfile
from cdb.platform.mom.entities import Class
from cdb.platform.mom.relships import Relship
from cs.workflow.briefcases import Briefcase


class UpdateRelshipAccessProfiles(object):
    def run(self):
        self.update_rs_acc_prof()

    def update_rs_acc_prof(self):
        # cs.workflow
        self._update_rs_acc_prof("Prozesskomponenten", "Workflow components")

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


class InitBriefcaseIDs(object):
    def run(self):
        empty_ids = Briefcase.KeywordQuery(briefcase_id=None)
        for briefcase in empty_ids:
            briefcase.make_id(None)


pre = [InitBriefcaseIDs]
post = [UpdateRelshipAccessProfiles]
