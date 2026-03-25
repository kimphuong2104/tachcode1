# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
The module contains functionality that deals with the Web UI
plugin configuration.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb.objects import Object, Forward, Reference, Reference_1, Reference_N, ReferenceMethods_N, N, OBJECT_STORE
from cdb.platform.mom import entities
from cdb import misc
from cdb import tools
from cdb import ue, sqlapi
from cs.web.components import library_config

# Exported objects
__all__ = []

fCsweb_plugin = Forward(__name__ + ".Csweb_plugin")
fCsweb_plugin_config = Forward(__name__ + ".Csweb_plugin_config")
fCsweb_plugin_config_library = Forward(__name__ + ".Csweb_plugin_config_library")
fCsweb_plugin_libs = Forward(__name__ + ".Csweb_plugin_libs")


class Csweb_plugin_libs(Object):
    __maps_to__ = "csweb_plugin_libs"
    __classname__ = "csweb_plugin_libs"

    Library = Reference_1(library_config.Libraries, fCsweb_plugin_libs.library_name)


class Csweb_plugin_config(Object):
    __maps_to__ = "csweb_plugin_config"
    __classname__ = "csweb_plugin_config"

    Libraries = Reference(N, fCsweb_plugin_config_library,
                          fCsweb_plugin_config_library.plugin_id == fCsweb_plugin_config.plugin_id,
                          fCsweb_plugin_config_library.discriminator == fCsweb_plugin_config.discriminator)

    def get_libraries(self):
        qry = ("SELECT l.*"
               " FROM csweb_libraries l INNER JOIN csweb_plugin_libs cl"
               " ON l.library_name = cl.library_name"
               " WHERE cl.plugin_id = '%s'"
               " AND cl.discriminator = '%s'"
               " ORDER BY cl.pos_nr"
               % (sqlapi.quote(self.plugin_id), sqlapi.quote(self.discriminator)))
        return library_config.Libraries.SQL(qry)

    PluginLibraries = ReferenceMethods_N(library_config.Libraries, get_libraries)

    Plugin = Reference(1, fCsweb_plugin, fCsweb_plugin_config.plugin_id)

    def _check_values(self, ctx):
        c = self.Plugin.get_callable()
        if c:
            c.check_values(ctx)

    event_map = {
        (("modify", "create", "copy"), "pre"): "_check_values"
    }


class Csweb_plugin(Object):
    __maps_to__ = "csweb_plugin"
    __classname__ = "csweb_plugin"

    Configurations = Reference(N, fCsweb_plugin_config,
                               fCsweb_plugin_config.plugin_id == fCsweb_plugin.plugin_id,
                               order_by=-Csweb_plugin_config.priority)

    # Dictionary that caches configuration information
    _configs = {}

    @classmethod
    def get_plugin_config(cls, plugin_id):
        """
        Retrieve the configuration for the plugin with the given `plugin_id`
        using the `get_config` method of the plugin. The content of the result
        is described there.
        This method caches the result to optimize the performance.
        The function returns ``None`` if there is no Web UI configuration
        for the given `plugin_id`.
        """
        if plugin_id in cls._configs:
            return cls._configs[plugin_id]

        plugin = cls.ByKeys(plugin_id)
        if plugin:
            result = plugin.get_config()
            cls._configs[plugin_id] = result
        else:
            result = None
        return result

    @classmethod
    def clear_cache(cls):
        """
        Clear the cache used by `get_plugin_config`.
        """
        OBJECT_STORE.clear()
        cls._configs = {}

    def get_config(self):
        """
        Retrieve the configuration for the plugin.
        The function will return a list of dictionaries ordered by the
        priority of the plugin configurations. Eeach dictionary contains the
        attributes ``discriminator``, ``component`` and ``setup`` of type
        string and  the attribute ``libraries`` that contains a list of tuples
        of a library name and its version.
        The values depends on the WEB UI plugin configuration.
        """
        clb = self.get_callable()
        result = [clb.generate_config(conf) for conf in self.Configurations]
        return self.get_callable().adapt_config(result)

    def get_callable(self):
        """
        Returns the object specified in `self.fqpyname` or
        the standard callable `WebUIPluginCallbackBase`
        if no fqpyname is specified.
        Raises an `ue.Exception` if the configuration for
        the callable is wrong.
        """
        result = WebUIPluginCallbackBase
        if self.fqpyname:
            try:
                result = tools.getObjectByName(self.fqpyname)
            except Exception as e:
                raise ue.Exception("csweb_err_plugin_fqpyname", self.fqpyname, repr(e))
            try:
                if not issubclass(result, WebUIPluginCallbackBase):
                    raise ue.Exception("csweb_err_plugin_fqpyname_derived", self.fqpyname)
            except TypeError:
                # issubclass raises an exception if cls is not a class
                raise ue.Exception("csweb_err_plugin_fqpyname_derived", self.fqpyname)
        return result

    def _check_fqpyname(self, ctx):
        """
        Check if fqpyname is set and the class is derived from
        WebUIPluginCallbackBase. `get_callable` will raise the
        exceptions for us.
        """
        self.get_callable()

    event_map = {
        (("modify", "create", "copy"), "pre"): "_check_fqpyname"
    }


