# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
General
-------

The enhancement API enables you to enhance functionality of BOM queries.
It can be used to enhance BOM queries on base of sql extensions or with filter with python functions.
Also, additional attributes for the BOM query results can be added.

Example for usage
-----------------

.. code-block:: python

    import datetime

    from cs.vp.items import Item

    from cs.vp.bom.bomqueries import flat_bom
    from cs.vp.bom.bomqueries_plugins import EffectivityDatesPlugin, FilterFunctionPlugin
    from cs.vp.bom.enhancement import FlatBomEnhancement

    bom_enhancement = FlatBomEnhancement()

    bom_enhancement.add(
        EffectivityDatesPlugin(
            valid_from=datetime.datetime.strptime("2021-08-17", "%Y-%m-%d")
        )
    )


    def bomfilter_function(bom_item_records):
        # Add your filter logic here
        return bom_item_records


    bom_enhancement.add(FilterFunctionPlugin(bomfilter_function))

    # Provide here your root item
    root_item = Item.Query()[0]

    filtered_flat_bom = flat_bom(root_item, bom_enhancement=bom_enhancement)


Possibilities for creating own plugins
--------------------------------------

Enhance the SQL
^^^^^^^^^^^^^^^

.. code-block:: sql
    :caption: Example pseudo sql to show possibilities to extend sql (see table below for references to variables <>)

    SELECT AbstractPlugin.BOM_ITEM_TABLE_ALIAS.*<bom_item_select_stmt_extension>
        FROM einzelteile AbstractPlugin.BOM_ITEM_TABLE_ALIAS
    <sql_join_stmt_extension>
    WHERE (assembly_statement)
        AND (<part_where_stmt_extension>)
        AND (<bom_item_where_stmt_extension>)

+--------------------------------+-------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------+
| Variable name                  | Enhancement                                                                         | Plugin                                                                                 |
+================================+=====================================================================================+========================================================================================+
| bom_item_select_stmt_extension | :meth:`cs.vp.bom.enhancement.FlatBomEnhancement.get_bom_item_select_stmt_extension` | :meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_bom_item_select_stmt_extension` |
+--------------------------------+-------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------+
| sql_join_stmt_extension        | :meth:`cs.vp.bom.enhancement.FlatBomEnhancement.get_sql_join_stmt_extension`        | :meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_sql_join_stmt_extension`        |
+--------------------------------+-------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------+
| part_where_stmt_extension      | :meth:`cs.vp.bom.enhancement.FlatBomEnhancement.get_part_where_stmt_extension`      | :meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_part_where_stmt_extension`      |
+--------------------------------+-------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------+
| bom_item_where_stmt_extension  | :meth:`cs.vp.bom.enhancement.FlatBomEnhancement.get_bom_item_where_stmt_extension`  | :meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_bom_item_where_stmt_extension`  |
+--------------------------------+-------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------+

Filter with python functions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Used to filter bom_item (einzelteile) records.

FlatBomEnhancement
    :meth:`cs.vp.bom.enhancement.FlatBomEnhancement.filter_bom_item_records`

Plugin
    :meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.filter_bom_item_records`

Add additional attributes
^^^^^^^^^^^^^^^^^^^^^^^^^

Used to retrieve additional attributes for the bom_item (einzelteile).

FlatBomEnhancement
    :meth:`cs.vp.bom.enhancement.FlatBomEnhancement.get_additional_bom_item_attributes`

Plugin
    :meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_additional_bom_item_attributes`
