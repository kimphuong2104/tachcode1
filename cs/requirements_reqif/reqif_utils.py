# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

import collections
import datetime
import logging
import os

from lxml import etree
from lxml.etree import DocumentInvalid, XMLSchema, XMLSyntaxError

from cdb import i18n, ue
from cdb.objects.core import ClassRegistry
from cdbwrapc import getFileTypeByFilename, getFileTypesByFilename
from cs.requirements import (RQMSpecification, RQMSpecObject, TargetValue,
                             rqm_utils)
from cs.requirements_reqif import ReqIFProfile
from cs.requirements_reqif.exceptions import ReqIFValidationError

LOG = logging.getLogger(__name__)


class ReqIFBase(object):

    def log(self, level_func, *args, **kwargs):
        kwargs = kwargs.copy()
        if 'extra' not in kwargs:
            kwargs['extra'] = self.logger_extra
        getattr(self.logger, level_func)(*args, **kwargs)

    def _load_content_types(self):
        self.content_types[RQMSpecification.__classname__] = rqm_utils.get_content_types_by_classname(RQMSpecification.__classname__)
        self.content_types[RQMSpecObject.__classname__] = rqm_utils.get_content_types_by_classname(RQMSpecObject.__classname__)
        self.content_types[TargetValue.__classname__] = rqm_utils.get_content_types_by_classname(TargetValue.__classname__)

    def _load_mapping_information(self, profile):
        self.log("info", "Load Mapping Informationen")
        if isinstance(profile, str):
            self.profile = ReqIFProfile.ByKeys(cdb_object_id=profile)
        else:
            self.profile = profile
        self.mapping_entities_by_internal_object_type = collections.defaultdict(list)
        self.mapping_entities_by_external_object_type = collections.defaultdict(list)
        self.mapping_attributes_by_entity_mapping = collections.defaultdict(dict)
        last_internal = []
        last_external = []
        profiles = self.profile.Entities.Execute()
        for x in profiles:
            if not x.object_type_field_name:
                last_internal.append(x)
            else:
                self.mapping_entities_by_internal_object_type[x.internal_object_type].append(x)
            if not x.ext_object_type_field_name:
                last_external.append(x)
            else:
                self.mapping_entities_by_external_object_type[x.external_object_type].append(x)

        # ensure that the default mapping is the last option and specialized mappings are preferred
        if last_internal:
            for last in last_internal:
                self.mapping_entities_by_internal_object_type[last.internal_object_type].append(last)
        if last_external:
            for last in last_external:
                self.mapping_entities_by_external_object_type[last.external_object_type].append(last)

        for attr in self.profile.AllAttributes.Execute():
            self.mapping_attributes_by_entity_mapping[attr.entity_object_id][attr.external_identifier] = attr
        self.cdbDataTypes = set(self.profile.AllAttributes.data_type)
        self.mapping_relation_types = self.profile.RelationTypes.Execute()
        self.log("info", "Mapping Profile: %s (%s)", self.profile.profile_name, self.profile.cdb_object_id)
        for candidates in self.mapping_entities_by_external_object_type.values():
            for entity in candidates:
                self.log("info", "  Mapping Entity: %s (%s/%s) - %s (%s/%s)",
                         entity.internal_object_type,
                         entity.object_type_field_name,
                         entity.object_type_field_value,
                         entity.external_object_type,
                         entity.ext_object_type_field_name,
                         entity.ext_object_type_field_value)
                for attr in self.mapping_attributes_by_entity_mapping[entity.cdb_object_id].values():
                    self.log("info", "    Mapping Entity Attribute: %s - %s (%s)",
                             attr.internal_field_name, attr.external_identifier, attr.external_field_name)
        for rel_type in self.mapping_relation_types:
            self.log("info", "  Mapping Relation Type: %s - %s",
                     rel_type.link_name,
                     rel_type.external_link_type)

    def _get_entity_mapping(self, **kwargs):
        """ Determines the mapping which should be used.

            Specialized Mappings are preferred over
            Default Mappings (only external id <-> internal entity).
            If more than one specialized mapping would match, the first one is taken.
        """

        ext_obj_type_id = kwargs.get('ext_obj_type_id')
        ext_obj_attributes = kwargs.get('ext_obj_attributes', {})
        obj = kwargs.get('obj')
        if obj:
            # export direction
            candidates = self.mapping_entities_by_internal_object_type.get(obj.GetClassname())

            def candidate_checker(candidate):
                if not candidate.object_type_field_name or (getattr(obj, candidate.object_type_field_name) == candidate.object_type_field_value):
                    return candidate

        else:
            # import direction
            candidates = self.mapping_entities_by_external_object_type.get(ext_obj_type_id)

            def candidate_checker(candidate):
                if not candidate.ext_object_type_field_name:
                    return candidate
                else:
                    attr = ext_obj_attributes.get(candidate.ext_object_type_field_name)
                    if attr is not None and attr.get('value') == candidate.ext_object_type_field_value:
                        return candidate

        if candidates:
            last_candidate = None
            # doors heuristic to use heading entity mapping if ReqIF.Text is empty and
            # ReqIF.ChapterName is non empty
            heading_candidates = [
                x for x in candidates if (not x.ext_object_type_field_name and x.ext_object_type_field_value == 'Heading')
            ]
            if heading_candidates:
                heading_candidate = heading_candidates[0]
                reqif_chaptername_attr_ids = [
                    x.get('identifier') for x in ext_obj_attributes.values()
                    if x.get('long_name') == 'ReqIF.ChapterName'
                ]
                if reqif_chaptername_attr_ids:
                    reqif_chaptername_attr_id = reqif_chaptername_attr_ids[0]
                    reqif_text_attr_ids = [
                        x.get('identifier') for x in ext_obj_attributes.values()
                        if x.get('long_name') == 'ReqIF.Text'
                    ]
                    reqif_text_attr_id = reqif_text_attr_ids[0] if reqif_text_attr_ids else None
                    if (
                        ext_obj_attributes.get(reqif_chaptername_attr_id) and
                        (reqif_text_attr_id is None or ext_obj_attributes.get(reqif_text_attr_id))
                    ):
                        # ReqIF.Text is empty and ReqIF.ChapterName is non empty and we should use the Heading candidate
                        return heading_candidate

            for candidate in candidates:
                ret = candidate_checker(candidate)
                if ret is not None:
                    return ret
                last_candidate = candidate
            if obj:
                msg = (
                    "Missing Entity Mapping for: %s (%s=%s)",
                    obj.GetDescription(),
                    last_candidate.object_type_field_name if last_candidate else None,
                    (getattr(obj, last_candidate.object_type_field_name) if last_candidate.object_type_field_name else None)
                )
                self.log("error", msg)
                raise ue.Exception("just_a_replacement", msg[0] % msg[1:])

    def _convert_enum_value_to_str(self, enum_val):
        if isinstance(enum_val, datetime.datetime):
            return enum_val.isoformat()
        else:
            return u"{}".format(enum_val)


