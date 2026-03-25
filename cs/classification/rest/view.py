
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module rest

This is the documentation for the rest module.
"""

import json
import logging
import webob

from copy import deepcopy

import cdbwrapc

from cdb import ue, util, sqlapi
from cdb import i18n
from cdb.objects import ByID
from cdb.objects import core
from cs.platform.web import root
from cs.platform.web.rest import get_collection_app, support
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.uisupport.resttable import RestTableDefWrapper

import cs.classification.solr
from cs.classification import api, catalog, computations, ObjectClassification, tools
from cs.classification.classes import ClassificationClass, ClassProperty, \
    ClassPropertyValueExclude
from cs.classification.object_classification import ClassificationUpdater
from cs.classification.classification_data import ClassificationData
from cs.classification.util import add_file_data,  is_property_value_found
from cs.classification.validation import ClassificationValidator, \
    ClassificationValidationException

from cs.classification.rest import main
from cs.classification.rest import model as rest_models
from cs.classification.rest import utils
from cs.classification.solr import SolrCommandException

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

LOG = logging.getLogger(__name__)


@main.ClassificationInternalApp.json(model=core.Object)
def _system_classification(obj, request):
    if obj is None or not obj.CheckAccess("read"):
        raise webob.exc.HTTPForbidden
    try:
        for_create = 'true' == request.params.get('for_create', 'false')
        data = ClassificationData(obj, request=request, check_rights=True, filter_write_access=for_create)
        values, metadata, values_checksum = data.get_classification()

        assigned_classes_not_deletable = []
        assigned_classes_rest = {}
        for assigned_class in data.get_assigned_classes_objs():
            if assigned_class.cdb_objektart:
                assigned_classes_rest[assigned_class.class_code] = utils.render_object_classification_to_json(
                    request, assigned_class
                )
            if assigned_class.HasField('not_deletable') and assigned_class.not_deletable:
                assigned_classes_not_deletable.append(assigned_class.class_code)
        metadata['assigned_classes_not_deletable'] = assigned_classes_not_deletable
        metadata['deleted_classes'] = []
        metadata['deleted_properties'] = []

        if for_create:
            acc_info = ClassificationData.get_access_info(
                data.get_assigned_classes(), dd_classname=obj.GetClassname(),
                for_create=True, add_base_classes=True
            )
            assigned_classes_to_copy = []
            copy_infos = ClassificationClass.get_copy_info(
                dd_classname=obj.GetClassname(), class_codes=data.get_assigned_classes()
            )
            values_checksum = None
            for assigned_class in data.get_assigned_classes():
                if copy_infos.get(assigned_class):
                    assigned_classes_to_copy.append(assigned_class)
            if len(assigned_classes_to_copy) != len(data.get_assigned_classes()):
                new_metadata = ClassificationData.remove_properties(
                    assigned_classes_to_copy, values, True, check_rights=True
                )
                metadata['assigned_classes'] = assigned_classes_to_copy
                metadata['classes_view'] = new_metadata['classes_view']
        else:
            acc_info = ClassificationData.get_access_info(
                data.get_assigned_classes(), obj=obj, for_create=False, add_base_classes=True
            )

        return {
            "system:classification": {
                "metadata": metadata,
                "values": utils.ensure_json_serialiability(values),
                "values_checksum": values_checksum,
                "acc_info": acc_info,
                "assigned_classes_with_olc": assigned_classes_rest,
                "rule_results": ClassificationValidator.calculate_rules(
                    values, prop_codes_for_evaluation=None, ignore_errors=True
                ),
                "prop_codes_for_validation": ClassificationValidator.get_property_codes_for_validation(
                    list(metadata["classes"]), list(values)
                ),
                "catalog_configs": utils.get_property_catalog_configs(request, metadata)
            }
        }
    except Exception as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))
    raise webob.exc.HTTPNoContent


@main.ClassificationByIDApp.json(model=core.Object, request_method="GET")
def default_view_by_id(obj, request):
    collection_app = root.get_v1(request).child("collection")
    obj_rest_name = support.rest_name(obj)
    if obj_rest_name is None:
        raise webob.exc.HTTPNotFound

    result = request.view(
        obj,
        app=collection_app.child(GenericApp, rest_name=obj_rest_name)
    )
    return result


@main.ClassificationInternalApp.json(model=rest_models.ClassificationClassModel, request_method="POST")
def class_info(model, request):
    from cdb import kernel
    from cdb import sig
    from cdb.objects import ClassRegistry

    try:
        data = request.json

        new_class = model.code
        object_oid = data.get('cdb_object_id', None)
        with_defaults = data['withDefaults']
        active_props_only = data['activePropsOnly']
        create_all_blocks = data['withDefaults']
        dd_classname = data['dataDictionaryClassName']
        properties = data.get('properties', {})

        if not data['searchMode'] and object_oid:
            obj = ByID(object_oid)
            pyclass = obj.__class__
        elif dd_classname:
            obj = None
            rel = kernel.getPrimaryTableForClass(dd_classname)
            pyclass = ClassRegistry().find(rel)
        else:
            obj = None
            pyclass = None

        if not data['searchMode']:
            if pyclass:
                sig.emit(pyclass, "classification_select_class")(obj, data['assignedClassCodes'], new_class)

            dd_classname = obj.GetClassname() if obj else data['dataDictionaryClassName']
            acc_info = ClassificationData.get_access_info(
                [new_class], obj=obj, dd_classname=dd_classname, for_create=True
            )

            if not acc_info[new_class]:
                new_class_object = ClassificationClass.ByKeys(code=new_class)
                # FIXME: get the error message without creating an exception
                ue_ex = ue.Exception(
                    "cs_classification_no_permission_for_class",
                    new_class_object.name if new_class_object else new_class
                )
                LOG.exception(ue_ex)
                raise webob.exc.HTTPUnprocessableEntity(str(ue_ex))

        assigned_classes = set(data['assignedClassCodes'])
        assigned_classes.add(new_class)
        classification_data = ClassificationData(
            object_oid, class_codes=list(assigned_classes), narrowed=False, request=request, check_rights=True
        )
        values, metadata = classification_data.get_new_classification_with_complete_metadata(
            new_class, with_defaults, active_props_only, create_all_blocks
        )

        prop_codes_for_validation = {}
        rule_results = {}
        if not data['searchMode']:
            orig_values = str(values) if LOG.isEnabledFor(logging.DEBUG) else ""
            prop_codes_for_validation = ClassificationValidator.get_property_codes_for_validation(
                list(metadata["classes"]), list(values)
            )
            rule_values = deepcopy(values)
            rule_values.update(properties)
            rule_results = ClassificationValidator.calculate_rules(rule_values)
            if pyclass:
                # intentionally not documented. for internal use only!
                sig.emit(pyclass, "classification", "new_class")(new_class, dict(metadata), values)
            if LOG.isEnabledFor(logging.DEBUG) and orig_values != str(values):
                LOG.debug("Classification new_class hook modified value structure:")
                LOG.debug("   orig: %s", orig_values)
                LOG.debug("   new: %s", values)

        return {
            "metadata": metadata,
            "values": utils.ensure_json_serialiability(values),
            "rule_results": rule_results,
            "prop_codes_for_validation": prop_codes_for_validation,
            "catalog_configs": utils.get_property_catalog_configs(request, metadata)
        }
    except ClassificationValidationException as validation_exception:
        LOG.exception(validation_exception)
        raise webob.exc.HTTPUnprocessableEntity(str(validation_exception.to_ue_Exception()))
    except Exception as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@main.ClassificationInternalApp.json(model=rest_models.ClassificationClassesModel, request_method="POST")
def class_infos(model, request):
    try:
        data = request.json
        with_rules = data['searchMode'] is False
        with_defaults = data['withDefaults']
        assigned_classes = set(data['assignedClassCodes'])
        active_props_only = data.get('activePropsOnly', True)
        properties = data.get('properties', {})

        classification_data = ClassificationData(
            None, class_codes=list(assigned_classes), narrowed=False, request=request, check_rights=True
        )
        values, metadata = classification_data.get_new_classification(
            [], with_defaults=with_defaults, active_props_only=active_props_only,
            create_all_blocks=with_defaults
        )
        additional_property_codes = set(data.get('additionalPropertyCodes', []))
        if additional_property_codes:
            metadata["addtl_properties"] = ClassificationData.get_catalog_property_metadata(
                additional_property_codes
            )
            default_value_oids = ClassificationData.find_default_values(metadata["addtl_properties"])
            default_values_by_oid = ClassificationData.load_default_values(default_value_oids)
            ClassificationData.pad_values_intern(
                props_dict=metadata["addtl_properties"],
                values_dict=values,
                parent_property_path=None,
                position=None,
                with_defaults=False,
                with_defaults_in_blocks=with_defaults,
                active_props_only=True,
                create_all_blocks=False,
                narrowed=False,
                default_values_by_oid=default_values_by_oid,
                key_prop_values=None
            )

        if with_rules:
            rule_values = deepcopy(values)
            rule_values.update(properties)
            rule_results = ClassificationValidator.calculate_rules(rule_values)
            prop_codes_for_validation = ClassificationValidator.get_property_codes_for_validation(
                list(metadata["classes"]), list(values)
            )
        else:
            rule_results = {}
            prop_codes_for_validation = {}

        return {
            "metadata": metadata,
            "rule_results": rule_results,
            "prop_codes_for_validation": prop_codes_for_validation,
            "values": utils.ensure_json_serialiability(values),
            "catalog_configs": utils.get_property_catalog_configs(request, metadata)
        }
    except Exception as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@main.ClassificationInternalApp.json(model=rest_models.BlockPropertyValueCodeModel, request_method="POST")
def get_missing_block_multi_values(model, request):
    data = request.json
    class_code = data['clazzCode']
    property_code = data['propertyCode']
    property_values = data['propertyValues']
    missing_values = ClassificationData(
        data.get('cdb_object_id', None), class_codes=[class_code], request=request
    ).create_missing_block_values(property_code, property_values)
    return missing_values


@main.ClassificationInternalApp.json(model=rest_models.PropertyValueCodeModel, request_method="POST")
def get_added_multi_value(model, request):
    data = request.json

    class_code = data['clazzCode']
    create_all_blocks = not data['searchMode']
    object_oid = data.get('cdb_object_id', None)
    property_value = data['propertyValue']

    class_codes = [class_code] if class_code else None
    values, prop_data = ClassificationData(
        data.get('cdb_object_id', None), class_codes=class_codes, request=request
    ).get_new_value(property_value['value_path'], create_all_blocks)

    if not data['searchMode']:
        from cdb import kernel
        from cdb import sig
        from cdb.objects import ClassRegistry
        pyclass = None
        dd_classname = data['dataDictionaryClassName']
        if object_oid:
            obj = ByID(object_oid)
            pyclass = obj.__class__
        elif dd_classname:
            rel = kernel.getPrimaryTableForClass(dd_classname)
            pyclass = ClassRegistry().find(rel)

        orig_values = str(values) if LOG.isEnabledFor(logging.DEBUG) else ""

        # intentionally not documented. for internal use only
        sig.emit(pyclass, "classification", "new_value")(class_code, dict(prop_data), values)

        if LOG.isEnabledFor(logging.DEBUG) and orig_values != str(values):
            LOG.debug("Classification new_class hook modified value structure:")
            LOG.debug("   orig: %s", orig_values)
            LOG.debug("   new: %s", values)

    return values


@main.ClassificationInternalApp.json(model=rest_models.ApplicableClassesModel, request_method="POST")
def get_applicable_classes(model, request):

    data = request.json
    dd_class_name = data.get('dataDictionaryClassName')
    class_code = data.get('classificationClassCode')
    with_inactive_classes = data.get('withInactiveClasses', True)

    result = {}

    if class_code:
        is_applicable = 1 == data.get('isApplicable', 0)
        is_exclusive = 1 == data.get('isExclusive', 0)

        result["applicable_classes"] = ClassificationClass.get_applicable_sub_classes(
            dd_class_name,
            class_code,
            is_parent_class_applicable=is_applicable,
            is_parent_class_exclusive=is_exclusive,
            only_active=True,
            only_released=not with_inactive_classes
        )
    else:
        result["additional_properties"] = not ("0" == util.get_prop("adpr"))
        result["show_class_tree_always"] = ("1" == util.get_prop("sclt"))
        result["initially_expand_class_pictures"] = ("1" == util.get_prop("iecp"))

        result["applicable_classes"] = ClassificationClass.get_applicable_root_classes(
            dd_class_name,
            only_active=True,
            only_released=not with_inactive_classes
        )

    return result


@main.ClassificationInternalApp.json(model=rest_models.MatchingClassesModel, request_method="GET")
def get_matching_classes(model, request):

    dd_class_name = request.params["dataDictionaryClassName"]
    only_active = request.params.get('onlyActive', 'true')
    only_released = request.params.get('onlyReleased', 'true')
    query_string = request.params["query"]

    request_limit = int(request.params['limit'])

    matching_classes = ClassificationClass.search_applicable_classes(
        dd_class_name,
        query_string,
        limit=1 + request_limit,
        only_active=('true' == only_active),
        only_released=('true' == only_released)
    )
    add_file_data(request, matching_classes)

    has_more = False
    result = []
    for matching_class in matching_classes:
        if len(result) <= request_limit:
            result.append({
                "code": matching_class["code"],
                "name": matching_class["label"],
                "parent_path": matching_class["parent_class_codes"],
                "file": matching_class["file"]
            })
        else:
            has_more = True

    return {
        "matching_classes": result,
        "has_more": has_more
    }


@main.ClassificationInternalApp.json(model=rest_models.MatchingPropertiesModel, request_method="GET")
def get_matching_properties(model, request):

    request_limit = int(request.params['limit'])
    query_limit = request_limit + 1
    query_string = request.params["query"].lower()
    name_col = "name_" + i18n.default()
    sql_statement = "SELECT * FROM cs_property " \
                    "WHERE cs_property.status = 200 AND lower({name_col}) LIKE '%{query_string}%' " \
                    "ORDER BY {name_col}".format(
        name_col=name_col, query_string=query_string
    )

    matching_properties = []
    records = sqlapi.RecordSet2(
        sql=sql_statement,
        max_rows=query_limit
    )
    for record in records:
        if (util.check_access("cs_property", record, "read")):
            matching_properties.append({
                "code": record["code"],
                "name": record[name_col]
            })

    has_more = len(matching_properties) > request_limit
    if has_more:
        del matching_properties[-1]

    return {
        "matching_properties": matching_properties,
        "has_more": has_more
    }


@main.ClassificationInternalApp.json(model=rest_models.TopLevelPropertyFolderModel, request_method="GET")
def get_top_level_property_folder(model, request):
    top_level_folder = []

    icon_url = catalog.PropertyFolder.GetClassIcon()

    name_col = "name_" + i18n.default()
    sql_statement = "SELECT cdb_object_id, {name_col} FROM cs_property_folder " \
        "WHERE parent_id IS NULL OR parent_id = '' " \
        "ORDER BY {name_col}".format(
            name_col=name_col
        )
    records = sqlapi.RecordSet2(sql=sql_statement)
    for record in records:
        top_level_folder.append({
            "description": record[name_col],
            "folder_id": record["cdb_object_id"],
            "icon_url": icon_url,
            "name": record[name_col]
        })

    return top_level_folder


@main.ClassificationInternalApp.json(model=rest_models.PropertyFolderContentModel, request_method="GET")
def get_folder_content(model, request):
    folder_content = []
    desc_col = "description_" + i18n.default()
    name_col = "name_" + i18n.default()

    folder_icon_url = catalog.PropertyFolder.GetClassIcon()
    property_icon_url = catalog.Property.GetClassIcon()

    sql_statement = "SELECT cdb_object_id, {name_col} FROM cs_property_folder where parent_id = '{parent_id}' ORDER BY {name_col}".format(
        name_col=name_col,
        parent_id=model.folder_id
    )
    records = sqlapi.RecordSet2(sql=sql_statement)
    for record in records:
        folder_content.append({
            "description": record[name_col],
            "folder_id": record["cdb_object_id"],
            "icon_url": folder_icon_url,
            "name": record[name_col]
        })

    # remove properties which have a code conflict with solr field names
    sql_statement = "SELECT cs_property.* FROM cs_property_folder_assignment " \
                    "JOIN cs_property ON cs_property.cdb_object_id = cs_property_folder_assignment.property_id " \
                    "WHERE cs_property_folder_assignment.folder_id = '{folder_id}' AND cs_property.status = 200 " \
                    "AND cs_property.code not in ('id', 'type')" \
                    "ORDER BY cs_property.{name_col}".format(
        desc_col=desc_col,
        name_col=name_col,
        folder_id=model.folder_id
    )
    records = sqlapi.RecordSet2(sql=sql_statement)
    for record in records:
        if record["code"].startswith('_'):
            # remove properties which might have a code conflict with solr field names
            continue
        if util.check_access("cs_property", record, "read"):
            folder_content.append({
                "code": record["code"],
                "description": record[desc_col],
                "icon_url": property_icon_url,
                "name": record[name_col]
            })

    return folder_content


@main.ClassificationInternalApp.json(model=rest_models.PropertyCodeModel, request_method="POST")
def get_property(model, request):
    data = request.json
    property_code = data.get('propertyCode')

    properties = ClassificationData.get_catalog_property_metadata([property_code])
    default_value_oids = ClassificationData.find_default_values(properties)
    default_values_by_oid = ClassificationData.load_default_values(default_value_oids)

    values = {}
    ClassificationData.pad_values_intern(
        props_dict=properties,
        values_dict=values,
        parent_property_path=None,
        position=None,
        with_defaults=False,
        with_defaults_in_blocks=False,
        active_props_only=True,
        create_all_blocks=False,
        narrowed=False,
        default_values_by_oid=default_values_by_oid,
        key_prop_values=None
    )
    return {
        'metadata': properties,
        'values': values,
        'catalog_configs': utils.get_property_catalog_configs(
            request, {
                'addtl_properties': properties
            }
        )
    }


@main.ClassificationInternalApp.json(model=rest_models.EnumValuesModel, request_method="POST")
def get_enum_values(model, request):
    try:
        data = request.json
        class_code = data.get('clazzCode')
        property_code = data.get('propertyCode')

        enum_values = api.get_catalog_values(
            class_code=class_code,
            property_code=property_code,
            active_only=True,
            request=request
        )

        additional_enum_value_object_ids = data.get('additionalEnumValueObjectIds')
        if additional_enum_value_object_ids is not None and len(additional_enum_value_object_ids) > 0:
            property_values = catalog.PropertyValue.object_property_values_to_json_data(
                cdb_object_ids=additional_enum_value_object_ids, property_codes=[property_code]
            )

            for object_entries in property_values.values():
                for object_entry in object_entries:
                    if not is_property_value_found(
                            object_entry["type"],
                            object_entry["value"],
                            enum_values,
                            compare_normalized_values=False
                    ):
                        enum_values.append(object_entry)

        class_codes = data.get('classCodes', None)
        if class_code and class_codes:
            property_values = data.get('values', None)
            ClassificationUpdater(None).calculate_normalized_float_values(property_values)
            enum_values = ClassificationValidator.get_validated_catalog_values(
                class_codes, property_code, property_values, enum_values
            )
        return {
            "enums": {
                property_code: utils.ensure_json_serialiability(enum_values)
            }
        }
    except Exception as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@main.ClassificationInternalApp.json(model=rest_models.ClassificationUnitsModel)
def get_units(model, request):
    from cs.classification.units import UnitCache
    return {
        'units': UnitCache.get_all_units_by_id(),
        'compatible_units': UnitCache.get_all_units_by_compatibility()
    }


@main.ClassificationInternalApp.json(model=rest_models.SearchClassificationModel, request_method="POST")
def _search_for_classification_classdef_files(model, request):
    import tatsu

    def _prepare_files(obj, rest_files, request):
        result = []
        for f in getattr(obj, "Files", []):
            try:
                rest_file = next((
                    rf for rf in rest_files
                    if rf["cdb_object_id"] == f.cdb_object_id
                ))
                attrs = utils.ensure_json_serialiability(f.GetDisplayAttributes())
                attrs["self"] = rest_file
                result.append(attrs)
            except StopIteration:
                pass
        return result

    def _prepare_object(obj, app, request):
        result = utils.ensure_json_serialiability(obj.GetDisplayAttributes())
        rest_obj = request.view(obj, app=app)
        rest_files = rest_obj.get("relship:files", {"targets": []})

        result["self"] = rest_obj
        result["extract"] = "-"
        result["showMore"] = False
        result["files"] = _prepare_files(obj, rest_files["targets"], request)
        result["link"] = rest_obj["system:ui_link"]

        return result

    objects = []
    try:
        collection_app = root.get_v1(request).child('collection')
        for obj in itersearch(request, model.classdef):
            obj_rest_name = support.rest_name(obj)
            if obj_rest_name is not None:
                generic_app = collection_app.child(GenericApp, rest_name=obj_rest_name)
                objects.append(_prepare_object(obj, generic_app, request))

        return {
            "objects": objects,
            "result_complete": True
        }
    except (tatsu.exceptions.ParseError, SolrCommandException) as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@main.ClassificationInternalApp.json(model=rest_models.ClassificationValidationModel, request_method="POST")
def validate_classification(model, request):
    try:
        data = request.json
        class_codes_for_validation = data.get("classCodesForValidation", [])
        updater = ClassificationUpdater(None)
        updater.validate(data, class_codes_for_validation)

        changed_property_codes = data["changed_property_codes"]
        changed_properties = {
            prop_code: data["properties"][prop_code] for prop_code in changed_property_codes
        }
        return {
            "error_message": "\n".join(data["error_messages"]),
            "has_errors": len(data["error_messages"]) > 0,
            "properties": changed_properties,
            "changed_property_code": data["changed_property_code"],
            "rule_results": data["rule_results"]
        }
    except Exception as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@main.ClassificationInternalApp.json(model=rest_models.ClassificationValidationInfoModel, request_method="POST")
def get_validation_info(model, request):
    data = request.json
    class_codes = data["class_codes"]
    property_codes = data["property_codes"]

    prop_codes_for_validation = ClassificationValidator.get_property_codes_for_validation(
        class_codes, property_codes
    )
    return {
        "prop_codes_for_validation": prop_codes_for_validation
    }


def itersearch(request, classdef=None):
    import tatsu
    if classdef is not None:
        dd_class = core.ClassRegistry().find(classdef.getPrimaryTable())
        make_obj = lambda oid: dd_class.ByKeys(cdb_object_id=oid)
    else:
        make_obj = ByID
    data = request.json
    values = data.get('values', {})
    class_codes = data.get('classes', [])
    catalog_property_codes = set(data.get('catalog_property_codes', []))
    try:
        if isinstance(class_codes, str):
            class_codes = [class_codes]
        oids = cs.classification.solr.search_solr(values, class_codes, catalog_property_codes)

        for obj in map(make_obj, oids):
            if obj:
                yield obj
    except (tatsu.exceptions.ParseError, SolrCommandException) as e:
        LOG.exception(e)
        raise webob.exc.HTTPUnprocessableEntity(str(e))


@main.ClassificationInternalApp.json(model=rest_models.ClassificationModel, request_method="POST")
def access_info(model, request):
    data = request.json
    class_code = data['clazzCode']
    assigned_classes = [class_code]

    if model.obj:
        access_info = ClassificationData.get_access_info(
            assigned_classes, obj=model.obj, for_create=False, add_base_classes=True
        )
        assigned_classes_with_olc = {}
        obj_classification = ObjectClassification.ByKeys(
            ref_object_id=model.obj.cdb_object_id,
            class_code=class_code
        )
        if obj_classification:
            assigned_classes_with_olc[class_code] = utils.render_object_classification_to_json(
                request, obj_classification
            )
        return {
            "acc_info": access_info,
            "assigned_classes_with_olc": assigned_classes_with_olc
        }
    else:
        raise webob.exc.HTTPNoContent


@main.ClassificationInternalApp.json(model=rest_models.ClassificationOperationModel, request_method="POST")
def operation_info(model, request):
    operation = model.obj
    if operation:
        classification_data = json.loads(operation.GetText("classification_data"))
        assigned_classes = classification_data["assigned_classes"]
        properties = classification_data["properties"]

        classificationData = ClassificationData(
            None, assigned_classes, request, False, True, check_rights=True
        )
        values, metadata = classificationData.get_new_classification([], with_defaults=False)

        for prop_code, prop_values in values.items():
            if prop_code not in properties:
                properties[prop_code] = prop_values

        classificationData.remove_inactive_props(properties, metadata)

        return {
            "metadata": metadata,
            "properties": utils.ensure_json_serialiability(properties),
            "dd_classname": operation.dd_classname,
            "rule_results": ClassificationValidator.calculate_rules(properties),
            "prop_codes_for_validation": ClassificationValidator.get_property_codes_for_validation(
                list(metadata["classes"]), list(properties)
            )

        }
    else:
        raise webob.exc.HTTPNoContent


@main.ClassificationInternalApp.json(model=rest_models.ClassificationCheckAccessModel, request_method="POST")
def object_modify_rights(model, request):
    data = request.json
    is_modifiable = False
    context_object_id = data.get('context_object_id')
    dd_classname = data.get('dd_classname')
    if dd_classname:
        tmpObj = None
        if "cs_classification_constraint" == dd_classname:
            from cs.classification.constraints import Constraint
            tmpObj = Constraint(classification_class_id=context_object_id)
        elif "cs_classification_formula" == dd_classname:
            from cs.classification.computations import ComputationFormula
            tmpObj = ComputationFormula(property_id=context_object_id)
        elif "cs_classification_rule" == dd_classname:
            from cs.classification.rules import Rule
            tmpObj = Rule(class_property_id=context_object_id)
        if tmpObj:
            is_modifiable = tmpObj.CheckAccess("create")

    return {
        "is_modifiable": is_modifiable
    }


@main.ClassificationInternalApp.json(model=rest_models.ClassificationCodeCompletionModel, request_method="POST")
def get_code_completion(model, request):
    json_data = request.json
    class_codes = json_data.get('clazzCodes', [])
    for_variants = json_data.get('forVariants', False)

    class_oids = set(
        ClassificationClass.get_base_class_ids(class_codes=class_codes, include_given=True)
    )
    catalog_values = api.get_all_catalog_values(
        class_codes, active_only=True, request=request, for_variants=for_variants
    )

    if for_variants:
        class_props = ClassProperty.Query(
            (ClassProperty.classification_class_id.one_of(*class_oids)) & (ClassProperty.for_variants == 1)
        )
    else:
        class_props = ClassProperty.Query(ClassProperty.classification_class_id.one_of(*class_oids))

    properties = {}
    for class_prop in class_props:
        if not for_variants or 1 == class_prop.for_variants:
            properties[class_prop.code] = {
                'description': tools.get_label('prop_description', class_prop),
                'name': tools.get_label('name', class_prop).replace(' ', '_')
            }

    return {
        'catalog_values': utils.ensure_json_serialiability(catalog_values),
        'functions': computations.BaseTransformer.functions,
        'operators': computations.BaseTransformer.operators,
        'properties': properties,
        'values': computations.BaseTransformer.values
    }


@main.ClassificationInternalApp.json(model=rest_models.ClassificationSyntaxCheckModel, request_method="POST")
def check_syntax(model, request):
    data = request.json
    expression = data.get('expression', '')
    property_codes = set(data.get('property_codes', []))

    error_message = ''
    line = -1
    pos = -1
    missing_prop_codes = []

    try:
        used_prop_codes = computations.property_codes_used_in_expression(expression)
        missing_prop_codes = list(used_prop_codes.difference(property_codes))
    except SyntaxError as syntaxError:
        line = syntaxError.lineno
        pos = syntaxError.offset
        error_message = "{label}: {exception}".format(
            label=util.get_label("web.cs-classification-component.error_syntax_error"),
            exception=syntaxError
        )
    except Exception as exception:
        error_message = "{label} '{expression}': {exception}".format(
            label=util.get_label("web.cs-classification-component.error_eval_error"),
            expression=expression,
            exception=exception
        )

    return {
        'error_message': error_message,
        'missing_prop_codes': missing_prop_codes,
        'line': line,
        'pos': pos
    }


@main.ClassificationInternalApp.json(model=rest_models.ClassificationPropertyValueModel, request_method="POST")
def get_property_values(model, request):
    data = request.json

    class_property_id = data.get('class_property_id', '')
    catalog_property_id = data.get('catalog_property_id', '')
    value_class_name = ClassProperty.get_value_class_name(data.get('cdb_classname', ''))

    lang = i18n.default()
    value_column_name = ClassProperty.get_value_column_name(data.get('cdb_classname', ''))
    if "multilang_value" == value_column_name:
        value_column_name = "{}_{}".format(value_column_name, lang)

    rows = []
    if value_class_name and class_property_id and catalog_property_id:

        class_def = cdbwrapc.CDBClassDef(value_class_name)
        table_definition = RestTableDefWrapper(class_def.getDefaultProjection()).get_rest_data()

        excluded_value_ids = set()
        for property_value_exclude in ClassPropertyValueExclude.KeywordQuery(
                class_property_id=class_property_id, exclude=1
        ):
            excluded_value_ids.add(property_value_exclude.property_value_id)

        prop_value_icon_title = util.get_label("cs_property_value")
        class_prop_value_icon_title = util.get_label("cs_class_property_value")

        for property_value in catalog.PropertyValue.Query(
                catalog.PropertyValue.property_object_id.one_of(*[class_property_id, catalog_property_id]),
                order_by=["pos", value_column_name]
        ):
            columns = []
            if 0 == property_value.is_active and catalog_property_id == property_value.property_object_id:
                # skip inactive enum values of class property
                continue
            for column in table_definition['columns']:
                attribute = column['attribute']
                attribute_multilang = "{}_{}".format(attribute, lang)
                if "cs_multilang_property_value" == value_class_name and "multilang_value" == attribute:
                    attribute = "{}_{}".format(attribute, lang)
                value = None
                if 'cdb_object_icon' == attribute:
                    if property_value.property_object_id == class_property_id:
                        value = {
                            'icon': {
                                'src': "/resources/icons/byname/cs_classification_class/0",
                                'title': class_prop_value_icon_title
                            }
                        }
                    else:
                        value = {
                            'icon': {
                                'src': "/resources/icons/byname/cs_classification_property_catal/0",
                                'title': prop_value_icon_title
                            }
                        }
                elif 'object_reference_value' == attribute:
                    value = property_value[attribute]
                    ref_obj = ByID(value)
                    if ref_obj:
                        value = ref_obj.GetDescription()
                elif 'unit_symbol' == attribute:
                    value = property_value[attribute]
                elif property_value.HasField(attribute):
                    value = property_value[attribute]
                    if 'is_active' == attribute and property_value.cdb_object_id in excluded_value_ids:
                        # set catalog property values to inactive if excluded in class context
                        value = 0
                elif property_value.HasField(attribute_multilang):
                    value = property_value[attribute_multilang]

                columns.append(value)
            rest_obj = request.view(property_value, app=get_collection_app(request))
            rows.append({
                'id': property_value.cdb_object_id,
                'persistent_id': property_value.cdb_object_id,
                'property_id': property_value.property_object_id,
                'rest_obj': rest_obj,
                'restLink': rest_obj['@id'],
                'system:navigation_id': property_value.cdb_object_id,
                'columns': columns
            })

        return {
            'rows': utils.ensure_json_serialiability(rows),
            'table_definition': table_definition
        }
    else:
        return {
            'rows': [],
            'table_definition': None
        }


@main.ClassificationInternalApp.json(model=rest_models.HandleIdModel, request_method="GET")
def get_rest_object_for_handle_id(model, request):
    try:
        obj_handle_id = request.params["obj_handle_id"]
        obj = utils.get_rest_obj_by_handle_id(obj_handle_id)
        rest_obj = request.view(obj, app=get_collection_app(request))
        return rest_obj
    except:
        raise webob.exc.HTTPNotFound


@main.ClassificationInternalApp.json(model=rest_models.AddtlObjectRefValueModel, request_method="GET")
def get_addtl_object_ref_value(model, request):
    try:
        cdb_object_id = request.params["cdb_object_id"]
        return tools.get_addtl_objref_value(cdb_object_id, request)
    except:
        raise webob.exc.HTTPNotFound


