# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module object_classifiaction

This module contains utility functions for object classification. These functions are not part
of the external api!
"""

import datetime
import hashlib
import json
import logging

from collections import defaultdict
from urllib.parse import unquote


from cdb import sqlapi, cdbuuid, typeconversion
from cdb.objects import Object
from cdb.objects.cdb_file import CDB_File
from cs.platform.web.rest import get_collection_app

from cs.classification import ClassificationConstants, ClassificationException
from cs.classification import FloatRangeObjectPropertyValue, ObjectPropertyValue, ObjectClassification
from cs.classification import prepare_read, tools, type_map, util
from cs.classification.applicability import ClassificationReferenceApplicability
from cs.classification.catalog import classname_type_map, Property, PropertyValue
from cs.classification.classes import ClassificationClass
from cs.classification.classes import ClassProperty, DisplayOptions
from cs.classification.classes import ClassPropertyGroup, PropertyGroupAssignment
from cs.classification.classes import ClassPropertyValuesView
from cs.classification.units import UnitCache


LOG = logging.getLogger(__name__)


class ClassesNotApplicableException(ClassificationException, KeyError):

    def __init__(self, class_codes):
        self.details = "\n".join(sorted(class_codes))
        super(ClassesNotApplicableException, self).__init__(
            "cs_classification_classes_not_applicable", "\n" + self.details
        )

    def getDetails(self):
        return self.details


class ClassificationData(object):

    def __init__(
        self, obj, class_codes=None, request=None, narrowed=False, released_only=False,
        check_rights=False, filter_write_access=False
    ):
        # Note: obj may be an object_id, an object or None (e.g. for search)
        if obj is None:
            self.obj = None
            self.object_oid = None
        elif isinstance(obj, str):
            self.obj = None
            self.object_oid = obj
        elif isinstance(obj, Object):
            self.obj = obj
            self.object_oid = obj.cdb_object_id
        else:
            raise TypeError("Expected string or cdb.objects.Object. Got %s" % (type(obj)))

        self.class_codes = class_codes
        self._metadata = None
        self._assigned_class_codes = None
        self._assigned_class_objs = None
        self._class_codes_by_oid = None
        self._class_infos_by_code = None
        self._obi_ref_applicabilities_by_property_oid = None
        self._properties_by_class = None
        self._properties_by_oid = None
        self._prop_codes_by_oid = None
        self._groups_by_class = None
        self._block_details = None
        self._default_values_by_oid = None
        self._files_by_foid = None
        self._request = request
        self._narrowed = narrowed
        self._check_rights = check_rights
        self._filter_write_access = filter_write_access
        self._released_only = released_only
        self._data_checksum = None
        self._child_prop_by_code = None
        self._child_prop_code_by_oid = None
        self._child_prop_oid_by_code = None
        self._key_prop_values = None


    def _all_class_ids(self):
        return self._class_codes_to_ids(self._class_infos_by_code.keys())

    def _assigned_class_ids(self):
        return self._class_codes_to_ids(self._assigned_class_codes)

    def _class_codes_to_ids(self, class_codes):
        class_ids = []
        for class_code in class_codes:
            class_ids.append(self._class_infos_by_code[class_code]["cdb_object_id"])
        return class_ids

    def _get_obj_ref_applicabilities(self, property_id):
        if self._obi_ref_applicabilities_by_property_oid is None:
            self._load_class_properties()
            obj_ref_prop_oids = {
                prop.catalog_property_id for prop in self._properties_by_oid.values() if prop.getType() == "objectref"
            }
            self._obi_ref_applicabilities_by_property_oid = defaultdict(list)
            if obj_ref_prop_oids:
                self._obi_ref_applicabilities_by_property_oid = ClassificationData.load_obj_ref_applicabilities(
                    obj_ref_prop_oids
                )
        return self._obi_ref_applicabilities_by_property_oid.get(property_id, [])

    def _load_block_prop_details(self):
        if self._block_details is None:
            self._block_details = {}
            self._child_prop_code_by_oid = {}
            self._child_prop_oid_by_code = {}
            self._child_prop_by_code = {}
            self._load_class_properties()

            block_props = []
            for props in self._properties_by_class.values():
                block_props += [prop for prop in props if prop.getType() == "block"]

            if block_props:
                ClassificationData._resolve_block_properties(
                    block_props, True, self._block_details, self._child_prop_by_code, self._all_class_ids()
                )

                for code, prop in self._child_prop_by_code.items():
                    self._child_prop_code_by_oid[prop.cdb_object_id] = code
                    self._child_prop_oid_by_code[code] = prop.cdb_object_id

    def _load_block_key_prop_values(self):

        def _resolve_key_prop_codes(props_data):
            key_prop_codes = set()
            for _, prop in props_data.items():
                if "block" == prop["type"]:
                    key_prop_code = prop["key_property_code"]
                    if key_prop_code and 1 == prop["create_block_variants"]:
                        key_prop_codes.add(key_prop_code)
                    key_prop_codes.update(_resolve_key_prop_codes(prop["child_props_data"]))
            return key_prop_codes

        if self._key_prop_values is None:
            self._key_prop_values = {}
            self._load_block_prop_details()

            key_prop_codes = _resolve_key_prop_codes(self._block_details)
            if key_prop_codes:
                key_prop_oids = [self._child_prop_oid_by_code[prop_code] for prop_code in key_prop_codes]
                key_prop_values = defaultdict(list)
                for value_obj in PropertyValue.Query(((PropertyValue.property_object_id.one_of(*key_prop_oids)) & (PropertyValue.is_active == 1))):
                    key_prop_values[self._child_prop_code_by_oid[value_obj["property_object_id"]]].append(value_obj)

                key_props = {}
                for key_prop in Property.Query(Property.cdb_object_id.one_of(*key_prop_oids)):
                    key_props[self._child_prop_code_by_oid[key_prop.cdb_object_id]] = key_prop

                for key, values in key_prop_values.items():
                    self._key_prop_values[key] = PropertyValue.to_json_data(values, self._request, key_props[key])

    def _load_classes(self):

        def find_sublass(class_code):
            for class_info in all_class_infos:
                if class_code == class_info['parent_code']:
                    return True
            return False

        if self._assigned_class_codes is None:
            if self.class_codes is not None:
                self._assigned_class_codes = self.class_codes
            else:
                self._assigned_class_objs = ObjectClassification.KeywordQuery(
                    ref_object_id=self.object_oid
                )
                self._assigned_class_codes = [clazz.class_code for clazz in self._assigned_class_objs]

            self._class_codes_by_oid = {}
            self._class_infos_by_code = {}

            if self._assigned_class_codes:
                all_class_infos = ClassificationClass.get_base_class_infos(
                    class_codes=self._assigned_class_codes,
                    include_given=True,
                    only_released=self._released_only,
                    check_rights=self._check_rights
                )
                for class_info in all_class_infos:
                    code = class_info["code"]
                    oid = class_info["cdb_object_id"]

                    self._class_codes_by_oid[oid] = code
                    self._class_infos_by_code[code] = class_info

                # filter assigned classes according access rights
                assigned_class_codes = []
                for assigned_class_code in self._assigned_class_codes:
                    if assigned_class_code in self._class_infos_by_code:
                        if not self._assigned_class_objs and find_sublass(assigned_class_code):
                            # add only most specialized class assignment
                            continue
                        assigned_class_codes.append(assigned_class_code)

                if self._filter_write_access:
                    if self.object_oid and not self.obj:
                        from cdb.objects import ByID
                        self.obj = ByID(self.object_oid)
                    if self.obj:
                        access_infos = ClassificationData.get_access_info(
                            assigned_class_codes, dd_classname=self.obj.GetClassname(), for_create=True,
                        )
                        self._assigned_class_codes = []
                        for assigned_class_code in assigned_class_codes:
                            if access_infos.get(assigned_class_code, True):
                                self._assigned_class_codes.append(assigned_class_code)
                else:
                    self._assigned_class_codes = assigned_class_codes
                if self._assigned_class_objs:
                    assigned_class_objs = []
                    for assigned_class_obj in self._assigned_class_objs:
                        if assigned_class_obj.class_code in self._class_infos_by_code:
                            assigned_class_objs.append(assigned_class_obj)
                    self._assigned_class_objs = assigned_class_objs

    def _load_defaults(self):
        if self._default_values_by_oid is None:
            # collect default oids
            default_value_oids = set()
            metadata = self.get_classification_metadata()
            for _, class_details in metadata["classes"].items():
                default_value_oids.update(ClassificationData.find_default_values(class_details["properties"]))

            self._default_values_by_oid = ClassificationData.load_default_values(default_value_oids)

    def _load_files(self):
        if self._files_by_foid is None:
            self._files_by_foid = defaultdict(list)
            if self._request:
                self._load_classes()
                file_objs = CDB_File.Query(
                    ((CDB_File.cdbf_object_id.one_of(*self._all_class_ids())) & (CDB_File.cdbf_primary == 0)),
                    order_by=["cdbf_object_id", "cdbf_name"]
                )
                collection_app = get_collection_app(self._request)
                for f in file_objs:
                    url = unquote(self._request.link(f, app=collection_app))
                    self._files_by_foid[f.cdbf_object_id].append({"url": url,
                                                                  "alt": f.cdbf_name,
                                                                  "content_type": f.content_type})

    def _load_groups(self):
        if self._groups_by_class is None:
            self._groups_by_class = defaultdict(list)
            self._load_classes()
            self._load_class_properties()

            groups = ClassPropertyGroup.Query(
                ClassPropertyGroup.classification_class_id.one_of(*self._all_class_ids()),
                order_by=['classification_class_id', 'position']
            )
            props_by_group_id = defaultdict(list)
            if groups:
                grp_assignments = PropertyGroupAssignment.Query(
                    PropertyGroupAssignment.group_object_id.one_of(*groups.cdb_object_id),
                    order_by=['group_object_id', 'position']
                )
                for asgn in grp_assignments:
                    prop = self._properties_by_oid.get(asgn.property_object_id)
                    if prop:
                        grp_data = {"prop_code": prop.code,
                                    "class_code": self._class_codes_by_oid.get(prop.classification_class_id),
                                    "display_option": DisplayOptions.by_label(asgn.display_option).id}
                        props_by_group_id[asgn.group_object_id].append(grp_data)

            for group in groups:
                data = {
                    'cdb_object_id': group.cdb_object_id,
                    'name': tools.get_label('name', group._record),
                    'initial_expanded': 1 == group.initial_expand,
                    'properties': props_by_group_id.get(group.cdb_object_id, [])
                }
                self._groups_by_class[self._class_codes_by_oid.get(group.classification_class_id)].append(data)

    def _load_class_properties(self):
        if self._properties_by_class is None:
            self._load_classes()
            self._properties_by_class = defaultdict(list)
            self._prop_codes_by_oid = {}
            self._properties_by_oid = {}
            all_class_ids = self._all_class_ids()
            for prop in ClassProperty.Query(
                ClassProperty.classification_class_id.one_of(*all_class_ids),
                order_by=["classification_class_id", "position"]
            ):
                if not self._released_only or prop.isActive():
                    self._properties_by_class[self._class_codes_by_oid.get(prop.classification_class_id)].append(prop)
                    self._prop_codes_by_oid[prop.cdb_object_id] = prop.code
                    self._properties_by_oid[prop.cdb_object_id] = prop

    def _resolve_parent_classes(self, class_code):
        self._load_classes()
        return self._class_infos_by_code[class_code]["parent_class_codes"]

    def get_assigned_classes(self, include_bases=False, as_object_ids=False):
        self._load_classes()
        if as_object_ids:
            if include_bases:
                return self._all_class_ids()
            else:
                return self._assigned_class_ids()
        else:
            if include_bases:
                return self._class_infos_by_code.keys()
            else:
                return self._assigned_class_codes

    def get_assigned_classes_objs(self):
        self._load_classes()
        return self._assigned_class_objs

    def filter_values(self, property_codes, values):
        for prop_code in property_codes:
            del values[prop_code]

    def get_classification(self):
        values = self.get_classification_data()
        self.pad_values(values, active_props_only=True)

        metadata = dict(self.get_classification_metadata())
        addtl_properties = ClassificationData.get_catalog_property_metadata(
            list(values), check_rights=self._check_rights
        )
        metadata["addtl_properties"] = addtl_properties

        if self._check_rights:
            property_codes = set(values.keys()) - set(
                list(self._prop_codes_by_oid.values()) + list(addtl_properties.keys())
            )
            self.filter_values(property_codes, values)

        self.remove_inactive_props(values, metadata)

        enum_values_by_prop_code = util.get_enum_values_with_labels(util.get_text_prop_codes(values))
        if len(enum_values_by_prop_code):
            util.add_enum_labels(values, enum_values_by_prop_code)
            util.create_all_block_descriptions(values)

        return values, metadata, self.get_classification_data_checksum()

    def get_classification_data_checksum(self, reload=False):
        if self._data_checksum is None or reload:
            value_objects = ObjectPropertyValue.KeywordQuery(ref_object_id=self.object_oid)
            # FIXME: filter value objects by read rights of parent classes and catalog properties
            self._data_checksum = ClassificationData.calc_checksum(value_objects)
        return self._data_checksum

    @classmethod
    def load_obj_ref_applicabilities(cls, catalog_prop_ids):
        result = defaultdict(list)
        applicabilities = ClassificationReferenceApplicability.KeywordQuery(property_id=catalog_prop_ids)
        for applicability in applicabilities:
            result[applicability.property_id].append(applicability.dd_classname)
        return result

    @classmethod
    def _resolve_block_properties(cls, block_props, is_class_prop, result_dict, child_prop_by_code, class_ids=None):

        def _resolve_block_properties_intern(block_codes, is_class_prop, result_dict, child_prop_by_code):
            block_prop_rel = "cs_class_property" if is_class_prop else "cs_property"
            block_code = "a.catalog_property_code" if is_class_prop else "a.code"

            in_classes = ""
            if is_class_prop and class_ids:
                in_classes = "AND " + tools.format_in_condition("a.classification_class_id", class_ids)

            stmt = ("SELECT a.code block_code, c.*, b.display_option, b.is_editable, b.is_mandatory, 1 as is_visible, "
                    "b.default_unit_object_id, b.is_unit_changeable is_block_unit_changeable, b.position prop_ass_pos FROM %s a, "
                    "cs_block_prop_assign b, cs_property c where %s = b.block_property_code "
                    "AND b.assigned_property_code = c.code AND %s %s"
                    "ORDER BY a.code, b.position" %
                    (block_prop_rel, block_code, tools.format_in_condition("a.code", block_codes), in_classes))
            rset = sqlapi.RecordSet2(sql=stmt)
            object_ref_props_oids = []
            for r in rset:
                prop_type = classname_type_map[r.cdb_classname]
                if prop_type == "objectref":
                    object_ref_props_oids.append(r.cdb_object_id)
            obi_ref_applicabilities_by_property_oid = ClassificationData.load_obj_ref_applicabilities(object_ref_props_oids)
            for r in rset:
                prop_type = classname_type_map[r.cdb_classname]
                if prop_type == "block":
                    data = result_dict.get(r.code)
                    if not data:
                        data = ClassificationData._get_property_data(r, prop_type)
                        data['child_props'] = []
                        data['child_props_data'] = {}
                        result_dict[r.code] = data
                else:
                    data = ClassificationData._get_property_data(r, prop_type)
                    child_prop_by_code[r.code] = r
                    if prop_type == "objectref":
                        data["applicable_classes"] = obi_ref_applicabilities_by_property_oid.get(r.cdb_object_id, [])
                block_data = result_dict[r.block_code]
                if r.code not in block_data["child_props"]:
                    block_data["child_props"].append(r.code)
                    block_data["child_props_data"][r.code] = data

            blocks_to_resolve = [r.code for r in rset if r.cdb_classname == 'cs_block_property']
            if blocks_to_resolve:
                _resolve_block_properties_intern(blocks_to_resolve, False, result_dict, child_prop_by_code)

        for block_prop in block_props:
            raw_data = dict(block_prop._record.items())
            if not is_class_prop:
                raw_data['is_editable'] = 1
                raw_data['is_mandatory'] = 0
                raw_data['is_visible'] = 1
                raw_data['display_option'] = DisplayOptions.NewLine.id

            data = ClassificationData._get_property_data(raw_data, block_prop.getType())
            data['child_props'] = []
            data['child_props_data'] = {}
            result_dict[block_prop.code] = data

        block_codes = [prop.code for prop in block_props]
        if block_codes:
            _resolve_block_properties_intern(block_codes, is_class_prop, result_dict, child_prop_by_code)
        # nested blocks are deeply assigned to parents by child_props_data now
        # keep root blocks in top level dict only
        for k in list(result_dict):
            if k not in block_codes:
                del result_dict[k]


    def get_new_classification_with_complete_metadata(
        self, new_class, with_defaults, active_props_only, create_all_blocks
    ):
        values = {}
        metadata = dict(self.get_classification_metadata())

        for class_code in [new_class] + self._resolve_parent_classes(new_class):
            class_details = metadata["classes"][class_code]
            self.pad_values(values,
                            class_details["properties"],
                            with_defaults=with_defaults,
                            active_props_only=active_props_only,
                            create_all_blocks=create_all_blocks)

        if active_props_only:
            self.remove_inactive_props(values, metadata)
        return values, metadata

    def get_new_classification(
            self, curr_assigned_classes, with_defaults=True, active_props_only=True, create_all_blocks=True
    ):
        """
        Returns an empty value and metadata structure.
        This method is for API purposes to get empty data and structure
        of newly assigned classes.

        :param curr_assigned_classes: The volatile client state of assigned classes. If specified,
                                      the `assigned_classes` list is recalculated
                                      based on this volatile overall classification. Classes may be
                                      added or removed in the volatile client state.
                                      Data and metadata of already assigned base classes is filtered
                                      out.
        """
        values = {}
        metadata = dict(self.get_classification_metadata())

        not_existing_classes = set(self.class_codes) - set(metadata["assigned_classes"])
        if not_existing_classes:
            raise ClassesNotApplicableException(not_existing_classes)

        if curr_assigned_classes:
            # build set with resolved parent classes for classes in curr_assigned_classes
            all_curr_classes = set(
                ClassificationClass.get_base_class_codes(
                    class_codes=curr_assigned_classes, include_given=True
                )
            )
            # Update assigned classes list: Add new class(es) and remove it's bases
            assigned_classes = set(curr_assigned_classes)
            for code in self._assigned_class_codes:
                if code not in all_curr_classes:
                    assigned_classes.add(code)
            bases_of_new_classes = set(self._class_infos_by_code.keys()) - set(self._assigned_class_codes)
            for base_cls in bases_of_new_classes:
                if base_cls in assigned_classes:
                    assigned_classes.remove(base_cls)
            metadata["assigned_classes"] = list(assigned_classes)

            # Remove class metadata of previously assigned classes (curr_assigned_classes and bases)
            for code in all_curr_classes:
                if code in metadata["classes"]:
                    del metadata["classes"][code]
            for _, class_details in metadata["classes"].items():
                self.pad_values(values,
                                class_details["properties"],
                                with_defaults=with_defaults,
                                active_props_only=active_props_only,
                                create_all_blocks=create_all_blocks)
        else:
            self.pad_values(values,
                            with_defaults=with_defaults,
                            active_props_only=active_props_only,
                            create_all_blocks=create_all_blocks)

        if active_props_only:
            self.remove_inactive_props(values, metadata)
        return values, metadata

    def create_missing_block_values(self, property_code, property_values):
        """
        Returns a list of property values that contains block values for not existing enum values of the
        key property.

        :param property_code: The property code of the block to create values for.
        :param property_values: The existing property values.

        """

        def contains_value(compare_value):
            for property_value in property_values:
                if util.are_property_values_equal(
                    property_value["value"]["child_props"][key_property_code][0]["property_type"],
                    property_value["value"]["child_props"][key_property_code][0]["value"],
                    compare_value
                ):
                    return True
            return False

        if not property_values:
            return []

        self._load_block_prop_details()
        last_value_path = property_values[-1]['value_path']

        _, prop_data = self.get_new_value(last_value_path)
        prop_details = prop_data[property_code]

        key_property_code = prop_details["key_property_code"]
        if not key_property_code:
            return []

        key_prop_values = self._key_prop_values.get(key_property_code, None)
        new_block_values = []
        if key_prop_values:
            for _, key_value in enumerate(key_prop_values):
                if not contains_value(key_value["value"]):
                    new_values, _ = self.get_new_value(last_value_path)
                    new_value = new_values[property_code][0]
                    new_value["value"]["child_props"][key_property_code][0]["value"] = key_value["value"]
                    util.create_block_descriptions(property_code, new_value)
                    new_block_values.append(new_value)
                    last_value_path = new_value['value_path']
        return new_block_values

    def get_new_value(self, prop_path, create_all_blocks=True):
        """
        Returns an empty value and metadata structure for the given property.
        This method is for client purposes to get empty data and structure
        for new values of multi value properties.

        :param prop_path: The fully qualified value path of the highest existing multi value.
                          Samples:

                          `TEMPERATURE:001`:
                          Creates a new multi value with value path `TEMPERATURE:002`. If it is a
                          block property, the new block value is deeply constructed with this new path.

                          `GEOMETRY/POSITION/REMARK:000`:
                          Creates a new multi value for the `REMARK` property with
                          value path `GEOMETRY/POSITION/REMARK:001` to be placed inside
                          the block `GEOMETRY/POSITION/`.
        """

        def resolve(path, prop_details):
            if len(path) > 1 and prop_details["type"] == "block":
                path = path[1:]
                prop_details = prop_details["child_props_data"].get(path[0])
                return resolve(path, prop_details)
            else:
                return prop_details

        self._load_class_properties()
        self._load_block_prop_details()

        path_elems = prop_path.split("/")

        # get new multi value position from leaf path element
        if ":" in path_elems[-1]:
            pos = path_elems[-1].split(":")[1]
            pos = "%s" % (int(pos) + 1)
            pos = pos.zfill(3)
        else:
            pos = "001"

        # build multi value position neutralized path
        pure_path = [elem.split(":")[0] if ":" in elem else elem for elem in path_elems]
        root_prop_code = pure_path[0]
        leaf_prop_code = pure_path[-1]

        parent_path = None
        if len(path_elems) > 1:
            parent_path = "/".join(path_elems[:-1])

        if self.class_codes:
            # find root prop and resolve rest of pure_path
            for _, props in self._properties_by_class.items():
                for prop in props:
                    if prop.code == root_prop_code:
                        prop_details = self.get_property_data(prop)
                        prop_details = resolve(pure_path, prop_details)
                        prop_data = {leaf_prop_code: prop_details}
                        values = {}
                        self.pad_values(values, prop_data, parent_path, pos, active_props_only=False,
                                        with_defaults_in_blocks=True, create_all_blocks=create_all_blocks)
                        return values, prop_data
        else:
            prop_data = ClassificationData.get_catalog_property_metadata(
                [leaf_prop_code], check_rights=self._check_rights
            )
            values = {}
            self.pad_values(values, prop_data, parent_path, pos, active_props_only=False,
                            with_defaults_in_blocks=True, create_all_blocks=create_all_blocks)
            return values, prop_data
        return {}, {}

    def pad_values(self, values, props_dict=None, parent_property_path=None,
                   multivalue_pos=None, with_defaults=False, with_defaults_in_blocks=False,
                   active_props_only=False,
                   create_all_blocks=True):

        self._load_defaults()
        self._load_block_key_prop_values()

        if props_dict:
            ClassificationData.pad_values_intern(
                props_dict,
                values,
                parent_property_path,
                multivalue_pos,
                with_defaults,
                with_defaults_in_blocks,
                active_props_only,
                create_all_blocks,
                self._narrowed,
                self._default_values_by_oid,
                self._key_prop_values,
                request=self._request)

        else:
            metadata = self.get_classification_metadata()
            for _, class_details in metadata["classes"].items():
                ClassificationData.pad_values_intern(
                    class_details["properties"],
                    values,
                    None,
                    None,
                    with_defaults,
                    with_defaults_in_blocks,
                    active_props_only,
                    create_all_blocks,
                    self._narrowed,
                    self._default_values_by_oid,
                    self._key_prop_values,
                    request=self._request)

    @classmethod
    def pad_values_intern(
        cls,
        props_dict,
        values_dict,
        parent_property_path,
        position,
        with_defaults,
        with_defaults_in_blocks,
        active_props_only,
        create_all_blocks,
        narrowed,
        default_values_by_oid,
        key_prop_values,
        request=None):

        def get_block_data(block_prop_code, block_prop_details, property_path):
            child_props = {}
            for child_prop_code, child_prop_details in block_prop_details["child_props_data"].items():
                child_props[child_prop_code] = get_empty_data(child_prop_code,
                                                              child_prop_details,
                                                              property_path)
            result = {"child_props": child_props,
                      "description": ""}
            return result

        def get_empty_value(prop_code, prop_details, property_path):
            prop_type = prop_details["type"]
            default_value_oid = None
            if prop_type == "block":
                value = get_block_data(prop_code, prop_details, property_path)
            else:
                value = None
                if with_defaults and "default_value_oid" in prop_details and default_values_by_oid:
                    default_value_obj = default_values_by_oid.get(prop_details["default_value_oid"])
                    if default_value_obj:
                        if prop_type == "multilang" and with_defaults:
                            value_cls = type_map[prop_type]
                            value = value_cls.get_empty_value()
                            for lang, multilang_value in value.items():
                                value[lang]["text_value"] = default_value_obj["multilang_value_" + lang]
                        else:
                            value = default_value_obj.value
                        default_value_oid = default_value_obj.cdb_object_id

                if not default_value_oid:
                    value_cls = type_map[prop_type]
                    value = value_cls.get_empty_value()
                    if prop_type == "float":
                        unit_object_id = prop_details["default_unit_object_id"]
                        value["unit_object_id"] = unit_object_id
                    if prop_type == "float_range":
                        unit_object_id = prop_details["default_unit_object_id"]
                        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                            value[range_identifier]["unit_object_id"] = unit_object_id

                if prop_type == "boolean" and with_defaults:
                    if prop_details["default_value"] == 1:
                        value = True
                    elif prop_details["default_value"] == 0:
                        value = False
                    else:
                        value = None
                elif prop_type == "float":
                    if not narrowed:
                        if value["unit_object_id"]:
                            # add unit label for float
                            unit_label = UnitCache.get_unit_label(value["unit_object_id"])
                            value["unit_label"] = unit_label
                    elif "float_value_normalized" in value:
                        del value["float_value_normalized"]
                elif prop_type == "float_range":
                    if not narrowed:
                        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                            if value[range_identifier]["unit_object_id"]:
                                # add unit label for float
                                unit_label = UnitCache.get_unit_label(
                                    value[range_identifier]["unit_object_id"]
                                )
                                value[range_identifier]["unit_label"] = unit_label
                    elif "float_value_normalized" in value:
                        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                            del value[range_identifier]["float_value_normalized"]

            return value, default_value_oid

        def get_empty_data(prop_code, prop_details, parent_property_path, position=None):

            if create_all_blocks and key_prop_values and position is None\
                    and 'block' == prop_details["type"] and 1 == prop_details["create_block_variants"]:
                block_key_property_code = prop_details["key_property_code"]
                block_key_prop_values = key_prop_values.get(block_key_property_code, None)
                if block_key_prop_values:
                    # create all block variants
                    data = []
                    for pos, key_value in enumerate(block_key_prop_values):
                        empty_value = get_empty_data(prop_code, prop_details, parent_property_path, pos)[0]
                        value_object = empty_value["value"]["child_props"][block_key_property_code][0]
                        value_object["value"] = key_value["value"]
                        if "objectref" == value_object["property_type"] and request and not narrowed:
                            value_object["addtl_value"] = tools.get_addtl_objref_value(value_object["value"], request)
                        util.create_block_descriptions(prop_code, empty_value)
                        data.append(empty_value)
                    return data

            if not parent_property_path:
                property_path = prop_code
            else:
                property_path = "%s/%s" % (parent_property_path, prop_code)
            if position:
                property_path += ":%s" % position

            value, _ = get_empty_value(prop_code, prop_details, property_path)
            data = {
                "property_type": prop_details["type"],
                "id": None,
                "value": value
            }

            if "objectref" == prop_details["type"] and request and not narrowed:
                data["addtl_value"] = tools.get_addtl_objref_value(value, request)

            if not narrowed:
                data["value_path"] = property_path
            return [data]

        for prop_code, prop_details in props_dict.items():
            prop_type = prop_details["type"]
            if prop_code not in values_dict:
                prop_is_active = prop_details["flags"][7] if not parent_property_path else True
                if (active_props_only and prop_is_active) or not active_props_only:
                    with_defaults_arg = with_defaults
                    if prop_type == 'block' and with_defaults_in_blocks:
                        with_defaults = True
                    values_dict[prop_code] = get_empty_data(prop_code,
                                                             prop_details,
                                                             parent_property_path,
                                                             position)
                    with_defaults = with_defaults_arg
            elif prop_type == 'block':
                # for blocks check detail props (each single multi value, if exists)
                if with_defaults_in_blocks:
                    with_defaults = True
                for value_entry in values_dict[prop_code]:
                    ClassificationData.pad_values_intern(prop_details["child_props_data"],
                                                         value_entry["value"]["child_props"],
                                                         value_entry.get("value_path"),
                                                         None, with_defaults, with_defaults_in_blocks,
                                                         active_props_only, create_all_blocks, narrowed,
                                                         default_values_by_oid,
                                                         key_prop_values)
            elif prop_type == 'float_range':
                # pad values for missing range identifiers
                for prop_value in values_dict[prop_code]:
                    pad_range_value = False
                    for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                        if range_identifier not in prop_value["value"]:
                            pad_range_value = True
                            break
                    if pad_range_value:
                        empty_value = get_empty_data(
                            prop_code, prop_details, parent_property_path, position
                        )
                        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                            if range_identifier not in prop_value["value"]:
                                prop_value["value"][range_identifier] = empty_value[0]["value"][range_identifier]

    def remove_inactive_props(self, values, metadata):
        """
        Removes inactive properties from metadata that don't
        have a value in values.
        """

        def _remove_prop_from_groups(class_details, prop_code):
            for grp in class_details.get("property_groups", []):
                for prop_detail in grp["properties"]:
                    if prop_detail["prop_code"] == prop_code:
                        grp["properties"].remove(prop_detail)

        def _filter_props(class_details, values_dict):
            props_dict = class_details["properties"]
            for prop_code, prop_details in list(props_dict.items()):
                if prop_code not in values_dict:
                    prop_is_active = prop_details["flags"][7]
                    if not prop_is_active:
                        del props_dict[prop_code]
                        _remove_prop_from_groups(class_details, prop_code)

        for _, class_details in metadata["classes"].items():
            _filter_props(class_details, values)

    @classmethod
    def remove_properties(cls, class_codes, values, with_metadata, check_rights=False):
        """
        Removes all property values that do not belong to the given class codes
        """

        # get catalog property codes to prevent them from being deleted
        catalog_prop_codes = set()
        if values:
            stmt = "select code from cs_property where {}".format(
                tools.format_in_condition("code", values.keys())
            )
            rset = sqlapi.RecordSet2(sql=stmt)
            for r in rset:
                catalog_prop_codes.add(r.code)

        # remove class props that don't belong to any of the given classes in class_codes
        classification_data = ClassificationData(
            None, class_codes, narrowed=not with_metadata, check_rights=check_rights
        )
        if with_metadata:
            metadata = classification_data.get_classification_metadata()
        else:
            metadata = None
        valid_props = classification_data.get_properties(include_bases=True)
        for prop_code in list(values):
            if prop_code not in valid_props and prop_code not in catalog_prop_codes:
                del values[prop_code]
        return metadata

    @classmethod
    def find_default_values(cls, props_dict):
        default_value_oids = set()
        for _, prop_details in props_dict.items():
            if prop_details["type"] == "block":
                default_value_oids.update(ClassificationData.find_default_values(prop_details["child_props_data"]))
            else:
                if "default_value_oid" in prop_details and prop_details["default_value_oid"]:
                    default_value_oids.add(prop_details["default_value_oid"])
        return default_value_oids

    @classmethod
    def load_default_values(cls, default_value_oids):
        # select all at once
        default_values_by_oid = {}
        if default_value_oids:
            default_value_objs = PropertyValue.Query(PropertyValue.cdb_object_id.one_of(*default_value_oids))
            for val_obj in default_value_objs:
                default_values_by_oid[val_obj.cdb_object_id] = val_obj
        return default_values_by_oid

    def _get_default_value_obj(self, oid):
        self._load_defaults()
        return self._default_values_by_oid.get(oid)

    @classmethod
    def get_access_info(
            cls, class_codes, obj=None, dd_classname=None, for_create=False, add_base_classes=False,
            object_classifications=None
    ):
        if not obj and not for_create:
            raise ValueError("obj must be given if for_create is False")
        if not obj and not dd_classname:
            raise ValueError("dd_classname must be given if obj is None")
        if not dd_classname:
            dd_classname = obj.GetClassname()

        access_by_class_code = {}
        if class_codes:
            access_infos = ClassificationClass.get_access_rights(
                dd_classname=dd_classname, class_codes=class_codes
            )
            for class_code in class_codes:
                access = True
                if access_infos[class_code]["access_rights"]:
                    write_access_obj, write_access_obj_classification, olc = access_infos[class_code]["access_rights"]
                else:
                    raise RuntimeError(
                        "Access rights requested for invalid combination of classification class "
                        "and data dictionary class: %s: %s" % (class_code, dd_classname)
                    )
                if obj and write_access_obj and not obj.CheckAccess(write_access_obj):
                    access = False
                elif write_access_obj_classification:
                    if for_create:
                        obj_classification = ObjectClassification(
                            ref_object_id=cdbuuid.create_uuid(),
                            class_code=class_code,
                            cdb_objektart=olc,
                            status=0
                        )
                    else:
                        obj_classification = None
                        if object_classifications:
                            for oc in object_classifications:
                                if obj.cdb_object_id == oc.ref_object_id and class_code == oc.class_code:
                                    obj_classification = oc
                                    break
                        else:
                            obj_classification = ObjectClassification.ByKeys(
                                ref_object_id=obj.cdb_object_id,
                                class_code=class_code
                            )
                    if obj_classification and obj_classification.cdb_objektart:
                        access = obj_classification.CheckAccess(write_access_obj_classification)
                access_by_class_code[class_code] = access

        if add_base_classes:
            for class_code, has_write_access in list(access_by_class_code.items()):
                access_info = access_infos[class_code]
                parent_class_code = access_info["parent_class_code"]
                while parent_class_code:
                    if parent_class_code not in access_infos:
                        break
                    parent_class_access_info = access_infos[parent_class_code]
                    if has_write_access and access_by_class_code.get(parent_class_code) is False:
                        # if a base class is reached by multiple assigned classes all
                        # subclasses must grant write access, else the base class is ready only
                        break
                    access_by_class_code[parent_class_code] = has_write_access
                    parent_class_code = parent_class_access_info["parent_class_code"]

        return access_by_class_code

    def get_class_codes(self):
        self._load_classes()
        return self._class_infos_by_code.keys()

    def get_class_metadata(self, code):
        self._load_classes()
        class_info = self._class_infos_by_code.get(code)
        if not class_info:
            return None
        data = {'class': class_info,
                'properties': self.get_property_data_for_class(code)}
        if not self._narrowed:
            data['property_groups'] = [self.get_toplevel_group(code)] + self.get_property_groups_for_class(code)
            data['files'] = self.get_class_files(code)
        result = {code: data}
        parent_code = class_info["parent_code"]
        if parent_code:
            parent_class_info = self.get_class_metadata(parent_code)
            if parent_class_info:
                result.update(parent_class_info)
            else:
                class_info["parent_code"] = None
        return result

    def get_class_files(self, code):
        self._load_files()
        return self._files_by_foid.get(self._class_infos_by_code[code]["cdb_object_id"], [])

    def get_toplevel_group(self, class_code):
        """
        Returns a special group named 'TOPLEVEL_GROUP',
        which contains all properties that are not assigned explicitly to any group.
        """
        props = self.get_props_without_group(class_code)
        properties_data = []
        for prop in props:
            prop_data = {"prop_code": prop.code,
                         "class_code":  self._class_codes_by_oid.get(prop.classification_class_id),
                         "display_option": DisplayOptions.by_label(prop.display_option).id}
            properties_data.append(prop_data)
        data = {
            'initial_expanded': True,
            'name': "TOPLEVEL_GROUP",
            'properties': properties_data
        }
        return data

    def get_props_without_group(self, class_code):
        self._load_class_properties()
        self._load_groups()
        result = []
        props = self._properties_by_class.get(class_code, [])
        if props:
            assigned_prop_codes = set()
            groups = self._groups_by_class.get(class_code, [])
            for group in groups:
                for prop_detail in group["properties"]:
                    assigned_prop_codes.add(prop_detail["prop_code"])
            all_prop_codes = set([prop.code for prop in props])
            unassigned_props = all_prop_codes - assigned_prop_codes
            result = [p for p in props if p.code in unassigned_props]
        return result

    def get_property_groups_for_class(self, code):
        self._load_groups()
        return self._groups_by_class.get(code, [])

    @classmethod
    def get_property_flags(cls, prop_rec):
        flags = ['is_editable', 'is_mandatory', 'is_visible', 'is_multivalued', 'is_enum_only', 'has_enum_values']
        flags = [prop_rec[flag] if prop_rec[flag] else 0 for flag in flags]
        flags.append(DisplayOptions.by_label(prop_rec["display_option"]).id)
        flags.append(1 if 200 == prop_rec['status'] else 0)
        is_unit_changeable = 1 if prop_rec.get('is_block_unit_changeable', prop_rec.get('is_unit_changeable')) else 0
        flags.append(is_unit_changeable)
        for_variants = 1 if prop_rec.get('for_variants', 0) else 0
        flags.append(for_variants)
        is_url = 1 if prop_rec.get('is_url', 0) else 0
        flags.append(is_url)
        return flags

    @classmethod
    def _get_property_data(cls, prop_rec, prop_type):
        result = {}
        result['flags'] = cls.get_property_flags(prop_rec)
        result['code'] = prop_rec['code']
        result['catalog_code'] = prop_rec.get('catalog_property_code', prop_rec['code'])
        result['external_code'] = prop_rec['external_code']
        result['external_system'] = prop_rec['external_system']
        result['name'] = tools.get_label('name', prop_rec)
        result['description'] = tools.get_label('prop_description', prop_rec)
        result['position'] = prop_rec.get('position', 0)
        result['type'] = prop_type
        result['catalog'] = prop_rec['katalog']
        if prop_rec['default_value_oid']:
            result['default_value_oid'] = prop_rec['default_value_oid']
        if prop_type == 'block':
            result["create_block_variants"] = prop_rec["create_block_variants"] if prop_rec["create_block_variants"] else 0
            result["key_property_code"] = prop_rec["key_property_code"] if prop_rec["key_property_code"] else u""
            result["initial_expanded"] = 1 == prop_rec.get('initial_expand', 0)
        elif prop_type == 'boolean':
            result["bool_label"] = tools.get_label('label', prop_rec)
            result["default_value"] = prop_rec['default_value']
        elif prop_type == 'datetime':
            result["with_timestamp"] = prop_rec['with_timestamp']
        elif prop_type in ['float', 'float_range']:
            result["float_format"] = [prop_rec['no_integer_positions'], prop_rec['no_decimal_positions']]
            result["default_unit_object_id"] = prop_rec.get('default_unit_object_id')
            result["base_unit_object_id"] = prop_rec.get('unit_object_id')
            result["base_unit_symbol"] = UnitCache.get_unit_label(prop_rec.get('unit_object_id'))
            if not result["default_unit_object_id"]:
                # fallback to base unit if no default unit is set
                result["default_unit_object_id"] = prop_rec.get('unit_object_id')
            result["default_unit_symbol"] = UnitCache.get_unit_label(result["default_unit_object_id"])
        elif prop_type in ['text', 'multilang']:
            result["multiline"] = prop_rec["multiline"] if prop_rec["multiline"] else 1
            data_length = prop_rec.get("data_length")
            result['pattern'] = prop_rec.get('pattern')
            result['regex'] = prop_rec.get('regex')
            if not data_length or data_length > 4000:
                result["data_length"] = 4000
            else:
                result["data_length"] = data_length
        return result

    def get_property_data(self, prop_obj):
        self._load_class_properties()
        self._load_block_prop_details()
        prop_type = prop_obj.getType()
        if prop_type == 'block':
            data = self._block_details.get(prop_obj.code)
        else:
            data = ClassificationData._get_property_data(prop_obj._record, prop_type)
            if prop_type == "objectref":
                data["applicable_classes"] = self._get_obj_ref_applicabilities(prop_obj.catalog_property_id)
        return data

    def get_property_data_for_class(self, class_code):
        self._load_class_properties()
        self._load_block_prop_details()
        result = {}
        for prop in self._properties_by_class.get(class_code, []):
            result[prop.code] = self.get_property_data(prop)
        return result

    def get_properties(self, class_code=None, include_bases=False):
        self._load_class_properties()
        class_codes = None
        if class_code:
            class_codes = [class_code]
            if include_bases:
                class_codes += self._resolve_parent_classes(class_code)

        result = {}
        for clazz, props in self._properties_by_class.items():
            if not class_codes or clazz in class_codes:
                for prop in props:
                    result[prop.code] = prop
        return result

    def get_catalog_values(
        self, active_only, request=None, for_variants=False, with_normalized_values=False
    ):
        self._load_class_properties()
        self._load_block_prop_details()
        catalog_values = {}

        prop_oids = set()
        if not for_variants:
            # child props cannot be used for variants
            for prop_code, prop in self._child_prop_by_code.items():
                if prop.has_enum_values:
                    prop_oids.add(prop.cdb_object_id)
            if prop_oids:
                catalog_value_objs_by_prop_oid = defaultdict(list)
                if active_only:
                    catalog_value_objs = PropertyValue.Query(
                        PropertyValue.property_object_id.one_of(*prop_oids) & (PropertyValue.is_active == 1)
                    )
                else:
                    catalog_value_objs = PropertyValue.Query(
                        PropertyValue.property_object_id.one_of(*prop_oids)
                    )
                for catalog_value_obj in catalog_value_objs:
                    catalog_value_objs_by_prop_oid[catalog_value_obj.property_object_id].append(
                        catalog_value_obj
                    )
                for property_object_id, catalog_value_objs in catalog_value_objs_by_prop_oid.items():
                    catalog_values[self._child_prop_code_by_oid[property_object_id]] = \
                        PropertyValue.to_json_data(catalog_value_objs, request)

        class_oids = set()
        for class_code, props in self._properties_by_class.items():
            for prop in props:
                if for_variants and not prop.for_variants:
                    continue
                if prop.has_enum_values:
                    class_oids.add(prop.classification_class_id)

        if class_oids:
            catalog_value_objs_by_prop_code = defaultdict(list)
            stmt = """
                select property_id as property_object_id, cs_class_property_values_v.*
                from cs_class_property_values_v where {class_ids} {active_condition}
            """.format(
                class_ids=tools.format_in_condition('classification_class_id', class_oids),
                active_condition="and is_active = 1" if active_only else ""
            )
            for catalog_value_obj in ClassPropertyValuesView.SQL(stmt):
                catalog_value_objs_by_prop_code[catalog_value_obj.property_code].append(catalog_value_obj)
            for prop_code, catalog_value_objs in catalog_value_objs_by_prop_code.items():
                catalog_values[prop_code] = PropertyValue.to_json_data(catalog_value_objs, request)
        return catalog_values


    def _calculate_client_view(self):
        # calculate information which properties shall be displayed in which class
        class_codes_displaying_prop_by_prop_code = defaultdict(set)
        for assigned_class_code in self._assigned_class_codes:
            visible_property_codes_for_assigned_class = set()
            path = [assigned_class_code] + self._resolve_parent_classes(assigned_class_code)
            for class_code in path:
                for group in self._metadata["classes"][class_code].get("property_groups", []):
                    for property_ref in group["properties"]:
                        property_code = property_ref["prop_code"]
                        if property_code not in visible_property_codes_for_assigned_class:
                            # store deepest occurrence for property in class path
                            visible_property_codes_for_assigned_class.add(property_code)
                            class_codes_displaying_prop_by_prop_code[property_code].add(class_code)
        # remove duplicated properties from groups
        classes_with_properties = set(self._assigned_class_codes)
        for class_code, clazz in self._metadata["classes"].items():
            for group in clazz.get("property_groups", []):
                props_to_display = []
                for prop in group["properties"]:
                    if class_code in class_codes_displaying_prop_by_prop_code[prop["prop_code"]]:
                        props_to_display.append(prop)
                        classes_with_properties.add(class_code)
                group["properties"] = props_to_display
        self._metadata["classes_view"] = self._get_classes_view(classes_with_properties)

    def _get_classes_view(self, classes_with_properties):
        """
        Returns an ordered list of class codes for display purposes on client side.
        The list contains assigned classes and it's parents and is ordered buttom up and alphabetically
        by the internationalized class name on each level. Classes without properties are filtered out.
        """

        def add_to_tree(t, path):
            for node in path:
                t = t[node]

        def build_orderd_list(dict_tree):
            # get class infos and sort them alphabetically by internationalized name
            classinfos = [self._class_infos_by_code[code] for code in dict_tree.keys()]
            classinfos = sorted(
                classinfos, key=lambda class_info: (class_info["pos"], class_info["name"]), reverse=True
            )
            for class_info in classinfos:
                code = class_info["code"]
                classes_view.append(code)
                build_orderd_list(dict_tree[code])

        # collect class paths for each assigned class starting from it's root class
        class_pathes = []
        for class_code in self._assigned_class_codes:
            path = list(self._resolve_parent_classes(class_code)) + [class_code]
            class_pathes.append(path)

        # build a tree
        Tree = lambda: defaultdict(Tree)
        tree = Tree()
        for path in class_pathes:
            add_to_tree(tree, path)
        # build an ordered list from the tree
        classes_view = []
        build_orderd_list(tree)

        # filter out classes without properties
        classes_view = [code for code in classes_view if code in classes_with_properties]
        classes_view.reverse()
        return classes_view

    def get_classification_metadata(self):
        if self._metadata is None:
            self._metadata = {}
            self._load_classes()
            classes = {}
            for code in self._assigned_class_codes:
                class_info = self.get_class_metadata(code)
                if class_info:
                    classes.update(class_info)
            self._metadata["classes"] = classes
            self._metadata["assigned_classes"] = self._assigned_class_codes
            if not self._narrowed:
                self._calculate_client_view()
        return self._metadata

    def get_classification_data(self, with_object_descriptions=True, calc_checksums=True):
        if self.obj:
            dd_classnames = [self.obj.GetClassname()]
        else:
            dd_classnames = tools.get_dd_classnames([self.object_oid])
        data, checksums = ClassificationData._load_data(
            [self.object_oid], dd_classnames, self._narrowed, self._request, calc_checksums=calc_checksums,
            with_object_descriptions=with_object_descriptions
        )
        result = data[0]
        self._data_checksum = checksums[0] if calc_checksums else None

        # reduce result to the props
        if self._check_rights:
            self._load_class_properties()
            addtl_properties = ClassificationData.get_catalog_property_metadata(
                list(result), check_rights=self._check_rights
            )
            property_codes = set(result.keys()) - set(
                list(self._prop_codes_by_oid.values()) + list(addtl_properties.keys())
            )
            self.filter_values(property_codes, result)
        elif self.class_codes:
            self._load_class_properties()
            for prop_code in list(result):
                if prop_code not in self._prop_codes_by_oid.values():
                    del result[prop_code]

        return result

    def get_classification_data_for_oids(self, oids):
        result = {}
        if not oids:
            return result

        dd_classnames = tools.get_dd_classnames(oids)
        data, checksums = ClassificationData._load_data(
            oids, dd_classnames, self._narrowed, self._request, calc_checksums=True
        )
        assigned_classes = defaultdict(set)
        stmt = (
            "SELECT ref_object_id, class_code FROM cs_object_classification WHERE {}".format(
                tools.format_in_condition("ref_object_id", oids)
            )
        )
        for object_classification in sqlapi.RecordSet2(sql=stmt):
            assigned_classes[object_classification.ref_object_id].add(object_classification.class_code)
        pos = 0
        for values in data:
            result[oids[pos]] = {
                "assigned_classes": assigned_classes.get(oids[pos], []),
                "properties": values,
                "values_checksum": checksums[pos]
            }
            pos += 1
            if self.class_codes:
                self._load_class_properties()
                for prop_code in list(values):
                    if prop_code not in self._prop_codes_by_oid.values():
                        del values[prop_code]
        return result

    @classmethod
    def _load_data(cls, object_ids, dd_classnames, narrowed, request, calc_checksums=False, with_object_descriptions=True):
        checksums = [] if calc_checksums else None
        result = []
        if not object_ids:
            return result, checksums

        for dd_classname in dd_classnames:
            prepare_read(dd_classname)

        stmt = "SELECT * from cs_object_property_value where {} order by ref_object_id, property_path".format(
            tools.format_in_condition("ref_object_id", object_ids)
        )
        data = defaultdict(list)
        for r in sqlapi.RecordSet2(sql=stmt):
            # group object property values by ref_object_id
            data[r.ref_object_id].append(r)

        # process raw data for each ref_object_id
        # Important: keep ordering as defined by object_ids parameter
        for object_id in object_ids:
            result.append(cls._load_from_records(data.get(object_id, []), narrowed, request, with_object_descriptions))
            if calc_checksums:
                checksums.append(cls.calc_checksum_from_records(data.get(object_id, [])))

        return result, checksums

    @classmethod
    def load_data(cls, object_ids, narrowed, request, calc_checksums=False):
        dd_classnames = tools.get_dd_classnames(object_ids)
        return ClassificationData._load_data(object_ids, dd_classnames, narrowed, request, calc_checksums)

    @classmethod
    def _load_from_records(cls, recs, narrowed, request, with_object_descriptions=True):
        curr_obj_result = defaultdict(list)
        float_range_data = None
        multilang_data = None
        for i, val in enumerate(recs):
            parent_dict = curr_obj_result
            value_from_record = ObjectPropertyValue.get_value_from_record(val)
            property_path = val.property_path
            property_type = val.property_type
            property_code = val.property_code
            val_id = val.id
            if property_path:
                value_path = []
                for path_segment in property_path.split(ClassificationConstants.BLOCK_PATH_SEP)[:-1]:
                    code_and_pos = path_segment.split(':')
                    code = code_and_pos[0]
                    value_pos = 0 if len(code_and_pos) == 1 else int(code_and_pos[1])
                    value_path.append(path_segment)
                    if code in parent_dict and len(parent_dict[code]) >= value_pos + 1:
                        parent_dict = parent_dict[code][value_pos]["value"]["child_props"]
                    else:
                        block_prop = {"property_type": "block",
                                      "id": ClassificationConstants.BLOCK_PATH_SEP.join(value_path),
                                      "value": {"child_props": defaultdict(list)}}
                        if not narrowed:
                            block_prop["value"]["description"] = ""
                            block_prop["value_path"] = ClassificationConstants.BLOCK_PATH_SEP.join(value_path)

                        parent_dict[code].append(block_prop)
                        parent_dict = block_prop["value"]["child_props"]


            if property_type == "float_range":
                data_dict = value_from_record
                data_dict["id"] = val_id
                data_dict["unit_label"] = UnitCache.get_unit_label(data_dict["unit_object_id"])

                val_dict = {
                    data_dict['range_identifier']: data_dict
                }
                if float_range_data is None:
                    float_range_data = {
                        "property_type": property_type,
                        "id": property_path,
                        "value": val_dict
                    }
                    if not narrowed:
                        float_range_data["value_path"] = property_path
                else:
                    float_range_data["value"].update(val_dict)

                next_property_path = None
                if len(recs) > i + 1:
                    next_property_path = recs[i + 1].property_path
                if next_property_path and next_property_path == property_path:
                    # collect more values
                    continue
                else:
                    # store collected floatrange data
                    parent_dict[property_code].append(float_range_data)
                    float_range_data = None

            elif property_type == "multilang":
                # collect multilang values (one value entry for each language with same property_path)
                data_dict = value_from_record
                data_dict["id"] = val_id
                val_dict = {data_dict['iso_language_code']: data_dict}

                if multilang_data is None:
                    multilang_data = {"property_type": property_type,
                                      "id": property_path,
                                      "value": val_dict}
                    if not narrowed:
                        multilang_data["value_path"] = property_path
                else:
                    multilang_data["value"].update(val_dict)

                next_property_path = None
                if len(recs) > i + 1:
                    next_property_path = recs[i + 1].property_path
                if next_property_path and next_property_path == property_path:
                    # collect more values
                    continue
                else:
                    # store collected multilang data
                    parent_dict[property_code].append(multilang_data)
                    multilang_data = None
            else:
                data = {
                    "property_type": property_type,
                    "id": val_id,
                    "value": value_from_record
                }
                if not narrowed:
                    data["value_path"] = property_path

                if property_type == 'float':
                    # add unit label for float
                    data["value"]["unit_label"] = UnitCache.get_unit_label(
                        data["value"]["unit_object_id"]
                    )
                elif property_type == 'objectref':
                    # add ui link and text
                    if not narrowed and with_object_descriptions:
                        data["addtl_value"] = tools.get_addtl_objref_value(value_from_record, request)
                parent_dict[property_code].append(data)
        if not narrowed:
            util.create_all_block_descriptions(curr_obj_result)
        return curr_obj_result

    @classmethod
    def calc_checksum(cls, value_objects):
        value_records = [value_obj._record for value_obj in value_objects]
        return cls.calc_checksum_from_records(value_records)

    @classmethod
    def calc_checksum_from_records(cls, value_records):

        def date_to_str(dt):
            if isinstance(dt, datetime.date):
                return typeconversion.to_legacy_date_format(dt)
            return dt

        hash_obj = hashlib.md5()
        sorted_records = sorted(value_records, key=lambda v: v["id"])
        for rec in sorted_records:
            hash_obj.update(json.dumps(rec.items(), default=date_to_str, sort_keys=True).encode("utf-8"))

        return hash_obj.hexdigest()

    @classmethod
    def calc_persistent_checksum(cls, value_objects):
        def date_to_str(dt):
            if isinstance(dt, datetime.date):
                return typeconversion.to_legacy_date_format(dt)
            return dt

        ignore_keys = set(["id", "ref_object_id"])
        hash_obj = hashlib.md5()
        value_objects = sorted(value_objects, key=lambda v: v["property_path"])
        for v in value_objects:
            data = v._record.items() # pylint: disable=W0212
            data = [item for item in data if item[0] not in ignore_keys]
            hash_obj.update(json.dumps(data, default=date_to_str, sort_keys=True).encode("utf-8"))

        return hash_obj.hexdigest()

    @classmethod
    def get_catalog_property_metadata(cls, catalog_property_codes, check_rights=False):
        props = Property.KeywordQuery(code=catalog_property_codes)
        return cls.get_catalog_property_metadata_for_properties(props, check_rights=check_rights)

    @classmethod
    def get_catalog_property_metadata_for_properties(cls, catalog_properties, check_rights=False):
        result = {}

        prop_ids = [prop.cdb_object_id for prop in catalog_properties if prop.cdb_classname == "cs_object_reference_property"]
        obi_ref_applicabilities_by_property_oid = ClassificationData.load_obj_ref_applicabilities(prop_ids)

        block_details = {}
        block_props = [prop for prop in catalog_properties if prop.cdb_classname == "cs_block_property"]
        ClassificationData._resolve_block_properties(block_props, False, block_details, {})

        for prop in catalog_properties:
            if check_rights and not prop.CheckAccess('read'):
                continue
            prop_type = prop.getType()
            if prop_type == 'block':
                result[prop.code] = block_details.get(prop.code)
            else:
                raw_data = dict(prop._record.items())
                raw_data['is_editable'] = 1
                raw_data['is_mandatory'] = 0
                raw_data['is_visible'] = 1
                raw_data['display_option'] = DisplayOptions.NewLine.id
                result[prop.code] = ClassificationData._get_property_data(raw_data, prop_type)
                if prop.cdb_classname == "cs_object_reference_property":
                    result[prop.code]["applicable_classes"] = obi_ref_applicabilities_by_property_oid.get(prop.cdb_object_id, [])

        return result
