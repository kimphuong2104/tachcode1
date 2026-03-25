#
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Version:  $Id$
#
from cdbwrapc import StatusInfo

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import cdbwrapc

from cs.classification import tools
from cs.classification.classes import ClassificationClass
from cs.classification.classification_data import ClassificationData
from cs.classification.util import add_file_data
from cs.classification.web.objectplan.main import ObjectplanApp
from cs.classification.web.objectplan import util


class ObjectPlanClassInfoModel(object):
    pass


@ObjectplanApp.path(path='internal/class_info', model=ObjectPlanClassInfoModel)
def class_info():
    return ObjectPlanClassInfoModel()


@ObjectplanApp.json(model=ObjectPlanClassInfoModel, request_method="GET")
def get_sub_classes(model, request):  # @UnusedVariable
    dd_class_name = request.params["dataDictionaryClassName"]
    class_code = request.params["classCode"]
    uses_webui = 'true' == request.params.get("usesWebUI", 'false')

    if class_code:
        sub_classes = ClassificationClass.get_applicable_sub_classes(
            dd_class_name, class_code, only_active=True, only_released=False, for_oplan=True
        )
    else:
        sub_classes = ClassificationClass.get_applicable_root_classes(
            dd_class_name, only_active=True, only_released=False, for_oplan=True
        )

    for class_info in sub_classes:
        class_info["search_url"] = util.make_search_url(dd_class_name, class_info["code"], uses_webui)
        class_info["create_url"] = util.make_create_url(dd_class_name, class_info)

    sub_classes = sorted(sub_classes, key=lambda entry: entry["oplan_tile_title"])
    picture = add_file_data(request, sub_classes, class_code)

    class_path = []
    classes_by_oid = {}
    given_class = None
    for clazz in ClassificationClass.get_base_classes(class_codes=[class_code], include_given=True):
        classes_by_oid[clazz.cdb_object_id] = clazz
        if class_code == clazz.code:
            given_class = clazz

    parent_class = given_class
    while parent_class:
        class_path.append({
            "label": parent_class.name,
            "code": parent_class.code
        })
        parent_class = classes_by_oid.get(parent_class.parent_class_id)

    class_path.reverse()
    class_path = [{
        "label": cdbwrapc.CDBClassDef(dd_class_name).getDesignation(),
        "code": None
    }] + class_path

    return {
        "classPath": class_path,
        "classes": sub_classes,
        "picture": picture
    }


class ObjectPlanClassDetailsModel(object):
    pass


@ObjectplanApp.path(path='internal/class_details', model=ObjectPlanClassDetailsModel)
def class_details():
    return ObjectPlanClassDetailsModel()


@ObjectplanApp.json(model=ObjectPlanClassDetailsModel, request_method="GET")
def get_class_details(model, request):  # @UnusedVariable
    class_code = request.params["classCode"]
    classification_data = ClassificationData(
        None, class_codes=[class_code], narrowed=False, request=request, check_rights=True
    )
    class_documents = ClassificationClass.get_class_documents(class_code)
    addtl_doc_info = [{
        "ui_link": tools.get_obj_link(request, doc),
        "ui_text": doc.GetDescription(),
        "cdb_objektart": doc.z_art,
        "status": doc.z_status,
        "cdb_status_txt": StatusInfo(doc.z_art, doc.z_status).getLabel() if StatusInfo(doc.z_art, doc.z_status) else doc.z_status_txt
    } for doc in class_documents]
    return {
        "documents": addtl_doc_info,
        "metadata": classification_data.get_classification_metadata(),
    }
