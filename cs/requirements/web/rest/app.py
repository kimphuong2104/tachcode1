#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from webob.exc import HTTPForbidden

from cdb import ElementsError
from cdb.constants import kOperationModify
from cs.platform.web import permissions
from cs.platform.web.license import check_license, check_license_for_operation
from cs.platform.web.permissions import ReadPermission
from cs.platform.web.rest import CollectionApp
from cs.platform.web.rest.generic.convert import object_operation_args
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.generic.operation_decorator import \
    rest_operation_decorator
from cs.requirements import RQMSpecObject
from cs.requirements.richtext import RichTextModifications


class RQMSpecObjectApp(GenericApp):
    def __init__(self):
        super(RQMSpecObjectApp, self).__init__("spec_object")


@CollectionApp.mount(app=RQMSpecObjectApp, path="spec_object")
def _mount_app():
    return RQMSpecObjectApp()


@GenericApp.defer_links(model=RQMSpecObject)
def _defer_spec_object(app, _spec_object):
    return app.child(RQMSpecObjectApp())


@RQMSpecObjectApp.json(model=RQMSpecObject, permission=ReadPermission, name="extended")
@check_license
def _spec_object_default_extended(spec_object, request):
    result = request.view(spec_object, name="base_data")
    modified_attribute_values = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
        spec_object, result
    )
    result.update(modified_attribute_values)
    result["__rqm_extended__"] = 1
    return result


@RQMSpecObjectApp.json(model=RQMSpecObject, request_method='PUT', name="extended")
@permissions.check_rest_method
def object_modify(self, request):
    try:
        check_license_for_operation(self.GetClassname(), kOperationModify)
        args, addl_args = object_operation_args(request, self.GetClassDef())
        rest_operation_decorator(kOperationModify, self, addl_args, **args)

        # return the object we just modified back to client
        return request.view(self, name="extended")
    except ElementsError as e:
        raise HTTPForbidden(str(e))
