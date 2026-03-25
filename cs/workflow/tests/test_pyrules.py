#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from cdb import testcase
from cdb.objects.rules import Rule
from cs.workflow import pyrules


def setup_module():
    testcase.run_level_setup()


class RuleWrapperTestCase(testcase.RollbackTestCase):
    def _get_rule(self, pyrule):
        return Rule.Create(name=pyrule)

    def _get_wrapper(self, pyrule, name_de):
        return pyrules.RuleWrapper.Create(
            cdb_pyrule=pyrule,
            name_de=name_de,
            category="TEST"
        )

    def test_all_wrappers_by_name(self):
        pyrules.all_wrappers_by_name.cache_clear()
        pyrules.RuleWrapper.Query().Delete()
        a = self._get_wrapper("a", "A")
        b = self._get_wrapper("b", "B")
        self.assertEqual(
            pyrules.all_wrappers_by_name(),
            {
                "A": a,
                "B": b,
            }
        )
        pyrules.all_wrappers_by_name.cache_clear()

    def test_references(self):
        rule = self._get_rule("RULE")
        wrapper = self._get_wrapper(rule.name, "WRAPPER")
        self.assertEqual(
            wrapper.Rule,
            rule
        )

    def test_ByName(self):
        pyrules.all_wrappers_by_name.cache_clear()
        a = self._get_wrapper("a", "A")
        b = self._get_wrapper("b", "B")
        self.assertEqual(
            pyrules.RuleWrapper.ByName("A"),
            a
        )
        self.assertEqual(
            pyrules.RuleWrapper.ByName("B"),
            b
        )
        pyrules.all_wrappers_by_name.cache_clear()


class WithRuleWrapperTestCase(testcase.RollbackTestCase):
    def test_get_rule_object_id(self):
        with self.assertRaises(RuntimeError):
            pyrules.WithRuleWrapper()._get_rule_object_id()

    def test_references(self):
        with self.assertRaises(AttributeError):
            _ = pyrules.WithRuleWrapper().RuleWrapper

    def test_getRuleName(self):
        with self.assertRaises(AttributeError):
            pyrules.WithRuleWrapper().getRuleName()
