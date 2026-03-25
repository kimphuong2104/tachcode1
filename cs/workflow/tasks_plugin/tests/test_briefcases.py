#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import cdbwrapc
import mock
from collections import OrderedDict
from cdb import testcase
from cs.platform.web.root.main import _get_dummy_request
from cs.workflow.processes import Process
from cs.workflow.systemtasks import InfoMessage
from cs.workflow.tasks import ExecutionTask
from cs.workflow.tasks_plugin import briefcases


def setup_module():
    testcase.run_level_setup()


class BriefcaseModel(testcase.RollbackTestCase):
    maxDiff = None

    @mock.patch.object(briefcases, "StatusInfo")
    @mock.patch.object(briefcases, "ByID")
    def test_get_view(self, ByID, StatusInfo):
        ByID.return_value = mock.MagicMock(
            CheckAccess=mock.MagicMock(return_value=True)
        )
        request = mock.MagicMock()
        request.view = mock.MagicMock(return_value={1: 2})
        StatusInfo.return_value = mock.MagicMock(
            getLabel=mock.MagicMock(return_value="Execution"),
            getCSSColor=mock.MagicMock(return_value="green")
        )

        obj = self._build_obj({'attr_status': 'status'})
        obj.status=50
        
        olc = mock.MagicMock(return_value="olc")
        obj.ToObjectHandle.return_value = mock.MagicMock(
            getOLC=olc
        )

        briefcaseModel = briefcases.BriefcasesModel("objId")

        self.assertEqual(
            briefcaseModel.get_view(obj, request, "app"),
            {1: 2, "status": {"status": 50, "color": "green", "label": "Execution"}}
        )

        ByID.assert_called_once_with("objId")
        StatusInfo.assert_called_once_with("olc", 50)
        ByID.return_value.CheckAccess.assert_called_once_with("read")

    def test_get_view_file(self):
        # SystemTask_Loop.png
        file_obj = briefcases.CDB_File.ByKeys("79875a61-149f-11e9-a3b0-605718ab0986")
        model = mock.Mock(spec=briefcases.BriefcasesModel)
        request = _get_dummy_request("http://BASE")
        app = briefcases.get_collection_app(request)
        result = briefcases.BriefcasesModel.get_view(model, file_obj, request, app)
        self.assertEqual(result, {
            '@id': 'http://BASE/api/v1/collection/system_task_definition/2df381c0-1416-11e9-823e-605718ab0986/files/79875a61-149f-11e9-a3b0-605718ab0986',
            '@type': 'http://BASE/api/v1/class/cdb_file',
            'cdb_object_id': '79875a61-149f-11e9-a3b0-605718ab0986',
            'system:description': 'SystemTask_Loop.png',
            'system:icon_link': '/resources/icons/byname/FileType_PNG?',
            'system:ui_link': 'http://BASE/api/v1/collection/system_task_definition/2df381c0-1416-11e9-823e-605718ab0986/files/79875a61-149f-11e9-a3b0-605718ab0986',
        })

    @mock.patch.object(briefcases, "get_collection_app", return_value="collection_app")
    @mock.patch.object(briefcases.BriefcasesModel, "get_view")
    @mock.patch.object(briefcases, "ByID")
    def test__get_briefcases(self, ByID, get_view, _):
        request = mock.MagicMock()
        request.view.side_effect = lambda b, app: {"@id": b.atId}

        get_view.side_effect = lambda x, _, __: {"cdb_object_id": x.cdb_object_id, "@id": x.atId}

        briefcase1 = mock.MagicMock(
            cdb_object_id=1,
            atId="b1",
            CheckAccess=mock.MagicMock(return_value=True),
            Content=[
                mock.MagicMock(
                    cdb_object_id="obj1", atId="info/project/P00001",
                    CheckAccess=mock.MagicMock(return_value=True)
                )
            ]
        )

        briefcase2 = mock.MagicMock(
            cdb_object_id=2,
            atId="b2",
            CheckAccess=mock.MagicMock(return_value=True),
            Content=[
                mock.MagicMock(
                    cdb_object_id="obj2", atId="info/task/T00001",
                    CheckAccess=mock.MagicMock(return_value=True)
                )
            ]
        )

        task_bc = [briefcase1, briefcase2]
        getBriefcases = mock.MagicMock()
        getBriefcases.side_effect = lambda x: task_bc if x == "edit" else []

        Process=mock.MagicMock()
        Process.getBriefcases.side_effect = lambda _: []

        ByID.return_value = mock.MagicMock(
            CheckAccess=mock.MagicMock(return_value=True),
            Process=Process,
            getBriefcases=getBriefcases
        )

        briefcaseModel = briefcases.BriefcasesModel("objId")

        returned_briefcases, objects = briefcaseModel._get_briefcases(request)

        expected = OrderedDict()
        expected[1] = {
                    "@id": "b1",
                    "references": ["info/project/P00001"]
                }
        expected[2] = {
                    "@id": "b2",
                    "references": ["info/task/T00001"]
                }

        self.assertEqual(
            returned_briefcases,
            expected
        )
        expected = [
                {'@id': 'info/project/P00001', 'cdb_object_id': 'obj1'},
                {'@id': 'info/task/T00001', 'cdb_object_id': 'obj2'},
                {"@id": "b1", "mode": "edit"},
                {"@id": "b2", "mode": "edit"},
            ]
        for item in expected:
            self.assertIn(item, list(objects))

    def _get_data(self, is_info):
        wf = Process.Create(cdb_process_id="Test_Briefcases", is_template=0, status=0)
        wf.make_attachments_briefcase()
        wf.AddAttachment("99504583-76e1-11de-a2d5-986f0c508d59")  # caddok
        task = ExecutionTask.Create(
            cdb_process_id=wf.cdb_process_id,
            task_id="Test_Briefcases",
        )
        info = InfoMessage.Create(
            cdb_process_id=wf.cdb_process_id,
            task_id=task.task_id,
        )

        uuid = info.cdb_object_id if is_info else task.cdb_object_id
        model = briefcases.BriefcasesModel(uuid)
        data = model.get_data(_get_dummy_request())
        expected =  ["briefcases", "objects"]
        for item in expected:
            self.assertIn(item, list(data.keys()))
        self.assertEqual(len(data["objects"]), 2)
        self.assertEqual(len(data["briefcases"]), 1)

        descriptions = {x["system:description"] for x in data["objects"]}
        self.assertEqual(descriptions, {
            str("Anhänge"),
            str(" Administrator  (caddok)"),
        })

    def test_get_data_task(self):
        self._get_data(False)

    def test_get_data_info_message(self):
        self._get_data(True)

    def _build_obj(self, wf_info):
        classDef = mock.MagicMock()
        classDef.get_workflow_info.return_value = wf_info
        obj = mock.MagicMock()
        obj.GetClassDef.return_value = classDef

        return obj

    def test__get_status_attr(self):
        briefcase = mock.MagicMock(spec=briefcases.BriefcasesModel)
        obj = self._build_obj({'attr_status': 'myStatusAttr'})

        self.assertEqual(
            briefcases.BriefcasesModel._get_status_attr(briefcase, obj),
            'myStatusAttr'
        )

    def test__get_status_attr_None(self):
        briefcase = mock.MagicMock(spec=briefcases.BriefcasesModel)
        obj = self._build_obj(None)

        self.assertEqual(
            briefcases.BriefcasesModel._get_status_attr(briefcase, obj),
            None
        )



class RestlinkModel(testcase.RollbackTestCase):

    @mock.patch.object(cdbwrapc, "createOperationFromCMSGUrl")
    @mock.patch.object(briefcases, "ByID")
    @mock.patch.object(briefcases, "get_restlink")
    def test_get_restlink(self, get_restlink, ByID, createOperationFromCMSGUrl):

        restlinkModel = briefcases.RestlinkModel()

        handle = mock.MagicMock()
        handle.getUUID.return_value = "Uuid"

        operation  = mock.MagicMock()
        operation.getObjectResult.return_value = handle

        createOperationFromCMSGUrl.return_value = operation
        ByID.side_effect = lambda x: x + "Obj"
        get_restlink.side_effect = lambda x: "/api/v1/collection/" + x

        self.assertEqual(
            restlinkModel.get_restlink("cmsg"),
            "/api/v1/collection/UuidObj"
        )
