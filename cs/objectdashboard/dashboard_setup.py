#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import cdbwrapc
from cdb import sig, sqlapi, transactions, util
from cdb.objects import Object, Reference_N

from cs.objectdashboard import forwarded_classes as fc
from cs.objectdashboard.config import DashboardConfig, DashboardDefaultConfig
from cs.objectdashboard.dashboard import GET_REFERENCE_CLASSNAMES


def _copy_objects_referenced_by_dashboard_config(default_conf, new_conf):
    """
    Copies for given DashboardDefaultConfig all referenced objects collected
    by emitted signal ``cs.objectdashboard.dashboard.GET_REFERENCE_CLASSNAMES``
    for given DashboardConfig.

    :param default_conf: default dashboard configuration checked for references
                         that have to be copied for the new dashboard config
    :type default_conf: cs.objectdashboard.config.DashboardDefaultConfig

    :param new_conf: dashboard configuration for which referenced objects of
                     default dashboard config are copied
    :type new_conf: cs.objectdashboard.config.DashboardConfig

    Referenced classes have to register against the signal
    GET_REFERENCE_CLASSNAMES to be considered by this method:

    .. rubric :: Example
    .. code-block :: python

        from cdb import sig
        from cdb.objects import Object
        from cs.objectdashboard.dashboard import GET_REFERENCE_CLASSNAMES

        class ExampleClass(Object):
            ...

        @sig.connect(GET_REFERENCE_CLASSNAMES)
        def register_class_def():
            "Register class definition"
            return ExampleClass

    .. note ::

        Helper function, only used internally if DashboardConfigs are created
        from DashboardDefaultConfigs.
    """

    # collect all classes registered as references for dashboard configs
    for registered_class in sig.emit(GET_REFERENCE_CLASSNAMES)():
        # Create a copy of referenced object of DashboardDefaultConfig
        # for DashboardConfig
        referenced_objects = registered_class.KeywordQuery(
            cdb_config_id=default_conf.cdb_object_id
        )
        for obj in referenced_objects:
            # intentionally copy without access check
            cref = obj.Copy(cdb_config_id=new_conf.cdb_object_id)
            # also copy any Long Text Attributes, since there are not copied
            # per default by a simple Copy
            for textFieldName in obj.GetTextFieldNames():
                cref.SetText(textFieldName, obj.GetText(textFieldName))


class DashboardDefault(Object):
    """
    Context class for ``DashboardDefaultConfig`` entries that serves as
    a container for default configurations for a single class.
    """

    __classname__ = __maps_to__ = "cs_objdashboard_default"

    ConfigEntries = Reference_N(
        fc.DashboardDefaultConfig,
        fc.DashboardDefaultConfig.context_object_id
        == fc.DashboardDefault.cdb_object_id,
    )

    def get_template_classname(self):
        return self.classname

    def _get_empty_context_object_ids(self):
        """
        :returns: ``cdb_object_id``s of entries of class ``self.classname``
            without corresponding ``DashboardConfig`` entries.
        :rtype: list
        """
        if self.classname:
            table_name = cdbwrapc.getPrimaryTableForClass(self.classname)
        else:
            table_name = None

        if table_name:
            records = sqlapi.RecordSet2(
                sql="""
                    SELECT cdb_object_id
                    FROM {table_name}
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {config_table}
                        WHERE {config_table}.context_object_id
                            = {table_name}.cdb_object_id
                    )
                    """.format(
                    table_name=table_name,
                    config_table=DashboardConfig.__maps_to__,
                )
            )
            return [record.cdb_object_id for record in records]
        else:
            raise util.ErrorMessage("cs_objdashboard_no_relation")

    def on_cs_objdashboard_apply_default_now(self, ctx):
        """
        Applies this default configuration to objects of ``self.classname``
        that do not already have a dashboard configuration.

        Finally, the user is shown how many objects were affected.

        .. note ::
            Will not have any effect if this default configuration has no
            configuration entry.
        """
        if not self.ConfigEntries:
            return

        context_oids = self._get_empty_context_object_ids()
        vals = DashboardDefaultConfig.MakeChangeControlAttributes()

        with transactions.Transaction():
            for config in self.ConfigEntries:
                config_vals = dict(config)
                del config_vals["cdb_object_id"]
                config_vals.update(vals)

                for context_oid in context_oids:
                    # a single INSERT statement would be optimal,
                    # but would require generating cdb_object_ids on the fly
                    config_vals["context_object_id"] = context_oid
                    dashboard_conf = DashboardConfig.Create(**config_vals)

                    # Copy all referenced objects by the default config for the
                    # new dashboard_config
                    _copy_objects_referenced_by_dashboard_config(config, dashboard_conf)

        if ctx:
            msgbox = ctx.MessageBox(
                "cs_objdashboard_applied_default",
                [len(context_oids)],
                "applied_defaults",
                ctx.MessageBox.kMsgBoxIconInformation,
            )
            ctx.show_message(msgbox)


class WithDefaultDashboard:
    """
    Mixin for ``cdb.objects.Object`` classes that instantiates the current
    default dashboard configuration after creating or copying an object of
    this class.
    """

    def _create_default_widgets(self, ctx=None):
        """
        Creates dashboard configuration for ``self`` based on the default
        configuration.
        """
        # new from template: if the template has an object dashboard
        # configuration it gets copied with all other related objects.
        # else create configuration from default configuration

        template = None
        if ctx:
            template = getattr(ctx, "cdbtemplate", None)
        # If the template has dashboard configurations ...
        if template and self.has_obj_dashboard_config(
            getattr(template, "cdb_object_id", "")
        ):
            # ... copy dashboard configs without access check
            dashboardConfigurations = DashboardConfig.KeywordQuery(
                context_object_id=template.cdb_object_id
            )
            with transactions.Transaction():
                for config in dashboardConfigurations:
                    new_conf = config.Copy(context_object_id=self.cdb_object_id)
                    _copy_objects_referenced_by_dashboard_config(config, new_conf)
            return

        # If there is no template or the template has no dashboard config ...
        # ... get the default dashboard config ...
        default_config = fc.DashboardDefault.ByKeys(classname=self._getClassname())
        # ... if there is none, no dashboard configs are created/copied
        if not default_config:
            return

        # ... if there is one, copy its dashboard configs without access check
        for config in default_config.ConfigEntries:
            # Create dashboard entries by copying everything from the default
            # dashboard config

            desc = {
                "component_name": config.component_name,
                "settings": config.settings,
                "xpos": config.xpos,
                "ypos": config.ypos,
            }
            dashboard_conf = DashboardConfig.create_from_description(
                desc,
                self.cdb_object_id,
            )
            # Copy all referenced objects by the default config for the
            # new dashboard_config
            _copy_objects_referenced_by_dashboard_config(config, dashboard_conf)

    @staticmethod
    def has_obj_dashboard_config(context_object_id):
        """
        Check if a dashboard configuration exists for a given context ID.

        :param context_object_id: ``cdb_object_id`` to check the existence of
            a dashboard configuration for
        :type context_object_id: basestring

        :returns: ``True`` if any configuration exists; ``False`` otherwise
        :rtype: bool
        """
        if not context_object_id:
            return False

        dashboard_config = DashboardConfig.KeywordQuery(
            context_object_id=context_object_id
        )
        return bool(dashboard_config)

    event_map = {
        (("create", "copy"), "post"): "_create_default_widgets",
    }
