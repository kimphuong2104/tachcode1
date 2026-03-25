#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
This module implements displaying the catalog for the CDB_SelectAndAssign Operation.

When retrieving operation info objects via operations.py, CDB_SelectAndAssign operations
have a catalog_url field that points to this REST endpoint. This will:

(1) Call any configured SelectAndAssignPre Powerscript Hooks; this will return a message
    to the frontend containing the reason of the cancellation:

    ```
       {
           "cancelled": message
       }
    ```

(2) Return a catalog info object that may be used with the Catalog frontend component

    ```
       {
           "catalog": {
                # ...
           }
       }
    ```

Throws an HTTPNotFound if CDB_SelectAndAssign is not available.
"""

from dataclasses import dataclass, field
from typing import Any
from webob.exc import HTTPNotFound

from cdbwrapc import RelshipContext
from cdb.platform.mom import getObjectHandle
from cdb.platform.mom.entities import CDBClassDef
from cdb.objects import ClassRegistry
from cs.platform.web.rest.support import rest_objecthandle, get_value_dict
from cs.platform.core.selectandassign import call_SelectAndAssign_pre_hook

from . import App, catalogs, get_uisupport_app


@dataclass
class OperationCatalogModel:
    referer_clname: str
    referer_keys: str
    relship_name: str
    relship_def: Any = field(init=False)
    key_dict: Any = field(init=False)

    def __post_init__(self):
        cldef = CDBClassDef(self.referer_clname)
        self.key_dict = get_value_dict(CDBClassDef(self.referer_clname), self.referer_keys)
        rc = RelshipContext(getObjectHandle(cldef, **self.key_dict), self.relship_name)
        self.relship_def = rc.get_rship_def()

    def _call_pre_hooks(self):
        result = call_SelectAndAssign_pre_hook(self.key_dict, self.relship_def.get_name())
        if result.assignment_cancelled():
            return {
                "cancelled": result.get_cancelled_msg()
            }
        return None

    def get_catalog_info(self, request):
        if cancelled := self._call_pre_hooks():
            # SelectAndAssignPre-Hook cancelled the operation
            return cancelled
        elif catalog_and_label := self.relship_def.get_assignment_op_info():
            catalog = catalog_and_label['catalog']
            label = catalog_and_label['label']
            catalog_info = {
                "label": label,
                "itemsURL": "",
                "selectURL": "",
                "catalogTableURL": "",
                "typeAheadURL": "",
                "valueCheckURL": ""
            }
            catalogs.get_catalog_config(
                request,
                catalog_info,
                catalog,
                False,
                False,
                self.referer_clname,
                self.referer_keys,
                self.relship_name,
                add_multiselect_hint=True,
            )
            return {
                "catalog": catalog_info
            }

        return None

    def link(self, request):
        app = get_uisupport_app(request)
        return request.link(self, app=app)



@App.path(path="operation/catalog/{referer_clname}/{referer_keys}/{relship_name}",
          model=OperationCatalogModel)
def _catalog_operation_model(referer_clname, referer_keys, relship_name):
    return OperationCatalogModel(referer_clname, referer_keys, relship_name)


@App.json(model=OperationCatalogModel)
def _catalog_operation_view(model, request):
    payload = model.get_catalog_info(request)
    if payload is None:
        raise HTTPNotFound()
    return payload
