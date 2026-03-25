#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import json
import mock
import os
from cdb import constants, rte
from cdb import sqlapi
from cdb import testcase
from cdb import util
from cdb.elink.wsgi import ScriptRequest
from cdb.elink import setCurrentRequest
from cdb.objects import operations
from cdb.objects.org import Person

from cs.workflow.briefcases import FolderContent
from cs.workflow.designer import json_data
from cs.workflow.designer import WorkflowDesigner
from cs.workflow.designer.pages import AppData
from cs.workflow.forms import Form
from cs.workflow.processes import Process
from cs.workflowtest.cdbwf_task_extension import SimpleTaskExtension

TESTDATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "json_data"
)


def setup_module():
    testcase.run_level_setup()


def _get_page():
    page = AppData()
    page.application = WorkflowDesigner()
    setCurrentRequest(ScriptRequest(
        {
            "wsgi.url_scheme": "http",
            "HTTP_HOST": "localhost",
            "SERVER_PORT": "80",
            "REQUEST_METHOD": "GET",
            "QUERY_STRING": "",
        },
        None,
        None
    ))
    return page


def _get_testdata(filename):
    filepath = os.path.join(TESTDATA_PATH, filename)
    with open(filepath, "r", encoding= "utf-8") as testfile:
        result = json.loads(
            testfile.read().replace("http://www.example.org", rte.environ.get(constants.kEnvWWWServiceURL, u""))
        )
    return result


def sort_briefcases(data):
    """
    sort briefcases to match exported sidebar.json
    (key order of dicts is unstable in Python 3)
    """
    data["briefcases"] = {
        b.briefcase_id: b
        for b in sorted(
            data["briefcases"].values(),
            key=lambda x: x.briefcase_id,
        )
    }


