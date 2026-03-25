#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi, transactions
from cdb.comparch import protocol
from cdb.comparch.packages import Package


class PatchResourceOperations:
    """
    Patches the operation configuration of `cs.resources`
    to match umbrella release 15.5's new conventions.

    Only relevant for `cs.resources` <= `15.3.2`.
    """

    __updates__ = [
        (
            "ausgaben "
            "SET d = 'Gehe zu/Ressourcenplan', "
            "    uk = 'Go to/Resource Schedule' "
            "WHERE ausgabe_label = 'pcs_resourcechart' "
        ),
        (
            "ausgaben "
            "SET d = 'Unterstruktur anlegen ...', "
            "    uk = 'Create Substructure ...' "
            "WHERE ausgabe_label = 'cdbpcs_taskbreakdown' "
        ),
        (
            "cdb_op_names "
            "SET menugroup = 100000, "
            "    ordering = 3030 "
            "WHERE name = 'CDBPCS_CapaChart' "
        ),
        (
            "cdb_op_names "
            "SET menugroup = 35, "
            "    ordering = 10 "
            "WHERE name = 'cdbpcs_taskbreakdown_elink' "
        ),
        (
            "cdb_operations "
            "SET menugroup = NULL, "
            "    ordering = NULL, "
            "    label = NULL "
            "WHERE name = 'CDBPCS_CapaChart' "
            "AND classname IN ('cdbpcs_task', 'cdbpcs_project') "
        ),
        (
            "cdb_operations "
            "SET menugroup = NULL, "
            "    ordering = NULL, "
            "    label = NULL "
            "WHERE name = 'cdbpcs_taskbreakdown_elink' "
            "AND classname = 'cdbpcs_task' "
        ),
    ]

    def is_relevant(self):
        resources_pkg = Package.ByKeys(name="cs.resources")
        if resources_pkg:
            return True
        return False

    def run(self):
        if self.is_relevant():
            with transactions.Transaction():
                for update in self.__updates__:
                    sqlapi.SQLupdate(update)

            protocol.logMessage(
                "Updated cs.resources operation labels and position. "
                "Please check label translations "
                "for languages other than english and german."
            )


class PatchECOperations:
    """
    Patches the relationship configuration of `cs.ec`
    to match umbrella release 15.5's new conventions.

    Only relevant for `cs.ec` <= `15.4.0`.
    """

    __updates__ = [
        (
            "cdb_relships "
            "SET menugroup = NULL, "
            "    ordering = NULL, "
            "    show_in_menu = 0 "
            "WHERE name = 'cdbecm_project2cdbecm_ec' "
        ),
    ]

    def is_relevant(self):
        resources_pkg = Package.ByKeys(name="cs.ec")
        if resources_pkg:
            return True
        return False

    def run(self):
        if self.is_relevant():
            with transactions.Transaction():
                for update in self.__updates__:
                    sqlapi.SQLupdate(update)

            protocol.logMessage(
                "Removed Project to EC relationship from project context menu."
            )


pre = []
post = [PatchResourceOperations, PatchECOperations]
