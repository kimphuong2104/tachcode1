#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
This module contains the classes and interfaces that are needed for the most
common customization scenarios.
"""
from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from cdb.objects import ByID, Object

from cs.vp.cad import CADVariant
from cs.vp.items import Item
from cs.documents import Document

from cs.vp.bomcreator.bom import msg, UserHintList
from cs.vp.bomcreator.factory import Factory


class BOMContext(object):
    """
    Information about the objects involved in a BOM import.

    This class bundles the input to a BOM creation method.
    It is a simple data container.
    """
    def __init__(self,
                 object_id,
                 teilenummer, t_index,
                 cadsource,
                 global_user_hints,
                 variant_id=None):
        """
        :Attributes:
          - `object_id`: String
              ID of the business object that the operation was applied to.
              For now, this is always a document, but implementations of
              BOMReader should not rely on this assumption.
          - `teilenummer`: String
              part number of the assembly that will receive the generated BOM
          - `t_index`: String
              part version of the assembly that will receive the generated BOM
          - `cadsource`: String
              application of the business object
          - `global_user_hints`: cs.vp.bomcreator.bom.UserHintList
              list of global errors and hints
          - 'variant_id': String or None
              optional variant id of the variant whose BOM should be created
              In this case, (teilenummer, t_index) identifies the assembly of
              the variant.
        """
        self.object_id = object_id
        self.teilenummer = teilenummer
        self.t_index = t_index
        self.cadsource = cadsource
        self.global_user_hints = global_user_hints
        self.variant_id = variant_id

    def to_json(self):
        return {
            'object_id': self.object_id,
            'teilenummer': self.teilenummer,
            't_index': self.t_index,
            'cadsource': self.cadsource,
            'variant_id': self.variant_id
        }

    @staticmethod
    def from_json(js):
        args = js.copy()
        args['global_user_hints'] = UserHintList()
        return BOMContext(**args)


class BOMFatalError(Exception):
    """
    Should be raised from :class:`BOMReader` implementations when no BOM
    could be created at all.
    As a result, the "Save" button will not be visible in the user interface,
    and the framework will not attempt to use the result of the reader.
    """


class BOMReader(object):
    """
    Abstract Base Class for all BOM reader implementations.

    This is the most general interface. For most custom implementations,
    :class:`SimpleBOMReader` will be the better choice as the base class.

    Derived classes must have a `__init__` method with the following signature:

    `def __init__(self, bom_context, factory, custom_state)`

    - `bom_context`: :class:`BOMContext`
                     input data
    - `factory`: :class:`cs.vp.bomcreator.factory.Factory`
                 factory to create BOMs and BOM entries in accordance
                 witht the current configuration
    - `custom_state`: dictionary
                      may contain implementation-specific state
                      that is needed across multiple, recursive
                      invocations of a reader

    `__init__` may raise a :class:`BOMFatalError`.

    If it does not raise an error, instances must have an attribute `boms`
    which contains a list of :class:`cs.vp.bomcreator.bom.GeneratedBOM`
    (typically a singleton list, but multiple BOMs are supported, too)

    Instances of BOMReader are only used *once*. If a new BOM creation
    process is started, a fresh instance will be used.

    Implementations that want to support recursive invocation also need to
    supply a list of IDs of encountered documents in the attribute
    `referenced_docs` and optionally a list of the variant ids of the
    those documents in 'referenced_variant_ids'.
    see :func:`cs.vp.bomcreator.bomreader.make_recursive_reader_type`.

    Derived classes may have a static method :meth:`is_applicable_to`::

         @staticmethod
         def is_applicable_to(object_id)

    which must return False if the reader type cannot be used
    on the given object.
    `object_id` is typically the `cdb_object_id` of a document, but may also
    be the id of other business object types in future implementations.
    """

    def adjust_and_filter(self, attributes):
        """
        This method is a customization point to create specialized
        implementations that derive from existing BOM readers.

        `attributes` is a dictionary of `bom_item` attribute values.
        No guarantees are given about which attribute values are contained
        or about their format.

        The attributes may be modified to adjust the input data.

        Returns a Boolean indicating whether the entry with these attributes
        should be kept (`True`) or discarded (`False`).

        It is the responsibility of concrete implementations to **call** this
        method and respect the result.

        It is the responsibility of customizations of these implementations
        to **override** this method if they want to filter
        or adjust BOM entries.

        """
        return True

    def pre_show_component(self, bom, bom_entry, user_hints):
        """
        This method is called immediately before the preview is generated.
        At this point, automatically generated position numbers have become
        available.
        By default, it does nothing.

        Derived classes may inspect and change the attributes.

        If values of an existing component are changed, you must use the method
        :meth:`update_attribute` of :class:`cs.vp.bomcreator.bom.BOMEntry`!

        WARNING: You cannot use instance variables in this method.
        If you need persistent values, use :meth:`set_user_attribute` of class
        :class:`cs.vp.bomcreator.bom.GeneratedBOM` instead.

        :Parameters:
        - `bom`: :class:`cs.vp.bomcreator.bom.GeneratedBOM`
        - `bom_entry`: :class:`cs.vp.bomcreator.bom.BOMEntry`
        - `user_hints`: :class:`cs.vp.bomcreator.bom.UserHintList`
        """

    def post_write_component(self, bom, bom_entry, user_hints):
        """
        This method is called immediately after a component of a BOM has
        been written to the database. By default, it does nothing.

        Derived classes may inspect the attributes and
        status of the component (`bom_entry.attrs`, `bom_entry.status`),
        add warnings and errors to the `user_hints` or even cancel the
        process of writing the BOM by raising an exception derived from
        `RuntimeError`.

        WARNING: You cannot use instance variables in this method.
        If you need persistent values, use :meth:`set_user_attribute` of class
        :class:`cs.vp.bomcreator.bom.GeneratedBOM` instead.

        :Parameters:
        - `bom`: :class:`cs.vp.bomcreator.bom.GeneratedBOM`
        - `bom_entry`: :class:`cs.vp.bomcreator.bom.BOMEntry`
        - `user_hints`: :class:`cs.vp.bomcreator.bom.UserHintList`
        """

    def post_write_bom(self, bom, user_hints):
        """
        This method is called after all components of a BOM have been written
        to the database but before the transaction is committed
        and warnings and errors are displayed. By default, it does nothing.

        Derived classes may verify constraints and possibly cancel the process
        by raising an exception derived from `RuntimeError`.

        WARNING: You cannot use instance variables in this method.
        If you need persistent values, use :meth:`set_user_attribute` of
        :class:`cs.vp.bomcreator.bom.GeneratedBOM` instead.

        :Parameters:
        - `bom`: :class:`cs.vp.bomcreator.bom.GeneratedBOM`
        - `user_hints`: :class:`cs.vp.bomcreator.bom.UserHintList`
        """

    def post_write_boms(self, boms, user_hints):
        """
        This method is called after all BOMs of a document have been written
        to the database.

        If multiple BOMReader classes have been used to create the BOMs,
        this method will only be called for the BOMReader class of the first
        BOM.

        `bom` contains only the successfully written BOMs.

        WARNING: You cannot use instance variables in this method.
        If you need persistent values, use :meth:`set_user_attribute` of
        :class:`cs.vp.bomcreator.bom.GeneratedBOM` instead.

        :Parameters:
        - `boms`: list of :class:`cs.vp.bomcreator.bom.GeneratedBOM`
        - `user_hints`: :class:`cs.vp.bomcreator.bom.UserHintList`
        """

    def use_kernel_operations(self):
        """
        Whether to use kernel operations for saving changes in BOMs.

        If True, the BOMs are saved similarly to running the operation
        interactively. Notably, user exits (customization code) will be executed.

        If False, the BOMs are saved using a lower-level mechanism which does not
        call user-exits but is much faster.

        :return: boolean
        """
        return True

    def ignore_component_document(self, document, user_hints=None):
        """Checks whether the given document matches the object rule
        `BOM: Ignore Component Document`.
        """
        if user_hints is None and hasattr(self, '_bom'):
            user_hints = self._bom.user_hints
        try:
            ignore_it = document.MatchRule("BOM: Ignore Component Document")
            if ignore_it:
                self.log("Referenced document '%s-%s' ignored according"
                         " to object rule 'BOM: Ignore Component Document'"
                         % (document.z_nummer, document.z_index))
            return ignore_it
        except RuntimeError:
            if user_hints is not None:
                user_hints.append(msg('WSM_BOM_rule_not_found')
                                  % "BOM: Ignore Component Document")
            return False

    def ignore_component_item(self, item, user_hints=None):
        """Checks whether the given item matches the object rule
        `BOM: Ignore Component Item`.
        """
        if user_hints is None and hasattr(self, '_bom'):
            user_hints = self._bom.user_hints
        try:
            ignore_it = item.MatchRule("BOM: Ignore Component Item")
            if ignore_it:
                self.log("Position for part %s-%s ignored according"
                         " to object rule 'BOM: Ignore Component Item'" %
                         (item.teilenummer, item.t_index))
            return ignore_it
        except RuntimeError:
            if user_hints is not None:
                user_hints.append(msg('WSM_BOM_rule_not_found')
                                  % "BOM: Ignore Component Item")
            return False

    def ignore_variant(self, cad_variant, user_hints=None):
        """Checks whether the given CADVariant matches the object rule
        `BOM: Ignore Variant` or whether it is the only variant and matches
        the rule `BOM: Ignore Singleton Variant`.
        """
        if user_hints is None and hasattr(self, '_bom'):
            user_hints = self._bom.user_hints
        try:
            result = cad_variant.MatchRule("BOM: Ignore Variant")
            if result:
                self.log("CADVariant %s (%s) ignored according"
                         " to object rule 'BOM: Ignore Variant'"
                         % (cad_variant.variant_id, cad_variant.variant_name))
            else:
                result = self.ignore_singleton_variant(cad_variant)

            return result
        except RuntimeError:
            if user_hints is not None:
                user_hints.append(msg('WSM_BOM_rule_not_found')
                                  % "BOM: Ignore Variant"
                                    " or BOM: Ignore Singleton Variant")
            return False

    def ignore_singleton_variant(self, cad_variant):
        result = False
        if len(cad_variant.Document.CADVariants) == 1:
            result = cad_variant.MatchRule("BOM: Ignore Singleton Variant")
            if result:
                self.log("CADVariant %s (%s) ignored according"
                         " to object rule 'BOM: Ignore Singleton Variant'"
                         % (cad_variant.variant_id,
                            cad_variant.variant_name))
        return result

    def recursive_ignore_component(self, document, user_hints):
        """No BOM is created for documents that are encountered
        during recursive BOM creation and that match this rule."""
        try:
            ignore_it = document.MatchRule("BOM: Recursive Ignore Component")
            if ignore_it:
                self.log("Referenced document '%s-%s' ignored according"
                         " to object rule 'BOM: Recursive Ignore Component'"
                         % (document.z_nummer, document.z_index))
            return ignore_it
        except RuntimeError:
            user_hints.append(msg('WSM_BOM_rule_not_found')
                              % "BOM: Recursive Ignore Component")
            return False

    def log(self, msg):
        """Write a log message, prepended by the class name."""
        logging.info("%s: %s", self.__class__.__name__, msg)

    def get_referenced_doc(self, doc_id, user_hints):
        """Retrieves a referenced document by object id."""
        item_doc = ByID(doc_id)
        if item_doc is None:
            user_hints.append_error(
                msg('WSM_BOM_referenced_document_not_found') % doc_id)
        return item_doc

    def get_part_from_document(self, item_doc, variant_id, user_hints, variant_name=None):
        """
        Given a document and optionally a variant id,
        returns the associated part. Respects ignore rules.

        If the given variant does not have an item: falls back on the document.

        This methods is complicated because of E059471: change of variant ids.
        :returns: cs.vp.items.Item or None
        """
        item = None
        if variant_id is not None:
            variant = CADVariant.ByKeys(item_doc.z_nummer,
                                        item_doc.z_index,
                                        variant_id)
            if variant is None:
                # try to find by variant name
                # (use case: assembly uses new variant ids, component still has old variant id)
                if variant_name is not None:
                    variant = CADVariant.ByKeys(item_doc.z_nummer,
                                                item_doc.z_index,
                                                variant_name)
                if variant is None:
                    # try to use variant_id as variant_name
                    # (use case: assembly uses old variant ids, but component already has new variant id)
                    variants = CADVariant.KeywordQuery(z_nummer=item_doc.z_nummer,
                                                       z_index=item_doc.z_index,
                                                       variant_name=variant_id)
                    variants = list(variants)  # avoid multiple DB statements
                    if variants:
                        self.log("Found variant %s of document (%s, %s) by name instead of id. "
                                 % (variant_id,
                                    item_doc.z_nummer,
                                    item_doc.z_index))
                        variant = variants[0]
                    else:
                        self.log("Variant %s of document (%s, %s) not found. "
                                 "Using document article instead."
                                 % (variant_id,
                                    item_doc.z_nummer,
                                    item_doc.z_index))
                        # fall through and try to use document's part instead

            if variant is not None:
                if not self.ignore_variant(variant):
                    if not variant.teilenummer:
                        user_hints.append(msg('WSM_BOM_variant_no_part_assigned')
                                          % (variant.variant_name or variant_id,
                                             item_doc.z_nummer, item_doc.z_index))
                    else:
                        # When selecting an article for a variant with a browser,
                        # the field t_index of CADVariant stays at NULL/None
                        # if an article with t_index=u'' is chosen. (why?)
                        # Workaround here, otherwise the article is not found:
                        t_index = variant.t_index
                        if t_index is None:
                            t_index = u''
                        # end workaround
                        item = Item.ByKeys(variant.teilenummer, t_index)
                        if item is None:
                            user_hints.append(msg('WSM_BOM_variant_part_not_found')
                                              % (variant.teilenummer,
                                                 variant.t_index,
                                                 variant.variant_name or variant_id,
                                                 item_doc.z_nummer, item_doc.z_index))

        # find out part from document
        # (if variant not given or no success with variant)
        if not item:
            item = item_doc.Item
            if item is None:
                user_hints.append(msg('WSM_BOM_document_has_no_article')
                                  % (item_doc.z_nummer, item_doc.z_index))

        return item

    def get_assembly_from_document(self, item_doc, variant_id, user_hints, ignore_singleton_variant=False):
        """
        Find out the target for a BOM by document and optional variant id.
        This method will never use the item of the CAD document
         if a variant id is given.

        :returns: cs.vp.items.Item or None
        """
        item = None
        if variant_id is not None:
            variant = CADVariant.ByKeys(item_doc.z_nummer,
                                        item_doc.z_index,
                                        variant_id)
            if variant:
                if ignore_singleton_variant and self.ignore_singleton_variant(variant):
                    item = item_doc.Item
                else:
                    if variant.teilenummer:
                        # When selecting an article for a variant with a browser,
                        # the field t_index of CADVariant stays at NULL
                        # if an article with t_index=u'' is chosen. (why?)
                        # Workaround here, otherwise the article is not found:
                        t_index = variant.t_index
                        if t_index is None:
                            t_index = u''
                        # end workaround
                        item = Item.ByKeys(variant.teilenummer, t_index)
                        if item is None:
                            user_hints.append(msg('WSM_BOM_variant_assembly_not_found')
                                              % (variant.teilenummer,
                                                 variant.t_index,
                                                 variant_id,
                                                 item_doc.z_nummer, item_doc.z_index))
        else:
            item = item_doc.Item
            if item is None:
                user_hints.append(msg('WSM_BOM_document_has_no_article')
                                  % (item_doc.z_nummer, item_doc.z_index))

        return item

    def deserialize(self, context, factory):
        """
        private
        """


class SimpleBOMReader(BOMReader):
    """
    Base class for BOM reader implementations that

    * create only a single BOM
    * should automatically respect the current configuration
      (for display, merging and updating)

    Derived classes only have to implement :meth:`fill_BOM`.

    They don't need to define their own `__init__` method.

    Instances of derived classes are always created by the framework,
    never by user code. Instances are only used *once*. If a new BOM creation
    process is started, a fresh instance is created.
    """
    def __init__(self, bom_context, factory, _custom_state):
        self._factory = factory
        self._bom = factory.create_BOM()
        self.boms = [self._bom]
        self.fill_BOM(bom_context)

    def fill_BOM(self, bom_context):
        """
        This method must be overridden by derived classes.

        The method has the task to fill the associated BOM by calling
        :meth:`add_position`. It may call :meth:`add_error`/:meth:`add_warning`
        to show hints to the user.

        It may also raise :class:`BOMFatalError` in case of errors
        that prevent any creation of a meaningful BOM.

        :Parameters:

          - `bom_context`: :class:`BOMContext`
        """

    def add_position(self, **attrs):
        """
        Adds a position to the BOM of this reader.

        Depending on the configuration and the data, this may not actually
        add a new position. It may instead just increase the value of the
        `menge` attribute of an  existing position. In this case, the
        existing position is returned.

        This method respects the result of the inherited method
        :meth:`adjust_and_filter`,
        so the position may not actually be added if a custom implementation
        filters it.

        :Parameters:
          - any of the attributes of the CIM DATBASE class `bom_item`
            may be used as a keyword argument
          - `teilenummer`: part number; **required**
          - `t_index`: part version; optional; if not given, the latest version
            of the part is used
          - `position`: determines the item order of a BOM; if not given,
            an increasing value is automatically assigned
          - `menge`: amount; if not given, it will be set to 1.0
          - ...
        """
        keep_it = self.adjust_and_filter(attrs)
        if keep_it:
            entry = self._factory.create_BOMEntry(**attrs)
            return self._bom.add_entry(entry)
        else:
            return None

    def add_error(self, error_msg):
        """Adds an error message that will be logged and shown to the user.
        Calling this method does not prevent a successful BOM import.

        `error_msg` may contain line feeds.

        :Parameters:
          - `error_msg`: String
        """
        self._bom.user_hints.append_error(error_msg)

    def add_warning(self, msg):
        """Adds a warning message that will be logged and shown to the user.

        `msg` may contain line feeds.

        :Parameters:
          - `msg`: String
        """
        self._bom.user_hints.append(msg)


def create_and_sync(doc, errors_and_hints, FactoryClass=Factory, cadsource=None, item=None, create_json=False):
    """
    Create and and sync a BOM (or possibly a list of BOMs) for the given CAD
    document, using CAD-source-dependent configuration settings.
    The result must be saved with save_boms

    :Parameters
      - errors_and_hints: UserHintList
          receives error messages
      - factoryClass: for testing only
      - cadsource:  optional; otherwise taken from doc
      - item: optional Item; otherwise taken from doc
      - create_json: bool (whether to create a temporary JSON file of the BOM; this is usually only necessary
                           when saving the BOM from an eLink app)
    :returns: boolean, boolean, list of boms
              bom changed, list of boms to write to disk
              bom_content_changed content without index changes
    """
    boms = create_bom(doc, errors_and_hints, FactoryClass=FactoryClass, cadsource=cadsource, item=item)
    bom_changed = False
    bom_content_changed = False
    for b in boms:
        save_json = create_json and isinstance(doc, Object)
        changed, content_changed = b.synchronize(save_json)
        bom_changed = changed or bom_changed
        bom_content_changed = content_changed or bom_content_changed
        errors_and_hints.extend(b.user_hints)
    return bom_changed, bom_content_changed, boms


def save_boms(boms, errors_and_hints):
    """
    :Parameters
      - boms: List of BOMs
         BOMs that should be written into database
      - errors_and_hints: UserHintList
          receives error messages
    """
    success = True
    written_boms = []
    for b in boms:
        bom_success = b.write(errors_and_hints)
        if bom_success:
            written_boms.append(b)
        else:
            success = False

    if boms:
        first_bom_reader = boms[0].get_factory().reader if boms else None
        if first_bom_reader:
            first_bom_reader.post_write_boms(written_boms, errors_and_hints)

    delete_unused_new_articles(boms)
    if errors_and_hints.has_error():
        success = False

    return success


def create_and_save_bom(doc, errors_and_hints, FactoryClass=Factory, cadsource=None, item=None, create_json=False):
    """
    Create and saves a BOM (or possibly a list of BOMs) for the given CAD
    document, using CAD-source-dependent configuration settings.

    :Parameters
      - errors_and_hints: UserHintList
          receives error messages
      - factoryClass: for testing only

    :Returns bool
          whether the bom (or all BOMs) could be created and saved
    """
    _, _, boms = create_and_sync(doc,
                                 errors_and_hints, FactoryClass,
                                 cadsource=cadsource, item=item,
                                 create_json=create_json)
    return save_boms(boms, errors_and_hints)


def create_bom(obj, global_user_hints,
               custom_state=None,
               FactoryClass=Factory,
               variant_id=None,
               cadsource=None,
               item=None):
    """
    Create a BOM (or possibly a list of BOMs) for the given object,
    using CAD-source-dependent configuration settings.

    :Parameters
      - global_user_hints: UserHintList
          receives error messages that cannot be associated with
          a specific BOM.

      - custom_state: dictionary which can contain arbitrary information
            that BOMReader implementations want to thread
            through multiple invocations of a reader.

      - factoryClass: for testing only

      - variant_id: String
          optional variant id of the configuration we are interested in

      - cadsource: String
          optional value for the cad source (otherwise taken from obj.erzeug_system)
          (relevant for finding the right configuration and for the cadsource attribute of positions)
    """
    if cadsource is None:
        cadsource = obj.erzeug_system
    if item is None:
        item = obj.Item
    if item is None:
        global_user_hints.append_error(
            msg('WSM_BOM_root_obj_has_no_article') % obj.GetDescription())
        return []

    if custom_state is None:
        custom_state = dict()

    boms = []
    if isinstance(obj, Object) and obj.has_key("cdb_object_id"):
        bom_context_object = obj.cdb_object_id
    else:
        bom_context_object = obj

    context = BOMContext(bom_context_object,
                         item.teilenummer, item.t_index,
                         cadsource,
                         global_user_hints,
                         variant_id)
    try:
        boms_of_item = create_bom_from_bom_context(context,
                                                   custom_state,
                                                   FactoryClass)
        boms.extend(boms_of_item)
    except BOMFatalError as e:
        global_user_hints.append_error(u"%s" % e)

    return boms


def delete_unused_new_articles(boms):
    """
    Deletes any new article that is associated with one of the given BOMs
    if the article is not used in any saved BOM and not edited by the user.

    It is okay to call this function multiple times with the same argument.

    :Parameters:
      - boms: list(:class:`cs.vp.bomcreator.bom.GeneratedBOM`)
    """
    for b in boms:
        b.dispose_temporary_assembly_if_unused()


def create_bom_from_bom_context(context,
                                custom_state=None,
                                FactoryClass=Factory):  # for testability
    """Create a BOM or a list of BOMs according to the input data in context.
    :Parameters:
      - context: BOMContext
      - FactoryClass: only for testing
    """
    boms = []
    if custom_state is None:
        custom_state = dict()
    factory = FactoryClass(context)
    custom_state['global_user_hints'] = context.global_user_hints

    creator = factory.create_BOMReader(custom_state)
    if creator:
        boms = creator.boms
    else:
        context.global_user_hints.append_error(msg('WSM_BOM_reader_not_found')
                                               % factory.config_name)
    return boms


def make_recursive_reader_type(reader_class, result_order, max_depth=1000,
                               create_from_doc=create_bom):
    """
    Given a class that implements the BOMReader interface,
    creates a class that also implements this interface, but
    additionally creates BOMs for the referenced docs.

    In other words: Takes a non-recursive bom reader C and
    creates a recursive one, based on C.
    Ignores a document if it has encountered the document before
    (breaking cycles).

    :Parameters
      - reader_class: class
          a class derived from :class:`cs.vp.bomcreator.bomreader.BOMReader`
          instances of this class have to return a list of IDs of referenced
          documents in the attribute `referenced_docs`
      - result_order: :class:`ResultOrder`
          how to sort the tree of BOMs; either `ResultOrder.DepthFirst`
          or `ResultOrder.BreadthFirst`
      - max_depth: int
          maximum recursion depth (0:no limit)
    """
    class Reader(BOMReader):
        def __init__(self, bom_context, factory, state):
            self.log("started on object %s, for part %s-%s" %
                     (bom_context.object_id,
                      bom_context.teilenummer,
                      bom_context.t_index))
            self.referenced_docs = []  # this will always stay empty

            # check for cycle
            if 'traversed_parts' not in state:
                state['traversed_parts'] = set()
            traversed_parts = state['traversed_parts']
            this_part = bom_context.teilenummer, bom_context.t_index
            if this_part in traversed_parts:
                self.boms = []
                self.log("detected cycle; ignoring object")
                return
            traversed_parts.add(this_part)

            # check for max depth
            if 'current_depth' not in state:
                state['current_depth'] = 0
            current_depth = state['current_depth']
            current_depth += 1
            if max_depth > 0:
                if current_depth > max_depth:
                    self.boms = []
                    self.log("maximum recursion depth of %d reached"
                             % max_depth)
                    return
            state['current_depth'] = current_depth

            # create direct bom with non-recursive reader-type
            factory.reader_class = reader_class
            simple_reader = factory.create_BOMReader(state)
            self.boms = simple_reader.boms
            # for every referenced do:
            # collect boms, using the configured BOMReader
            boms_of_referenced = []
            self.log("processing referenced_docs")
            global_user_hints = state.get('global_user_hints', UserHintList())
            for i, referenced_doc_id in enumerate(simple_reader.referenced_docs):
                variant_id = None
                if hasattr(simple_reader, 'referenced_variant_ids'):
                    variant_id = simple_reader.referenced_variant_ids[i]
                obj = ByID(referenced_doc_id)
                if obj is None:
                    self.log("Referenced object %s not found."
                             % referenced_doc_id)
                else:
                    if self.recursive_ignore_component(obj, global_user_hints):
                        self.log(
                            "Ignoring referenced object %s according to rule."
                            % referenced_doc_id)
                    else:
                        self.log("Processing referenced object %s" %
                                 referenced_doc_id)

                        if isinstance(obj, Document):
                            cadsource = None  # will be taken from erzeug_system
                        else:
                            cadsource = bom_context.cadsource  # inherit from referencing object

                        boms_of_doc = create_from_doc(obj,
                                                      global_user_hints,
                                                      state,
                                                      variant_id=variant_id,
                                                      cadsource=cadsource)
                        boms_of_referenced.append(boms_of_doc)

            self.log("postprocessing referenced objects")
            # append results of referenced docs,
            # depending on requested result order
            # (we are only concerned with ordering the boms on the top level;
            # ordering on the deeper level is done
            # by deeper invocations of the reader)
            if result_order == ResultOrder.DepthFirst:
                for boms in boms_of_referenced:
                    self.boms.extend(boms)
            elif result_order == ResultOrder.BreadthFirst:
                # first collect the first one from every document
                for boms in boms_of_referenced:
                    if len(boms) >= 1:
                        self.boms.append(boms[0])
                    # and now the rest
                for boms in boms_of_referenced:
                    if len(boms) >= 2:
                        self.boms.extend(boms[1:])
            else:
                logging.error("bomcreator: unknown ResultOrder: %s", result_order)

        def deserialize(self, context, factory):
            factory.reader_class = reader_class
            factory.create_BOMReader(create_boms=False)  # needed for side effect

        def log(self, msg):
            """Overridden to provide more meaningfull prefix."""
            logging.info("Recursive (%s): %s", reader_class.__name__, msg)

    return Reader


class ResultOrder(object):
    DepthFirst = 0
    BreadthFirst = 1
