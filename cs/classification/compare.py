# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.classification import util
from cs.classification.classification_data import ClassificationData


class ClassificationDataComparator(object):

    def __init__(self, left_obj_id, right_obj_id, with_metadata=False, narrowed=True, check_rights=False):

        self.classification_is_equal = True
        self._left_data = ClassificationData(left_obj_id, narrowed=narrowed, check_rights=check_rights)
        self._right_data = ClassificationData(right_obj_id, narrowed=narrowed, check_rights=check_rights)

        assigned_classes_left = set(self._left_data.get_assigned_classes())
        assigned_classes_right = set(self._right_data.get_assigned_classes())

        self._assigned_classes = assigned_classes_left.intersection(assigned_classes_right)
        self._assigned_classes_left_only = assigned_classes_left.difference(assigned_classes_right)
        self._assigned_classes_right_only = assigned_classes_right.difference(assigned_classes_left)

        self._combined_data = ClassificationData(
            None, class_codes=assigned_classes_left.union(assigned_classes_right),
            narrowed=narrowed, check_rights=check_rights
        )
        self._combined_data._load_block_prop_details() # pylint: disable=W0212
        self._key_prop_codes = self._resolve_key_prop_codes(self._combined_data._block_details) # pylint: disable=W0212
        if with_metadata:
            self._metadata = self._combined_data.get_classification_metadata()
            if not narrowed:
                self._combined_data._calculate_client_view() # pylint: disable=W0212
        else:
            self._metadata = None

    def compare(self):
        self.classification_is_equal = True

        if self._assigned_classes_left_only or self._assigned_classes_right_only:
            self.classification_is_equal = False

        props_left = self._left_data.get_classification_data()
        props_right = self._right_data.get_classification_data()

        props_diff = self._compare_properties(props_left, props_right)

        return {
            "assigned_classes": list(self._assigned_classes),
            "assigned_classes_left": list(self._assigned_classes_left_only),
            "assigned_classes_right": list(self._assigned_classes_right_only),
            "classification_is_equal": self.classification_is_equal,
            "metadata": self._metadata,
            "properties": props_diff
        }

    def _compare_properties(self, props_left, props_right):
        props_diff = {}
        # strip empty values ?
        for prop_code in set(list(props_left.keys()) + list(props_right.keys())):
            values_left = props_left.get(prop_code, [])
            values_right = props_right.get(prop_code, [])
            props_diff[prop_code] = self._compare_values(prop_code, values_left, values_right)
        return props_diff

    def _compare_values(self, prop_code, values_left, values_right):
        if 1 == len(values_left) and 1 == len(values_right):
            return [self._compare_value(values_left[0], values_right[0])]
        else:
            return self._compare_multi_values(prop_code, values_left, values_right)

    def _compare_multi_values(self, prop_code, values_left, values_right):
        identifying_property_code = self._key_prop_codes.get(prop_code, '')
        positions_right = set()
        equal_values = []
        diff_values = []
        left_values = []
        for value_left in values_left:
            if identifying_property_code and identifying_property_code in value_left["value"]["child_props"]:
                id_value_left = value_left["value"]["child_props"][identifying_property_code][0]
            else:
                id_value_left = None
            pos_right = -1
            for pos, value_right in enumerate(values_right):
                if pos in positions_right:
                    # already compared
                    continue
                if identifying_property_code and identifying_property_code in value_right["value"]["child_props"]:
                    id_value_right = value_right["value"]["child_props"][identifying_property_code][0]
                    if self._are_values_equal(id_value_left, id_value_right):
                        props_diff = self._compare_properties(
                            value_left["value"]["child_props"], value_right["value"]["child_props"]
                        )
                        value_left["value"]["child_props"] = props_diff
                        if "id" in value_left:
                            del value_left["id"]
                        diff_values.append(value_left)
                        pos_right = pos
                        positions_right.add(pos_right)
                        break
                elif self._are_values_equal(value_left, value_right):
                    self._strip_ids(value_left)
                    equal_values.append(value_left)
                    pos_right = pos
                    break
            if -1 == pos_right:
                self.classification_is_equal = False
                self._strip_ids(value_left)
                value_left["value_left"] = value_left["value"]
                value_left["value_right"] = None
                del value_left["value"]
                if "addtl_value" in value_left:
                    value_left["addtl_value_left"] = value_left["addtl_value"]
                    value_left["addtl_value_right"] = None
                    del value_left["addtl_value"]
                left_values.append(value_left)
            else:
                positions_right.add(pos_right)
        compared_values = left_values + equal_values + diff_values
        for pos, value_right in enumerate(values_right):
            if pos not in positions_right:
                self.classification_is_equal = False
                self._strip_ids(value_right)
                compared_values.append(value_right)
                value_right["value_right"] = value_right["value"]
                value_right["value_left"] = None
                del value_right["value"]
                if "addtl_value" in value_right:
                    value_right["addtl_value_right"] = value_right["addtl_value"]
                    value_right["addtl_value_left"] = None
                    del value_right["addtl_value"]
        return compared_values

    def _compare_value(self, value_left, value_right):
        if "block" == value_left["property_type"]:
            props_diff = self._compare_properties(
                value_left["value"]["child_props"], value_right["value"]["child_props"]
            )
            value_left["value"]["child_props"] = props_diff
            if "id" in value_left:
                del value_left["id"]
            return value_left
        elif not self._are_values_equal(value_left, value_right):
            self.classification_is_equal = False
            self._strip_ids(value_left)
            value_left["value_left"] = value_left["value"]
            self._strip_ids(value_right)
            value_left["value_right"] = value_right["value"]
            del value_left["value"]
            if "addtl_value" in value_left:
                value_left["addtl_value_left"] = value_left["addtl_value"]
                value_left["addtl_value_right"] = None
                del value_left["addtl_value"]
            if "addtl_value" in value_right:
                value_left["addtl_value_right"] = value_right["addtl_value"]
        else:
            self._strip_ids(value_left)
        return value_left

    def _are_values_equal(self, value_left, value_right):
        if value_left:
            property_type = value_left["property_type"]
        elif value_right:
            property_type = value_right["property_type"]
        else:
            return True
        if "block" == property_type:
            for child_prop_code in list(value_left["value"]["child_props"].keys()) + list(value_right["value"]["child_props"].keys()):
                child_values_left = value_left["value"]["child_props"].get(child_prop_code, [])
                child_values_right = value_right["value"]["child_props"].get(child_prop_code, [])
                if not self._are_child_values_equal(child_values_left, child_values_right):
                    return False
            return True
        else:
            return util.are_property_values_equal(
                property_type, value_left["value"], value_right["value"], compare_normalized_values=False
            )

    def _are_child_values_equal(self, values_left, values_right):
        if len(values_left) != len(values_right):
            return False
        for value_left in values_left:
            pos_right = -1
            for pos, value_right in enumerate(values_right):
                if self._are_values_equal(value_left, value_right):
                    pos_right = pos
                    break
            if -1 == pos_right:
                return False
        return True

    def _resolve_key_prop_codes(self, props_data):
        key_prop_codes = {}
        for prop_code, prop in props_data.items():
            if "block" == prop["type"]:
                key_prop_code = prop["key_property_code"]
                if key_prop_code:
                    key_prop_codes[prop_code] = key_prop_code
                key_prop_codes.update(self._resolve_key_prop_codes(prop["child_props_data"]))
        return key_prop_codes

    def _strip_ids(self, value):
        property_type = value["property_type"]
        if "block" == property_type:
            if "id" in value:
                del value["id"]
            for _, child_values in value["value"]["child_props"].items():
                for child_value in child_values:
                    self._strip_ids(child_value)
        elif property_type in ["float_range", "multilang"]:
            if "id" in value:
                del value["id"]
            for _, val in value["value"].items():
                if "id" in val:
                    del val["id"]
        elif "id" in value:
            del value["id"]
        else:
            # nothing to do here
            pass
        return value
