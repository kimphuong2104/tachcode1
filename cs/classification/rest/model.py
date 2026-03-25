#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import cdbwrapc

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class ApplicableClassesModel(object):  # just to make morepath happy
    pass


class MatchingClassesModel(object):  # just to make morepath happy
    pass


class MatchingPropertiesModel(object):  # just to make morepath happy
    pass


class TopLevelPropertyFolderModel(object):  # just to make morepath happy
    pass


class PropertyFolderContentModel(object):

    def __init__(self, folder_id):
        self.folder_id = folder_id


class PropertyCodeModel(object):  # just to make morepath happy
    pass


class BlockPropertyValueCodeModel(object):  # just to make morepath happy
    pass


class ClassificationClassModel(object):  # just to make morepath happy

    def __init__(self, code):
        self.code = code


class ClassificationClassesModel(object):  # just to make morepath happy
    pass


class ClassificationModel(object):

    def __init__(self, obj):
        self.cdb_object_id = obj.cdb_object_id
        self.obj = obj


class ClassificationOperationModel(object):

    def __init__(self, obj):
        self.cdb_object_id = obj.cdb_object_id
        self.obj = obj


class ClassificationUnitsModel(object):  # just to make morepath happy
    pass


class ClassificationValidationModel(object):  # just to make morepath happy
    pass


class ClassificationValidationInfoModel(object):  # just to make morepath happy
    pass


class EnumValuesModel(object):  # just to make morepath happy
    pass


class PropertyValueCodeModel(object):  # just to make morepath happy
    pass


class HandleIdModel(object):  # just to make morepath happy
    pass


class AddtlObjectRefValueModel(object):  # just to make morepath happy
    pass


class SearchClassificationModel(object):

    def __init__(self, classname):
        try:
            self.classdef = cdbwrapc.CDBClassDef(classname)
        except:
            self.classdef = None


class ClassificationCheckAccessModel(object):  # just to make morepath happy
    pass


class ClassificationCodeCompletionModel(object):  # just to make morepath happy
    pass


class ClassificationSyntaxCheckModel(object):  # just to make morepath happy
    pass


class ClassificationPropertyValueModel(object):  # just to make morepath happy
    pass
