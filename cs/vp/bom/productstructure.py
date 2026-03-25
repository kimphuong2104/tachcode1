# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
FIXMEs:

Filter Rule:
- Rule im Standard leeren. Allg. Dokumentiereren. Release Notes.
- Update Task: Prädikat 'mBOM items without an engineering view' der Objektregel 'mBOM Manager: Ignore differences' löschen

"""

from collections import defaultdict
from datetime import datetime
from io import StringIO

from cdb import util
from cdb.objects import Rule

from cs.vp.bom import bomqueries
from cs.vp.items import Item

IMPRECISE_INDEX = "IMP"
FILTER_RULE = "mBOM Manager: Ignore differences"


class TreeNode:
    def __init__(self, parent, level, sort_id, record=None):
        self.record = record
        self.parent = parent
        if parent:
            parent.children.append(self)
        self.children = []
        self.quantity = None
        self.level = level
        self.sort_id = sort_id

    def path_from_root(self, full_records=False, path=None):
        if not path:
            path = []
        if self.parent:
            path += self.parent.path_from_root(full_records, path)
            path.append(self.record if full_records else self.record.cdb_object_id)
        return path

    def match(self, **kwargs):
        return all([self.record[k] == v for k, v in kwargs.items()])


class ProductStructure(object):

    def __init__(self, root_item, bom_enhancement=None):
        self.root_item = root_item
        self.bom_enhancement = bom_enhancement
        self.flat_bom = None
        self.tree = None
        self._nodes_by_item_oid = defaultdict(list)
        self._nodes_by_item_keys = defaultdict(list)
        self._nodes_by_item_number = defaultdict(list)
        self._node_by_bom_item_oid = {}
        self.flat_bom = bomqueries.flat_bom(self.root_item, bom_enhancement=self.bom_enhancement)
        self.tree = self._build_tree()

    def _build_tree(self):

        def _build(node, level=0, counter=0, visited_items=None):
            level += 1
            item_key = (node.record.teilenummer, node.record.t_index)
            visited_items = [item_key] if visited_items is None else visited_items
            for rec in records_by_assembly[(node.record.teilenummer, node.record.t_index)]:
                counter += 1
                child_node = TreeNode(node, level, counter, rec)
                child_item_key = (rec.teilenummer, rec.t_index)

                self._node_by_bom_item_oid[rec.cdb_object_id] = child_node
                self._nodes_by_item_oid[rec.item_object_id].append(child_node)
                self._nodes_by_item_keys[(rec.teilenummer, rec.t_index)].append(child_node)
                self._nodes_by_item_number[rec.teilenummer].append(child_node)
                if child_item_key in visited_items:
                    continue

                counter = _build(child_node, level, counter, [*visited_items, child_item_key])
            return counter

        records_by_assembly = defaultdict(list)
        for r in self.flat_bom:
            records_by_assembly[(r.baugruppe, r.b_index)].append(r)

        # sorting
        for children in records_by_assembly.values():
            children.sort(key=bomqueries.get_sort_key)

        root_node = TreeNode(None, 0, 0, self.root_item)
        root_node.quantity = 1.0
        _build(root_node)
        return root_node

    def __str__(self):

        def _write(node, depth=0):
            depth += 1
            for c in node.children:
                space = (depth - 1) * 3 * ' '
                txt = "%s %s %s/%s Qty:%s %s\n" % (space,
                                                   str(c.record.position).rjust(3, ' '),
                                                   c.record.teilenummer, c.record.t_index,
                                                   c.record.menge,
                                                   c.record.benennung)
                result.write(txt)
                _write(c, depth)

        result = StringIO()
        result.write("%s/%s\n" % (self.root_item.teilenummer, self.root_item.t_index))
        _write(self.tree)
        return result.getvalue()

    def get_node(self, bom_item_object_id):
        return self._node_by_bom_item_oid.get(bom_item_object_id)

    def get_nodes_by_item_number(self, part_number):
        return self._nodes_by_item_number.get(part_number, [])

    def get_imprecise_nodes(self, part_number):
        nodes = self.get_nodes_by_item_number(part_number)
        nodes = list(filter(lambda node: node.record.is_imprecise == 1, nodes))
        return nodes

    def get_nodes_by_item_keys(self, item_no, item_index):
        return self._nodes_by_item_keys.get((item_no, item_index), [])

    def get_nodes_by_item_oid(self, item_oid):
        return self._nodes_by_item_oid.get(item_oid, [])

    def get_quantities(self, imprecise):
        result = defaultdict(lambda: defaultdict(int))

        def _map(tnode, depth):
            if depth > 0:  # exclude root
                _op(tnode)
            for child in tnode.children:
                _map(child, depth + 1)

        def _op(tnode):
            if tnode.quantity is None:
                quantity = tnode.record.menge if tnode.record.menge else 0
                quantity *= tnode.parent.quantity
                tnode.quantity = quantity

            if tnode.record.is_imprecise == 1 and imprecise:
                index = IMPRECISE_INDEX
            else:
                index = tnode.record.t_index
            result[tnode.record.teilenummer][index] += tnode.quantity

        _map(self.tree, 0)
        return result

    def get_paths(self, part_no, part_index, full_records=False):
        result = []
        if part_index is None:
            nodes = self.get_nodes_by_item_number(part_no)
        else:
            nodes = self.get_nodes_by_item_keys(part_no, part_index)
        for node in nodes:
            result.append(node.path_from_root(full_records))
        return result

    def find_nodes(self, **kwargs):
        return [node for node in self._node_by_bom_item_oid.values() if node.match(**kwargs)]


class ProductStructureQuantityDiff(object):

    def __init__(self, master, derived):
        self.lps = master
        self.rps = derived
        self.lps_use_imprecise_indexes = False
        self.rps_use_imprecise_indexes = False
        self._diffs = None
        self._imp_diff_indexes = defaultdict(list)  # dict to remember consolidated indexes due to imprecise logic

    def get_diffs(self):
        lquantities = self.lps.get_quantities(imprecise=self.lps_use_imprecise_indexes)
        rquantities = self.rps.get_quantities(imprecise=self.rps_use_imprecise_indexes)
        return self.calculate_diff(lquantities, rquantities)

    def calculate_diff(self, lquantities, rquantities):

        def add_all_diffs(keys, quantities, op):
            for teilenummer in keys:
                for index, quant in quantities[teilenummer].items():
                    result[(teilenummer, index)] = quant if op == "+" else -quant

        def add_diffs(result_dict, teilenummer, keys, index_quantities, op):
            for index in keys:
                quant = index_quantities[index]
                result_dict[(teilenummer, index)] = quant if op == "+" else -quant

        def diff_indexes(teilenummer, lindexes_dict, rindexes_dict):
            lindexes = set(lindexes_dict)
            rindexes = set(rindexes_dict)

            _diffs = {}
            only_left_indexes = lindexes.difference(rindexes)
            add_diffs(_diffs, teilenummer, only_left_indexes, lindexes_dict, "-")
            only_right_indexes = rindexes.difference(lindexes)
            add_diffs(_diffs, teilenummer, only_right_indexes, rindexes_dict, "+")
            both_indexes = lindexes.intersection(rindexes)
            for index in both_indexes:
                diff = rindexes_dict[index] - lindexes_dict[index]
                if diff:
                    _diffs[(teilenummer, index)] = diff

            # handle imprecise diffs
            imp_diff = _diffs.get((teilenummer, IMPRECISE_INDEX))
            if imp_diff and len(_diffs) >= 2:
                # Wenn es genau einen precise Index Diff gibt, mit dem der Imprecise Diff verreichnet werden kann,
                # können die Mengen ausgeglichen werden
                precise_entry = None
                for key, quantity in _diffs.items():
                    if imp_diff > 0 and quantity < 0:
                        if precise_entry is not None:
                            precise_entry = None
                            break
                        precise_entry = key
                    elif imp_diff < 0 and quantity > 0:
                        if precise_entry is not None:
                            precise_entry = None
                            break
                        precise_entry = key
                if precise_entry:
                    self._imp_diff_indexes[precise_entry[0]].append(precise_entry[1])
                    quantity = _diffs[precise_entry]
                    if quantity + imp_diff == 0:
                        del _diffs[precise_entry]
                        del _diffs[(teilenummer, IMPRECISE_INDEX)]

                    elif imp_diff > 0 and quantity < 0:
                        # add to negative quantity
                        if quantity + imp_diff < 0:
                            _diffs[precise_entry] += imp_diff
                            del _diffs[(teilenummer, IMPRECISE_INDEX)]
                        elif quantity + imp_diff > 0:
                            del _diffs[precise_entry]
                            _diffs[(teilenummer, IMPRECISE_INDEX)] += quantity
                    elif imp_diff < 0 and quantity > 0:
                        #  remove from positive quantity
                        if quantity + imp_diff > 0:
                            _diffs[precise_entry] += imp_diff
                            del _diffs[(teilenummer, IMPRECISE_INDEX)]
                        elif quantity + imp_diff < 0:
                            del _diffs[precise_entry]
                            _diffs[(teilenummer, IMPRECISE_INDEX)] += quantity
                else:
                    if imp_diff > 0 and len(rquantities[teilenummer]) == 1 or \
                            imp_diff < 0 and len(lquantities[teilenummer]) == 1:
                        # If all occurrences of an item are imprecise on one side the quantities can be consolidated
                        # with any indices on the other side
                        for key in _diffs.keys():
                            self._imp_diff_indexes[key[0]].append(key[1])
                        quantity = sum(_diffs.values())
                        if quantity != 0:
                            _diffs = {(teilenummer, IMPRECISE_INDEX): quantity}
                        else:
                            _diffs = {}
                    else:
                        # In case of multiple indices all quantity diffs must fit into the imprecise diff.
                        c = 0
                        to_delete = []
                        for key, quantity in _diffs.items():
                            if imp_diff > 0 and quantity < 0:
                                c += quantity
                                to_delete.append(key)
                            if imp_diff < 0 and quantity > 0:
                                c += quantity
                                to_delete.append(key)

                        if (imp_diff > 0 and c + imp_diff >= 0) or (imp_diff < 0 and c + imp_diff <= 0):
                            new_imp_diff = c + imp_diff
                            if new_imp_diff == 0:
                                del _diffs[(teilenummer, IMPRECISE_INDEX)]
                            else:
                                _diffs[teilenummer, IMPRECISE_INDEX] = new_imp_diff
                            for key in to_delete:
                                self._imp_diff_indexes[key[0]].append(key[1])
                                del _diffs[key]

            result.update(_diffs)

        result = {}
        lkeys = set(lquantities)
        rkeys = set(rquantities)

        only_left = lkeys.difference(rkeys)  # all indexes are missing on right side
        add_all_diffs(only_left, lquantities, "-")
        only_right = rkeys.difference(lkeys)  # all indexes are superfluous on right side
        add_all_diffs(only_right, rquantities, "+")
        both = lkeys.intersection(rkeys)
        for teilenummer in both:
            diff_indexes(teilenummer, lquantities[teilenummer], rquantities[teilenummer])

        return result


class xBOMQuantityDiff(ProductStructureQuantityDiff):

    def __init__(self, master, derived):
        super().__init__(master, derived)
        self.lps_use_imprecise_indexes = False
        self.rps_use_imprecise_indexes = True
        self.lquantities = None
        self.rquantities = None

        self.depends_on_oid_mapping = {}
        self.depends_on_oids_by_part_no = defaultdict(list)

    def get_diffs(self):
        if self._diffs is None:
            self.lquantities = self.lps.get_quantities(imprecise=self.lps_use_imprecise_indexes)
            self.rquantities = self.rps.get_quantities(imprecise=self.rps_use_imprecise_indexes)

            self._pre_process_derived_sub_boms(self.rquantities)
            self._diffs = self.calculate_diff(self.lquantities, self.rquantities)
            self._filter_empty_cdb_depends_on()
            self._apply_filter_rule()
        return self._diffs

    def _pre_process_derived_sub_boms(self, quantities):
        master_items = set()
        replacements = set()
        for rec in self.rps.flat_bom:
            if rec.type_object_id == self.rps.root_item.type_object_id and rec.cdb_depends_on:
                master_items.add(rec.cdb_depends_on)
                index = IMPRECISE_INDEX if rec.is_imprecise else rec.t_index
                replacements.add((rec.teilenummer, index, rec.cdb_depends_on))

        # lookup master item oids on left product structure or load from db, if not found (diff case)
        to_load = []
        for oid in master_items:
            nodes = self.lps.get_nodes_by_item_oid(oid)
            if nodes:
                self.depends_on_oid_mapping[oid] = (nodes[0].record.teilenummer, nodes[0].record.t_index)
                self.depends_on_oids_by_part_no[nodes[0].record.teilenummer].append(oid)
            else:
                to_load.append(oid)

        for item in Item.KeywordQuery(cdb_object_id=to_load):
            self.depends_on_oid_mapping[item.cdb_object_id] = (item.teilenummer, item.t_index)
            self.depends_on_oids_by_part_no[item.teilenummer].append(item.cdb_object_id)

        for part_no, part_index, master_item_oid in replacements:
            master_item = self.depends_on_oid_mapping.get(master_item_oid)
            if master_item:
                quantity = quantities[part_no][part_index]
                del quantities[part_no][part_index]
                index = IMPRECISE_INDEX if part_index == IMPRECISE_INDEX else master_item[1]
                quantities[master_item[0]][index] += quantity

    def _get_object_ids(self):
        item_oids = set()
        for keys in self._diffs.keys():
            if keys[1] == IMPRECISE_INDEX:
                nodes = self.lps.get_nodes_by_item_number(keys[0])
                nodes += self.rps.get_nodes_by_item_number(keys[0])
                for n in nodes:
                    item_oids.add(n.record.item_object_id)
            else:
                nodes = self.rps.get_nodes_by_item_keys(*keys)
                if not nodes:
                    nodes = self.lps.get_nodes_by_item_keys(*keys)
                if nodes:
                    item_oids.add(nodes[0].record.item_object_id)
        return item_oids

    def _apply_filter_rule(self):
        filter_rule = Rule.ByKeys(FILTER_RULE)
        if filter_rule and filter_rule.Predicates:
            item_oids = list(self._get_object_ids())
            for item in Item.KeywordQuery(cdb_object_id=item_oids):
                if filter_rule.match(item):
                    if (item.teilenummer, item.t_index) in self._diffs:
                        del self._diffs[(item.teilenummer, item.t_index)]
                    elif (item.teilenummer, IMPRECISE_INDEX) in self._diffs:
                        del self._diffs[(item.teilenummer, IMPRECISE_INDEX)]

    def _filter_empty_cdb_depends_on(self):
        for keys in list(self._diffs):
            if keys[1] == IMPRECISE_INDEX:
                nodes = self.rps.get_nodes_by_item_number(keys[0])
                for node in nodes:
                    if node.record.is_imprecise and \
                            node.record.type_object_id == self.rps.root_item.type_object_id and \
                            not node.record.cdb_depends_on:
                        del self._diffs[keys]
                        break
            else:
                nodes = self.rps.get_nodes_by_item_keys(*keys)
                if nodes and \
                        nodes[0].record.type_object_id == self.rps.root_item.type_object_id and \
                        not nodes[0].record.cdb_depends_on:
                    del self._diffs[keys]


    def _get_nodes_for_derived_sub_bom(self, master_part_no, master_part_index):
        if master_part_no not in self.depends_on_oids_by_part_no:
            return []

        nodes_by_master_index = {}
        all_nodes = []

        for oid in self.depends_on_oids_by_part_no[master_part_no]:
            nodes = self.rps.find_nodes(cdb_depends_on=oid)
            nodes_by_master_index[self.depends_on_oid_mapping[oid][1]] = nodes
            all_nodes += nodes

        nodes = []
        if master_part_index == IMPRECISE_INDEX:
            # all imprecise nodes and all nodes of indexes which have been consolidated with imprecise occurrences
            nodes += list(filter(lambda node: node.record.is_imprecise == 1, all_nodes))
            for index in self._imp_diff_indexes.get(master_part_no, []):
                nodes += nodes_by_master_index.get(index, [])
            nodes = list(set(nodes))
        else:
            if master_part_no in self._imp_diff_indexes and master_part_index in self._imp_diff_indexes[master_part_no]:
                # all imprecise occurrences and all exact matching occurrences
                nodes = list(filter(lambda node: node.record.is_imprecise == 1 or node in nodes_by_master_index.get(master_part_index, []), all_nodes))
            else:
                # all exact matching precise occurrences
                nodes = list(filter(lambda node: node.record.is_imprecise == 0, nodes_by_master_index.get(master_part_index, [])))
        return nodes

    def get_differences_data(self, use_mapping=True):
        independent_index_label = util.get_label("web.bommanager.index_independent")

        self.get_diffs()
        result = {}
        for keys in self._diffs:
            part_no = keys[0]
            part_index = keys[1]
            data = {
                "teilenummer": part_no,
                "t_index": independent_index_label if part_index == IMPRECISE_INDEX else part_index
            }

            # get considered nodes for left and right structure
            if part_index == IMPRECISE_INDEX:
                rnodes = self.rps.get_imprecise_nodes(part_no)
                for index in self._imp_diff_indexes.get(part_no, []):
                    rnodes += self.rps.get_nodes_by_item_keys(part_no, index)

                rnodes += self._get_nodes_for_derived_sub_bom(*keys)
                rnodes = list(set(rnodes))

                lnodes = []
                for index in self._imp_diff_indexes.get(part_no, []):
                    lnodes += self.lps.get_nodes_by_item_keys(part_no, index)
            else:
                lnodes = self.lps.get_nodes_by_item_keys(*keys)
                if part_no in self._imp_diff_indexes and part_index in self._imp_diff_indexes[part_no]:
                    # all imprecise occurrences and all exact matching occurrences
                    rnodes = self.rps.get_nodes_by_item_number(part_no)
                    rnodes = list(filter(lambda node: node.record.is_imprecise == 1 or node.record.t_index == part_index, rnodes))
                    rnodes += self._get_nodes_for_derived_sub_bom(*keys)
                else:
                    # all exact matching precise occurrences
                    rnodes = self.rps.get_nodes_by_item_keys(*keys)
                    rnodes = list(filter(lambda node: node.record.is_imprecise == 0, rnodes))
                    rnodes += self._get_nodes_for_derived_sub_bom(*keys)

            # filter out nodes with same mapping tag and quantity on left and right side
            # (these nodes are not responsible for the diff and can be excluded from the search stepper)
            if use_mapping:
                lnodes_by_tag = defaultdict(list)
                for n in lnodes:
                    lnodes_by_tag[n.record.mbom_mapping_tag].append(n)
                rnodes_by_tag = defaultdict(list)
                for n in rnodes:
                    rnodes_by_tag[n.record.mbom_mapping_tag].append(n)
                lnodes = []
                rnodes = []
                all_mapping_tags = set(list(lnodes_by_tag.keys()) + list(rnodes_by_tag.keys()))
                for mapping_tag in all_mapping_tags:
                    _lnodes = lnodes_by_tag.get(mapping_tag, [])
                    _rnodes = rnodes_by_tag.get(mapping_tag, [])
                    if not mapping_tag or sum(node.quantity for node in _lnodes) != sum(node.quantity for node in _rnodes):
                        lnodes += _lnodes
                        rnodes += _rnodes

            lquant = sum(node.quantity for node in lnodes)
            rquant = sum(node.quantity for node in rnodes)
            diff = rquant - lquant
            if diff == 0:
                # In some cases, diff becomes 0 due to reverse mapping of cdb_depends_on
                continue

            data["diff"] = diff
            data["lbom_quantity"] = lquant
            data["rbom_quantity"] = rquant

            # sort by level for lowest level
            sorted_nodes = sorted(lnodes + rnodes, key=lambda node: node.level)
            level = sorted_nodes[0].level
            data["bom_level"] = level

            # append derived bom part number
            if part_no in self.depends_on_oids_by_part_no:
                # should be only one but in case of inconsistencies it could be more
                part_numbers = set([node.record.teilenummer for node in rnodes if node.record.cdb_depends_on])
                data["teilenummer"] += " / " + ", ".join(part_numbers)

            nodes_for_obj = rnodes if diff > 0 and rnodes else lnodes
            # sort by validity date to get latest item for item data
            always_valid = datetime(1900, 1, 1)
            sorted_nodes = sorted(nodes_for_obj, key=lambda node: node.record.item_ce_valid_from if node.record.item_ce_valid_from else always_valid)
            node = sorted_nodes[-1]
            data["t_kategorie"] = node.record.t_kategorie
            data["label"] = node.record.benennung
            data["item_object_id"] = node.record.item_object_id
            data["is_leaf"] = node.record.baugruppenart != "Baugruppe"

            # add path information for each node
            rnodes.sort(key=lambda node: node.sort_id)
            lnodes.sort(key=lambda node: node.sort_id)
            data["lpaths"] = [node.path_from_root() for node in lnodes]
            data["rpaths"] = [node.path_from_root() for node in rnodes]

            result[(part_no, part_index)] = data

        return result


def print_quantities(quantities, title):
    print(title)
    for teilenummer, d in quantities.items():
        print("%s" % teilenummer)
        for index, quantity in d.items():
            print("   '%s': %s" % (index, quantity))
