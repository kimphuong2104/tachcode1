#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


import argparse
import json
import logging
import os
import re
import sys

from collections import defaultdict
from cdbwrapc import PhysQuantity, sml_table

from cdb import ElementsError, cdbuuid
from cdb import transactions
from cdb import sqlapi
from cdb import i18n
from cdb.objects import paginated
from cdb.objects.core import ClassRegistry
from cdb.util import DBInserter

from cs.documents import Document
from cs.vp.classification import PropertyValue

from cs.classification import applicability, ObjectClassification, type_map,\
    tools
from cs.classification import catalog
from cs.classification import classes
from cs.classification import units
from cs.classification import util
from cs.vp.classification.sml import IMAGECLASSES
from cs.classification.units import UnitCache, Unit

LOG = logging.getLogger("cs.classification.sml_migration")


# Datentypen mapping
def get_prop_class(sml_prop_rec):
    mm_dt = sml_prop_rec.din4001_mm_dt
    # mm_v1 = sml_prop_rec.din4001_mm_v1
    mm_n1 = sml_prop_rec.din4001_mm_n1

    if mm_dt == "B":
        return catalog.BooleanProperty
    elif mm_dt == "Z":
        if not mm_n1:
            return catalog.IntegerProperty
        else:
            return catalog.FloatProperty
    elif mm_dt == "T":
        return catalog.TextProperty
    else:
        LOG.error(
            "Ignoring catalog property: prop_id='{}', mm_mk='{}': Invalid data type: '{}'".format(
                sml_prop_rec.prop_id, sml_prop_rec.din4001_mm_mk, mm_dt
            )
        )
        return None


class SMLMigration(object):

    def run(self, unit_helper, data_dir, lang, sml_root_code, schema_migration, data_migration, dry_run=True):
        with transactions.Transaction():
            code_helper = CodeHelper()
            self._run(code_helper, unit_helper, lang, sml_root_code, data_dir, schema_migration, data_migration)
            if dry_run:
                LOG.info("DRY RUN: No changes commited to database!")
                raise transactions.Rollback()

    def _run(self, code_helper, unit_helper, lang, sml_root_code, data_dir, schema_migration, data_migration):
        if schema_migration:
            LOG.info("Starting schema migration ...")
            prop_catalog_builder = self._process_prop_catalog(code_helper, unit_helper, lang)
            class_hierarchie_builder = self._process_class_hierarchie(
                code_helper, unit_helper, lang, sml_root_code, data_dir, prop_catalog_builder
            )
            class_mapping = class_hierarchie_builder.class_mapping
            property_mapping = class_hierarchie_builder.property_mapping
            LOG.info("Schema migration done.")
        else:
            LOG.info("Reading mapping files ...")
            class_mapping_file = os.path.join(data_dir, 'class_mapping.json')
            class_mapping = _load_json_file("class", class_mapping_file)
            if not class_mapping:
                LOG.fatal("No class mapping found. Skipping data migration.")
                _abort(11)
            property_mapping_file = os.path.join(data_dir, 'property_mapping.json')
            property_mapping = _load_json_file("property", property_mapping_file)
            if not property_mapping:
                LOG.fatal("No property mapping found. Skipping data migration.")
                _abort(12)
            LOG.info("Reading mapping files done.")
        if data_migration:
            LOG.info("Starting data migration ...")
            self._process_classification(class_mapping, property_mapping, unit_helper)
            LOG.info("Data migration done.")

    def _process_prop_catalog(self, code_helper, unit_helper, lang):
        prop_catalog_builder = PropCatalogBuilder(code_helper, unit_helper, lang)
        prop_catalog_builder.build()
        return prop_catalog_builder

    def _process_class_hierarchie(
        self, code_helper, unit_helper, lang, sml_root_code, data_dir, prop_catalog_builder
    ):
        class_hierarchie_builder = ClassHierarchieBuilder(
            code_helper, unit_helper, lang, sml_root_code, data_dir, prop_catalog_builder
        )
        class_hierarchie_builder.build()
        return class_hierarchie_builder

    def _process_classification(self, class_mapping, property_mapping, unit_helper):
        ClassificationBuilder(class_mapping, property_mapping, unit_helper).build()


