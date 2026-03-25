#!/usr/bin/env python
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
report generator implementation
"""

import os
import shutil
import traceback

from cdb import cdbuuid, misc, mq, ue
from cdb.objects import ByID
from cdb.objects.pdd import Sandbox
from cs.tools.powerreports import SUPPORTED_FILETYPES, XMLReportTemplate
from cs.tools.powerreports.reportserver.report_queue_arg import set_job_args
from cs.tools.powerreports.reportserver.reportlib import log

__all__ = ["ReportGenerator"]


class ReportGenerator(object):
    def __init__(self, tmpl_cdb_object_id, cdb_file_cdb_object_id, **args):
        self.tmpl_cdb_object_id = tmpl_cdb_object_id
        self.cdb_file_cdb_object_id = cdb_file_cdb_object_id
        self.args = args
        self.sys_args = args.get("__sys_args__", None)
        if not self.sys_args:
            log("__sys_args__ missing in args. Cannot create report", 0, misc.kLogErr)

        self.sandbox_name = "report_generator__%s" % (cdbuuid.create_uuid())

        # create an explicit sandbox to control the removal
        self.sandbox = Sandbox(self.sandbox_name)
        self.workdir = self.sandbox._location
        log("ReportGenerator.__init__(): sandbox is '%s'" % self.workdir)
        self.xml_fname = None

    def __del__(self):
        log("ReportGenerator.__del__ (base)")
        self._cleanup()

    def _get_xml_source(self, args):
        source = None
        if "source" in args:
            source = ByID(args["source"])
        else:
            log("ReportGenerator: XML Source not found in args.", 0, misc.kLogErr)
        return source

    def _cleanup(self):
        if self.sandbox is not None:
            self.sandbox.clear()
            self.sandbox = None

    def _get_context_objects(self, args):
        objects = []
        if "objects" in args and args["objects"]:
            objects = [ByID(o) for o in args["objects"]]
        return objects

    def _export_xml_data(self):
        # Export data from xml source
        objects = self._get_context_objects(self.sys_args)
        xml_source_obj = self._get_xml_source(self.sys_args)
        if not xml_source_obj:
            log("source missing in sys_args. Cannot create report.", 0, misc.kLogErr)
            return
        log("ReportGenerator: START EXPORT")
        xml_fname = xml_source_obj.export_ex(
            objects,
            self.template_fname,
            self.tmpl_cdb_object_id,
            self.cdb_file_cdb_object_id,
            "0",
            **self.args
        )
        log("ReportGenerator: END EXPORT")
        return xml_fname

    def _checkout_template(self):
        tmpl = XMLReportTemplate.KeywordQuery(cdb_object_id=self.tmpl_cdb_object_id)
        if not tmpl:
            raise ue.Exception("powerreports_tmpl_not_found", self.tmpl_cdb_object_id)
        tmpl = tmpl[0]
        # skip non-Excel files (accidentally added to the report template object)
        xls_list = [
            f
            for f in tmpl.Files
            if os.path.splitext(f.cdbf_name)[1].lower() in SUPPORTED_FILETYPES
        ]
        cdbfile = ([f for f in xls_list if int(f.cdbf_primary) == 1] or xls_list)[0]
        if not cdbfile:
            raise ue.Exception("powerreports_tmpl_file_not_found")

        target_basename = self.sys_args.get("target", "report")
        template_fname = os.path.join(
            self.workdir,
            "%s%s" % (target_basename, os.path.splitext(cdbfile.cdbf_name)[1]),
        )
        try:
            cdbfile.checkout_file(template_fname)
        except Exception as ex:
            raise ue.Exception(
                "powerreports_tmpl_file_not_loaded", cdbfile.cdbf_name, str(ex)
            )
        log("ReportGenerator: Checked out report template: %s" % template_fname)

        return template_fname

    # extraction of report template and report data
    def _prepare_report(self):
        self.template_fname = self._checkout_template()
        self.xml_fname = self._export_xml_data()

    def _copy_results(self, dst_path, gen_ret):
        ret = gen_ret

        def _copy(src_fname, dst_path):
            dst_fname = os.path.join(dst_path, os.path.basename(src_fname))
            log("Copying '%s' to '%s'" % (src_fname, dst_fname))
            shutil.copyfile(src_fname, dst_fname)
            return dst_fname

        if dst_path:
            if not os.path.exists(dst_path):
                log("Destination path '%s' does not exist" % dst_path, 0, misc.kLogErr)
            else:
                report_format = self.sys_args["report_format"]
                if any(f in report_format for f in ["Excel", "E-Link"]):
                    ret["xls"] = _copy(gen_ret["xls"], dst_path)
                if any(f in report_format for f in ["PDF", "E-Link"]):
                    ret["pdf"] = _copy(gen_ret["pdf"], dst_path)
        return ret

    def create_report(self, target_path=None):
        ret = {"status": "", "xls": None, "pdf": None}
        try:
            log(
                "ReportGenerator.create_report(): workdir: '%s', target_path '%s'"
                % (self.workdir, target_path)
            )
            self._prepare_report()
            make_excel = "Excel" in self.sys_args["report_format"]
            make_pdf = "PDF" in self.sys_args["report_format"]
            custom_props = self.sys_args["custom_props"]
            # TAG: mkn
            from cs.tools.powerreports.xmlreportgenerator import ExcelReportGenerator

            excel_repgen = ExcelReportGenerator(
                self.template_fname, self.xml_fname, custom_props
            )
            gen_ret = excel_repgen.generate(make_pdf)
            ret["status"] = gen_ret["status"]

            # attach report files (if any)
            if ret["status"] == "OK":
                excel = gen_ret["xls"]
                pdf = gen_ret["pdf"]
                if excel and make_excel:
                    ret["xls"] = excel
                if pdf and make_pdf:
                    ret["pdf"] = pdf
                ret = self._copy_results(target_path, ret)
        except Exception as ex:  # pylint: disable=W0718,W0703
            if ret["status"] in ["", "OK"]:
                ret["status"] = "%s" % ex
            log("%s" % traceback.format_exc())
        finally:
            log("ReportGenerator.create_report(): result is '%s'" % (ret))
        return ret

    def dispatch_report_job(self):
        # set up mq job
        queue = mq.Queue("xsd_reports")
        job = queue.new(cdbf_object_id=self.tmpl_cdb_object_id)
        # write args to the database
        set_job_args(job.id(), self.args)
        job.start()
