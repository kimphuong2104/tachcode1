# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import collections
import datetime
import re
import time
import uuid

from cdb import sqlapi, ue, util
from cdb.objects import Forward, Object, references
from cdb.objects.core import ByID, NotUnique
from cdb.platform.gui import CDBCatalog, I18nCatalogEntry
from cs.classification.classes import (BooleanClassProperty,
                                       ClassificationClass,
                                       DatetimeClassProperty,
                                       FloatClassProperty,
                                       IntegerClassProperty, TextClassProperty,
                                       MultilangClassProperty,
                                       ClassProperty,
                                       ClassPropertyValuesView)

from cs.requirements import rqm_utils

fReqIFProfile = Forward(__name__ + ".ReqIFProfile")
fReqIFProfileEntity = Forward(__name__ + ".ReqIFProfileEntity")
fReqIFProfileAttribute = Forward(__name__ + ".ReqIFProfileAttribute")
fReqIFProfileEnumerationAttribute = Forward(__name__ + ".ReqIFProfileEnumerationAttribute")
fReqIFProfileEnumerationValue = Forward(__name__ + ".ReqIFProfileEnumerationValue")
fReqIFProfileRelationType = Forward(__name__ + ".ReqIFProfileRelationType")
fReqIFProfileEntityClassAssignment = Forward(__name__ + ".ReqIFProfileEntityClassAssignment")

xsd_id_matcher = re.compile('^[a-zA-Z_][a-zA-Z0-9_.-]*$')