class PropCatalogBuilder(object):

    OLD_ROOT_ID = "1"

    def __init__(self, code_helper, unit_helper, lang):
        self._code_helper = code_helper
        self._lang = lang
        self._unit_helper = unit_helper
        self._prop_without_cat = []

        self.props_done = {}
        self.prop_value_mapping = defaultdict(dict)

        # maps new catalog prop codes to sml prop_ids
        self.prop_codes_by_prop_id = {}

        # Read categories
        cdbsml_propcat = sqlapi.RecordSet2("cdbsml_propcat")
        self.cat_by_id = {}
        for cat in cdbsml_propcat:
            self.cat_by_id[cat.cat_id] = cat
            cat.children = []
            # cat.parent = None
            cat.props = []

        # Read hierarchy relationships
        for x in sqlapi.RecordSet2("cdbsml_propcathier"):
            parent = self.getcat(x.cat_id)
            child = self.getcat(x.child_id)
            if parent and child:
                parent.children.append(child)
                # child.parent = parent

        # Read props
        props_rset = sqlapi.RecordSet2("cdbsml_property")
        self._setup_prop_codes(props_rset)
        for prop in props_rset:
            ok = False
            if prop.cat_id:
                cat = self.getcat(prop.cat_id)
                if cat:
                    cat.props.append(prop)
                    ok = True
            if not ok:
                self._prop_without_cat.append(prop)

    def _setup_prop_codes(self, props_rset):
        props_by_code = defaultdict(list)
        for rec in props_rset:
            props_by_code[rec.din4001_mm_mk].append(rec)

        for code, recs in props_by_code.items():
            if len(recs) > 1:
                LOG.info(
                    "Catalog property code '{}' is not unique ({} properties):".format(
                        code, len(recs)
                    )
                )
                for rec in recs:
                    new_code = self._code_helper.get_property_code("{}_{}".format(code, rec.prop_id))
                    LOG.info(
                        "  Code of property with id '{}' will be changed from '{}' to '{}'".format(
                            rec.prop_id, code, new_code
                        )
                    )
                    self.prop_codes_by_prop_id[rec.prop_id] = new_code
            else:
                new_code = self._code_helper.get_property_code(code)
                if code != new_code:
                    LOG.info(
                        "  Code of property with id '{}' will be changed from '{}' to '{}'".format(
                            recs[0].prop_id, code, new_code
                        )
                    )
                self.prop_codes_by_prop_id[recs[0].prop_id] = new_code

    def get_code_for_prop_id(self, prop_id):
        return self.prop_codes_by_prop_id[prop_id]

    def getcat(self, myid):
        return self.cat_by_id.get(myid)

    def build(self):
        root = self.getcat(PropCatalogBuilder.OLD_ROOT_ID)
        self._build(root, None)

        for prop in self._prop_without_cat:
            self._create_prop(prop)

    def _build(self, node, parent):
        if node.cat_id == PropCatalogBuilder.OLD_ROOT_ID:
            # One single root node is not required any more.
            # All folders below the old root node are the new root nodes.
            # Props that are assigned to the old root folder are assigned to the new
            # All folder after migration.
            new_folder = None
        else:
            args = {
                "parent_id": parent.cdb_object_id if parent else ''
            }
            args.update(MultiLanguageHelper.get_multilanguage_attrs("cdbsml_propcat", "name_", node))
            new_folder = catalog.PropertyFolder.Create(**args)

        self._create_props(node, new_folder)
        for child in node.children:
            self._build(child, new_folder)

    def _create_props(self, node, new_folder):
        for prop in node.props:
            new_prop = self.props_done.get(prop.prop_id, None)
            if not new_prop:
                new_prop = self._create_prop(prop)
                if new_prop:
                    self.props_done[prop.prop_id] = new_prop
            # attach to folder
            if new_prop and new_folder:
                args = {
                    "folder_id": new_folder.cdb_object_id,
                    "property_id": new_prop.cdb_object_id
                }
                catalog.PropertyFolderAssignment.Create(**args)
                LOG.info("Catalog property {} added to folder '{}'".format(new_prop.code, new_folder.name_en))

    def _create_prop(self, prop):
        cls = get_prop_class(prop)
        if not cls:
            # Note: Invalid data type error is logged by get_prop_class
            return None

        if prop.din4001_mm_me and int(prop.din4001_mm_me) == 999:
            # Special case: Sennheiser Mixed Felder
            # clss = fields.DDSHMixed
            LOG.error("Sennheiser Mixed Felder will be ignored: {}".format(prop.prop_id))
            return None

        prop_args = {
            "cdb_status_txt": "Released",
            "status": 200,
            "cdb_objektart": "cs_property",
            "is_multivalued": 0,
            "is_enum_only": 1 if prop.use_pval_excl == "1" else 0,
            "code": self.get_code_for_prop_id(prop.prop_id),
            "default_value_oid": "",
            "has_enum_values": 1 if prop.use_pval == "1" else 0,
            "external_code": "",
            "external_system": "",
            "multiline": 1,
        }
        prop_args.update(MultiLanguageHelper.get_multilanguage_attrs("cdbsml_property", "name_", prop))
        if prop.prop_definition:
            key = "prop_description_{}".format(self._lang)
            prop_args[key] = prop.prop_definition
        if prop.mask_browser:
            LOG.warning("Mask browser for sml property {} will be ignored".format(prop.prop_id))
        unit_info = self._unit_helper.get_unit_info(prop.prop_id)
        if cls == catalog.FloatProperty:
            prop_args["no_decimal_positions"] = prop.din4001_mm_n1
            prop_args["no_integer_positions"] = prop.din4001_mm_v1
            if unit_info:
                prop_args["unit_object_id"] = unit_info['norm_unit_oid']
                prop_args["is_unit_changeable"] = len(unit_info['unit_mapping']) > 0
            else:
                prop_args["unit_object_id"] = None
                prop_args["is_unit_changeable"] = 0
        elif cls == catalog.TextProperty:
            prop_args["data_length"] = prop.din4001_mm_v1
        new_prop = cls.Create(**prop_args)
        LOG.info("Created catalog property {} for Characteristic {}".format(new_prop.code, prop.prop_id))
        # attach to all folder
        args = {
            "folder_id": catalog.PropertyFolder.ALL_PROPERTIES_FOLDER,
            "property_id": new_prop.cdb_object_id
        }
        catalog.PropertyFolderAssignment.Create(**args)

        # Create value list
        values = PropertyValue.KeywordQuery(prop_id=prop.prop_id)
        if len(values) and "1" != prop.use_pval:
            LOG.warning(
                "Property values of property '{}' are ignored because value range is not set.".format(
                    prop.prop_id
                )
            )
            return new_prop
        for v in values:
            t = cls.getType()
            if t == "boolean":
                continue
            value_cls = catalog.value_type_map[t]
            value_args = {"property_object_id": new_prop.cdb_object_id,
                          "is_active": 1}
            try:
                if t == "text":
                    value_args["text_value"] = v.pval_value
                elif t == "integer":
                    value_args["integer_value"] = int(v.pval_value)
                elif t == "float":
                    if prop.din4001_mm_me:
                        value, unit, _, _ = PhysQuantity(int(prop.din4001_mm_me), '', '').splitValue(v.pval_value)
                        value_args["float_value"] = value
                        value_args["unit_object_id"] = unit_info['unit_mapping'][unit]
                    else:
                        value_args["float_value"] = float(v.pval_value)
                        if prop.prop_unit:
                            value_args["unit_object_id"] = unit_info['default_unit_oid']
                else:
                    continue
            except (ElementsError, KeyError, ValueError):
                LOG.warning(
                    "Property value '{}' of property '{}' is invalid for data type '{}'. Value will be ignored.".format(
                        v.pval_value, prop.prop_id, t
                    )
                )
                continue
            else:
                prop_val = value_cls.Create(**value_args)
                LOG.info("Created catalog property value '{}' for property {}".format(v.pval_value, new_prop.code))
                self.prop_value_mapping[prop.prop_id][v.pval_value] = prop_val.cdb_object_id
        return new_prop


