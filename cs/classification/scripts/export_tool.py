# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import argparse
import io
import os
import sys
from cdb import cdbuuid
from collections import defaultdict
from cdb.objects import ClassRegistry
from cdb.comparch.resolver import JsonWriter
from cdb.comparch import blob_utils
from cs.classification.classes import ClassificationClass
from cs.classification.tools import chunk


class Exporter(object):

    def __init__(self, exp_dir, with_subclasses=False, classes_to_export=None, chunk_size=10000):
        self.class_codes_to_export = classes_to_export
        self.with_subclasses = with_subclasses
        self.objects_by_type = defaultdict(set)
        self.exp_dir = exp_dir
        self.class_oids = []
        self.chunk_size = chunk_size
        if exp_dir:
            self.exp_filename = os.path.join(exp_dir, "data.json")
            self.blobs_dir = os.path.join(exp_dir, "blobs")
            os.mkdir(self.blobs_dir)

    def collect(self):
        rel = "cs_classification_class"
        py_cls = ClassRegistry().find(rel, True)
        if self.class_codes_to_export:
            class_codes = set(self.class_codes_to_export)
            if self.with_subclasses:
                class_codes.update(
                    ClassificationClass.get_sub_class_codes(class_codes=self.class_codes_to_export)
                )
            classes_to_export = py_cls.KeywordQuery(code=class_codes)
        else:
            classes_to_export = py_cls.Query()
        if not classes_to_export:
            print("Nothing to export")
            return
        self.objects_by_type["cs_classification_class"] = set(classes_to_export)
        self.class_oids = [clazz.cdb_object_id for clazz in self.objects_by_type["cs_classification_class"]]

        self._resolve_files()
        self._resolve_class_applicabilities()
        self._resolve_props()
        self._resolve_property_groups()
        self._resolve_constraints()
        self._resolve_table_columns()
        # resolve units
        self._resolve_units("cs_class_property")
        self._resolve_units("cs_property")
        self._resolve_units("cs_property_value")
        # resolve pattern
        self._resolve_pattern("cs_class_property")
        self._resolve_pattern("cs_property")
        self._resolve_pattern_character()
        # resolve catalog folder and assignments of used catalog properties
        self._resolve_catalog_folders()

    def _resolve_files(self):
        rel = "cdb_file"
        py_cls = ClassRegistry().find(rel, True)
        for class_oids in chunk(self.class_oids, self.chunk_size):
            files = py_cls.KeywordQuery(cdbf_object_id=class_oids)
            self.objects_by_type[rel].update(files)
            if self.exp_dir:
                blob_ids = [f.cdbf_blob_id for f in files]
                if blob_ids:
                    blob_utils.export_blobs(self.blobs_dir, blob_ids)

    def _resolve_class_applicabilities(self):
        rel = "cs_classification_applicabilit"
        py_cls = ClassRegistry().find(rel, True)
        for class_oids in chunk(self.class_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(classification_class_id=class_oids))

    def _resolve_property_groups(self):
        rel = "cs_class_property_group"
        py_cls = ClassRegistry().find(rel, True)

        for class_oids in chunk(self.class_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(classification_class_id=class_oids))
        property_groups = self.objects_by_type[rel]

        rel = "cs_property_group_assign"
        py_cls = ClassRegistry().find(rel, True)
        for group_oids in chunk([group.cdb_object_id for group in property_groups], self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(group_object_id=group_oids))

    def _resolve_props(self):
        rel = "cs_class_property"
        py_cls = ClassRegistry().find(rel, True)

        for class_oids in chunk(self.class_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(classification_class_id=class_oids))

        # resolve required catalog props
        props = self.objects_by_type[rel]
        rel = "cs_property"
        catalog_prop_codes = set([prop.catalog_property_code for prop in props])
        if catalog_prop_codes:
            py_cls = ClassRegistry().find(rel, True)

            for catalog_prop_codes_chunk in chunk(list(catalog_prop_codes), self.chunk_size):
                self.objects_by_type[rel].update(py_cls.KeywordQuery(code=catalog_prop_codes_chunk))

            # resolve block properties
            block_props = [prop for prop in self.objects_by_type[rel]
                           if prop.cdb_classname == "cs_block_property"]
            self._resolve_block_props(block_props)

            # resolve obj ref props
            obj_ref_props = [prop for prop in self.objects_by_type[rel]
                             if prop.cdb_classname == "cs_object_reference_property"]
            self._resolve_obj_ref_props(obj_ref_props)

        # resolve property values
        self._resolve_prop_values("cs_class_property")
        self._resolve_prop_values("cs_property")

        # resolve formulas and rules of properties
        self._resolve_formulas()
        self._resolve_rules()

    def _resolve_constraints(self):
        rel = "cs_classification_constraint"
        py_cls = ClassRegistry().find(rel, True)
        for class_oids in chunk(self.class_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(classification_class_id=class_oids))

    def _resolve_formulas(self):
        rel = "cs_classification_computation"
        py_cls = ClassRegistry().find(rel, True)
        prop_oids = [prop.cdb_object_id for prop in self.objects_by_type["cs_class_property"]]
        for prop_oids_chunk in chunk(prop_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(property_id=prop_oids_chunk))

    def _resolve_rules(self):
        rel = "cs_classification_rule"
        py_cls = ClassRegistry().find(rel, True)
        prop_oids = [prop.cdb_object_id for prop in self.objects_by_type["cs_class_property"]]
        for prop_oids_chunk in chunk(prop_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(class_property_id=prop_oids_chunk))

    def _resolve_table_columns(self):
        rel = "cs_class_table_columns"
        py_cls = ClassRegistry().find(rel, True)
        for class_oids in chunk(self.class_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(classification_class_id=class_oids))

    def _resolve_catalog_folders(self):

        def _resolve_parent_folders(folders):
            parent_folder_oids = set([folder.parent_id for folder in folders if folder.parent_id])
            if parent_folder_oids:
                parent_folders = py_cls.KeywordQuery(cdb_object_id=parent_folder_oids)
                self.objects_by_type[rel].update(parent_folders)
                _resolve_parent_folders(parent_folders)

        rel = "cs_property_folder_assignment"
        py_cls = ClassRegistry().find(rel, True)
        prop_oids = [prop.cdb_object_id for prop in self.objects_by_type["cs_property"]]
        if prop_oids:
            for prop_oids_chunk in chunk(prop_oids, self.chunk_size):
                self.objects_by_type[rel].update(py_cls.KeywordQuery(property_id=prop_oids_chunk))

            folder_oids = set([asgn.folder_id for asgn in self.objects_by_type[rel]])
            rel = "cs_property_folder"
            py_cls = ClassRegistry().find(rel, True)
            if folder_oids:
                folders = py_cls.KeywordQuery(cdb_object_id=folder_oids)
                self.objects_by_type[rel] = set(folders)
                _resolve_parent_folders(folders)

    def _resolve_pattern(self, prop_rel):
        rel = "cs_classification_pattern"
        py_cls = ClassRegistry().find(rel, True)
        pattern = set([prop.pattern for prop in self.objects_by_type[prop_rel] if prop.pattern])
        if pattern:
            pattern_objs = py_cls.KeywordQuery(pattern=pattern)
            self.objects_by_type[rel].update(pattern_objs)

    def _resolve_pattern_character(self):
        pattern_chars = set()
        for pattern in self.objects_by_type["cs_classification_pattern"]:
            for pattern_char in pattern.pattern:
                pattern_chars.add(pattern_char)
        if pattern_chars:
            rel = "cs_classification_symbol"
            py_cls = ClassRegistry().find(rel, True)
            symbols = py_cls.KeywordQuery(pattern_char=pattern_chars)
            self.objects_by_type[rel].update(symbols)

    def _resolve_units(self, prop_rel):
        rel = "cs_unit"
        py_cls = ClassRegistry().find(rel, True)
        if prop_rel == "cs_class_property":
            unit_oids = set([prop.default_unit_object_id for prop in self.objects_by_type[prop_rel]
                             if prop.default_unit_object_id])
        else:
            unit_oids = set([prop.unit_object_id for prop in self.objects_by_type[prop_rel]
                             if prop.unit_object_id])
        if unit_oids:
            units = py_cls.KeywordQuery(cdb_object_id=unit_oids)
            self.objects_by_type[rel].update(units)

    def _resolve_obj_ref_props(self, obj_ref_props):
        rel = "cs_classification_ref_appl"
        py_cls = ClassRegistry().find(rel, True)
        prop_oids = [prop.cdb_object_id for prop in obj_ref_props]
        for prop_oids_chunk in chunk(prop_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(property_id=prop_oids_chunk))

    def _resolve_block_props(self, block_props):
        if not block_props:
            return
        rel = "cs_block_prop_assign"
        py_cls = ClassRegistry().find(rel, True)

        block_prop_assignments = set()
        for block_prop_codes in chunk([prop.code for prop in block_props], self.chunk_size):
            block_prop_assignments.update(py_cls.KeywordQuery(block_property_code=block_prop_codes))
        self.objects_by_type[rel].update(block_prop_assignments)

        py_cls = ClassRegistry().find("cs_property", True)
        assigned_prop_codes = set([asgn.assigned_property_code for asgn in block_prop_assignments])
        assigned_props = set()
        for prop_codes_chunk in chunk(list(assigned_prop_codes), self.chunk_size):
            assigned_props.update(py_cls.KeywordQuery(code=prop_codes_chunk))
        self.objects_by_type["cs_property"].update(assigned_props)

        nested_blocks = [prop for prop in assigned_props if prop.cdb_classname == "cs_block_property"]
        self._resolve_block_props(nested_blocks)

    def _resolve_prop_values(self, prop_rel):
        rel = "cs_property_value"
        py_cls = ClassRegistry().find(rel, True)
        prop_oids = [prop.cdb_object_id for prop in self.objects_by_type[prop_rel]]

        for prop_oids_chunk in chunk(prop_oids, self.chunk_size):
            self.objects_by_type[rel].update(py_cls.KeywordQuery(property_object_id=prop_oids_chunk))

        if prop_rel == "cs_class_property":
            rel = "cs_property_value_exclude"
            py_cls = ClassRegistry().find(rel, True)
            for prop_oids_chunk in chunk(prop_oids, self.chunk_size):
                self.objects_by_type[rel].update(py_cls.KeywordQuery(class_property_id=prop_oids_chunk))

    def export(self):

        sort_functions = {
            "cdb_file": lambda obj: obj.cdbf_blob_id,
            "cs_block_prop_assign": lambda obj: (obj.block_property_code, obj.assigned_property_code),
            "cs_class_property": lambda obj: obj.code,
            "cs_class_property_group": lambda obj: obj.cdb_object_id,
            "cs_class_table_columns": lambda obj: (obj.classification_class_id, obj.class_property_id),
            "cs_classification_applicabilit": lambda obj: (obj.dd_classname, obj.classification_class_id),
            "cs_classification_class": lambda obj: obj.code,
            "cs_classification_computation": lambda obj: obj.cdb_object_id,
            "cs_classification_constraint": lambda obj: obj.cdb_object_id,
            "cs_classification_pattern": lambda obj: obj.pattern,
            "cs_classification_ref_appl": lambda obj: obj.cdb_object_id,
            "cs_classification_rule": lambda obj: obj.cdb_object_id,
            "cs_classification_symbol": lambda obj: obj.pattern_char,
            "cs_property": lambda obj: obj.code,
            "cs_property_folder": lambda obj: obj.cdb_object_id,
            "cs_property_folder_assignment": lambda obj: (obj.folder_id, obj.property_id),
            "cs_property_group_assign": lambda obj: (obj.group_object_id, obj.property_object_id),
            "cs_property_value": lambda obj: obj.cdb_object_id,
            "cs_property_value_exclude": lambda obj: (obj.classification_class_id, obj.class_property_id, obj.property_value_id),
            "cs_unit": lambda obj: obj.symbol
        }


        with io.open(self.exp_filename, "w") as jsonfile:
            json_strings = []
            rels = sorted(self.objects_by_type.keys())
            for rel in rels:
                objs = self.objects_by_type[rel]
                sort_func = sort_functions.get(rel, None)
                if sort_func:
                    dump_objs = sorted(objs, key=sort_func)
                else:
                    dump_objs = objs
                if dump_objs:
                    jsonwriter = MyJsonWriter(rel, "", "", [obj.ToJson() for obj in dump_objs])
                    json_strings.append(jsonwriter.dumps())
            json_string = "{%s\n}" % ",".join(json_strings)
            jsonfile.write(json_string)