class ReqIFProfile(Object):

    __classname__ = "cdbrqm_reqif_profile"
    __maps_to__ = "cdbrqm_reqif_profile"

    Entities = references.Reference_N(fReqIFProfileEntity, fReqIFProfileEntity.reqif_profile_id == fReqIFProfile.cdb_object_id)
    AllAttributes = references.Reference_N(fReqIFProfileAttribute, fReqIFProfileAttribute.reqif_profile_id == fReqIFProfile.cdb_object_id)
    RelationTypes = references.Reference_N(fReqIFProfileRelationType, fReqIFProfileRelationType.reqif_profile_id == fReqIFProfile.cdb_object_id)

    def assertValid(self, direction):
        if direction == 'import':
            if len(self.AllAttributes.KeywordQuery(object_type_classname=MultilangClassProperty.__classname__)) > 0:
                errors = ["MultilangClassProperties are not supported for ReqIF Import yet"]
                raise ValueError("Invalid ReqIF Profile (%s): \n%s" % (self.profile_name, "\n".join(errors)))
        mapping_data = self.get_mapping_data()
        errors = []
        hasEntityMappings = len(mapping_data.get('entities').get(direction)) > 0
        if not hasEntityMappings:
            errors.append('No entity mapping - at least one is mandatory.')
        hasAttributeMappings = len(mapping_data.get('attributes')) > 0
        if not hasAttributeMappings:
            errors.append('No attribute mapping - at least one is mandatory.')
        hasDataTypes = len(mapping_data.get('datatypes')) > 0
        if not hasDataTypes:
            errors.append('No datatype - at least one is mandatory.')
        if not len(errors) == 0:
            raise ValueError("Invalid ReqIF Profile (%s): \n%s" % (self.profile_name, "\n".join(errors)))

    def load_db_enum_data(self):
        db_enum_cache = collections.defaultdict(dict)
        # load all enum values for all mapped enumerations within the profile
        enumeration_attribute_mappings = self.AllAttributes.KeywordQuery(data_type='enumeration')
        prop_codes = [
            attribute_mapping.internal_field_name for
            attribute_mapping in enumeration_attribute_mappings
        ]
        props = {prop.code: prop for prop in ClassProperty.KeywordQuery(code=prop_codes)}
        classification_class_ids = [prop.classification_class_id for prop in props.values()]
        classification_class_codes = ClassificationClass.oids_to_code(classification_class_ids)

        for attribute_mapping in enumeration_attribute_mappings:
            enum_cache_key = attribute_mapping.external_identifier
            if attribute_mapping.is_mapped_enumeration:
                enum_mapping = attribute_mapping.get_internal_to_external_map()
            prop = props.get(attribute_mapping.internal_field_name)
            enum_value_objects = ClassPropertyValuesView.get_catalog_value_objects(
                classification_class_codes[prop.classification_class_id],
                prop.code,
                True
            )
            for enum_value in enum_value_objects:
                value = rqm_utils.get_classification_val(enum_value, language="en")
                value = rqm_utils.convert_enum_value_to_str(value)
                if attribute_mapping.is_mapped_enumeration:
                    val_id, mapped_val = enum_mapping.get(
                        enum_value.cdb_object_id,
                        (
                            enum_value.value_oid,
                            value  # fallback to default
                        )
                    )
                    val_id = prefixID(val_id)
                    db_enum_cache[enum_cache_key][mapped_val] = {
                        'key': val_id,
                        'value': value,
                        'mapped_value': mapped_val
                    }
                else:
                    db_enum_cache[enum_cache_key][value] = {
                        'key': enum_value.value_oid,
                        'value': value
                    }
        return db_enum_cache

    def get_mapping_entities(self, as_dict=False):
        mapping_entities_by_internal_object_type = collections.defaultdict(dict)
        mapping_entities_by_external_object_type = collections.defaultdict(dict)
        mapping_entities = self.Entities.Execute()
        for entity_mapping in mapping_entities:
            if entity_mapping.object_type_field_name:
                # this is a specific entity mapping with an attribute value condition
                mapping_entities_by_internal_object_type[entity_mapping.internal_object_type][entity_mapping.object_type_field_value] = entity_mapping.ToJson() if as_dict else entity_mapping
                mapping_entities_by_internal_object_type[entity_mapping.internal_object_type]["__conditional_attribute__"] = entity_mapping.object_type_field_name
            else:
                # this is the default entity mapping without further conditions
                mapping_entities_by_internal_object_type[entity_mapping.internal_object_type]["__default_entity_mapping__"] = entity_mapping.ToJson() if as_dict else entity_mapping
            if entity_mapping.ext_object_type_field_name:
                # this is a specific entity mapping with an attribute value condition
                mapping_entities_by_external_object_type[entity_mapping.external_object_type][entity_mapping.ext_object_type_field_value] = entity_mapping.ToJson() if as_dict else entity_mapping
                mapping_entities_by_external_object_type[entity_mapping.external_object_type]["__conditional_attribute__"] = entity_mapping.ext_object_type_field_name
            elif not entity_mapping.ext_object_type_field_name and entity_mapping.ext_object_type_field_value == 'Heading':
                # special doors heading type
                reqif_chapter_name_attributes = entity_mapping.Attributes.KeywordQuery(external_field_name='ReqIF.ChapterName').Execute()
                if reqif_chapter_name_attributes:
                    mapping_entities_by_external_object_type[entity_mapping.external_object_type]["__doors_heading_type_mapping__"] = entity_mapping.ToJson() if as_dict else entity_mapping
                    mapping_entities_by_external_object_type[entity_mapping.external_object_type]["__doors_heading_ReqIF.ChapterName_attribute_id__"] = reqif_chapter_name_attributes[0].external_identifier
            else:
                # this is the default entity mapping without further conditions
                mapping_entities_by_external_object_type[entity_mapping.external_object_type]["__default_entity_mapping__"] = entity_mapping.ToJson() if as_dict else entity_mapping
        return {
            'export': mapping_entities_by_internal_object_type,
            'import': mapping_entities_by_external_object_type
        }

    def get_mapping_attributes(self, as_dict=False):
        mapping_attributes_by_entity_mapping = collections.defaultdict(dict)
        for attr in self.AllAttributes.Execute():
            mapping_attributes_by_entity_mapping[attr.entity_object_id][attr.external_identifier] = attr.ToJson() if as_dict else attr
        return mapping_attributes_by_entity_mapping

    def get_mapping_datatypes(self, as_dict=False):
        datatypes = set(self.AllAttributes.data_type)
        return list(datatypes) if as_dict else datatypes

    def get_mapping_relation_types(self, as_dict=False):
        mapping_relation_types = collections.defaultdict(dict)
        for relation_mapping in self.RelationTypes.Execute():
            mapping_relation_types[relation_mapping.external_link_type] = relation_mapping.ToJson() if as_dict else relation_mapping
        return mapping_relation_types

    def get_mapping_data(self, as_dict=False):
        data = dict(
            entities=self.get_mapping_entities(as_dict),
            attributes=self.get_mapping_attributes(as_dict),
            datatypes=self.get_mapping_datatypes(as_dict),
            relations=self.get_mapping_relation_types(as_dict),
            enums=self.load_db_enum_data()
        )
        if as_dict:
            data.update(self.ToJson())
        return data

    def _ensure_one_default(self, ctx):
        if self.is_default:
            if len(ReqIFProfile.Query(u"is_default = 1 AND cdb_object_id != '%s'" % self.cdb_object_id)) > 0:
                raise ue.Exception("cdbrqm_reqif_err_only_one_default")

    def copy_sub_elements(self, ctx):
        source = rqm_utils._get_source_object(self, ctx, ReqIFProfile)
        entity_old_new_map = {}
        # copy all entities and correct their linking to the profile
        for entity in source.Entities:
            new_entity = entity.Copy(reqif_profile_id=self.cdb_object_id)
            entity_old_new_map[entity.cdb_object_id] = new_entity.cdb_object_id
            for classAssignment in entity.ClassificationClassAssignments:
                classAssignment.Copy(entity_object_id=new_entity.cdb_object_id)
        # copy all attributes and correct their linking to the profile and the entity
        for attribute in source.AllAttributes:
            args = dict(
                reqif_profile_id=self.cdb_object_id,
                entity_object_id=entity_old_new_map[attribute.entity_object_id],
                cdb_classname=attribute.cdb_classname if attribute.cdb_classname is not None else ''
            )
            attribute.Copy(**args)
        # copy all relation types and correct their linking to the profile
        for relationtype in source.RelationTypes:
            relationtype.Copy(reqif_profile_id=self.cdb_object_id)

    @classmethod
    def get_default(cls):
        default_profiles = ReqIFProfile.KeywordQuery(is_default=1)
        if len(default_profiles) == 1:
            return default_profiles[0]

    event_map = {(('create', 'copy', 'modify'), ('post_mask', 'pre')): '_ensure_one_default',
                 ('copy', 'post'): 'copy_sub_elements'}


