#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Test Module __init__

This is the documentation for the tests.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import imp
import logging
import os
import re
import unittest

from cdb import acs
from cdb import cdbuuid
from cdb import constants
from cdb import testcase

from cdb.objects import cdb_file
from cdb.objects import operations
from cdb.objects.pdd import Sandbox

from cdb.objects.cdb_filetype import CDB_FileType


def import_common(package):
    from cdb.comparch.packages import get_package_dir
    path = os.path.join(
        get_package_dir(package), "tests", "accepttests", "steps")
    return imp.load_source(
        package + ".common_steps", os.path.join(path, "common_steps.py"))

common = import_common("cs.threed")


class DisableFileTypeGenOnlyCad(object):
    """
    This class is needed because of E056251. It prevents files from being
    deleted if the ft_genonlycad flag is set to 1
    """
    def __init__(self):
        self.file_types = CDB_FileType.KeywordQuery(ft_genonlycad=1)

    def __enter__(self):
        self.file_types.Update(ft_genonlycad=0)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file_types.Update(ft_genonlycad=1)


class ACSJobHandler(logging.Handler):
    """
    A handler class which extracts logging records coming from
    cdb.acs.acstools._DummyJob.

    Because _DummyJob ist too dumb and does not return a @#%&*! log!
    """

    def __init__(self):
        """
        Initialize the handler.

        If stream is not specified, sys.stderr is used.
        """
        super(ACSJobHandler, self).__init__()
        self.messages = []
        self.exp = re.compile("^  job.log : (?P<message>.*)$", re.DOTALL)

    def emit(self, record):
        """
        Emit a record.

        It filters all the messages of the form "  job.log : ..." and
        saves them to a private buffer.

        The messages can be accessed using the methods get_logs() and get_current_log()
        """
        try:
            msg = str(self.format(record))
            match = self.exp.match(msg)

            if match:
                self.messages.append(match.group("message"))
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def get_logs(self):
        return self.messages

    def get_current_log(self):
        return "\n".join(self.messages)


class HoopsTestCase(unittest.TestCase):
    "Unit tests for the method cs.threed.hoops.converter.convert_documents"

    def setUp(self):
        super(HoopsTestCase, self).setUp()
        self.to_delete = []

    def tearDown(self):
        super(HoopsTestCase, self).tearDown()
        with DisableFileTypeGenOnlyCad():
            for obj in self.to_delete:
                operations.operation(
                    constants.kOperationDelete,
                    obj
                )

    def create_documents(self, with_duplicate=False):
        self.main_doc = common.generateCADDocument(
            common.generateItem()
        )

        self.create_file(
            self.main_doc, "sw_cm_assembly.sldasm", "SolidWorks:asm",
            occurrences=["SolidWorks-part.sldprt", "sw_cm_part.sldprt"]
        )
        self.create_file(self.main_doc, "SolidWorks-part.sldprt", "SolidWorks:part", primary=False)

        self.subdoc1 = common.generateCADDocument(common.generateItem())
        self.create_link(self.main_doc, self.subdoc1)
        self.create_file(self.subdoc1, "sw_cm_part.sldprt", "SolidWorks:part", primary=False)

        if with_duplicate:
            self.create_file(
                self.subdoc1, "SolidWorks-part.sldprt", "SolidWorks:part", primary=False)

        self.to_delete.append(self.main_doc)
        self.to_delete.append(self.subdoc1)

    def create_file(self, doc, filename, filetype, occurrences=None, primary=True):
        if occurrences is None:
            occurrences = []

        filepath = os.path.join(common.files_dir, filename)
        fobj = common.generateFile(
            doc, filepath, filetype,
            auto_disable_genonlycad=True,
            primary=primary
        )
        self.create_appinfo(doc, fobj, occurrences)

    def create_appinfo(self, doc, fobj, occurrences):
        filename = fobj.cdbf_name

        xml_occurrences = [
            """
                <occurrence id="{target}.1" bom-relevant="yes" name="{target}.1" suppressed="no">
                    <cadreference path="{target}"/>
                    <tmatrix>
                        <entry id="1" value="1"/>
                        <entry id="10" value="0"/>
                        <entry id="11" value="1"/>
                        <entry id="12" value="0"/>
                        <entry id="13" value="0"/>
                        <entry id="14" value="0"/>
                        <entry id="15" value="0"/>
                        <entry id="16" value="1"/>
                        <entry id="2" value="0"/>
                        <entry id="3" value="0"/>
                        <entry id="4" value="0"/>
                        <entry id="5" value="0"/>
                        <entry id="6" value="1"/>
                        <entry id="7" value="0"/>
                        <entry id="8" value="0"/>
                        <entry id="9" value="0"/>
                    </tmatrix>
                </occurrence>
            """.format(target=occurrence)
            for occurrence in occurrences
        ]

        ws = Sandbox()
        p2 = ws.create(doc, filename + ".appinfo", "Appinfo")
        with open(p2, 'w') as fd:
            fd.write(
                """
                    <appinfo>
                        <occurrences>
                            %s
                        </occurrences>
                    </appinfo>
                """ % "\n".join(xml_occurrences)
            )
        ws.commit()
        doc.Reload()
        fobj.Reload()

        itemid = fobj.cdb_wspitem_id
        for fobj in doc.Files.KeywordQuery(cdbf_name=filename + ".appinfo"):
            fobj.cdb_belongsto = itemid

    def create_link(self, src, dest, create_reference=True):
        cdb_file.cdb_link_item.Create(
            cdbf_object_id=src.cdb_object_id,
            cdb_link=dest.cdb_object_id,
            cdb_wspitem_id=cdbuuid.create_uuid()
        )

        if create_reference is True:
            common.generateDocumentReference(src, dest, "test_ref")

    def get_jobs(self, fobjs):
        acsqueue = acs.getQueue()
        jobs = [
            job for job in acsqueue.query_jobs("src_object_id IN (%s)" % (
                ", ".join(["'%s'" % fobj.cdb_object_id for fobj in fobjs])
            ))
            if job.cdbmq_state in ["P", "W"]
        ]
        return jobs


def setup():
    from cdb import testcase
    from cdb import rte
    import cdbwrapc

    @testcase.without_error_logging
    def run_level_setup():
        rte.ensure_run_level(rte.USER_IMPERSONATED,
                             prog="nosetests",
                             user="cs_threed_service")
        # Necessary for nosetest - powerscript did it on its own
        cdbwrapc.init_corbaorb()

    run_level_setup()
