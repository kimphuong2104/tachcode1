#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock

from cdb import testcase
from cs.taskmanager import conf


class BaseTest(testcase.RollbackTestCase):
    def assertObjectsEqual(self, a, b):
        self.assertEqual(dict(a), dict(b))


class TaskClass(BaseTest):
    def test_Context(self):
        tc = conf.TaskClass.KeywordQuery(classname="cs_tasks_test_olc")[0]
        self.assertObjectsEqual(tc.Contexts[0].TaskClass, tc)

    def test_ByClassname_None(self):
        conf.TaskClass.KeywordQuery(classname="foo").Delete()
        self.assertIsNone(conf.TaskClass.ByClassname("foo"))

    def test_ByClassname_exists(self):
        a = conf.TaskClass.Create(classname="foo", name="a")
        conf.TaskClass.Create(classname="foo", name="b")
        self.assertObjectsEqual(
            conf.TaskClass.ByClassname("foo"),
            a,
        )

    def test_is_task_object_mismatch(self):
        task_class = conf.TaskClass(classname="foo")
        task = mock.Mock(GetClassname=mock.Mock(return_value="bar"))
        self.assertFalse(task_class.is_task_object(task))

    def test_is_task_object_match(self):
        task_class = conf.TaskClass(classname="foo")
        task = mock.Mock(GetClassname=mock.Mock(return_value="foo"))
        self.assertTrue(task_class.is_task_object(task))

    @mock.patch.object(
        conf.TaskClass,
        "Query",
        return_value=[
            mock.Mock(classname="a", deadline="A"),
            mock.Mock(classname="b", deadline="B"),
        ],
    )
    def test_GetDeadlineMapping(self, Query):
        self.assertEqual(
            conf.TaskClass.GetDeadlineMapping(),
            {
                "a": {"cs_tasks_col_deadline": {"is_async": False, "propname": "A"}},
                "b": {"cs_tasks_col_deadline": {"is_async": False, "propname": "B"}},
            },
        )

    def test_get_status_change_operation(self):
        task_class = mock.Mock(
            spec=conf.TaskClass,
            status_change_operation="O",
        )
        self.assertEqual(
            conf.TaskClass.get_status_change_operation(task_class),
            "O",
        )

    @mock.patch.object(conf, "get_objects_class", return_value=None)
    def test_checkClass_no_obj_cls(self, _):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkClass(task_class, ctx)

        self.assertEqual(
            str(error.exception), "Klasse 'foo' kann nicht gefunden werden."
        )

    @mock.patch.object(conf, "get_objects_class")
    def test_checkClass_no_uuid(self, get_objects_class):
        get_objects_class.return_value.GetFieldByName.side_effect = AttributeError
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkClass(task_class, ctx)

        self.assertEqual(
            str(error.exception),
            "Der Klasse 'foo' fehlt das Attribut 'cdb_object_id'. "
            "Bitte wählen Sie eine andere Klasse oder legen Sie zuerst das Attribut an.",
        )

    @mock.patch.object(conf, "get_objects_class")
    def test_checkClass(self, get_objects_class):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        self.assertIsNone(conf.TaskClass.checkClass(task_class, ctx))

    def test_checkFilterClass_no_filter(self):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.filter_classname = None
        self.assertIsNone(conf.TaskClass.checkFilterClass(task_class, ctx))

    @mock.patch.object(conf, "CDBClassDef", return_value=None)
    def test_checkFilterClass_no_class(self, _):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkFilterClass(task_class, ctx)

        self.assertEqual(str(error.exception), "Die Klasse 'foo' existiert nicht.")

    @mock.patch.object(conf, "CDBClassDef", side_effect=["base", None])
    def test_checkFilterClass_no_filter_class(self, _):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.filter_classname = "foo"
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkFilterClass(task_class, ctx)

        self.assertEqual(str(error.exception), "Die Klasse 'foo' existiert nicht.")

    @mock.patch.object(conf, "CDBClassDef")
    def test_checkFilterClass_no_subclass(self, CDBClassDef):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        ctx.dialog.filter_classname = "bar"
        CDBClassDef.return_value.hasFacets.return_value = False
        CDBClassDef.return_value.getBaseClassNames.return_value = ["not foo"]
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkFilterClass(task_class, ctx)

        self.assertEqual(
            str(error.exception),
            "Die Klasse 'bar' ist keine Unterklasse oder zulässige Facette von 'foo'.",
        )

    @mock.patch.object(conf, "CDBClassDef")
    def test_checkFilterClass_no_facet1(self, CDBClassDef):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        ctx.dialog.filter_classname = "bar"
        CDBClassDef.return_value.hasFacets.return_value = False
        CDBClassDef.return_value.getBaseClassNames.return_value = ["not foo"]
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkFilterClass(task_class, ctx)

        self.assertEqual(
            str(error.exception),
            "Die Klasse 'bar' ist keine Unterklasse oder zulässige Facette von 'foo'.",
        )

    @mock.patch.object(conf, "Entity")
    @mock.patch.object(conf, "CDBClassDef")
    def test_checkFilterClass_no_facet2(self, CDBClassDef, Entity):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        ctx.dialog.filter_classname = "bar"
        CDBClassDef.return_value.hasFacets.return_value = True
        CDBClassDef.return_value.getBaseClassNames.return_value = ["not foo"]
        Entity.ByKeys.return_value.cdb_classname = "cdb_class"
        with self.assertRaises(conf.util.ErrorMessage) as error:
            conf.TaskClass.checkFilterClass(task_class, ctx)

        self.assertEqual(
            str(error.exception),
            "Die Klasse 'bar' ist keine Unterklasse oder zulässige Facette von 'foo'.",
        )

    @mock.patch.object(conf, "CDBClassDef")
    def test_checkFilterClass_subclass(self, CDBClassDef):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        ctx.dialog.filter_classname = "bar"
        CDBClassDef.return_value.hasFacets.return_value = False
        CDBClassDef.return_value.getBaseClassNames.return_value = ["foo"]
        self.assertIsNone(conf.TaskClass.checkFilterClass(task_class, ctx))

    @mock.patch.object(conf, "Entity")
    @mock.patch.object(conf, "CDBClassDef")
    def test_checkFilterClass_facet(self, CDBClassDef, Entity):
        task_class = mock.Mock(spec=conf.TaskClass)
        ctx = mock.Mock()
        ctx.dialog.classname = "foo"
        ctx.dialog.filter_classname = "bar"
        CDBClassDef.return_value.hasFacets.return_value = True
        CDBClassDef.return_value.getBaseClassNames.return_value = ["not foo"]
        Entity.ByKeys.return_value.cdb_classname = "cdb_facet"
        self.assertIsNone(conf.TaskClass.checkFilterClass(task_class, ctx))


