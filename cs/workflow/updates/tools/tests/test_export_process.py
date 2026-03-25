#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from functools import reduce
from cdb import cdbuuid
from cdb import imex
from cdb import sqlapi
from cdb import testcase
from cs.workflow.processes import Process
from cs.workflow.tasks import RunLoopSystemTask
from cs.workflow.updates.tools import export_process


def setup_module():
    testcase.run_level_setup()


class MockCustomUpdate(object):
    def __init__(self, lines):
        self.lines = lines
        self.fname = u"test_export_tool_{}.exp".format(
            cdbuuid.create_uuid()
        )

    def run(self):
        self.export_lines()
        self.delete_lines()
        self.import_file()

    def export_lines(self):
        imex.export(
            ignore_errors=False,
            control_file=None,
            control_lines=self.lines,
            output_file=self.fname,
        )

    def delete_lines(self):
        def _delete(line):
            line = line.lstrip()
            if line[0] != '#':
                sqlapi.SQLdelete(line[1:].lstrip())
        for line in self.lines:
            _delete(line)

    def import_file(self):
        for row in imex.ExpFile(self.fname, charset="utf-8"):
            row.insert()

def create_process(process_id, **kwargs):
    return Process.Create(
        status=0,
        cdb_process_id=process_id, title=process_id, **kwargs
    )

def create_system_task(process_id, task_id):
    return RunLoopSystemTask.Create(
        status=0,
        cdb_process_id=process_id, task_id=task_id,
        task_definition_id="2df381c0-1416-11e9-823e-605718ab0986"
    )

def create_cycle_data():
    top = create_process("TOP")
    top_task = create_system_task("TOP", "TOP_T")
    mid = create_process("MID", parent_task_object_id=top_task.cdb_object_id)
    mid_task = create_system_task("MID", "MID_T")
    last = create_process("LAST", parent_task_object_id=mid_task.cdb_object_id)
    create_system_task("LAST", "LAST_T")
    return top, mid, last

def get_expected(process_id, cdb_object_id):
    expected = [
        "* FROM cdbwf_process_pyrule_assign WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbfolder_content WHERE cdb_folder_id IN "
        "(SELECT cdb_object_id FROM cdbwf_briefcase WHERE cdb_process_id='{}')".format(process_id),
        "* FROM cdbwf_briefcase WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_briefcase_link WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_form_template WHERE cdb_object_id IN "
        "( SELECT form_template_id FROM cdbwf_form WHERE cdb_process_id='{}')".format(process_id),
        "* FROM cdbwf_form WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_form_contents_txt WHERE cdb_object_id='{}'".format(cdb_object_id),
        "* FROM cdbwf_constraint WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_filter_parameter WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_info_message WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_process WHERE cdb_process_id='{}'".format(process_id),
        "* FROM cdbwf_task WHERE cdb_process_id='{}'".format(process_id),
    ]
    return expected


class TestExportTool(testcase.RollbackTestCase):
    def test_export_cycles(self):
        data = create_cycle_data()
        expected = reduce(
            lambda x, y: x + y,
            [get_expected(d.cdb_process_id, d.cdb_object_id) for d in reversed(data)]
        )
        result = list(
            export_process.get_workflow_export_control("TOP")
        )
        self.maxDiff = None
        # compare lists as order is critical
        self.assertEqual(result, expected)

    def test_export_ACCESS_TEST(self):
        result = list(
            export_process.get_workflow_export_control("ACCESS_TEST")
        )
        expected = get_expected('ACCESS_TEST', '4765c691-b7eb-11e8-a2d5-5cc5d4123f3b')
        self.maxDiff = None
        # compare lists as order is critical
        self.assertEqual(result, expected)

    def test_custom_update(self):
        lines = list(
            export_process.get_workflow_export_control("ACCESS_TEST")
        )
        custom_update = MockCustomUpdate(lines)
        # just make sure no DB errors are raised
        custom_update.run()
