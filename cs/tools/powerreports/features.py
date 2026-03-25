# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module features

Handling the feature assignments of reports.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.comparch import modules

# Some imports
from cdb.platform import lic
from cdb.sig import connect

# Exported objects
__all__ = []


class FeatureIDReportAssignment(lic.FeatureIDAssignment):
    __classname__ = "cdb_lic_feature_assign_rep"
    __match__ = lic.FeatureIDAssignment.cdb_classname >= __classname__

    @classmethod
    def _create_from_report(cls, report):
        """
        Creates an entry from `report` that represents
        a cdbxml_report record or `cs.tools.powerreports.XMLReport`
        """
        cls.Create(report_name=report.name, cdb_module_id=report.cdb_module_id)

    @classmethod
    def remove_orphan_report_assignments(cls, module_id=""):
        """
        Removes license entries for reports that are
        no longer part of the installation.
        """
        from cdb import sqlapi
        from cdb.comparch import get_dev_namespace

        if module_id and not modules.Module.is_modifiable(module_id):
            raise RuntimeError(
                "Your development namespace is '%s'. "
                "The module '%s' belongs to the namespace '%s' that "
                "can't be modified."
                % (
                    get_dev_namespace(),
                    module_id,
                    modules.Module.get_dev_namespace(module_id),
                )
            )
        condition = "cdb_classname = 'cdb_lic_feature_assign_rep' AND cdb_module_id"
        if module_id:
            condition += " = '%s'" % (sqlapi.quote(module_id))
        else:
            condition += " LIKE '%s%%'" % (sqlapi.quote(get_dev_namespace()))
        condition += " AND NOT EXISTS (select 1 FROM cdbxml_report WHERE "
        condition += "cdb_lic_feature_assign.report_name = cdbxml_report.name)"
        sqlapi.SQLdelete("FROM cdb_lic_feature_assign WHERE %s" % (condition))

    @classmethod
    def generate_missing_report_assignments(cls, module_id=""):
        """
        Generates an entry for every report that belongs to
        the module `module_id` or for all reports of the
        customizing namespace if `module_id` is empty.
        This entry ist just a template -
        someone has to assign the correct feature and to sign
        the assignment.
        The function will raise a `RuntimeError` if `module_id`
        is not part of the actual customizing namespace.
        """
        from cdb import sqlapi, transactions
        from cdb.comparch import get_dev_namespace

        if module_id and not modules.Module.is_modifiable(module_id):
            raise RuntimeError(
                "Your development namespace is '%s'. "
                "The module '%s' belongs to the namespace '%s'"
                "that can't be modified."
                % (
                    get_dev_namespace(),
                    module_id,
                    modules.Module.get_dev_namespace(module_id),
                )
            )

        condition = "cdb_module_id"
        if module_id:
            condition += " = '%s'" % (sqlapi.quote(module_id))
        else:
            condition += " LIKE '%s%%'" % (sqlapi.quote(get_dev_namespace()))
        condition += " AND NOT EXISTS (select 1 FROM cdb_lic_feature_assign WHERE "
        condition += "cdb_lic_feature_assign.report_name = cdbxml_report.name AND "
        condition += (
            "cdb_lic_feature_assign.cdb_classname = 'cdb_lic_feature_assign_rep')"
        )
        reports = sqlapi.RecordSet2("cdbxml_report", condition=condition)

        with transactions.Transaction():
            for report in reports:
                cls._create_from_report(report)


@connect(modules.Module, "cdb_gen_lic_assign_feature", "now")
def generate_features(module, ctx):
    FeatureIDReportAssignment.remove_orphan_report_assignments(module.module_id)
    FeatureIDReportAssignment.generate_missing_report_assignments(module.module_id)