class Attribute(BaseTest):
    @mock.patch.object(conf, "CDBClassDef")
    def test_validatePropname_sync_pass(self, _):
        attr = mock.Mock(
            spec=conf.Attribute,
            is_async=False,
        )
        self.assertIsNone(conf.Attribute.validatePropname(attr, None))

    @mock.patch.object(conf, "CDBClassDef", return_value=None)
    def test_validatePropname_sync_fail(self, _):
        attr = mock.Mock(
            spec=conf.Attribute,
            is_async=False,
        )
        with self.assertRaises(conf.util.ErrorMessage):
            conf.Attribute.validatePropname(attr, None)

    @mock.patch.object(conf, "CDBClassDef", return_value=None)
    def test_validatePropname_async(self, _):
        attr = mock.Mock(
            spec=conf.Attribute,
            is_async=True,
        )
        self.assertIsNone(conf.Attribute.validatePropname(attr, None))


class TreeContext(BaseTest):
    def test_resolve_empty_response(self):
        tree_context = conf.TreeContext()
        with mock.patch.object(conf.TreeContext, "TreeRelationships", None):
            self.assertEqual(tree_context.resolve(None, {}, None), [])
            self.assertEqual(tree_context.resolve(mock.MagicMock(), {}, None), [])

    @mock.patch.object(conf, "resolve_contexts")
    @mock.patch.object(conf, "update_objects")
    def test_resolve(self, update_objects, resolve_contexts):
        TreeRelationships = ["relships"]
        update_objects.return_value = "key@1"
        resolve_contexts.return_value = [
            ["C", "B", "A"],
            ["D", "C"],
            ["C", "B", "b", "A"],
            ["D", "C", "B", "A"],
        ]

        task = mock.MagicMock()
        task.ToObjectHandle = mock.MagicMock(return_value="oh")
        objects = {}
        request = mock.MagicMock()
        tree_context = conf.TreeContext()
        with mock.patch.object(
            conf.TreeContext, "TreeRelationships", TreeRelationships
        ):
            self.assertEqual(
                tree_context.resolve(task, objects, request),
                [
                    ["C", "B", "b", "A"],
                    ["D", "C", "B", "A"],
                ],
            )

        update_objects.assert_called_once_with(
            objects, task.ToObjectHandle.return_value, request
        )

        resolve_contexts.assert_called_once_with(
            task.ToObjectHandle.return_value,
            TreeRelationships,
            objects,
            request,
            [[update_objects.return_value]],
        )


if __name__ == "__main__":
    unittest.main()
