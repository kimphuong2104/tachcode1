# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function

import collections
import copy
import datetime
import json
import logging
import os

from cdb import (
    ElementsError, auth, cdbuuid, profiling, sqlapi, transactions, ue, util)
from cdb.lru_cache import lru_cache
from cdb.objects.cdb_file import CDB_File
from cdb.objects.core import ByID
from cdb.objects.org import User
from cs.audittrail import AuditTrailApi
from cs.baselining.support import BaselineTools
from cs.classification import api as classification_api
from cs.classification.util import convert_datestr_to_datetime
from cs.currency import Currency
from cs.requirements_reqif.reqif_export_ng import ReqIFNodes
from cs.tools.semanticlinks import SemanticLink

from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue, rqm_utils
from cs.requirements.classes import (RequirementCategory,
                                     RQMSpecificationCategory)
from cs.requirements.rqm_utils import strip_tags, RQMHierarchicals
from cs.requirements_reqif import ReqIFProfile, reqif_utils, unPrefixID
from cs.requirements_reqif.reqif_parser import ReqIFParser, ReqIFzHandler
from cs.requirements_reqif.reqif_utils import ReqIFBase
import math
from cs.requirements.richtext import RichTextModifications

LOG = logging.getLogger(__name__)


def statement_count():
    stat = sqlapi.SQLget_statistics()
    return stat['statement_count']


class ReqIFMappingError(BaseException):
    pass