class ClassHierarchieBuilder(object):

    OLD_ROOT_ID = "root"

    def __init__(self, code_helper, unit_helper, lang, sml_root_code, data_dir, prop_catalog_builder):
        self._code_helper = code_helper
        self._data_dir = data_dir
        self._lang = lang
        self._sml_root_code = sml_root_code
        self._unit_helper = unit_helper
        self._prop_catalog_builder = prop_catalog_builder

        self._class_propset_mapping = {}
        self._property_mapping = defaultdict(dict)

        self._prop_sets = {}
        for prop_set in sqlapi.RecordSet2("cdbsml_propset"):
            prop_set.props = []
            self._prop_sets[prop_set.pset_id] = prop_set

        for prop_rel in sqlapi.RecordSet2("cdbsml_pset_prop"):
            prop_set = self._prop_sets.get(prop_rel.pset_id) # use get as prop_rel.pset_id can be empty!
            if prop_set:
                prop_set.props.append(prop_rel)

        self._groups_by_id = {}
        cdbsml_cgroups = sqlapi.RecordSet2("cdbsml_cgroup")
        for group in cdbsml_cgroups:
            self._groups_by_id[group.cgroup_id] = group
            group.children = []
            group.parent = None
            group.prop_sets = []

        group_parents = defaultdict(list)
        for group_parent_rel in sqlapi.RecordSet2("cdbsml_cg_hier"):
            group_parents[group_parent_rel.child_id].append(group_parent_rel.cgroup_id)

        for group_id, parent_ids in group_parents.items():
            if len(parent_ids) == 1:
                child = self._groups_by_id.get(group_id)
                parent = self._groups_by_id.get(parent_ids[0])
                if parent and child:
                    parent.children.append(child)
                    child.parent = parent
            else:
                LOG.warning(
                    "Group '{}' is added to root class as it has multiple parents: {}".format(
                        group_id, ', '.join(parent_ids)
                    )
                )

        prop_set_parents = defaultdict(list)
        for prop_set_rel in sqlapi.RecordSet2("cdbsml_cg_pset"):
            prop_set_parents[prop_set_rel.pset_id].append(prop_set_rel.cgroup_id)

        self._top_level_prop_sets = []
        for pset_id, parent_ids in prop_set_parents.items():
            prop_set = self._prop_sets.get(pset_id)
            if len(parent_ids) == 1:
                group = self._groups_by_id.get(parent_ids[0])
                if group and prop_set:
                    group.prop_sets.append(prop_set)
            elif prop_set:
                LOG.warning(
                    "Propset '{}' is added to root class as it has multiple parents: {}".format(
                        pset_id, ', '.join(parent_ids)
                    )
                )
                self._top_level_prop_sets.append(prop_set)

    @property
    def class_mapping(self):
        return self._class_propset_mapping

    @property
    def property_mapping(self):
        return self._property_mapping

    def build(self):
        class_args = {
            "code": self._code_helper.get_class_code(self._sml_root_code),
            "cdb_status_txt": "Released",
            "cdb_objektart": "cs_classification_class",
            "is_abstract": True,
            "is_exclusive": True,
            "name_de": self._sml_root_code,
            "name_en": self._sml_root_code,
            "parent_class_id": None,
            "status": 200
        }
        root_class = classes.ClassificationClass.Create(**class_args)
        appicalbility_args = {
            "classification_class_id": root_class.cdb_object_id,
            "dd_classname": "part",
            "is_active": 1,
            "write_access_obj": "save"
        }
        applicability.ClassificationApplicability.Create(**appicalbility_args)

        for group_id, group in self._groups_by_id.items():
            if group_id == ClassHierarchieBuilder.OLD_ROOT_ID:
                # old root class is not needed
                continue
            if group.parent is None or group.parent.cgroup_id == ClassHierarchieBuilder.OLD_ROOT_ID:
                self._create_class(group, root_class)

        for prop_set in self._top_level_prop_sets:
            self._create_property_set(prop_set, root_class)

        class_mapping_file = os.path.join(self._data_dir, 'class_mapping.json')
        _save_json_file("class", class_mapping_file, self._class_propset_mapping)

        property_mapping_file = os.path.join(self._data_dir, 'property_mapping.json')
        _save_json_file("property", property_mapping_file, dict(self._property_mapping))

    def _create_class(self, group, parent_class):
        class_args = {
            "code": self._code_helper.get_class_code(group.cgroup_id),
            "cdb_status_txt": "Released",
            "cdb_objektart": "cs_classification_class",
            "is_abstract": True,
            "parent_class_id": parent_class.cdb_object_id if parent_class else None,
            "status": 200
        }
        class_args.update(MultiLanguageHelper.get_multilanguage_attrs("cdbsml_cgroup", "name_", group))
        new_class = classes.ClassificationClass.Create(**class_args)
        LOG.info(
            "Created classification class {} for Characteristics Group {}".format(
                class_args["code"], group.cgroup_id
            )
        )
        self._build_documents(
            new_class,
            "select * from cdbsml_cg_docs where cgroup_id='{}' order by purpose".format(group.cgroup_id)
        )
        for prop_set in group.prop_sets:
            self._create_property_set(prop_set, new_class)
        for child_group in group.children:
            self._create_class(child_group, new_class)

    def _create_property_set(self, prop_set, parent_class):

        class_args = {
            "code": self._code_helper.get_class_code(prop_set.pset_id),
            "cdb_status_txt": "Released",
            "cdb_objektart": "cs_classification_class",
            "parent_class_id": parent_class.cdb_object_id if parent_class else None,
            "status": 200
        }
        class_args.update(MultiLanguageHelper.get_multilanguage_attrs("cdbsml_propset", "name_", prop_set))

        tags = {}
        stmt = "select * from cdbsml_pset_names where pset_id = '{}'".format(prop_set.pset_id)
        names = sqlapi.RecordSet2(sql=stmt)
        for name in names:
            tag = MultiLanguageHelper.get_multilanguage_attrs("cdbsml_pset_names", "name_", name)
            for key, tag_val in tag.items():
                if key in tags and tags[key]:
                    tags[key] = "{} {}".format(tags[key], tag_val)
                else:
                    tags[key] = tag_val
        class_args.update(tags)

        new_class = classes.ClassificationClass.Create(**class_args)
        self._class_propset_mapping[prop_set.pset_id] = new_class.code
        LOG.info(
            "Created classification class {} for Class List of Characteristics {}".format(
                class_args["code"], prop_set.pset_id
            )
        )
        self._build_class_properties(new_class, prop_set)
        update_args = {}
        if prop_set.textrule:
            key = "class_description_tag_{}".format(self._lang)
            update_args[key] = self._convert_textrule(prop_set)

        if update_args:
            new_class.Update(**update_args)

        self._build_documents(
            new_class,
            "select * from cdbsml_pset_doc where pset_id='{}' order by purpose".format(prop_set.pset_id)
        )

        stmt = "select * from cdbsml_preset where pset_id = '{}'".format(prop_set.pset_id)
        presets = sqlapi.RecordSet2(sql=stmt)
        if len(presets):
            LOG.warning(
                "Presets found for pset_id = '{}'. Presets are not supported from cs.classifcation!".format(
                    prop_set.pset_id
                )
            )

        stmt = "select * from cdbsml_pset_view where pset_id = '{}'".format(prop_set.pset_id)
        cad_views = sqlapi.RecordSet2(sql=stmt)
        if len(cad_views):
            LOG.warning(
                "CAD views found for pset_id = '{}'. CAD views are not supported from cs.classifcation!".format(
                    prop_set.pset_id
                )
            )

    def _build_class_properties(self, new_class, prop_set):
        for prop in prop_set.props:
            catalog_property = self._prop_catalog_builder.props_done.get(prop.prop_id, None)
            if not catalog_property:
                continue
            pros_args = {
                "code": self._code_helper.get_property_code("{}_{}".format(new_class.code, prop.prop_mk)),
                "catalog_property_code": catalog_property.code,
                "classification_class_id": new_class.cdb_object_id,
                "catalog_property_id": catalog_property.cdb_object_id,
                "default_unit_object_id": catalog_property.unit_object_id,
                "cdb_objektart": "cs_class_property",
                "display_option": "New Line",
                "position": prop.prop_nr,
                "status": 200
            }
            # prop.prop_browser is not supported in cs.classification
            pros_args.update(catalog_property.getClassDefaults())
            clazz = classes.type_map[catalog_property.getType()]
            new_prop = clazz.Create(**pros_args)
            prop_info = {
                "sml_prop_id": prop.prop_id,
                "code": new_prop.code,
                "type": new_prop.getType(),
                "unit_object_id": new_prop.unit_object_id
            }
            self._property_mapping[prop_set.pset_id][prop.prop_mk] = prop_info
            LOG.info(
                "Created class property {} for Characteristic {}.{}".format(
                    pros_args["code"], prop_set.pset_id, prop.prop_mk
                )
            )
            self._build_prop_val_excludes(prop_set, prop, catalog_property, new_prop)

    def _build_prop_val_excludes(self, prop_set, prop, catalog_property, new_prop):

            stmt = "SELECT * FROM cdbsml_pval_subset_v where pset_id='{}' and prop_mk='{}' and pval_exclude=1".format(
                prop_set.pset_id, prop.prop_mk
            )
            prop_val_excludes = sqlapi.RecordSet2(sql=stmt)
            for prop_val_exclude in prop_val_excludes:
                try:
                    value_oid = self._prop_catalog_builder.prop_value_mapping[prop.prop_id][prop_val_exclude.pval_value]
                    ins = DBInserter("cs_property_value_exclude")
                    ins.add("classification_class_id", new_prop.classification_class_id)
                    ins.add("class_property_id", new_prop.cdb_object_id)
                    ins.add("property_value_id", value_oid)
                    ins.add("property_id", catalog_property.cdb_object_id)
                    ins.add("exclude", 1)
                    ins.insert()
                    LOG.info(
                        "Deactivated catalog value '{}' for class property {}".format(
                            prop_val_exclude.pval_value, new_prop.code
                        )
                    )
                except Exception: # pylint: disable=W0703
                    LOG.warn(
                        "Property value '{}' of property '{}.{}' cannot be deactivated.".format(
                            prop_val_exclude.pval_value, prop_set.pset_id, prop.prop_mk
                        )
                    )

    def _build_documents(self, new_class, stmt):
        primary_file = None
        for doc_link in sqlapi.RecordSet2(sql=stmt):

            if doc_link.purpose not in IMAGECLASSES['oplan'] and doc_link.purpose not in IMAGECLASSES['mask']:
                args = {
                    'classification_class_id': new_class.cdb_object_id,
                    'z_nummer': doc_link.z_nummer,
                    'z_index': doc_link.z_index,
                    'pos': doc_link.get('position')
                }
                classes.DocumentAssignment.Create(**args)
                LOG.info(
                    "Created document assignment for class {}: {} {}".format(
                        new_class.code, doc_link.z_nummer, doc_link.z_index
                    )
                )
            else:
                doc = Document.ByKeys(doc_link.z_nummer, doc_link.z_index)
                if doc:
                    for sml_file in doc.getPrimaryFiles():
                        if doc_link.purpose in IMAGECLASSES['mask']:
                            args = {
                                'cdbf_object_id': new_class.cdb_object_id,
                                'cdbf_primary': 0
                            }
                            sml_file.Copy(**args)
                            LOG.info(
                                "Created picture for class {}: {}{} - {}".format(
                                    new_class.code, doc.z_nummer, doc.z_index, sml_file.cdbf_name
                                )
                            )

                        if not primary_file and doc_link.purpose in IMAGECLASSES['oplan']:
                            args = {
                                'cdbf_object_id': new_class.cdb_object_id,
                                'cdbf_primary': 1
                            }
                            primary_file = sml_file.Copy(**args)
                            LOG.info(
                                "Created objectplan picture for class {}: {}{} - {}".format(
                                    new_class.code, doc.z_nummer, doc.z_index, primary_file.cdbf_name
                                )
                            )

    def _convert_textrule(self, prop_set):

        def replacer(match):

            text = match.groupdict().get('text')
            if text:
                replacement = '"{}"'.format(text)

            sml_property_code = match.groupdict().get('property')
            if sml_property_code:
                property_mappings = self._property_mapping.get(prop_set.pset_id)
                if not property_mappings:
                    LOG.warning(
                        "Textrule will be ignored! Cannot find property mapping for prop_set id '{}'.".format(
                            prop_set.pset_id
                        )
                    )
                    return ''
                property_mapping = property_mappings.get(sml_property_code)
                if not property_mapping:
                    LOG.warning(
                        "Textrule will be ignored! Cannot find property mapping for prop_set id '{}'.".format(
                            prop_set.pset_id
                        )
                    )
                    return ''
                replacement = property_mapping.get('code', '')

                format_string = match.groupdict().get('format')
                if format_string:
                    # the unit is never displayed in sml!
                    replacement = "{}({})".format(replacement, format_string)

                expression = match.groupdict("prop").get('expr')
                if expression:
                    LOG.warning(
                        "Python expressions used in textrule of prop_set id '{}' are not supported and will be ignored!".format(
                            prop_set.pset_id
                        )
                    )

                is_float_property = False
                modifier = match.groupdict().get('modifier')
                if is_float_property and "asgiven" != modifier:
                    LOG.warning(
                        "Normalized modifier used in textrule of prop_set id '{}' are not supported and will be ignored!".format(
                            prop_set.pset_id
                        )
                    )

            if settings["first_match"]:
                settings["first_match"] = False
            else:
                replacement = ' + {}'.format(replacement)

            return replacement

        settings = {
            "first_match": True
        }

        classification_pattern = re.sub(
            r"(\["
            r"((?P<modifier>\w+)\()?"
            r"(?P<property>\w+)"
            r"\)?"
            r"(!(?P<expr>[^|]+))?"
            r"(\|(?P<format>[^\]]*))?"
            r"\])|"
            r"(?P<text>[^[]+)",
            replacer,
            prop_set.textrule
        )
        return classification_pattern


