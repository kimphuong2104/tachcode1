import mock
import unittest

from cs.costing.component_structure import views


class Utility(unittest.TestCase):

    @mock.patch.object(views, "get_classinfo_REST")
    def test__get_oid_from_url_wrong_classname(self, get_classinfo_REST):
        mock_class_def = mock.MagicMock()
        mock_class_def.getClassname = mock.MagicMock(return_value="foo")
        get_classinfo_REST.return_value = mock_class_def, "bar"
        with self.assertRaises(ValueError):
            views._get_oid_from_url("/foo_rest_class/foo_rest_key")
        get_classinfo_REST.assert_called_once_with("foo_rest_class")

    @mock.patch.object(views, "get_classinfo_REST")
    def test__get_oid_from_url(self, get_classinfo_REST):
        mock_class_def = mock.MagicMock()
        mock_class_def.getClassname = mock.MagicMock(return_value="cdbpco_comp2component")
        get_classinfo_REST.return_value = mock_class_def, "bar"
        self.assertEqual(
            "foo_rest_key",
            views._get_oid_from_url("/foo_rest_class/foo_rest_key")
        )
        get_classinfo_REST.assert_called_once_with("foo_rest_class")



tnobj = mock.MagicMock(comp_object_id="tcoid", cloned=0)
pnobj = mock.MagicMock(comp_object_id="pcoid", cloned=1)


class CostTreeView(unittest.TestCase):
    @mock.patch.object(views.util, "resolve_component_structure", return_value=(1, 2, 3, 4))
    def test_resolve_structure(self, resolve_component_structure):
        x = mock.MagicMock(
            spec=views.CostTreeView,
            root_oid="foo",
            request="baz",
        )
        self.assertIsNone(views.CostTreeView.resolve_structure(x))
        self.assertEqual(x.records, 1)
        self.assertEqual(x.rows, 2)
        self.assertEqual(x.flat_nodes, 3)
        self.assertEqual(x.levels, 4)
        resolve_component_structure.assert_called_once_with(
            x.root_oid,
            x.get_row_and_node,
            x.request,
        )

    @mock.patch.object(views, "get_object_icon")
    @mock.patch.object(views, "get_object_description")
    @mock.patch.object(views, "get_costing_structure_dtag")
    def test_get_additional_data(self, get_costing_structure_dtag, get_object_description,
                                      get_object_icon):
        record = mock.MagicMock(table_name="cdbpco_calculation", cloned=0)
        get_costing_structure_dtag.return_value = ("{name} (x{quantity})", ['name', 'quantity'])
        self.assertEqual(
            views.CostTreeView.get_additional_data(record, "req"),
            {
                "system:description": get_object_description.return_value,
                "system:icon_link": get_object_icon.return_value,
                "cloned": record.record["cloned"],
                "cloned_icon_link": {"url": ""},
                "comp_object_id": "",
                "component_id": "",
            },
        )
        get_object_description.assert_called_once_with(
            "{name} (x{quantity})", record.record, "name", "quantity")
        get_object_icon.assert_called_once_with(
            "cdbpco_comp_object", record.record, "cdb_classname")

    def test_get_tree_object_no_rest_obj(self):
        self.assertEqual(
            views.CostTreeView.get_tree_object(None),
            {},
        )

    def test_get_tree_object(self):
        rest_object = {
            "@id": "ID--1",
            "@type": "type",
            "system:classname": "Classname",
            "system:navigation_id": "navigation",
            "system:description": "Description",
            "system:icon_link": "Icon",
            "cloned": 1,
            "cloned_icon_link": "/resources/icons/byname/cdbpco_cloned",
            "comp_object_id": "comp_object_id",
            "component_id": "component_id",
        }
        self.assertEqual(
            views.CostTreeView.get_tree_object(rest_object),
            {
                "@id": "ID",
                "@type": "type",
                "system:classname": "Classname",
                "system:navigation_id": "navigation",
                "system:description": "Description",
                "label": "Description",
                "cloned": 1,
                "icons": [
                    {"url": "Icon"},
                     "/resources/icons/byname/cdbpco_cloned",
                ],
                "rest_key": "ID--1",
                "comp_object_id": "comp_object_id",
                "component_id": "component_id",
            },
        )

    def test_persist_drop_not_move(self):
        with self.assertRaises(NotImplementedError):
            views.CostTreeView.persist_drop("T", "P", [], "PR", False)

    def test_delete_copy(self):
        with self.assertRaises(NotImplementedError):
            views.CostTreeView.delete_copy("foo")
