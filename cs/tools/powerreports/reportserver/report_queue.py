#!/usr/bin/env python
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
import sys
import time

from cdb import ddl, mail, misc, mq
from cdb.fls import allocate_server_license
from cdb.objects import org
from cs.tools.powerreports.reportserver.report_generator import ReportGenerator
from cs.tools.powerreports.reportserver.report_queue_arg import (
    get_job_args,
    set_job_args,
)
from cs.tools.powerreports.reportserver.reportlib import getConfValue, log


class ReportJob(mq.Job):
    def __init__(self, id, queue):
        mq.Job.__init__(self, id, queue)
        allocate_server_license("POWERREPORTS_004")
        self._args = None

    @property
    def args(self):
        if not self._args:
            self._args = get_job_args(self.id())
        return self._args

    def run(self):
        self.sys_args = self.args.get("__sys_args__", None)
        if not self.sys_args:
            reason = "__sys_args__ missing in args. Cannot create report."
            log(reason, 0, misc.kLogErr)
            self.fail(5, reason)
            return
        self.persno = self.sys_args.get("persno", "")
        if not self.persno:
            reason = "persno missing in sys_args. Cannot create report."
            log(reason, 0, misc.kLogErr)
            self.fail(10, reason)
            return
        self.dispatch()
        # delete job arguments after dispatched successfully
        set_job_args(self.id())
        self.done()

    def send_mail(self, report_result, persno, mail_subject, mail_body):
        msg = mail.Message()
        msg.To(org.Person.ByKeys(persno).e_mail)
        msg.From(
            getConfValue("REPORT_QUEUE_SENDER_EMAIL_ADDRESS", "NoReply@SomeCompany.org")
        )
        msg.Organization(
            getConfValue("REPORT_QUEUE_SENDER_ORGANIZATION", "SomeCompany")
        )
        msg.Subject(mail_subject)
        if report_result["status"] == "OK":
            if report_result["xls"]:
                msg.attach(report_result["xls"])
            if report_result["pdf"]:
                msg.attach(report_result["pdf"])
            msg.body(mail_body)
            msg.send()
        else:
            txt = getConfValue(
                "REPORT_QUEUE_FAILURE_MESSAGE",
                "Report generation failed. "
                "Please contact your CONTACT Elements administrator.",
            )
            if getConfValue("REPORT_QUEUE_FAILURE_MESSAGE_APPEND_ERROR", 0):
                txt = "%s\n\n(%s)" % (txt, report_result["status"])
            msg.body(txt)
            msg.send()
            self.fail(20, "Report creation failed: %s" % report_result["status"])

    def dispatch(self):
        """This method is meant to be virtual"""
        from cdb.platform.gui import Message

        # Following example will send a mail with the generated files as
        # attachments. Settings for the mail service are read from the
        # "power_reports.conf" in the config folder. Example settings:
        # REPORT_QUEUE_SENDER_EMAIL_ADDRESS = "NoReply@SomeCompany.org"
        # REPORT_QUEUE_SENDER_ORGANIZATION  = "SomeCompany"
        # REPORT_QUEUE_FAILURE_MESSAGE  = "Report generation failed. Please contact your " \
        #                                 "CONTACT Elements administrator."
        start_time = time.time()
        repgen = ReportGenerator(self.cdbf_object_id, self.cdb_object_id, **self.args)
        # send results as mail
        self.send_mail(
            repgen.create_report(),
            self.persno,
            "%s Report: %s"
            % (
                Message.GetMessage("branding_product_name"),
                self.sys_args.get("target", ""),
            ),
            "[report generation time: %s]" % (time.time() - start_time),
        )


if __name__ == "__main__":
    theQueue = mq.Queue(
        "xsd_reports",
        ReportJob,
        fieldlist=[ddl.Char("cdbf_object_id", 40), ddl.Char("cdb_object_id", 40)],
    )

    log("Server process started")
    sys.exit(theQueue.cli(sys.argv))
