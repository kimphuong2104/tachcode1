#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
To setup custom classes as time schedule contents in the Gantt Chart Web UI
application, you have to supply a plugin.

These plugins are classes derived from
:py:class:`cs.pcs.timeschedule.web.plugins.TimeSchedulePlugin`
and contain information about the contents class.
This is a performance optimization because the
application loads time schedule contents using ``cdb.sqlapi.RecordSet2`` only.
Important ``cdb.objects.Object``-based interfaces are instead supplied by the
plugin.

.. warning ::

    Plugins contain redundant logic to determine

    - Web UI links and internals and
    - object icons and descriptions.

    Make sure any changes you make in the configuration are reflected in time
    schedule plugins.

"""

import logging

from cdb import sig, sqlapi
from cdb.objects.iconcache import IconCache, _LabelValueAccessor
from cdbwrapc import CDBClassDef
from cs.web.components.ui_support.forms import FormInfoBase

from cs.pcs.projects.project_structure import util
from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.timeschedule.web.models.helpers import get_oid_query_str

GET_TABLE_DATA_PLUGINS = sig.signal()


class TimeSchedulePlugin:
    """
    ``TimeSchedulePlugin`` classes must contain the following strings as
    class constants to identify data to be handled by this plugin:

    :guilabel:`table_name`
        Name of the database table to select objects from.

    :guilabel:`classname`
        (Base) Classname as configured in the Data Dictionary.

    .. note ::

        Default implementations use additional class constants.
        See their documentation for details.

    To use custom plugins,

    - you have to register them and
    - their :py:meth:`Validate` classmethod may not raise an error.

    .. rubric :: Example: Registering a custom plugin

    .. code-block :: python

            from cdb import sig
            from cs.pcs.timeschedule.web.plugins import GET_TABLE_DATA_PLUGINS
            from cs.pcs.timeschedule.web.plugins import TimeSchedulePlugin
            import MyPlugin from custom.timeschedule.plugins

            @sig.connect(GET_TABLE_DATA_PLUGINS)
            def _register_timeschedule_plugin(register_callback):
                register_callback(MyPlugin)

    """

    table_name = None
    classname = None
    catalog_name = None
    has_olc = True
    nullable_fields = set()

    __olc_required_strings__ = [
        "olc_attr",
        "status_attr",
    ]

    __required_strings__ = [
        "table_name",
        "classname",
        "catalog_name",
        "__icon_base_url__",
        "description_pattern",
        # optional:
        # subject_id_attr and subject_type_attr
    ]
    __required_string_tuples__ = ["description_attrs"]

    @classmethod
    def Validate(cls):
        """
        Called when time schedule application collects plugins.
        Only valid plugins are used.
        Uses the class constants ``cls.__required_strings__`` and
        ``cls.__required_string_tuples__``.

        :guilabel:`__required_strings__`
            List of strings matching required class constants expected to
            contain strings each.

        :guilabel:`__required_string_tuples__`
            List of strings matching required class constants expected to
            contain tuples of strings each.

        :raises ValueError: if the plugin is invalid, e.g. any constants are
            missing or of wrong type.
        """

        def is_str(value):
            return isinstance(value, str)

        def is_str_tuple(value):
            if not isinstance(value, tuple):
                return False
            return all(is_str(x) for x in value)

        for olc_attr in cls.__olc_required_strings__:
            if not is_str(getattr(cls, olc_attr, None)):
                logging.info("schedule plugin '%s' has no OLC info", cls)
                cls.has_olc = False

        missing = [
            name
            for name in cls.__required_strings__
            if not is_str(getattr(cls, name, None))
        ]

        missing += [
            name
            for name in cls.__required_string_tuples__
            if not is_str_tuple(getattr(cls, name, None))
        ]
        if missing:
            raise ValueError(
                f"missing attributes (or of wrong type):\n\t{', '.join(missing)}"
            )

    @classmethod
    def GetRequiredFields(cls):
        """
        :returns: Field names required by the frontend for objects of this
            plugin's class.
            Only fields included here are guaranteed to be transported to the
            client.
        :rtype: set
        """
        required = set.union(
            set(cls.icon_attrs),
            set(cls.description_attrs),
            set([cls.subject_id_attr, cls.subject_type_attr]),
        )
        if cls.has_olc:
            required = required.union(set([cls.olc_attr, cls.status_attr]))
        return required

    @classmethod
    def GetNullableFields(cls):
        """
        NULL values are not part of REST objects sent to the frontend.
        This is an optimization in the platform to save bandwidth.
        However, the time schedule's update model misinterprets the value's
        absence as "the value remains unchanged".
        This results in the UI showing an obsolete state until the next full refresh.

        To fix this, specify ``cls.nullable_fields`` as the set of field names
        where NULL values are to be expected.

        :returns: Field names that may be updated to contain NULL value
        :rtype: set
        """
        return cls.nullable_fields

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        """
        :param root_oid: The `cdb_object_id` of the root object
            to resolve the structure of.
        :param root_oid: str

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: list of only the root object
        :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`

        :raises ValueError: if non-existing root_oid
        """

        where = f"id='{sqlapi.quote(root_oid)}'"
        for record in sqlapi.RecordSet2("cdb_object", where):
            return [PCS_LEVEL(root_oid, record.relation, 0)]
        raise ValueError

    olc_attr = None
    status_attr = "status"

    @classmethod
    def GetObjectKind(cls, record):
        """
        Replacement for ``cdb.objects.Object.GetObjectKind``.
        Uses the class constant ``cls.olc_attr``.

        :guilabel:`olc_attr`
            Field name containing the object's lifecycle name
            (usually "cdb_objektart").

        :param record: Database representation of a timeschedule content
            object.
        :type record: cdb.sqlapi.Record

        :returns: The object lifecycle name of the object represented by
            ``record``.
        :rtype: str

        :raises AttributeError: if ``cls.olc_attr`` is not set
        """
        return record[cls.olc_attr]

    __icon_base_url__ = "/resources/icons/byname"
    icon_id = None
    icon_attrs = None

    @classmethod
    def GetObjectIcon(cls, record):
        """
        Replacement for ``cdb.objects.Object.GetObjectIcon``.

        :param record: Database representation of a timeschedule content
            object.
        :type record: cdb.sqlapi.Record

        :returns: Relative URL of the object's icon.
        :rtype: str
        """

        # record will only have non-null value for cdb_classname if it is of a subclass
        cdb_classname = record.get("cdb_classname")
        class_def = (
            CDBClassDef(cdb_classname) if cdb_classname else CDBClassDef(cls.classname)
        )
        icon_id = class_def.getObjectIconId()
        return IconCache.getIcon(icon_id, accessor=_LabelValueAccessor(record))

    description_pattern = None
    description_attrs = None

    @classmethod
    def GetDescription(cls, record):
        """
        Replacement for ``cdb.objects.Object.GetDescription``.
        Uses the class constants ``cls.description_pattern`` and
        ``cls.description_attrs``.

        :guilabel:`description_pattern`
            String pattern to resolve an object description.
            Placeholders will be replaced with object values of the fields
            given in ``description_attrs``.

        :guilabel:`description_attrs`
            Tuple of strings representing field names used in
            ``description_pattern``.

        :param record: Database representation of a timeschedule content
            object.
        :type record: cdb.sqlapi.Record

        :returns: The object's description.
        :rtype: str
        """
        args = [
            record[attr]
            for attr in cls.description_attrs  # pylint: disable=not-an-iterable
        ]
        return cls.description_pattern.format(*args)

    subject_id_attr = None
    subject_type_attr = None

    @classmethod
    def GetResponsible(cls, record):
        """
        Uses the class constants ``cls.subject_id_attr`` and
        ``cls.subject_type_attr``.

        .. note ::

            ``GetResponsible`` works even if ``record`` is missing attributes.
            It will not log any errors, but default to empty values.

        :guilabel:`subject_id_attr`
            Field name containing the ID of a person or role.

        :guilabel:`subject_type_attr`
            Field name containing the "subject type" of values in the field
            ``subject_id_attr``.

        :param record: Database representation of a timeschedule content
            object.
        :type record: cdb.sqlapi.Record

        :returns: Subject ID and type of given ``record`` mapped to stable
            keys "subject_id" and "subject_type".
            Both values default to empty strings if ``record`` is missing the
            respective attribute.
        :rtype: dict
        """
        return {
            "subject_id": record.get(cls.subject_id_attr, ""),
            "subject_type": record.get(cls.subject_type_attr, ""),
        }

    @classmethod
    def _GetCatalogQuery(cls, schedule):
        """
        :param schedule: The schedule to get the query conditions for.
        :type schedule: cs.pcs.timeschedule.TimeSchedule

        :returns: Key-value pairs used for the initial query of the catalog.
            The default implementation queries for the project ID of the
            schedule.
        :rtype: dict
        """
        pid = schedule.cdb_project_id
        if pid:
            return {"cdb_project_id": pid}
        return {}

    @classmethod
    def GetCatalogConfig(cls, schedule, request):
        """
        Uses the class constant ``cls.catalog_name`` (the name of a GUI
        catalog to select multiple, comma-separated cdb_object_id values).

        :param schedule: The schedule to get catalog data for.
        :type schedule: cs.pcs.timeschedule.TimeSchedule

        :param request: The request sent from the frontend.
        :type request: morepath.Request

        :returns: Data required to render a frontend catalog for adding
            objects of this class to the time schedule elements.
        :rtype: dict

        :raises ElementsError: if ``cls.catalog_name`` is not the name of an
            existing catalog.
        """
        catalog_config = FormInfoBase.get_catalog_config(
            request,
            cls.catalog_name,
            False,  # is_combobox
            True,  # as_objs
        )
        catalog_config["formData"] = cls._GetCatalogQuery(schedule)
        return catalog_config

    @classmethod
    def GetClassReadOnlyFields(cls):
        """
        :returns: Class-specific fields that are always read only
        :rtype: list of str
        """
        return []

    @classmethod
    def GetObjectReadOnlyFields(cls, oids):
        """
        :returns: Object-specific readonly fields indexed by ``oids``
        :rtype: dict ({str: list of str})
        """
        return {}

    @classmethod
    def GetQueryStrFromOids(cls, oids):
        """
        :returns: SQL WHERE clause for given values, e.g.
            ``"cdb_object_id IN ('a', 'b', 'c')"``.
        :rtype: str

        :raises ValueError: if
            - any value contains a non-string value in first position
        """

        try:
            query_str = get_oid_query_str(oids)
        except TypeError as exc:
            raise ValueError(f"non-string oid value: '{oids}'") from exc

        return query_str

    @classmethod
    def ResolveRecords(cls, oids):
        """
        :returns: table names and records for objects identified by
            ``oids``.
        :rtype: list of `cs.pcs.projects.project_structure.util.PCS_RECORD`

        :raises cdb.dberrors.DBConstraintViolation: if any table name is
            invalid or does not exist.
        """
        query_str = cls.GetQueryStrFromOids(oids)
        records_with_read_access = sqlapi.RecordSet2(
            cls.table_name, query_str, access="read"
        )

        if hasattr(cls, "table_view"):
            query_str_with_read_access = cls.GetQueryStrFromOids(
                [record.cdb_object_id for record in records_with_read_access]
            )
            records_with_read_access = sqlapi.RecordSet2(
                cls.table_name,
                sql=f"SELECT * FROM {cls.table_view} WHERE {query_str_with_read_access}",
            )
        return [
            util.PCS_RECORD(cls.table_name, record)
            for record in records_with_read_access
        ]


class WithTimeSchedulePlugin:
    def _register_plugin(self, plugin):
        try:
            plugin.Validate()
            self.plugins[plugin.table_name] = plugin
        except (AttributeError, ValueError) as verr:
            logging.error("ignoring broken timeschedule plugin: %s (%s)", verr, plugin)

    def collect_plugins(self, signal):
        """
        Emit ``signal`` to register plugins connected to it.
        Plugins must pass a validation step to be registered.

        .. note ::

            Registering a plugin will replace plugins
            already registered for the same ``table_name``

        """
        self.plugins = {}
        sig.emit(signal)(self._register_plugin)
