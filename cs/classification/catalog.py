# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module catalog

This is the documentation for the catalog module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from _collections import defaultdict
import types
import re

from cdb import i18n
from cdb import sig
from cdb import sqlapi
from cdb import transactions
from cdb import ue
from cdb.objects.core import Object
from cdb.objects import ByID
from cdb.objects import references
from cdb.objects import expressions
from cdb.objects import objectlifecycle
from cdb.objects.references import ReferenceMethods_1
from cdb.transactions import Transaction

import cdbwrapc

from cs.classification import applicability
import cs.classification
from cs.classification import tools

from cs.classification.pattern import Pattern

fProperty = expressions.Forward("cs.classification.catalog.Property")
fPropertyValue = expressions.Forward("cs.classification.catalog.PropertyValue")
fObjectReferenceProperty = expressions.Forward("cs.classification.catalog.ObjectReferenceProperty")
fClassificationReferenceApplicability = expressions.Forward(
    "cs.classification.applicability.ClassificationReferenceApplicability")
fBlockClassProperty = expressions.Forward("cs.classification.classes.BlockClassProperty")
fBlockProperty = expressions.Forward("cs.classification.catalog.BlockProperty")
fBlockPropertyAssignment = expressions.Forward("cs.classification.catalog.BlockPropertyAssignment")
fClassProperty = expressions.Forward("cs.classification.classes.ClassProperty")


class Property(Object):
    __maps_to__ = "cs_property"
    __classname__ = "cs_property"

    class EDIT(objectlifecycle.State):
        status = 0

    class RELEASED(objectlifecycle.State):
        status = 200

    class BLOCKED(objectlifecycle.State):
        status = 300

    PropertyValues = references.Reference_N(
        fPropertyValue,
        fPropertyValue.property_object_id == fProperty.cdb_object_id
    )

    DependentClassProperties = references.Reference_N(
        fClassProperty,
        fClassProperty.catalog_property_id == fProperty.cdb_object_id
    )

    BlockPropertyAssignments = references.Reference_N(
        fBlockPropertyAssignment,
        fBlockPropertyAssignment.assigned_property_object_id == fProperty.cdb_object_id
    )

    # This only makes sense for object reference properties
    # but we need it here because otherwise it can't be navigated by
    # the module content resolver
    Applicabilities = references.Reference_N(
        applicability.ClassificationReferenceApplicability,
        fClassificationReferenceApplicability.property_id == fObjectReferenceProperty.cdb_object_id
    )

    def _property_values(self, active_only=True, count=False):
        args = {"property_object_id": self.cdb_object_id}
        if active_only:
            args["is_active"] = 1
        if count:
            return len(PropertyValue.KeywordQuery(**args))
        else:
            return PropertyValue.KeywordQuery(**args)

    def property_values(self, active_only=True):
        return self._property_values(active_only, count=False)

    def has_property_values(self, active_only=True):
        return self._property_values(active_only, count=True) > 0

    @classmethod
    def get_catalog_codes(cls):
        catalog_prop_codes = set()
        for row in sqlapi.RecordSet2(sql="SELECT code FROM cs_property"):
            catalog_prop_codes.add(row["code"])
        return catalog_prop_codes

    @classmethod
    def get_catalog_values(cls, property_code, active_only, request=None):
        prop = cls.ByKeys(code=property_code)
        if prop:
            args = {"property_object_id": prop.cdb_object_id}
            if active_only:
                args["is_active"] = 1
            data = PropertyValue.KeywordQuery(**args)
            return PropertyValue.to_json_data(data, request, prop=prop)

    @classmethod
    def get_catalog_values_by_oid(cls, prop, active_only, request=None):
        args = {
            "property_object_id": prop.cdb_object_id
        }
        if active_only:
            args["is_active"] = 1
        data = PropertyValue.KeywordQuery(**args)
        return PropertyValue.to_json_data(data, request, prop=prop)

    def default_value(self):
        return PropertyValue.ByKeys(cdb_object_id=self.default_value_oid)

    def getClassDefaults(self):
        attrs = [
            "default_value_oid",
            "is_multivalued",
            "is_enum_only",
            "has_enum_values",
            "katalog"
        ]
        attrs.extend([
            field.name
            for field in Property.name.getLanguageFields().values()
        ])
        attrs.extend([
            field.name
            for field in Property.prop_description.getLanguageFields().values()
        ])
        return {attr: getattr(self, attr) for attr in attrs}

    def isActive(self):
        """ :return: True if the property can be imported in a class.

            In the default implementation this is the case, when the property
            has the status RELEASED. Customers can change this.
        """
        return self.status == self.RELEASED.status

    def validate_code(self, ctx):
        from cs.classification.classes import ClassProperty
        if len(Property.KeywordQuery(code=self.code)) > 0:
            raise ue.Exception("cs_classification_class_property_code_not_unique", self.code)
        if len(ClassProperty.KeywordQuery(code=self.code)) > 0:
            raise ue.Exception("cs_classification_class_property_code_not_unique2", self.code)

    def isNumeric(self):
        return False

    def set_fields_readonly(self, ctx):
        readonly_attrs = ['code']
        ctx.set_fields_readonly(readonly_attrs)

    def disable_default(self, ctx):
        ctx.set_readonly('default_value_oid')

    def _check_multivalue_change(self, ctx):
        from cs.classification import ObjectPropertyValue

        old_value = ctx.object.is_multivalued
        new_value = u'' if self.is_multivalued is None else str(self.is_multivalued)

        if new_value != old_value:
            if new_value == u'1':
                # single to multivalue change is always possible
                ctx.keep("propagate_to_class_properties_needed", "1")
            elif new_value == u'0':
                # multivalue to single value change is only possible if no property values exist
                property_codes = [self.code]
                derived_class_properties = sqlapi.RecordSet2(
                    "cs_class_property", "catalog_property_id='%s'" % self.cdb_object_id
                )
                for class_property in derived_class_properties:
                    property_codes.append(class_property.code)
                if ObjectPropertyValue.value_exists_in(property_codes):
                    raise ue.Exception('cs_classification_property_multivalue_not_changeable')
                else:
                    ctx.keep("propagate_to_class_properties_needed", "1")

    def add_to_all_properties_folder(self, ctx):
        if ctx.relationship_name == 'cs_property_folder_assignment' and \
                ctx.parent.cdb_object_id == PropertyFolder.ALL_PROPERTIES_FOLDER:
            return
        PropertyFolderAssignment.Create(folder_id=PropertyFolder.ALL_PROPERTIES_FOLDER,
                                        property_id=self.cdb_object_id)

    def propagate_to_class_properties(self, ctx):
        if "propagate_to_class_properties_needed" in ctx.ue_args.get_attribute_names():
            is_multivalued = 'NULL' if self.is_multivalued is None else self.is_multivalued
            sqlapi.SQLupdate(
                "cs_class_property set is_multivalued = {is_multivalued} where catalog_property_code = '{code}'".format(
                    is_multivalued=is_multivalued, code=self.code
                )
            )

    def set_has_enum_values(self, has_values_hint=False):
        changed = False
        if has_values_hint or self.has_property_values():
            if not self.has_enum_values:
                self.has_enum_values = 1
                has_values_hint = True
                changed = True
        elif self.has_enum_values:
            self.has_enum_values = 0
            changed = True

        if changed:
            # also check class properties based on this prop
            for class_prop in self.DependentClassProperties:
                class_prop.set_has_enum_values(has_values_hint)

    def reset_default_value(self, value_oid):
        if (
                (self.default_value_oid == value_oid) or
                (self.default_value_oid is not None and value_oid is None)
        ):
            self.default_value_oid = None
            # also check class properties based on this prop
            for class_prop in self.DependentClassProperties:
                class_prop.reset_default_value(value_oid)

    def value_exists(self):
        from cs.classification import ObjectPropertyValue
        # FIXME: must resolve class properties based on this catalog prop
        return ObjectPropertyValue.value_exists(self.code)

    @classmethod
    def get_valid_code(cls, code):
        from cs.classification.util import check_code, create_code, make_code_unique

        valid_code = code if check_code(code) else create_code(code)
        stmt = "SELECT code FROM cs_class_property " \
               "WHERE code like '{prop_code}%' " \
               "UNION ALL " \
               "SELECT code FROM cs_property " \
               "WHERE code like '{prop_code}%'".format(prop_code=valid_code)
        unique_code = make_code_unique(stmt, valid_code)

        return unique_code

    def _delete_block_prop_assigments(self, ctx):
        # Why is this needed as properties that are assigned to a block cannot be deleted?
        sqlapi.SQLdelete(
            "from cs_block_prop_assign where assigned_property_code = '{prop_code}'".format(
                prop_code=sqlapi.quote(self.code)
            )
        )

    event_map = {
        (('create', 'copy'), 'pre'): ('validate_code'),
        (('create', 'copy'), 'pre_mask'): ('disable_default'),
        (('create', 'copy'), 'post'): ('add_to_all_properties_folder'),
        ('delete', 'post'): ('_delete_block_prop_assigments'),
        ('modify', 'pre_mask'): 'set_fields_readonly',
        ('modify', 'pre'): '_check_multivalue_change',
        ('modify', 'post'): 'propagate_to_class_properties'
    }


