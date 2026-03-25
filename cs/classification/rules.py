# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module rules

This is the documentation for the rules module.
"""

from collections import namedtuple
from cdb.objects import Object


class Rule(Object):
    __classname__ = "cs_classification_rule"
    __maps_to__ = "cs_classification_rule"

    def _set_readonly(self, ctx):
        ctx.set_fields_readonly(["cdb_classification_class_id", "property_name"])

    def _clear_rule_cache(self, ctx):
        from cs.classification.validation import ClassificationValidator
        ClassificationValidator.reload_rules()

    event_map = {
        ("modify", "pre_mask"): "_set_readonly",
        (('modify', 'create', 'copy', 'delete'), 'post'): '_clear_rule_cache'
    }


RuleValue = namedtuple("RuleValue", "id label")


class RuleValues(object):
    # NOTE: if ids are changed constants in classification web component must be changed accordingly
    InheritFromProperty = RuleValue(0, "")
    Yes = RuleValue(1, "Yes")
    No = RuleValue(2, "No")

    all_rule_values = [InheritFromProperty, Yes, No]

    @classmethod
    def by_label(cls, label):
        if label:
            for opt in cls.all_rule_values:
                if opt.label == label:
                    return opt
        return cls.InheritFromProperty