class ReqIFProfileAttribute(Object):

    __classname__ = "cdbrqm_reqif_profile_attrs"
    __maps_to__ = "cdbrqm_reqif_profile_attrs"

    Profile = references.Reference_1(fReqIFProfile, fReqIFProfile.cdb_object_id == fReqIFProfileEntity.reqif_profile_id)
    Entity = references.Reference_1(fReqIFProfileEntity,
                                    fReqIFProfileEntity.reqif_profile_id == fReqIFProfileAttribute.reqif_profile_id,
                                    fReqIFProfileEntity.cdb_object_id == fReqIFProfileAttribute.entity_object_id
                                    )

    def is_classification_property(self):
        return self.object_type_classname in [TextClassProperty.__classname__,
                                              BooleanClassProperty.__classname__,
                                              IntegerClassProperty.__classname__,
                                              FloatClassProperty.__classname__,
                                              DatetimeClassProperty.__classname__] and self.is_property

    @classmethod
    def _create_from_property_preparation(cls, ctx):
        # we should only react on web ui creation on drop cases
        if ctx.uses_webui and "property_object_id" in ctx.dialog.get_attribute_names():
            mandatory_dialog_fields = ["property_object_id", "reqif_profile_id", "entity_object_id"]
            for dialog_field in mandatory_dialog_fields :
                if dialog_field not in ctx.dialog.get_attribute_names() or not ctx.dialog[dialog_field]:
                    raise ue.Exception("just_a_replacement", "Missing parameters")
            reqif_profile_id = ctx.dialog.reqif_profile_id
            entity_object_id = ctx.dialog.entity_object_id
            entity = ReqIFProfileEntity.ByKeys(reqif_profile_id=reqif_profile_id, cdb_object_id=entity_object_id)
            if not entity:
                raise ue.Exception("cdbrqm_reqif_invalid_drop_relation")
            property_object_id = ctx.dialog.property_object_id
            cls._handle_property_drop(
                entity=entity,
                property_object_id=property_object_id,
                ctx=ctx,
            )
           
    @classmethod
    def _handle_property_drop(cls, entity, property_object_id, ctx):
        prop = ByID(property_object_id)
        if not prop:
            raise ue.Exception('cdbrqm_reqif_invalid_property')

        internal_field_name = prop.code
        ctx.set("internal_field_name", internal_field_name)
        object_type_classname = prop.cdb_classname
        ctx.set("object_type_classname", object_type_classname)

        if prop.is_multivalued and not prop.is_enum_only:
            raise ue.Exception('cdbrqm_reqif_only_enum_propertys_can_be_multivalued')
        ctx.set('is_property', '1')
        ctx.set('is_multivalued', prop.is_multivalued)
        # ctx.set('is_editable', prop.is_editable)
        # property must belong to the class or a base class of the assigned classes
        class_codes = list(entity.ClassificationClasses.code)
        assigned_class_codes = ClassificationClass.get_base_class_codes(
            class_codes=class_codes, include_given=True
        )
        property_class_codes = ClassificationClass.get_base_class_codes(
            class_ids=[prop.classification_class_id], include_given=True
        )
        if not set(property_class_codes).intersection(set(assigned_class_codes)):
            classification_cls = ByID(prop.classification_class_id)
            raise ue.Exception(
                'cdbrqm_reqif_property_class_not_assigned_to_entity',
                classification_cls.GetDescription(),
                entity.GetDescription() if entity else ''
            )

        if internal_field_name and object_type_classname in [
            TextClassProperty.__classname__, MultilangClassProperty.__classname__
        ]:
            if prop.is_enum_only:
                ctx.set('data_type', 'enumeration')
            else:
                if internal_field_name == MultilangClassProperty.__classname__:
                    # for now MultiLangClassProperties are only supported in export direction
                    # and for enum only properties
                    raise ue.Exception('cdbrqm_reqif_unsupported_property_type')
                ctx.set('data_type', 'char')
        elif internal_field_name and object_type_classname in [BooleanClassProperty.__classname__, IntegerClassProperty.__classname__]:
            if prop.is_enum_only:
                ctx.set('data_type', 'enumeration')
            else:
                ctx.set('data_type', 'integer')
        elif internal_field_name and object_type_classname in [FloatClassProperty.__classname__]:
            if prop.is_enum_only:
                ctx.set('data_type', 'enumeration')
            else:
                ctx.set('data_type', 'float')
        elif internal_field_name and object_type_classname in [DatetimeClassProperty.__classname__]:
            if prop.is_enum_only:
                ctx.set('data_type', 'enumeration')
            else:
                ctx.set('data_type', 'date')
        else:
            raise ue.Exception('cdbrqm_reqif_unsupported_property_type')

    def _insert_data_type_for_drag_and_drop(self, ctx=None):
        if not self.data_type:
            if ctx and ctx.dragged_obj:
                if not self.Entity:
                    raise ue.Exception("cdbrqm_reqif_invalid_drop_relation")
                property_object_id = ctx.dragged_obj.cdb_object_id
                self._handle_property_drop(
                    entity=self.Entity,
                    property_object_id=property_object_id,
                    ctx=ctx,
                )

    def change_editability(self, ctx=None):
        w = ctx.dialog.writeable
        if w != '' and not self.is_reference_link:
            sqlapi.SQLupdate("{table_name} SET is_editable={editable} WHERE reqif_profile_id='{profile_id}' AND external_identifier='{external_id}'".format(
                table_name=ReqIFProfileAttribute.__maps_to__,
                editable=w,
                profile_id=self.reqif_profile_id,
                external_id=self.external_identifier)
            )
            ctx.refresh_tables([ReqIFProfileAttribute.__maps_to__])

    @classmethod
    def set_profile_and_entity(cls, ctx=None):
        parent = ByID(ctx.parent.cdb_object_id)
        if isinstance(parent, ReqIFProfileEntity):
            ctx.set('entity_object_id', parent.cdb_object_id)
            ctx.set('reqif_profile_id', parent.reqif_profile_id)
        else:
            ctx.set('reqif_profile_id', parent.cdb_object_id)

    @classmethod
    def add_object_ref_link_attribute(cls, ctx=None):
        args = dict(
            reqif_profile_id=ctx.dialog.reqif_profile_id,
            entity_object_id=ctx.dialog.entity_object_id,
            internal_field_name='rqm_object_reference_link',
            is_reference_link=1,
            data_type='xhtml'
        )
        results = cls.KeywordQuery(**args).Execute()
        if not results:
            args['external_identifier'] = rqm_utils.createUniqueIdentifier()
            args['external_field_name'] = util.get_label(
                'cdbrqm_reqif_object_ref_link_column_name'
            )
            cls.Create(**args)
            ctx.refresh_tables([
                cls.__maps_to__
            ])

    event_map = {
        ('create', 'pre_mask'): ('_insert_data_type_for_drag_and_drop', '_create_from_property_preparation'),
        ('cdbrqm_reqif_attr_editable', 'now'): 'change_editability',
        ('cdbrqm_reqif_prof_attrs_add_ref', ('pre_mask', 'pre')): 'set_profile_and_entity',
        ('cdbrqm_reqif_prof_attrs_add_ref', ('now')): 'add_object_ref_link_attribute'
    }