class ClassificationBuilder(object):

    def __init__(self, class_mapping, property_mapping, unit_helper):
        self._class_mapping = class_mapping
        self._property_mapping = property_mapping
        self._unit_helper = unit_helper

        self._used_prop_sets = set()

    def build(self):
        self._build_object_classifications()
        self._build_object_property_values()

    def _build_object_classifications(self):
        stmt = "SELECT cdb_object_id, sachgruppe FROM teile_stamm WHERE sachgruppe NOT NULL AND sachgruppe != ''"
        classified_parts = sqlapi.RecordSet2(sql=stmt)
        for part in classified_parts:
            class_code = self._class_mapping.get(part.sachgruppe, None)
            if class_code:
                self._used_prop_sets.add(part.sachgruppe)
                ObjectClassification._Create(
                    ref_object_id=part.cdb_object_id,
                    class_code=class_code
                )
                LOG.info(
                    "Created classification for part '{}' and class '{}'".format(
                        part.cdb_object_id, class_code
                    )
                )
            else:
                LOG.error(
                    "Cannot create object classification for '{}'. No corresponding class found!".format(
                        part.sachgruppe
                    )
                )

    def _build_object_property_values(self):

        for prop_set in self._used_prop_sets:
            try:
                if prop_set not in self._property_mapping:
                    LOG.error("Cannot find property mapping for prop_set '{}'".format(prop_set))
                    continue
                sqltable = sml_table(prop_set)
                sml_class = ClassRegistry().find(sqltable, generate=True)
                if not sml_class:
                    LOG.error("Cannot find smlclass '{}'".format(prop_set))
                    continue
                for page in paginated(sml_class.Query(), 1000):
                    for part_property_values in page:
                        self._build_object_property_values_for_part(
                            prop_set, sqltable, part_property_values
                        )
            except Exception as ex: # pylint: disable=W0703
                LOG.exception("Processing sml table '{}': {}".format(sqltable, ex))

    def _build_object_property_values_for_part(self, prop_set, sqltable, part_property_values):
        try:
            stmt = "select cdb_object_id from teile_stamm where teilenummer='{}' and t_index='{}'".format(
                part_property_values.teilenummer,
                part_property_values.t_index
            )
            result = sqlapi.RecordSet2(sql=stmt)
            if not result:
                LOG.error("Cannot find part '{}/{}'".format(
                    part_property_values.teilenummer, part_property_values.t_index)
                )
                return
            cdb_object_id = result[0].cdb_object_id
            for sml_prop_code, prop_info in self._property_mapping.get(prop_set, {}).items():
                try:
                    prop_value = part_property_values[sml_prop_code.lower()]
                    unit_col = "{}_pq".format(sml_prop_code.lower())
                    prop_unit = part_property_values[unit_col] if unit_col in part_property_values else None
                except Exception as ex: # pylint: disable=W0703
                    LOG.exception(
                        "Skipping characterisic '{}' for part '{}/{}': {}".format(
                            sml_prop_code, part_property_values.teilenummer, part_property_values.t_index, ex
                        )
                    )
                    return
                self._build_object_property_value(
                    sml_prop_code,
                    prop_info,
                    cdb_object_id,
                    part_property_values.teilenummer,
                    part_property_values.t_index,
                    prop_value,
                    prop_unit
                )
        except Exception as ex: # pylint: disable=W0703
            LOG.exception(
                "Processing sml table '{}' for part '{}/{}': {}".format(
                    sqltable, part_property_values.teilenummer, part_property_values.t_index, ex
                )
            )

    def _build_object_property_value(self, sml_prop_code, prop_info, part_oid, part_number, part_index, value, unit):
        if value is None or '' == value:
            LOG.debug(
                "Skipping empty value for part '{}/{}' and property '{}'".format(
                    part_number, part_index, sml_prop_code
                )
            )
            return

        prop_type = prop_info["type"]
        args = {
            "id": cdbuuid.create_uuid(),
            "ref_object_id": part_oid,
            "property_code": prop_info["code"],
            "property_path": prop_info["code"],
            "property_type": prop_type,
            "value_pos": 0
        }

        if "boolean" == prop_type:
            args["boolean_value"] = value
        elif "float" == prop_type:
            args["float_value"] = value
            unit_info = self._unit_helper.get_unit_info(prop_info["sml_prop_id"])
            if unit_info:
                if unit:
                    unit_oid = unit_info["unit_mapping"].get(unit, None)
                    if not unit_oid:
                        LOG.error(
                            "No unit found for value '{} {}'. Skipping value for part '{}/{}' and property '{}'.".format(
                                value,
                                unit,
                                part_number,
                                part_index,
                                prop_info["code"]
                            )
                        )
                        return
                    args["unit_object_id"] = unit_oid
                    # sml stores normalized value in database! use sml-value as normalized value and recalculate input value.
                    args["normalized_float_value"] = value
                    args["float_value"] = units.normalize_value(
                        value,
                        unit_info["norm_unit_oid"],
                        args["unit_object_id"],
                        prop_info["code"]
                    )
                else:
                    if unit_info["unit_mapping"]:
                        LOG.warning(
                            "No unit given, using default unit {} for value '{}' of part '{}/{}' and property '{}'.".format(
                                UnitCache.get_unit_info(unit_info["default_unit_oid"])['symbol'],
                                value,
                                part_number,
                                part_index,
                                prop_info["code"]
                            )
                        )
                    args["unit_object_id"] = unit_info["default_unit_oid"]
                    args["normalized_float_value"] = units.normalize_value(
                        value,
                        args["unit_object_id"],
                        unit_info["norm_unit_oid"],
                        prop_info["code"]
                    )
            else:
                if prop_info["unit_object_id"]:
                    LOG.error(
                        "No unit mapping found for '{}' but property '{}' has a unit. Skipping value '{}' for part '{}/{}'.".format(
                            prop_info["sml_prop_id"], prop_info["code"], value, part_number, part_index
                        )
                    )
                    return
                args["normalized_float_value"] = value
        elif "integer" == prop_type:
            args["integer_value"] = value
        elif "text" == prop_type:
            args["text_value"] = value
        else:
            LOG.error(
                "Property type '{}' not supported by SML. Skipping value {} for part '{}/{}'.".format(
                    prop_type, value, part_number, part_index
                )
            )
            return

        value_class = type_map[prop_type]
        value_class._Create(**args)
        LOG.debug(
            "Value '{}' created for for part '{}/{}' and property '{}'".format(
                value, part_number, part_index, prop_info["code"]
            )
        )


