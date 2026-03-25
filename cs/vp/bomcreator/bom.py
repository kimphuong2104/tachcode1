#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Classes representing BOMs and their entries.
"""

from __future__ import absolute_import
from collections import defaultdict
import math
import json
import datetime
import uuid
import os
import logging

from cdb import misc, sqlapi, transaction, util
from cdb.dberrors import DBConstraintViolation
from cdb.objects.operations import operation
from cdb.objects import Object
from cdb import auth
from cdb.i18n import FallbackLanguages
from cdb.platform.gui import Message
from cdb.fls import get_license
from cdb import CADDOK

from cs.vp.bom import AssemblyComponent, AssemblyComponentOccurrence
from cs.vp.items import Item
import six


class BOM(object):
    """
    A dictionary of :class:`BOMEntry` that keeps information about
    the order of entries.

    The order information is needed because it represents the sort value of
    occurrences which in turn is needed to give meaningful position values
    to new items and to display items in the right order.
    """
    def __init__(self):
        self._entries = dict()  # BOMEntry.key --> BOMEntry
        self._order = []  # list of keys in the order they were added

    def to_json(self):
        json_entries = []
        result = {'entries': json_entries}
        for key in self._order:
            json_entries.append(self._entries[key].to_json())
        return result

    def index_less_keys(self):
        return {e.index_less_key for e in self._entries.values()}

    def from_json(self, js):
        """
        Deserialize into an existing instance.
        """
        for json_entry in js['entries']:
            bom_entry = BOMEntry.from_json(json_entry)
            self._order.append(bom_entry.key)
            self._entries[bom_entry.key] = bom_entry

    def add_entry(self, new_entry):
        """
        Adds an entry to this BOM.
        If an equivalent entry already exists, updates `menge` and
        the occurrences. In this case, the existing entry is returned.

        :Parameters:
          - `new_entry`: :class:`cs.vp.bomcreator.bom.BOMEntry`
        """
        existing_entry = self._entries.get(new_entry.key)
        if existing_entry is not None:
            existing_entry.add_menge(new_entry.get_menge())
            for occ in new_entry.occurrences:
                existing_entry.add_occurrence(occ)
            return existing_entry
        else:
            self._entries[new_entry.key] = new_entry
            self._order.append(new_entry.key)
            return None

    def entries(self):
        """
        Entries in the order they were added.
        """
        return [self._entries[key] for key in self._order]

    def get_sort_val(self, entry):
        """
        Given a BOMEntry that must belong to this BOM:
        returns the entry's sort value as int.

        :Parameters:
          - `entry`: :class:`cs.vp.bomcreator.bom.BOMEntry`
        """
        return self._order.index(entry.key)

    def intersecting_entries(self, other):
        """
        Returns the list of BOMEntrys that are both in `self` and `other`.
        The result is unordered.

        :Parameters:
          - `other`: :class:`cs.vp.bomcreator.bom.BOM`
        """
        self_keys = set(self._entries.keys())
        other_keys = set(other._entries.keys())  # pylint: disable=protected-access
        common_keys = self_keys.intersection(other_keys)
        return ([(self._entries[key], other._entries[key])  # pylint: disable=protected-access
                 for key in common_keys])

    def entries_not_in(self, other):
        """
        Returns the list of BOMEntrys that are in `self` but not in `other`.
        The result is ordered as the entries were added to `self`.
        """
        other_keys = set(other._entries.keys())  # pylint: disable=protected-access
        filtered_order = [k for k in self._order if k not in other_keys]
        return [self._entries[k] for k in filtered_order]

    def index_less_equal(self, other):
        """
        compares two boms but doesn't consider the index of the entries
        """
        return self.index_less_keys() == other.index_less_keys()


class BOMEntry(object):
    """
    An entry in a BOM, containing information for
    displaying and synchronizing to the database.
    """

    # status constants
    # WARNING: the actual int values are relevant!

    # this entry has not been synchronized yet:
    Unknown = 0
    # this entry will be deleted in the DB:
    Deleted = 1
    # the entry existed before but some of the attributes have changed:
    Changed = 2
    # this is a completely new entry, it did not exist in the db before:
    New = 3
    # the new information contains the same information as previously
    # in the DB:
    Unchanged = 4

    def __init__(self, key, attributes, display_exprs, indexless_key=None):
        """Create a new BOMEntry.

        :Parameters:
         - key: tuple which determines the identity of an entry
         - attributes: dict with attributes directly corresponding to bom_item
              (must contain at least teilenummer, t_index, menge)
              Other primary key attributes (baugruppe, pos..)
              will be added later by synchronize.
         - display_exprs: list of names of expressions like "menge" or
              "Item.designation"
         - indexless_key: tuple wich determines the identity of entry without index
        """
        self.key = key
        self.index_less_key = indexless_key if indexless_key is not None else key
        self.attrs = attributes
        self.old_attrs = dict()  # contains old values of changed attributes
        assert('teilenummer' in attributes)
        assert('t_index' in attributes)
        assert('menge' in attributes)
        self.display_expressions = display_exprs

        self.occurrences = []  # list of OccurrenceInfo
        self.old_occurrences = None  # old occs when changed
        self.status = BOMEntry.Unknown
        self.status_message = msg('WSM_BOM_unchanged_component')
        # will contain a TableRow when prepared for display:
        self.display_row = None
        # id of the component;
        # for new components, this will be set only after the component was created in the DB
        self.cdb_object_id = self.attrs.get("cdb_object_id")

        # if True, this is an entry from the database and it should
        # only be replaced; never deleted
        self.only_for_replace = False

    def to_json(self):
        old_occurrences = None
        if self.old_occurrences is not None:
            old_occurrences = [occ.to_json() for occ in self.old_occurrences]
        return {
            'attrs': encode_attributes(self.attrs),
            'old_attrs': encode_attributes(self.old_attrs),
            'status': self.status,
            'status_message': self.status_message,
            'key': self.key,
            'occurrences': [occ.to_json() for occ in self.occurrences],
            'old_occurrences': old_occurrences,
            'cdb_object_id': self.cdb_object_id,
            'display_row': self.display_row.to_json(),
        }

    @staticmethod
    def from_json(js):
        attrs = decode_attributes(js['attrs'])
        res = BOMEntry(tuple(js['key']), attrs, display_exprs=[])
        res.display_row = TableRow.from_json(js['display_row'])
        res.cdb_object_id = js['cdb_object_id']
        res.old_attrs = decode_attributes(js['old_attrs'])
        res.status = js['status']
        res.status_message = js['status_message']
        for occ in js['occurrences']:
            res.occurrences.append(OccurrenceInfo.from_json(occ))
        if js['old_occurrences'] is not None:
            res.old_occurrences = []
            for occ in js['old_occurrences']:
                res.old_occurrences.append(OccurrenceInfo.from_json(occ))
        res.item = Item.ByKeys(res.attrs['teilenummer'],
                               res.attrs['t_index'])

        return res

    # Interface for creation and initial adjustment of BOMEntries

    def add_occurrence(self, occ):
        """Adds an occurrence to this entry.
        The occurrence will be stored in the DB in the 'write' method.
        Duplicate occurrences are ignored.

        :Parameters:
          - occ: OccurrenceInfo
        """
        if occ not in self.occurrences:
            self.occurrences.append(occ)
        else:
            logging.warning("bomcreator: ignoring duplicate occurrence %s"
                            " for position of article %s, %s",
                            occ.occurrence_id,
                            self.attrs.get('teilenummer', "missing"),
                            self.attrs.get('t_index', "missing"))

    def add_menge(self, additional):
        self.attrs['menge'] += additional

    def get_menge(self):
        return self.attrs['menge']

    def set_position(self, newpos):
        self.attrs['position'] = newpos

    def position(self):
        return self.attrs.get('position')

    # Interface for synchronizing

    def has_position(self):
        """
        Returns True iff the entry already has a position value,
        either as a simple value or wrapped by a SharedPosition.
        """
        if 'position' not in self.attrs:
            return False

        pos = self.position()
        if pos is None:
            return False

        if isinstance(pos, SharedPosition) and pos.value is None:
            return False

        return True

    def provide_position(self, position_number):
        if 'position' not in self.attrs or self.position() is None:
            self.set_position(position_number)
        else:
            self.instantiate_shared_position(position_number)

    def instantiate_shared_position(self, position_number=None):
        """Replaces a SharedPosition with its concrete value.

        If no position_number is given,
        the SharedPosition must already have a value."""
        if 'position' not in self.attrs:
            return

        pos = self.position()
        if not isinstance(pos, SharedPosition):
            return

        if pos.value is None:
            if position_number is None:
                raise ValueError("instantiate_shared_position called without "
                                 "position number even though the entry has no position value yet")
            pos.value = position_number
            self.set_position(position_number)
        else:
            self.set_position(pos.value)
            if position_number is not None and position_number != pos.value:
                # conflict: database value is different from shared value
                # -> keep the database value and log an error
                logging.error("bomcreator: entry has position number %s in database,"
                              " but has a shared position number of %s. Using database position number."
                              " (teilenummer: %s, t_index: %s)",
                              position_number, pos.value,
                              self.attrs.get('teilenummer', "missing"),
                              self.attrs.get('t_index', "missing"))

    MISSING_VALUE = object()

    def update_attribute(self, attr, value):
        """Updates or sets an attribute of the BOM entry.

        If the BOM entry was "unchanged" before, its status is updated to "changed" if the new value differs
        or was missing before.
        """
        old_val = self.attrs.get(attr, self.MISSING_VALUE)
        if old_val is self.MISSING_VALUE or not value_is_equal(old_val, value):
            self.attrs[attr] = value
            if self.status == self.Unchanged:
                self.set_changed()
            # log an error if the types of new and old values are incompatible
            if old_val is not self.MISSING_VALUE:
                self.old_attrs[attr] = old_val
                old_type = type(old_val)
                new_type = type(value)
                if new_type != old_type:
                    old_is_null = old_val is sqlapi.NULL
                    both_are_strings = isinstance(old_val, six.string_types) and isinstance(value, six.string_types)
                    if not old_is_null and not both_are_strings:
                        old_type = (u"%s" % old_type)[1:-1]
                        new_type = (u"%s" % new_type)[1:-1]
                        logging.error("BOMEntry.update_attribute: unexpected data type for attribute '%s': expected '%s', got '%s'", attr, old_type, new_type)

    def update_occurrences(self, occurrences):
        # still the same except for ordering?
        if set(occurrences) == set(self.occurrences):
            return
        self.old_occurrences = self.occurrences
        self.occurrences = occurrences
        was_unchanged = self.status == BOMEntry.Unchanged
        self.set_changed(because_of_occurrences_only=was_unchanged)

    def set_changed(self, because_of_occurrences_only=False):
        self.status = BOMEntry.Changed
        self.status_message = msg('WSM_BOM_changed_component')
        if because_of_occurrences_only:
            self.status_message = msg('WSM_BOM_changed_component_because_of_occurrences_only')

    def set_new(self):
        self.status = BOMEntry.New
        self.status_message = msg('WSM_BOM_new_component')

    def set_deleted(self):
        self.status = BOMEntry.Deleted
        self.status_message = msg('WSM_BOM_deleted_component')

    def prepare_display(self):
        """Prepare an entry for evaluation in the HTML generation."""
        # copy attributes and occurrences...
        attributes = self.attrs.copy()
        occ_ids = ', '.join([occ_info.occurrence_id
                             for occ_info in self.occurrences])
        attributes['occurrences'] = occ_ids
        old_attributes = self.old_attrs.copy()
        if self.old_occurrences is not None:
            old_occ_ids = ', '.join([occ_info.occurrence_id
                                     for occ_info in self.old_occurrences])
            old_attributes['occurrences'] = old_occ_ids
            # for new positions: add "empty values" for all database attributes
        if self.status == BOMEntry.New:
            for n in AssemblyComponent.GetFieldNames():
                if n not in attributes:
                    attributes[n] = ''
                    # replace NULLs with ""
        for attrDict in [attributes, old_attributes]:
            for k, v in six.iteritems(attrDict):
                if v is None:
                    attrDict[k] = ''
                    # ... and delegate to TableRow
        self.item = Item.ByKeys(self.attrs['teilenummer'],
                                self.attrs['t_index'])
        if self.item is None:
            logging.error("Could not find item '%s-%s' referenced by preview BOM for assembly '%s-%s'",
                          self.attrs['teilenummer'], self.attrs['t_index'],
                          self.attrs.get("baugruppe", "unknown"),
                          self.attrs.get("b_index", "unknown"))

        self.display_row = TableRow(self.display_expressions,
                                    attributes,
                                    old_attributes,
                                    self.item)

    def write(self, user_hints, use_kernel_operations):
        assert(self.status != BOMEntry.Unknown)
        if self.status == BOMEntry.New:
            return self._create_in_db(use_kernel_operations, user_hints)
        elif self.status == BOMEntry.Changed:
            return self._write_changes(use_kernel_operations, user_hints)
        elif self.status == BOMEntry.Unchanged:
            return True
        elif self.status == BOMEntry.Deleted:
            return self._delete_in_db(use_kernel_operations)
        else:
            logging.error("bomcreator: unknown BOMEntry status: %s", self.status)
            return False

    def _create_in_db(self, use_kernel_operations, user_hints):
        if use_kernel_operations:
            success = self._MOM_create()
        else:
            success = self._fast_create()
        return success and self._create_occurrences(self.occurrences, user_hints)

    def _write_changes(self, use_kernel_operations, user_hints):
        changed_dict = dict()
        for k in self.old_attrs:
            changed_dict[k] = self.attrs[k]
        if use_kernel_operations:
            if not self._MOM_update(changed_dict):
                return False
        else:
            if not self._fast_update(changed_dict):
                return False
        return self._sync_occurrences(user_hints)

    def _sync_occurrences(self, user_hints):
        """
        Create/update/delete bom_item_occurrences.
        This is called for "changed" items only.
        :param user_hints: UserHintList
        :return: bool
        """
        if self.old_occurrences is None:
            # this means: the occurrences are unchanged
            return True

        # find new, changed, deleted occurrences
        old_by_key = {occ.key(): occ for occ in self.old_occurrences}
        old_keys = set(old_by_key)
        current_by_key = {occ.key(): occ for occ in self.occurrences}
        current_keys = set(current_by_key)
        new_keys = current_keys - old_keys
        changed_keys = current_keys & old_keys
        to_delete_keys = old_keys - current_keys
        new_occs = [current_by_key[nk] for nk in new_keys]
        changed_occs = [current_by_key[nk] for nk in changed_keys]  # (potentially changed)
        occs_to_delete = [old_by_key[nk] for nk in to_delete_keys]

        self._delete_occurrences(occs_to_delete, user_hints)
        success = (self._update_occurrences(changed_occs, user_hints)
                   and
                   self._create_occurrences(new_occs, user_hints))
        return success

    def _delete_in_db(self, use_kernel_operations):
        if use_kernel_operations:
            return self._MOM_delete()
        else:
            return self._fast_delete()

    def _update_occurrences(self, changed_occs, user_hints):
        """
        :param changed_occs: potentially changed occurrences
        :return: bool
        """
        for occ_info in changed_occs:
            occ_key = self._occurrence_key(occ_info)
            obj = AssemblyComponentOccurrence.ByKeys(**occ_key)
            if obj is None:
                logging.error("BOM._update_occurrence: could not find occurrence to update. bom_item: %s, occurrence_id: %s, path: %s",
                              self._ident(),
                              occ_info.occurrence_id,
                              occ_info.reference_path)
                # don't make this error fail the operation; it is usually inconsequential
            else:
                obj.Update(relative_transformation=occ_info.tmatrix,
                           reference_path=occ_info.reference_path,
                           occurrence_variant_id=occ_info.occurrence_variant_id)
        return True

    def _create_occurrences(self, occurrences, user_hints):
        for occ_info in occurrences:
            occ_attrs = self._occurrence_key(occ_info)
            occ_attrs['reference_path'] = occ_info.reference_path
            occ_attrs['occurrence_variant_id'] = occ_info.occurrence_variant_id
            occ_attrs['relative_transformation'] = occ_info.tmatrix
            obj = AssemblyComponentOccurrence.Create(**occ_attrs)
            if obj is None:
                user_hints.append_error(
                    msg('WSM_BOM_could_not_create_occurrence')
                    % (occ_info.occurrence_id, self._ident()))
                return False
        return True

    def _delete_occurrences(self, occ_list, user_hints):
        if occ_list is not None:
            for occ_info in occ_list:
                occ_key = self._occurrence_key(occ_info)
                obj = AssemblyComponentOccurrence.ByKeys(**occ_key)
                if obj is None:
                    occ_id = occ_info.occurrence_id
                    user_hints.append_error(
                        msg('WSM_BOM_could_not_find_occurrence_to_delete')
                        % (occ_id, self._ident()))
                else:
                    obj.Delete()

    def _occurrence_key(self, occ_info):
        """
        Returns a key for a specific bom position.
        (Not the DB key which is a cdb_object_id, but an identifying key derived from the parent and data)
        :param occ_info: OccurrenceInfo
        :return: dict with the key attributes of a bom_item_occurrence
        """
        # the cdb_object_id of the bompos (required in 15.8)
        occ_key = {'bompos_object_id': self.cdb_object_id}
        occ_id = occ_info.occurrence_id
        occ_key['occurrence_id'] = occ_id
        occ_key['assembly_path'] = occ_info.assembly_path
        return occ_key

    def _ident(self):
        """Self description for user messages."""
        return "Position (" + self.cdb_object_id if self.cdb_object_id else "new" + ")"

    def _MOM_create(self):
        comp = operation("CDB_Create", AssemblyComponent, **self.attrs)
        self.cdb_object_id = comp.cdb_object_id
        return True

    def _fast_create(self):
        comp = AssemblyComponent.Create(**self.attrs)
        self.cdb_object_id = comp.cdb_object_id
        return True

    def _MOM_update(self, attrs):
        operation("CDB_Modify", self._get_component(), **attrs)
        return True

    def _fast_update(self, changed_dict):
        self._get_component().Update(**changed_dict)
        return True

    def _MOM_delete(self):
        operation("CDB_Delete", self._get_component())
        return True

    def _fast_delete(self):
        component = self._get_component()
        component.Occurrences.Delete()
        component.Delete()
        return True

    def _get_component(self):
        """self must have all the necessary key attributes.
        Which means that it must have been created from the database."""
        return AssemblyComponent.ByKeys(self.cdb_object_id)


def encode_attributes(attrs):
    # mask floats such that their type always survives the javascript round-trip
    res = attrs.copy()
    for k, v in six.iteritems(attrs):
        if isinstance(v, float):
            res[k] = {'type': "float", 'value': v}
    return res


def decode_attributes(attrs):
    res = attrs.copy()
    for k, v in six.iteritems(attrs):
        if isinstance(v, dict):
            if v.get('type') == "float":
                res[k] = float(v['value'])
    return res


class TableRow(object):
    """
    Calculates and represents the information needed to render a BOMEntry.
    """
    def __init__(self, display_expressions, attributes, old_attrs, item):
        self.floatFormatting = util.get_prop('flfo')
        position = FieldObject(attributes)
        full_old_attrs = attributes.copy()
        full_old_attrs.update(old_attrs)
        old_position = FieldObject(full_old_attrs)
        self.columns = []
        for expr in display_expressions:
            new_val = self._eval_expression(expr, position, item)
            old_val = self._eval_expression(expr, old_position, item)
            if old_val == new_val:
                old_val = None
            self.columns.append((expr, new_val, old_val))

    def to_json(self):
        return self.columns

    @staticmethod
    def from_json(js):
        row = TableRow([], {}, {}, None)
        row.columns = js
        return row

    SYNTAX_ERROR = "Syntax error: '%s' is not an expression" \
                   " of the form 'A' or 'A.B'."
    UNKNOWN_QUALIFIER = "Error: Unknown qualifier '%s'. The only allowed" \
                        " qualifiers are 'Item' and the empty qualifier."
    UNKNOWN_ATTRIBUTE = "Error: Unknown attribute '%s' of '%s'."

    def _eval_expression(self, expr, position, item):
        """Evaluates an expression like 'menge' or 'Item.designation'.
        """
        tokens = expr.split('.')
        if len(tokens) > 2:
            return self.SYNTAX_ERROR % expr
        qualifiers = {'': position, 'Item': item}
        if len(tokens) == 1:
            qualifier = ''
            attribute_name = tokens[0]
        else:
            qualifier = tokens[0]
            attribute_name = tokens[1]
        if qualifier not in qualifiers:
            return self.UNKNOWN_QUALIFIER % qualifier
        obj = qualifiers[qualifier]
        if not hasattr(obj, attribute_name):
            return self.UNKNOWN_ATTRIBUTE % (attribute_name, qualifier)
        attribute = getattr(obj, attribute_name)
        # We cannot directly check whether attribute is a localized field.
        # (LocalizedObjectWrapper is an internal class.)
        # But if the attribute is indexable by string keys,
        # it should be a localized field.
        try:
            attribute = localizedWithFallback(attribute)
        except TypeError:  # otherwise it is a simple value
            pass
        if isinstance(attribute, float):
            attribute = format_float(attribute, self.floatFormatting)
        return attribute


class FieldObject(object):
    """Creates an object from a dict."""
    def __init__(self, attributes):
        for k, v in list(six.iteritems(attributes)):
            setattr(self, k, v)


class OccurrenceInfo(object):
    """
    Data container for information about an occurrence.
    """
    def __init__(self, occurrence_id, reference_path, assembly_path,
                 occurrence_variant_id="", tmatrix="", occurrence_variant_name=""):
        # replace possible Nones with ""
        # because of Oracle NULL/empty string behaviour
        self.occurrence_id = occurrence_id or ""
        self.reference_path = reference_path or ""
        self.assembly_path = assembly_path or ""
        self.occurrence_variant_id = occurrence_variant_id or ""
        self.tmatrix = tmatrix or ""
        self.occurrence_variant_name = occurrence_variant_name or ""

    def key(self):
        """
        Key that makes an occurrence unique within its assembly.
        """
        return (self.reference_path, self.occurrence_id)

    def to_json(self):
        return {
            'occurrence_id': self.occurrence_id,
            'reference_path': self.reference_path,
            'assembly_path': self.assembly_path,
            'occurrence_variant_id': self.occurrence_variant_id,
            'tmatrix': self.tmatrix,
            'occurrence_variant_name': self.occurrence_variant_name
        }

    def __repr__(self):
        return repr(self.to_json())

    @staticmethod
    def from_json(js):
        return OccurrenceInfo(**js)

    # override identity to detect duplicates
    def __eq__(self, other):
        return self._cmpVal().__eq__(other._cmpVal())

    def __hash__(self):
        return hash(self._cmpVal())

    def _cmpVal(self):
        return (self.occurrence_id,
                self.reference_path,
                self.assembly_path,
                self.occurrence_variant_id,
                self.tmatrix)  # do not include occurrence_variant_name because we don't store it in db


class SharedPosition(object):
    """
    This class is useful if multiple BOM entries should receive the same
    generated position number.

    It can be used as the value of the 'position' attribute of an entry.
    If an instance of SharedPosition is used for multiple entries, they
    will receive the same position number when the BOM is synchronized.
    """
    def __init__(self):
        self.value = None


class GeneratedBOM(BOM):
    """
    A bill of materials that is generated from a business object (typically a CAD document).
    It is associated with an assembly (given by `bom_context`).

    After :meth:`synchronize`, it represents a merged bill of materials,
    containing information about entries to be created/deleted/changed.

    It also contains information to display the contents and status of
    all BOM positions.
    """
    def __init__(self, bom_context, factory, headers, new_positions_step):
        """BOMs are normally created using method :meth:`create_BOM` of class
        :class:`cs.vp.bomcreator.factory.Factory`.

        Its methods are normally called by the server code, not directly by
        customization code.

        :Parameters:
                - `bom_context`: :class:`cs.vp.bomcreator.bomreader.BOMContext`
                - `factory`: :class:`cs.vp.bomcreator.factory.Factory`
                - `headers`: list of strings that serve as column headers of
                   the HTML table
                - `new_position_step`: int
        """
        BOM.__init__(self)
        self._context = bom_context
        self._use_kernel_operations = True
        self._factory = factory
        self._assembly = Item.ByKeys(self._context.teilenummer,
                                     self._context.t_index)
        self.assemblyIsTemporary = False  # also used in HTML
        self._wasWritten = False
        self._assemblyDeleted = False
        self._assemblyIsModified = False

        # attributes for the HTML generating:
        self.id = self._assembly.cdb_object_id
        designation = self._assembly.i18n_benennung
        self.display_name = designation + " (" + self._assembly.teilenummer
        if self._assembly.t_index:
            self.display_name += "-" + self._assembly.t_index
        self.display_name += ")"

        self._visual_indent = 0

        self.is_writeable = True
        self.headers = headers
        self.user_hints = UserHintList()

        self.cadsource = bom_context.cadsource
        self.new_positions_step = new_positions_step

        # will contain a partition of entries for display:
        self.non_deleted_entries = None
        self.deleted_entries = None

        self._user_attributes = {}

        self.is_selected = True  # modified only on client

        self._pre_show_component = None
        self._post_write_component = None
        self._post_write_bom = None
        self.instance_id = None

    def get_factory(self):
        return self._factory

    @staticmethod
    def _temporary_json_path(instance_id):
        return misc.jail_filename(CADDOK.TMPDIR, u"bomcreator_%s_%s.json" % (auth.persno, instance_id))

    @staticmethod
    def tempfile_pattern():
        return GeneratedBOM._temporary_json_path("*")

    def write_to_disk(self):
        js = self.to_json()
        target = self._temporary_json_path(self.instance_id)
        with open(target, "w") as f:
            json.dump(js, f, cls=ReplaceDatetimeEncoder)

    @staticmethod
    def read_from_disk(instance_id):
        source = GeneratedBOM._temporary_json_path(instance_id)
        if not os.path.exists(source):
            raise RuntimeError(u"Cannot load BOM "
                               u"because file '%s' was unexpectedly deleted on the server."
                               % source)

        with open(source) as f:
            js = json.load(f, cls=ReplaceDatetimeDecoder)
        return GeneratedBOM.from_json(js)

    def delete_temporary_json(self):
        path = self._temporary_json_path(self.instance_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except EnvironmentError:
                logging.error(u"Could not delete temporary BOM file %s", path)

    def to_json(self):
        """
        Returns a dict that can be serialized to JSON.
        Contains all the information necessary to display and write the BOM.
        """
        if self.instance_id is None:
            self.instance_id = uuid.uuid4().hex
        result = BOM.to_json(self)
        result["headers"] = self.headers
        result["context"] = self._context.to_json()
        result["use_kernel_operations"] = self._use_kernel_operations
        result["id"] = self.id
        result["instance_id"] = self.instance_id
        result["assemblyIsTemporary"] = self.assemblyIsTemporary
        result["assemblyIsModified"] = self._assemblyIsModified
        result["user_attributes"] = filter_dict_serializable(self._user_attributes)
        result["is_selected"] = self.is_selected
        result["user_hints"] = self.user_hints.to_json()
        return result

    @staticmethod
    def from_json(js, FactoryClass=None):  # pylint: disable=arguments-differ
        """
        :param js: a dict as created by to_json
        :param FactoryClass for testing only
        :return: a GeneratedBOM
        """
        from cs.vp.bomcreator.bomreader import BOMContext, Factory  # pylint: disable=C0415

        # create a BOM object fully compatible to the original BOM
        if FactoryClass is None:
            FactoryClass = Factory
        context = BOMContext.from_json(js['context'])
        factory = FactoryClass(context)
        reader = factory.create_BOMReader(create_boms=False)
        reader.deserialize(context, factory)
        bom = factory.create_BOM()

        # fill the BOM instance with our data
        bom.instance_id = js['instance_id']
        bom.headers = js['headers']
        BOM._use_kernel_operations = js['use_kernel_operations']  # pylint: disable=protected-access
        bom.assemblyIsTemporary = js['assemblyIsTemporary']
        bom._assemblyIsModified = js['assemblyIsModified']  # pylint: disable=protected-access
        bom._user_attributes = js['user_attributes']  # pylint: disable=protected-access
        bom.is_selected = js['is_selected']
        bom.user_hints = UserHintList.from_json(js["user_hints"])
        BOM.from_json(bom, js)

        return bom

    def add_entry(self, new_entry):
        """
        Overridden to silently ignore components with the same part as the assembly itself
        """
        teilenummer = new_entry.attrs.get("teilenummer")
        t_index = new_entry.attrs.get("t_index")
        if teilenummer is not None:
            if t_index is None:
                t_index = ""
            baugruppe = self._context.teilenummer
            b_index = self._context.t_index or ""
            if teilenummer == baugruppe and t_index == b_index:
                logging.info("bomcreator: ignoring BOM entry with part identical to assembly (%s)",
                             new_entry.attrs)
                return None
        return BOM.add_entry(self, new_entry)

    def get_assembly(self):
        """
        Returns the :class:`cs.vp.items.Item` that this BOM belongs to.
        """
        return self._assembly

    def create_and_add_entry(self, **attrs):
        """
        Creates a BOM entry for this BOM, taking into account the current
        configuration.
        If an entry already exists for the given key attributes,
        the existing entry is returned.

        :Parameters:
           - `attrs`: dictionary containing values of `bom_item` attributes;
                      must contain at least `teilenummer`
        """
        return self.add_entry(self.create_entry(**attrs))

    def create_entry(self, **attrs):
        return self._factory.create_BOMEntry(**attrs)

    def merge_bom(self, other_bom):
        """
        Add all positions of `other_bom` to this bom.
        The positions are merged according to their key attributes.

        .. warning::
           The caller must ensure that there are no conflicting `position`
           numbers in the two BOMs.

        :Parameters:
                - `other_bom`: :class:`cs.vp.bom.BOM`
        """
        for bom_entry in other_bom.entries():
            self.create_and_add_entry(**bom_entry.attrs)

    def synchronize(self, json_data=True):
        """
        Creates a merged version of this BOM and the BOM of the associated
        assembly already existing in the database. The result is represented
        in this object, ready to be displayed and (after user confirmation)
        to be stored in the database.

        :Parameters:
              - `json_data`: bool

        returns bom_changed, bom_content_changed

        bom_changed is true if any record is changed included index changes on the same position

        bom_content_changed is true if a content changed or other componets are added or deleted (without regarding the t_index)
        """
        has_BOM_rights = self._has_BOM_rights()
        if not has_BOM_rights:
            self.user_hints.append(
                msg('WSM_BOM_rights_revoked') % self.display_name)

        has_required_license = self._check_license(self.user_hints)

        # used in HTML code
        self.is_writeable = has_BOM_rights and has_required_license

        # build a compatible representation of the existing BOM of our Item
        db_bom, other_cad_source_positions = self._build_db_bom()

        # for existing assembly components:
        for entry, db_entry in self.intersecting_entries(db_bom):
            # in case other entries want to use the same position number:
            entry.instantiate_shared_position(db_entry.position())
            # take some (configurable) attributes from the new entry, keep others
            self._factory.sync_BOMEntries(db_entry, entry)

            if entry.status == BOMEntry.Changed:
                self._check_for_used_posno(entry, other_cad_source_positions)

        # for deleted components: add to BOM with status Deleted
        # (in order to display the deleted entries and
        # possibly delete them later in 'write')
        toDelete = db_bom.entries_not_in(self)
        for db_entry in toDelete:
            if not db_entry.only_for_replace:
                db_entry.set_deleted()
                self.add_entry(db_entry)

        # for new components:
        # set status to New and
        # assign position to position-less entries
        all_entries = self.entries() + db_bom.entries()
        if all_entries:
            reusablePositions = ReusablePositionSupply()
            for entry in reversed(toDelete):
                if not entry.only_for_replace:
                    teilenummer = entry.attrs['teilenummer']
                    posnr = entry.attrs['position']
                    reusablePositions.add_by_teilenummer(teilenummer, posnr)
                    reusablePositions.add_by_occurrences(entry.occurrences, posnr)
                    reusablePositions.add_by_sort_val(db_bom.get_sort_val(entry), posnr)
            all_positions = [entry.position() for entry in all_entries
                             if entry.has_position() and not isinstance(entry.position(), SharedPosition)]
            all_positions.append(self._getMaxPosInDb())
            max_pos = max(all_positions)

            # first: try to get position by teilenummer or occurrence_id
            new_entries = self.entries_not_in(db_bom)
            for entry in new_entries:
                entry.set_new()
                if not entry.has_position():
                    # check if we have reusable positions for this part
                    # 1. check if new entry has the same teilenummer as a deleted entry (when a part was indexed)
                    teilenummer = entry.attrs['teilenummer']
                    pos = reusablePositions.get_by_teilenummer(teilenummer)
                    if pos is None:
                        # 2. check if the occurrence ids are the same as a deleted entry (when a part was copied)
                        pos = reusablePositions.get_by_occurrences(entry.occurrences)
                    if pos is not None:
                        entry.provide_position(pos)

                self._check_for_used_posno(entry, other_cad_source_positions)

            # for still missing positions: try to get by sortVal or create new position
            for entry in new_entries:
                if not entry.has_position():
                    sortVal = self.get_sort_val(entry)
                    pos = reusablePositions.get_by_sort_val(sortVal)
                    if pos is None:
                        # create a new position number
                        max_pos += self.new_positions_step
                        pos = max_pos
                    entry.provide_position(pos)
                    self._check_for_used_posno(entry, other_cad_source_positions)
                else:
                    entry.instantiate_shared_position()

        # allow customization immediately before display
        bom_content_changed = not self.index_less_equal(db_bom)
        bom_changed = False
        if self._pre_show_component:
            for entry in self.entries():
                self._pre_show_component(self, entry, self.user_hints)

        for entry in self.entries():
            entry.prepare_display()
            bom_changed = bom_changed or entry.status != BOMEntry.Unchanged
        # split for display
        self.deleted_entries = [e for e in self.entries()
                                if e.status == BOMEntry.Deleted]
        self.non_deleted_entries = [e for e in self.entries()
                                    if e.status != BOMEntry.Deleted]
        # make sure the lists are displayed sorted by position
        # (may not be the case if the position was predefined
        # in the input data and input entries were out of order)
        self.deleted_entries.sort(key=lambda e: e.position())
        self.non_deleted_entries.sort(key=lambda e: e.position())
        self.show_import_checkbox = (self.non_deleted_entries
                                     or self.deleted_entries
                                     or self.assemblyIsTemporary)
        # "<", "&", ">" will be escaped by the template engine
        # and unescaped by the Javascript code
        if json_data:
            self.write_to_disk()
        return bom_changed, bom_content_changed

    def num_changes(self):
        """
        :return: number of changes in BOM. Only valid after 'synchronize' has been called.
        """
        ret = 0
        for entry in self.entries():
            if entry.status != BOMEntry.Unchanged:
                ret += 1
        return ret

    def _build_db_bom(self):
        """
        Read the existing BOM from the database for merging.

        Read entries with different cadsource into a special dict to check
        for problems and produce warnings.

        :return pair (BOM, dict(posno->set(BOMEntry)))
        """
        db_bom = BOM()
        other_cadsource_positions = defaultdict(set)  # posno -> set(BOMEntry)
        for comp in self._assembly.Components:
            if comp.cadsource is None:
                comp_source = ""
            else:
                comp_source = first_source_part(comp.cadsource)
            bom_source = first_source_part(self.cadsource)
            equal_source = comp_source == bom_source
            source_to_replace = (self._factory.cadsource_to_replace
                                 and comp_source == self._factory.cadsource_to_replace)
            position_is_relevant = equal_source or source_to_replace
            attrs = dict((field, comp[field]) for field in comp.GetFieldNames())
            db_entry = self._factory.create_BOMEntry(**attrs)

            if position_is_relevant:
                for occ in comp.Occurrences:
                    occ_info = OccurrenceInfo(occ.occurrence_id,
                                              occ.reference_path,
                                              occ.assembly_path,
                                              occ.occurrence_variant_id,
                                              occ.relative_transformation)
                    db_entry.add_occurrence(occ_info)
                db_entry.only_for_replace = not equal_source
                db_bom.add_entry(db_entry)
            else:
                pos = db_entry.position()
                if pos is not None:
                    other_cadsource_positions[pos].add(db_entry)
        return db_bom, other_cadsource_positions

    def _check_for_used_posno(self, entry, other_cad_source_positions):
        """
        Check whether the posno of the given entry is already used in the database
        for a different cadsource.

        :param entry BOMEntry
        :param other_cad_source_positions  dict(posno->set(BOMEntry))
        """
        pos = entry.position()
        if pos is not None:
            other_cad_source_entries = other_cad_source_positions.get(pos, [])
            for other_cad_source_entry in other_cad_source_entries:
                cadsource = other_cad_source_entry.attrs.get('cadsource')
                # BOM can be saved, but is the reused posno intentional?
                self.user_hints.append(msg('WSM_BOM_duplicate_position_warning') % (pos, cadsource))

    def set_pre_show_component(self, callback):
        """
        Internal function. Should not be used by custom code directly.

        Registers a callback that is called for every component
        immediateley before the preview is generated.
        See :class:`cs.vp.bomcreator.bomreader.BOMReader` for details.
        """
        self._pre_show_component = callback

    def set_post_write_component(self, callback):
        """
        Internal function. Should not be used by custom code directly.

        Registers a callback that is called whenever a BOM component was
        written. See :class:`cs.vp.bomcreator.bomreader.BOMReader` for details.
        """
        self._post_write_component = callback

    def set_post_write_bom(self, callback):
        """
        Internal function. Should not be used by custom code directly.

        Registers a callback that is called when a BOM was
        written. See :class:`cs.vp.bomcreator.bomreader.BOMReader` for details.
        """
        self._post_write_bom = callback

    def set_use_kernel_operations(self, active):
        """
        Internal function. Should not be used by custom code directly.

        Whether to use kernel operations for saving.
        :param active: boolean
        """
        self._use_kernel_operations = active

    def _getMaxPosInDb(self):
        """
        Returns the maximum position number in the database BOM of this
        assembly. Takes into account all positions, independently of their
        cadsource.

        :return: Int
        """
        sql = ("SELECT MAX(position) max_pos FROM einzelteile"
               " WHERE baugruppe = '%s' AND b_index = '%s'"
               % (self._assembly.teilenummer, self._assembly.t_index))
        rset = sqlapi.RecordSet2(sql=sql)
        if len(rset) > 0 and rset[0]["max_pos"]:
            return int(rset[0]["max_pos"])
        else:
            return 0

    def write(self, user_hints):
        """Writes a generated BOM into the database
        (for the associated assembly).
        :meth:`synchronize` must have been called before.

        :Parameters:
          - `user_hints`: :class:`cs.vp.bomcreator.bom.UserHintList`
        """
        if not self._has_BOM_rights():
            user_hints.append_error(
                msg('WSM_BOM_rights_revoked') % self.display_name)
            return False

        if not self._check_license(user_hints):
            return False

        try:
            with transaction.Transaction():
                success = True
                entries = sorted(self.entries(), key=lambda e: e.status)
                for entry in entries:
                    try:
                        success = entry.write(user_hints, self._use_kernel_operations)
                        if not success:
                            break
                        if not self._use_kernel_operations:
                            self._assembly.Reload()  # keep object values up-to-date
                        if self._post_write_component:
                            self._post_write_component(self, entry, user_hints)
                    except Exception:  # pylint: disable=W0703
                        user_hints.append_error(
                            msg('WSM_BOM_error_writing_entry')
                            % (self._assembly.teilenummer, self._assembly.t_index, entry.cdb_object_id))
                        raise  # rolls back transaction!

                if not success:
                    user_hints.append_error(
                        msg('WSM_BOM_bom_not_imported')
                        % self.display_name)
                    return False
                # if there are new components,
                # make it an assembly (if it is not already)
                if not self._assembly.isAssembly():
                    if any(entry.status == BOMEntry.New
                           for entry in self.entries()):
                        if self._use_kernel_operations:
                            operation('CDB_Modify', self._assembly,
                                      baugruppenart="Baugruppe")
                        else:
                            self._assembly.baugruppenart = "Baugruppe"

                if self._post_write_bom:
                    self._post_write_bom(self, user_hints)

                user_hints.append_success(msg('WSM_BOM_bom_imported')
                                          % self.display_name)
                self._wasWritten = True
                return True
        except RuntimeError as ex:
            user_hints.append_error(u"%s" % ex)
            user_hints.append_error(msg('WSM_BOM_bom_not_imported')
                                    % self.display_name)
            return False

    def mark_assembly_as_temporary(self):
        """
        Mark the assembly of this BOM as temporary, i.e. it might have to
        be deleted later if not used. (internal)
        """
        self.assemblyIsTemporary = True

    def mark_assembly_as_modified(self):
        """
        Assembly has possibly been edited by the user. (internal)
        """
        self._assemblyIsModified = True

    def dispose_temporary_assembly_if_unused(self):
        """
        If this BOM has an unused temporary assembly, delete it. (internal)
        :param otherBoms: list(GeneratedBOM) to check of usage of assembly
        """
        if self.assemblyIsTemporary:
            if not self._assemblyDeleted and not self._wasWritten and not self._assemblyIsModified:
                try:
                    operation("CDB_Delete", self._assembly)
                    self._assemblyDeleted = True
                except Exception:  # pylint: disable=W0703
                    # assembly is probably used by other assembly
                    # ignore silently
                    pass

    def set_user_attribute(self, key, val):
        """
        Stores arbitrary key/value pairs in this BOM.
        This can be useful for custom BOMReader implementations that need to remember some values
        for later stages of BOM creation.

        For example::

          bom.set_user_attribute("is_main_bom", True)
          ...
          if bom.get_user_attribute("is_main_bom"):
              ...

        :Parameters:
                - `key`: str
                - `val`: simpe JSON-serializable value
        """
        self._user_attributes[key] = val

    def get_user_attribute(self, key, default=None):
        """
        Retrieve a value previously set with `set_user_attribute`.

        :Parameters:
                - `key`: str
        """
        return self._user_attributes.get(key, default)

    def set_visual_indent(self, indent):
        """
        Change the visual indent of the BOM in the preview.
        This can be useful if this BOM is displayed as part of a a hierarchy
        of BOMs.

        :Parameters:
                - `indent`: int
        """
        self._visual_indent = indent

    def get_margin(self):
        """
        Used from HTML. (internal)
        """
        return six.text_type(self._visual_indent * 20)

    def _has_BOM_rights(self):
        """Does the current user have the right to create, save and delete
        the BOM of our associated part?"""
        return (self._assembly.CheckAccess('create_bom')
                and self._assembly.CheckAccess('save_bom')
                and self._assembly.CheckAccess('delete_bom'))

    def _check_STL_license(self):
        # this license is already checked when starting the elink app
        # however, we check again, to secure direct invocations
        return get_license("BOMCREATOR_001")

    def _check_license(self, user_hints):
        """
        Check the license.
        """
        success = self._check_STL_license()
        if not success:
            user_hints.append_error(msg('WSM_BOM_BOMCreator_license_missing'))
        return success

    def _hasItemAsNewComponent(self, item):
        """
        :param item: Item
        :return: bool
        """
        for e in self.entries():
            if e.status == BOMEntry.New:
                if (e.attrs['teilenummer'] == item.teilenummer and
                            e.attrs['t_index'] == item.t_index):
                    return True
        return False


def value_is_equal(left, right):
    """
    Compares two values for equality.

    Takes into account that floating point values typically cannot be stored
    in the database with the same precision as Python's float.

    :returns bool
    """
    if type(left) is float and type(right) is float:
        if left == right:
            equal = True
        elif left == 0.0 or right == 0.0:
            # exactly one of the values is 0
            equal = False
        else:  # (none of the values is 0)
            db_epsilon = 1.0e-10
            left_exp = 10.0 ** int(math.log10(abs(left)))
            right_exp = 10.0 ** int(math.log10(abs(right)))
            if left_exp != right_exp:
                equal = False
            else:
                diff = abs(left / left_exp - right / right_exp)
                equal = diff < db_epsilon
    else:
        equal = left == right
    return equal


def first_source_part(cadsource):
    """
    Removes the second part of a CAD source if it exists.
    :param cadsource: string
    :return: string
    """
    split_source = cadsource.split(":")
    if len(split_source) > 1:
        cadsource = split_source[0]
    return cadsource


class BOMSuppressedMessage(Object):
    __maps_to__ = "bom_suppressed_message"
    __classname__ = "bom_suppressed_message"


IGNORE_PREFIX = "[IGNORED]"

# cache messages by label
# (will contain the IGNORE_PREFIX is message should be ignored)
message_cache = {}


def clear_message_cache():
    """
    To force loading messages from the database and reevaluating their ignore status.
    """
    message_cache.clear()


def msg(name):
    """
    Retrieves a message text in the current language (cached).
    Messages that should be ignored according the config, start with the IGNORE_PREFIX.

    :param name: the message label
    """
    txt = message_cache.get(name)
    if txt is None:
        m = Message.ByKeys(name)
        if m is not None:
            txt = m.message_ml
            if msg_is_ignored(name):
                txt = IGNORE_PREFIX + txt
        else:
            logging.error("bomcreator: could not find message '%s'", name)
            txt = name
        # make escaped "\n" in message work as real line feed
        txt = txt.replace("\\n", "\n")
        message_cache[name] = txt
    return txt


def msg_is_ignored(name):
    """
    :param name: Label of a message (meldungen).
    :return: Bool
    """
    return BOMSuppressedMessage.ByKeys(name) is not None


class UserHintList(object):
    """
    List of error messages and hints that have occurred
    during a BOM creation.
    Automatically logs all added messages.
    Implementations that derive from :class:`SimpleBOMReader`
    don't have to use this class directly.

    Implements a list-like interface.
    """
    def __init__(self):
        self._messages = []
        self._hasError = False
        self._hasWarning = False

    def messages(self):
        return self._messages

    def __iter__(self):
        return self._messages.__iter__()

    def __getitem__(self, key):
        return self._messages.__getitem__(key)

    def __len__(self):
        return self._messages.__len__()

    def append(self, msg):
        """Adds a string and logs it as a message."""
        if not msg.startswith(IGNORE_PREFIX):
            self._append((msg, 'warning'))
        logging.warning("bomcreator user hint: %s", msg)
        self._hasWarning = True

    def append_error(self, msg):
        """Adds a string and logs it as an error."""
        if msg.startswith(IGNORE_PREFIX):
            logging.warning("bomcreator: error messages cannot be ignored (%s)", msg)
            msg = msg[len(IGNORE_PREFIX):]
        self._append((msg, 'error'))
        logging.error("bomcreator error hint: %s", msg)

    def append_success(self, msg):
        """Adds a success message and logs it as a message."""
        if msg.startswith(IGNORE_PREFIX):
            logging.warning("bomcreator: success messages cannot be ignored (%s)", msg)
            msg = msg[len(IGNORE_PREFIX):]
        self._append((msg, 'success'))
        logging.info("bomcreator user hint: %s", msg)

    def extend(self, other):
        """Adds all messages of another UserHintList but does not log the
        messages again."""
        for msg in other._messages:  # pylint: disable=protected-access
            self._append(msg)

    def has_error(self):
        return self._hasError

    def has_warning(self):
        return self._hasWarning

    def _append(self, pair):
        self._messages.append(pair)
        if pair[1] == 'warning':
            self._hasWarning = True
        elif pair[1] == 'error':
            self._hasError = True

    def to_json(self):
        return self._messages

    @staticmethod
    def from_json(data):
        l = UserHintList()
        for msg in data:
            l._append(msg)  # pylint: disable=protected-access
        return l


def localizedWithFallback(field, allowEmpty=True):
    """
    Retrieves a text from a localized field, using fallback languages even
    if "fala" is not enabled for the field.

    :param field: a LocalizedField
    :param allowEmpty: if False, languages returning an empty string are
                       skipped
    """
    for lang in [''] + FallbackLanguages():
        t = field[lang]
        if allowEmpty:
            if isinstance(t, six.string_types):
                return t
        elif t:
            return t
    return u""


def format_float(val, flfo):
    formatString = "%%%sg" % flfo
    val = formatString % val
    return val


def filter_dict_serializable(d):
    result = {}
    for key, value in six.iteritems(d):
        try:
            json.dumps(key)
            json.dumps(value)
            result[key] = value
        except (TypeError, ValueError):
            pass
    return result


class ReplaceDatetimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return {
                'type': "datetime",
                'year': o.year,
                'month': o.month,
                'day': o.day,
                'hour': o.hour,
                'minute': o.minute,
                'second': o.second,
                'microsecond': o.microsecond
            }
        return json.JSONEncoder.default(self, o)


class ReplaceDatetimeDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, *args, object_hook=self.dict_to_object, **kwargs)

    def dict_to_object(self, d):
        if d.get('type') == "datetime":
            del d['type']
            return datetime.datetime(**d)
        return d


class ReusablePositionSupply(object):
    """
    Stores reusable position numbers.
    Those position numbers are accessible by multiple keys:
     - teilenummer
     - occurrence (id)
     - sort val of BOM entry
    """
    def __init__(self):
        self.positions_by_teilenummer = defaultdict(list)
        self.positions_by_occurrences = defaultdict(list)
        self.position_by_sortVal = dict()
        self.teilenummer_by_position = dict()
        self.occurrences_by_position = dict()
        self.sortVal_by_position = dict()

    def add_by_teilenummer(self, teilenummer, posnr):
        """
        Add a number for reuse.
        :param teilenummer: str
        :param posnr: int
        """
        self.positions_by_teilenummer[teilenummer].append(posnr)
        self.teilenummer_by_position[posnr] = teilenummer

    def add_by_occurrences(self, occurrences, posnr):
        """
        Add a number for reuse.
        :param occurrences: list of OccurrenceInfo (ordering doesn't matter)
        :param posnr: int
        """
        occurrence_ids = frozenset(occ.occurrence_id for occ in occurrences)
        if occurrence_ids:
            self.positions_by_occurrences[occurrence_ids].append(posnr)
            self.occurrences_by_position[posnr] = occurrence_ids

    def add_by_sort_val(self, sortVal, posnr):
        """
        Add a number for reuse.
        :param sortVal: int
        :param posnr: int
        """
        self.position_by_sortVal[sortVal] = posnr
        self.sortVal_by_position[posnr] = sortVal

    def get_by_teilenummer(self, teilenummer):
        """
        Consume a position number if there is one for the given teilenummer.
        :param teilenummer: str
        :return: int or None
        """
        posnr = None
        positions = self.positions_by_teilenummer.get(teilenummer)
        if positions:
            posnr = positions.pop()
            # make sure the posnr is also no longer accessible by other keys
            self._remove_by_occurrence(posnr)
            self._remove_by_sort_val(posnr)
        return posnr

    def get_by_occurrences(self, occurrences):
        """
        Consume a position number if there is one for the occurrences.
        :param occurrences: list of OccurrenceInfo (ordering doesn't matter)
        :return: int or None
        """
        occurrence_ids = frozenset(occ.occurrence_id for occ in occurrences)
        posnr = None
        positions = self.positions_by_occurrences.get(occurrence_ids)
        if positions:
            posnr = positions.pop()
            # make sure the posnr is also no longer accessible by other keys
            self._remove_by_teilenummer(posnr)
            self._remove_by_sort_val(posnr)
        return posnr

    def get_by_sort_val(self, sortVal):
        """
        Consume a position if there is one for the given sortVal.
        :param sortVal: int
        :return: int or None
        """
        posnr = self.position_by_sortVal.get(sortVal)
        if posnr is not None:
            self._remove_by_teilenummer(posnr)
            self._remove_by_occurrence(posnr)
        return posnr

    def _remove_by_occurrence(self, posnr):
        occurrence_ids = self.occurrences_by_position.get(posnr)
        if occurrence_ids:
            positions_by_occs = self.positions_by_occurrences.get(occurrence_ids)
            if positions_by_occs:
                positions_by_occs.remove(posnr)

    def _remove_by_sort_val(self, posnr):
        sortVal = self.sortVal_by_position.get(posnr)
        if sortVal is not None:
            self.position_by_sortVal.pop(sortVal, None)

    def _remove_by_teilenummer(self, posnr):
        teilenummer = self.teilenummer_by_position.get(posnr)
        if teilenummer:
            positions_by_teilenummer = self.positions_by_teilenummer.get(teilenummer)
            if positions_by_teilenummer:
                positions_by_teilenummer.remove(posnr)
