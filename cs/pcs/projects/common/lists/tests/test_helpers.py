#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

from cdb import testcase
from cdb.platform import mom
from mock import MagicMock, Mock, patch

from cs.pcs.projects import Project
from cs.pcs.projects.common import lists
from cs.pcs.projects.common.lists.helpers import (
    _generateDisplayConfig,
    _generateListItems,
)


class TestListHelperFunctions(testcase.RollbackTestCase):
    @patch("cs.pcs.projects.common.lists.helpers.gui")
    @patch("cs.pcs.projects.common.lists.helpers.logging")
    def test__generateDisplayConfig_python_help_func_err(self, logging, gui):
        classname = "classname"
        component = Mock()
        # mock functions
        getDisplayTypeComponent = Mock(return_value=component)
        getDisplayTypeProperties = Mock(side_effect=Exception(Mock(), ""))
        configEntry = Mock(
            DisplayType=Mock(),
            layout_position="foo",
            getDisplayTypeComponent=getDisplayTypeComponent,
            getDisplayTypeProperties=getDisplayTypeProperties,
        )
        # setup input parameter
        listOfConfigEntries = [configEntry]

        with patch.object(
            lists.helpers,
            "LAYOUT_POSITIONS",
            {
                "foo": "bar",
            },
        ):
            _generateDisplayConfig(listOfConfigEntries, classname)

        gui.Message.GetMessage.assert_called_once()
        logging.exception.assert_called_once()

    def test__generateDisplayConfig(self):
        key = "key"
        name = "name"
        classname = "classname"
        fqpyname = "fqpyname"
        primary = "primaryText"
        newKey = "1:name_0"
        # Mock attributes
        configEntry = Mock()
        component = Mock()
        configEntry.DisplayType = Mock()
        configEntry.DisplayType.name = name
        configEntry.DisplayType.fqpyname = fqpyname
        configEntry.layout_position = primary
        # Mock functions
        pythonFunc = Mock()
        getDisplayTypeComponent = Mock(return_value=component)
        getDisplayTypeProperties = Mock()
        getDisplayTypeProperties.return_value = {key: pythonFunc}
        configEntry.getDisplayTypeComponent = getDisplayTypeComponent
        configEntry.getDisplayTypeProperties = getDisplayTypeProperties
        # setup input parameter
        listOfConfigEntries = [configEntry]
        # expected return values
        expectedDisplayConf = {
            "1": [{"comp": component, "props": {key: newKey}}],
            "2": [],
            "b": [],
            "a": [],
        }

        expectedDictAttrFunc = {
            newKey: {
                "function": pythonFunc,
                "function_name": fqpyname,
                "layout_position": primary,
                "display_type": name,
                "classname": classname,
            }
        }

        displayConf, dictAttrFunc, isError = _generateDisplayConfig(
            listOfConfigEntries, classname
        )
        self.assertDictEqual(displayConf, expectedDisplayConf)
        self.assertDictEqual(dictAttrFunc, expectedDictAttrFunc)
        assert not isError

    @patch("cs.pcs.projects.common.lists.helpers.gui")
    @patch("cs.pcs.projects.common.lists.helpers.logging")
    def test__generateListItems_python_func_err(self, logging, gui):
        objKey = "objKey"
        funcKey = "funcKey"
        # Mock request
        request = Mock()
        # Mock parameter
        displayId = Mock()
        objHandle = Mock()
        pythonFunc = Mock()
        pythonFunc.side_effect = Exception(Mock(), "")
        dictAttrFunc = {
            funcKey: {
                "function": pythonFunc,
                "function_name": "fqpyname",
                "layout_position": "primary",
                "display_type": "name",
                "classname": "classname",
            }
        }
        dictObjHandles = {objKey: objHandle}

        _generateListItems(displayId, dictAttrFunc, dictObjHandles, [objKey], request)
        pythonFunc.assert_called_with(objHandle)
        logging.exception.assert_called_once()
        gui.Message.GetMessage.assert_called_once()

    @patch.object(lists.helpers, "rest_key")
    def test_cached_rest_key(self, rest_key):
        # cache miss
        self.assertEqual(
            lists.helpers.cached_rest_key("foo"),
            rest_key.return_value,
        )
        # cache hit, so rest_key is not called again
        self.assertEqual(
            lists.helpers.cached_rest_key("foo"),
            rest_key.return_value,
        )
        rest_key.assert_called_once_with("foo")

    @patch.object(lists.helpers, "cached_rest_key", return_value="B")
    def test__get_ui_link_web(self, cached_rest_key):
        handle = MagicMock()
        handle.getClassDef.return_value.getRESTName.return_value = "A"
        self.assertEqual(
            lists.helpers._get_ui_link("req", handle),
            "/info/A/B",
        )
        cached_rest_key.assert_called_once_with(handle)

    @patch("cs.pcs.projects.common.lists.helpers.gui")
    @patch("cs.pcs.projects.common.lists.helpers.logging")
    def test__generateListItems_python_func_return_value_err(self, logging, gui):
        objKey = "objKey"
        funcKey = "funcKey"
        displayId = "displayId"
        # Mock request
        request = Mock()
        # Mock parameter
        objHandle = Mock()
        pythonFunc = Mock(return_value=Mock())
        dictAttrFunc = {
            funcKey: {
                "function": pythonFunc,
                "function_name": "fqpyname",
                "layout_position": "primary",
                "display_type": "name",
                "classname": "classname",
            }
        }
        dictObjHandles = {objKey: objHandle}
        with patch(
            "cs.pcs.projects.common.lists.helpers.json.dumps",
            side_effect=TypeError(Mock(), ""),
        ):
            _generateListItems(
                displayId, dictAttrFunc, dictObjHandles, [objKey], request
            )
        logging.exception.assert_called_once()
        gui.Message.GetMessage.assert_called_once()

    def test__generateListItems(self):
        funcKey = "funcKey"
        # Mock request
        request = Mock()
        # Mock parameter
        displayId = Mock()
        objectLink = Mock()
        # Since __getattr__ is not mockable (reserved magic function)
        # create a real ObjectHandle here with the attribute cdb_project_id
        # as the sortKey demands
        cdb_project_id = "dummyProjectId"
        clsname = "cdbpcs_project"
        dummyProject = Project.Create(
            cdb_project_id=cdb_project_id, ce_baseline_id="", cdb_object_id="P1"
        )
        sortedKeys = [dummyProject.cdb_object_id]
        dictObjHandles = mom.getObjectHandlesFromObjectIDs(
            [dummyProject.cdb_object_id], False, True
        )
        prop = Mock()
        # Mock function
        pythonFunc = Mock(return_value=prop)
        dictAttrFunc = {
            funcKey: {
                "function": pythonFunc,
                "function_name": "fqpyname",
                "layout_position": "primary",
                "display_type": "name",
                "classname": "classname",
            }
        }
        # Construct expected output
        expected_list = [
            {
                "attrs": {funcKey: prop, "system:ui_link": objectLink},
                "display_config": displayId,
                "contextObject": {
                    "system:classname": clsname,
                    "system:navigation_id": cdb_project_id,
                    "@type": f"/api/v1/class/{clsname}",
                    "@id": f"{request.application_url}/api/v1/collection/project/dummyProjectId",
                },
            }
        ]
        with patch("cs.pcs.projects.common.lists.helpers.json.dumps", new=lambda x: x):
            with patch(
                "cs.pcs.projects.common.lists.helpers._get_ui_link",
                return_value=objectLink,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.helpers.rest_key",
                    return_value=cdb_project_id,
                ):
                    list_of_items, isError = _generateListItems(
                        displayId, dictAttrFunc, dictObjHandles, sortedKeys, request
                    )
        assert not isError
        self.assertEqual(list_of_items, expected_list)


if __name__ == "__main__":
    unittest.main()
