# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
REST usage
----------

To use enhancement plugins in REST usecase (e.g. `BomTable`) a registration has to be done
for the specific scopes.
The plugin gets only loaded in the provided scopes. The register also respects all dependencies
of the plugins.

For cs.vp scopes for the `BomTable` and child components are provided
:class:`cs.vp.bom.enhancement.register.BomTableScope`.
If you want to use own scopes for custom REST endpoints you can use any kind of strings as scopes.

Also, the plugins can load `default_data` for the `BomTable` for this the plugins need to be
in the special scope `INIT`.
See :meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.create_for_default_data`,
:meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.get_default_data`

Example
^^^^^^^

.. code-block:: python

    from cs.vp.bom.bomqueries_plugins import EffectivityDatesPlugin
    from cs.vp.bom.enhancement.register import PluginRegister, BomTableScope

    PluginRegister().register_plugin(
        EffectivityDatesPlugin,
        [
            BomTableScope.LOAD,
            BomTableScope.SEARCH,
            BomTableScope.DIFF_LOAD,
            BomTableScope.DIFF_SEARCH,
            BomTableScope.MAPPING,
            BomTableScope.FIND_LBOMS,
            BomTableScope.SYNC_LBOM,
            BomTableScope.SYNC_RBOM,
        ],
    )