class TextProperty(Property):
    __classname__ = "cs_text_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "text"

    def getClassDefaults(self):
        result = super(TextProperty, self).getClassDefaults()
        result.update(
            data_length=self.data_length,
            is_url=self.is_url,
            multiline=self.multiline,
            pattern=self.pattern,
            regex=self.regex
        )
        return result

    def propagate_to_text_class_properties_needed(self, ctx):
        data_length = '' if self.data_length is None else str(self.data_length)
        if data_length != ctx.object.data_length:
            ctx.keep("propagate_to_text_class_properties_needed", "1")
            return
        pattern = '' if self.pattern is None else self.pattern
        if pattern != ctx.object.pattern:
            ctx.keep("propagate_to_text_class_properties_needed", "1")
            return

    def propagate_to_text_class_properties(self, ctx):
        if "propagate_to_text_class_properties_needed" in ctx.ue_args.get_attribute_names():
            data_length = 'NULL' if self.data_length is None else self.data_length
            sqlapi.SQLupdate(
                "cs_class_property set data_length = {data_length}, pattern = '{pattern}', regex = '{regex}' where catalog_property_code = '{code}'".format(
                    code=self.code, data_length=data_length, pattern=sqlapi.quote(self.pattern),
                    regex=sqlapi.quote(self.regex)
                )
            )

    def create_regex(self, ctx):
        regex = Pattern.create_reg_ex(self.pattern)
        self.regex = regex

    def update_regex(self, ctx):
        if self.pattern != ctx.object.pattern:
            self.create_regex(ctx)

    event_map = {
        (('create'), 'pre'): ('create_regex'),
        (('modify'), 'pre'): ('update_regex', 'propagate_to_text_class_properties_needed'),
        (('modify'), 'post'): ('propagate_to_text_class_properties')
    }


class BooleanProperty(Property):
    __classname__ = "cs_boolean_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "boolean"

    def getClassDefaults(self):
        result = super(BooleanProperty, self).getClassDefaults()
        result.update(
            default_value=self.default_value
        )
        for field in BooleanProperty.label.getLanguageFields().values():
            result[field.name] = getattr(self, field.name)
        return result


class DatetimeProperty(Property):
    __classname__ = "cs_datetime_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "datetime"

    def getClassDefaults(self):
        result = super(DatetimeProperty, self).getClassDefaults()
        result.update(
            with_timestamp=self.with_timestamp
        )
        return result


class IntegerProperty(Property):
    __classname__ = "cs_integer_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "integer"

    def isNumeric(self):
        return True


class FloatProperty(Property):
    __classname__ = "cs_float_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "float"

    def getClassDefaults(self):
        result = super(FloatProperty, self).getClassDefaults()
        result.update(
            is_unit_changeable=self.is_unit_changeable,
            no_decimal_positions=self.no_decimal_positions,
            no_integer_positions=self.no_integer_positions,
            unit_object_id=self.unit_object_id,
        )
        return result

    def isNumeric(self):
        return True

    def prevent_baseunit_change(self, ctx):
        if ctx.dialog.unit_object_id != ctx.object.unit_object_id:
            if len(self.DependentClassProperties) > 0:
                raise ue.Exception('cs_classification_property_unit_not_changeable_2')
            if len(self.BlockPropertyAssignments) > 0:
                raise ue.Exception('cs_classification_property_unit_not_changeable_3')
            if self.has_property_values(active_only=False):
                raise ue.Exception('cs_classification_property_unit_not_changeable_4')
            if self.value_exists():
                raise ue.Exception('cs_classification_property_unit_not_changeable')

    event_map = {
        (('modify'), 'pre'): ('prevent_baseunit_change')
    }


