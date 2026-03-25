#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import inspect
import logging

from cdb import auth, util
from cdb.cad import getCADConfValue, getMaxIndex
from cdb.objects.operations import operation
from cdb.tools import getObjectByName

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent
from cs.vp.bomcreator.bom import BOMEntry, GeneratedBOM, first_source_part,\
    msg, format_float
from cs.vp.bomcreator.bomconfig import BOMConfig
import six


class Factory(object):
    """
    Creates

    - instances of :class:`cs.vp.bomcreator.bomreader.BOMReader`
      (varying in their concrete subtype)
    - instances of :class:`BOMEntry`
      (varying in the attributes they contain), and
    - instances of :class:`GeneratedBOM`
      (only varying in the headers for display)

    based on the currently valid configuration.

    The valid configuration depends on the CAD source and on the roles
    of the current user.

    Instances of this class are used only *once*. They are not recycled for
    new BOM creation processes.
    """
    def __init__(self, bom_context):
        """The `__init__` method finds out the correct configuration to use
        and loads and evaluates it.

        :Parameters:
         - bom_context: :class:`cs.vp.bomcreator.bomreader.BOMContext`
              input data

        Custom implementations of BOM readers never create a factory manually.
        It is passed to them via their `__init__` method instead.
        """
        self._context = bom_context
        self.cadsource = bom_context.cadsource

        self._configure_new_position_step()

        config = BOMConfig.find_config(self.cadsource, bom_context.object_id)

        if config is None:
            logging.error(u"bomcreator: no configuration found for current"
                          u" user '%s'; using default values instead.",
                          auth.persno)
            self._context.global_user_hints.append(
                msg('WSM_BOM_no_matching_configuration'))

        self.cadsource_to_replace = ""
        self.config_name = "no config"
        if config:
            self.cadsource_to_replace = config.get_cadsource_to_replace()
            self.config_name = config.name

        self._configure_bom_method(config)
        self._configure_display_attrs(config)
        self._configure_headers(config)
        self._configure_key_attrs(config)
        self._configure_sync_attrs(config)
        self._configure_sync_from_cad_attrs(config)

        self.floatFormatting = util.get_prop('flfo')
        self.reader = None

        self._init_component_field_types()

    def _init_component_field_types(self):
        self._component_field_types = {}
        for field_name in AssemblyComponent.GetFieldNames():
            db_type = getattr(AssemblyComponent, field_name).type
            python_type = None
            if db_type == 0:
                python_type = six.text_type
            elif db_type == 1:
                python_type = int
            elif db_type == 2:
                python_type = float
            else:
                # don't check other types
                # (assumption: date columns are never part of the key)
                pass
            self._component_field_types[field_name] = python_type

    def create_BOMReader(self, custom_state=None, create_boms=True):
        """Creates an object implementing the
        :class:`cs.vp.bomcreator.bomreader.BOMReader` interface.
        The concrete type of the returned object depends
        on configuration settings.

        :Parameters:
          - `custom_state`: dictionary (internal state of implementations)
        """
        if custom_state is None:
            custom_state = {}
        # Two step creation of the reader because
        # Factory.create_bom needs to know the reader instance and is called
        # from the reader's __init__
        if self.reader_class:
            self.reader = self.reader_class.__new__(self.reader_class)
            if create_boms:
                self.reader.__init__(self._context, self, custom_state)
        return self.reader

    def create_BOMEntry(self, **attrs):
        """Creates a :class:`BOMEntry` according to the configuration.

        :Parameters:
           - `attrs`: dictionary containing values of `bom_item` attributes;
                      must contain at least `teilenummer`
        """
        self._add_required_default_attributes(attrs)
        key = self._create_BOMEntry_key(attrs)
        index_less_key = self._create_BOMEntry_key(attrs, ["t_index"])

        # connect to parent
        attrs['baugruppe'] = self._context.teilenummer
        attrs['b_index'] = self._context.t_index
        #
        return BOMEntry(key,
                        attrs,
                        self.display_attrs,
                        index_less_key)

    def get_attribute_mapping(self):
        """
        Retrieves the configured mapping from source attributes to CDB
        attributes. The meaning of "source attributes" is
        implementation-specific. This configuration part is only useful for
        some `BOMReader` implementations.

        The result is a list of 3-tuples:
        (`cdb_name`, `source_name`:string, `is_property`)

         - `cdb_name`: String;
           the name of an attribute of class `AssemblyComponent`
         - `source_name`: String;
           the name of a source attribute. The details depend on the specific implementation.
         - `is_property`: int;
           1 if the source is considered a property; 0 if it is an attribute
        """
        return list(self.sync_from_cad_attrs)

    def sync_BOMEntries(self, existing, new):
        """
        Synchronizes an `existing` :class:`cs.vp.bomcreator.bom.BOMEntry`
        with a new one. "new" will be overwritten with the result.

        This method is typically not called directly by client code.
        """
        # First save state of 'new'
        new_attrs = new.attrs
        new_occurrences = new.occurrences
        # copy 'existing' to 'new'
        new.__dict__ = existing.__dict__.copy()
        # simulate updating (so that status and display are updated correctly)
        new.status = BOMEntry.Unchanged
        for k, v in six.iteritems(new_attrs):
            if k in self.sync_attrs:
                new.update_attribute(k, v)
        new.update_occurrences(new_occurrences)

    def create_BOM(self):
        """Creates a :class:`cs.vp.bomcreator.bom.GeneratedBOM` that is
        adjusted according to the configuration and which represents
        a BOM of the item associated with this factory."""
        bom = GeneratedBOM(self._context,
                           self,
                           self.headers,
                           self.new_positions_step)
        if self.reader:
            bom.set_use_kernel_operations(self.reader.use_kernel_operations())
            bom.set_post_write_component(self.reader.post_write_component)
            bom.set_post_write_bom(self.reader.post_write_bom)
            bom.set_pre_show_component(self.reader.pre_show_component)
        return bom

    def create_BOM_for_assembly(self, item):
        """Creates a :class:`cs.vp.bomcreator.bom.GeneratedBOM` for the given
        item. The generated BOM will respect the configuration settings of
        this Factory but is not attached to the original item.

        :Parameters:
          - `item`: a :class:`cs.vp.items.Item`
        """
        from cs.vp.bomcreator.bomreader import BOMContext  # pylint: disable=C0415
        new_context = BOMContext(self._context.object_id,
                                 item.teilenummer,
                                 item.t_index,
                                 self._context.cadsource,
                                 self._context.global_user_hints)
        new_factory = Factory(new_context)
        new_factory.reader = self.reader
        new_bom = new_factory.create_BOM()
        return new_bom

    def create_assembly_and_BOM(self, *args, **kwargs):
        """Creates a new :class:`cs.vp.items.Item` and a
        :class:`cs.vp.bomcreator.bom.GeneratedBOM` attached to this item.

        WARNING: This must only be used if a matching assembly does not
        yet exist, i.e. a call to this method should always be guarded by
        condition for the existing assembly.

        The item is created using a CDB operation.
        The keyword arguments are preset attributes for the new item.
        The "extra" arguments are passed on to the operation (for example,
        for passing 'system_args').
        """
        item = operation("CDB_Create", Item, *args, **kwargs)
        bom = self.create_BOM_for_assembly(item)
        bom.mark_assembly_as_temporary()
        return bom

    def createVirtualWorkspace(self, *args, **kwargs):
        """
        Use this only for WSM BOM readers (cs.workspaces must be installed).
        """
        from cs.wsm.virtualworkspace import VirtualWorkspace  # pylint: disable=C0415
        return VirtualWorkspace(*args, **kwargs)

    def is_column_editable(self, col_index):
        return self.column_is_editable[col_index]

    def _configure_bom_method(self, config):
        self.reader_class = None
        standard_reader = "cs.vp.bomcreator.generatenobom.GenerateNoBOM"
        try:
            self.reader_class = getObjectByName(standard_reader)
        except ImportError:
            logging.error("bomcreator: could not import default bom reader %s", standard_reader)

        if config is None:
            return
        reader_class = config.get_reader_type()
        if reader_class is None:
            logging.error("bomcreator: configured bom method"
                          " not found: '%s'; using default instead.",
                          config.Method.class_name)
        elif not inspect.isclass(reader_class):
            logging.error("bomcreator: configured bom method"
                          " is not a class: '%s'; using default instead.",
                          config.Method.class_name)
        else:
            self.reader_class = reader_class

    def _configure_display_attrs(self, config):
        self.display_attrs = ['position', 'teilenummer', 't_index',
                              'Item.designation', 'menge']
        if config is None:
            return
        display_attrs = config.get_column_attributes()
        if len(display_attrs) < 1:
            logging.error("bomcreator: empty columns found for '%s';"
                          " using default instead.",
                          self.cadsource)
        else:
            self.display_attrs = display_attrs

    def _configure_headers(self, config):
        if config is None:
            self._configure_default_headers()
            return
        headers = config.get_column_headers()
        if len(headers) < 1:
            self._configure_default_headers()
            logging.error("bomcreator: no column headers found for '%s';"
                          " using default instead.",
                          self.cadsource)
        else:
            self.headers = [h[0] for h in headers]
            self.column_is_editable = [h[1] for h in headers]

    def _configure_default_headers(self):
        labels = ['WSM_BOM_POSITION', 'WSM_BOM_PART_NO', 'WSM_BOM_PART_INDEX',
                  'WSM_BOM_DESIGNATION', 'WSM_BOM_AMOUNT']
        self.headers = [util.get_label(label) for label in labels]
        self.column_is_editable = [False for _ in labels]

    def _configure_key_attrs(self, config):
        self.key_attrs = ['teilenummer', 't_index']
        if config is None:
            return
        key_attrs = config.get_key_attributes()
        if len(key_attrs) < 1:
            logging.error("bomcreator: empty key"
                          " attributes; using default instead.")
            return
        if any(not AssemblyComponent.HasField(key)
               for key in key_attrs):
            logging.error("bomcreator: the list of key attributes contains"
                          " unknown attributes: '%s';using default instead.",
                          key_attrs)
            return
        self.key_attrs = sorted(key_attrs)  # sort to have a consistent order

    def _configure_sync_attrs(self, config):
        self.sync_attrs = ["menge"]
        if config is None:
            return
        if config.get_cadsource_to_replace():
            self.sync_attrs.append("cadsource")
        sync_attrs = config.get_sync_attributes()
        for attr in sync_attrs:
            if not AssemblyComponent.HasField(attr):
                logging.error("bomcreator: the list of sync attributes has"
                              " an unknown attribute: '%s'; ignoring it",
                              attr)
            else:
                self.sync_attrs.append(attr)

    def _configure_sync_from_cad_attrs(self, config):
        self.sync_from_cad_attrs = []
        if config is None:
            return
        for (cdb_attr, appinfo_attr, is_property) in config.get_mappings():
            # filter problematic mappings
            if not AssemblyComponent.HasField(cdb_attr):
                logging.error("bomcreator: unknown CDB attribute in"
                              " mapping: %s; ignoring this mapping",
                              cdb_attr)
                continue
            if len(appinfo_attr) == 0:
                logging.error("bomcreator: empty source attribute name on"
                              " right side of mapping: %s;ignoring this mapping",
                              appinfo_attr)
                continue
            self.sync_from_cad_attrs.append((cdb_attr,
                                             appinfo_attr,
                                             is_property))

    def _configure_new_position_step(self):
        default_new_positions_step = 10
        new_positions_step = getCADConfValue(u"STL Schrittweite",
                                             self.cadsource)
        if new_positions_step is None:
            logging.error("bomcreator: no 'Schrittweite' found for '%s';"
                          " using default instead.",
                          self.cadsource)
            self.new_positions_step = default_new_positions_step
        try:
            self.new_positions_step = int(new_positions_step)
            if self.new_positions_step < 1:
                logging.error("bomcreator: illegal value for 'Schrittweite':"
                              " '%s'; using default of 10 instead.",
                              self.new_positions_step)
                self.new_positions_step = default_new_positions_step
        except ValueError:
            logging.error("bomcreator: illegal format for 'Schrittweite':"
                          " '%s'; using default of 10 instead.",
                          new_positions_step)
            self.new_positions_step = default_new_positions_step

    def _add_required_default_attributes(self, attrs):
        defaults = {"auswahlmenge": 0.0,
                    "variante": "",
                    "cadsource": first_source_part(self.cadsource),
                    "menge": 1.0}
        for k, v in six.iteritems(defaults):
            if k not in attrs:
                attrs[k] = v
        if 't_index' not in attrs:
            attrs['t_index'] = getMaxIndex(attrs['teilenummer'], "teile_stamm")

    def _create_BOMEntry_key(self, attrs, key_filter=frozenset()):
        """
        Returns a tuple that is used as the merge key for the bom entry
        represented by the given attribute values.

        :Parameters:
           - `attrs`: dictionary containing values of `bom_item` attributes

        """
        key_elements = []
        for attr_name in self.key_attrs:
            if attr_name in key_filter:
                continue
            val = attrs[attr_name]
            expected_type = self._component_field_types[attr_name]
            if expected_type is not None:
                if val is not None:  # allow missing values
                    actual_type = type(val)
                    if expected_type is six.text_type:
                        if not isinstance(val, six.string_types):
                            logging.warning("BOM Factory: attribute '%s': expected data type unicode or string, got data type '%s' (converting automatically)", attr_name, actual_type)
                            val = u"%s" % val
                    elif actual_type != expected_type:
                        logging.warning("BOM Factory: attribute '%s': expected data type '%s', got data type data '%s' (trying to convert automatically)", attr_name, expected_type, actual_type)
                        try:
                            val = expected_type(val)
                        except ValueError:
                            logging.error("BOM Factory: failed to convert value of attribute '%s'", attr_name)

            if isinstance(val, float):
                val = format_float(val, self.floatFormatting)
            key_elements.append(val)
        key = tuple(key_elements)
        return key