class JSONDataTestCase(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(JSONDataTestCase, cls).setUpClass()
        cls.page = _get_page()
        cls.kwargs = {
            x: x.upper() for x in [
                "modify",
                "schemaEditable",
                "responsible",
                "deadline",
                "cdb_status_txt",
            ]
        }
        cls.kwargs.update({"readonly": False})
        cls.process_id = "JSON_TEST"
        cls.cdb_object_id = "e09e9d21-c86a-11e8-a1c6-5cc5d4123f3b"
        cls.process = Process.ByKeys(cls.process_id)

        contents = {
            0: Person.ByKeys("wftest_bystander"),
            146: cls.process,
            147: Form.KeywordQuery(cdb_object_id=cls.cdb_object_id)[0],
        }

        cls.data = [
            SimpleTaskExtension.Create(
                cdb_process_id=cls.process_id,
                task_id="T00003989",
                example_text="EXT",
            )
        ]
        for briefcase in cls.process.AllBriefcases:
            content = contents.get(briefcase.briefcase_id)
            if content:
                cls.data.append(FolderContent.Create(
                    cdb_folder_id=briefcase.cdb_object_id,
                    cdb_content_id=content.cdb_object_id,
                ))

        cls.task = cls.process.AllTasks.KeywordQuery(title="1.1")[0]
        cls.extended = cls.process.AllTasks.KeywordQuery(title="Extension")[0]
        cls.extended.Update(cdb_extension_class="cs_workflowtest_task_extension")
        cls.systask = cls.process.AllTasks.KeywordQuery(title="Information")[0]
        cls.group = cls.process.TaskGroups[0]
        cls.completion = cls.process.AllTaskGroups.KeywordQuery(
            cdb_classname="cdbwf_aggregate_proc_completion"
        )[0]
        cls.settings = util.PersSettings()
        json_data.check_access_proactively_enabled.cache_clear()

    @classmethod
    def tearDownClass(cls):
        super(JSONDataTestCase, cls).tearDownClass()
        cls.extended.Update(cdb_extension_class="")
        for obj in getattr(cls, "data", []):
            obj.Delete()

    def assertJSONEqual(self, result, expected):
        self.maxDiff = None
        result_u = str(
            json.dumps(result, sort_keys=True, indent=4)
        )
        expected_u = str(
            json.dumps(expected, sort_keys=True, indent=4)
        )
        self.assertEqual(
            result_u,
            expected_u,
        )

    def _set_check_access(self, value):
        self.settings.setValue(
            "cs.workflow.designer",
            "check_access_proactively",
            value,
        )

    def test_check_access_proactively_enabled(self):
        self.assertEqual(json_data.check_access_proactively_enabled(), True)
        self._set_check_access("0")
        self.assertEqual(json_data.check_access_proactively_enabled(), True)
        json_data.check_access_proactively_enabled.cache_clear()
        self.assertEqual(json_data.check_access_proactively_enabled(), False)

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_cached_briefcase_contents(self, is_csweb):
        briefcase_oid = "42507da1-c86a-11e8-b50b-5cc5d4123f3b"
        self.assertJSONEqual(
            json_data.get_cached_briefcase_contents(self.page, briefcase_oid),
            _get_testdata("briefcase_contents.json")
        )
        is_csweb.assert_not_called()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_load_process_data(self, is_csweb):
        result = json_data.load_process_data(self.page, self.process_id)

        def _obj2oid(obj_dict):
            return {
                k: [x.cdb_object_id for x in v]
                for k, v in obj_dict.items()
            }

        self.assertEqual(
            result["briefcase_contents"],
            _get_testdata("process_briefcase_contents.json")
        )
        is_csweb.assert_has_calls([mock.call()] * 3)
        self.assertEqual(
            _obj2oid(result["briefcase_links"]),
            {
                u'': [u'4257f7ae-c86a-11e8-b23f-5cc5d4123f3b'],
                u'T00003984': [u'e3e8e621-c86a-11e8-8868-5cc5d4123f3b'],
                u'T00003987': [
                    u'72565833-c86a-11e8-8978-5cc5d4123f3b',
                    u'e67a8d81-c86a-11e8-a450-5cc5d4123f3b',
                ],
                u'T00003986': [u'e0a294c0-c86a-11e8-9bfc-5cc5d4123f3b'],
            }
        )
        self.assertEqual(
            {k: v.cdb_object_id for k, v in result["briefcases"].items()},
            {
                0: "4254ea6e-c86a-11e8-8bca-5cc5d4123f3b",
                146: "6ce9a462-c86a-11e8-9e38-5cc5d4123f3b",
                147: "e0a0e70f-c86a-11e8-a02e-5cc5d4123f3b",
            }
        )
        task_ids = result["components"].task_id

        self.assertEqual(
            set(task_ids),
            set([
                "T00003984",
                "T00003985",
                "T00003987",
                "T00003988",
                "T00003986",
                "T00003989",
                "T00003983",
            ])
        )
        # task_ids are ordered by ascending position
        # completion task's position is NULL -> it is sorted last by Oracle
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            index = -1
        else:
            index = 0
        self.assertEqual(
            task_ids[index],
            "T00003983"
        )
        self.assertEqual(
            _obj2oid(result["forms"]),
            {}
        )
        self.assertEqual(
            _obj2oid(result["constraints"]),
            {"T00003983": ["5e6de8b2-c86a-11e8-b71d-5cc5d4123f3b"]}
        )
        self.assertEqual(
            result["process"].cdb_object_id,
            "42507da1-c86a-11e8-b50b-5cc5d4123f3b"
        )

    def test_get_process_structure(self):
        self.assertJSONEqual(
            json_data.get_process_structure(
                self.page,
                json_data.load_process_data(self.page, self.process_id)
            ),
            _get_testdata("process_structure.json")
        )

    def test_get_graph_data(self):
        self.assertJSONEqual(
            json_data.get_graph_data(
                self.page,
                json_data.load_process_data(self.page, self.process_id)
            ),
            _get_testdata("graph_data.json")
        )

    def test_clean_text(self):
        self.assertEqual(json_data.clean_text(None), "")
        for value in ["0", 0, True, False]:
            self.assertEqual(json_data.clean_text(value), value)

    def test_make_node(self):
        self.assertEqual(
            json_data.make_node(self.page, {"x": "component"}, foo="bar"),
            {
                "iface": "cs-workflow-node",
                "foo": "bar",
                "task_id": "process-end",
                "task": {
                    "x": "component"
                }
            }
        )

    def test_get_constraints(self):
        with self.assertRaises(AttributeError):
            json_data.get_constraints(self.page, self.process)

        self.assertJSONEqual(
            json_data.get_constraints(self.page, self.completion),
            _get_testdata("constraints.json")
        )

    def test_get_constraint_data(self):
        constraint = self.process.AllConstraints[0]
        self.assertJSONEqual(
            json_data.get_constraint_data(self.page, constraint),
            _get_testdata("constraint.json")
        )

    def test_get_component_data(self):
        self.assertEqual(
            json_data.get_component_data(self.page, None),
            None
        )
        self.assertJSONEqual(
            json_data.get_component_data(self.page, self.process),
            _get_testdata("graph_data.json")
        )
        self.assertJSONEqual(
            json_data.get_component_data(self.page, self.task),
            _get_testdata("task_data.json")
        )
        self.assertJSONEqual(
            json_data.get_component_data(self.page, self.group),
            _get_testdata("parallel_data.json")
        )
        self.assertJSONEqual(
            json_data.get_component_data(self.page, self.completion),
            _get_testdata("completion_data.json")
        )

    def test_get_loop_task_data(self):
        from cs.workflow.briefcases import BriefcaseLink
        from cs.workflow.constraints import Constraint
        from cs.workflow.tasks import RunLoopSystemTask
        loop_task = operations.operation(
            constants.kOperationNew,
            RunLoopSystemTask,
            operations.form_input(
                RunLoopSystemTask,
                cdb_process_id=self.process.cdb_process_id,
                position=99,
                parent_id="",
                title="Loop Task",
                task_definition_id="2df381c0-1416-11e9-823e-605718ab0986",
            )
        )
        loop_task.Update(
            cdb_object_id="LOOP_OID",
            task_id="LOOP",
        )
        BriefcaseLink.Create(
            cdb_process_id=loop_task.cdb_process_id,
            task_id=loop_task.task_id,
            briefcase_id=146,
            iotype=0,
            extends_rights=0,
        )
        constraint = Constraint.Create(
            cdb_process_id=loop_task.cdb_process_id,
            task_id=loop_task.task_id,
            rule_name="03d8ab8f-22e4-11e9-97e9-68f7284ff046",
            invert_rule=0,
        )
        constraint.Update(cdb_object_id="CONSTRAINT_OID")

        loop_task.create_first_cycle()
        loop_task.CurrentCycle.Update(cdb_process_id="CYCLE")

        self.assertJSONEqual(
            json_data.get_component_data(self.page, loop_task),
            _get_testdata("loop_task_data.json")
        )

    def test_get_responsible_info(self):
        for task in self.process.AllTasks:
            self.assertJSONEqual(
                json_data.get_responsible_info(self.page, task),
                _get_testdata("responsible_info_{}.json".format(task.task_id))
            )

    def test_get_description(self):
        self.assertJSONEqual(
            json_data.get_description(self.page, self.process),
            _get_testdata("process_description.json")
        )
        self.assertJSONEqual(
            json_data.get_description(self.page, self.task),
            _get_testdata("task_description.json")
        )

    def test_get_task_info(self):
        self.assertJSONEqual(
            json_data.get_task_info(self.page, self.task, **self.kwargs),
            _get_testdata("task_info.json")
        )
        self.assertJSONEqual(
            json_data.get_task_info(self.page, self.systask, **self.kwargs),
            _get_testdata("systask_info.json")
        )

    def test_get_task_fields(self):
        self.assertJSONEqual(
            json_data.get_task_fields(self.page, self.task, **self.kwargs),
            _get_testdata("task_fields.json")
        )
        self.assertJSONEqual(
            json_data.get_task_fields(self.page, self.systask, **self.kwargs),
            _get_testdata("systask_fields.json")
        )

    def test_get_parameters(self):
        self.assertEqual(json_data.get_parameters(self.page, self.task), None)
        self.assertJSONEqual(
            json_data.get_parameters(self.page, self.systask),
            _get_testdata("parameters.json")
        )

    def test_get_task_extension(self):
        self.assertJSONEqual(
            json_data.get_task_extension(self.page, self.extended),
            _get_testdata("task_extension.json")
        )

    def test_get_task_data(self):
        self.assertJSONEqual(
            json_data.get_task_data(self.page, self.task, None),
            _get_testdata("task_data.json")
        )
        self.assertJSONEqual(
            json_data.get_task_data(self.page, self.systask, None),
            _get_testdata("systask_data.json")
        )

    def test_get_parallel_data(self):
        self.assertJSONEqual(
            json_data.get_parallel_data(self.page, self.group, None),
            _get_testdata("parallel_data.json")
        )

    def test_get_sequential_data(self):
        self.skipTest("tbd")

    def test_get_completion_data(self):
        self.assertJSONEqual(
            json_data.get_completion_data(self.page, self.completion, None),
            _get_testdata("completion_data.json")
        )

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_briefcase_contents(self, is_csweb):
        self.assertJSONEqual(
            json_data.get_briefcase_contents(self.page, self.process),
            _get_testdata("briefcase_contents.json")
        )
        is_csweb.assert_has_calls([mock.call()] * 2)

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_contents_for_briefcase(self, is_csweb):
        briefcase = self.process.Briefcases[0]
        self.assertJSONEqual(
            json_data.get_contents_for_briefcase(self.page, briefcase, None),
            _get_testdata("contents_for_briefcase.json")
        )
        is_csweb.assert_not_called()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_briefcase_content_operations_web(self, is_csweb):
        self.assertJSONEqual(
            json_data.get_briefcase_content_operations(self.page, self.task),
            _get_testdata("briefcase_content_operations_web.json")
        )
        is_csweb.assert_called_once_with()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=False)
    def test_get_briefcase_content_operations_win(self, is_csweb):
        self.assertJSONEqual(
            json_data.get_briefcase_content_operations(self.page, self.task),
            _get_testdata("briefcase_content_operations_win.json")
        )
        is_csweb.assert_called_once_with()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_global_briefcase(self, is_csweb):
        link = self.process.BriefcaseLinks[0]
        self.assertJSONEqual(
            json_data.get_global_briefcase(self.page, link),
            _get_testdata("global_briefcase.json")
        )
        is_csweb.assert_not_called()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_global_briefcases(self, is_csweb):
        self.assertJSONEqual(
            json_data.get_global_briefcases(self.page, self.process),
            _get_testdata("global_briefcases.json")
        )
        is_csweb.assert_not_called()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_local_briefcase(self, is_csweb):
        briefcase = self.task.Briefcases[0]
        self.assertJSONEqual(
            json_data.get_local_briefcase(self.page, briefcase),
            _get_testdata("local_briefcase.json")
        )
        is_csweb.assert_not_called()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_local_briefcases(self, is_csweb):
        self.assertJSONEqual(
            json_data.get_local_briefcases(self.page, self.process),
            _get_testdata("local_briefcases.json")
        )
        is_csweb.assert_not_called()

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_sidebar(self, is_csweb):
        data = json_data.load_process_data(self.page, self.process_id)
        sort_briefcases(data)
        self.assertJSONEqual(
            json_data.get_sidebar(self.page, data),
            _get_testdata("sidebar.json")
        )
        is_csweb.assert_has_calls([mock.call()] * 3)

    @mock.patch.object(json_data.misc, "is_csweb", return_value=True)
    def test_get_briefcases(self, is_csweb):
        self.assertJSONEqual(
            json_data.get_briefcases(self.page, self.process),
            _get_testdata("briefcases.json")
        )
        is_csweb.assert_not_called()

    def test_get_task_forms(self):
        self.assertJSONEqual(
            json_data.get_task_forms(self.page, self.task),
            _get_testdata("task_forms.json")
        )

    def test_get_briefcase_links(self):
        self.assertJSONEqual(
            json_data.get_briefcase_links(self.page, self.task),
            _get_testdata("briefcase_links.json")
        )

    def test_get_briefcase_link(self):
        link = self.task.BriefcaseLinks[0]
        self.assertJSONEqual(
            json_data.get_briefcase_link(self.page, link),
            _get_testdata("briefcase_link.json")
        )

    def test_get_project_data(self):
        self.assertJSONEqual(
            json_data.get_project_data(self.page, self.process),
            _get_testdata("project_data.json")
        )

    def test_get_app_data(self):
        load_process_data = json_data.load_process_data

        def _sorted_process_data(page, process_id):
            data = load_process_data(page, process_id)
            sort_briefcases(data)
            return data

        with mock.patch.object(
            json_data,
            "load_process_data",
            side_effect=_sorted_process_data
        ):
            self.assertJSONEqual(
                json_data.get_app_data(self.page, self.process_id),
                _get_testdata("app_data.json")
            )

    def test_make_new_task_component(self):
        self.assertEqual(
            json_data.make_new_task_component(self.page, self.process),
            {
                "nonselectable": 1,
                "iface": "cs-workflow-node",
                "task_id": "add-task",
                "task": {
                    "iface": "cs-workflow-new-task"
                }
            }
        )

    def test_make_process_end(self):
        self.assertEqual(
            json_data.make_process_end(self.page, self.process),
            {
                "nonselectable": 1,
                "iface": "cs-workflow-node",
                "task_id": "process-end",
                "task": {
                    "iface": "cs-workflow-process-end",
                    "followedByCompletion": "followed-by-completion",
                    "statusIcon": "/static/powerscript/cs.workflow.designer/cis_ok-circle_gray.svg",
                    "statusStyle": "status-none"
                }
            }
        )