class ReqIFProfileEnumerationAttribute(ReqIFProfileAttribute):
    __classname__ = "cdbrqm_reqif_profile_enum_attr"
    __match__ = ReqIFProfileAttribute.cdb_classname >= __classname__

    EnumValues = references.Reference_N(
        fReqIFProfileEnumerationValue,
        fReqIFProfileEnumerationValue.entity_object_id == fReqIFProfileEnumerationAttribute.entity_object_id,
        fReqIFProfileEnumerationValue.reqif_profile_id == fReqIFProfileEnumerationAttribute.reqif_profile_id,
        fReqIFProfileEnumerationValue.reqif_profile_attribute_id == fReqIFProfileEnumerationAttribute.cdb_object_id,
        order_by=fReqIFProfileEnumerationValue.external_value
    )

    def get_internal_to_external_map(self):
        int_to_ext_map = {}
        for enum_value in self.EnumValues:
            int_to_ext_map[enum_value.internal_identifier] = (
                enum_value.external_identifier, enum_value.external_value
            )
        return int_to_ext_map


class ReqIFProfileEnumerationValue(Object):
    __classname__ = "cdbrqm_reqif_enum_value"
    __maps_to__ = "cdbrqm_reqif_enum_value"


class ReqIFProfileEntityInvalidError(ValueError):
    pass