class FloatRangeProperty(Property):
    __classname__ = "cs_float_range_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "float_range"

    def getClassDefaults(self):
        result = super(FloatRangeProperty, self).getClassDefaults()
        result.update(
            is_unit_changeable=self.is_unit_changeable,
            no_decimal_positions=self.no_decimal_positions,
            no_integer_positions=self.no_integer_positions,
            unit_object_id=self.unit_object_id,
        )
        return result

    def isNumeric(self):
        return True

    def prevent_baseunit_change(self, ctx):
        if self.unit_object_id != ctx.object.unit_object_id:
            if len(self.DependentClassProperties) > 0:
                raise ue.Exception(
                    'cs_classification_property_unit_not_changeable_2')
            if len(self.BlockPropertyAssignments) > 0:
                raise ue.Exception(
                    'cs_classification_property_unit_not_changeable_3')
            if self.has_property_values(active_only=False):
                raise ue.Exception(
                    'cs_classification_property_unit_not_changeable_4')
            if self.value_exists():
                raise ue.Exception(
                    'cs_classification_property_unit_not_changeable')

    event_map = {
        (('modify'), 'pre'): 'prevent_baseunit_change'
    }


class MultilangProperty(Property):
    __classname__ = "cs_multi_lang_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "multilang"

    def getClassDefaults(self):
        result = super(MultilangProperty, self).getClassDefaults()
        result.update(
            data_length=self.data_length,
            multiline=self.multiline
        )
        return result

    def propagate_to_multilang_class_properties_needed(self, ctx):
        data_length = '' if self.data_length is None else str(self.data_length)
        if data_length != ctx.object.data_length:
            ctx.keep("propagate_to_multilang_class_properties_needed", "1")

    def propagate_to_multilang_class_properties(self, ctx):
        if "propagate_to_multilang_class_properties_needed" in ctx.ue_args.get_attribute_names():
            data_length = 'NULL' if self.data_length is None else self.data_length
            sqlapi.SQLupdate(
                "cs_class_property set data_length = {data_length} where catalog_property_code = '{code}'".format(
                    code=self.code, data_length=data_length
                )
            )

    event_map = {
        (('modify'), 'pre'): 'propagate_to_multilang_class_properties_needed',
        (('modify'), 'post'): 'propagate_to_multilang_class_properties'
    }


class ObjectReferenceProperty(Property):
    __classname__ = "cs_object_reference_property"
    __match__ = Property.cdb_classname >= __classname__

    @classmethod
    def getType(cls):
        return "objectref"


class BlockProperty(Property):
    __classname__ = "cs_block_property"
    __match__ = Property.cdb_classname >= __classname__

    AssignedProperties = references.Reference_N(fBlockPropertyAssignment,
                                                      fBlockPropertyAssignment.block_property_code == fBlockProperty.code)

    @classmethod
    def getType(cls):
        return "block"

    def getClassDefaults(self):
        result = super(BlockProperty, self).getClassDefaults()
        result.update(
            create_block_variants=self.create_block_variants,
            key_property_code=self.key_property_code,
            initial_expand=self.initial_expand
        )
        for field in BlockProperty.description.getLanguageFields().values():
            result[field.name] = getattr(self, field.name)
        return result

    def set_readonly(self, ctx):
        if ctx.dialog['is_multivalued'] == u'1':
            ctx.set_writeable('key_property_code')
            if ctx.dialog['key_property_code']:
                ctx.set_writeable('create_block_variants')
            else:
                ctx.set_readonly('create_block_variants')
                ctx.set('create_block_variants', u'0')
        else:
            ctx.set_readonly('create_block_variants')
            ctx.set('create_block_variants', u'0')
            ctx.set_readonly('key_property_code')
            ctx.set('key_property_code', u'')

    def propagate_to_block_class_properties_needed(self, ctx):
        key_property_code = '' if self.key_property_code is None else self.key_property_code
        if key_property_code != ctx.object.key_property_code:
            ctx.keep("propagate_to_block_class_properties_needed", "1")

    def propagate_to_block_class_properties(self, ctx):
        if "propagate_to_block_class_properties_needed" in ctx.ue_args.get_attribute_names():
            set_create_block_variants = ""
            if not self.key_property_code:
                set_create_block_variants = ", create_block_variants = 0"
            sqlapi.SQLupdate(
                "cs_class_property set key_property_code = '{key_prop_code}' {set_create_block_variants} where catalog_property_code = '{code}'".format(
                    code=self.code, key_prop_code=self.key_property_code,
                    set_create_block_variants=set_create_block_variants
                )
            )

    def _check_selected_key_property(self, ctx):
        if self.key_property_code:
            prop = Property.ByKeys(code=self.key_property_code)
            if isinstance(prop, BlockProperty):
                raise ue.Exception('cs_classification_key_property_cannot_be_block')
            if prop.is_multivalued:
                raise ue.Exception('cs_classification_key_property_cannot_be_multivalued')

    event_map = {
        (('create', 'modify', 'copy'), 'pre_mask'): 'set_readonly',
        (('create', 'modify', 'copy'), 'dialogitem_change'): 'set_readonly',
        (('create', 'modify', 'copy'), 'pre'): '_check_selected_key_property',
        (('modify'), 'pre'): 'propagate_to_block_class_properties_needed',
        (('modify'), 'post'): 'propagate_to_block_class_properties'
    }


