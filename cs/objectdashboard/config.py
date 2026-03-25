#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
import json
import logging

from cdb import auth, sqlapi, ue
from cdb.objects import Forward, Object, Reference_1

from cs.objectdashboard import forwarded_classes as fc

fNotesContent = Forward("cs.pcs.widgets.notes_content.NotesContent")


class _DashboardConfig:
    """
    Abstract base class for default and object dashboard configuration entries
    """

    @classmethod
    def get_config(cls, context_object_id):
        """
        :param context_object_id: ``cdb_object_id`` of the context object to
            query configuration entries for
        :type context_object_id: basestring

        :returns: ``DashboardDefaultConfig`` entries matching given parameters,
            ordered by ``xpos`` and ``ypos``
        :rtype: cdb.objects.references.ObjectCollection
        """
        new_config = []

        config = cls.Query(
            f"context_object_id = '{sqlapi.quote(context_object_id)}'",
            addtl="ORDER BY xpos, ypos",
            access="read",
        )

        if not config:
            # if no config was found end early and return empty value
            logging.exception(
                "'%s' has no read access on Global KPIS thresholds", auth.persno
            )
            return new_config

        try:
            for c in config:
                if c["component_name"] == "cs-pcs-widgets-ProjectRadar":
                    settings = json.loads(c["settings"])
                    for s in settings["configuration"]:
                        if s["tile"] == "cs-pcs-widgets-InBudget":
                            s["args"] = [
                                DefaultKPIsThreshold.ByKeys(
                                    kpi_name="CPI"
                                ).success_threshold,
                                DefaultKPIsThreshold.ByKeys(
                                    kpi_name="CPI"
                                ).danger_threshold,
                            ]
                        elif s["tile"] == "cs-pcs-widgets-InTime":
                            s["args"] = [
                                DefaultKPIsThreshold.ByKeys(
                                    kpi_name="SPI"
                                ).success_threshold,
                                DefaultKPIsThreshold.ByKeys(
                                    kpi_name="SPI"
                                ).danger_threshold,
                            ]
                    c.settings = json.dumps(settings)
                new_config.append(c)
        except AttributeError:
            new_config = config
            msg = "Global KPIs threshold are not configured"
            logging.error(msg)
        except ValueError:
            new_config = config
        return new_config

    @classmethod
    def create_from_description(cls, desc, context_object_id):
        """
        :param desc: Keyword arguments to use for the new entry
        :type desc: dict

        :param context_object_id: ``cdb_object_id`` of the new entry's context
        :type context_object_id: basestring

        :returns: New configuration entry from given parameters
        :rtype: DashboardDefaultConfig

        Convenience function to create objects from simple dictionary
        descriptions
        """
        return cls.Create(context_object_id=context_object_id, **desc)

    def _check_once_only(self, ctx):
        """
        :param self: Configuration entry to check
        :type self: DashboardConfig or DashboardDefaultConfig

        :raises ue.Exception: if widget ``self`` is only allowed once but not
            unique in this context
        """
        cls = self.__class__
        if (
            self.Widget
            and self.Widget.once_only
            and cls.Query(
                (cls.context_object_id == self.context_object_id)
                & (cls.component_name == self.component_name)
                & (cls.cdb_object_id != self.cdb_object_id)
            )
        ):
            raise ue.Exception(
                "cs_objdashboard_widget_once_only", self.Widget.comp_path
            )


class DashboardConfig(Object, _DashboardConfig):
    """
    Dashboard configuration entry for a context object. Each context object
    can have multiple entries arranged in a grid (``xpos``, ``ypos``).

    ``settings`` is serialized JSON containing frontend confguration data.
    """

    __classname__ = __maps_to__ = "cs_objdashboard_config"

    Widget = Reference_1(
        fc.Widget,
        fc.DashboardConfig.component_name,
    )

    event_map = {
        (("copy", "create", "modify"), "pre"): "_check_once_only",
    }


class DashboardDefaultConfig(Object, _DashboardConfig):
    """
    Dashboard default configuration entry for a context object. Each context
    object can have multiple entries arranged in a grid (``xpos``, ``ypos``).

    ``settings`` is serialized JSON containing frontend confguration data.
    """

    __classname__ = __maps_to__ = "cs_objdashboard_default_cfg"

    Widget = Reference_1(fc.Widget, fc.DashboardDefaultConfig.component_name)

    event_map = {
        (("copy", "create", "modify"), "pre"): "_check_once_only",
    }


class DefaultKPIsThreshold(Object):
    __classname__ = __maps_to__ = "cs_objdashboard_default_kpis"

    event_map = {
        (("copy", "create", "modify"), "pre"): "_check_thresholds",
    }

    def _check_thresholds(self, ctx):
        if self.success_threshold < self.danger_threshold:
            raise ue.Exception("kpi_threshold_error1")
        if self.success_threshold == self.danger_threshold:
            raise ue.Exception("kpi_threshold_error2")
        if self.danger_threshold < 0 or self.danger_threshold > 1:
            raise ue.Exception("kpi_threshold_error4")
        if self.success_threshold < 0 or self.success_threshold > 1:
            raise ue.Exception("kpi_threshold_error3")


class KPIsName(Object):
    __classname__ = __maps_to__ = "cdbpcs_kpis_name"


class Widget(Object):
    """
    Dashboard component ("catalog" entry). Lists components available in the
    system along with their general settings.
    """

    __classname__ = __maps_to__ = "cs_objdashboard_widget"

    @classmethod
    def ByClassname(cls, classname):
        """
        :param classname: Classname to query applicable components for
        :type classname: basestring

        :returns: Widget entries applicable for given
            ``classname``
        :rtype: cdb.objects.references.ObjectCollection
        """
        return cls.Query(
            f"comp_path IN (SELECT comp_path FROM {WidgetApplicability.__maps_to__} "
            f"WHERE classname = '{classname}')"
        )

    @classmethod
    def get_libraries(cls):
        """
        :returns: External frontend libraries required by any Widget
        :rtype: list

        Example return value:

        .. code-block :: python

            [('cs-activitystream-web', '15.1.0')]

        .. note ::

            Library entries may contain duplicates
        """
        components = sqlapi.RecordSet2(cls.GetTableName())
        return [
            (c.library_name, c.library_version) for c in components if c.library_name
        ]


class WidgetApplicability(Object):
    __classname__ = __maps_to__ = "cs_objdashboard_widget_appl"


DASHBOARD_LAYOUTS = [
    {"name": "m", "columns": ["medium"]},
    {"name": "mm", "columns": ["medium", "medium"]},
    {"name": "mmm", "columns": ["medium", "medium", "medium"]},
    {"name": "sm", "columns": ["small", "medium"]},
    {"name": "ms", "columns": ["medium", "small"]},
    {"name": "mss", "columns": ["medium", "small", "small"]},
    {"name": "sms", "columns": ["small", "medium", "small"]},
    {"name": "ssm", "columns": ["small", "small", "medium"]},
    {"name": "mmmm", "columns": ["medium", "medium", "medium", "medium"]},
]
