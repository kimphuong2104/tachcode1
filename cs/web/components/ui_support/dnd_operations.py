#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import defaultdict

from . import App
from cdbwrapc import RelshipContext
from cdb import constants
from cdb.platform import mom
from cdb.platform.mom.operations import OperationStateInfo
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web.rest.support import rest_objecthandle

__revision__ = "$Id$"


def get_dnd_operation(obj, parent_classname, keys, relship_name):
    hndl = rest_objecthandle(CDBClassDef(parent_classname), keys)
    relship_ctx = RelshipContext(hndl, relship_name)
    return relship_ctx.operationForDroppedObject(obj)


def get_dnd_operations(request, dropped_objects, parent_classname, keys, relship_name):
    from . import forms
    from . import operations
    result = []
    for obj in dropped_objects:
        op = get_dnd_operation(obj, parent_classname, keys, relship_name)
        if op is None:
            continue
        dav = op.get_dialog_and_values(mom.SimpleArguments())
        opstateinfo = OperationStateInfo(dav['operation_state'])
        target_classname = opstateinfo.get_classname()
        opinfo_model = operations.OperationInfoRelship(
            parent_classname,
            keys,
            relship_name,
            target_classname=target_classname)
        opinfos = request.view(opinfo_model)

        # Try to find our operation
        # The original code has only searched in link_opinfo but
        # fails to work for non N:M relationships (E065343)
        # Because of this we check the class in the first step
        # After this only the operation is checked. This should be
        # good enough because we should always get the create operation
        # of the link class if there is one and the create operation of
        # the target class for DnD configurations.
        candidates = opinfos.get('link_opinfo', ("", []))[1]
        candidates += opinfos.get('reference_opinfo', ("", []))[1]

        opnames = [opstateinfo.get_operation_name()]
        if opnames[0] == constants.kOperationAddToRelationship:
            # AddToRelationship is actually not offered in the menu
            # Use the create operation in this case
            opnames.append(constants.kOperationNew)

        opinfo = None
        for opname in opnames:
            for strong_check in (True, False):
                for info in candidates:
                    if opname == info['opname'] and \
                       (not strong_check or info['classname'] == target_classname):
                        opinfo = info
                        break
                if opinfo:
                    break
            if opinfo:
                break

        if opinfo is None:
            # Thinkabout - this causes the UI to do nothing after the
            # catalog selection.
            continue

        clsdef = CDBClassDef(opinfo['classname'])
        result.append({
            "label": obj.getDesignation(),
            "opstate": forms.FormInfoBase(clsdef).get_forminfo_dict(
                request,
                dav["dialog"],
                dav["values"],
                dav["operation_state"]),
            "opinfo": opinfo
        })
    return result


class DnDOperationsModel(object):

    def __init__(self, parent_classname, keys, relship_name):
        self.parent_classname = parent_classname
        self.keys = keys
        self.relship_name = relship_name

    def get_operations(self, request):
        selected_rest_ids = request.json.get("rest_ids", [])
        rest_ids_by_class = defaultdict(list)
        for classname, rest_id in selected_rest_ids:
            rest_ids_by_class[classname].append(rest_id)
        ohs = []
        for classname, rest_ids in rest_ids_by_class.items():
            cdef = CDBClassDef(classname)
            try:
                handles_by_rest_id = mom.getObjectHandlesFromRESTIDs(cdef, rest_ids, True)
                handles = [handles_by_rest_id.get(rest_id) for rest_id in rest_ids]
                ohs += [h for h in handles if h is not None]
            except ValueError:
                pass
        return get_dnd_operations(request, ohs, self.parent_classname, self.keys, self.relship_name)


@App.path(path='/dnd_operations/{parent_classname}/{keys}/{relship_name}', model=DnDOperationsModel)
def _dnd_operations(parent_classname, keys, relship_name):
    return DnDOperationsModel(parent_classname, keys, relship_name)


@App.json(model=DnDOperationsModel, request_method='POST')
def _get_dnd_operations(self, request):
    return {
        "operations": self.get_operations(request)
    }
