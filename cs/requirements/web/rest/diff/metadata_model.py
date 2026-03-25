# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import logging
from _cdbwrapc import SQL_DATE, SQL_FLOAT, SQL_INTEGER
from cdb import fls, sig, sqlapi, util, ue
from cdb.objects.core import ByID, ClassRegistry
from cdb.platform.mom.fields import (DDField, DDMultiLangField,
                                     DDMultiLangFieldBase,
                                     DDMultiLangMappedField)
from cdbwrapc import CDBClassDef
from cs.requirements import (RQMSpecification, RQMSpecObject, TargetValue,
                             rqm_utils)

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


LOG = logging.getLogger(__name__)
METADATA_CRITERION_DIFF_PLUGIN_ID = 'metadata'


class DiffMetadataAPIModel (object):

    def __init__(self, left_cdb_object_id, right_cdb_object_id):
        self.left_cdb_object_id = left_cdb_object_id
        self.right_cdb_object_id = right_cdb_object_id
        if right_cdb_object_id == "null":
            # Right element is empty
            self.left_object = ByID(self.left_cdb_object_id)
            self.right_object = None
            self.empty_element = True
        else:
            if left_cdb_object_id == "null":
                # Left element is empty
                self.left_object = None
                self.right_object = ByID(self.right_cdb_object_id)
                self.empty_element = True
            else:
                self.left_object = ByID(self.left_cdb_object_id)
                self.right_object = ByID(self.right_cdb_object_id)
                self.empty_element = False

    def check_access(self):
        if (
            (
                self.empty_element and
                self.left_object and
                self.left_object.CheckAccess('read')
            ) or
            (
                self.empty_element and
                self.right_object and
                self.right_object.CheckAccess('read')
            ) or
            (
                self.left_object and self.left_object.CheckAccess('read') and
                self.right_object and self.right_object.CheckAccess('read')
            )
        ):
            access_granted = True
        else:
            access_granted = False
        return access_granted

    @classmethod
    def get_blacklisted_fields(cls):
        black_list = util.PersonalSettings().getValueOrDefault(
            "cs.requirements.diff",
            "attribute_filter_out_list",
            u"cdb_cdate, reqif_id, cdb_mdate, cdb_object_id, ce_baseline_id, ce_baseline_cdate, specification_object_id, template_oid, ce_baseline_name, ce_baseline_creator, ce_baseline_comment, ce_baseline_origin_id, parent_object_id, ce_baseline_object_id, subject_type, position, sortorder, maxno,ce_baseline_info_tag"
        )
        black_list_array = [black_listed.strip() for black_listed in black_list.split(',')]
        return black_list_array

    @classmethod
    def fast_metadata_diff_ids(cls, left_spec, right_spec, settings, additional_conditions=None):
        """ Searches all objects (their ids) that have different attribute values
        compared to their counterpart within the given
        left and right specification object contexts.

        Attributes used for comparison are controlled by _metadata_diff_fields

        Per default: only requirement objects are searched,
            via settings also target values can be searched as well.
        """
        fls.allocate_license('RQM_070')
        if settings is None:
            settings = {}
        if additional_conditions is None:
            additional_conditions = {}
        languages = settings.get('languages', [])
        attributes = ['cdb_object_id', 'requirement_object_id', 'pos']
        criterions_per_class = settings.get('criterions_per_class', {})
        entities_to_search_for = [
            x for x in [
                RQMSpecification,
                RQMSpecObject,
                TargetValue
            ] if (
                x.__maps_to__ in criterions_per_class and
                METADATA_CRITERION_DIFF_PLUGIN_ID in criterions_per_class[x.__maps_to__]
            )
        ]
        changed_ids = set()
        changed_req_ids = set()
        changed_tv_ids = set()
        errors = []
        warnings = []
        empty = "'', chr(1)" if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE else "''"
        for entity in entities_to_search_for:
            additional_condition = additional_conditions.get(entity.__maps_to__, "1=1")
            cdef = CDBClassDef(entity.__classname__)
            class_names = [entity.__classname__] + list(cdef.getSubClassNames(True))
            fields = {}
            for class_name in class_names:
                clazz = ClassRegistry().findByClassname(class_name)
                metadata_errors, metadata_warnings, metadata_fields = DiffMetadataAPIModel._metadata_diff_fields(
                    languages=languages,
                    all_fields=clazz.GetFieldNames(addtl_field_type=any),
                    classname=class_name,
                    without_mapped=True
                )
                errors += metadata_errors
                warnings += metadata_warnings
                fields.update(metadata_fields)
            attributes_to_compare_condition = []
            for field_name in sorted(fields.keys()):
                field_sql_type = fields.get(field_name).get('sqltype')
                right_side_fieldname= (
                    f"CAST(right_side.{field_name} as varchar)"
                    if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES else 
                    f"right_side.{field_name}"
                )
                right_side_non_empty_stmt = (
                    f" AND {right_side_fieldname} NOT IN ({empty})"
                    if field_sql_type not in (
                        SQL_INTEGER,
                        SQL_FLOAT,
                        SQL_DATE
                    ) else ''
                )
                left_side_fieldname= (
                    f"CAST(left_side.{field_name} as varchar)"
                    if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES else 
                    f"left_side.{field_name}"
                )
                left_side_non_empty_stmt = (
                    f" AND {left_side_fieldname} NOT IN ({empty})"
                    if field_sql_type not in (
                        SQL_INTEGER,
                        SQL_FLOAT,
                        SQL_DATE
                    ) else ''
                )
                attributes_to_compare_condition.append(
                    f"(left_side.{field_name} != right_side.{field_name})"
                )
                attributes_to_compare_condition.append(
                    f"""
                        (
                                left_side.{field_name} IS NULL
                            AND
                                right_side.{field_name} IS NOT NULL
                            {right_side_non_empty_stmt}
                        )
                    """
                )
                attributes_to_compare_condition.append(
                    f"""
                        (
                                right_side.{field_name} IS NULL
                            AND
                                left_side.{field_name} IS NOT NULL
                            {left_side_non_empty_stmt}
                        )
                    """
                )
            view = entity.__maps_to_view__
            columns = ",".join([
                f"right_side.{attr} {attr}"
                if hasattr(entity, attr) else
                f"NULL {attr}"
                for attr in attributes
            ])
            left_spec_id = left_spec.cdb_object_id
            right_spec_id = right_spec.cdb_object_id
            attributes_to_compare_condition = " OR ".join(attributes_to_compare_condition)
            stmt = f"""
                SELECT
                    {columns} from {view} left_side, {view} right_side
                WHERE
                    left_side.specification_object_id='{left_spec_id}'
                AND
                    left_side.ce_baseline_origin_id=right_side.ce_baseline_origin_id
                AND
                    right_side.specification_object_id='{right_spec_id}'
                AND
                    {additional_condition}
                AND
                    ({attributes_to_compare_condition})
            """
            if entity == RQMSpecification:
                stmt = f"""
                SELECT
                    {columns} from {view} left_side, {view} right_side
                WHERE
                    left_side.cdb_object_id='{left_spec_id}'
                AND
                    left_side.ce_baseline_origin_id=right_side.ce_baseline_origin_id
                AND
                    right_side.cdb_object_id='{right_spec_id}'
                AND
                    {additional_condition}
                AND
                    ({attributes_to_compare_condition})
            """

            rs = sqlapi.RecordSet2(sql=stmt)
            for r in rs:
                cdb_object_id = r['cdb_object_id']
                requirement_object_id = r['requirement_object_id']
                tv_pos_id = r['pos']
                if requirement_object_id:
                    changed_tv_ids.add((cdb_object_id, requirement_object_id, tv_pos_id))
                    changed_req_ids.add(requirement_object_id)
                    changed_ids.add(requirement_object_id)
                else:
                    changed_req_ids.add(cdb_object_id)
                changed_ids.add(cdb_object_id)
        return {
            'errors': errors,
            'warnings': warnings,
            'changed_req_ids': changed_req_ids,
            'changed_tv_ids': changed_tv_ids,
            'changed_ids': changed_ids
        }

    @classmethod
    def _metadata_diff_fields(cls, languages, all_fields, classname, without_mapped=False):
        cdef = CDBClassDef(classname)
        filter_out = util.PersonalSettings().getValueOrDefault(
            "cs.requirements.diff",
            "attribute_filter_out_list",
            u"""
            cdb_cdate,
            reqif_id,
            cdb_mdate,
            cdb_object_id,
            ce_baseline_id,
            ce_baseline_cdate,
            specification_object_id,
            requirement_object_id,
            template_oid,
            ce_baseline_name,
            ce_baseline_creator,
            ce_baseline_comment,
            ce_baseline_origin_id,
            parent_object_id,
            ce_baseline_object_id,
            subject_type,
            position,
            sortorder,
            maxno,
            ce_baseline_info_tag"""
        )
        filter_out = set([filtered_oud.strip() for filtered_oud in filter_out.split(',')])
        fields = {}
        errors = []
        warnings = []
        for fieldname in all_fields:
            attribute_definition = cdef.getAttributeDefinition(fieldname)
            if attribute_definition is None:
                msg = str(ue.Exception("cdbrqm_diff_metadata_plugin_unknown_db_rel_column", classname, fieldname))
                warnings.append(msg) # will be presented to the user in frontend
                LOG.warning(msg) # will be logged
                continue # ignore for processing but show a warning to the user and in LOG
            ddfield = DDField.ByKeys(classname=classname, field_name=fieldname)
            attribute_language = attribute_definition.getIsoLang()
            if (
                fieldname not in filter_out and
                (not attribute_language or attribute_language in languages) and
                not attribute_definition.is_joined(True) and
                not (attribute_definition.is_mapped() and attribute_language) and
                not (isinstance(ddfield, DDMultiLangMappedField) and attribute_language) and
                (not isinstance(ddfield, DDMultiLangFieldBase) or ddfield.MultiLangField is None) and
                not isinstance(ddfield, DDMultiLangField)
            ):
                if not without_mapped and hasattr(ddfield, 'ma_target_map_key') and ddfield.ma_target_map_key:
                    filter_out.add(ddfield.ma_target_map_key)
                if not without_mapped or not attribute_definition.is_mapped(True):
                    fields[fieldname] = {
                        'label': attribute_definition.getLabel(),
                        'sqltype': attribute_definition.getSQLType()
                    }
        return errors, warnings, {
            fname: value for (fname, value) in fields.items() if fname not in filter_out
        }

    @classmethod
    def metadata_diff(cls, left_object, right_object, languages):
        requirement_obj = left_object if left_object else right_object
        _errors, _warnings, fields = cls._metadata_diff_fields(
            languages=languages,
            all_fields=requirement_obj.GetFieldNames(addtl_field_type=any),
            classname=requirement_obj.GetClassname()
        )
        if left_object and right_object:
            result_dict = {}
            result_dict_no_changes = {}
            total_valid_attributes = 0
            same_value_attributes = 0
            for fieldname, value in fields.items():
                label = value.get('label')
                total_valid_attributes = total_valid_attributes + 1
                left_value = getattr(left_object, fieldname) if left_object else ""
                right_value = getattr(right_object, fieldname) if right_object else ""
                if left_value != right_value:
                    # There is a difference
                    result_dict[fieldname] = {
                        "label": "{}".format(label),
                        "left": rqm_utils.date_to_str(left_value),
                        "right": rqm_utils.date_to_str(right_value)
                    }
                else:
                    same_value_attributes = same_value_attributes + 1
                    result_dict_no_changes[fieldname] = {
                        "label": "{}".format(label),
                        "right": rqm_utils.date_to_str(right_value)
                    }
            if same_value_attributes == total_valid_attributes:
                return result_dict_no_changes
            else:
                return result_dict
        else:
            result_single_requirement = {}
            for fieldname, value in fields.items():
                label = value.get('label')
                attribute_value = getattr(requirement_obj, fieldname)
                result_single_requirement[fieldname] = {
                    "label": "{}".format(label),
                    "right": rqm_utils.date_to_str(attribute_value)
                }
            return result_single_requirement

    def diff(self, languages):
        result_dict = DiffMetadataAPIModel.metadata_diff(self.left_object, self.right_object, languages)
        return result_dict


@sig.connect(RQMSpecification, "rqm_diff_plugins", "init")
def register_diff_plugin(registry):
    registry.register_criterion([
        RQMSpecification,
        RQMSpecObject,
        TargetValue
    ], METADATA_CRITERION_DIFF_PLUGIN_ID, util.get_label('web.rqm_diff.metadata'))


@sig.connect(RQMSpecification, "rqm_diff_plugins", "search", 'metadata')
def search(left_spec, right_spec, settings):
    return DiffMetadataAPIModel.fast_metadata_diff_ids(left_spec, right_spec, settings)
