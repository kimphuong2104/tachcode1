#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import os
from cdb import ddl
from cdb import testcase
from cs.workflow.updates.v15_4_3_8 import RemoveOldFields
from tempfile import gettempdir
import pathlib


def setup_module():
    testcase.run_level_setup()


class Test_update(testcase.RollbackTestCase):
    "integration test simulating update from <15.4.3 to 15.4.3 and removing old table fields"
    
    def setUp(self):
        super(Test_update, self).setUp()
        self.changes = [
            {
            "table":"cdbwf_form_contents_txt",
            "fields":["cdb_process_id","task_id","form_template_id"]
            },
            {
            "table":"cdbwf_form",
            "fields":["task_id"]
            }
        ]
        for change in self.changes:
            table = ddl.Table(change["table"])
            for field in change["fields"]:
                if not table.hasColumn(field):
                    table.addAttributes(ddl.Char(field,20))

        self.filePath = str(pathlib.Path(
            gettempdir(),
            "upd-v15.4.3.8-workflow-forms.exp")
        )
        try:
            os.unlink(self.filePath)
        except:
            pass


    def tearDown(self):
        super(Test_update, self).tearDown()
        for change in self.changes:
            table = ddl.Table(change["table"])
            for field in change["fields"]:
                if table.hasColumn(field):
                    table.dropAttributes(field)

    def test_RemoveOldFields(self):
        update = RemoveOldFields()
        update.run()

        errors = []
        passed = True

        for change in self.changes:
            table = ddl.Table(change["table"])
            for field in change["fields"]:
                if table.hasColumn(field):
                    passed = False
                    errors.append(
                        "Field '{0}' still in {1}".format(field,change["table"])
                    )

        fileContent = ""
        with open(self.filePath, "r") as myfile:
            fileContent = myfile.read()
        for change in self.changes:
            if not "T" + change["table"] in fileContent:
                passed = False
                errors.append("Table not in exported file")
        self.assertTrue(passed, ("\n").join(errors))
