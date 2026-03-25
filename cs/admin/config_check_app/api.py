# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
REST API for the config checker app

The error objects can be queried via the rest api, which can be accessed under
``config-check-api``.
The data is grouped by modules. Thus the result is list of objects containing a
key ``module_id`` and the error list (``errors``).


Each error object has the following entries:

object
    Object which contains the configuration error.

classDesignation
    Class name of the object.

url
   An url referencing the object.

check
    Name of the implemented checker, which has found the error.

description
    Error message.

isWarning
    ``true`` if this is considered as an error.

details
    Additional information.


The error objects are sorted by ``classDesignation`` and ``check``
"""

from __future__ import absolute_import

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

from operator import itemgetter

from cdb.comparch.modules import Module
from cdb.comparch.packages import Package

from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal
from cs.platform.web.uisupport import get_ui_link


class ConfigCheckApi(JsonAPI):
    pass


@Internal.mount(app=ConfigCheckApi, path="/cs-admin/config-check-api")
def _mount_app():
    return ConfigCheckApi()


class ConfigCheckApiModel(object):
    def __init__(self, modules, packages):
        self.modules = modules
        self.packages = packages

    def _object_description(self, obj):
        result = obj.GetDescription()
        if not result:
            result = obj.DBInfo()
        return result

    def _format_errors(self, errors):
        # sorted by class and check type
        result = sorted([{
            "object": self._object_description(error.obj),
            "classDesignation": error.obj.GetClassDef().getDesignation('en'),
            "url": get_ui_link(None, error.obj),
            "check": error.check.name,
            "description": error.desc,
            "isWarning": error.is_warning,
            "details": error.get_details()
            } for error in errors],
            key=itemgetter('classDesignation', 'check'))
        return result

    def get_check_results(self):
        try:
            from cdb.comparch.config_check import ConfigChecker
        except ImportError:
            return {"error": "Platform release too old, this function is not yet supported!"}
        checker = ConfigChecker(set())
        if self.modules:
            for module in Module.KeywordQuery(module_id=self.modules).Execute():
                checker.check_module(module, True)
        if self.packages:
            for pkg in Package.KeywordQuery(name=self.packages).Execute():
                checker.check_package(pkg, True)
        if not self.modules and not self.packages:
            # No packages or modules means "check everything"
            for pkg in Package.Query().Execute():
                checker.check_package(pkg, True)
            checker.check_unassigned_objects()

        return {
            "results": [{
                    "module_id": module_id,
                    "errors": self._format_errors(errors)}
                for module_id, errors in checker.results_by_module()
            ]
        }


@ConfigCheckApi.path(model=ConfigCheckApiModel, path="",
                     converters=dict(modules=[str], packages=[str]))
def _path(modules=None, packages=None):
    return ConfigCheckApiModel(modules, packages)


@ConfigCheckApi.json(model=ConfigCheckApiModel)
def _json(model, request):
    return model.get_check_results()
