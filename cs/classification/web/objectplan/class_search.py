#
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Version:  $Id$
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import cdbwrapc
import copy

from cs.classification import prepare_oplan
from cs.classification.classes import ClassificationClass
from cs.classification.util import add_file_data
from cs.classification.web.objectplan.main import ObjectplanApp
from cs.classification.web.objectplan import util


class ObjectPlanClassSearchModel(object):
    pass


@ObjectplanApp.path(path='internal/class_search', model=ObjectPlanClassSearchModel)
def open_search():
    return ObjectPlanClassSearchModel()


@ObjectplanApp.json(model=ObjectPlanClassSearchModel, request_method="GET")
def get_matching_classes(model, request):  # @UnusedVariable
    dd_class_name = request.params["dataDictionaryClassName"]
    query_string = request.params["queryString"]
    uses_webui = 'true' == request.params.get("usesWebUI", 'false')

    if not query_string:
        # check lic on root entry
        prepare_oplan(dd_class_name)

    class_path = [{
        "label": cdbwrapc.CDBClassDef(dd_class_name).getDesignation(),
        "code": None
    }]

    if query_string:
        matching_classes = ClassificationClass.search_applicable_classes(
            dd_class_name, query_string, only_active=True, only_released=False, for_oplan=True
        )
    else:
        matching_classes = ClassificationClass.get_applicable_root_classes(
            dd_class_name, only_active=True, only_released=False, for_oplan=True
        )
    for class_info in matching_classes:
        class_info["search_url"] = util.make_search_url(dd_class_name, class_info["code"], uses_webui)
        class_info["create_url"] = util.make_create_url(dd_class_name, class_info)

    add_file_data(request, matching_classes)

    return {
        "classes": matching_classes,
        "classPath": class_path
    }
