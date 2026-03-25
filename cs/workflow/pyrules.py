#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.lru_cache import lru_cache
from cdb.objects import Forward
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import ReferenceMethods_1

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

fRule = Forward("cdb.objects.rules.Rule")
fRuleWrapper = Forward("{}.RuleWrapper".format(__name__))


@lru_cache(maxsize=1, clear_after_ue=False)
def all_wrappers_by_name():
    return {
        wrapper.name: wrapper
        for wrapper in RuleWrapper.Query()
    }


class RuleWrapper(Object):
    __maps_to__ = "cdbwf_pyrule"
    __classname__ = "cdbwf_pyrule"

    Rule = Reference_1(fRule, fRuleWrapper.cdb_pyrule)

    @classmethod
    def ByName(cls, name):
        return all_wrappers_by_name()[name]


class WithRuleWrapper(object):
    """
    Adds RuleWrapper-related functionality to a "client" class. Client classes
    have to implement the method ``_get_rule_object_id``.
    """
    def _get_rule_object_id(self):
        raise RuntimeError("to be implemented by subclasses")

    def _getRuleWrapper(self):
        rule_oid = self._get_rule_object_id()
        if rule_oid:
            for x in fRuleWrapper.KeywordQuery(cdb_object_id=rule_oid):
                return x
        return None

    RuleWrapper = ReferenceMethods_1(fRuleWrapper, _getRuleWrapper)

    def _getRule(self):
        wrapper = self.RuleWrapper
        if wrapper:
            return wrapper.Rule
        return None

    Rule = ReferenceMethods_1(fRule, _getRule)

    def getRuleName(self):
        wrapper = self.RuleWrapper
        if wrapper:
            return wrapper.name
        return None
