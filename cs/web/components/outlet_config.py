#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Handling of Web UI outlets
"""

from __future__ import absolute_import
import six

__revision__ = "$Id$"

from collections import defaultdict
from copy import deepcopy

import cdbwrapc
import os
from cdb import auth
from cdb import sig
from cdb import sqlapi
from cdb import tools
from cdb import ue
from cdb import util
from cdb import cdbuuid
from cdb.objects import Object, Reference_1, Reference_N, Forward, ReferenceMethods_N
from cdb.platform.gui import Label, Icon
from .configuration_helpers import WithComponentOrConfiguration, WithJsonProperties
from cs.platform.web.rest import support
from cs.web.components.library_config import Libraries, get_dependencies
from cs.web.components.plugin_config import Csweb_plugin
from .library_config import _get_script_urls

OutletDescription = Forward(__name__ + ".OutletDescription")
OutletDefinition = Forward(__name__ + ".OutletDefinition")
OutletPosition = Forward(__name__ + ".OutletPosition")
OutletPositionOwner = Forward(__name__ + ".OutletPositionOwner")
OutletChild = Forward(__name__ + ".OutletChild")
fOutletChildLibs = Forward(__name__ + ".OutletChildLibs")


class OutletPositionCallbackBase(object):
    """
    A class that gives you the opportunity to
    customize the configuration of outlets.
    You should derive from this class to implement your
    own behaviour if you have configured a fqpyname in
    the OutletPosition.
    """

    needs_object = True

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        """
        This callback allows you to manipulate the configuration of the
        position. You may change `pos_config` or return a list of dictionaries
        that should be used instead of this configuration.
        `cldef` is the class definition of the object `obj` that contains the
        data displayed by the outlet.
        """
        return pos_config

    @classmethod
    def adapt_final_config(cls, component_config, cldef, obj):
        """
        This callback allows you to manipulate the configuration of the
        position after the configuration had been transferred to the form
        that will be transferred to the frontend. You have to change
        component_config in place.
        `cldef` is the class definition of the object `obj` that contains the
        data displayed by the outlet.
        """
        pass


class OutletPositionCallbackClassBase(OutletPositionCallbackBase):
    """
    A class that inherits from OutletPositionCallbackBase. This class
    should be used instead of OutletPositionCallbackBase if the callback
    is not dependent on an object. The outlet configuration can then be
    cached in the frontend.
    """

    needs_object = False


def replace_outlets(model, app_setup):
    """ Walks through the `applicationConfiguration` subtree in `app_setup`, and
        searches for `outlet` properties defined for the components therein.
        For each occurence that is found, the `outlet` key is removed, and the
        configuration of that outlet is inserted.
        `model` is an subclass of ``ConfigurableUIModel``, that can be used to
        register libraries etc.

        THINKABOUT: for now, this will only work for DetailViews. Probably at
        least ClassViews should have this too.
    """
    # The top level keys may either be strings (ie. component names) or actual
    # configurations.
    new_conf = {k: v if isinstance(v, six.string_types) else _walk_tree(model, v)
                for k, v in six.iteritems(app_setup["applicationConfiguration"])}
    app_setup["applicationConfiguration"] = new_conf


def _walk_tree(model, configuration):
    """ Here, `configuration` is a dictionary in the form expected by the JS
        function ``confToComponent``. Process the configuration itself, and
        recursively call this function to process sub-components. Returns the
        new configuration, with outlets replaced.
    """
    new_conf = configuration.copy()

    # Handle outlet for this component, modifies new_conf in place. This is done
    # before the recursive calls, so that we automatically handle outlets in
    # components that were just inserted from an outlet.
    _replace_outlet(model, new_conf)

    # Recurse into children etc.
    children = new_conf.pop("children", None)
    if children is not None:
        new_conf["children"] = [_walk_tree(model, c) for c in children]

    for name in ("components", "componentClasses"):
        conf_dict = new_conf.pop(name, None)
        if conf_dict is not None:
            new_conf[name] = {k: _walk_tree(model, v)
                              for k, v in six.iteritems(conf_dict)}

    return new_conf


def _get_callbacks(cfg):
    """
    Returns the configured callables or ``[]``
    """
    result = []
    fqpynames = cfg.get("setup_fqpynames")
    for fqpn in fqpynames:
        if fqpn:
            result.append(tools.getObjectByName(fqpn))
    return result


def _run_callback(cb, cfg, classdef, obj):
    try:
        return cb.adapt_initial_config(cfg, classdef, obj)
    except TypeError:
        return cb.adapt_initial_config(cfg, classdef)
    except AttributeError:
        pass
    return []


def _replace_outlet(model, new_conf, outlet=None, keys=None):
    """ If `new_conf` has an outlet definition, replace that with the configured
        components that should be rendered.
    """
    outlet_name = new_conf.pop("outlet", outlet)
    if outlet_name is None:
        return

    outlet_cfgs = OutletDefinition.get_outlet_positions(outlet_name, model.classdef)
    children = new_conf.setdefault("children", [])
    properties = new_conf.setdefault("properties", {})
    libraries = new_conf.setdefault("libraries", [])
    properties["__outlets"] = []
    comp_ids = []
    config_needs_object = False
    obj = None
    try:
        obj = model.get_object()
    except AttributeError:
        if keys is not None:
            rest_name = model.classdef.getRESTName()
            obj = support.get_object_from_rest_name(rest_name, keys)
    for cfg in outlet_cfgs:
        cbs = _get_callbacks(cfg)
        if cbs:
            for cb in cbs:
                if cb.needs_object:
                    config_needs_object = True
                    break
            cfgs = [cfg]
            for cb in cbs:
                result = []
                for c in cfgs:
                    result += _run_callback(cb, c, model.classdef, obj)
                cfgs = result
        else:
            cfgs = [cfg]
        for c in cfgs:
            idx = len(children)
            key = "__outlet_%d" % idx
            icon = c.get("icon_url")
            if icon:
                iconattr = "icon_url"
            else:
                iconattr = "icon_id"
                icon = c.get("icon_id")
            comp_id = c.get("outlet_child_name")
            if c.get("cfg_id"):
                comp_id = comp_id + "-" + c.get("cfg_id")
            suffix = "-" + c.get("outlet_pos_id") if c.get("outlet_pos_id") else ""
            comp_id = comp_id + suffix
            comp_id = comp_id if comp_id not in comp_ids else comp_id + "-" + str(c.get("pos"))
            comp_ids.append(comp_id)
            properties["__outlets"].append({"key": key,
                                            "childIndex": idx,
                                            "title": c["title"],
                                            iconattr: icon,
                                            "comp_id": comp_id})
            config = _make_component(model, c, key)
            for lib in _get_libraries(model, c):
                libraries.append(lib)
            for cb in cbs:
                try:
                    cb.adapt_final_config(config, model.classdef, obj)
                except TypeError:
                    cb.adapt_final_config(config, model.classdef)
            children.append(config)
    new_conf["needs_object"] = config_needs_object


def _make_component(model, outlet_cfg, key):
    result = {}
    config_file = outlet_cfg.get("configuration")
    if config_file is None:
        result["name"] = outlet_cfg.get("component")
    else:
        cfg = model.load_config_file(config_file)
        result.update(cfg["configuration"])
        model.add_configuration_to_context(cfg)
    # Collect the resulting properties for the component
    props = result.setdefault("properties", {})
    props.update(outlet_cfg.get("properties", {}))
    props["__outlet"] = {"key": key}
    return result


def _add_lib(libs, lib_name, lib_version):
    urls = _get_script_urls(lib_name, lib_version)
    lib = {"library_name": lib_name, "script_urls": urls}
    if lib not in libs:
        libs.append(lib)


def _get_libraries(model, outlet_cfg):
    libs = []

    def add_lib(lib_name, lib_version):
        library = Libraries.ByKeys(lib_name)
        if library is not None:
            for _lib in get_dependencies(library):
                _add_lib(libs, _lib.library_name, _lib.library_version)
        else:
            _add_lib(libs, lib_name, lib_version)

    config_file = outlet_cfg.get("configuration")
    outlet_child_name = outlet_cfg.get("outlet_child_name")
    if config_file is not None:
        cfg = model.load_config_file(config_file)
        for lib_name, lib_version in cfg.get("libraries", []):
            add_lib(lib_name, lib_version)
        for pluginContext in cfg.get("pluginContexts", []):
            for i in Csweb_plugin.get_plugin_config(pluginContext):
                for lib_name, lib_version in i.get("libraries", []):
                    _add_lib(libs, lib_name, lib_version)
    outlet_child = support.get_object_from_rest_name("outlet_child", outlet_child_name)
    if (outlet_child):
        for lib in outlet_child.Libraries:
            add_lib(lib.library_name, lib.library_version)
    return libs


class OutletDescription(Object):
    __maps_to__ = 'csweb_outlet_description'
    __classname__ = 'csweb_outlet_description'

    Definitions = Reference_N(OutletDefinition,
                              OutletDefinition.outlet_name == OutletDescription.outlet_name)


class OutletDefinition(Object):
    """
    A class that serves as an entry point to evaluate an outlet in the context
    of a specific class. When an outlet definition is searched, the class hierarchy
    is respected.
    """
    __maps_to__ = 'csweb_outlet_definition'
    __classname__ = 'csweb_outlet_definition'

    Positions = Reference_N(OutletPosition,
                            OutletPosition.outlet_name == OutletDefinition.outlet_name,
                            OutletPosition.classname == OutletDefinition.classname)
    Description = Reference_1(OutletDescription, OutletDefinition.outlet_name)

    # Cache for configuration data
    # {(outlet_name, classname) -> {position -> [config, ...]}}
    _Cache = None

    @classmethod
    def _fill_cache(cls):
        def _get_child_dict(cfg):
            """
            Returns the configuration of an outlet child as dictionary
            or an error configuration if there is no child configuration.
            """
            child = all_children.get(cfg.child_name)
            if child:
                return cfg.to_dict(child)
            else:
                from cdb import misc
                from cdb.platform.gui import Message
                errmsg = Message.GetMessage("csweb_err_outlet_child_undefined",
                                            cfg.child_name)
                misc.log_error(errmsg)
                return {"outlet_child_name": "ConfigurationError",
                        "component": "cs-web-components-base-ConfigurationError",
                        "properties": {"message": errmsg},
                        "title": cdbwrapc.get_label("web.base.config_error"),
                        "icon_id": "ConfigurationError",
                        "setup_fqpynames": []}

        if cls._Cache is not None:
            return
        cls._Cache = {}
        all_children = {c.outlet_child_name: c.to_dict()
                        for c in OutletChild.Query()}
        # get all roles at once
        roles = defaultdict(list)
        for o in OutletPositionOwner.Query():
            roles[(o.outlet_name, o.classname, o.outlet_position_identifier)].append(o.role_id)
        # get all positions at once
        positions = defaultdict(list)
        for p in sorted(OutletPosition.Query(), key=lambda x: x.priority, reverse=True):
            positions[(p.outlet_name, p.classname)].append(p)

        for definition in OutletDefinition.Query().Execute():
            key = (definition.outlet_name, definition.classname)
            position_cache = defaultdict(list)
            for p in positions[(definition.outlet_name, definition.classname)]:
                child = _get_child_dict(p)
                child["roles"] = roles[(p.outlet_name, p.classname, p.outlet_position_identifier)]
                position_cache[p.pos].append(child)

            cls._Cache[key] = position_cache

    @classmethod
    def _clear_cache(cls):
        cls._Cache = None

    @classmethod
    def get_outlet_definition(cls, outlet_name, classdef):
        """ Returns an outlet definition for the given outlet name and class.
            Searches upwards in the inheritance hierarchy, with `*`as fallback, for
            a matching outlet definition entry. If no suitable outlet definition is found,
            the fallback of the outlet description is accessed (recursively).
        """
        cls._fill_cache()
        clsnames = ([classdef.getClassname()] +
                    [name for name in classdef.getBaseClassNames()] +
                    ["*"])
        for cn in clsnames:
            match = cls._Cache.get((outlet_name, cn))
            if match is not None:
                # filter for the current user (all outlets are cached)
                return {key: cls.filter_positions_by_user(p, auth.persno)
                        for key, p in match.items()}
        outlet_description = OutletDescription.ByKeys(outlet_name)
        outlet_fallback = outlet_description.outlet_fallback if outlet_description else ""
        if outlet_fallback:
            return cls.get_outlet_definition(outlet_fallback, classdef)
        return {}

    @classmethod
    def filter_positions_by_user(cls, configs, persno):
        """ Returns a list of child configuration for a specified user."""
        roles = set(util.get_roles("GlobalContext", "", persno))

        def cond(x):
            return len(roles.intersection(x["roles"])) > 0

        return list(filter(cond, configs))

    @classmethod
    def get_outlet_positions(cls, outlet_name, classdef):
        """ Returns a list of outlet positions for the given outlet name and
            class. For each distinct position, this selects the entry with the
            highest property (first in cached list, the lists are sorted
            accordingly).
            TODO: evaluate rules, and use the first match.
        """
        result = []
        positions = cls.get_outlet_definition(outlet_name, classdef)
        for pos in sorted(positions.keys()):
            configs = positions[pos]
            if configs:
                result.append(configs[0])
        return result


class OutletPosition(Object, WithJsonProperties):
    """
    Each outlet position defines one child component. The position numbers specify
    the ordering of the children. An outlet position is associated with role ids,
    and is taken into account only if the current user has one of these roles.
    It is possible to define more than one outlet position with the same position
    number. In this case, the one with the highest priority is used.
    """
    __maps_to__ = 'csweb_outlet_position'
    __classname__ = 'csweb_outlet_position'

    Owners = Reference_N(OutletPositionOwner,
                         OutletPositionOwner.outlet_name == OutletPosition.outlet_name,
                         OutletPositionOwner.classname == OutletPosition.classname,
                         OutletPositionOwner.outlet_position_identifier == OutletPosition.outlet_position_identifier)
    Definition = Reference_1(OutletDefinition,
                             OutletPosition.outlet_name,
                             OutletPosition.classname)
    Child = Reference_1(OutletChild, OutletPosition.child_name)
    Label = Reference_1(Label, OutletPosition.ausgabe_label)
    Icon = Reference_1(Icon, OutletPosition.cdb_icon_id == Icon.cdb_icon_id)

    def to_dict(self, outlet_child_dict):
        """ Create a dictionary representation of self. The values from the
            outlet child form the basis, but can be overwritten here.
        """
        # Use deepcopy to ensure the setup_fqpynames list will not be changed
        result = deepcopy(outlet_child_dict)
        result.update(pos=self.pos,
                      priority=self.priority,
                      outlet_pos_id=self.outlet_pos_id)
        if self.ausgabe_label:
            result["title"] = cdbwrapc.get_label(self.ausgabe_label)
        if self.cdb_icon_id:
            result["icon_id"] = self.cdb_icon_id
        fqpynames = result.setdefault("setup_fqpynames", [])
        if self.setup_fqpyname and self.setup_fqpyname not in fqpynames:
            result["setup_fqpynames"].append(self.setup_fqpyname)

        own_props = self.get_properties()
        if own_props:
            props = dict(outlet_child_dict["properties"])
            props.update(own_props)
            result["properties"] = props
        return result

    def get_callable(self):
        """
        Returns the object specified in `self.fqpyname` or
        ``None`` if no fqpyname is specified.
        Raises an `ue.Exception` if the configuration for
        the callable is wrong.
        """
        result = None
        if self.setup_fqpyname:
            try:
                result = tools.getObjectByName(self.setup_fqpyname)
            except Exception as e:
                raise ue.Exception("csweb_err_plugin_fqpyname", self.setup_fqpyname, repr(e))
            try:
                if not issubclass(result, OutletPositionCallbackBase):
                    raise ue.Exception("csweb_err_outlet_fqpyname_derived", self.setup_fqpyname)
            except TypeError:
                # issubclass raises an exception if cls is not a class
                raise ue.Exception("csweb_err_outlet_fqpyname_derived", self.setup_fqpyname)
        return result

    def _check_fqpyname(self, ctx):
        """
        Check if fqpyname is set and the class is derived from
        `OutletPositionCallbackBase`. `get_callable` will raise the
        exceptions for us.
        """
        self.get_callable()

    def _preset_position_identifier(self, ctx):
        ctx.set("outlet_position_identifier", cdbuuid.create_uuid())

    event_map = {
        (("modify", "create", "copy"), "pre"): "_check_fqpyname",
        (("create", "copy"), "pre_mask"): "_preset_position_identifier"
    }


class OutletPositionOwner(Object):
    __maps_to__ = 'csweb_outlet_position_owner'
    __classname__ = 'csweb_outlet_position_owner'

    Position = Reference_1(OutletPosition,
                           OutletPositionOwner.outlet_name,
                           OutletPositionOwner.classname,
                           OutletPositionOwner.outlet_position_identifier)


class OutletChildLibs(Object):
    __maps_to__ = "csweb_outlet_child_libs"
    __classname__ = "csweb_outlet_child_libs"

    Library = Reference_1(Libraries, fOutletChildLibs.library_name)


class OutletChild(Object, WithComponentOrConfiguration, WithJsonProperties):
    """
    An outlet child provides the configuration for a React component that should be
    rendered as an outlet position.
    """
    __maps_to__ = 'csweb_outlet_child'
    __classname__ = 'csweb_outlet_child'

    Label = Reference_1(Label, OutletPosition.ausgabe_label)
    Icon = Reference_1(Icon, OutletPosition.cdb_icon_id == Icon.cdb_icon_id)
    Usages = Reference_N(OutletPosition,
                         OutletPosition.child_name == OutletChild.outlet_child_name)
    LibraryReferences = Reference_N(OutletChildLibs,
                                    OutletChildLibs.outlet_child_name == OutletChild.outlet_child_name,
                                    order_by=OutletChildLibs.pos_nr)

    def _get_libraries(self):
        qry = ("SELECT l.*"
               " FROM csweb_libraries l INNER JOIN csweb_outlet_child_libs cl"
               " ON l.library_name = cl.library_name"
               " WHERE cl.outlet_child_name = '%s'"
               " ORDER BY cl.pos_nr") % sqlapi.quote(self.outlet_child_name)
        return Libraries.SQL(qry)

    Libraries = ReferenceMethods_N(Libraries, _get_libraries)

    def get_title(self):
        return cdbwrapc.get_label(self.ausgabe_label) if self.ausgabe_label else ''

    def to_dict(self):
        result = {"title": self.get_title(),
                  "icon_id": self.cdb_icon_id,
                  "outlet_child_name": self.outlet_child_name,
                  "properties": self.get_properties(),
                  "setup_fqpynames": [self.setup_fqpyname]
                  if self.setup_fqpyname else []}
        self._set_component_configuration(result)
        return result

    def get_callable(self):
        """
        Returns the object specified in `self.fqpyname` or
        ``None`` if no fqpyname is specified.
        Raises an `ue.Exception` if the configuration for
        the callable is wrong.
        """
        result = None
        if self.setup_fqpyname:
            try:
                result = tools.getObjectByName(self.setup_fqpyname)
            except Exception as e:
                raise ue.Exception("csweb_err_plugin_fqpyname", self.setup_fqpyname, repr(e))
            try:
                if not issubclass(result, OutletPositionCallbackBase):
                    raise ue.Exception("csweb_err_outlet_fqpyname_derived", self.setup_fqpyname)
            except TypeError:
                # issubclass raises an exception if cls is not a class
                raise ue.Exception("csweb_err_outlet_fqpyname_derived", self.setup_fqpyname)
        return result

    def _check_fqpyname(self, ctx):
        """
        Check if fqpyname is set and the class is derived from
        `OutletPositionCallbackBase`. `get_callable` will raise the
        exceptions for us.
        """
        self.get_callable()

    event_map = {
        (("modify", "create", "copy"), "pre"): "_check_fqpyname",
    }


# On any change concerning the outlet configuration, flush the cache
def _flush_cache(self, ctx):
    if not ctx.error:
        OutletDefinition._clear_cache()


for clazz in (OutletDefinition, OutletPosition, OutletPositionOwner, OutletChild):
    for action in ("create", "copy", "modify", "delete"):
        sig.connect(clazz, action, "post")(_flush_cache)