class ReqIFProfileEntityClassAssignment(Object):
    __classname__ = "cdbrqm_reqif_prof_ent2cl_cls"
    __maps_to__ = "cdbrqm_reqif_prof_ent2cl_cls"


class ReqIFProfileEntity(Object):

    __classname__ = "cdbrqm_reqif_profile_entities"
    __maps_to__ = "cdbrqm_reqif_profile_entities"

    Profile = references.Reference_1(fReqIFProfile, fReqIFProfile.cdb_object_id == fReqIFProfileEntity.reqif_profile_id)
    Attributes = references.Reference_N(fReqIFProfileAttribute,
                                        fReqIFProfileAttribute.entity_object_id == fReqIFProfileEntity.cdb_object_id,
                                        fReqIFProfileAttribute.reqif_profile_id == fReqIFProfileEntity.reqif_profile_id,
                                        order_by=fReqIFProfileAttribute.internal_field_name)

    ClassificationClassAssignments = references.Reference_N(fReqIFProfileEntityClassAssignment,
                                                            fReqIFProfileEntityClassAssignment.entity_object_id == fReqIFProfileEntity.cdb_object_id)

    ClassificationClasses = references.ReferenceMethods_N(ClassificationClass, lambda self: self._classificationClasses())

    def _classificationClasses(self):
        eca = self.ClassificationClassAssignments.classification_class_object_id
        return ClassificationClass.KeywordQuery(cdb_object_id=eca)

    def get_objects_by_reqif_id(self, reqif_id, revision_key_attr, max_revision=None):
        # reqif ids are unique but not version specific
        from cdb.objects import ClassRegistry
        cls = ClassRegistry().find(self.internal_object_type)
        if cls:
            if hasattr(cls, '__maps_to_view__'):
                ti = util.TableInfo(cls.__maps_to_view__)
                if max_revision is None:
                    stmt = "SELECT MAX({attr_list}) max_revision FROM {name} WHERE {condition}".format(
                        attr_list=revision_key_attr,
                        name=ti.name(),
                        condition=ti.condition(
                            ["reqif_id"],
                            [reqif_id]
                        )
                    )
                    rs = sqlapi.RecordSet2(
                        sql=stmt,
                        table=cls.__maps_to__
                    )
                    if rs:
                        max_revision = rs[0]['max_revision']
                        if max_revision is None:
                            max_revision = ''
                        else:
                            max_revision = int(float(max_revision))  # due to oracle where the max result is a float
                stmt = "SELECT {attr_list} FROM {name} WHERE {condition}".format(
                    attr_list=ti.attrname_list(),
                    name=ti.name(),
                    condition=ti.condition(
                        [
                            "reqif_id",
                            revision_key_attr,
                            "ce_baseline_id"
                        ],
                        [
                            reqif_id.strip(),
                            "{}".format(max_revision),
                            ""
                        ]
                    )
                )
                rs = sqlapi.RecordSet2(
                    sql=stmt,
                    table=cls.__maps_to__
                )
                res = cls.FromRecords(rs)
                if res:
                    if len(res) > 1:
                        raise NotUnique("Multiple objects found for reqif_id: {}".format(reqif_id))
                    return res[0]
            else:
                ti = util.TableInfo(cls.__maps_to__)
                if max_revision is None:
                    stmt = "SELECT MAX({attr_list}) max_revision FROM {name} WHERE {condition}".format(
                        attr_list=revision_key_attr,
                        name=ti.name(),
                        condition=ti.condition(
                            ["reqif_id"],
                            [reqif_id]
                        )
                    )
                    rs = sqlapi.RecordSet2(
                        sql=stmt
                    )
                    if rs:
                        max_revision = rs[0]['max_revision']
                args = {
                    'reqif_id': reqif_id,
                    revision_key_attr: max_revision,
                    'ce_baseline_id': ''
                }
                return cls.ByKeys(**args)
        else:
            raise ReqIFProfileEntityInvalidError(self)