class MyJsonWriter(JsonWriter):

    def dumps(self):
        _data = [self._obj_to_json(d) for d in self._data]
        result = """
  "%s": {
    "CONTENT": [
      %s
    ],
    "CONTENT_DOMAIN": "%s",
    "UPDATE_POLICY": "%s"
  }"""
        return result % (self._table_name,
                         ",\n      ".join(_data),
                         self._content_domain,
                         self._update_policy)


def run(exp_dir, with_subclasses=False, classes_to_export=None):
    if not os.path.exists(exp_dir):
        raise RuntimeError("Directory %s doesn't exist" % exp_dir)
    if os.path.isfile(exp_dir):
        raise RuntimeError("%s is an existing file" % exp_dir)
    target_dir = os.path.join(exp_dir, "%s_%s" % ("classification", cdbuuid.create_uuid()))
    os.mkdir(target_dir)
    exp = Exporter(target_dir, with_subclasses, classes_to_export)
    exp.collect()
    exp.export()
    return exp


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Utility to export classification classes including '
                    'all dependencies except base and sub classes'
    )
    parser.add_argument(
        '--classes',
        dest='classes_to_export',
        type=str,
        help='Commaseperated list of class codes to export'
    )
    parser.add_argument(
        '-r',
        dest='with_subclasses',
        action='store_true',
        help='Include all subclasses'
    )
    parser.add_argument(
        "exp_dir",
        help="Export destination directory"
    )
    args = parser.parse_args()

    try:
        classes = None
        if args.classes_to_export:
            classes = [class_code.strip() for class_code in args.classes_to_export.split(',')]
        exporter = run(args.exp_dir, args.with_subclasses, classes)
    except RuntimeError as e:
        print("%s" % e)
        sys.exit(42)
    else:
        print("Data has been exported to %s" % exporter.exp_dir)