class CodeHelper(object):

    def __init__(self):
        self._class_codes = set()
        stmt = "SELECT code FROM cs_classification_class"
        rset = sqlapi.RecordSet2(sql=stmt)
        for r in rset:
            self._class_codes.add(r.code)

        self._prop_codes = set()
        stmt = "SELECT code FROM cs_class_property " \
            "UNION ALL " \
            "SELECT code FROM cs_property"
        rset = sqlapi.RecordSet2(sql=stmt)
        for r in rset:
            self._prop_codes.add(r.code)

    def _get_code(self, all_codes, code):
        valid_code = code if util.check_code(code) else util.create_code(code)
        count = 1
        while valid_code in all_codes:
            valid_code = "{}_{}".format(valid_code, count)
            count += 1
        return valid_code

    def get_class_code(self, code):
        return self._get_code(self._prop_codes, code)

    def get_property_code(self, code):
        return self._get_code(self._prop_codes, code)


class MultiLanguageHelper(object):

    _multilang_cols = None

    # src_rel, src_attr, target_rel, target_attr
    multilanguage_attrs = [
        ("cdbsml_property", "name_", "cs_property", "name_"),
        ("cdbsml_propcat", "name_", "cs_property_folder", "name_"),
        ("cdbsml_propset", "name_", "cs_classification_class", "name_"),
        ("cdbsml_pset_names", "name_", "cs_classification_class", "tags_"),
        ("cdbsml_cgroup", "name_", "cs_classification_class", "name_")
    ]

    @classmethod
    def _init(cls):
        cls._multilang_cols = defaultdict(dict)
        for src_rel, src_attr, target_rel, target_attr in cls.multilanguage_attrs:
            src_cols = i18n.find_columns(src_rel, src_attr)
            target_cols = i18n.find_columns(target_rel, target_attr)
            src_languages = set(src_cols.keys())
            target_languages = set(target_cols.keys())

            # log missing target languages
            for missing_lang in src_languages - target_languages:
                LOG.error(
                    "No target column for multi language attribute {}.{} in target table {}. Data will be ignored!".format(
                        src_rel, src_cols[missing_lang], target_rel
                    )
                )
            valid_langs = src_languages.intersection(target_languages)
            cls._multilang_cols[src_rel][src_attr] = [(src_cols[lang], target_cols[lang]) for lang in valid_langs]

    @classmethod
    def get_multilanguage_attrs(cls, rel, multilang_base_name, rec):
        if cls._multilang_cols is None:
            cls._init()
        result = {}
        if rel in cls._multilang_cols:
            for src_col, target_col in cls._multilang_cols[rel][multilang_base_name]:
                result[target_col] = rec[src_col]
        else:
            raise RuntimeError("MultiLanguageHelper: Invalid relation requested: {}".format(rel))
        return result


