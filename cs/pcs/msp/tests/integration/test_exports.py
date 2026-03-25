#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import difflib
import os
import unittest

import pytest
from cdb import sqlapi, testcase
from cdb.dberrors import DBConstraintViolation
from lxml import etree  # nosec

from cs.pcs.msp.export_mapping import XmlExportConfiguration


def sort_tasks_by_uid(root):
    "makes xml root comparable to others"

    def _by_uid(task):
        uid = task.find("{http://schemas.microsoft.com/project}UID")
        return int(uid.text)

    tasks = root.find("{http://schemas.microsoft.com/project}Tasks")

    if len(tasks):
        tasks[:] = sorted(tasks, key=_by_uid)

    return root


def xml_equal(a, b):
    if a.tag != b.tag:
        return False

    if a.text != b.text:
        return False

    if a.tail != b.tail:
        return False

    if a.attrib != b.attrib:
        return False

    if len(a) != len(b):
        return False

    return all(xml_equal(ca, cb) for ca, cb in zip(a, b))


def assertXMLEqual(result, expected):
    parser = etree.XMLParser(encoding="utf-8")

    def _parse(xml_filepath):
        root = etree.parse(xml_filepath, parser).getroot()  # nosec
        return sort_tasks_by_uid(root)

    a = _parse(result)
    b = _parse(expected)

    assert xml_equal(a, b), "\n".join(
        difflib.context_diff(
            etree.tostring(a).decode("utf-8").splitlines(),
            etree.tostring(b).decode("utf-8").splitlines(),
            n=2,
        )
    )


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class MSPExport(testcase.RollbackTestCase):
    PROJECT_ID = "Ptest.msp.export"

    def _setup_testdata(self):
        # add "Regular Task" to workflow's "Attachment" briefcase
        record = sqlapi.Record(
            "cdbfolder_content",
            cdb_folder_id="7b282c8a-6a21-11eb-8d51-3ce1a147c610",
            cdb_content_id="2b19f4ca-6a22-11eb-a33b-3ce1a147c610",
            position=0,
        )
        try:
            record.insert()
        except DBConstraintViolation:
            pass  # already there

        self.resetSQLCount()

    @property
    def expected_path(self):
        return os.path.join(
            os.path.dirname(__file__),
            "test_data",
            f"{self.PROJECT_ID}.xml",
        )

    def test_export_project(self):
        """
        export a small project to XML demonstrating every exported feature

        exported XML is compared against pre-recorded test export,
        but project tasks are sorted by UID first to be independent
        of DB insertion order
        """
        self.skipTest("FIXME: diff exists with CE 15.8")
        self._setup_testdata()

        result_path = XmlExportConfiguration.generate_xml_from_project(self.PROJECT_ID)

        assertXMLEqual(result_path, self.expected_path)


if __name__ == "__main__":
    unittest.main()