class BlockPropertyAssignment(Object):
    __maps_to__ = "cs_block_prop_assign"
    __classname__ = "cs_block_prop_assign"

    def allow_delete(self, ctx):
        from cs.classification.classes import BlockClassProperty
        catalog_block_property = BlockProperty.KeywordQuery(code=self.block_property_code)
        if catalog_block_property:
            # check if catalog property is used in classes
            if len(BlockClassProperty.KeywordQuery(catalog_property_id=catalog_block_property.cdb_object_id)) > 0:
                raise ue.Exception("cs_classification_block_property_used_in_classes")

    def check_recursion(self, ctx):
        if self.block_property_code == self.assigned_property_code:
            raise ue.Exception("cs_classification_block_property_recursive")
        stmt = "WITH {recursive} t(assigned_property_code, block_property_code) AS ( " \
               "SELECT assigned_property_code, block_property_code FROM cs_block_prop_assign WHERE assigned_property_code='{block_prop_code}' " \
               "UNION ALL " \
               "SELECT t2.assigned_property_code, t2.block_property_code FROM cs_block_prop_assign t2 " \
               "JOIN t ON t.block_property_code = t2.assigned_property_code " \
               ") SELECT * FROM t WHERE block_property_code = '{assigned_prop_code}'".format(
            block_prop_code=self.block_property_code,
            assigned_prop_code=self.assigned_property_code,
            recursive=tools.format_recursive()
        )
        rset = sqlapi.RecordSet2(sql=stmt)
        if len(rset) > 0:
            raise ue.Exception("cs_classification_block_property_recursive")

    def preset_position(self, ctx):
        stmt = "max(position) FROM cs_block_prop_assign WHERE block_property_code='%s'" \
               % self.block_property_code
        t = sqlapi.SQLselect(stmt)
        max_position = 0
        if not sqlapi.SQLnull(t, 0, 0):
            max_position = sqlapi.SQLinteger(t, 0, 0)
        self.position = max_position + 10

    def preset_default_unit(self, ctx):
        assigned_prop = ByID(self.assigned_property_object_id)
        if assigned_prop:
            self.default_unit_object_id = assigned_prop.unit_object_id
            self.is_unit_changeable = assigned_prop.is_unit_changeable

    def set_fields_readonly(self, ctx):
        ctx.set_fields_readonly(['assigned_property_object_id'])

    def change_unit_fields(self, ctx):
        assigned_prop = ByID(self.assigned_property_object_id)
        if assigned_prop:
            if assigned_prop.unit_object_id:
                ctx.set_mandatory('default_unit_object_id')
            else:
                ctx.set_fields_readonly(['default_unit_object_id', 'is_unit_changeable'])

    def set_default_unit_object_id(self, ctx):
        assigned_prop = ByID(self.assigned_property_object_id)
        if assigned_prop and not self.default_unit_object_id:
            self.default_unit_object_id = assigned_prop.unit_object_id

    event_map = {
        (('create', 'copy'), 'pre_mask'): ('preset_position', 'preset_default_unit'),
        (('create', 'copy'), 'pre'): ('check_recursion', 'set_default_unit_object_id'),
        (('modify'), 'pre'): 'set_default_unit_object_id',
        (('delete'), 'pre'): 'allow_delete',
        (('modify'), 'pre_mask'): ('change_unit_fields', 'set_fields_readonly')
    }


type_map = {
    "text": TextProperty,
    "boolean": BooleanProperty,
    "datetime": DatetimeProperty,
    "integer": IntegerProperty,
    "float": FloatProperty,
    "float_range": FloatRangeProperty,
    "multilang": MultilangProperty,
    "objectref": ObjectReferenceProperty,
    "block": BlockProperty
}

classname_type_map = {
    "cs_text_property": "text",
    "cs_boolean_property": "boolean",
    "cs_datetime_property": "datetime",
    "cs_integer_property": "integer",
    "cs_float_property": "float",
    "cs_float_range_property": "float_range",
    "cs_multi_lang_property": "multilang",
    "cs_object_reference_property": "objectref",
    "cs_block_property": "block",
}