class UnitHelper(object):

    PROP_UNITS_KEY = ""

    def __init__(self, data_dir, exit_on_error=True):
        self._err = False

        self._unit_oids_by_symbol = self._load_classification_units()

        self._unit_mapping_file = os.path.join(data_dir, 'unit_mapping.json')
        self._unit_mapping = _load_json_file("unit", self._unit_mapping_file)

        self._dimensionality_by_type = {}
        self._quantity_type_mapping = {}
        self._create_quantity_type_mapping()

        self._property_unit_mapping = {}
        self._create_property_unit_mapping()

        if self._err and exit_on_error:
            _abort(10)

    def _create_quantity_type_mapping(self):
        try:
            self._quantity_type_mapping = {}
            self._dimensionality_by_type = {}
            for quant_type in self._load_quant_types():
                self._dimensionality_by_type[str(quant_type.type)] = quant_type.quantity
                LOG.info(
                    "Processing quantity type {} ({}): '{}'.".format(  # pylint: disable=C0209, W1202
                        quant_type.quantity, quant_type.type, quant_type.valid_vals
                    )
                )
                unit_mapping = {}
                norm_unit = ''
                for valid_val in quant_type.valid_vals[1:-1].split('|'):
                    valid_val = valid_val.strip()
                    if not valid_val:
                        continue
                    unit_mapping[valid_val] = self._get_unit_mapping(quant_type.quantity, valid_val)
                    if not norm_unit:
                        if valid_val == "*":
                            test_val = "1"
                        else:
                            test_val = "1{}".format(valid_val)
                        try:
                            _, _, _, norm_unit_sml = PhysQuantity(quant_type.type, '', '').splitValue(test_val)
                            norm_unit = self._get_unit_mapping(quant_type.quantity, norm_unit_sml)
                        except: # pylint: disable=W0702
                            self._log_err(
                                "Error retrieving norm unit for {} ({}): '{}'.".format(  # pylint: disable=C0209
                                    quant_type.quantity, quant_type.type, test_val
                                )
                            )
                self._quantity_type_mapping[str(quant_type.type)] = {
                    'dimensionality': quant_type.quantity,
                    'norm_unit_oid': norm_unit,
                    'unit_mapping': unit_mapping
                }
        except Exception as exc: # pylint: disable=W0703
            self._log_err("Error creating quantity type mapping: {}".format(exc), exc)
            self._quantity_type_mapping = {}
            self._dimensionality_by_type = {}

    def _create_property_unit_mapping(self):
        try:
            self._property_unit_mapping = {}
            props_with_unit = sqlapi.RecordSet2(
                sql="select prop_id, prop_unit, din4001_mm_me from cdbsml_property "
                    "where (prop_unit is not null and prop_unit != '') or (din4001_mm_me is not null and din4001_mm_me != '')"
            )
            for prop in props_with_unit:
                if prop.din4001_mm_me:
                    quantity_mapping = self._quantity_type_mapping[prop.din4001_mm_me]
                    unit_info = UnitCache.get_unit_info(quantity_mapping['norm_unit_oid'])
                    if unit_info:
                        LOG.info(
                            "'{}' is used as normalization unit for Characteristic '{}'.".format(
                                unit_info.get('symbol', ''), prop.prop_id
                            )
                        )
                    if prop.prop_unit:
                        # use prop_unit as default unit
                        default_unit_oid = self._get_unit_mapping(
                            quantity_mapping['dimensionality'], prop.prop_unit
                        )
                        unit_info = UnitCache.get_unit_info(default_unit_oid)
                        if unit_info:
                            LOG.info(
                                "'{}' (display unit) is used as default unit for Characteristic '{}'.".format(
                                    unit_info.get('symbol', ''), prop.prop_id
                                )
                            )
                    else:
                        # use norm_unit also as default
                        default_unit_oid = quantity_mapping['norm_unit_oid']
                        unit_info = UnitCache.get_unit_info(default_unit_oid)
                        if unit_info:
                            LOG.info(
                                "'{}' (norm unit) is used as default unit for Characteristic '{}'.".format(
                                    unit_info.get('symbol', ''), prop.prop_id
                                )
                            )
                    self._property_unit_mapping[prop.prop_id] = {
                        'default_unit_oid': default_unit_oid,
                        'norm_unit_oid': quantity_mapping['norm_unit_oid'],
                        'unit_mapping': quantity_mapping['unit_mapping'],
                    }
                else:
                    key = u"{}-{}".format(prop.prop_id, prop.prop_unit)  # pylint: disable=C0209, W1406
                    if UnitHelper.PROP_UNITS_KEY not in self._unit_mapping:
                        self._unit_mapping[UnitHelper.PROP_UNITS_KEY] = {}
                    unit_symbol = self._unit_mapping[UnitHelper.PROP_UNITS_KEY].get(key, "")
                    if not unit_symbol:
                        self._log_err("Cannot find unit mapping for property: {}".format(key))
                    else:
                        unit_oid = self._get_unit_oid_by_symbol(unit_symbol)
                        # use default unit also as norm unit
                        LOG.info(
                            "'{}' is used as normalization unit for Characteristic '{}'.".format(
                                UnitCache.get_unit_info(unit_oid)['symbol'], prop.prop_id
                            )
                        )
                        LOG.info(
                            "'{}' is used as default unit for Characteristic '{}'.".format(
                                UnitCache.get_unit_info(unit_oid)['symbol'], prop.prop_id
                            )
                        )
                        self._property_unit_mapping[prop.prop_id] = {
                            'default_unit_oid': unit_oid,
                            'norm_unit_oid': unit_oid,
                            'unit_mapping': {}
                        }
        except Exception as exc: # pylint: disable=W0703
            self._log_err("Error creating property unit mapping: {}".format(exc), exc)
            self._property_unit_mapping = {}

    def _get_unit_mapping(self, dimensionality, sml_unit):
        if dimensionality not in self._unit_mapping:
            self._log_err("Cannot find unit mapping for dimensionality: {}".format(dimensionality))
            return ""
        unit = self._unit_mapping[dimensionality].get(sml_unit, "")
        if not unit:
            self._log_err("Cannot find unit mapping: {}, {}".format(dimensionality, sml_unit))
            return ""
        return self._get_unit_oid_by_symbol(unit)

    def _get_unit_oid_by_symbol(self, symbol):
        unit_oid = self._unit_oids_by_symbol.get(symbol, "")
        if not unit_oid:
            try:
                unit_args = {
                    "symbol": symbol,
                    "dimensionality": Unit.get_pint_dimensionality(symbol)
                }
                for lang in i18n.getActiveGUILanguages():
                    unit_args["name_" + lang] = symbol
                pint_unit = Unit.Create(**unit_args)
                UnitCache.clear()
                self._unit_oids_by_symbol[symbol] = pint_unit.cdb_object_id
                LOG.info("Created unit for symbol {}".format(symbol))
            except Exception as ex: # pylint: disable=W0703
                self._log_err("Cannot create cs.classification unit for symbol {}: {}".format(symbol, ex), ex)
        return unit_oid

    def _load_classification_units(self):
        try:
            unit_oids_by_symbol = {}
            for unit_oid, unit in units.UnitCache.get_all_units_by_id().items():
                unit_oids_by_symbol[unit["symbol"]] = unit_oid
            return unit_oids_by_symbol
        except Exception as exc: # pylint: disable=W0703
            self._log_err("Error loading cs.classification units: {}".format(exc), exc)
            return {}

    def _load_quant_types(self, only_used=True):
        if only_used:
            rset = sqlapi.RecordSet2(sql="select distinct(din4001_mm_me) from cdbsml_property "
                                         "where din4001_mm_me is not null and din4001_mm_me != ''")
            used_phys_quantities = [r.din4001_mm_me for r in rset]
            if used_phys_quantities:
                stmt = "SELECT * FROM phys_quant_types WHERE {}".format(
                    tools.format_in_condition("type", used_phys_quantities)
                )
                return sqlapi.RecordSet2(sql=stmt)
            else:
                return []
        else:
            return sqlapi.RecordSet2("phys_quant_types")

    def _log_err(self, msg, exc=None):
        self._err = True
        if exc:
            LOG.exception(msg)
        else:
            LOG.error(msg)

    def get_unit_info(self, property_id):
        return self._property_unit_mapping.get(property_id, {})

    def save_unit_mapping(self):
        _save_json_file("unit", self._unit_mapping_file, self._unit_mapping)

    def update_unit_mapping(self, overwrite=False, only_used=True):
        if overwrite:
            self._unit_mapping = {}
        dimensionality_by_type = {}
        for quant_type in self._load_quant_types(only_used):
            dimensionality_by_type[str(quant_type.type)] = quant_type.quantity
            dimensionality = quant_type.quantity
            if dimensionality not in self._unit_mapping:
                self._unit_mapping[dimensionality] = {}
            mapping = self._unit_mapping[dimensionality]

            for compatible_unit in quant_type.valid_vals[1:-1].split('|'):
                compatible_unit = compatible_unit.strip()
                if compatible_unit:
                    mapping[compatible_unit] = mapping.get(compatible_unit, '')

        props_with_unit = sqlapi.RecordSet2(
            sql="select prop_id, prop_unit, din4001_mm_me from cdbsml_property "
                "where prop_unit is not null and prop_unit != ''"
        )
        for prop in props_with_unit:
            if prop.din4001_mm_me:
                dimensionality = dimensionality_by_type[prop.din4001_mm_me]
                if prop.prop_unit not in self._unit_mapping[dimensionality]:
                    self._log_err(
                        "Unit {} set in property with id {} does not exist in quantity type {}".format(
                            prop.prop_unit, prop.prop_id, prop.din4001_mm_me
                        )
                    )
            else:
                if UnitHelper.PROP_UNITS_KEY not in self._unit_mapping:
                    self._unit_mapping[UnitHelper.PROP_UNITS_KEY] = {}
                units_mapping = self._unit_mapping[UnitHelper.PROP_UNITS_KEY]
                key = u"{}-{}".format(prop.prop_id, prop.prop_unit) # pylint: disable=C0209, W1406
                if key not in units_mapping:
                    units_mapping[key] = ""


