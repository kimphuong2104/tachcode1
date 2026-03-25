#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
The module `cs.web.components.configurable_ui` provides the basic functionality
to describe the structure of a frontend application through configuration. Part
of this configuration is transmitted to the frontend, and is interpreted there
to derive the actual component structure.
"""

from __future__ import absolute_import
import six
__revision__ = "$Id$"

import json
import sys
from collections import OrderedDict

from cdb import auth
from cdb import misc
from cdb import sig
from cdb import tools
from cdb import util
from cdb.objects import Object, Forward, Reference, N
from cdb.platform.gui import CDBCatalog
from cs.web.components.base.main import BaseApp, BaseModel
from cs.web.components.plugin_config import Csweb_plugin
from cs.web.components.library_config import Libraries, get_dependencies
from .configuration_helpers import WithComponentOrConfiguration


class ConfigurableUIModel(BaseModel):
    """ This abstract morepath model class implements methods to read an
        application configuration from JSON files, and provide morepath
        applications access to the resulting configuration data.

        The configuration is exported as a dictionary, whose content will be
        provided to the frontend JavaScript code. The dictionary will contain
        at least the follwing keys:

        * `pageRenderer`: The name of the top level React component that will
          be rendered by the frontend. Subclasses must overwrite
          `page_renderer` to contain a React component name. This component
          will be used in the frontend as the top level React element on the
          page.

        * `frameComponent`: The configuration for the common frame, that will
          be the same for all or nearly all pages. The actual content will be
          displayed inside the frame. The value for `frameComponent` is
          determined by the method `page_frame`.

    """

    # Name of the page renderer component to use. Must be overwritten by
    # subclasses.
    page_renderer = None

    # Dictionary that caches configuration information
    configs = {}

    # Dictionary that caches the frame configurations
    frames = {}

    def __init__(self):
        super(ConfigurableUIModel, self).__init__()
        # The configuration is loaded on demand.
        # _application_configuration == None is the marker that it has not been
        # loaded already.
        self._application_configuration = None
        self._libraries = OrderedDict()
        self._setup_functions = []
        self._plugin_contexts = set()
        self._page_frame = u"csweb_default_page_frame"

    @property
    def app_conf(self):
        """ Returns the application configuration, that is to be used by the
            frontend to create the UI.
        """
        self._check_load_application_configuration()
        return self._application_configuration

    @property
    def libraries(self):
        """ Returns a list of JavaScript libraries that are required by the
            configured application. The libraries are included as <script> tags
            in the generated HTML.
        """
        self._check_load_application_configuration()
        return list(six.iteritems(self._libraries))

    @property
    def setup_functions(self):
        """ Returns a list of functions to be executed during the setup phase
            of the application. Typically, these functions augment the appSetup
            object that is passed to the frontend.
        """
        self._check_load_application_configuration()
        return self._setup_functions

    @property
    def plugin_contexts(self):
        """ Returns a list with plugin context names that are used on the page.
            The plugin context names are used to determine the needed plugin
            configuration, that must be passed to the frontend.
        """
        self._check_load_application_configuration()
        return self._plugin_contexts

    def set_page_frame(self, frame_id):
        """
        Sets the ID of the page frame. This ID is returned
        if calling `page_frame`. Note that you have to call this
        function before `load_application_configuration` is called to have
        any effect for the application.
        """
        self._page_frame = frame_id

    def page_frame(self):
        """
        ID of the page frame to use for the application. May be
        overwritten by subclasses to display a different frame (eg. without
        a sidebar). You can set the ID by calling `set_page_name`.
        """
        return self._page_frame

    def add_library(self, libname, libversion):
        """ Adds the JavaScript library `libname` with version `libversion` to
            the list of libraries that are needed by the frontend.
        """
        existing_version = self._libraries.get(libname)
        if existing_version is None:
            self._libraries[libname] = libversion
        elif existing_version != libversion:
            raise RuntimeError("More than one version of library %s requested"
                               % libname)

    def add_setup_function(self, fqpyname):
        try:
            fct = tools.getObjectByName(fqpyname)
            self._setup_functions.append(fct)
        except ImportError as e:
            misc.log_error("ConfigurableUIModel: Could not import setup"
                           " function '%s': %s" % (fqpyname, e))

    def add_plugin_context(self, context_name):
        self._plugin_contexts.add(context_name)

    @classmethod
    def load_config(cls, config_clname):
        """
        Returns a list of dictionaries. Each dictionary contains a configuration
        of the type `config_clname` that has to be derived from ``csweb_config_page``.
        The configuration is cached so you might not get the actual values.
        """
        result = cls.configs.get(config_clname)
        if result is None:
            result = [c.convert2dict() for c in Csweb_page_config.KeywordQuery(cdb_classname=config_clname)]
            # Hacky fix for wrong configs, MUST BE REMOVED in the future!!
            # The interpretation of the ui_name attribute for instances of
            # csweb_page_config_class was buggy, it was used as cdb_classname
            # (see E053354).
            # Some developers created configurations with classnames instead,
            # so if some entry is not as expected, assume that this was meant.
            if config_clname == "csweb_page_config_class":
                from cdbwrapc import CDBClassDef
                from cdb import sqlapi
                # This is the set of names that should appear
                ui_and_rest_names = set([
                    rec.ui_name for rec in sqlapi.RecordSet2("csweb_ui_and_rest_names")])
                ui_and_rest_names.add('*')
                for cfg in result:
                    if cfg["classname"] not in ui_and_rest_names:
                        misc.log_error(
                            "The class page configuration %s/%s does not refer to"
                            " a UI or REST name. Please correct the configuration!"
                            % (cfg["classname"], cfg["viewname"]))
                        # Not from the expected set, assume classname
                        cdef = CDBClassDef(cfg["classname"])
                        if cdef.isValid() and cdef.getRESTName():
                            cfg["classname"] = cdef.getRESTName()

            cls.configs[config_clname] = result
        return result

    @classmethod
    def load_config_file(cls, fname):
        with open(fname, "rb") as f:
            return json.load(f)

    def add_configuration_to_context(self, cfg):
        """ Store required libraries, setup functions and plugin contexts that
            are encountered when reading a configuration file. All of these are
            collected, and processed when the page is rendered.
        """
        for name, version in cfg.get("libraries", []):
            library = Libraries.ByKeys(name)
            if library is not None:
                for _lib in get_dependencies(library):
                    self.add_library(_lib.library_name, _lib.library_version)
            else:
                self.add_library(name, version)
        for fct_name in cfg.get("setupFunctions", []):
            self.add_setup_function(fct_name)
        for context_name in cfg.get("pluginContexts", []):
            self.add_plugin_context(context_name)

    def insert_component_configuration(self, attribute, config):
        """ If the dict `config` contains an entry ``configuration``, the
            corresponding value is used as a file name, and its content
            (interpreted as JSON) is set as `attribute` in the application
            configuration.

            Otherwise, `config` must have a key ``component`` that has the name
            of a React component as its value. This name is set unchanged as
            `attribute` in the application configuration.

            The frontend in turn interprets strings as component names, and
            everything else as a component configuration object.
        """
        config_file = config.get("configuration")
        if config_file is None:
            self._application_configuration[attribute] = config.get("component")
        else:
            cfg = self.load_config_file(config_file)
            self._application_configuration[attribute] = cfg["configuration"]
            self.add_configuration_to_context(cfg)

    def load_frame_configuration(self):
        name = self.page_frame()
        config = self.frames.get(name)
        if config is None:
            frame = Csweb_page_frame.ByKeys(name)
            if not frame:
                raise RuntimeError("Configuration missing for frame '%s'" % name)
            config = frame.convert2dict()
            self.frames[name] = config
        self.insert_component_configuration("frameComponent", config)

    def _check_load_application_configuration(self):
        if self._application_configuration is None:
            #  Each application has a page renderer component, that will be the
            # top level React component on the page.
            self._application_configuration = {"pageRenderer": self.page_renderer}
            self.load_application_configuration()

    def load_application_configuration(self):
        """ Load and insert any application specific configuration into this
            instance. To be overwritten by subclasses, if there is anything
            they need to load. What exactly needs to be loaded depends on the
            page renderer component that the subclass uses.

            .. note::

               Don't forget to call super!

            This method is guaranteed to be called only once, so subclasses
            don't need to implement any checks for duplicate calls.

        """
        self.load_frame_configuration()


class SinglePageModel(ConfigurableUIModel):
    """ Model for a page whose content is defined through a page configuration.
        Subclasses only need to overwrite ``page_name``. The model uses the
        page name to select an entry with matching `name` from the
        :guilabel:`Standalone Page Configuration`.
        That entry in turn describes the UI to render.
    """

    # All single pages use the same page renderer component.
    page_renderer = "cs-web-components-base-SinglePage"

    # Page name to look up in the configuration. Must be overwritten by
    # subclasses.
    page_name = None

    def __init__(self):
        super(SinglePageModel, self).__init__()

    def load_application_configuration(self):
        cfg = self.load_config("csweb_page_config_app")
        config = select_by_roles([c for c in cfg if c["name"] == self.page_name])
        self.set_page_frame(config["pageframe_id"])
        super(SinglePageModel, self).load_application_configuration()
        self.insert_component_configuration("pageContent", config)


def handle_configuration(model, request, app_setup):
    # Call setup functions read from configuration files
    for fct in model.setup_functions:
        fct(model, request, app_setup)
    # Insert the configurations for any plugins the page (potentially) uses. Do
    # this after the setup functions are called, to allow them to specify which
    # plugins may be needed.
    plg_config = {}
    plg_libs = []
    plg_setup = []
    for ctx_name in model.plugin_contexts:
        cfg_entries = []
        for entry in Csweb_plugin.get_plugin_config(ctx_name):
            cfg_entries.append({'discriminator': entry.get('discriminator'),
                                'component': entry.get('component')})
            for name, version in entry.get("libraries", []):
                plg_libs.append((name, version))
            fqpyname = entry.get("setup")
            if fqpyname is not None:
                try:
                    plg_setup.append(tools.getObjectByName(fqpyname))
                except ImportError as e:
                    misc.log_error("ConfigurableUIModel: Could not import setup"
                                   " function '%s': %s" % (fqpyname, e))
        plg_config[ctx_name] = cfg_entries
        app_setup.update(pluginConfiguration=plg_config)
    for fct in plg_setup:
        fct(model, request, app_setup)
    # The configuration files can specify JS libs to load, and the setup
    # functions may add additional ones, so we access the required libs
    # after executing the setup.
    return model.libraries + plg_libs


class ConfigurableUIApp(BaseApp):
    """ Morepath application class for configurable UIs. This class only exists
        as a point to attach a morepath @view directive, and as a baseclass for
        applications.

        Subclasses must be created to create specific mount points.
    """

    def __init__(self):
        super(ConfigurableUIApp, self).__init__()

    def update_app_setup(self, app_setup, model, request):
        super(ConfigurableUIApp, self).update_app_setup(app_setup, model, request)

        # FIXME(app_inheritance) special handling: only run for ConfigurableUIModel, see D082907
        if not isinstance(model, ConfigurableUIModel):
            return

        # For each configurable UI, the frontend needs at least
        # the application configuration.
        app_setup.update(applicationConfiguration=model.app_conf)
        # Call any connected slots. The model class is used as first parameter in
        # the emitter, so that @connects can be specific to derived classes, and
        # still take advantage of the class hierarchy handling implemented in the
        # cdb.sig logic.
        # The settings dict is given as an in/out parameter, so that the called
        # functions may merge their individual setup deep into the possibly nested
        # dict.
        slot = sig.emit(type(model), ConfigurableUIModel, "application_setup")
        slot(model, request, app_setup)
        libs = handle_configuration(model, request, app_setup)
        for name, version in libs:
            request.app.include(name, version)


def filter_by_roles(configurations):
    """ Returns those entries from the list `configurations` that match one of
        the user's roles.
    """
    my_roles = set(util.get_roles("GlobalContext", "", auth.persno))
    return [c for c in configurations if set(c["roles"]).intersection(my_roles)]


def select_by_roles(configurations):
    """ Select a single configuration from the list `configurations` that match
        one of the user's roles. If more than one match this condition, select
        one that is not defined for the role 'public'.
    """
    configs = filter_by_roles(configurations)
    if len(configs) > 1:
        configs = [c for c in configs if u'public' not in c["roles"]]
    if len(configs) > 0:
        return configs[0]
    else:
        raise RuntimeError("No configuration found")


@ConfigurableUIApp.view(model=ConfigurableUIModel, name="app_component", internal=True)
def _app_component(_model, _request):
    # No app component defined here, None signals that we have an explicit app
    # configuration.
    return None


@ConfigurableUIApp.view(model=ConfigurableUIModel, name="base_path", internal=True)
def get_base_path(_model, request):
    return request.path


fLabel = Forward("cdb.platform.gui.Label")
fCsweb_page_config = Forward(__name__ + ".Csweb_page_config")
fCsweb_page_config_owner = Forward(__name__ + ".Csweb_page_config_owner")


class Csweb_page_config(Object, WithComponentOrConfiguration):
    __maps_to__ = "csweb_page_config"
    __classname__ = "csweb_page_config"

    Label = Reference(1, fLabel, fCsweb_page_config.ausgabe_label)

    Owners = Reference(N, fCsweb_page_config_owner,
                       fCsweb_page_config_owner.page_id == fCsweb_page_config.page_id)

    def convert2dict(self):
        """
        A function that converts `self` to a dictionary that can be used
        in the way ``ConfigurableUIModel`` works,
        """
        result = {"viewname": self.viewname,
                  "pageframe_id": self.pageframe_id,
                  "priority": self.priority if self.priority is not None else -sys.maxsize,
                  "roles": [r.subject_id for r in self.Owners]}
        self._set_component_configuration(result)
        return result


class Csweb_page_config_class(Csweb_page_config):
    __classname__ = "csweb_page_config_class"
    __match__ = Csweb_page_config.cdb_classname >= __classname__

    def convert2dict(self):
        result = self.Super(Csweb_page_config_class).convert2dict()
        result["classname"] = self.ui_name
        return result


class Csweb_page_config_detail(Csweb_page_config):
    __classname__ = "csweb_page_config_detail"
    __match__ = Csweb_page_config.cdb_classname >= __classname__

    def convert2dict(self):
        result = self.Super(Csweb_page_config_detail).convert2dict()
        result["classname"] = self.classname
        return result


class Csweb_page_config_app(Csweb_page_config):
    __classname__ = "csweb_page_config_app"
    __match__ = Csweb_page_config.cdb_classname >= __classname__

    def convert2dict(self):
        result = self.Super(Csweb_page_config_app).convert2dict()
        result["name"] = self.page_id
        return result


class Csweb_page_frame(Object, WithComponentOrConfiguration):
    __maps_to__ = "csweb_page_frame"
    __classname__ = "csweb_page_frame"

    def convert2dict(self):
        """
        A function that converts `self` to a dictionary that can be used
        in the way ``ConfigurableUIModel`` works,
        """
        result = {}
        self._set_component_configuration(result)
        return result


class Csweb_page_config_owner(Object):
    __maps_to__ = "csweb_page_config_owner"
    __classname__ = "csweb_page_config_owner"


class RestOrUiNameCatalog(CDBCatalog):
    """ Catalog to display all configured REST- and UI-Names, and in addition
        allows "*" for fallback configurations.
    """
    def init(self):
        CDBCatalog.init(self)

    def skipValueCheck(self, attr, value):
        return attr == "ui_name" and value == "*"
