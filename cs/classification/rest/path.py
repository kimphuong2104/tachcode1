#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module rest

This is the documentation for the rest module.
"""

from cdb.objects.core import Object

from cs.classification.rest import model
from cs.classification.rest.main import ClassificationByIDApp
from cs.classification.rest.main import ClassificationInternalApp
from cs.classification.rest.utils import get_rest_obj_by_id

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@ClassificationByIDApp.path(path='{object_id}', model=Object)
def get_object_by_id(object_id, app):
    return get_rest_obj_by_id(object_id)


@ClassificationInternalApp.path(path='{object_id}', model=Object)
def get_object(object_id, app):
    return get_rest_obj_by_id(object_id)


@ClassificationInternalApp.path(path='obj_by_handle_id', model=model.HandleIdModel)
def get_object_by_handle_id(app):
    return model.HandleIdModel()


@ClassificationInternalApp.path(path='access_info/{object_id}/', model=model.ClassificationModel)
def get_access_info(app, object_id):
    return model.ClassificationModel(get_rest_obj_by_id(object_id))


@ClassificationInternalApp.path(path='operation/{object_id}/', model=model.ClassificationOperationModel)
def get_operation(app, object_id):
    return model.ClassificationOperationModel(get_rest_obj_by_id(object_id))


@ClassificationInternalApp.path(path='applicable_classes', model=model.ApplicableClassesModel)
def get_applicable_classes(app):
    return model.ApplicableClassesModel()


@ClassificationInternalApp.path(path='matching_classes', model=model.MatchingClassesModel)
def get_matching_classes(app):
    return model.MatchingClassesModel()


@ClassificationInternalApp.path(path='top_level_property_folder', model=model.TopLevelPropertyFolderModel)
def get_top_level_property_folder(app):
    return model.TopLevelPropertyFolderModel()


@ClassificationInternalApp.path(path='property_folder_content/{folder_id}/', model=model.PropertyFolderContentModel)
def get_property_folder_content(app, folder_id):
    return model.PropertyFolderContentModel(folder_id)


@ClassificationInternalApp.path(path='matching_properties', model=model.MatchingPropertiesModel)
def get_matching_properties(app):
    return model.MatchingPropertiesModel()


@ClassificationInternalApp.path(path='property', model=model.PropertyCodeModel)
def get_property_from_code():
    return model.PropertyCodeModel()


@ClassificationInternalApp.path(path='class/{code}', model=model.ClassificationClassModel)
def get_class_from_code(code, app):
    return model.ClassificationClassModel(code=code)


@ClassificationInternalApp.path(path='classes', model=model.ClassificationClassesModel)
def get_classes_for_codes(code, app):
    return model.ClassificationClassesModel()


@ClassificationInternalApp.path(path='enum_values', model=model.EnumValuesModel)
def get_enum_values_model():
    return model.EnumValuesModel()


@ClassificationInternalApp.path(path='class_property_values', model=model.ClassificationPropertyValueModel)
def _class_property_values():
    return model.ClassificationPropertyValueModel()


@ClassificationInternalApp.path(path='property_value', model=model.PropertyValueCodeModel)
def get_property_value_from_code():
    return model.PropertyValueCodeModel()


@ClassificationInternalApp.path(path='missing_block_values', model=model.BlockPropertyValueCodeModel)
def get_missing_block_property_values_from_code():
    return model.BlockPropertyValueCodeModel()


@ClassificationInternalApp.path(path='units', model=model.ClassificationUnitsModel)
def get_units():
    return model.ClassificationUnitsModel()


@ClassificationInternalApp.path(path='validate', model=model.ClassificationValidationModel)
def validate_classification():
    return model.ClassificationValidationModel()


@ClassificationInternalApp.path(path='validation_info', model=model.ClassificationValidationInfoModel)
def get_validation_info():
    return model.ClassificationValidationInfoModel()


@ClassificationInternalApp.path(path='search/{classname}', model=model.SearchClassificationModel)
def _search_internal(app, classname):
    return model.SearchClassificationModel(classname)


@ClassificationInternalApp.path(path='check_modify_access', model=model.ClassificationCheckAccessModel)
def check_modify_access():
    return model.ClassificationCheckAccessModel()


@ClassificationInternalApp.path(path='code_completion', model=model.ClassificationCodeCompletionModel)
def get_code_completion():
    return model.ClassificationCodeCompletionModel()


@ClassificationInternalApp.path(path='syntax_check', model=model.ClassificationSyntaxCheckModel)
def check_syntax():
    return model.ClassificationSyntaxCheckModel()


@ClassificationInternalApp.path(path='addtl_object_ref_value', model=model.AddtlObjectRefValueModel)
def get_addtl_object_ref_value():
    return model.AddtlObjectRefValueModel()

