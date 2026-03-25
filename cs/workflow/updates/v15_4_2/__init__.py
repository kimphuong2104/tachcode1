#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb import transaction
from cdb.comparch import protocol
from cdb.platform.mom.entities import Class
from cs.workflow import constraints
from cs.workflow.pyrules import RuleWrapper


class MigrateRules(object):
    __category__ = None
    __table__ = None
    __attr__ = None

    def _get_missing_rules(self):
        raise RuntimeError("to be implemented by subclasses")

    def create_missing_wrappers(self):
        missing_wrappers = self._get_missing_rules()

        with transaction.Transaction():
            for missing_rule in missing_wrappers:
                RuleWrapper.Create(
                    cdb_pyrule=missing_rule,
                    category=self.__category__,
                    name_de=missing_rule,
                    name_en=missing_rule,
                    name_tr=missing_rule,
                    name_zh=missing_rule,
                )

        protocol.logMessage(
            "created {} missing '{}' rule wrappers".format(
                len(missing_wrappers),
                self.__category__
            )
        )

    def _get_wrappers(self):
        wrappers = sqlapi.RecordSet2(
            sql="SELECT cdb_object_id, cdb_pyrule "
                "FROM cdbwf_pyrule "
                "WHERE category='{}'".format(
                    self.__category__
                )
        )
        return {
            x.cdb_pyrule: x.cdb_object_id
            for x in wrappers
        }

    def _get_update_stmt(self):
        return (
            "{table} "
            "SET {attr}='{{oid}}' "
            "WHERE {attr}='{{rule}}'".format(
                table=self.__table__,
                attr=self.__attr__,
            )
        )

    def migrate_rule_names(self):
        wrappers = self._get_wrappers()
        stmt = self._get_update_stmt()

        with transaction.Transaction():
            for rule, oid in wrappers.items():
                sqlapi.SQLupdate(
                    stmt.format(
                        oid=sqlapi.quote(oid),
                        rule=sqlapi.quote(rule)
                    )
                )

        protocol.logMessage("migrated '{}' rules".format(self.__category__))


class MigrateConstraintRules(MigrateRules):
    __category__ = constraints.RULE_CATEGORY
    __table__ = "cdbwf_constraint"
    __attr__ = "rule_name"

    def _get_missing_rules(self):
        """
        Returns set of rule names to be created as rule wrappers, e.g. those
        used in constraints that neither exist in cdbwf_pyrule.cdb_object_id or
        cdbwf_pyrule.cdb_pyrule (with the appropriate category) yet.
        """
        rules = sqlapi.RecordSet2(
            sql="SELECT DISTINCT {attr} "
                "FROM {table} "
                "WHERE {attr} > '' "
                "AND {attr} NOT IN ("
                "  SELECT cdb_pyrule "
                "  FROM cdbwf_pyrule "
                "  WHERE category='{category}'"

                "  UNION SELECT cdb_object_id "
                "  FROM cdbwf_pyrule "
                ")".format(
                    table=self.__table__,
                    attr=self.__attr__,
                    category=constraints.RULE_CATEGORY
                )
        )
        return set([x.rule_name for x in rules])

    def run(self):
        self.create_missing_wrappers()
        self.migrate_rule_names()
        Class.ByKeys(self.__table__).compile(force=True)


class MigrateFilterRules(MigrateRules):
    __category__ = "Briefcase filter"
    __table__ = "cdbwf_filter_parameter"
    __attr__ = "rule_name"

    def _get_missing_rules(self):
        """
        Returns set of rule names to be created as rule wrappers, e.g. those
        used in constraints that neither exist in cdbwf_pyrule.cdb_object_id or
        cdbwf_pyrule.cdb_pyrule (with the appropriate category) yet.
        """
        rules = sqlapi.RecordSet2(
            sql="SELECT DISTINCT {attr} "
                "FROM {table} "
                "WHERE {attr} > '' "
                "AND {attr} NOT IN ("
                "  SELECT cdb_pyrule "
                "  FROM cdbwf_pyrule "
                "  WHERE category='{category}'"

                "  UNION SELECT cdb_object_id "
                "  FROM cdbwf_pyrule "
                ")"
                "AND name NOT IN ("
                "  'failure_condition', "
                "  'success_condition'"
                ")".format(
                    table=self.__table__,
                    attr=self.__attr__,
                    category=constraints.RULE_CATEGORY
                )
        )
        return set([x.rule_name for x in rules])

    def run(self):
        self.create_missing_wrappers()
        self.migrate_rule_names()


class InitializeCurrentCycle(object):
    def run(self):
        rows = sqlapi.SQLupdate(
            "cdbwf_process SET current_cycle=0 WHERE current_cycle IS NULL"
        )
        protocol.logMessage(
            "initialized cdbwf_process.current_cycle for {} workflows".format(
                rows
            )
        )


pre = []
post = [
    MigrateConstraintRules, MigrateFilterRules,
    InitializeCurrentCycle,
]
