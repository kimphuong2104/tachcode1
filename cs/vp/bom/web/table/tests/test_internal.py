from typing import Any, Self, Optional
from unittest.mock import patch, MagicMock

import pytest
from cdbwrapc import CDBClassDef

from cdb.testcase import RollbackTestCase
from cs.platform.web.rest.support import get_restlink_by_keys
from cs.platform.web.root import Root
from cs.platform.web.root.main import _get_dummy_request
from morepath import Response
from webtest import TestApp as Client

from cs.vp.bom.enhancement import FlatBomRestEnhancement
from cs.vp.bom.enhancement.plugin import AbstractRestPlugin, Dependencies
from cs.vp.bom.enhancement.register import BomTableScope
from cs.vp.bom.enhancement.tests.test_register import FakePluginRegister
from cs.vp.bom.tests import (
    generateAssemblyComponent,
    generateItem,
    generateAssemblyComponentOccurrence,
)


class TestInternal(RollbackTestCase):
    def setUp(self):
        super(TestInternal, self).setUp()

        self.assembly = generateItem()
        self.comp = generateAssemblyComponent(self.assembly, menge=2)

        self.occurrence1 = generateAssemblyComponentOccurrence(
            self.comp,
            occurrence_id="occurrence1",
            relative_transformation="occurrence1",
        )
        self.occurrence2 = generateAssemblyComponentOccurrence(
            self.comp,
            occurrence_id="occurrence2",
            relative_transformation="occurrence2",
        )

    def make_request(self):
        c = Client(Root())

        url = "/internal/bomtable/bom_item_occurrences"

        params = {
            "bom_item_keys": {
                "cdb_object_id": self.comp["cdb_object_id"]
            }
        }

        return c.post_json(
            url,
            params=params,
        )

    def assert_row(self, row_data, obj):
        rest_link = get_restlink_by_keys(
            "bom_item_occurrence", objargs=obj, request=_get_dummy_request()
        )

        self.assertEqual(row_data["@id"], rest_link)
        self.assertEqual(row_data["persistent_id"], rest_link)

        columns_data = row_data["columns"]
        self.assertEqual(columns_data[0], obj.occurrence_id)
        self.assertEqual(columns_data[1], obj.reference_path)
        self.assertEqual(columns_data[2], obj.assembly_path)
        self.assertEqual(columns_data[3], obj.relative_transformation)

    def test_table(self):
        response = self.make_request()

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(2, len(response_rows))

        self.assert_row(response_rows[0], self.occurrence1)
        self.assert_row(response_rows[1], self.occurrence2)


class ClientBomEnhancementDefaultData:
    def __init__(self):
        self.client: Client = Client(Root())
        self.url: str = "/internal/bomtable/bom_enhancement_default_data"
        self.bom_table_url: str = "bomTableUrl/abc/123"
        self.instance_name: str = "instanceName"
        self.root_item_cdb_object_id: str = "rootItem_123"
        self.additional_data: dict = {"abc": "xyz"}
        self.bom_enhancement_options: dict = {
            "ADDITIONAL_DATA_FOR_FETCH_DEFAULT_DATA": self.additional_data
        }

    def do_request(self) -> Response:
        return self.client.post_json(
            self.url,
            params={
                "bomTableUrl": self.bom_table_url,
                "instanceName": self.instance_name,
                "rootItemCdbObjectId": self.root_item_cdb_object_id,
                "bomEnhancementOptions": self.bom_enhancement_options,
            },
        )


@pytest.fixture
def client_bom_enhancement_default_data() -> ClientBomEnhancementDefaultData:
    return ClientBomEnhancementDefaultData()


@patch("cs.vp.bom.enhancement.FlatBomRestEnhancement.get_plugin_register")
def test_bom_enhancement_default_data_correctly_called(
    get_plugin_register_mock: MagicMock,
        client_bom_enhancement_default_data,
) -> None:
    expected_default_data = {"abc": 123, "xyz": "abc"}
    fake_plugin_register = FakePluginRegister()

    class FakePlugin(AbstractRestPlugin):
        DISCRIMINATOR = "FakeEnhancement"

        @classmethod
        def create_for_default_data(
            cls, dependencies: Dependencies, **kwargs: Any
        ) -> Optional[Self]:
            assert (
                    kwargs["bom_table_url"]
                    == client_bom_enhancement_default_data.bom_table_url
            )
            assert (
                    kwargs["instance_name"]
                    == client_bom_enhancement_default_data.instance_name
            )
            assert (
                    kwargs["root_item_cdb_object_id"]
                    == client_bom_enhancement_default_data.root_item_cdb_object_id
            )
            assert (
                    kwargs["additional_data"]
                    == client_bom_enhancement_default_data.additional_data
            )

            return cls()

        def get_default_data(self) -> tuple[Any, Any]:
            return (None, expected_default_data)

    fake_plugin_register.register_plugin(FakePlugin, BomTableScope.INIT)
    fake_plugin_register.close_registration()

    get_plugin_register_mock.configure_mock(return_value=fake_plugin_register)
    response = client_bom_enhancement_default_data.do_request()

    assert response.status_code == 200
    assert response.json == {
        FlatBomRestEnhancement.DEFAULT_ENHANCEMENT_KEY: {},
        FlatBomRestEnhancement.DEFAULT_RESET_DATA_KEY: {
            FakePlugin.DISCRIMINATOR: expected_default_data
        },
    }
