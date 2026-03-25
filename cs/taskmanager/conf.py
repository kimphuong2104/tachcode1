#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import defaultdict

from cdb import kernel, util
from cdb.lru_cache import lru_cache
from cdb.objects import (
    ByID,
    Forward,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_1,
)
from cdb.objects.core import ClassRegistry
from cdb.platform.mom.entities import Entity
from cdbwrapc import CDBClassDef
from cs.taskmanager.context import filter_redundant, resolve_contexts, update_objects

fTaskClass = Forward(__name__ + ".TaskClass")
fAttribute = Forward(__name__ + ".Attribute")
fColumn = Forward(__name__ + ".Column")
fTreeContextRelationship = Forward(__name__ + ".TreeContextRelationship")
fTreeContext = Forward(__name__ + ".TreeContext")
fRule = Forward("cdb.objects.Rule")
fObject = Forward("cdb.objects.Object")
fClassDef = Forward("cdb.platform.mom.entities.Class")


def deep_update(source, overrides):
    """
    Update a nested dictionary or similar mapping.
    Modify ``source`` in place.
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source


@lru_cache(maxsize=1, clear_after_ue=False)
def get_cache():
    """returns pseudo-singleton Cache instance"""
    return Cache()


def get_objects_class(classname):
    tbl = kernel.getPrimaryTableForClass(classname)
    if tbl:
        base_cls = ClassRegistry().find(tbl)
        if base_cls:
            # pylint: disable=W0212
            return base_cls._FindLeafClass({"cdb_classname": classname})
    return None


class TaskClass(Object):
    """
    Defines a class of task-like objects and how to display them.

    Tasks matching this class definition are identified using an Object Rule,
    which has to be queryable, since it is compiled to a view
    ``cs_tasks_headers_v`` to support fast access.

    - **name**: Unique name.
    - **classname**: Name of an Elements class.
    - **rule_id**: Name of an Object Rule identifying tasks to be displayed for
      a user. Will usually involve a user-specific variable, such as
      ``$(role)`` or ``$(persno)``.

    The mapping to the tasks table is derived from the :ref:`cs-tasks-attr`
    relationship containing the class's attribute definitions.

    TaskClasses may also specify a number of :ref:`cs-tasks-context-tree`.
    """

    __maps_to__ = "cs_tasks_class"
    __classname__ = "cs_tasks_class"

    Attributes = Reference_N(
        fAttribute, fAttribute.tclass_object_id == fTaskClass.cdb_object_id
    )
    Rule = Reference_1(fRule, fTaskClass.rule_id)
    ObjectsClass = ReferenceMethods_1(
        fObject, lambda self: get_objects_class(self.classname)
    )
    ClassDef = Reference_1(fClassDef, fTaskClass.classname)

    Contexts = Reference_N(
        fTreeContext,
        fTreeContext.tclass_object_id == fTaskClass.cdb_object_id,
    )

    @classmethod
    def ByClassname(cls, classname):
        for task_class in cls.KeywordQuery(classname=classname):
            return task_class

    def is_task_object(self, obj):
        object_classname = obj.GetClassname()
        return self.classname == object_classname

    @classmethod
    def GetDeadlineMapping(cls):
        result = {
            task_class.classname: {
                "cs_tasks_col_deadline": Attribute.FormatMapping(task_class.deadline)
            }
            for task_class in cls.Query()
        }
        return result

    def get_status_change_operation(self):
        return self.status_change_operation

    def checkClass(self, ctx):
        objects_class = get_objects_class(ctx.dialog.classname)
        if not objects_class:
            raise util.ErrorMessage("cs_tasks_class_missing", ctx.dialog.classname)
        try:
            objects_class.GetFieldByName("cdb_object_id")
        except AttributeError:
            raise util.ErrorMessage("cs_tasks_oid_missing", ctx.dialog.classname)

    def checkFilterClass(self, ctx):
        if ctx.dialog.filter_classname:
            base_class = CDBClassDef(ctx.dialog.classname)
            filter_class = CDBClassDef(ctx.dialog.filter_classname)
            if not base_class:
                raise util.ErrorMessage("cs_tasks_no_class", ctx.dialog.classname)
            if not filter_class:
                raise util.ErrorMessage(
                    "cs_tasks_no_class", ctx.dialog.filter_classname
                )

            is_subclass = ctx.dialog.classname in filter_class.getBaseClassNames()
            is_facet = (
                base_class.hasFacets()
                and Entity.ByKeys(ctx.dialog.filter_classname).cdb_classname
                == "cdb_facet"
            )

            if not (is_subclass or is_facet):
                raise util.ErrorMessage(
                    "cs_tasks_invalid_filter_class",
                    ctx.dialog.filter_classname,
                    ctx.dialog.classname,
                )

    def recompileView(self, ctx):
        if getattr(ctx, "error", None):
            return

        from cs.taskmanager import TaskHeaders

        TaskHeaders.compileToView()

    event_map = {
        (("create", "copy"), "pre"): ("checkClass", "checkFilterClass"),
        ("modify", "pre"): "checkFilterClass",
        (("create", "copy", "modify", "delete"), "post"): "recompileView",
    }


class Attribute(Object):
    """
    Attribute mapping of a :ref:`cs-tasks-class`. For each :ref:`cs-tasks-col`
    and TaskClass, up to one Attribute may exist, telling the system how to map
    the Column to tasks of this TaskClass.

    - **tclass_object_id**: ``cdb_object_id`` of a task class definition.
    - **column_object_id**: ``cdb_object_id`` of a column definition.
    - **propname**: An attribute, property, or method of any object of this
      task class. Will be evaluated at runtime using ``cs.taskmanager.eval``.
    """

    __maps_to__ = "cs_tasks_attribute"
    __classname__ = "cs_tasks_attribute"

    TaskClass = ReferenceMethods_1(fTaskClass, lambda self: ByID(self.tclass_object_id))
    Column = Reference_1(fColumn, fAttribute.column_object_id)

    @classmethod
    def GetMapping(cls):
        mapping = defaultdict(dict)

        for attr in cls.Query():
            if attr.Column:
                mapping[attr.TaskClass.classname][attr.Column.name] = cls.FormatMapping(
                    attr.propname, attr.is_async
                )

        return mapping

    @classmethod
    def FormatMapping(cls, propname, is_async=False):
        return {"is_async": is_async, "propname": propname}

    def validatePropname(self, _):
        def is_class_field(field_name, classname):
            cdef = CDBClassDef(classname)
            return cdef and cdef.getAttributeDefinition(field_name)

        if (
            not self.is_async
            and self.TaskClass
            and not is_class_field(self.propname, self.TaskClass.classname)
        ):
            raise util.ErrorMessage("cs_tasks_non_nativ_attr", self.propname)

    event_map = {
        (("create", "copy", "modify"), "pre"): "validatePropname",
    }


class Column(Object):
    """
    Columns define the schema of the tasks table. They may also define a custom
    frontend component to render its cells. If you want to render complex
    values (e.g. no simple strings or numbers), you will want to specify a
    plugin.

    - **name**: ID of a label naming this column.
    - **tooltip**: ID of a label with a more detailed description of this
      column.
    - **plugin_component**: Name of a React component registered in the
      frontend registry. Note that you can only use components of libraries
      already included in the application's header, usually only
      ``cs-taskmanager-web`` itself.
    """

    __maps_to__ = "cs_tasks_column"
    __classname__ = "cs_tasks_column"

    Attributes = Reference_N(
        fAttribute, fAttribute.column_object_id == fColumn.cdb_object_id
    )

    def resolve_tooltip(self):
        if self.tooltip:
            return util.get_label(self.tooltip)
        return None


class FilterableContext(Object):
    """
    Class entries representing a context class that is filterable in
    cs-taskmanager-web to be shipped with client modules.
    """

    __maps_to__ = "cs_tasks_context"
    __classname__ = "cs_tasks_context"


class Cache(object):
    """
    Holds everything needed for mapping tasks as a singleton cache to maximize
    backend performance.

    Note: Updates to configuration objects (TaskClass, Column, Attribute)
    during a cdbsrv session have no effect unless the cache is explicitely
    refreshed:

    .. code-block:: python

        from cs.taskmanager.conf import Cache

        Cache.refresh()

    The cache is structured like this:

    .. code-block:: python

        cache.classes == {"task_classname": TaskClassObject}
        cache.classnames == ["classname1", "classname2"]
        cache.columns == {"column_object_id": ColumnObject}
        cache.context_classnames == ["classname3", "classname4"]
        cache.mapping == {"task_classname": {"column_id": "field_name"}}

    """

    def __init__(self):
        self.initialize()

    @classmethod
    def refresh(cls):
        get_cache().initialize()

    def initialize(self):
        columns = {c.cdb_object_id: c for c in Column.Query()}
        task_classes = TaskClass.Query()
        classes = {task_class.name: task_class for task_class in task_classes}
        mapping = Attribute.GetMapping()
        mapping = deep_update(mapping, TaskClass.GetDeadlineMapping())

        self.classes = classes
        self.classnames = [
            task_class.filter_classname or task_class.classname
            for task_class in task_classes
        ]
        self.columns = columns
        self.context_classnames = FilterableContext.Query().classname
        self.mapping = mapping


def _handle_fallback(hook, field, source, parent):
    if source and source == parent:
        hook.set(field, "")
        hook.set_readonly(field)
    else:
        hook.set_writeable(field)


class TreeContextRelationship(Object):
    __maps_to__ = "cs_tasks_context_tree_relships"
    __classname__ = "cs_tasks_context_tree_relships"

    event_map = {
        (
            ("create", "modify", "copy"),
            ("pre_mask", "dialogitem_change"),
        ): "handle_fallback",
    }

    @staticmethod
    def handle_fallback_hook(hook):
        prefix = "cs_tasks_context_tree_relships"
        field = "{}.fallback_relship_name".format(prefix)
        new_values = hook.get_new_values()
        source = new_values["{}.source_classname".format(prefix)]
        parent = new_values["{}.parent_classname".format(prefix)]
        _handle_fallback(hook, field, source, parent)

    def handle_fallback(self, ctx):
        field = "fallback_relship_name"
        source = ctx.dialog.source_classname
        parent = ctx.dialog.parent_classname
        _handle_fallback(ctx, field, source, parent)


class TreeContext(Object):
    """
    Configuration class for defining the tree context for a given task class.
    """

    __maps_to__ = "cs_tasks_context_tree"
    __classname__ = "cs_tasks_context_tree"

    TaskClass = Reference_1(
        fTaskClass,
        fTaskClass.cdb_object_id == fTreeContext.tclass_object_id,
    )

    TreeRelationships = Reference_N(
        fTreeContextRelationship,
        fTreeContextRelationship.context_tree_name == fTreeContext.name,
        order_by=fTreeContextRelationship.rship_position,
    )

    def resolve(self, task, objects, request):
        """
        Resolves the contexts for a single tree context.
        The result will contain all the contexts based on current configuration.
        This method will mutate the objects parameter.

        :param task: the task object for which contexts need to be resolved.
        :type task: CDB Object.

        :param objects: The objects dictionary which will be updated with the
            objects involved in the contexts.
        :type objects: dict

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: List of all the contexts for the provided task. Each context will
            be a list of restkeys of the objects involved.
            An example of return value:
                [
                    ["0@P000000", "D000000@", "P000000@T000031413", "P000000"],
                    ["0@P000000", "D000000@", "P000000@T000031412", "P000000"],
                ]

        :rtype: list

        .. note ::

            "Duplicate" contexts are filtered out.
            See :py:func:`cs.taskmanager.context.filter_redundant` for details.

        """
        if not task or not self.TreeRelationships:
            return []

        oh = task.ToObjectHandle()
        task_rest_key = update_objects(objects, oh, request)

        contexts = resolve_contexts(
            oh, list(self.TreeRelationships), objects, request, [[task_rest_key]]
        )
        return filter_redundant(contexts)