class PropertyValue(Object):
    __maps_to__ = "cs_property_value"
    __classname__ = "cs_property_value"

    def _get_property(self):
        from cs.classification.classes import ClassProperty
        prop = ClassProperty.ByKeys(cdb_object_id=self.property_object_id)
        if not prop:
            prop = Property.ByKeys(cdb_object_id=self.property_object_id)
        return prop

    Property = ReferenceMethods_1(Object, _get_property)

    def _value(self, new_val=None):
        attr = PropertyValue.get_value_attr(self.cdb_classname)

        if isinstance(attr, str):
            if new_val is not None:
                setattr(self, attr, new_val)
            return getattr(self, attr)
        else:
            if new_val is not None:
                for key in new_val:
                    setattr(self, key, new_val[key])
            return {key: getattr(self, key) for key in attr}

    @property
    def value(self):
        return self._value()

    @value.setter
    def value(self, val):
        return self._value(val)

    def disable_value_for_variability_class_properties(self):
        """
        Disables this property value in all variability class properties
        to avoid probably unwanted new variability model combinations
        """
        from cs.classification.classes import ClassProperty
        from cs.classification.cs_classification_propval_exc import update_excludes

        variability_class_properties = ClassProperty.KeywordQuery(
            catalog_property_id=self.property_object_id,
            for_variants=1
        )

        for class_property in variability_class_properties:
            update_excludes(class_property, True, [self.cdb_object_id])

    def disable_value_for_variability_class_properties_after_create(self, _):
        # For cs.variants: To avoid an automatic creation of new variant possibilities
        # because an catalog property get an new value activated
        # we build exclude rules in all class properties with "for_variant" == 1 for this value
        if self.is_active == 1:
            self.disable_value_for_variability_class_properties()

    def disable_value_for_variability_class_properties_after_modify(self, ctx):
        # For cs.variants: To avoid an automatic creation of new variant possibilities
        # because an catalog property get an new value activated
        # we build exclude rules in all class properties with "for_variant" == 1 for this value
        if self.is_active == 1 and ctx.previous_values.is_active == u"0":
            self.disable_value_for_variability_class_properties()

    @classmethod
    def get_value_attr(cls, value_classname):
        attr = value_type_map[value_classname_type_map[value_classname]]._value_attr
        if isinstance(attr, types.MethodType):
            attr = attr()
        return attr

    @classmethod
    def object_property_values_to_json_data(cls, cdb_object_ids=None, property_codes=None, request=None):
        in_condition = ""
        if cdb_object_ids:
            in_condition = "AND ({0})".format(tools.format_in_condition('ref_object_id', cdb_object_ids))
        if property_codes:
            in_condition = in_condition + "AND ({0})".format(tools.format_in_condition('property_code', property_codes))

        stmt = """
            select distinct property_type, property_code, datetime_value, float_value, float_value_normalized, unit_object_id, integer_value, object_reference_value, text_value
            from cs_object_property_value
            where
                property_type != 'float_range' and property_type != 'multilang' and
                (datetime_value IS NOT NULL OR float_value IS NOT NULL OR integer_value IS NOT NULL OR object_reference_value IS NOT NULL OR text_value IS NOT NULL)
                {in_condition}
        """.format(in_condition=in_condition)

        type_by_code = {}
        object_ref_ids = set()
        catalog_values = defaultdict(list)
        for object_property_value in sqlapi.RecordSet2(sql=stmt):
            type_by_code[object_property_value.property_code] = object_property_value.property_type
            value = None
            if "float" == object_property_value.property_type:
                value = {
                    "float_value": object_property_value.float_value,
                    "float_value_normalized": object_property_value.float_value_normalized,
                    "unit_object_id": object_property_value.unit_object_id,
                }
                if object_property_value.unit_object_id:
                    from cs.classification import units
                    value["unit_label"] = units.UnitCache.get_unit_label(object_property_value.unit_object_id)
                else:
                    value["unit_label"] = u""
            elif "objectref" == object_property_value.property_type:
                value = object_property_value.object_reference_value
                object_ref_ids.add(value)
            else:
                value = object_property_value[object_property_value.property_type + "_value"]
            if value:
                elem = {
                    "description": "",
                    "label": "",
                    "pos": 0,
                    "type": object_property_value.property_type,
                    "value": value
                }
                catalog_values[object_property_value.property_code].append(elem)

        if request and object_ref_ids:
            objects_by_id = tools.load_objects(object_ref_ids)
            for prop_code, prop_type in type_by_code.items():
                if "objectref" == prop_type:
                    for elem in catalog_values[prop_code]:
                        ui_link = ""
                        ui_text = ""
                        object_id = elem["value"]
                        if object_id:
                            obj = objects_by_id.get(object_id)
                            if obj:
                                ui_text = obj.GetDescription()
                                ui_link = tools.get_obj_link(request, obj)
                            else:
                                ui_text = "** Object not found: %s **" % object_id
                        elem["addtl_value"] = {"ui_link": ui_link, "ui_text": ui_text}

        for prop_code, elems in catalog_values.items():
            prop_type = type_by_code[prop_code]
            sort_func = lambda entry: (entry["pos"], entry["label"], entry["value"])
            if prop_type == 'float':
                sort_func = lambda entry: (entry["pos"], entry["value"]["float_value_normalized"])
            elif prop_type == 'float_range':
                # not supported
                sort_func = None
            elif prop_type == 'multilang':
                # not supported
                sort_func = None
            elif prop_type == 'objectref':
                sort_func = lambda entry: (entry["pos"], entry["addtl_value"]["ui_text"]) \
                    if "addtl_value" in entry \
                    else (entry["pos"], entry["value"])
            if sort_func:
                catalog_values[prop_code] = sorted(elems, key=sort_func)

        return catalog_values

    @classmethod
    def to_json_data(cls, value_objects, request=None, prop=None):

        def update_normalized(prefix, obj, value):
            value["unit_label"] = u""
            value["float_value_normalized"] = value["float_value"]

            if value["unit_object_id"]:
                from cs.classification import units
                value["unit_label"] = units.UnitCache.get_unit_label(value["unit_object_id"])

                prop_code = None
                uoi = None
                if "property_code" in obj and "norm_unit_object_id" in obj:
                    prop_code = obj["property_code"]
                    uoi = obj["norm_unit_object_id"]
                elif prop is not None:
                    prop_code = prop.code
                    uoi = prop.unit_object_id
                else:
                    return

                # normalize value
                if prefix + "unit_object_id" in obj and obj[prefix + "unit_object_id"]:
                    value["float_value_normalized"] = units.normalize_value(
                        value["float_value"],
                        value["unit_object_id"],
                        uoi,
                        prop_code
                    )

        result = []
        for obj in value_objects:
            value = obj.value

            if obj.cdb_classname == "cs_float_property_value":
                update_normalized("", obj, value)
            elif obj.cdb_classname == "cs_float_range_property_value":
                if "min_float_value" in value:
                    value = FloatRangePropertyValue.convert_record(value)
                update_normalized("min_", obj, value["min"])
                update_normalized("max_", obj, value["max"])
            elif obj.cdb_classname == "cs_multilang_property_value":
                # build same structure as ObjectPropertyValue uses for multi language properties
                multi_langvalue = {}
                for k, v in value.items():
                    if v:
                        iso_code = k[-2:]
                        multi_langvalue[iso_code] = {'iso_language_code': iso_code,
                                                     'text_value': v}
                value = multi_langvalue
            elem = {
                "description": tools.get_label("description", obj),
                "label": tools.get_label("label", obj),
                "pos": obj.pos if obj.pos else 0,
                "type": value_classname_type_map[obj.cdb_classname],
                "value": value
            }
            result.append(elem)

        if value_objects:
            classname = value_objects[0].cdb_classname  # assuming all value objects are of the same type

            # add links and text for object refs
            if classname == "cs_object_ref_property_value" and request:
                object_ids = [r["value"] for r in result if r["value"]]
                objects_by_id = tools.load_objects(object_ids)
                for res in result:
                    ui_link = ""
                    ui_text = ""
                    object_id = res["value"]
                    if object_id:
                        obj = objects_by_id.get(object_id)
                        if obj:
                            ui_text = obj.GetDescription()
                            ui_link = tools.get_obj_link(request, obj)
                        else:
                            ui_text = "** Object not found: %s **" % object_id
                    res["addtl_value"] = {"ui_link": ui_link,
                                          "ui_text": ui_text}

            # Sorting
            sort_func = lambda entry: (entry["pos"], entry["label"], entry["value"])
            if classname == 'cs_float_property_value':
                sort_func = lambda entry: (entry["pos"], entry["value"]["float_value_normalized"])
            elif classname == 'cs_float_range_property_value':
                sort_func = lambda entry: (entry["pos"], entry["value"]["min"]["float_value_normalized"])
            elif classname == 'cs_multilang_property_value':
                language = i18n.default()
                sort_func = lambda entry: (entry["pos"], entry["value"][language]["text_value"]) \
                    if language in entry["value"] \
                    else (entry["pos"], '')
            elif classname == 'cs_object_ref_property_value':
                sort_func = lambda entry: (entry["pos"], entry["addtl_value"]["ui_text"]) \
                    if "addtl_value" in entry \
                    else (entry["pos"], entry["value"])
            if sort_func:
                result = sorted(result, key=sort_func)
        return result

    def set_has_enum_values(self, ctx):
        update_prop = False
        delete_default_value = True
        has_values_hint = False

        if ctx.action in ('create', 'copy') and self.is_active:
            update_prop = True
            has_values_hint = True
        elif ctx.action == 'delete':
            update_prop = True
            delete_default_value = True
        elif ctx.action == 'modify' and "activation_has_not_changed" not in ctx.ue_args.get_attribute_names():
            update_prop = True
            delete_default_value = False if self.is_active else True
            has_values_hint = True if self.is_active else False

        if update_prop or delete_default_value:
            prop = self.Property

        if delete_default_value:
            prop.reset_default_value(self.cdb_object_id)

        if update_prop:
            prop.set_has_enum_values(has_values_hint=has_values_hint)

    def handle_activation_changed(self, ctx):
        if ctx.object.is_active == self.is_active:
            ctx.keep("activation_has_not_changed", "0")

    def delete_excludes(self, ctx):
        del_prop_id = self.cdb_object_id
        with transactions.Transaction():
            delete_stmnt = sqlapi.SQLdelete("from cs_property_value_exclude where property_value_id='%s'" %
                                            self.cdb_object_id)

    def check_parent_relation(self, ctx, error_message_id):
        if not ctx.parent:
            return
        if self.property_object_id != ctx.parent.cdb_object_id:
            # propery value can only be modified in correct parent context
            raise ue.Exception(error_message_id)

    def check_parent_relation_for_delete(self, ctx):
        self.check_parent_relation(ctx, "cs_classification_property_value_not_deletable")

    def check_parent_relation_for_modify(self, ctx):
        self.check_parent_relation(ctx, "cs_classification_property_value_not_modifiable")

    def check_uses_for_delete(self, ctx):
        catalog_property_id = getattr(self.Property, "catalog_property_id", "")

        property_ids = [self.property_object_id, catalog_property_id] if catalog_property_id else [
            self.property_object_id]

        if self.cdb_classname in ['cs_float_range_property_value', 'cs_multilang_property_value']:
            value_exp = self.build_double_value_exp()
        else:
            value_exp = self.build_class_value_exp()

        double_check_stmt = "SELECT property_object_id FROM cs_property_value WHERE {prop_ids} {value_exp}".format(
            prop_ids=tools.format_in_condition('property_object_id', property_ids),
            value_exp=value_exp
        )
        if len(sqlapi.RecordSet2(sql=double_check_stmt)) > 1:
            return

        prop_code = self.Property.code

        class_prop_stmt = "SELECT DISTINCT code FROM cs_class_property where catalog_property_code = '{prop_code}'".format(
            prop_code=prop_code
        )

        rset = sqlapi.RecordSet2(sql=class_prop_stmt)

        property_codes = [r.code for r in rset]
        property_codes.append(prop_code)

        if self.cdb_classname in ['cs_float_range_property_value', 'cs_multilang_property_value']:
            value_exp = self.build_class_value_exp()

        self.has_object_classifications(property_codes, value_exp)

    def has_object_classifications(self, property_codes, value_exp):
        if self.cdb_classname in ['cs_float_range_property_value', 'cs_multilang_property_value']:
            value_exp = self.build_class_value_exp()

        for prop_codes in tools.chunk(property_codes, 1000):
            object_prop_stmt = "SELECT property_path FROM cs_object_property_value where {prop_codes} {value_exp}".format(
                prop_codes=tools.format_in_condition('property_code', prop_codes),
                value_exp=value_exp
            )
            if len(sqlapi.RecordSet2(sql=object_prop_stmt)) > 0:
                raise ue.Exception("cs_classification_property_value_used_in_classes")

    event_map = {
        ('delete', 'pre'): ('check_parent_relation_for_delete', 'check_uses_for_delete'),
        ('delete', 'post'): ('delete_excludes'),
        ('modify', 'pre_mask'): ('check_parent_relation_for_modify'),
        ('modify', 'pre'): ('handle_activation_changed'),
        ('modify', 'post'): ('disable_value_for_variability_class_properties_after_modify'),
        (('create', 'copy', 'delete', 'modify'), 'post'): ('set_has_enum_values'),
        (('create', 'copy'), 'post'): ('disable_value_for_variability_class_properties_after_create')
    }