def _abort(exit_code):
    LOG.fatal("Migration aborted!")
    sys.exit(exit_code)


def _load_json_file(json_file_type, json_file):
    try:
        LOG.info("Loading {} mapping: {}".format(json_file_type, json_file))
        with open(json_file) as f:
            return json.load(f)
    except Exception as exc: # pylint: disable=W0703
        LOG.warn("Error loading {} mapping file {}: {}".format(json_file_type, json_file, exc))
        return {}


def _save_json_file(json_file_type, json_file, data):
    try:
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4, separators=(',', ': '), sort_keys=True, ensure_ascii=False)
            f.write('\n')
        LOG.info("{} mapping saved to: {}".format(json_file_type, json_file))  # pylint: disable=C0209, W1202
    except Exception: # pylint: disable=W0703
        LOG.exception("Error saving {} mapping file to {}".format(json_file_type, json_file))


def _setup_logging(log_level, log_file):
    try:
        logFormatter = logging.Formatter("[%(asctime)s] %(levelname)-8.8s [%(name)s] %(message)s")

        LOG.propagate = False
        LOG.setLevel(logging.DEBUG)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        consoleHandler.setLevel(log_level)
        LOG.addHandler(consoleHandler)

        if log_file:
            fileHandler = logging.FileHandler(log_file, 'w')
            fileHandler.setFormatter(logFormatter)
            fileHandler.setLevel(log_level)
            LOG.addHandler(fileHandler)

    except ValueError as ve:
        print("Error setting up logging!")
        print(ve)
        sys.exit(10)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='sml to cs.classification migration tool.')
    parser.add_argument(
        '--dry-run',
        dest='dry_run',
        action='store_true',
        default=False,
        help='No changes are commited. default: False'
    )

    parser.add_argument(
        '--force',
        dest='force_mode',
        action='store_true',
        default=False,
        help='Overwrite existing data.'
    )

    parser.add_argument(
        '--default-language',
        dest='lang',
        default='de',
        help='Default language to store non multilangual sml fields in multilangual classification fields. default: de'
    )
    parser.add_argument(
        '--sml-root-class-code',
        dest='sml_root_code',
        default='SML_ROOT',
        help='Code for the sml root class. default: SML_ROOT'
    )

    parser.add_argument(
        '--log-level',
        dest='log_level',
        default='INFO',
        help='log level. default: INFO.'
    )
    parser.add_argument(
        '--log-file',
        dest='log_file',
        default=None,
        help='optional log file.'
    )

    parser.add_argument(
        '--data-dir',
        dest='data_dir',
        default=os.path.join(os.path.dirname(__file__)),
        help='unit mapping file.'
    )

    parser.add_argument(
        '--update-unit-mapping',
        dest='update_units',
        action='store_true',
        default=False,
        help='create or update the unit mapping.'
    )
    parser.add_argument(
        '--schema-migration',
        dest='schema_migration',
        action='store_true',
        default=False,
        help='executes the schema migration and writes mapping files.'
    )
    parser.add_argument(
        '--data-migration',
        dest='data_migration',
        action='store_true',
        default=False,
        help='executes the sml data migration.'
    )

    args = parser.parse_args()
    _setup_logging(args.log_level, args.log_file)

    class_codes = []
    for i in range(2001):
        class_codes.append(str(i))

    if args.update_units:
        LOG.info("Starting unit mapping update ...")
        unit_helper = UnitHelper(args.data_dir, False)
        unit_helper.update_unit_mapping(args.force_mode)
        unit_helper.save_unit_mapping()
        LOG.info("Unit mapping created. Make sure to add all missing pint unit symbols before you start the migration.")
    elif args.schema_migration or args.data_migration:
        LOG.info("Starting migration ...")
        unit_helper = UnitHelper(args.data_dir)
        SMLMigration().run(
            unit_helper, args.data_dir, args.lang, args.sml_root_code, args.schema_migration, args.data_migration, args.dry_run
        )
        LOG.info("SML migration completed. Remember to recreate the Solr search index!")