class ReqIFImportNG(ReqIFBase):

    DEFAULT_MAPPING_KEY = '###DEFAULT_SPECIFICATION###'

    def __init__(self, specification_mappings, profile, import_file, logger=None, logger_extra_args=None, create_baseline=True):
        """
        ReqIFImport parses a given ReqIF or ReqIFz file and imports its specifications
        and objects with the given profile.
        It checks for existing objects by comparing the reqif_id value and the
        identifier of the reqif object. If a matching object is found the cdb object
        will be updated, otherwise it will be created.
        """
        self.initialization_start = datetime.datetime.now()
        self.statistics = {
            'specifications_created': 0,
            'spec_objects_created': 0,
            'specifications_updated': 0,
            'spec_objects_updated': 0,
            'file_attachments_created': 0,
            'file_attachments_updated': 0,
            'file_attachments_update_not_needed': 0,
            'specifications_skipped': 0,
            'spec_objects_skipped': 0,
            'specifications_update_tried': 0,
            'spec_objects_update_tried': 0,
            'spec_relations_created': 0,
            'spec_relations_updated': 0
        }
        self.logger = logger if logger is not None else LOG
        self.logger_extra = logger_extra_args
        self.create_baseline = create_baseline
        # initialize variables
        self.content_types = {}
        if not specification_mappings:
            self.target_specification_mappings = {}
        else:
            self.target_specification_mappings = specification_mappings
        self.import_file = import_file
        self.binary_files = None
        self.objectList = {}
        self.qualityCharacteristics = []
        self.messages = []
        self.missing_spec_object_mappings = {}
        self.position_number_cache = dict(cdbrqm_spec_object={},
                                          cdbrqm_target_value={})
        self.attribute_definition_cache = None
        # get current user name from cdb
        self.user_name = auth.persno
        self.audit_trail_entries = {
            'create': [],
            'modify': []
        }
        self.missing_attribute_mappings = collections.defaultdict(dict)
        if isinstance(profile, str):
            self.profile = ReqIFProfile.ByKeys(cdb_object_id=profile)
            if not self.profile:
                raise ValueError('Invalid profile object id: %s' % profile)
        else:
            self.profile = profile
        self.parser_result = None
        self.initialization_end = None
        self.last_percentage = 0.0
        self.last_progress_modification = None
        self.specificationsById = None
        self.specObjectsById = None

    def initialize(self):
        ReqIFNodes.register_namespaces()
        self._load_content_types()
        self.mapping_data = self.profile.get_mapping_data()
        self.profile.assertValid(direction='import')
        self.log("info", "Start ReqIF-Import of '%s' with Profile: '%s'" % (self.import_file, self.profile.profile_name))
        self.log("info", "Specification Mappings:\n" +
                 "\n".join(["  (ReqIF ID: {}) -> ({}) ".format(k, v) for (k, v) in self.target_specification_mappings.items()]))

    def init_mappings(self, parser_result):
        # 1. for each spec type in reqif file check whether we have a mapping for it CHECK must be postponed if we only have candidates which we can only use with attribute values
        # 1.a for each spec attribute in spec type with a simple type check whether we have a mapping for it
        # 1.b for each spec attribute in spec type with a complex type check whether we have a mapping for it (enumerations also for each enum values)
        # 2. for each spec object type in reqif file check whether we have a mapping for it
        # 1.a for each spec attribute in spec type with a simple type check whether we have a mapping for it
        # 1.b for each spec attribute in spec type with a complex type check whether we have a mapping for it (enumerations also for each enum values)
        # 3. for each spec relation type in reqif file check whether we have a mapping for it
        entity_mappings_found = 0
        for specification_type_id, specification_type in parser_result.specification_types.items():
            entity_mapping = self.get_specification_mapping(
                ext_specification_type_id=specification_type_id,
                ext_obj_attributes=specification_type
            )
            if entity_mapping:
                entity_mappings_found += 1
            else:
                self.log('warning', 'No mapping for %s', specification_type)
        if entity_mappings_found == 0:
            raise ReqIFMappingError('No specification mapping found in %s - need at least one, check your mapping configuration' % self.profile.GetDescription())
        entity_mappings_found = 0
        for spec_object_type_id, spec_object_type in parser_result.spec_object_types.items():
            entity_mapping = self.get_spec_object_mapping(
                ext_spec_object_type_id=spec_object_type_id,
                ext_obj_attributes=spec_object_type  # must be spec_object_type attributes which currently are in spec_attributes of parser_result
            )
            if entity_mapping:
                entity_mappings_found += 1
            else:
                self.log('warning', 'No mapping for %s', spec_object_type)
        if entity_mappings_found == 0:
            raise ReqIFMappingError('No spec object mapping found in %s - need at least one, check your mapping configuration' % self.profile.GetDescription())

    def _get_entity_mapping(self, **kwargs):
        """ Determines the mapping which should be used.

            Specialized Mappings are preferred over
            Default Mappings (only external id <-> internal entity).
            If more than one specialized mapping would match, the first one is taken.
        """

        ext_obj_type_id = kwargs.get('ext_obj_type_id')
        ext_obj_attributes = kwargs.get('ext_obj_attributes')
        ext_obj_attribute_values = {
            x.get('definition'): x.get('THE-VALUE') for x in ext_obj_attributes.get('values', [])
        }
        obj = kwargs.get('obj')
        if obj:
            # export direction
            raise NotImplementedError('not yet')
        else:
            # import direction
            entity_mappings = self.mapping_data.get('entities').get('import').get(unPrefixID(ext_obj_type_id))
            if not entity_mappings:
                return None  # we do not have something for this ext_obj_type_id
            doors_heading_type_mapping = entity_mappings.get('__doors_heading_type_mapping__')
            if doors_heading_type_mapping and ext_obj_attribute_values:
                chapter_name_value = ext_obj_attribute_values.get(
                    entity_mappings.get('__doors_heading_ReqIF.ChapterName_attribute_id__')
                )
                if chapter_name_value:
                    all_attributes_of_heading_type_in_reqif = self.parser_result.spec_attributes.get(
                        ext_obj_attributes.get('type')
                    ).values()
                    # there must be a ReqIF.Text and ReqIF.ChapterName within that type
                    # as otherwise we do not have to use this heuristic as we have clean
                    # different types and not a mixed type
                    reqif_text_attribute_id = [
                        x for x in all_attributes_of_heading_type_in_reqif
                        if x.get('LONG-NAME') == 'ReqIF.Text'
                    ][0]['IDENTIFIER']
                    if not ext_obj_attribute_values.get(reqif_text_attribute_id):
                        # either not filled or not in the attribute values - then this is a heading
                        return doors_heading_type_mapping
            default_entity_mapping = entity_mappings.get('__default_entity_mapping__')
            entity_mapping = default_entity_mapping
            # special case determine entity mapping due to attribute values (e.g. for ReqMan TypeName attribute)
            conditional_attribute = entity_mappings.get('__conditional_attribute__')
            if conditional_attribute and ext_obj_attributes and conditional_attribute in ext_obj_attribute_values:
                entity_mapping = entity_mappings.get(
                    ext_obj_attribute_values[conditional_attribute],
                    default_entity_mapping
                )
            return entity_mapping

    def get_specification_mapping(self, ext_specification_type_id, ext_obj_attributes):
        return self._get_entity_mapping(ext_obj_type_id=ext_specification_type_id, ext_obj_attributes=ext_obj_attributes)

    def get_spec_object_mapping(self, ext_spec_object_type_id, ext_obj_attributes):
        return self._get_entity_mapping(ext_obj_type_id=ext_spec_object_type_id, ext_obj_attributes=ext_obj_attributes)

    def progress_callback(self, _filepath, _file_percentage, overall_percentage):
        if overall_percentage - self.last_percentage > 0.5:
            now = datetime.datetime.now()
            if self.last_progress_modification is not None:
                duration = (now - self.last_progress_modification).total_seconds()
                eta = (100.0 - overall_percentage) * 2 * duration
                done_date = now + datetime.timedelta(seconds=eta)
                LOG.debug('parsing progress: %4.1f, ETA: %s', overall_percentage, done_date.isoformat())
            else:
                LOG.debug('parsing progress: %4.1f', overall_percentage)
            self.last_progress_modification = now
            self.last_percentage = overall_percentage

    def imp(self):
        with profiling.profile():
            self.initialize()  # fail as early as possible if something is wrong with e.g. the reqif mapping
            hashes = ['md5']
            with ReqIFzHandler(self.import_file, hashes=hashes) as (
                reqif_files, binary_files, extraction_time
            ):
                if len(reqif_files) > 0:
                    self.log(
                        "debug",
                        '%s contain %s reqif files and %s binary files - extraction took %s s' % (
                            self.import_file, len(reqif_files), len(binary_files), extraction_time
                        )
                    )
                    with ReqIFParser(
                        reqif_files=reqif_files,
                        metadata_callback=self.init_mappings,
                        progress_callback=self.progress_callback
                    ) as parser_result:
                        self.parser_result = parser_result
                        self.binary_files = binary_files
                        self.initialization_end = datetime.datetime.now()
                        self.initialization_time = (
                            self.initialization_end - self.initialization_start).total_seconds()
                        self.log('debug', 'Initialization took: %s', self.initialization_time)
                        if len(reqif_files) > 1:
                            raise ElementsError('currently only one .reqif file is supported per .reqifz archive')
                        return self._imp()
                else:
                    raise ValueError('no reqif files found in %s' % self.import_file)

    def set_current_target_specification(self, spec, db_spec_obj):
        self.current_target_specification = None
        self.current_target_specification_tree_ctx = None
        target_spec = self.target_specification_mappings.get(
            spec.get('IDENTIFIER')
        )
        if (
            target_spec and
            db_spec_obj and
            target_spec.cdb_object_id == db_spec_obj.cdb_object_id
        ) or (
            target_spec and
            not db_spec_obj
        ):
            # target_spec will be updated
            self.current_target_specification = target_spec
            self.current_target_specification_tree_ctx = RQMHierarchicals.get_tree_down_context(
                self.current_target_specification, with_file_cache=True
            )
        elif (
            not target_spec and
            not db_spec_obj
        ):
            target_spec = self.target_specification_mappings.get(
                # As now all specs have reqif_ids since their creation
                # a spec with another reqif_id as the spec to be imported
                # can be used with a default key
                self.DEFAULT_MAPPING_KEY
            )
            if target_spec:
                if target_spec.reqif_id_locked == 0:
                    self.current_target_specification = target_spec
                    self.current_target_specification_tree_ctx = RQMHierarchicals.get_tree_down_context(
                        self.current_target_specification, with_file_cache=True
                    )
                    # default spec can only be used once
                    del self.target_specification_mappings[self.DEFAULT_MAPPING_KEY]
                    # an empty spec can only be used once as target for an external
                    # one as it will become the external reqif_id then so it is locked
                    # to that
                    target_spec.reqif_id_locked = 1
                else:
                    raise ue.Exception(
                        "cdbrqm_reqif_reqif_id_already_locked",
                        spec.get('LONG-NAME'),
                        spec.get('IDENTIFIER'),
                        target_spec.GetDescription()
                    )
            else:
                pass  # new spec will be created
        elif (
            target_spec and
            db_spec_obj and
            target_spec.cdb_object_id != db_spec_obj.cdb_object_id
        ):  # mismatch - prevent errors
            ex = ue.Exception("cdbrqm_reqif_imp_err_other_ctx",
                              db_spec_obj.GetClassDef().getDesignation(),
                              db_spec_obj.GetDescription())
            raise ex
        elif (
            not target_spec and
            db_spec_obj
        ):
            # prevent unintentional update
            raise ue.Exception(
                "cdbrqm_reqif_prevent_unintentional_specification_update",
                db_spec_obj.GetDescription(),
                db_spec_obj.reqif_id
            )
        else:
            raise ue.Exception("just_a_replacement", "This should not happen")

    def _createCDBObject(self, entity_mapping, specObject, attributes, parent_object=None, parent_is_spec=False, level=0):
        """
        Creates a new CDB object for given classname with given attributes.
        """
        classname = entity_mapping.internal_object_type
        parent_object_id = ""
        if parent_object is not None and (not parent_is_spec or classname == TargetValue.__classname__):
            parent_object_id = parent_object.cdb_object_id
        # target value specification is only a virtual object
        if classname == TargetValue.__classname__ and parent_object_id == "":
            raise ue.Exception('just_a_replacement', 'Found invalid Target Value without a parent.')
        args, classification_data = self._createCdbAttributesList(entity_mapping, attributes, level=level)
        if 'cdb_object_id' not in args:
            # ensure baselining compatibility
            args['cdb_object_id'] = cdbuuid.create_uuid()
            args['ce_baseline_object_id'] = args['cdb_object_id']
            args['ce_baseline_origin_id'] = cdbuuid.create_uuid()
        # if no args found, try long_name, desc or identifier
        if len(args) == 0:
            if specObject['LONG-NAME']:
                args["name"] = specObject['LONG-NAME']
            elif specObject['DESC']:
                args["name"] = specObject['DESC']
            else:
                args["name"] = specObject['IDENTIFIER']
        # prepare attributes for cdb
        args['reqif_id'] = specObject.get('IDENTIFIER')
        # parent object id and specification_object_id are not relevant for target values
        if not (classname in (TargetValue.__classname__, RQMSpecification.__classname__)):
            args['parent_object_id'] = parent_object_id
            args['specification_object_id'] = self.current_target_specification.cdb_object_id
            # preserve external authors
            if 'authors' not in args or not args['authors']:
                user = User.ByKeys(self.user_name)
                if user is not None:
                    args['authors'] = user.login
                else:
                    args['authors'] = auth.get_login()
        if classname == TargetValue.__classname__:
            args['requirement_object_id'] = parent_object_id
            args['specification_object_id'] = self.current_target_specification.cdb_object_id
        if classname == RQMSpecObject.__classname__:
            # set mandatory fields if not available
            if 'specobject_id' not in args.keys():
                # check for mandatory specobject_id
                req_id, maxno = RQMSpecObject.makeNumber()
                args['specobject_id'] = req_id
                args['maxno'] = maxno
            if 'currency' not in args.keys():
                args['currency'] = Currency.getDefaultCurrency().cdb_object_id
            if 'category' not in args.keys() and RequirementCategory.getDefaultCategory() is not None:
                args['category'] = RequirementCategory.getDefaultCategory().name
        if classname == RQMSpecification.__classname__:
            args['status'] = 0
            args['cdb_objektart'] = RQMSpecification.__classname__
            if 'category' not in args.keys() and RQMSpecificationCategory.get_default_category() is not None:
                args['category'] = RQMSpecificationCategory.get_default_category().name
            if 'spec_id' not in args.keys():
                # check for mandatory specobject_id
                req_id, maxno = RQMSpecification.makeNumber()
                args['spec_id'] = req_id
                args['maxno'] = maxno
            if 'revision' not in args.keys():
                args["revision"] = 0

        self.log("debug", level * 2 * " " + "Create Object '%s' with Attributes: '%s'" % (classname, args))
        objResult, qc = reqif_utils._cdb_op("Create", classname, None, args, importer=self, level=level)
        if objResult:
            self.log("debug", level * 2 * " " + "Object created : %s" % objResult)
            # save object in global list
            self.objectList[specObject['IDENTIFIER']] = {
                "cdb_object_id": objResult.cdb_object_id,
                "classname": classname}
            if qc:
                # save qc object for later calculation
                self.qualityCharacteristics.append(qc)
            if classification_data is not None:
                classification_api.update_classification(
                    objResult,
                    classification_data,
                    type_conversion=self._convert_classification_values,
                    full_update_mode=False
                )
            self.log(
                "debug",
                level * 2 * " " + "Object created : %s\nAttributes:%s\nClassification:%s" % (
                    objResult,
                    dict(args) if args is not None else None,
                    classification_data
                )
            )
        else:
            message = util.get_label("cdbrqm_reqif_obj_create_failed") % (specObject['IDENTIFIER'], objResult)
            self.log("error", level * 2 * " " + message)
            self.messages.append({
                'message': message,
                'level': 'error'
            })

        return objResult

    def _convert_classification_values(self, json_prop_value_dict):
        if json_prop_value_dict["property_type"] == 'datetime' and json_prop_value_dict["value"]:
            if not isinstance(json_prop_value_dict["value"], datetime.datetime):
                json_prop_value_dict["value"] = convert_datestr_to_datetime(json_prop_value_dict["value"]).replace(tzinfo=None)
            else:
                json_prop_value_dict["value"] = json_prop_value_dict["value"].replace(tzinfo=None)

    def _createSubElements(self, cdbParentObject, parsedObject, parent_is_spec=False, level=0):
        """
        Iterates recursively through hierarchy and creates the sub elements.
        """

        # hierarchy
        hierarchies = self.parser_result.spec_hierarchy_tree.get(parsedObject['IDENTIFIER'], [])
        for hier_id in hierarchies:
            hier = self.parser_result.spec_hierarchies[hier_id]
            self.log("debug", level * 2 * " " + "Hierarchy-Node: '%s' - '%s'" % (hier_id, hier.get('DESC', '')))
            hier_obj = self.parser_result.spec_hierarchies[hier_id]['object']
            if hier_obj:
                self.log("debug", level * 2 * " " + "Hierarchy-Obj: '%s'" % (hier_obj))
                # get spec object
                spec_object = self.parser_result.spec_objects[hier_obj]
                if spec_object:
                    spec_object_type_id = unPrefixID(str(spec_object['type']))
                    entity_mapping = self.get_spec_object_mapping(spec_object_type_id, spec_object)
                    if entity_mapping:
                        # TODO: add warning for too long values
                        # type mapping vorhanden
                        self.log("debug", level * 2 * " " + "Type-Mapping found: '%s' - '%s'" % (spec_object_type_id, entity_mapping))
                        source_cdb_object = entity_mapping.get_objects_by_reqif_id(
                            reqif_id=spec_object['IDENTIFIER'],
                            revision_key_attr='specification_revision',
                            max_revision=self.current_target_specification.revision
                        )
                        result_cdb_object = None
                        if source_cdb_object:
                            # spec-object existiert bereits -> Aktualisierung
                            self.log("debug", level * 2 * " " + "Spec-Object '%s'-'%s' already exists -> Update"
                                     % (source_cdb_object.name, source_cdb_object.reqif_id))
                            result_cdb_object = self._updateCDBObject(entity_mapping, source_cdb_object, spec_object, spec_object, level=level)
                            if result_cdb_object is not False:
                                self.statistics['spec_objects_updated'] += 1
                            else:
                                self.statistics['spec_objects_update_tried'] += 1
                        else:
                            # spec-object existiert noch nicht -> Neuanlage
                            self.log("debug", level * 2 * " " + "Spec-Object does not exist -> Create")
                            result_cdb_object = self._createCDBObject(entity_mapping, spec_object, spec_object, cdbParentObject, parent_is_spec, level=level)
                            self.statistics['spec_objects_created'] += 1
                        if result_cdb_object:
                            self._createSubElements(result_cdb_object, hier, level=level + 1)
                        elif source_cdb_object and result_cdb_object is False:  # update case when no update is needed
                            self._createSubElements(source_cdb_object, hier, level=level + 1)
                        else:
                            message = util.get_label("cdbrqm_reqif_err_specobj_import_failed") % (
                                spec_object_type_id,
                                spec_object['LONG-NAME'],
                                spec_object['DESC']
                            )
                            message_detailed = util.get_label("cdbrqm_reqif_err_specobj_import_failed_detailed") % (
                                spec_object_type_id,
                                spec_object['LONG-NAME'],
                                spec_object['DESC'],
                                spec_object
                            )
                            self.log("error", level * 2 * " " + message_detailed)
                            self.messages.append({
                                "message": message,
                                "level": "error"
                            })
                    else:
                        # kein type mapping vorhanden
                        if spec_object_type_id not in self.missing_spec_object_mappings:
                            self.missing_spec_object_mappings[spec_object_type_id] = 1
                            message = util.get_label("cdbrqm_reqif_err_specobj_import_failed_typemapping") % (
                                spec_object_type_id,
                                '>=1'
                            )
                            self.log("warning", level * 2 * " " + message)
                        else:
                            self.missing_spec_object_mappings[spec_object_type_id] += 1
                        self.statistics["spec_objects_skipped"] += 1
        return None

    def _updateClassification(self, cdbObject, classification_data):
        if classification_data is not None:
            classification_api.update_classification(
                cdbObject,
                classification_data,
                type_conversion=self._convert_classification_values,
                full_update_mode=True
            )

    def _updateCDBObject(self, entity_mapping, cdbObject, specObject, attributes, level=0):
        """
        Updates an existing object by given spec object.
        """
        self.log("debug", level * 2 * " " + "Update cdbObject: '%s'" % cdbObject)
        classname = cdbObject.GetClassname()
        reqif_id = specObject['IDENTIFIER']
        args, classification_data = self._createCdbAttributesList(
            entity_mapping, attributes, level=level, obj=cdbObject
        )
        args['reqif_id'] = reqif_id
        if cdbObject.reqif_id and reqif_id != cdbObject.reqif_id:
            if not isinstance(cdbObject, RQMSpecification):
                raise Exception('ReqIF ID must not be altered, only allowed exception is for specifications in special conditions')
            else:
                LOG.warn('ReqIF ID adjusted from %s to %s', cdbObject.reqif_id, reqif_id)
        self.log("debug", level * 2 * " " + "Update CDB-Object '%s' with Attributes: '%s'" % (cdbObject, args))
        objResult, qc = reqif_utils._cdb_op(
            "Update", classname, cdbObject, args, level=level, importer=self
        )

        if cdbObject:
            # save object in global list
            self.objectList[reqif_id] = {
                "cdb_object_id": cdbObject.cdb_object_id,
                "classname": classname
            }

        # Update method of object framework returns None in case of success
        if objResult is None:
            if qc:
                # save qc object for later calculation
                self.qualityCharacteristics.append(qc)
            self._updateClassification(cdbObject, classification_data)
            self.log(
                "info",
                level * 2 * " " + "Object updated : %s\nAttributes:%s\nClassification:%s" % (
                    cdbObject,
                    dict(attributes) if attributes is not None else None,
                    classification_data
                )
            )
            return cdbObject
        elif objResult is False:
            obj_desc = cdbObject.GetDescription()
            self.log(
                "debug",
                level * 2 * " " + "Object update not needed : %s" % (
                    cdbObject
                )
            )
            # unchanged metadata of an object does not imply
            # that the classification was not changed.
            self._updateClassification(cdbObject, classification_data)
            return objResult
        else:
            obj_desc = cdbObject.GetDescription() if cdbObject else reqif_id
            message = util.get_label("cdbrqm_reqif_obj_update_failed") % (obj_desc, objResult)
            self.log("error", level * 2 * " " + message)
            self.messages.append({
                'message': message,
                'level': 'error'
            })
            return objResult

    @lru_cache()
    def _get_object_data_replacements(self):
        replacements = {}
        for data_url in self.parser_result.object_references.keys():
            replacements[str('data="{}').format(data_url)] = str('data="{}').format(os.path.basename(data_url))
        return replacements

    def _adjust_object_data(self, the_value):
        replacements = self._get_object_data_replacements()
        new_value = rqm_utils.multireplace(the_value, replacements)
        new_value = RichTextModifications.remove_variables(new_value, remove_only_values=True)
        return new_value

    def _createCdbAttributesList(self, entity_mapping, attributes, level=0, obj=None):
        """
        Receives an attribute list from reqif file and returns a converted
        attribute list by mapping the external to internal attribute names with
        defined mapping rules.
        """
        content_types = self.content_types[entity_mapping.internal_object_type]
        args = {}
        classification_data = None

        class_codes_list = entity_mapping.ClassificationClasses.code
        if class_codes_list:
            if classification_data is None and obj is None:
                classification_data = classification_api.get_new_classification(class_codes_list)
            elif classification_data is None and obj is not None:
                classification_data = classification_api.get_classification(obj)
                classification_data = classification_api.rebuild_classification(classification_data, class_codes_list)
            else:
                pass  # classification_data is already present
            properties_data = classification_data.get('properties')

        # pre initialize the static values so that they are used even if they are not within the transferred fields
        for mapping_attr in self.mapping_data.get('attributes')[entity_mapping.cdb_object_id].values():
            if mapping_attr.static_internal_field_value:
                args[mapping_attr.internal_field_name] = mapping_attr.static_internal_field_value

        for attr in attributes.get('values'):
            mapping_attribute = self.mapping_data.get('attributes')[entity_mapping.cdb_object_id].get(attr['definition'])
            attribute_definition = self.parser_result.spec_attributes[attributes['type']][attr['definition']]
            attribute_base_type = self.parser_result.data_types[attribute_definition['type']]['type']
            if mapping_attribute:
                if mapping_attribute.is_reference_link:
                    continue  # reference links are readonly for navigation purposes for imports we do not need them
                elif mapping_attribute.is_property:
                    enum_cache = self.mapping_data.get('enums')[mapping_attribute.external_identifier]
                    new_values = []
                    # dummy_value is our copy base - it is present as the classification APIs ensure that
                    dummy_value = dict(properties_data[mapping_attribute.internal_field_name][0])
                    if 'THE-VALUE' in attr:
                        value_list = attr['THE-VALUE'] if isinstance(attr['THE-VALUE'], list) else [attr['THE-VALUE']]
                    else:
                        value_list = [attr['values']]
                    for value in value_list:
                        new_value = copy.deepcopy(dummy_value)
                        if mapping_attribute.data_type == 'enumeration':
                            for enum_val_ref in value:
                                new_value = copy.deepcopy(dummy_value)
                                new_value['id'] = None
                                raw_value = self.parser_result.data_type_enum_values[attribute_definition.get('type')][enum_val_ref]['LONG-NAME']
                                raw_value = enum_cache.get(raw_value, {'value': raw_value})['value']
                                if isinstance(dummy_value.get('value'), dict) and 'float_value' in dummy_value.get('value'):
                                    new_value['value']['float_value'] = float(raw_value)
                                else:
                                    new_value['value'] = raw_value
                                new_values.append(new_value)
                        else:
                            if isinstance(dummy_value.get('value'), dict) and 'float_value' in dummy_value.get('value'):
                                new_value['value']['float_value'] = value
                            elif attribute_base_type == 'xhtml':
                                # strip xhtml
                                self.log("warning", 2 * 2 * " " + "Converting XHTML to plain text -> possible loss of information.")
                                new_value['value'] = strip_tags(value)
                            else:
                                new_value['value'] = value
                            new_values.append(new_value)
                    properties_data[mapping_attribute.internal_field_name] = new_values
                elif mapping_attribute.static_internal_field_value:  # if a static value is given use it
                    args[mapping_attribute.internal_field_name] = mapping_attribute.static_internal_field_value
                else:
                    # add cdb attribute and value
                    content_type = content_types.get(mapping_attribute.internal_field_name)
                    if content_type == 'XHTML' and attribute_base_type == 'string':
                        args[mapping_attribute.internal_field_name] = "<xhtml:div>{}</xhtml:div>".format(attr['THE-VALUE'])
                    else:
                        if isinstance(attr['THE-VALUE'], float) and math.isnan(attr['THE-VALUE']):
                            args[mapping_attribute.internal_field_name] = None
                        elif content_type == 'XHTML' and attribute_base_type == 'xhtml':
                            # shorten data url
                            args[mapping_attribute.internal_field_name] = self._adjust_object_data(
                                attr['THE-VALUE']
                            )
                        elif content_type != 'XHTML' and attribute_base_type == 'xhtml':
                            # strip xhtml
                            self.log("warning", 2 * 2 * " " + "Converting XHTML to plain text -> possible loss of information.")
                            args[mapping_attribute.internal_field_name] = strip_tags(
                                attr['THE-VALUE']
                            )
                        else:
                            args[mapping_attribute.internal_field_name] = attr['THE-VALUE']

                self.log("debug", level * 2 * " " + "Attribute-Mapping found: external id: '%s' (long name: '%s') -> internal: '%s'"
                         % (mapping_attribute.external_identifier, mapping_attribute.external_field_name, mapping_attribute.internal_field_name))
            else:
                # kein mapping attribut gefunden -> Attribut wird ignoriert
                self.log("debug", level * 2 * " " + u"Mapping-Attribute not found for '%s' -> will be skipped."
                         % attribute_definition['LONG-NAME'])
                self.missing_attribute_mappings[entity_mapping.cdb_object_id][attribute_definition['IDENTIFIER']] = attribute_definition['LONG-NAME']
        return args, classification_data

    def _create_relations(self):
        """
        Iterates through all spec relations and creates these relations.
        """
        self.log("info", u"Importing Relations")

        # check if relations are available
        if not self.parser_result.spec_relations:
            self.log("warning", u"Import Document does not contain relations!")
            return None

        self.log("debug", "self.objectList: '%s' ", self.objectList)
        for spec_relation_id, spec_relation in self.parser_result.spec_relations.items():
            spec_relation_type = self.parser_result.spec_relation_types[spec_relation['type']]
            source_object = self.parser_result.spec_objects.get(spec_relation['source'])
            if not source_object:
                # check if source object is a specification node
                source_object = self.parser_result.specifications.get(spec_relation['source'])
                if not source_object:
                    self.log("error", u"Source Object not found -> Relation could not be created!")
                    break
            target_object = self.parser_result.spec_objects.get(spec_relation['target'])
            if not target_object:
                # check if target object is a specification node
                target_object = self.parser_result.specifications.get(spec_relation['target'])
                if not target_object:
                    # ignore open ends for relations
                    self.log("warning", u"Target Object not found -> Relation could not be created!")
                    continue
            source_reqif_id = source_object['IDENTIFIER']
            target_reqif_id = target_object['IDENTIFIER']
            self.log("debug", "Imported Relation '%s - %s, Type: %s - %s' between '%s' - '%s'"
                     % (spec_relation_id,
                        spec_relation.get('LONG_NAME', ''),
                        spec_relation['type'],
                        spec_relation_type.get('LONG_NAME', ''),
                        source_reqif_id,
                        target_reqif_id
                        ))

            cdb_spec_rel_type = None
            if (
                source_reqif_id in self.objectList.keys() and
                target_reqif_id in self.objectList.keys()
            ):

                self.log("debug", "Relation: Source '%s' and Target '%s' Objects are present"
                         % (source_object.get('LONG_NAME', ''), target_object.get('LONG-NAME', '')))

                cdb_source_object = self.objectList[source_reqif_id]
                cdb_target_object = self.objectList[target_reqif_id]

            cdb_spec_rel_type = self.mapping_data['relations'].get(spec_relation_type['IDENTIFIER'])
            if cdb_spec_rel_type:
                # check if relation already exists
                link = SemanticLink.ByKeys(
                    subject_object_id=cdb_source_object["cdb_object_id"],
                    object_object_id=cdb_target_object["cdb_object_id"]
                )
                if link:
                    # # update relation
                    link.Update(link_type_object_id=cdb_spec_rel_type.link_type_object_id)
                    self.statistics['spec_relations_updated'] += 1
                else:
                    # create relation
                    link = SemanticLink.Create(
                        subject_object_id=cdb_source_object["cdb_object_id"],
                        object_object_id=cdb_target_object["cdb_object_id"],
                        link_type_object_id=cdb_spec_rel_type.link_type_object_id,
                        subject_object_classname=cdb_source_object["classname"],
                        object_object_classname=cdb_target_object["classname"],
                    )
                    if link:
                        self.statistics['spec_relations_created'] += 1
                        link.generateMirrorLink(
                            cdb_source_object["classname"], cdb_target_object["classname"]
                        )
                if link:
                    self.log("info", "Relation created or updated: '%s'" % link)
                else:
                    message = util.get_label("cdbrqm_reqif_err_create_or_update_relation") % (
                        link, cdb_spec_rel_type
                    )
                    self.log("error", message)
                    self.messages.append({
                        "message": message,
                        "level": "error"
                    })
            else:
                # kein RelationType-Mapping gefunden
                self.messages.append({
                    "message": util.get_label("cdbrqm_reqif_err_no_reltypemapping_found") % (
                        spec_relation['IDENTIFIER'], spec_relation.get('LONG_NAME', '')
                    ),
                    "level": "error"
                })
                continue  # next relation

    def _upload_binary_files(self):
        self.log("debug", "Referenced File Attachments: %s" % self.parser_result.object_references.keys())
        db_files_cache = self.current_target_specification_tree_ctx.get('file_cache') if self.current_target_specification_tree_ctx is not None else {}
        for data_ref, data_details in self.parser_result.object_references.items():
            if data_ref in self.binary_files:
                previous_db_file_obj = None
                for data_detail in data_details:
                    obj_id = self.objectList[data_detail.get('spec_object_id')]['cdb_object_id']
                    binary_file = self.binary_files[data_ref]
                    path = binary_file['path']
                    file_hash = binary_file['hashes']['md5']
                    file_size = binary_file['size']
                    fname = os.path.basename(path)
                    ftype = reqif_utils._get_filetype(fname=fname, object_tag_details=data_detail)
                    additional_args = {"cdbf_name": fname,
                                       "cdbf_type": ftype.getName()}
                    cdb_file_obj = None
                    if db_files_cache:
                        cdb_file_objs = [x for x in db_files_cache.get(obj_id, []) if x.cdbf_name == fname]
                        if cdb_file_objs:
                            cdb_file_obj = cdb_file_objs[0]
                    if cdb_file_obj:
                        # update the previously file in db but only if needed (hash differs)
                        hash_to_import = u'md5:{file_hash}'.format(file_hash=file_hash)
                        if (
                            cdb_file_obj.cdbf_fsize == file_size and
                            cdb_file_obj.cdbf_hash and cdb_file_obj.cdbf_hash == hash_to_import
                        ):
                            self.statistics['file_attachments_update_not_needed'] += 1
                        else:
                            cdb_file_obj.checkin_file(
                                from_path=path,
                                additional_args=additional_args)
                            self.statistics['file_attachments_updated'] += 1
                    elif previous_db_file_obj is not None:
                        # was already uploaded/updated we just need a logical copy
                        previous_db_file_obj.Copy(cdbf_name=fname)
                        self.statistics['file_attachments_created'] += 1
                    else:
                        # was not uploaded before
                        cdb_file_obj = CDB_File.NewFromFile(
                            for_object_id=obj_id, from_path=path, primary=True,
                            additional_args=additional_args)
                        self.statistics['file_attachments_created'] += 1
                    if previous_db_file_obj is None:
                        previous_db_file_obj = cdb_file_obj
            else:
                self.log("error", "Referenced File Attachment '%s' does not exist source file" % data_ref)

    def _imp(self):
        """
        This method imports the parsed reqif structure. The found specifications
        will be created or updated as cdb objects (requirements,
        target values) with the given attributes.
        """
        # sqlapi.SQLselect('1 -- ReqIF Import start')
        start_sql_cnt = statement_count()
        start = datetime.datetime.now()
        self.specificationsById = self.parser_result.specifications
        self.specObjectsById = self.parser_result.spec_objects
        with transactions.Transaction():
            if not self.parser_result.specifications:
                raise ue.Exception("cdbrqm_reqif_no_specification_found")
            for spec_reqif_id, spec in self.parser_result.specifications.items():
                db_entity_classname = None
                LOG.info('test: %s', spec)
                spec_type_id = unPrefixID(spec.get('type'))
                entity_mapping = self.get_specification_mapping(
                    ext_specification_type_id=spec_type_id,
                    ext_obj_attributes=spec
                )
                if entity_mapping:
                    # TODO: add warnings for too long values
                    db_entity_classname = entity_mapping.internal_object_type
                    self.log(
                        "debug", "Type-Mapping found: '%s' - '%s'" % (
                            spec_type_id, entity_mapping)
                    )
                    db_spec_obj = entity_mapping.get_objects_by_reqif_id(
                        reqif_id=spec_reqif_id,
                        revision_key_attr='revision'
                    )
                    result_db_spec_obj = None

                    self.set_current_target_specification(spec, db_spec_obj)
                    self.log("debug", "Importing Specification '%s - %s - %s' ..."
                             % (spec.get('LONG-NAME'), spec.get('DESC'), spec_reqif_id))

                    if self.current_target_specification:
                        if not self.current_target_specification.CheckAccess('save'):
                            raise ue.Exception(
                                'just_a_replacement',
                                'Failed to import Specification (%s) due to missing Permissions' % self.current_target_specification.GetDescription()
                            )
                        if db_spec_obj:
                            self.log("debug", "Specification '%s'-'%s' does already exist -> Update"
                                     % (self.current_target_specification.name,
                                        self.current_target_specification.reqif_id))
                        else:
                            self.log("debug", "Specification does not exist but Target Specification was specified -> Update and continue")
                        if self.create_baseline:
                            self.log("info", "Creating baseline")
                            start_baseline_sql_cnt = statement_count()
                            start_baseline = datetime.datetime.now()
                            # sqlapi.SQLselect('1 -- Baselining start')
                            BaselineTools.create_baseline(
                                obj=self.current_target_specification,
                                name='ReqIF Import Baseline',
                                comment='Baseline created before ReqIF Import of {}: {} (ReqIF ID: {}).'.format(
                                    spec['LONG-NAME'],
                                    spec.get('DESC') if spec.get('DESC') is not None else '',
                                    spec['IDENTIFIER']
                                ),
                                system=True
                            )
                            stop_baseline = datetime.datetime.now()
                            stop_baseline_sql_cnt = statement_count()
                            # sqlapi.SQLselect('1 -- Baselining end')
                            self.log(
                                "debug",
                                "Baseline created took: %s and %d statements",
                                    (stop_baseline - start_baseline).total_seconds(),
                                    (stop_baseline_sql_cnt - start_baseline_sql_cnt)
                            )
                        result_db_spec_obj = self._updateCDBObject(
                            entity_mapping,
                            self.current_target_specification,
                            spec,
                            spec
                        )
                        if result_db_spec_obj is not False:
                            self.statistics['specifications_updated'] += 1
                        else:
                            self.statistics['specifications_update_tried'] += 1
                    else:
                        self.log("info", "Specification does not exist -> Create")
                        result_db_spec_obj = self._createCDBObject(entity_mapping, spec, spec)
                        self.target_specification_mappings[result_db_spec_obj.reqif_id] = result_db_spec_obj
                        self.set_current_target_specification(spec, result_db_spec_obj)
                        self.statistics['specifications_created'] += 1

                    if result_db_spec_obj and self.current_target_specification:
                        parent_is_specification = True if db_entity_classname not in [RQMSpecObject.__classname__] else False
                        self._createSubElements(result_db_spec_obj, spec, parent_is_specification, level=1)
                        if isinstance(result_db_spec_obj, RQMSpecification):
                            # Calculate our table sort order
                            result_db_spec_obj.update_sortorder()
                            result_db_spec_obj.adjust_fulfillment_kpi_active()
                    elif self.current_target_specification and result_db_spec_obj is False:
                        parent_is_specification = True if db_entity_classname not in [RQMSpecObject.__classname__] else False
                        self._createSubElements(self.current_target_specification, spec, parent_is_specification, level=1)
                        if isinstance(self.current_target_specification, RQMSpecification):
                            # Calculate our table sort order
                            self.current_target_specification.update_sortorder()
                            self.current_target_specification.adjust_fulfillment_kpi_active()
                    else:
                        raise ue.Exception(
                            "just_a_replacement",
                            "Failed to import Specification"
                        )
                else:
                    # kein type mapping vorhanden
                    message = util.get_label("cdbrqm_reqif_err_spec_import_failed") % (
                        spec_type_id, spec.get('LONG-NAME'), spec.get('DESC'))
                    self.log("warning", message)
                    self.messages.append({
                        "message": message,
                        "level": "warning"
                    })
                    self.statistics['specifications_skipped'] += 1
            for entity_type_id, count in self.missing_spec_object_mappings.items():
                message = util.get_label("cdbrqm_reqif_err_specobj_import_failed_typemapping") % (
                    entity_type_id,
                    count
                )
                self.log("warning", message)
                self.messages.append({
                    "message": message,
                    "level": "warning"
                })
            if (
                self.statistics['specifications_created'] +
                self.statistics['specifications_updated'] +
                self.statistics['specifications_update_tried']
            ) == 0:
                message = util.get_label("cdbrqm_reqif_err_nothing_imported") % (
                    "\n".join(
                        [
                            "{level}: {message}".format(
                                level=m.get('level').upper(),
                                message=m.get('message')
                            ) for m in self.messages
                        ]
                    )
                )
                raise ue.Exception("just_a_replacement", message)
            # create relations
            self._create_relations()
            self._upload_binary_files()

            audit_trail_api = AuditTrailApi()
            for k, v in self.audit_trail_entries.items():
                try:
                    if v:  # if nothing is changed do not track anything
                        audit_trail_api.createAuditTrailsWithDetails(
                            category=k,
                            objs=v,
                            longtext_stripper=strip_tags
                        )
                except BaseException as e:
                    LOG.exception(e)
            self.log("info", "ReqIF Import completed.")
        if self.missing_attribute_mappings:
            for entity_mapping_id, missing_attr in self.missing_attribute_mappings.items():
                self.log('info', 'Found missing attribute mappings for: %s', ByID(entity_mapping_id).GetDescription())
                for missing_attr_identifier, missing_attr_longname in missing_attr.items():
                    self.log('info',
                             "  No attribute mapping found for '%s' (%s) -> skipped.",
                             missing_attr_identifier,
                             missing_attr_longname
                             )
        self.log("info", "Statistics: %s", json.dumps(self.statistics, indent=4, ensure_ascii=False))
        stop = datetime.datetime.now()
        stop_sql_cnt = statement_count()
        # sqlapi.SQLselect('1 -- ReqIF Import stop')
        self.log(
            'debug', 'Import took: %s and %d statements',
            (stop - start).total_seconds(),
            (stop_sql_cnt - start_sql_cnt)
        )
        return self.messages


if __name__ == "__main__":
    import sys

    def _configure_stdout_logger():
        logger = logging.getLogger(__name__ + ".output")
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(fmt="%(levelname)s %(message)s", datefmt="")
        handler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        return logger

    if len(sys.argv) == 2:
        import_file = sys.argv[1]
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG({}, profile, import_file, logger=_configure_stdout_logger())
        importer.imp()
    elif len(sys.argv) > 2:
        import_file = sys.argv[1]
        profile = ReqIFProfile.ByKeys(profile_name=sys.argv[2])
        importer = ReqIFImportNG({}, profile, import_file, logger=_configure_stdout_logger())
        importer.imp()
