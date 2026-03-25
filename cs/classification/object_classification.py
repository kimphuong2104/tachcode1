# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module object_classifiaction

This module contains utility functions for object classification. These functions are not part
of the external api!
"""

import copy
import datetime
import json
import logging
import re

from collections import defaultdict

from cdb import cdbuuid
from cdb import ElementsError
from cdb import sqlapi
from cdb import transactions
from cdb import typeconversion
from cdb import ue
from cdb import util as cdb_util
from cdbwrapc import StatusInfo

from cs.classification import ClassificationConstants, ClassificationException, ObjectClassification, \
    ObjectClassificationLog, FloatRangeObjectPropertyValue
from cs.classification import ClassificationChecksum, ObjectPropertyValue, prepare_write, type_map
from cs.classification import tools
from cs.classification import util
from cs.classification import solr
from cs.classification import units
from cs.classification.api import InvalidChecksumException, ConstaintsViolationException, SearchIndexException
from cs.classification.classes import BlockClassProperty, ClassificationClass, ClassProperty, ClassPropertyValuesView
from cs.classification.classification_data import ClassificationData
from cs.classification.validation import ClassificationValidator, ClassificationValidationException


LOG = logging.getLogger(__name__)


class BlockPathsNotUnique(ClassificationException):

    def __init__(self, block_paths_skipped):
        self.block_paths_skipped = block_paths_skipped
        super(BlockPathsNotUnique, self).__init__("cs_classification_blocks_skiped")

    def getDetails(self):
        return "\n".join(sorted(self.block_paths_skipped))


class ExclusiveClassViolation(ClassificationException):

    def __init__(self, class_codes):
        self.details = "\n".join(sorted(class_codes))
        super(ExclusiveClassViolation, self).__init__(
            "cs_classification_exclusive_class_violation", "\n" + self.details
        )

    def getDetails(self):
        return self.details


class MandatoryValuesException(ClassificationException):

    def __init__(self, property_paths):
        self.property_paths = property_paths
        super(MandatoryValuesException, self).__init__(
            "cs_classification_mandatory_fields_not_filled"
        )

    def getDetails(self):
        property_paths = set()
        for property_path in self.property_paths:
            property_paths.add("/".join(property_path))
        sorted_property_path = sorted(property_paths)
        return "\n".join(sorted_property_path)


class NoWriteAccess(ClassificationException):

    def __init__(self, read_only_property_paths):
        self.read_only_property_paths = read_only_property_paths
        super(NoWriteAccess, self).__init__("cs_classification_no_write_access")

    def getDetails(self):
        return "\n".join(sorted(self.read_only_property_paths))


class PatternViolated(ClassificationException):

    def __init__(self, paths_with_pattern_violation):
        self.paths_with_pattern_violation = paths_with_pattern_violation
        super(PatternViolated, self).__init__("cs_classification_pattern_format_error")

    def getDetails(self):
        return "\n".join(sorted(self.paths_with_pattern_violation))


class ClassificationUpdater(object):

    def __init__(self, obj, type_conversion=None, full_update_mode=True):
        self.obj = obj
        self.object_oid = obj.cdb_object_id if obj else None
        self.type_conversion = type_conversion
        self._base_units = {}
        self._existing_object_classifications = []
        self._existing_value_objects_by_id = {}
        self._existing_value_objects = []
        self._updated_value_object_ids = set()
        self._float_props = set()
        self._float_values = []
        self._prop_to_assigned_classes = {}
        self._classes_for_access_control_check = set()
        self._catalog_prop_codes = set()

        self._classes_with_write_access = set()
        self._properties_with_write_access = set()
        self._skiped_prop_codes = set()

        # If True, data must be provided completely. Missing properties and classes are deleted.
        # If False, data can be specified partially and only updates/inserts are applied.
        self._full_update_mode = full_update_mode
        self._persistent_checksum = False

        self._values_to_create = []
        self._values_to_update = []
        self._values_to_delete = []
        self._properties_to_delete = set()

        self._all_class_codes = set()
        self._curr_class_codes = set()
        self._classes_to_add = set()
        self._classes_to_delete = set()
        self._class_infos_by_code = {}
        self._class_infos_by_oid = {}
        self._access_info = {}
        if obj:
            prepare_write(obj.GetClassname())

    def update(
        self, data, mandatory_prop_paths=None, props_with_no_values=None, check_access=True, update_index=True
    ):
        from cdb import sig

        def date_to_str(dt):
            if isinstance(dt, datetime.date):
                return typeconversion.to_legacy_date_format(dt)
            return dt

        def calculate_diffs(check_access, data):
            self._calculate_diffs(data)
            if check_access:
                self._check_access()
            update_data = copy.deepcopy(data)
            self.strip_diff_values(update_data)
            update_data["values_checksum"] = "invalid"
            new_assigned_classes = set(data["assigned_classes"])
            new_assigned_classes = new_assigned_classes.difference(self._classes_to_delete)
            update_data["assigned_classes"] = list(new_assigned_classes)
            if "metadata" in data:
                update_data["metadata"]["assigned_classes"] = update_data["assigned_classes"]
            update_data["deleted_classes"] = list(self._classes_to_delete)
            update_data["new_classes"] = list(self._classes_to_add)
            for new_value in self._values_to_create:
                self.set_old_value(update_data["properties"], None, new_value[1])
            for update_value in self._values_to_update:
                self.set_old_value(update_data["properties"], update_value[0], update_value[1])
            update_data["deleted_properties"] = self._values_to_delete
            return update_data

        try:
            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug(
                    "update classification before classification_update_pre: {} - {}".format(
                        self.obj.__class__, self.obj.cdb_object_id
                    )
                )

            sig.emit(self.obj.__class__, "classification_update", "pre")(self.obj, data)

            self._persistent_checksum = data.get(ClassificationConstants.PERSISTENT_VALUES_CHECKSUM, False)

            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug(
                    "update classification after classification_update_pre: {} - {}".format(
                        self.obj.__class__, self.obj.cdb_object_id
                    )
                )

            self._prepare_update(data)
            self.calculate_normalized_float_values(data["properties"])

            ClassificationValidator.calculate_formulars(
                data["properties"], self._base_units, self._properties_with_write_access
            )

            if mandatory_prop_paths is not None and props_with_no_values is not None:
                properties = dict(data["properties"])
                # add missing prop values for rule validation
                for prop_code, prop_values in props_with_no_values.items():
                    if prop_code not in properties:
                        properties[prop_code] = prop_values
                # validate rules and add mandatory properties from validation
                rule_results = ClassificationValidator.calculate_rules(properties)
                missing_mandatory_values = []
                for prop_code, results in rule_results.items():
                    if 1 == results['mandatory']:
                        mandatory_prop_paths.append([prop_code])
                # check mandatory property values
                for prop_path in mandatory_prop_paths:
                    ClassificationUpdater._check_mandatory_properties(
                        missing_mandatory_values, [], prop_path, data["properties"]
                    )
                if missing_mandatory_values:
                    raise MandatoryValuesException(missing_mandatory_values)

            error_messages = ClassificationValidator.check_constraints(
                self._classes_with_write_access, data["properties"], False, True
            )
            if error_messages:
                raise ConstaintsViolationException(error_messages)

            update_data = calculate_diffs(check_access, data)

            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug(
                    "update classification before classification_update_pre_commit: {} - {}".format(
                        self.obj.__class__, self.obj.cdb_object_id
                    )
                )

            data_before_pre_commit = json.dumps(data, default=date_to_str, sort_keys=True)
            sig.emit(self.obj.__class__, "classification_update", "pre_commit")(self.obj, data, update_data)

            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug(
                    "update classification after classification_update_pre_commit: {} - {}".format(
                        self.obj.__class__, self.obj.cdb_object_id
                    )
                )

            # only if data has been changed in pre_commit ...
            data_after_pre_commit = json.dumps(data, default=date_to_str, sort_keys=True)
            if data_before_pre_commit != data_after_pre_commit:
                self.calculate_normalized_float_values(data["properties"])
                update_data = calculate_diffs(check_access, data)

            classification_changed = self._apply_diffs_to_db()
            if not classification_changed:
                return

            cdb_mdate = datetime.datetime.utcnow()
            LOG.debug(
                "update classification database updated: {} - {}".format(
                    self.obj.__class__, self.obj.cdb_object_id
                )
            )

            cdb_index_date = None
            if update_index:
                try:
                    self._update_index(data)
                    cdb_index_date = datetime.datetime.utcnow()

                    if LOG.isEnabledFor(logging.DEBUG):
                        LOG.debug(
                            "update classification search index: {} - {}".format(
                                self.obj.__class__, self.obj.cdb_object_id
                            )
                        )
                except Exception as ex: # pylint: disable=W0703
                    LOG.exception(ex)
                    raise SearchIndexException()

            ObjectClassificationLog.update_log(
                ref_object_id=self.object_oid, cdb_mdate=cdb_mdate, cdb_index_date=cdb_index_date
            )

            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug(
                    "update classification before classification_update_post: {} - {}".format(
                        self.obj.__class__, self.obj.cdb_object_id
                    )
                )
            sig.emit(self.obj.__class__, "classification_update", "post")(self.obj, update_data)
            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug(
                    "update classification after classification_update_post: {} - {}".format(
                        self.obj.__class__, self.obj.cdb_object_id
                    )
                )

            return update_data

        except ClassificationValidationException as validation_exception:
            LOG.exception(validation_exception)
            raise validation_exception.to_ue_Exception()

    def _update_index(self, data):
        class_oids = set()
        if self._full_update_mode:
            for class_code in data["assigned_classes"]:
                class_oids.add(self._class_infos_by_code[class_code]["cdb_object_id"])
            properties = data["properties"]
        else:
            # get complete classification data to update the index as
            # solr does not support incremental updates with nested docs

            #solr.index_object(self.obj)

            classification = ClassificationData(self.obj, check_rights=False)
            properties = ClassificationData._load_from_records(
                self._existing_value_objects,
                narrowed=False, request=None, with_object_descriptions=False
            )
            properties.update(data["properties"])
            for prop_code_to_delete in self._properties_to_delete:
                if prop_code_to_delete in properties:
                    del properties[prop_code_to_delete]

            class_codes = set(
                [objclass.class_code for objclass in self._existing_object_classifications]
            )
            class_codes = class_codes - self._classes_to_delete | self._classes_to_add
            for class_code in class_codes:
                class_oids.add(self._class_infos_by_code[class_code]["cdb_object_id"])

        solr.update_index(
            self.obj, properties, list(class_oids), self._catalog_prop_codes, update_log=False
        )
        self.obj.UpdateSearchIndex()

    def strip_diff_values(self, data):
        for key in ["deleted_classes", "deleted_properties", "new_classes"]:
            if key in data:
                del data[key]
            pass
        self.strip_old_values(data["properties"])

    def strip_old_values(self, properties):
        for prop in properties.values():
            for property_value in prop:
                if 'block' == property_value['property_type']:
                    self.strip_old_values(property_value['value']['child_props'])
                elif 'multilang' == property_value['property_type'] and property_value['value']:
                    for _, lang_value in property_value['value'].items():
                        if 'old_value' in lang_value:
                            del lang_value['old_value']
                elif 'old_value' in property_value:
                    del property_value['old_value']

    def set_old_value(self, data, old_value_obj, value_args):
        property_path = value_args['property_path'].split(ClassificationConstants.BLOCK_PATH_SEP)
        props_data = data
        for path_segment in property_path:
            code_and_pos = path_segment.split(':')
            property_code = code_and_pos[0]
            value_pos = 0 if len(code_and_pos) == 1 else int(code_and_pos[1])
            prop_value = props_data[property_code][value_pos]
            if 'block' == prop_value['property_type']:
                props_data = prop_value['value']['child_props']

        old_value = None
        if old_value_obj:
            property_type = old_value_obj['property_type']
            if property_type == "float":
                old_value = old_value_obj.value
                if old_value_obj["unit_object_id"]:
                    old_value['unit_label'] = units.UnitCache.get_unit_label(old_value_obj['unit_object_id'])
            elif property_type == "float_range":
                old_value = old_value_obj.value
                if old_value_obj["unit_object_id"]:
                    old_value['unit_label'] = units.UnitCache.get_unit_label(old_value_obj['unit_object_id'])
                if "old_value" not in prop_value:
                    prop_value["old_value"] = {}
                prop_value["old_value"][old_value["range_identifier"]] = old_value
                return
            elif property_type == "multilang":
                value = prop_value['value'][old_value_obj.iso_language_code]
                value[u'old_value'] = old_value_obj.text_value
                return
            else:
                old_value = old_value_obj.value
        elif prop_value.get('property_type', '') == "multilang":
            for _, lang_value in prop_value['value'].items():
                lang_value['old_value'] = None
            return

        prop_value[u'old_value'] = old_value

    @classmethod
    def update_persistent_checksum(cls, obj):
        cls.update_persistent_checksum_for_id(obj.cdb_object_id)

    @classmethod
    def update_persistent_checksum_for_id(cls, ref_object_id, existing_checksum=None):
        checksum = ClassificationData.calc_persistent_checksum(
            ObjectPropertyValue.KeywordQuery(ref_object_id=ref_object_id)
        )
        classification_checksum = existing_checksum if existing_checksum else ClassificationChecksum.ByKeys(
            ref_object_id=ref_object_id
        )
        if classification_checksum:
            classification_checksum.Update(checksum=checksum)
        else:
            ClassificationChecksum.Create(ref_object_id=ref_object_id, checksum=checksum)

    @classmethod
    def flush_normalized_float_values(cls, props):
        for prop_code, prop_values in props.items():
            if not prop_values:
                continue
            for prop_value in prop_values:
                prop_type = prop_value["property_type"]
                if prop_type == "block":
                    cls.flush_normalized_float_values(prop_value["value"]["child_props"])
                elif prop_type == "float":
                    prop_value["value"]["float_value_normalized"] = None
                elif prop_type == "float_range":
                    for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                        prop_value["value"][range_identifier]["float_value_normalized"] = None

    @classmethod
    def multiple_update(cls, objs, data, typeconversion=None):
        """
        Classification of given objects is updated with given data:

        - For new class assignments all classification data is added.
        - Properties with no value set in data are ignored
          (currently there is no possibility to delete values).
        - For existing class assignments the classification data is updated:
          - Values of single valued properties are updated
          - Values of multiple valued simple properties are added if the value does not already exist.
          - Values of multiple valued block properties are updated as long a the keypath is complete.
            Updating stops if there is a multiple valued block property  without identifying
            property set.

        Mandatory properties as well as constraints and exclusive class assignments are checked
        and formulas are calculated based on the updated data.

        ATTENTION: there is no check if the given class codes are applicable, not abstract and
                   no exclusive flag is violated!

        :param objs: the ce objects to update the classification data for
        :param data: dict with assigned classes and property data

            .. code-block:: python

                {
                    "assigned_classes" : [<class_codes>],
                    "properties": {
                        <PROPERTY_CODE> : [<PROPERTY_VALUE_DICT>]
                    }
                }

        :param type_conversion: optional function used for type conversion before the data is updated in
                                the database.
        :return: dictionary with exceptions occurred during update by cdb_object_id of objects to be updated
        :rtype: `dict`

        """
        classification = ClassificationData(
            obj=None,
            class_codes=data["assigned_classes"],
            request=None,
            narrowed=False,
            released_only=False
        )
        properties = classification.get_properties(include_bases=True)
        classification._load_block_prop_details()
        block_prop_details = classification._block_details

        cls.flush_normalized_float_values(data["properties"])

        mandatory_prop_paths = []
        for prop in properties.values():
            if isinstance(prop, BlockClassProperty):
                cls._get_mandatory_property_paths(
                    mandatory_prop_paths, [prop.code], block_prop_details[prop.code]
                )
            elif prop.is_mandatory:
                mandatory_prop_paths.append([prop.code])

        obj_ids = [obj.cdb_object_id for obj in objs]
        old_classification_data = classification.get_classification_data_for_oids(obj_ids)

        errors = {}
        warnings = defaultdict(list)

        pattern_violating_values = cls.check_pattern(
            classification, data
        )
        if pattern_violating_values:
            for obj in objs:
                errors[obj.cdb_object_id] = PatternViolated(pattern_violating_values)
            return errors, warnings

        stmt = """
            select distinct class_code from cs_object_classification where {}
        """.format(tools.format_in_condition("ref_object_id", obj_ids))
        all_class_codes = set(data["assigned_classes"])
        if not all_class_codes:
            # no update needed without assigned_classes
            return errors, warnings
        for row in sqlapi.RecordSet2(sql=stmt):
            all_class_codes.add(row["class_code"])
        class_infos = ClassificationClass.get_base_class_infos(
            class_codes=all_class_codes, include_given=True, only_released=False
        )
        class_infos_by_code = {}
        for class_info in class_infos:
            class_infos_by_code[class_info["code"]] = class_info

        for obj in objs:
            try:
                props_with_no_values = {}
                persistent_data = old_classification_data.get(obj.cdb_object_id, {})
                cls._check_exclusive_classes(persistent_data, data["assigned_classes"], class_infos_by_code)
                # merge classification data ...
                updater = ClassificationUpdater(
                    obj, type_conversion=typeconversion, full_update_mode=False
                )
                block_paths_skipped = []
                eav_ids_to_delete = {}
                persistent_property_data = persistent_data.get("properties", {})
                class_prop_codes_with_update_data = set()
                for prop_code, prop_values in data["properties"].items():
                    prop = properties.get(prop_code, None)
                    if prop is None:
                        # ignore values if property does not exist in assigned classes
                        # maybe an error is better here
                        continue
                    if (
                        util.is_property_value_set(prop_values) or
                        ClassificationValidator.has_formula(prop_code)
                    ):
                        class_prop_codes_with_update_data.add(prop_code)
                        if prop_code not in persistent_property_data:
                            if 'delete_all' == prop_values[0].get('operation'):
                                # don't add any values if operation is delete all
                                pass
                            else:
                                # add new values to existing classification
                                persistent_property_data[prop_code] = prop_values
                        elif isinstance(prop, BlockClassProperty):
                            classification._load_block_prop_details()
                            cls._merge_block_prop_values(
                                prop_code,
                                block_paths_skipped,
                                block_prop_details[prop_code],
                                persistent_property_data[prop_code],
                                prop_values,
                                eav_ids_to_delete
                            )
                        elif prop.is_multivalued:
                            util.merge_simple_values(
                                persistent_property_data[prop_code], prop_values, eav_ids_to_delete
                            )
                        else:
                            util.replace_simple_prop_value(
                                persistent_property_data[prop_code][0], prop_values[0], eav_ids_to_delete
                            )
                    else:
                        props_with_no_values[prop_code] = prop_values
                        if prop_code not in persistent_property_data:
                            # add empty values to ensure that the user exists get complete structure
                            persistent_property_data[prop_code] = prop_values
                        continue
                # perform update
                updater.update({
                    "assigned_classes": data["assigned_classes"],
                    "properties": persistent_property_data
                }, mandatory_prop_paths, props_with_no_values, update_index=False)
                # delete eav entries because updater is not in full_update_mode and does not delete values
                read_only_prop_paths = updater._skiped_prop_codes & class_prop_codes_with_update_data
                if eav_ids_to_delete:
                    ids_to_delete = set()
                    for id, path in eav_ids_to_delete.items():
                        class_prop_code = path.split("/")[0].split(":")[0]
                        if class_prop_code in updater._properties_with_write_access:
                            ids_to_delete.add(id)
                        else:
                            read_only_prop_paths.add(class_prop_code)
                    if ids_to_delete:
                        sqlapi.SQLdelete(
                            "from cs_object_property_value where {}".format(
                                tools.format_in_condition('id', ids_to_delete)
                            )
                        )
                if read_only_prop_paths:
                    warnings[obj.cdb_object_id].append(NoWriteAccess(read_only_prop_paths))
                if block_paths_skipped:
                    warnings[obj.cdb_object_id].append(BlockPathsNotUnique(block_paths_skipped))
            except (ue.Exception, InvalidChecksumException) as e:
                errors[obj.cdb_object_id] = e
        # update index for all objects
        solr.index_objects(objs)
        return errors, warnings

    @classmethod
    def _check_exclusive_classes(cls, data, assigned_classes, class_infos_by_code):
        # check exclusive flags ...
        persistent_class_assignments = data.get("assigned_classes", [])
        exclusive_class_codes = set()
        for persistent_class_assignment in persistent_class_assignments:
            if 0 == class_infos_by_code[persistent_class_assignment]["is_exclusive"]:
                continue
            for base_class_code in class_infos_by_code[persistent_class_assignment]["parent_class_codes"]:
                if 1 == class_infos_by_code[base_class_code]["is_exclusive"]:
                    exclusive_class_codes.add(base_class_code)
                    break

        if exclusive_class_codes:
            exclusive_class_codes_violated = set()
            for class_code in assigned_classes:
                parent_class_codes = class_infos_by_code[class_code]["parent_class_codes"]
                already_classified = False
                for parent_class_code in [class_code] + parent_class_codes:
                    if parent_class_code in persistent_class_assignments:
                        already_classified = True
                        break
                if not already_classified and len(exclusive_class_codes.intersection(set(parent_class_codes))) > 0:
                    exclusive_class_codes_violated.add(class_code)
            if exclusive_class_codes_violated:
                exclusive_classes_names = ClassificationClass.get_class_names(exclusive_class_codes_violated)
                raise ExclusiveClassViolation(exclusive_classes_names)

    @classmethod
    def _merge_block_prop_values(
            cls, block_prop_path, block_paths_skipped, block_prop_data,
            old_values, new_values, eav_ids_to_delete
    ):
        if 1 == block_prop_data["flags"][3]:  # check if block is multivalued
            if block_prop_data["key_property_code"]:
                # find matching blocks
                for new_block_value in new_values:
                    new_block_identifier = \
                        new_block_value["value"]["child_props"][block_prop_data["key_property_code"]][0]
                    prop_type = new_block_identifier["property_type"]
                    old_block_value_updated = False
                    for old_block_value in old_values:
                        old_block_identifying_prop = old_block_value["value"]["child_props"].get(
                            block_prop_data["key_property_code"]
                        )
                        if old_block_identifying_prop and util.are_property_values_equal(
                            prop_type, new_block_identifier["value"], old_block_identifying_prop[0]["value"],
                            compare_normalized_values=False
                        ):
                            cls._merge_child_prop_values(
                                block_prop_path,
                                block_paths_skipped,
                                block_prop_data,
                                old_block_value,
                                new_block_value,
                                eav_ids_to_delete
                            )
                            old_block_value_updated = True
                            break
                    if not old_block_value_updated:
                        # insert new value
                        old_values.append(new_block_value)
            else:
                # block key path is not unique stop merging property values ...
                block_paths_skipped.append(block_prop_path)
                return
        else:
            old_block_value = old_values[0] if old_values else None
            new_block_value = new_values[0] if new_values else None
            cls._merge_child_prop_values(
                block_prop_path,
                block_paths_skipped,
                block_prop_data,
                old_block_value,
                new_block_value,
                eav_ids_to_delete
            )

    @classmethod
    def _merge_child_prop_values(
        cls, block_prop_path, block_paths_skipped, block_prop_data, old_block_value, new_block_value,
        eav_ids_to_delete
    ):
        if not old_block_value or not new_block_value:
            return
        for child_prop_code, child_prop_values in new_block_value["value"]["child_props"].items():
            child_prop = block_prop_data["child_props_data"].get(child_prop_code, None)
            if child_prop is None:
                # ignore values if property does not exist in assigned classes
                return
            if util.is_property_value_set(child_prop_values):
                persistent_child_prop_data = old_block_value["value"]["child_props"]
                if child_prop_code not in persistent_child_prop_data:
                    # add new values to existing classification
                    persistent_child_prop_data[child_prop_code] = child_prop_values
                elif "block" == child_prop["type"]:
                    cls._merge_block_prop_values(
                        block_prop_path + "/" + child_prop_code,
                        block_paths_skipped,
                        child_prop,
                        persistent_child_prop_data[child_prop_code],
                        child_prop_values,
                        eav_ids_to_delete
                    )
                    pass
                elif 1 == child_prop["flags"][3]:  # check if child prop is multivalued
                    util.merge_simple_values(
                        persistent_child_prop_data[child_prop_code],
                        child_prop_values,
                        eav_ids_to_delete
                    )
                else:
                    util.replace_simple_prop_value(
                        persistent_child_prop_data[child_prop_code][0],
                        child_prop_values[0],
                        eav_ids_to_delete
                    )

    @classmethod
    def _get_mandatory_property_paths(cls, mandatory_prop_paths, parent_path, block_prop_detail):
        for child_prop_data in block_prop_detail["child_props_data"].values():
            if "block" == child_prop_data["type"]:
                cls._get_mandatory_property_paths(
                    mandatory_prop_paths,
                    parent_path + [child_prop_data["code"]],
                    child_prop_data
                )
            elif 1 == child_prop_data["flags"][1]:
                mandatory_prop_paths.append(parent_path + [child_prop_data["code"]])

    @classmethod
    def _check_mandatory_properties(
            cls, missing_mandatory_values, parent_path, mandatory_prop_path, property_data
    ):
        prop_code = mandatory_prop_path[0]
        prop_values = property_data.get(prop_code)
        if not prop_values:
            missing_mandatory_values.append(parent_path + mandatory_prop_path)
        elif "block" == prop_values[0]["property_type"]:
            for block_val in prop_values:
                cls._check_mandatory_properties(
                    missing_mandatory_values,
                    parent_path + [prop_code],
                    mandatory_prop_path[1:],
                    block_val["value"]["child_props"]
                )
        else:
            if not prop_values or not util.is_property_value_set(prop_values):
                missing_mandatory_values.append(parent_path + [prop_code])

    @classmethod
    def check_classification(cls, data, check_rights=False):
        classification_data = ClassificationData(
            obj=None,
            class_codes=data["assigned_classes"],
            request=None,
            narrowed=False,
            released_only=False,
            check_rights=check_rights
        )

        updater = ClassificationUpdater(None)
        data['validation_mode'] = {'constraint': True, 'formula': True, 'rule': True}
        updater.validate(data, classification_data.get_class_codes())
        del data['validation_mode']

        error_messages = []
        missing_mandatory_values = updater.check_mandatory_property_values(
            classification_data, data, data['rule_results']
        )
        if missing_mandatory_values:
            error_messages.append(
                cdb_util.get_label("web.cs-classification-component.error_mandatory_properties")
            )

        pattern_violating_values = updater.check_pattern(
            classification_data, data
        )
        if pattern_violating_values:
            error_messages.append(
                cdb_util.get_label("web.cs-classification-component.error_pattern_violation")
            )

        identifying_value_error_paths = updater.check_identifying_properties(
            classification_data, data
        )
        if identifying_value_error_paths:
            error_messages.append(
                cdb_util.get_label("web.cs-classification-component.error_identifying_violalation")
            )

        return error_messages

    @classmethod
    def check_identifying_properties(cls, classification_data, data):

        def resolve_key_prop_codes(props_data):
            key_prop_codes = {}
            for prop_code, prop in props_data.items():
                if "block" == prop["type"]:
                    key_prop_code = prop["key_property_code"]
                    if key_prop_code:
                        key_prop_codes[prop_code] = key_prop_code
                    key_prop_codes.update(resolve_key_prop_codes(prop["child_props_data"]))
            return key_prop_codes

        def check_identifying_property_values(properties, parent_path):
            for prop_code, prop_values in properties.items():
                if prop_code in key_prop_codes:
                    key_prop_values = []
                    for pos, prop_value in enumerate(prop_values):
                        identifying_prop_value = prop_value["value"]["child_props"][
                            key_prop_codes[prop_code]][0]
                        is_duplicate = False
                        for key_prop_value in key_prop_values:
                            if util.are_property_values_equal(
                                key_prop_value["property_type"],
                                key_prop_value["value"],
                                identifying_prop_value["value"],
                                compare_normalized_values=False
                            ):
                                is_duplicate = True
                                identifying_value_error_paths.append(
                                    "{parent_path}{code}:{pos:03}".format(
                                        parent_path=parent_path,
                                        code=prop_code,
                                        pos=pos
                                    )
                                )
                        if not is_duplicate:
                            key_prop_values.append(identifying_prop_value)
                if "block" == prop_values[0]["property_type"]:
                    for pos, prop_value in enumerate(prop_values):
                        check_identifying_property_values(
                            prop_value["value"]["child_props"],
                            "{parent_path}{code}:{pos:03}/".format(
                                parent_path=parent_path,
                                code=prop_code,
                                pos=pos
                            )
                        )
            return key_prop_codes

        classification_data._load_block_prop_details()
        key_prop_codes = resolve_key_prop_codes(classification_data._block_details)

        identifying_value_error_paths = []
        if key_prop_codes:
            check_identifying_property_values(data["properties"], "")

        return identifying_value_error_paths

    @classmethod
    def check_mandatory_property_values(cls, classification_data, data, rule_results):
        properties = classification_data.get_properties(include_bases=True)
        classification_data._load_block_prop_details()
        block_prop_details = classification_data._block_details

        mandatory_prop_paths = []
        for prop in properties.values():
            if isinstance(prop, BlockClassProperty):
                cls._get_mandatory_property_paths(
                    mandatory_prop_paths, [prop.code], block_prop_details[prop.code]
                )
            elif prop.is_mandatory:
                rule_result = rule_results.get(prop.code)
                if rule_result and 1 != rule_result['mandatory']:
                    # rule overrules mandatory flag of property
                    continue
                mandatory_prop_paths.append([prop.code])

        for prop_code, results in rule_results.items():
            if 1 == results['mandatory']:
                mandatory_prop_paths.append([prop_code])

        missing_mandatory_values = []
        for prop_path in mandatory_prop_paths:
            cls._check_mandatory_properties(
                missing_mandatory_values, [], prop_path, data["properties"]
            )
        return missing_mandatory_values

    @classmethod
    def check_pattern(cls, classification_data, data):

        def format_path(parent_path, prop_code, pos):
            path = parent_path + "/" if parent_path else ""
            path += prop_code
            if 0 != pos:
                path += ':' + str(pos)
            return path

        def check_values(parent_path, property_data, block_prop_details):
            for prop_code, prop_values in property_data.items():
                prop_type = prop_values[0]["property_type"] if prop_values else ""
                if "block" == prop_type:
                    count = 0
                    prop_details = block_prop_details.get(prop_code, {})
                    if prop_details:
                        for block_val in prop_values:
                            check_values(
                                format_path(parent_path, prop_code, count),
                                block_val["value"]["child_props"],
                                block_prop_details[prop_code]["child_props_data"]
                            )
                            count += 1
                elif "text" == prop_type:
                    regex = ""
                    prop = properties.get(prop_code)
                    if prop:
                        regex = prop.regex
                    else:
                        prop_details = block_prop_details.get(prop_code, {})
                        regex = prop_details.get("regex", "")
                    if regex:
                        matcher = re.compile(regex)
                        count = 0
                        for prop_val in prop_values:
                            value = prop_val["value"]
                            if value and not matcher.match(value):
                                if not ClassPropertyValuesView.get_catalog_text_value(
                                    prop_code, prop_val["value"], True
                                ):
                                    pattern_violating_values.append(
                                        format_path(parent_path, prop_code, count)
                                    )
                            count += 1
                else:
                    # nothing to do for other prop types
                    pass

        properties = classification_data.get_properties(include_bases=True)
        classification_data._load_block_prop_details()

        pattern_violating_values = []
        check_values("", data["properties"], classification_data._block_details)
        return pattern_violating_values

    def calculate_normalized_float_values(self, properties):

        def _calculate_normalized_float_value(prop_code, value_dict, value_id):
            if not value_dict:
                return

            base_unit_id = self._base_units.get(prop_code, {}).get("unit_object_id")

            # use default unit for new values, if unit_object_id has not been specified
            new = value_id is None or value_id not in self._existing_value_objects_by_id

            if new and "unit_object_id" not in value_dict:
                value_dict["unit_object_id"] = base_unit_id

            # if the property has a default unit, the unit must be specified for property values
            unit_object_id = value_dict.get("unit_object_id")
            if base_unit_id and not unit_object_id:
                raise ElementsError("Unit is missing for value of property %s. The unit must "
                                    "be specified by the key unit_object_id within the value "
                                    "dictionary of the property." % prop_code)

            # calculate and set the normalized value
            value_dict["float_value_normalized"] = units.normalize_value(value_dict["float_value"],
                                                                         unit_object_id,
                                                                         base_unit_id,
                                                                         prop_code)

        self._find_floats(properties)
        self._base_units = util.load_base_units(self._float_props)

        # calculate normalized values for all floats
        for prop_code, value in self._float_values:

            if value["property_type"] == "float":
                _calculate_normalized_float_value(prop_code, value["value"], value_id=value["id"])
            elif value["property_type"] == "float_range":
                for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                    value_dict = value["value"].get(range_identifier)
                    if value_dict:
                        _calculate_normalized_float_value(prop_code, value_dict, value_dict.get("id", None))
            else:
                continue

    def validate(self, data, class_codes_for_validation):
        try:
            self.calculate_normalized_float_values(data["properties"])
            properties_for_validation = data.get("properties_for_validation")
            validation_mode = data.get("validation_mode")
            data["changed_property_codes"] = set()
            data["rule_results"] = None
            data["error_messages"] = []
            if validation_mode and validation_mode.get("formula", False):
                data["changed_property_codes"] = ClassificationValidator.calculate_formulars(
                    data["properties"], self._base_units, properties_for_validation
                )
            # evaluate constraints and rules also if formulas changed the values
            if (validation_mode and validation_mode.get("rule", False)) or data["changed_property_codes"]:
                data["rule_results"] = ClassificationValidator.calculate_rules(
                    data["properties"], properties_for_validation
                )
            if (validation_mode and validation_mode.get("constraint", False)) or data["changed_property_codes"]:
                data["error_messages"] = ClassificationValidator.check_constraints(
                    class_codes_for_validation, data["properties"], False, True
                )
        except ClassificationValidationException as validation_exception:
            LOG.exception(validation_exception)
            raise validation_exception.to_ue_Exception()

    def _prepare_update(self, data):
        self._updated_value_object_ids = set()
        self._existing_object_classifications = ObjectClassification.KeywordQuery(
            ref_object_id=self.object_oid
        )
        self._curr_class_codes = set([oc.class_code for oc in self._existing_object_classifications])

        self._existing_value_objects = ObjectPropertyValue.KeywordQuery(
            ref_object_id=self.object_oid, order_by=["property_path"]
        )
        expected_values_checksum = data.get("values_checksum")
        if expected_values_checksum:
            current_checksum = ClassificationData.calc_checksum(self._existing_value_objects)
            if current_checksum != expected_values_checksum:
                raise InvalidChecksumException()

        self._diff_class_assignments(data)

        self._existing_value_objects_by_id = {}
        for v in self._existing_value_objects:
            self._existing_value_objects_by_id[v.id] = v

    def _calculate_diffs(self, data):
        self._diff_class_assignments(data)
        self._values_to_create = []
        self._values_to_update = []
        self._values_to_delete = []
        self._diff_properties(data["properties"], data.get("deleted_properties", []))

    def _apply_diffs_to_db(self):
        # apply changes
        with transactions.Transaction():
            update_checksum = False
            classification_changed = self._apply_class_assignments()
            for val_cls, args in self._values_to_create:
                classification_changed = True
                if self._persistent_checksum:
                    val_obj = val_cls.Create(**args)
                    self._existing_value_objects_by_id[val_obj.id] = val_obj
                    update_checksum = True
                else:
                    # note: for performance reasons intentionally _Create is used, because we don't need the
                    # newly created object, which would be constructed and returned with Create.
                    val_cls._Create(**args)
            for value_obj, args in self._values_to_update:
                classification_changed = True
                update_checksum = True
                value_obj.Update(**args)
            if self._values_to_delete:
                classification_changed = True
                if self._persistent_checksum:
                    update_checksum = True
                    for value_to_delete in self._values_to_delete:
                        del self._existing_value_objects_by_id[value_to_delete.id]
                # note: for performance reasons intentionally low level sqlapi
                sqlapi.SQLdelete("from cs_object_property_value where {}".format(
                    tools.format_in_condition("id", [c.id for c in self._values_to_delete])
                ))
            if self._persistent_checksum:
                classification_checksum = ClassificationChecksum.ByKeys(ref_object_id=self.obj.cdb_object_id)
                if  update_checksum or not classification_checksum:
                    checksum = ClassificationData.calc_persistent_checksum(
                        list(self._existing_value_objects_by_id.values())
                    )
                    if classification_checksum:
                        classification_checksum.Update(checksum=checksum)
                    else:
                        ClassificationChecksum.Create(ref_object_id=self.obj.cdb_object_id, checksum=checksum)
            return classification_changed

    def _map_properties_to_assigned_classes(self, data):
        self._prop_to_assigned_classes = defaultdict(set)
        class_ids = set() # used to avoid querying class properties with same codes but different classes
        parents_by_assigned_class = defaultdict(list)
        for cls_code, class_info in self._class_infos_by_code.items():
            parent_class_codes = []
            while class_info:
                class_ids.add(class_info["cdb_object_id"])
                parent_class_codes.append(class_info["code"])
                class_info = self._class_infos_by_code.get(class_info["parent_class_code"])
            parents_by_assigned_class[cls_code] = parent_class_codes
        class_props = ClassProperty.KeywordQuery(
            classification_class_id=self._class_infos_by_oid.keys()
        )
        class_prop_codes = set()
        for p in class_props:
            class_prop_codes.add(p.code)
            cls_code = self._class_infos_by_oid[p.classification_class_id]["code"]
            found = False
            for assigned_class, parent_path in parents_by_assigned_class.items():
                if cls_code in parent_path:
                    self._prop_to_assigned_classes[p.code].add(assigned_class)
                    found = True
            if not found:
                pass

        self._properties_with_write_access = set()
        for props_code, class_codes in self._prop_to_assigned_classes.items():
            if not class_codes:
                self._properties_with_write_access.add(props_code)
                continue
            for class_code in class_codes:
                if class_code in self._classes_with_write_access:
                    self._properties_with_write_access.add(props_code)
                    break

    def _property_codes_of_deleted_classes(self):
        """
        Determine the property codes which are obsolete due to deleted classes. This covers also base class
        properties that are not needed anymore.
        """

        assigned_classes = (self._curr_class_codes | self._classes_to_add) - self._classes_to_delete
        property_codes_belonging_only_to_classes = set()
        for property_code, classes_with_this_property in self._prop_to_assigned_classes.items():
            if not classes_with_this_property:
                # skip catalog properties
                continue
            if not classes_with_this_property.intersection(assigned_classes):
                # the property belongs to none of the assigned classes (persistent or transient)
                # therefore all property values can be deleted
                property_codes_belonging_only_to_classes.add(property_code)
        return property_codes_belonging_only_to_classes

    def _add_to_access_control_check(self, property_path):
        path_segments = property_path.split(ClassificationConstants.BLOCK_PATH_SEP)
        property_code = path_segments[0].split(':')[0]
        class_codes = self._prop_to_assigned_classes.get(property_code)
        if class_codes:
            self._classes_for_access_control_check.update(class_codes)

    def _check_access(self):
        denied_classes_codes = []
        for class_code, has_write_access in self._access_info.items():
            if class_code not in self._classes_for_access_control_check:
                continue
            if not has_write_access:
                denied_classes_codes.append(class_code)
        if denied_classes_codes:
            denied_classes_names = ClassificationClass.get_class_names(denied_classes_codes)
            raise ue.Exception(
                "cs_classification_no_permission_for_classes", ",\n".join(denied_classes_names)
            )

    def _diff_class_assignments(self, data):

        assigned_class_codes = set(data.get("assigned_classes", []))
        all_class_codes = assigned_class_codes.union(self._curr_class_codes)

        if not all_class_codes:
            # no classes assigned: set catalog property codes
            self._catalog_prop_codes = set(data["properties"].keys())
            return

        if all_class_codes == self._all_class_codes:
            # no diff calculation needed
            return

        self._all_class_codes = all_class_codes
        self._classes_to_add = assigned_class_codes.difference(self._curr_class_codes)
        if self._full_update_mode:
            self._classes_to_delete = self._curr_class_codes.difference(assigned_class_codes)
        else:
            # remove all non persistent class codes as the do not have to be deleted
            self._classes_to_delete = set(data.get("deleted_classes", [])).intersection(self._curr_class_codes)

        self._class_infos_by_code = ClassificationClass.get_base_class_info_by_code(
            class_codes=all_class_codes, include_given=True
        )
        for _, class_info in self._class_infos_by_code.items():
            self._class_infos_by_oid[class_info["cdb_object_id"]] = class_info

        # remove existing base_class assignments ...
        parents_of_dest_classes = set()
        for code in assigned_class_codes:
            parent_class_code = self._class_infos_by_code[code]["parent_class_code"]
            while parent_class_code:
                parents_of_dest_classes.add(parent_class_code)
                parent_class_code = self._class_infos_by_code[parent_class_code]["parent_class_code"]

        self._classes_to_delete.update(self._curr_class_codes.intersection(parents_of_dest_classes))
        if LOG.isEnabledFor(logging.DEBUG) and self._classes_to_delete:
            LOG.debug("Class codes to delete: {}".format(self._classes_to_delete))

        # don't add baseclasses of existing class assignments
        parents_of_curr_classes = set()
        for code in self._curr_class_codes:
            parent_class_code = self._class_infos_by_code[code]["parent_class_code"]
            while parent_class_code:
                parents_of_curr_classes.add(parent_class_code)
                parent_class_code = self._class_infos_by_code[parent_class_code]["parent_class_code"]
        self._classes_to_add = self._classes_to_add.difference(parents_of_curr_classes)
        if LOG.isEnabledFor(logging.DEBUG) and self._classes_to_add:
            LOG.debug("Class codes to delete: {}".format(self._classes_to_add))

        # initialize access infos
        self._classes_for_access_control_check.update(self._classes_to_delete)
        self._classes_for_access_control_check.update(self._classes_to_add)
        self._access_info = ClassificationData.get_access_info(
            (assigned_class_codes | self._classes_to_delete) - self._classes_to_add,
            obj=self.obj,
            for_create=False,
            add_base_classes=False,
            object_classifications=self._existing_object_classifications
        )
        self._access_info.update(ClassificationData.get_access_info(
            self._classes_to_add, obj=self.obj, for_create=True, add_base_classes=False
        ))
        assigned_classes_with_write_access = set()
        for class_code, has_write_access in self._access_info.items():
            if has_write_access:
                assigned_classes_with_write_access.add(class_code)

        self._classes_with_write_access = set(assigned_classes_with_write_access)
        for code in assigned_classes_with_write_access:
            parent_class_code = self._class_infos_by_code[code]["parent_class_code"]
            while parent_class_code:
                self._classes_with_write_access.add(parent_class_code)
                parent_class_code = self._class_infos_by_code[parent_class_code]["parent_class_code"]

        self._map_properties_to_assigned_classes(data)
        self._catalog_prop_codes = set(data["properties"].keys()).difference(
            set(self._prop_to_assigned_classes.keys())
        )


    def _apply_class_assignments(self):
        classification_changed = False
        if self._classes_to_delete:
            classification_changed = True
            # note: for performance reasons intentionally low level sqlapi
            sqlapi.SQLdelete(
                "from cs_object_classification where ref_object_id='%s' and %s" %
                (self.object_oid, tools.format_in_condition('class_code', self._classes_to_delete))
            )
        if self._classes_to_add:
            dd_classname = self.obj.GetClassname()
            access_rights = ClassificationClass.get_access_rights(
                dd_classname=dd_classname, class_codes= self._classes_to_add
            )
            for class_code in self._classes_to_add:
                classification_changed = True
                olc = None
                status_txt = ""
                if class_code in access_rights:
                    if access_rights[class_code]["access_rights"]:
                        _, _, olc = access_rights[class_code]["access_rights"]
                    else:
                        raise RuntimeError(
                            "Access rights requested for invalid combination of classification class "
                            "and data dictionary class: %s: %s" % (class_code, dd_classname)
                        )
                    if olc:
                        info = StatusInfo(olc, 0)
                        try:
                            status_txt = info.getStatusTxt()
                        except:
                            pass
                # note: for performance reasons intentionally _Create is used, because we don't need the
                # newly created object, which would be constructed and returned bei Create.
                ObjectClassification._Create(
                    ref_object_id=self.object_oid, class_code=class_code,
                    cdb_objektart=olc, status=0, cdb_status_txt=status_txt
                )
        return classification_changed

    def _diff_properties(self, properties, catalog_prop_codes_to_delete):

        for prop_code, prop_values in properties.items():
            property_is_writeable = True
            if prop_code not in self._properties_with_write_access and prop_code not in self._catalog_prop_codes:
                # skip diffing for readonly properties
                property_is_writeable = False
                self._skiped_prop_codes.add(prop_code)
            has_multi_values = len(prop_values) > 1
            for value_pos, prop_value in enumerate(prop_values):
                if has_multi_values:
                    prop_path = "{}:{:03}".format(prop_code, value_pos)
                else:
                    prop_path = "{}".format(prop_code)
                prop_value["value_path"] = prop_path

                if "block" == prop_value["property_type"]:
                    self._diff_block_property_values(
                        prop_path,
                        prop_value,
                        property_is_writeable,
                        has_multi_values)
                else:
                    self._diff_property_value(
                        prop_path,
                        prop_code,
                        prop_value,
                        property_is_writeable,
                        has_multi_values)

        if self._full_update_mode:
            value_ids_to_delete = set(self._existing_value_objects_by_id.keys()).difference(
                self._updated_value_object_ids
            )
            for eav_id in value_ids_to_delete:
                val_obj = self._existing_value_objects_by_id[eav_id]
                self._values_to_delete.append(val_obj)
                self._add_to_access_control_check(val_obj.property_path)
                if LOG.isEnabledFor(logging.DEBUG):
                    LOG.debug(
                        "delete property value: {} - {} - {}".format(
                            self.object_oid, val_obj.property_path, val_obj.value
                        )
                    )
        else:
            # get property codes from deleted classes
            self._properties_to_delete = self._property_codes_of_deleted_classes().union(
                catalog_prop_codes_to_delete
            )

            for value_id, val_obj in self._existing_value_objects_by_id.items():
                delete_value = False
                top_level_prop_code = val_obj.property_path.split('/')[0].split(':')[0]
                if top_level_prop_code in self._properties_to_delete:
                    # delete all property values from deleted_classes
                    delete_value = True
                elif (
                    top_level_prop_code in properties and
                    (
                        top_level_prop_code in self._properties_with_write_access or
                        top_level_prop_code in self._catalog_prop_codes
                    ) and
                    value_id not in self._updated_value_object_ids
                ):
                    # delete all not modified property values with write access
                    delete_value = True

                if delete_value:
                    self._values_to_delete.append(val_obj)
                    self._add_to_access_control_check(val_obj.property_path)
                    if LOG.isEnabledFor(logging.DEBUG):
                        LOG.debug(
                            "delete property value: {} - {} - {}".format(
                                self.object_oid, val_obj.property_path, val_obj.value
                            )
                        )

    def _diff_block_property_values(self,
                                    prop_path,
                                    block_property,
                                    property_is_writeable,
                                    has_multi_values):
        child_prop_values = block_property['value']['child_props']
        for prop_code, prop_values in child_prop_values.items():
            child_has_multivalues = len(prop_values) > 1
            for value_pos, prop_value in enumerate(prop_values):
                if child_has_multivalues:
                    child_prop_path = "{}/{}:{:03}".format(prop_path, prop_code, value_pos)
                else:
                    child_prop_path = "{}/{}".format(prop_path, prop_code)
                prop_value["value_path"] = child_prop_path
                if "block" == prop_value["property_type"]:
                    self._diff_block_property_values(
                        child_prop_path,
                        prop_value,
                        property_is_writeable,
                        has_multi_values or child_has_multivalues)
                else:
                    self._diff_property_value(
                        child_prop_path,
                        prop_code,
                        prop_value,
                        property_is_writeable,
                        has_multi_values or child_has_multivalues)

    def _diff_property_value(self,
                             prop_path,
                             prop_code,
                             prop_value,
                             property_is_writeable,
                             has_multi_values):

        def _diff_eav_entry(prop_type,
                            prop_code,
                            prop_path,
                            value,
                            eav_id,
                            property_is_writeable):

            val_cls = type_map[prop_type]
            args = val_cls.build_value_dict(value)

            if prop_type == 'datetime':
                # micoseconds and timezone is not stored. remove for compare
                date_value = args["datetime_value"]
                if isinstance(date_value, datetime.datetime):
                    date_value = date_value.replace(tzinfo=None)
                    date_value = date_value.replace(microsecond=0)
                args["datetime_value"] = date_value

            value_obj = self._existing_value_objects_by_id.get(eav_id) if eav_id else None
            if value_obj:
                if property_is_writeable:
                    # update
                    args["property_path"] = prop_path

                    # diff args to persistent object to avoid useless db update
                    diffs = False
                    for k, v in args.items():
                        if (k in ["float_value", "float_value_normalized"] and
                                not util.isclose(value_obj[k], v)) or value_obj[k] != v:
                            diffs = True
                            break
                    if diffs:
                        self._add_to_access_control_check(prop_path)
                        self._values_to_update.append((value_obj, args))

                        if LOG.isEnabledFor(logging.DEBUG):
                            LOG.debug(
                                "update property value: {} - {} - {} - {}".format(
                                    self.object_oid, prop_path, value_obj.value, value
                                )
                            )

                self._updated_value_object_ids.add(value_obj.id)
                return value_obj.id
            else:
                value_set = True
                if value is None:
                    value_set = False # NOSONAR
                elif prop_type in ["float", "float_range"] and value["float_value"] is None:
                    value_set = False # NOSONAR
                elif "multilang" == prop_type and value["text_value"] is None:
                    value_set = False # NOSONAR
                top_level_prop_code = prop_path.split('/')[0].split(':')[0]
                if has_multi_values or top_level_prop_code in self._catalog_prop_codes:
                    # always add additional properties and multivalues
                    value_set = True
                if value_set:
                    # add
                    args.update({"id": cdbuuid.create_uuid(),
                                 "ref_object_id": self.object_oid,
                                 "property_code": prop_code,
                                 "property_path": prop_path,
                                 "property_type": prop_type})
                    self._add_to_access_control_check(prop_path)
                    self._values_to_create.append((val_cls, args))

                    if LOG.isEnabledFor(logging.DEBUG):
                        LOG.debug(
                            "add property value: {} - {} - None - {}".format(
                                self.object_oid, prop_path, value
                        )
                    )

        if self.type_conversion and prop_value["value"] is not None:
            self.type_conversion(prop_value)

        prop_type = prop_value["property_type"]
        if prop_type == "datetime" and prop_value["value"] and isinstance(prop_value["value"], str):
            prop_value["value"] = util.convert_datestr_to_datetime(prop_value["value"])
            prop_value["value"] = util.convert_datestr_to_datetime(prop_value["value"])

        if prop_type == "float_range":
            if prop_value["value"]:
                for _, data in prop_value["value"].items():
                    eav_id = data.get("id")
                    _diff_eav_entry(prop_type,
                                    prop_code,
                                    prop_path,
                                    data,
                                    eav_id,
                                    property_is_writeable)
        elif prop_type == "multilang":
            if prop_value["value"]:
                for _, data in prop_value["value"].items():
                    eav_id = data.get("id")
                    _diff_eav_entry(prop_type,
                                    prop_code,
                                    prop_path,
                                    data,
                                    eav_id,
                                    property_is_writeable)
        else:
            eav_id = _diff_eav_entry(
                prop_type,
                prop_code,
                prop_path,
                prop_value["value"],
                prop_value["id"],
                property_is_writeable
            )
            if not prop_value["id"]:
                prop_value["id"] = eav_id

    def _find_floats(self, props, is_inside_block=False):
        for prop_code, prop_values in props.items():
            if not prop_values:
                continue
            for prop_value in prop_values:
                prop_type = prop_value["property_type"]
                if prop_type == "block":
                    self._find_floats(prop_value["value"]["child_props"], is_inside_block=True)
                elif prop_type in ["float", "float_range"]:
                    self._float_props.add((prop_code, is_inside_block))
                    self._float_values.append((prop_code, prop_value))