"""

# Exported objects
__all__ = [
    "get_bom_enhancement_data_from_request",
    "FlatBomEnhancement",
    "FlatBomRestEnhancement",
    "EnhancementPluginError",
]

from typing import Type, Any, Optional
from morepath import Request

from cdb.sqlapi import Record

from cs.vp.bom.enhancement import plugin, register
from cs.vp.bom.enhancement.exceptions import EnhancementPluginError


def get_bom_enhancement_data_from_request(request: Request) -> dict[str, Any]:
    """
    Extracts the bom enhancement data from a REST request (POST json key: `bomEnhancementData`).

    :param request: morepath request

    :return: dict with first level keys to be the plugin discriminators and
             the values the plugin corresponding data.
             Return an empty dict if no bom enhancement data exists.
    """
    return request.json.get("bomEnhancementData", {})


class FlatBomEnhancement:
    """
    Class to manage different plugins which can be used to enhance bom queries

    :return: a constructed :class:`cs.vp.bom.enhancement.FlatBomEnhancement` object
    """

    def __init__(self):
        self.statement_cache: dict[str, str] = {}
        self.plugins: dict[Type[plugin.AbstractPlugin], plugin.AbstractPlugin] = {}

    def __contains__(self, plugin_class: Type[plugin.AbstractPlugin]) -> bool:
        """
        Check if enhancement has plugin.

        :param plugin_class: plugin class to check

        :return: True if a plugin with the given type has already been added, otherwise False
        """
        return plugin_class in self.plugins

    def add(self, plugin_object: plugin.AbstractPlugin) -> None:
        """
        Add a plugin to the enhancement.
        Only one constructed object of a plugin class is allowed to be added.

        :param plugin_object: constructed object of type :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin`

        :raises: ValueError:
            If already a constructed object of a plugin class exists or
            if two plugins are added that implement a component join extension
        """

        from cs.vp.bom.bomqueries_plugins import ComponentJoinPlugin

        plugin_class = type(plugin_object)

        if plugin_class in self.plugins:
            raise ValueError(
                "plugin {0} already created".format(
                    plugin_class.__module__ + "." + plugin_class.__qualname__
                )
            )

        if isinstance(plugin_object, ComponentJoinPlugin):
            for plugin in self.plugins.values():
                if isinstance(plugin, ComponentJoinPlugin):
                    registed_plugin_class = type(plugin)
                    raise ValueError(
                        "Only one ComponentJoinPlugin supported: already registerd plugin {}, plugin to be added {}".format(
                            registed_plugin_class.__module__ + "." + registed_plugin_class.__qualname__,
                            plugin_class.__module__ + "." + plugin_class.__qualname__
                        )
                    )

        self.plugins[plugin_class] = plugin_object

    def get_sql_join_stmt_extension(self) -> str:
        """
        Extension for SQL statement to include additional "JOIN" statements for all plugins.
        Each statement of the different plugins
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_sql_join_stmt_extension`)
        gets added together as these are. So each plugin is responsible for providing correct syntax.

        If a plugin returns `None` it will be ignored by this function.

        A plugin that implements this method should provide the table alias names of the joined tables as
        constants to allow other plugins to use this in select or where statement extension.

        See :ref:`Enhance the SQL`

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: Extension for SQL statement to include additional "JOIN" statements
        """

        cache_key = "get_sql_join_stmt_extension"
        if cache_key in self.statement_cache:
            return self.statement_cache[cache_key]

        result = ""

        for each in self.plugins.values():
            try:
                sql_join_stmt_extension = each.get_sql_join_stmt_extension()
            except Exception as ex:
                raise EnhancementPluginError(
                    each, self.get_sql_join_stmt_extension.__name__, self, str(ex)
                ) from ex
            if sql_join_stmt_extension is None:
                continue
            result += sql_join_stmt_extension

        self.statement_cache[cache_key] = result
        return result

    def get_part_where_stmt_extension(self) -> str:
        """
        Extension for SQL statement to include additional "WHERE" condition statement
        for the part (teile_stamm) table for all plugins. Each statement of the different plugins
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_part_where_stmt_extension`)
        gets connected with AND.

        If a plugin returns `None` it will be ignored by this function.

        See :ref:`Enhance the SQL`

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: SQL "WHERE" condition for the part (teile_stamm) table
        """

        cache_key = "get_part_where_stmt_extension"
        if cache_key in self.statement_cache:
            return self.statement_cache[cache_key]

        result = []

        for each in self.plugins.values():
            try:
                part_where_stmt_extension = each.get_part_where_stmt_extension()
            except Exception as ex:
                raise EnhancementPluginError(
                    each, self.get_part_where_stmt_extension.__name__, self, str(ex)
                ) from ex

            if part_where_stmt_extension is None:
                continue
            result.append("({0})".format(part_where_stmt_extension))

        self.statement_cache[cache_key] = " AND ".join(result) if result else "1=1"
        return self.statement_cache[cache_key]

    def get_bom_item_select_stmt_extension(self) -> str:
        """
        Extension for SQL "SELECT" statement for the bom_item (einzelteile) table for all plugins.
        Each statement of the different plugins
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_bom_item_select_stmt_extension`)
        gets added together as these are. So each plugin is responsible for providing correct syntax.

        If a plugin returns `None` it will be ignored by this function.

        See :ref:`Enhance the SQL`

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: Extension for SQL "SELECT" statement for the bom_item (einzelteile) table
        """

        cache_key = "get_bom_item_select_stmt_extension"
        if cache_key in self.statement_cache:
            return self.statement_cache[cache_key]

        result = ""

        for each in self.plugins.values():
            try:
                bom_item_select_stmt_extension = (
                    each.get_bom_item_select_stmt_extension()
                )
            except Exception as ex:
                raise EnhancementPluginError(
                    each, self.get_bom_item_select_stmt_extension.__name__, self, str(ex)
                ) from ex
            if bom_item_select_stmt_extension is None:
                continue
            result += bom_item_select_stmt_extension

        self.statement_cache[cache_key] = result
        return result

    def get_bom_item_where_stmt_extension(self) -> str:
        """
        Extension for SQL statement to include additional "WHERE" condition statement
        for the bom_item (einzelteile) table for all plugins. Each statement of the different plugins
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_bom_item_where_stmt_extension`)
        gets connected with AND.

        If a plugin returns `None` it will be ignored by this function.

        See :ref:`Enhance the SQL`

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: SQL "WHERE" condition for the bom_item (einzelteile) table
        """

        cache_key = "get_bom_item_where_stmt_extension"
        if cache_key in self.statement_cache:
            return self.statement_cache[cache_key]

        result = []

        for each in self.plugins.values():
            try:
                bom_item_where_stmt_extension = each.get_bom_item_where_stmt_extension()
            except Exception as ex:
                raise EnhancementPluginError(
                    each, self.get_bom_item_where_stmt_extension.__name__, self, str(ex)
                ) from ex
            if bom_item_where_stmt_extension is None:
                continue
            result.append("({0})".format(bom_item_where_stmt_extension))

        self.statement_cache[cache_key] = " AND ".join(result) if result else "1=1"
        return self.statement_cache[cache_key]

    def get_additional_bom_item_attributes(
        self, bom_item_record: Record
    ) -> dict[Any, Any]:
        """
        Used to retrieve additional attributes for the bom_item (einzelteile) table for all plugins.
        Each plugin can return a dict
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.get_additional_bom_item_attributes`)
        and these gets updated together to one dict. So the plugins should take care that
        the dictionary keys are unique.

        If a plugin returns `None` it will be ignored by this function.

        :param bom_item_record: database record of the bom_item

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: dictionary with additional attributes for the bom_item
        """

        result = {}

        for each in self.plugins.values():
            try:
                additional_bom_item_attributes = each.get_additional_bom_item_attributes(
                    bom_item_record
                )
            except Exception as ex:
                raise EnhancementPluginError(
                    each, self.get_additional_bom_item_attributes.__name__, self, str(ex)
                ) from ex
            if additional_bom_item_attributes is None:
                continue
            result.update(additional_bom_item_attributes)

        return result

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        """
        Will call for each plugin
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.filter_bom_item_records`)
        with the currently filtered bom_item_records.

        :param bom_item_records: list with :class:`cdb.sqlapi.Record`

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: filtered list from all plugins with :class:`cdb.sqlapi.Record`
        """
        result = list(bom_item_records)

        for each in self.plugins.values():
            try:
                result = each.filter_bom_item_records(result)
            except Exception as ex:
                raise EnhancementPluginError(
                    each, self.filter_bom_item_records.__name__, self, str(ex)
                ) from ex
        return result

    def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
        """
        Will call for each plugin
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractPlugin.resolve_bom_item_children`)
        with the currently filtered bom_item_record to decide whether the children
        should be resolved further

        With the first plugin that returns false, further processing is aborted and
        all remaining plugins are not called.

        :param bom_item_record: `cdb.sqlapi.Record`

        :raises: `EnhancementPluginError`:
            If a plugin raises any error. Stops execution after first error

        :return: True (default) if the children are resolved or False if not
        """
        for each_plugin in self.plugins.values():
            try:
                if not each_plugin.resolve_bom_item_children(bom_item_record):
                    return False
            except Exception as ex:
                raise EnhancementPluginError(
                    each_plugin, self.resolve_bom_item_children.__name__, self, str(ex)
                ) from ex
        return True


class FlatBomRestEnhancement(FlatBomEnhancement):
    """
    Extension for :class:`cs.vp.bom.enhancement.FlatBomEnhancement` class for usage
    inside of REST endpoints.

    :param scope: can be any predefined enum from :class:`cs.vp.bom.enhancement.register.BomTableScope`
                  or any string. Latter is used to use own scopes.

    :return: a constructed :class:`cs.vp.bom.enhancement.FlatBomRestEnhancement` object
    """

    DEFAULT_ENHANCEMENT_KEY: str = "enhancementData"
    DEFAULT_RESET_DATA_KEY: str = "resetData"

    def __init__(self, scope: register.ScopeType):
        super().__init__()

        self.bom_enhancement_rest_data: Optional[dict[str, Any]] = None
        """
        Dict with first level keys to be the plugin discriminators.
        The value of these keys will then be provided to each plugin
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.create_from_rest_data`).
        """

        self.scope: register.ScopeType = scope

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"scope='{register.BomTableScope(self.scope).name}')"
        )

    def get_plugin_register(self) -> register.PluginRegister:
        """
        Return the plugin register.

        Automatic closes the registration
        :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`.
        """
        plugin_register = register.PluginRegister()
        plugin_register.close_registration()
        return plugin_register

    def get_dependency_plugins(
        self, plugin_cls: Type[plugin.AbstractRestPlugin]
    ) -> dict[Type[plugin.AbstractRestPlugin], Optional[plugin.AbstractRestPlugin]]:
        """
        Return all dependency plugins for the given plugin class reference

        .. note::
             this method works only correctly after the method
             :meth:`cs.vp.bom.enhancement.FlatBomRestEnhancement.initialize_from_request`
             was called

        :param plugin_cls: class reference for a plugin

        :return: dict with dependencies which where requested by the given plugin class reference.
                 key is the class type reference.
                 value is the instanced plugin.

                 .. note::
                     It is guaranteed that this dict contains keys for all given dependencies
                     :attr:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.DEPENDENCIES`.
                     If a dependency does not exist the value is `None`.
        """
        result: dict[
            Type[plugin.AbstractRestPlugin], Optional[plugin.AbstractRestPlugin]
        ] = {}
        plugin_data = self.get_plugin_register().get_plugin_data(plugin_cls, self.scope)
        if plugin_data is None:
            return result

        for each_dep in self.get_plugin_register().dependency_plugin_walker(
            plugin_data, include_self=False
        ):
            result[each_dep.plugin_cls] = self.plugins.get(each_dep.plugin_cls)
        return result

    def get_plugins_default_data(self) -> dict[str, Any]:
        """
        Return the default data for all initialized plugins

        .. note::
            :meth:`cs.vp.bom.enhancement.FlatBomRestEnhancement.initialize_for_default_data` must be called first

        :return: dict with default data for all initialized plugins.
                 key is the :attr:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.DISCRIMINATOR` of the
                 plugin. Value is arbitrary data of the plugin.
        """
        default_data = {}
        default_reset_data = {}

        for each_plugin in self.plugins.values():
            if not isinstance(each_plugin, plugin.AbstractRestPlugin):
                continue

            enhancement_data, reset_data = each_plugin.get_default_data()

            if enhancement_data is not None:
                default_data[each_plugin.DISCRIMINATOR] = enhancement_data
            if reset_data is not None:
                default_reset_data[each_plugin.DISCRIMINATOR] = reset_data

        return {self.DEFAULT_ENHANCEMENT_KEY: default_data,
                self.DEFAULT_RESET_DATA_KEY: default_reset_data}

    def initialize_for_default_data(self, **kwargs: Any) -> None:
        """
        Initialize all plugins registered in the scope of this enhancement for default data generation.
        Will look for plugins in the given scope of this enhancement the plugin register

        :param kwargs: these kwargs are passed to the all plugins
                       registered in the scope of this enhancement method
                       :meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.create_for_default_data`
        """

        plugin_register = self.get_plugin_register()
        for each_plugin in plugin_register.dependency_reverse_walker(self.scope):
            # guard for manuel added plugins via FlatBomEnhancement.add
            if each_plugin.plugin_cls in self.plugins:
                continue

            plugin_object = each_plugin.plugin_cls.create_for_default_data(
                self.get_dependency_plugins(each_plugin.plugin_cls), **kwargs
            )

            if plugin_object is not None:
                self.add(plugin_object)

    def initialize_from_request(self, request: Request) -> None:
        """
        Initialize all plugins registered in the scope of this enhancement with data
        (POST json key: `bomEnhancementData`) of the request.

        The data needs to a dict with first level keys to be the plugin discriminators.
        The value of these keys will then be provided to each plugin
        (:meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.create_from_rest_data`).

        Will look for plugins in the given scope of this enhancement the plugin register

        :param request: morepath request
        """
        bom_enhancement_data = get_bom_enhancement_data_from_request(request)
        self.initialize_plugins_with_rest_data(bom_enhancement_data)

    def initialize_plugins_with_rest_data(
        self,
        bom_enhancement_rest_data: dict[str, Any],
    ) -> None:
        """
        Initialize all plugins registered in the scope of this enhancement with given REST data.

        :param bom_enhancement_rest_data: dict with first level keys to be the plugin discriminators.
                                          The value of these keys will then be provided to each plugin
                                          (:meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.create_from_rest_data`).
        """
        self.bom_enhancement_rest_data = bom_enhancement_rest_data

        for each_plugin in self.get_plugin_register().dependency_reverse_walker(
            self.scope
        ):
            # guard for manuel added plugins via FlatBomEnhancement.add
            if each_plugin.plugin_cls in self.plugins:
                continue

            plugin_object = self._initialize_plugin_with_rest_data(
                each_plugin.plugin_cls
            )

            if plugin_object is not None:
                self.add(plugin_object)

    def _initialize_plugin_with_rest_data(
        self,
        plugin_cls: Type[plugin.AbstractRestPlugin],
    ) -> Optional[plugin.AbstractRestPlugin]:
        """
        Initialize given plugin class reference with REST data stored in enhancement
        :attr:`cs.vp.bom.enhancement.FlatBomRestEnhancement.bom_enhancement_rest_data`.

        :param plugin_cls: class reference for a plugin to be registered
        """
        rest_data = None
        if self.bom_enhancement_rest_data is not None:
            rest_data = self.bom_enhancement_rest_data.get(
                plugin_cls.DISCRIMINATOR, None
            )
        return plugin_cls.create_from_rest_data(
            rest_data, self.get_dependency_plugins(plugin_cls)
        )