@sig.connect(PropertyValue, list, "cs_classification_values_activ", "now")
def _activate_property_values(property_values, ctx):
    if not ctx.parent:
        return
    prop = ByID(ctx.parent.cdb_object_id)

    # For cs.variants: To avoid an automatic creation of new variant possibilities
    # because an catalog property get an new value activated
    # we build exclude rules in all class properties with "for_variant" == 1 for this value
    if isinstance(prop, Property):
        # Filter values which are already active?
        for each in property_values:
            if each.is_active != 1:
                each.disable_value_for_variability_class_properties()

    # Doing this after extension for cs.variants
    # because the extension has to check if property value is already activated
    _set_property_values_active_state(prop, property_values, 1)
    ctx.refresh_tables(['cs_property_value'])


@sig.connect(PropertyValue, list, "cs_classification_values_inactiv", "now")
def _deactivate_property_values(property_values, ctx):
    if not ctx.parent:
        return
    prop = ByID(ctx.parent.cdb_object_id)
    _set_property_values_active_state(prop, property_values, 0)
    ctx.refresh_tables(['cs_property_value'])


def _set_property_values_active_state(prop, property_values, active):
    from cs.classification.classes import ClassProperty
    from cs.classification.cs_classification_propval_exc import update_excludes

    if not prop:
        return

    if not prop.CheckAccess("save"):
        raise ue.Exception("cs_classification_external_class_not_modifiable")  # change error message

    regex = re.compile(prop.regex) if active and prop.regex else None
    pattern_violation = False

    property_value_ids = []
    exclude_ids = []
    for property_value in property_values:
        if active and regex:
            if regex.match(property_value.text_value) is None:
                pattern_violation = True
                continue
        if prop.cdb_object_id == property_value.property_object_id:
            property_value_ids.append(property_value.cdb_object_id)
        else:
            exclude_ids.append(property_value.cdb_object_id)

    with Transaction():
        if property_value_ids:
            sqlapi.SQLupdate(
                "cs_property_value SET is_active = {} where {}".format(
                    active,
                    tools.format_in_condition("cdb_object_id", property_value_ids)
                )
            )
            if not active:
                if prop.default_value_oid in property_value_ids:
                    prop.reset_default_value(prop.default_value_oid)

        if exclude_ids and isinstance(prop, ClassProperty):
            update_excludes(prop, not active, exclude_ids)

        prop.set_has_enum_values()

    if pattern_violation:
        raise ue.Exception("cs_classification_invalid_format_on_activation", prop.pattern)