def set_titles_from_richtexts(cls, args):
    if (
        hasattr(cls, '__description_attrname_format__') and cls.__description_attrname_format__ and
        hasattr(cls, '__short_description_attrname_format__') and cls.__short_description_attrname_format__
    ):
        for iso_lang in i18n.Languages():
            description_attr_name = cls.__description_attrname_format__.format(iso=iso_lang)
            short_description_attr_name = cls.__short_description_attrname_format__.format(iso=iso_lang)
            if description_attr_name in args:
                description = args.get(description_attr_name)
                if hasattr(cls, short_description_attr_name):
                    short_title = rqm_utils.get_short_title_from_richtext(
                        field_length=getattr(cls, short_description_attr_name).length,
                        richtext=description
                    )
                    if short_title:
                        args[short_description_attr_name] = short_title
                else:
                    LOG.warning(
                        "Richtext long text %s does exist but corresponding short description field %s does not exist",
                        description_attr_name, short_description_attr_name
                    )


def create_audittrail_attribute_changes(importer, obj, db_args, update=False):
    config = rqm_utils.get_audittrail_config_for_rqm()
    tree_down_ctx = importer.current_target_specification_tree_ctx
    long_text_cache = tree_down_ctx['long_text_cache'].get(obj.__classname__, {}) if update else None

    def same_empty_val(val):
        if val == '' or val is None:
            return ''
        else:
            return val

    changes = []
    for k in db_args:
        new_val = same_empty_val(db_args.get(k))
        if k in obj.GetTextFieldNames():
            if long_text_cache:
                db_value = long_text_cache.get(k, {}).get(obj.cdb_object_id) if update else None
            else:
                db_value = obj.GetText(k) if update else None
            old_val = same_empty_val(db_value)
            if old_val != new_val:
                changes.append({
                    "attribute_name": k,
                    "old_value": "{}".format(old_val) if update else None,
                    "new_value": new_val,
                    "longtext": 1,
                    "detail_classname": "cdb_audittrail_detail_richtext"
                })
        else:
            old_val = same_empty_val(getattr(obj, k) if update and hasattr(obj, k) else None)
            if old_val != new_val:
                changes.append({
                    "attribute_name": k,
                    "old_value": "{}".format(old_val) if update else None,
                    "new_value": new_val,
                })
    changes_to_track = [  # E057076 skip attribute changes which should not be tracked
        x for x in changes if x.get('attribute_name') in config.get(obj.GetClassname())]
    return changes, changes_to_track


def _get_parent_ids(elem):
    parent_ids = []
    if elem.parent_object_id:
        parent_ids.append(elem.parent_object_id)
    parent = elem.ParentRequirement
    while parent:
        parent = parent.ParentRequirement
        if parent:
            parent_ids.append(parent.cdb_object_id)
    parent_ids.reverse()
    return parent_ids


