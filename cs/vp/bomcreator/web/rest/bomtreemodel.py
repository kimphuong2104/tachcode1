#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
import glob
import logging
import os
import stat
import time
from collections import defaultdict
import six

from cs.platform.web.uisupport import get_ui_link
from cs.vp.bomcreator import UserHintList, msg, get_object, clear_message_cache, create_bom, GeneratedBOM


class BOMTreeModel(object):
    """
    Calculates the contents of the tree view of BOMs (on the left side of the preview).
    """
    def __init__(self, root, cadsource=None):
        """
        :param root: cdb_object_id of the root object (typically a Document)
        :param cadsource: optional cadsource (relevant for non-Documents)
        """
        self.root = root
        self.cadsource = cadsource
        self._global_errors = UserHintList()

    def create_result(self, request):
        self._garbage_collect_old_tempfiles()
        obj, error = get_object(cdb_object_id=self.root)
        if obj is None:
            self._global_errors.append_error(error)
            res = {'global_user_hints': self._global_errors,
                   'tree': [],
                   'title': ""}
        else:
            # avoid a restart due to changed messages or changes in their ignore status.
            clear_message_cache()
            # create synchronized bom(s)
            boms = create_bom(obj, self._global_errors, cadsource=self.cadsource)

            # TODO add temporary item for testing
            # top = boms[0]
            # temp1 = top._factory.create_assembly_and_BOM(t_kategorie="Baukasten")
            # temp2 = top._factory.create_assembly_and_BOM(t_kategorie="Baukasten")
            # temp1.create_and_add_entry(teilenummer=temp2.get_assembly().teilenummer, t_index=temp2.get_assembly().t_index)
            # top.create_and_add_entry(teilenummer=temp1.get_assembly().teilenummer, t_index=temp1.get_assembly().t_index)
            # boms.append(temp1)
            # boms.append(temp2)

            for b in boms:
                b.synchronize()

            tree = self._create_tree(boms)
            res = {'global_user_hints': self._global_errors.messages(),
                   'columns': self._columns(),
                   'rows': self._create_rows(boms),
                   'tree': tree,
                   'root_description': obj.GetDescription(),
                   'root_icon_link': obj.GetObjectIcon(),
                   'root_link': get_ui_link(request, obj)
                   }
        return res

    def _garbage_collect_old_tempfiles(self):
        # SIDE EFFECT: delete old temporary files
        # (because they do not get deleted
        #  if the user just closes the tab without saving or cancelling)
        MAX_AGE = 3600 * 72  # 3 days
        for f in glob.glob(GeneratedBOM.tempfile_pattern()):
            try:
                age = time.time() - os.stat(f)[stat.ST_MTIME]
                if age > MAX_AGE:
                    os.remove(f)
            except EnvironmentError:
                logging.error(u"Could not garbage-collect temporary BOM file %s", f)

    def _columns(self):
        return [
            {
                "label": msg("WSM_BOM_save_column"),
                "id": 'save',
                "width": "40px",
            },
            {
                "label": msg("WSM_BOM_item_column"),
                "id": 'item',
                "width": "100%",
            },
            {
                "label": msg("WSM_BOM_is_temporary_item"),
                "id": 'is_temporary_item',
                "width": "40px",
            },
            {
                "label": msg("WSM_BOM_readonly_column"),
                "id": 'readonly',
                "width": "80px",
            },
            {
                "label": msg("WSM_BOM_warnings_column"),
                "id": 'warnings',
                "width": "80px",
            },
            {
                "label": msg("WSM_BOM_numchanges_column"),
                "id": 'numchanges',
                "width": "85px",
            },
        ]

    def _create_rows(self, boms):
        rows = []
        for bom in boms:
            row = bom_to_tree_row(bom)
            rows.append(row)
        return rows

    def _create_tree(self, boms):
        """
        :param boms: list of BOMs
        :return: list representing the tree structure suitable for cs.web table
                 or None if bom structure is recursive (in this case, a global error is added)
        """
        res = None
        # we know nothing about the order of the BOMs, so we cannot assume a topological ordering;
        # first find all "head" parts and their ids
        part_keys_to_bom_id = {}
        for bom in boms:
            asm = bom.get_assembly()
            key = (asm.teilenummer, asm.t_index)
            part_keys_to_bom_id[key] = bom.instance_id

        # now create a mapping of bom ids which represents the tree structure
        structure = defaultdict(set)
        positions = defaultdict(lambda: defaultdict(int))
        for bom in boms:
            for entry in bom.entries():
                part_id = part_keys_to_bom_id.get((entry.attrs['teilenummer'], entry.attrs['t_index']))
                if part_id is not None:
                    structure[bom.instance_id].add(part_id)
                    positions[bom.instance_id][part_id] = entry.attrs['position']

        # find the toplevel bom(s)
        groups, remaining = toposort(structure)
        if remaining:
            error = msg('WSM_BOM_recursive_bom')
            self._global_errors.append_error(error)
        else:
            # create tree recursively
            res = []

            def recurse(bom_id):
                children_ids = structure[bom_id]
                # sort sub-components by position attribute
                children_ids = sorted(children_ids, key=lambda component_id: positions[bom_id][component_id])
                children = [recurse(child_id) for child_id in children_ids]
                return {"id": bom_id, "children": children}

            if groups:
                toplevels = groups[-1]
                for toplevel in toplevels:
                    res.append(recurse(toplevel))

            # special case: add isolated empty boms (not contained in "structure")
            all_in_structure = set().union(*groups)
            for bom in boms:
                if bom.instance_id not in all_in_structure:
                    res.append({"id": bom.instance_id, "children": []})
        return res


def toposort(data):
    """
    :param data dictionary whose values are sets
    :return: (list of sets, set)  the second element contains the remaining elements in case of cycles

    Adapted from:
    http://code.activestate.com/recipes/578272-topological-sort/

    >>> toposort({1:{2, 3}, 2:{3}, 3:set()})
    ([set([3]), set([2]), set([1])], set([]))
    """
    # remove self-references
    for k, v in list(data.items()):
        v.discard(k)
    groups = []
    # Find all items that don't depend on anything and add empty set
    extra_items_in_deps = (six.moves.reduce(set.union, iter(data.values()), set())  # pylint: disable=E1121
                           - set(data))
    for item in extra_items_in_deps:
        data[item] = set()

    while True:
        ordered = set(item for item, dep in data.items() if not dep)
        if not ordered:
            break
        groups.append(ordered)
        data = {item: (dep - ordered)
                for item, dep in data.items() if item not in ordered}

    return groups, set(data.keys())


def bom_to_tree_row(bom):
    is_changed = bom.num_changes() > 0 or bom.assemblyIsTemporary
    selected = bom.is_writeable and is_changed and not bom.user_hints.has_error()
    row = {"id": bom.instance_id,
           "columns": [
               selected,
               bom.get_assembly().GetDescription(),
               bom.assemblyIsTemporary,
               not bom.is_writeable,
               [bom.user_hints.has_error(), bom.user_hints.has_warning()],
               bom.num_changes()
           ],
           "is_writable": bom.is_writeable,
           "is_changed": is_changed,
           "assembly_is_temporary": bom.assemblyIsTemporary,
           "user_hints": bom.user_hints.messages()
           }
    return row