class IntegerPropertyValue(PropertyValue):
    __classname__ = "cs_integer_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    _value_attr = "integer_value"

    @classmethod
    def getType(cls):
        return "integer"

    def build_class_value_exp(self):
        value_exp = "AND integer_value = {integer_value}".format(
            integer_value=self.integer_value,
        )
        return value_exp


class TextPropertyValue(PropertyValue):
    __classname__ = "cs_text_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    _value_attr = "text_value"

    @classmethod
    def getType(cls):
        return "text"

    def validate_pattern_value(self, ctx):
        if self.is_active:
            text_field = self.text_value
            if self.property_object_id:
                parent_obj_id = self.property_object_id
                parent_object = ByID(parent_obj_id)
                if parent_obj_id:
                    regex_str = parent_object.regex
                    if regex_str:
                        regex = re.compile(regex_str)
                        if regex.match(text_field) is None:
                            raise ue.Exception("cs_classification_invalid_format", parent_object.pattern)

    def build_class_value_exp(self):
        value_exp = "AND text_value='{text_value}'".format(
            text_value=sqlapi.quote(self.text_value)
        )
        return value_exp

    event_map = {
        (('create', 'copy', 'modify'), 'pre'): ('validate_pattern_value')
    }


class DatetimePropertyValue(PropertyValue):
    __classname__ = "cs_datetime_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    _value_attr = "datetime_value"

    @classmethod
    def getType(cls):
        return "datetime"

    def build_class_value_exp(self):
        value_exp = "AND datetime_value={datetime_value}".format(
            datetime_value=cdbwrapc.SQLdate_literal(self.datetime_value)
        )
        return value_exp


class FloatPropertyValue(PropertyValue):
    __classname__ = "cs_float_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    _value_attr = ["float_value", "unit_object_id"]

    @classmethod
    def getType(cls):
        return "float"

    def _check_unit(self, ctx):
        if self.property_object_id:
            prop = ByID(self.property_object_id)
            if prop:
                if prop.unit_object_id and not self.unit_object_id:
                    raise ue.Exception("cs_classification_err_unit_required")

    def _disable_unit(self, ctx):
        if ctx.dialog.property_object_id:
            prop = ByID(ctx.dialog.property_object_id)
            if prop:
                if not prop.unit_object_id:
                    ctx.set_readonly("unit_object_id")

    def _handle_unit(self, ctx):
        if ctx.dialog.property_object_id:
            prop = ByID(ctx.dialog.property_object_id)
            if prop:
                if prop.unit_object_id:
                    self.unit_object_id = prop.unit_object_id
                else:
                    ctx.set_readonly("unit_object_id")

    def build_class_value_exp(self):
        rel_tol = 1e-09

        value_exp = "and float_value > {float_lower} and float_value < {float_upper} " \
                    "and unit_object_id = '{unit_object_id}'".format(
            float_lower=self.float_value * (1 - rel_tol),
            float_upper=self.float_value * (1 + rel_tol),
            unit_object_id=sqlapi.quote(self.unit_object_id)
        )
        return value_exp

    event_map = {
        (('modify', 'query', 'requery'), 'pre_mask'): ('_disable_unit'),
        (('copy', 'create'), 'pre_mask'): ('_handle_unit'),
        (('copy', 'create', 'modify'), 'pre'): ('_check_unit')

    }