def _get_audittrail_attach_to(result_obj):
    if (
        isinstance(result_obj, TargetValue)
    ):
        attach_to = (
            [result_obj.specification_object_id] + _get_parent_ids(result_obj.Requirement) +
            [result_obj.requirement_object_id, result_obj.cdb_object_id]
        )
    elif (
        isinstance(result_obj, RQMSpecObject)
    ):
        attach_to = (
            [result_obj.specification_object_id] + _get_parent_ids(result_obj) +
            [result_obj.cdb_object_id]
        )
    else:
        attach_to = [result_obj.cdb_object_id]
    return attach_to


def _post_create_op_create_qc(args, qc_args, importer, classname, result_obj, level):
    if 'target_value' in args:
        qc_args['target_value'] = args['target_value']
    if 'act_value' in args:
        qc_args['act_value'] = args['act_value']
    qc_args['classname'] = classname
    qc_args['cdbf_object_id'] = result_obj.cdb_object_id
    importer.log("debug", level * 2 * " " + "Create QualityCharacteristics ... : '%s'" % qc_args)
    qc = rqm_utils.createQC(**qc_args)
    importer.log("debug", level * 2 * " " + "QualityCharacteristics created... : '%s'" % qc)
    return qc


def _cdb_op(opname, classname, cdbObject, args, importer=None, level=0):
    """
    """
    qc = None
    qc_args = {}
    cls = ClassRegistry().find(classname)
    if not cls:
        LOG.error('Invalid classname: %s', classname)
        raise ValueError('Invalid classname')
    change_control_attributes = cls.MakeChangeControlAttributes()
    if change_control_attributes:
        args.update(change_control_attributes)
    set_titles_from_richtexts(cls, args)
    if opname == 'Create':
        # some specific pre args and attach_to updates
        rqm_utils._update_position_cache(
            importer=importer,
            args=args,
            entity=cls
        )
        result_obj = cls.Create(**args)
        if result_obj:
            # check long text attributes
            for arg in args.keys():
                if arg in result_obj.GetTextFieldNames():
                    result_obj.SetText(arg, args[arg])
            qc = _post_create_op_create_qc(args, qc_args, importer, classname, result_obj, level)
            rqm_utils._update_position_cache(
                importer=importer,
                args=args,
                entity=cls,
                afterOperation=True
            )
            _, changes_to_track = create_audittrail_attribute_changes(
                importer,
                result_obj,
                args
            )
            importer.audit_trail_entries['create'].append(
                {
                    "cdb_object_id": result_obj.cdb_object_id,
                    "idx": 0,
                    "description": result_obj.GetDescription(),
                    "attach_to": _get_audittrail_attach_to(result_obj),
                    "classname": cls.__classname__,
                    "changes": changes_to_track
                }
            )
            return result_obj, qc
    elif opname == 'Update':
        rqm_utils._update_position_cache(
            importer=importer,
            args=args,
            entity=cls,
            obj=cdbObject
        )
        # some specific pre args, attach_to updates
        changes, changes_to_track = create_audittrail_attribute_changes(
            importer,
            cdbObject,
            args,
            update=True
        )
        real_changes = [
            x for x in changes
            if x.get('attribute_name') not in
            change_control_attributes.keys()
        ]
        if len(real_changes) > 0:
            importer.audit_trail_entries['modify'].append(
                {
                    "cdb_object_id": cdbObject.cdb_object_id,
                    "idx": 0,
                    "description": cdbObject.GetDescription(),
                    "attach_to": _get_audittrail_attach_to(cdbObject),
                    "classname": cls.__classname__,
                    "changes": changes_to_track
                }
            )
            # check long text attributes
            for arg in list(args):
                # do not update virtual attributes
                if arg in ["target_value", "act_value"]:
                    # handle target_value update case
                    if arg == "target_value":
                        qc = rqm_utils.getFulfillmentQC(cdbObject)
                        if qc is not None:
                            qc.set_target_value(args[arg])
                    del args[arg]
                if arg in cdbObject.GetTextFieldNames():
                    cdbObject.SetText(arg, args[arg])
                    # remove attribute from args list
                    del args[arg]
            ret = cdbObject.Update(**args), qc
            rqm_utils._update_position_cache(
                importer=importer,
                args=args,
                entity=cls,
                obj=cdbObject,
                afterOperation=True
            )
            return ret
        else:
            # even if not really an operation has been called - this object exists with this position in db
            rqm_utils._update_position_cache(
                importer=importer,
                args=args,
                entity=cls,
                obj=cdbObject,
                afterOperation=True
            )
            return False, None
    return None, qc


def _get_http_mime_type(fmime):
    return "{}/{}".format(fmime.type, fmime.subtype)


def _get_filetype(fname, object_tag_details):
    ftype = None
    if 'type' in object_tag_details:
        candidates = getFileTypesByFilename(fname)
        for c in candidates:
            if _get_http_mime_type(c.getMIMEType()) == object_tag_details.get('type'):
                ftype = c
                break
    if ftype is None:  # none found use the default
        ftype = getFileTypeByFilename(fname)
    return ftype