"""

# Exported objects
__all__ = [
    "BomTableScope",
    "ScopeType",
    "PluginRegisterData",
    "PluginRegister",
]

import enum
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Type, Generator, Optional, Sequence

from cs.vp.bom.enhancement import plugin

LOG = logging.getLogger(__name__)


class BomTableScope(enum.StrEnum):
    """
    Scopes used by `BomTable` REST endpoints to retrieve plugins for enhancement of the internal bom queries.
    """

    INIT = enum.auto()
    """
    Plugins in this scope are loaded during initialize of the `BomTable`. 
    Here plugins **have to be** registered if you want to use 
    :meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.get_default_data`.
    """

    LOAD = enum.auto()
    """
    Plugins in this scope are loaded during every data loading of the `BomTable`.
    This includes the first loading of the root item child's and then for every expanding of different levels.
    Also during a reload of the `BomTable` this scope is used.
    """

    SEARCH = enum.auto()
    """
    Plugins in this scope are loaded during the request of the `SearchStepper` of the `BomTable`.
    """

    DIFF_LOAD = enum.auto()
    """
    Plugins in this scope are loaded during the data loading of the difference table in the `xBOM Manager`.
    """

    DIFF_SEARCH = enum.auto()
    """
    Plugins in this scope are loaded during the search request of the difference table in the `xBOM Manager`.
    """

    MAPPING = enum.auto()
    """
    Plugins in this scope are loaded during the `mapping` operation in the `xBOM Manager`.
    """

    FIND_LBOMS = enum.auto()
    """
    Plugins in this scope are loaded during the ``find lbom`` operation in the `xBOM Manager`.
    """

    SYNC_LBOM = enum.auto()
    """
    Plugins in this scope are loaded during the ``sync lbom`` operation in the `xBOM Manager`.
    """

    SYNC_RBOM = enum.auto()
    """
    Plugins in this scope are loaded during the ``sync rbom`` operation in the `xBOM Manager`.
    """


ScopeType = BomTableScope | str


@dataclass(frozen=True)
class PluginRegisterData:
    """
    Dataclass to hold registered plugin class references
    :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin`
    with scope (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`).
    """

    scope: ScopeType
    """
    Scope of the registered plugin class.
    """

    plugin_cls: Type[plugin.AbstractRestPlugin]
    """
    Plugin class reference.
    """


class PluginRegister:
    """
    Register for plugins :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` in different scopes
    :class:`cs.vp.bom.enhancement.register.BomTableScope`.
    This register is used to lookup which plugins to load during the different REST scopes.

    Use :meth:`cs.vp.bom.enhancement.register.PluginRegister.register_plugin` to register your plugins for
    different scopes :class:`cs.vp.bom.enhancement.register.BomTableScope`.
    """

    _instance: "PluginRegister" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self) -> None:
        # init is called every time after __new__ so avoid reset guard all with hasattr
        if not hasattr(self, "plugin_list"):
            self.plugin_list: list[PluginRegisterData] = []

        if not hasattr(self, "plugins_to_register"):
            self.plugins_to_register: list[PluginRegisterData] = []

        if not hasattr(self, "plugins_to_unregister"):
            self.plugins_to_unregister: dict[
                Optional[ScopeType], set[Type[plugin.AbstractRestPlugin]]
            ] = defaultdict(set)

        if not hasattr(self, "is_registration_closed"):
            self.is_registration_closed = False

    def _raise_if_registration_closed(self) -> None:
        """
        Check if the registration is closed and raises an RuntimeError if it is.

        :raises RuntimeError: if the registration is closed after call to
                              :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`
        """
        if self.is_registration_closed:
            raise RuntimeError(
                "Registration is closed. No more (un)registration possible"
            )

    def register_plugin(
        self,
        plugin_cls: Type[plugin.AbstractRestPlugin],
        scope: ScopeType | Sequence[ScopeType],
    ) -> None:
        """
        Register a plugin class :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` in different scopes
        (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`).
        The dependencies of the registered plugin will be automatically also registered.
        This will happen after the call to
        :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`.
        The registered plugin could also be marked for unregister
        :meth:`cs.vp.bom.enhancement.register.PluginRegister.unregister_plugin` then this plugin and
        all dependencies of this plugin will **not** be added.

        If `scope` is a list then the plugin (and all its dependencies) is registered for all the scopes.

        :param plugin_cls: class reference for a plugin to be registered
        :param scope: can be any predefined enum from :class:`cs.vp.bom.enhancement.register.BomTableScope`
                      or any string. Latter is used to use own scopes. Can also be an iterable of these types.

        :raises RuntimeError: if the registration is closed after call to
                              :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`
        """
        self._raise_if_registration_closed()

        if isinstance(scope, str):
            scope = {scope}

        for each_scope in scope:
            self.plugins_to_register.append(
                PluginRegisterData(plugin_cls=plugin_cls, scope=each_scope)
            )

    def unregister_plugin(
        self,
        plugin_cls: Type[plugin.AbstractRestPlugin],
        scope: Optional[ScopeType | Sequence[ScopeType]] = None,
    ) -> None:
        """
        Unregister a plugin class :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` in different scopes
        (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`).
        The dependencies of the unregistered plugin will then be ignored.
        This will happen after the call to
        :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`.

        If `scope` is a list then the plugin is unregistered for all the scopes.
        If `scope` is `None` then the plugin will be unregistered in **any** scope where it is found.

        :param plugin_cls: class reference for a plugin to be unregistered
        :param scope: can be any predefined enum from :class:`cs.vp.bom.enhancement.register.BomTableScope`
                      or any string. Latter is used to use own scopes. Can also be an iterable of these types.

        :raises RuntimeError: if the registration is closed after call to
                              :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`
        """
        self._raise_if_registration_closed()

        # None is the wildcard for **any** scope
        if isinstance(scope, str) or scope is None:
            scope = {scope}

        for each_scope in scope:
            self.plugins_to_unregister[each_scope].add(plugin_cls)

    def close_registration(self) -> None:
        """
        Closes the registration. If the registration is already closed nothing is done.
        
        Will be handled automatic if :class:`cs.vp.bom.enhancement.FlatBomRestEnhancement` is used.

        All plugins which are marked for registration
        :meth:`cs.vp.bom.enhancement.register.PluginRegister.register_plugin` will be filtered based on the
        unregister data :meth:`cs.vp.bom.enhancement.register.PluginRegister.unregister_plugin`.
        All plugins which are not filtered are added with their dependencies to the final registration.
        """
        if self.is_registration_closed:
            return

        LOG.debug(
            "close registration:\nplugins_to_register:%s\nplugins_to_unregister:%s",
            self.plugins_to_register,
            self.plugins_to_unregister,
        )

        for plugin_to_register in self.plugins_to_register:
            if (
                plugin_to_register.plugin_cls
                in self.plugins_to_unregister[plugin_to_register.scope]
                # None is the wildcard for **any** scope
                or plugin_to_register.plugin_cls in self.plugins_to_unregister[None]
            ):
                LOG.debug(
                    "Skip plugin '%s' because it was marked for unregister",
                    plugin_to_register,
                )
            else:
                self._register_single_plugin(plugin_to_register)

        self.plugins_to_register.clear()
        self.plugins_to_unregister.clear()
        self.is_registration_closed = True
        LOG.debug("close registration finished:\n%s", self.plugin_list)

    def _register_single_plugin(self, plugin_data: PluginRegisterData) -> None:
        """
        Register a plugin class :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` in a scope
        (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`).
        The dependencies of the registered plugin will be automatically also registered.

        this method is called recursively

        :param plugin_data: :class:`cs.vp.bom.enhancement.register.PluginRegisterData`
        """
        if plugin_data in self:
            LOG.debug("Skip plugin '%s' because it is already registered", plugin_data)
            return

        self.plugin_list.append(plugin_data)
        LOG.debug("Plugin '%s' added", plugin_data)

        # register also all dependencies
        for each_required in plugin_data.plugin_cls.DEPENDENCIES:
            self._register_single_plugin(
                PluginRegisterData(plugin_cls=each_required, scope=plugin_data.scope)
            )

    def scope_generator(
        self, scope: ScopeType
    ) -> Generator[PluginRegisterData, None, None]:
        """
        Generator to iterate over all registered plugin defined for the given scope
        (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`).

        :param scope: can be any predefined enum from :class:`cs.vp.bom.enhancement.register.BomTableScope`
                      or any string. Latter is used to use own scopes.

        :return: generator which yields :class:`cs.vp.bom.enhancement.register.PluginRegisterData`
        """
        for cls in self.plugin_list:
            if cls.scope == scope:
                yield cls

    def dependency_reverse_walker(
        self, scope: ScopeType
    ) -> Generator[PluginRegisterData, None, None]:
        """
        Generator to iterate over all registered plugin defined for the given scope
        (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`) in **dependency order**.

        :param scope: can be any predefined enum from :class:`cs.vp.bom.enhancement.register.BomTableScope`
                      or any string. Latter is used to use own scopes.

        :return: generator which yields :class:`cs.vp.bom.enhancement.register.PluginRegisterData`
        """
        known_plugins = []

        for each_p in self.scope_generator(scope):
            for each_yield in self.dependency_plugin_walker(each_p):
                if each_yield not in known_plugins:
                    known_plugins.append(each_yield)
                    yield each_yield

    def dependency_plugin_walker(
        self, plugin_data: PluginRegisterData, include_self: bool = True
    ) -> Generator[PluginRegisterData, None, None]:
        """
        Generator to iterate over all dependency plugins for the given plugin register data
        and scope (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`)
        in **dependency order**.

        :param plugin_data: :class:`cs.vp.bom.enhancement.register.PluginRegisterData`
        :param include_self: Flag if the plugin instance of the given plugin class should be included

        :return: generator which yields :class:`cs.vp.bom.enhancement.register.PluginRegisterData`
        """
        for each_p_class in plugin_data.plugin_cls.DEPENDENCIES:
            sub_plugin = self.get_plugin_data(each_p_class, plugin_data.scope)
            if sub_plugin is None:  # Really possible?!
                continue

            yield from self.dependency_plugin_walker(sub_plugin)
        if include_self:
            yield plugin_data

    def get_plugin_data(
        self, plugin_cls: Type[plugin.AbstractRestPlugin], scope: ScopeType
    ) -> Optional[PluginRegisterData]:
        """
        Generator to iterate over all plugins for the given plugin class
        :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` and the given scope
        (:class:`cs.vp.bom.enhancement.register.BomTableScope` or `str`).

        :param plugin_cls: class reference for a plugin to be registered
        :param scope: can be any predefined enum from :class:`cs.vp.bom.enhancement.register.BomTableScope`
                      or any string. Latter is used to use own scopes

        :return: :class:`cs.vp.bom.enhancement.register.PluginRegisterData`
        """
        for each_plugin in self.scope_generator(scope):
            if each_plugin.plugin_cls == plugin_cls:
                return each_plugin
        return None

    def __contains__(self, item: PluginRegisterData) -> bool:
        """
        Checks if a :class:`cs.vp.bom.enhancement.register.PluginRegisterData` is already registered.
        Does only correctly work after call to
        :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`.

        :param item: :class:`cs.vp.bom.enhancement.register.PluginRegisterData`

        :return: True if element is already registered does only correctly work after call to
                 :meth:`cs.vp.bom.enhancement.register.PluginRegister.close_registration`
        """
        for each_plugin in self.plugin_list:
            if each_plugin == item:
                return True
        return False