class FloatRangePropertyValue(PropertyValue):
    __classname__ = "cs_float_range_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    _value_attr = ["min_float_value", "min_unit_object_id",
                   "max_float_value", "max_unit_object_id"]

    @classmethod
    def getType(cls):
        return "float_range"

    def _check_order(self, ctx):
        from cs.classification.units import normalize_value

        if not self.min_float_value or not self.max_float_value:
            return

        normalized_min_value = self.min_float_value
        normalized_max_value = self.max_float_value

        if self.min_unit_object_id or self.max_unit_object_id:
            prop = ByID(self.property_object_id)
            normalized_min_value = normalize_value(
                self.min_float_value, self.min_unit_object_id, prop.unit_object_id, prop.code
            )
            normalized_max_value = normalize_value(
                self.max_float_value, self.max_unit_object_id, prop.unit_object_id, prop.code
            )

        if normalized_min_value is not None and normalized_max_value is not None and normalized_min_value > normalized_max_value:
            raise ue.Exception('cs_float_range_min_max_error')

    def _check_unit(self, ctx):
        if self.property_object_id:
            prop = ByID(self.property_object_id)
            if prop and prop.unit_object_id:
                if self.min_float_value and not self.min_unit_object_id:
                    raise ue.Exception("cs_classification_err_unit_required")
                if self.max_float_value and not self.max_unit_object_id:
                    raise ue.Exception("cs_classification_err_unit_required")

    def _disable_unit(self, ctx):
        if ctx.dialog.property_object_id:
            prop = ByID(ctx.dialog.property_object_id)
            if prop:
                if not prop.unit_object_id:
                    self.min_unit_object_id = prop.unit_object_id
                    self.max_unit_object_id = prop.unit_object_id

    def _handle_unit(self, ctx):
        if ctx.dialog.property_object_id:
            prop = ByID(ctx.dialog.property_object_id)
            if prop:
                if prop.unit_object_id:
                    self.min_unit_object_id = prop.unit_object_id
                else:
                    ctx.set_readonly("min_unit_object_id")

                if prop.unit_object_id:
                    self.max_unit_object_id = prop.unit_object_id
                else:
                    ctx.set_readonly("max_unit_object_id")

    def _set_empty_value(self, ctx):

        if self.max_float_value is None and self.min_float_value is not None:
            self.max_float_value = self.min_float_value
            self.max_unit_object_id = self.min_unit_object_id

        if self.min_float_value is None and self.max_float_value is not None:
            self.min_float_value = self.max_float_value
            self.min_unit_object_id = self.max_unit_object_id

    def _value(self, new_val=None):
        if new_val is not None:
            for key in new_val:
                setattr(self, key, new_val[key])
        return self.convert_record(self)

    @classmethod
    def convert_record(cls, record):
        return {
            "min": {
                'float_value': record["min_float_value"],
                'range_identifier': "min",
                'unit_object_id': record["min_unit_object_id"]
            },
            "max": {
                'float_value': record["max_float_value"],
                'range_identifier': "max",
                'unit_object_id': record["max_unit_object_id"]
            }
        }

    def build_class_value_exp(self):
        rel_tol = 1e-09
        value_exp = "AND float_value > {min_float_lower} AND float_value < {min_float_upper} AND " \
                    "unit_object_id='{min_unit_object_id}' AND range_identifier='min' OR " \
                    "float_value > {max_float_lower} AND float_value < {max_float_upper} AND " \
                    "unit_object_id='{max_unit_object_id}' AND range_identifier='max' " \
                    "GROUP BY property_path, ref_object_id HAVING count(property_path) > 1".format(
            min_float_lower=self.min_float_value * (1 - rel_tol),
            min_float_upper=self.min_float_value * (1 + rel_tol),
            min_unit_object_id=sqlapi.quote(self.min_unit_object_id),
            max_float_lower=self.max_float_value * (1 - rel_tol),
            max_float_upper=self.max_float_value * (1 + rel_tol),
            max_unit_object_id=sqlapi.quote(self.max_unit_object_id),
        )
        return value_exp

    def build_double_value_exp(self):
        rel_tol = 1e-09
        double_value_exp = "and min_float_value > {min_float_lower} and min_float_value < {min_float_upper} " \
                           "and min_unit_object_id = '{min_unit_object_id}' " \
                           "and max_float_value > {max_float_lower} and max_float_value < {max_float_upper} " \
                           "and max_unit_object_id = '{max_unit_object_id}'".format(
            min_float_lower=self.min_float_value * (1 - rel_tol),
            min_float_upper=self.min_float_value * (1 + rel_tol),
            min_unit_object_id=sqlapi.quote(self.min_unit_object_id),
            max_float_lower=self.max_float_value * (1 - rel_tol),
            max_float_upper=self.max_float_value * (1 + rel_tol),
            max_unit_object_id=sqlapi.quote(self.max_unit_object_id)
        )
        return double_value_exp

    event_map = {
        (('modify', 'query', 'requery'), 'pre_mask'): ('_disable_unit'),
        (('copy', 'create'), 'pre_mask'): ('_handle_unit'),
        (('copy', 'create', 'modify'), 'pre'): ('_check_order', '_check_unit', '_set_empty_value')
    }


class MultilangPropertyValue(PropertyValue):
    __classname__ = "cs_multilang_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    @classmethod
    def _value_attr(cls):
        return [
            field.name
            for field in MultilangPropertyValue.multilang_value.getLanguageFields().values()
        ]

    @classmethod
    def getType(cls):
        return "multilang"

    def build_class_value_exp(self):
        languages = [i18n.default()] + i18n.FallbackLanguages()
        lang_used_exp = "AND "
        for lang in languages:
            lang_used_exp += "(text_value='{value}' AND iso_language_code='{lang}') OR ".format(
                lang=sqlapi.quote(lang),
                value=sqlapi.quote(self["multilang_value_{lang}".format(lang=lang)])
            )
        lang_used_exp = lang_used_exp[:-4]
        return lang_used_exp

    def build_double_value_exp(self):
        languages = [i18n.default()] + i18n.FallbackLanguages()
        double_value_exp = ""
        for lang in languages:
            double_value_exp += "AND multilang_value_{lang}='{value}'".format(
                lang=sqlapi.quote(lang),
                value=sqlapi.quote(self["multilang_value_{lang}".format(lang=lang)])
            )
        return double_value_exp


class ObjectRefPropertyValue(PropertyValue):
    __classname__ = "cs_object_ref_property_value"
    __match__ = PropertyValue.cdb_classname >= __classname__

    _value_attr = "object_reference_value"

    @classmethod
    def getType(cls):
        return "objectref"

    def build_class_value_exp(self):
        value_exp = "and object_reference_value='{object_reference_value}'".format(
            object_reference_value=sqlapi.quote(self.object_reference_value)
        )
        return value_exp


value_type_map = {
    "text": TextPropertyValue,
    "datetime": DatetimePropertyValue,
    "integer": IntegerPropertyValue,
    "float": FloatPropertyValue,
    "float_range": FloatRangePropertyValue,
    "multilang": MultilangPropertyValue,
    "objectref": ObjectRefPropertyValue
}

value_classname_type_map = {
    "cs_text_property_value": "text",
    "cs_datetime_property_value": "datetime",
    "cs_integer_property_value": "integer",
    "cs_float_property_value": "float",
    "cs_float_range_property_value": "float_range",
    "cs_multilang_property_value": "multilang",
    "cs_object_ref_property_value": "objectref"
}


class PropertyFolder(Object):
    __maps_to__ = "cs_property_folder"
    __classname__ = "cs_property_folder"

    # new catalog properties are automatically assigned to the 'All Properties' Folder
    ALL_PROPERTIES_FOLDER = 'bd6c0540-dc7b-11e6-8c8d-28d24433bf35'


class PropertyFolderAssignment(Object):
    __maps_to__ = "cs_property_folder_assignment"
    __classname__ = "cs_property_folder_assignment"