class Csweb_plugin_config_library(Object):
    __maps_to__ = "csweb_plugin_config_library"
    __classname__ = "csweb_plugin_config_library"


class WebUIPluginCallbackBase(object):
    """
    A class that gives you the opportunity to
    customize the configuration of plugins.
    You should derive from this class to implement your
    own plugin behaviour.
    """

    @classmethod
    def check_values(cls, ctx):
        """
        This function is called as a part of the ``pre`` userexit of
        a plugin configuration. Overwrite this function if you want
        to do additional checks for the values the user has entered.
        If the checks are not ok, raise an exception.
        """
        pass

    @classmethod
    def adapt_config(cls, plugin_configs):
        """
        This callback allows you to manipulate the list `plugin_configs`
        after the configuration has been read from the database.
        The function returns the adapted list - it is allowed to change
        plugin_config in place and return this list.
        """
        return plugin_configs

    @classmethod
    def generate_config(cls, plugin_config):
        """
        This callback allows you to overwrite the generation of a single
        configuration entry. `plugin_config_entry` is an object of type
        `csweb_plugin_config`. The default implementation returns a
        dictionary that contains at least the attribute ``discriminator``.
        The attributes ``component``, ``libraries``  and ``setup`` are
        set if the configuration contains a value.
        """
        config = {"discriminator": plugin_config.discriminator}
        if plugin_config.component:
            config["component"] = plugin_config.component
        if plugin_config.setup_fqpyname:
            config["setup"] = plugin_config.setup_fqpyname
        plugin_libraries = plugin_config.PluginLibraries
        libraries = [(library.library_name, library.library_version) for
                     library in plugin_config.Libraries]
        config["libraries"] = []
        if libraries or plugin_libraries:
            config["libraries"] = libraries
            for l in plugin_libraries:
                for lib_dep in library_config.get_dependencies(l):
                    if lib_dep not in config["libraries"]:
                        config["libraries"].append((lib_dep.library_name, lib_dep.library_version))
        return config


class WebUIPluginCallbackClassTileSmall(WebUIPluginCallbackBase):
    """
    PlugIn to manage plugins with the id ``class-tile_small``
    """

    @classmethod
    def check_values(cls, ctx):
        """
        Check if the discriminator is a valid regular expression.
        """
        discriminator = getattr(ctx.dialog, "discriminator", None)
        if discriminator:
            if not entities.Entity.ByKeys(discriminator):
                raise ue.Exception("csweb_err_classtilesmall_discriminator")

    @classmethod
    def adapt_config(cls, plugin_configs):
        """
        This callback allows you to manipulate the plugin_config list
        after the configuration has been read from the database.
        """

        def _add_subclass_config(config, plugin_configs):
            """
            The function checks if the class of `config` has subclasses
            where no specialized configuration is done. For each of this
            classes a copy of the configuration is added to plugin_configs
            """
            conf_clname = config["discriminator"]
            try:
                conf_cldef = entities.CDBClassDef(conf_clname)
                subclasses = conf_cldef.getSubClassNames(False)
                if subclasses:
                    ccn = set(pc["discriminator"] for pc in plugin_configs)
                    for subclass in subclasses:
                        if subclass not in ccn:
                            # Copy configuration
                            new_config = dict(config)
                            new_config["discriminator"] = subclass
                            plugin_configs.append(new_config)
            except NameError as e:
                misc.log_error("Failed to retrieve subclasses of %s:%s" %
                               (config.discriminator, e))

        # Note that adapt_config will append values to plugin_configs
        # It is ok to iterate over this new values because the subclasses
        # added to the list might have own subclasses
        for config in plugin_configs:
            _add_subclass_config(config, plugin_configs)
        return plugin_configs