class ReqIFProfileRelationType(Object):

    __classname__ = "cdbrqm_reqif_prof_rel_types"
    __maps_to__ = "cdbrqm_reqif_prof_rel_types"

    Profile = references.Reference_1(fReqIFProfile, fReqIFProfile.cdb_object_id == fReqIFProfileRelationType.reqif_profile_id)


class RequirementToTargetValueReqIFProfileRelationType(object):
    link_name = 'cdbrqm_requirement2target_value'


def prefixID(element_id):
    """
    As the ReqIF Schema requests ID fields with data type xsd:ID these IDs
    have to be start with an underscore or alphabetic character but not with
    a digit. Therefore the function returns the uuid with a special
    alphabetic prefix.
    """
    if not xsd_id_matcher.match(element_id):
        return 'cdb-%s' % element_id
    else:
        return element_id


def unPrefixID(element_id):
    """
    The complement function to the prefixID function.
    """
    if not element_id or not element_id.startswith('cdb-'):
        return element_id
    else:
        return element_id[4:]


def createXsdDateTime(date_time=None):
    """
    Creates a xsd:datetime string.

    If optional date_time argument is empty the generated string is created
    from datetime.datetime, otherwise the given datetime object is used.
    """
    xsd_date_iso_format = "%Y-%m-%dT%H:%M:%S"

    if (date_time):
        dt = date_time
    else:
        dt = datetime.datetime.now()
    dts = dt.strftime(xsd_date_iso_format)
    return dts
