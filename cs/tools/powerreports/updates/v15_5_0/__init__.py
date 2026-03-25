#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Update Tasks for cs.tools.powerreports 15.5.0
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from pkg_resources import DistributionNotFound

from cdb import ddl, sqlapi
from cdb.comparch import content, modules
from cdb.comparch.updutils import TranslationCleaner


class AdjustReportActionAndFormat(object):
    """
    Change the default of the existing Report format based on on previous setting
    """

    def run(self):
        table = ddl.Table("cdbxml_report")
        if (
            table.hasColumn("cdbxml_rep_exec_type")
            and table.hasColumn("cdbxml_report_action")
            and table.hasColumn("cdbxml_report_format")
        ):
            # Update all Server (synchron) format to Excel since other format is no longer supported
            sqlapi.SQLupdate(
                "cdbxml_report SET cdbxml_report_format='Excel',"
                " cdbxml_rep_exec_type=NULL WHERE"
                " cdbxml_rep_exec_type='Server (synchron)'"
            )  # noqa

            # Update all 'Server (asynchron)' to new report action('cdbxml_report_email')
            sqlapi.SQLupdate(
                "cdbxml_report SET cdbxml_report_action='cdbxml_report_email',"
                " cdbxml_rep_exec_type=NULL WHERE"
                " cdbxml_rep_exec_type='Server (asynchron)'"
            )  # noqa


class DeleteReportServer(object):
    """
    Delete ReportServer which is no longer available
    """

    def run(self):
        from cdb.platform.uberserver import Services

        for svc in Services.KeywordQuery(
            svcname="cs.tools.powerreports.powerreports_server.PowerReportsServer"
        ):
            svc.Delete()


class ChangeDefaultToFileClient(object):
    """
    Change the default Client of PowerReports to File Client
    """

    def run(self):
        # FILE_CLIENT = "true" || WSD = "false"
        sqlapi.SQLupdate("cdb_prop SET value = 'true' WHERE attr = 'prfc'")


class UpdateReportUUID(object):
    """
    Update cdb_object_id in cdbxml_report from standard reports
    """

    def run(self):
        rset = sqlapi.RecordSet2("cdbxml_report", addtl="order by cdb_module_id")
        curr_module_id = None
        curr_mc = None
        for r in rset:
            if r.cdb_module_id != curr_module_id:
                m = modules.Module.ByKeys(r.cdb_module_id)
                if m.isModifiable():
                    # skip customer modules
                    continue
                curr_module = m
                curr_module_id = curr_module.module_id
                try:
                    curr_mc = modules.ModuleContent(
                        curr_module_id,
                        curr_module.std_conf_exp_dir,
                        content.ModuleContentFilter(["cdbxml_report"]),
                    )
                except DistributionNotFound:
                    # Package is removed from file system but not not already synced at this point of time
                    # and still exists in the database for this reason
                    continue

            # find report by primary keys in module content
            mc_item = curr_mc.findItem("cdbxml_report", name=r.name, title=r.title)

            if mc_item:
                cdb_object_id = mc_item.getAttrs().get("cdb_object_id", None)
                # only update cdb_object_id from standard reports in DB
                if cdb_object_id:
                    r.update(cdb_object_id=cdb_object_id)


class RemoveLanguages(object):
    """
    Removes languages 'tr' and 'zh'.
    """

    def run(self):
        TranslationCleaner("cs.tools.powerreports", ["zh", "tr"])


class UpdateRoleAssignment(object):
    """
    Update role assignment for Administrator: PowerReports
    """

    def run(self):
        m = modules.Module.ByKeys("cs.tools.powerreports")
        content_filter = content.ModuleContentFilter(["cdb_global_subj"])
        mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

        for mc_item in mc.getModuleContentItems():
            if mc_item.getAttr("role_id") == "Administrator: PowerReports":
                try:
                    mc_item.insertIntoDB()
                except Exception:  # pylint: disable=W0703 # nosec
                    pass


post = [
    DeleteReportServer,
    ChangeDefaultToFileClient,
    RemoveLanguages,
    UpdateReportUUID,
    AdjustReportActionAndFormat,
    UpdateRoleAssignment,
]
