import json

from webtest import TestApp as Client

from cdb import constants
from cdb.objects import operations
from cdb.testcase import RollbackTestCase

from cs.platform.web.root import Root

from cs.vp.cad import Model
from cs.vp.items.tests import generateItem
from cs.vp.bom.tests import generateComponent


class TestTopMostModel(RollbackTestCase):
    def setUp(self):

        super(TestTopMostModel, self).setUp()
        self.child_item = generateItem()
        self.child_item2 = generateItem()
        self.root_item = generateItem()
        self.assembly_component = generateComponent(
            baugruppe=self.root_item.teilenummer,
            teilenummer=self.child_item.teilenummer,
        )
        self.assembly_component2 = generateComponent(
            baugruppe=self.child_item.teilenummer,
            teilenummer=self.child_item2.teilenummer,
        )

        self.child_doc = operations.operation(
            constants.kOperationNew,  # @UndefinedVariable
            Model,
            titel="child_doc",
            z_categ1="144",
            z_categ2="213",
            teilenummer=self.child_item.teilenummer,
            t_index=self.child_item.t_index,
        )
        self.child_doc2 = operations.operation(
            constants.kOperationNew,
            Model,
            titel="child_doc2",
            z_categ1="144",
            z_categ2="213",
            teilenummer=self.child_item2.teilenummer,
            t_index=self.child_item2.t_index,
        )


    def test_get_top_model_with_full_geometry(self):
        """ the `get_top_most_model_with_geometry` method returns the 0 as last index with geometry"""
        self.root_doc = operations.operation(
            constants.kOperationNew,
            Model,
            titel="root_doc",
            z_categ1="144",
            z_categ2="296",
            teilenummer=self.root_item.teilenummer,
            t_index=self.root_item.t_index,
        )

        c = Client(Root())

        path = [
            {"teilenummer": self.root_item.teilenummer, "t_index": self.root_item.t_index},
            {"teilenummer": self.child_item.teilenummer, "t_index": self.child_item.t_index},
            {"teilenummer": self.child_item2.teilenummer, "t_index": self.child_item2.t_index}
            ]

        url = "/internal/threed/find/get_top_most_model"
        response = c.post(url, json.dumps({"path": path}))

        self.assertEqual(200, response.status_int)

        index = response.json[0]
        cdb_object_id = response.json[1]

        self.assertEqual(index, 0)
        self.assertEqual(cdb_object_id, self.root_item.cdb_object_id)


    def test_get_top_model_with_partial_geometry(self):
        """ the `get_top_most_model_with_geometry` method returns the 1 as last index with geometry"""
        c = Client(Root())

        path = [
            {"teilenummer": self.root_item.teilenummer, "t_index": self.root_item.t_index},
            {"teilenummer": self.child_item.teilenummer, "t_index": self.child_item.t_index},
            {"teilenummer": self.child_item2.teilenummer, "t_index": self.child_item2.t_index}
            ]

        url = "/internal/threed/find/get_top_most_model"
        response = c.post(url, json.dumps({"path": path}))

        self.assertEqual(200, response.status_int)

        index = response.json[0]
        cdb_object_id = response.json[1]

        self.assertEqual(index, 1)
        self.assertEqual(cdb_object_id, self.child_item.cdb_object_id)

