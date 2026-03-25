# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: api.py 142800 2016-06-17 12:53:51Z kbu $"

import os

from cdb import cdbuuid
from cdb.util import get_label
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal

from cs.admin.comparch_app.main import (
    COMPARCH_API_FULLPATH,
    COMPARCH_API_PATH,
    COMPARCH_UNASSIGNED_OBJECTS,
    COMPARCH_UNASSIGNED_OBJECTS_DETAIL,
    COMPARCH_MODULE_CONTENT,
    COMPARCH_MODULE_CONTENT_DETAIL
)

_state_manager = None


class ComparchApi(JsonAPI):
    pass


@Internal.mount(app=ComparchApi, path=COMPARCH_API_PATH)
def _mount_app():
    return ComparchApi()


class ComparchApiModel(object):

    def __init__(self, extra_parameters):
        global _state_manager
        self.extra_parameters = extra_parameters
        self.mode = self.extra_parameters.get("mode")

        if not _state_manager:
            _state_manager = ApplicationStateManager(10)
        self.state_manager = _state_manager

    # API methods

    def get_results(self):
        if self.mode == COMPARCH_UNASSIGNED_OBJECTS:
            return self.get_unassigned_objects()
        elif self.mode == COMPARCH_UNASSIGNED_OBJECTS_DETAIL:
            return self.get_unassigned_object_detail()
        elif self.mode == COMPARCH_MODULE_CONTENT:
            return self.get_module_content()
        elif self.mode == COMPARCH_MODULE_CONTENT_DETAIL:
            return self.get_module_content_detail()
        else:
            return {"error": "Comparch 'mode' undefined or not supported!"}

    def get_unassigned_objects(self):
        from cdb.comparch import tools
        from cdb.comparch.resolver import ModuleContentResolver
        from cdb.objects import DataDictionary

        unassigned_objs = ModuleContentResolver.get_unassigned_objects()
        clnames = []
        for clname in unassigned_objs.keys():
            desc = tools.GetDescription("switch_tabelle", {"classname": clname})
            clnames.append({
                "item_type": clname,
                "desc": desc,
                "count": len(unassigned_objs[clname]),
                "link": COMPARCH_API_FULLPATH,
                "params": {
                    "mode": COMPARCH_UNASSIGNED_OBJECTS_DETAIL,
                    "item_type": clname,
                },
            })
        clnames = sorted(clnames, key=lambda i: i["desc"])

        return {
            "results": clnames,
        }

    def get_unassigned_object_detail(self):
        from cdb.comparch.resolver import ModuleContentResolver
        from cdb.platform.mom.entities import Class
        clname = self.extra_parameters.get("item_type")
        if not clname:
            return {"error": "Missing parameter 'item_type'!"}

        unassigned_objs = ModuleContentResolver.get_unassigned_objects(clname)
        columns = []
        rows = []
        if clname in unassigned_objs:
            cls = Class.ByKeys(clname)
            keys = [key.field_name for key in cls.PrimaryKey.Fields]

            desc = {"id": "__desc", "label": get_label("desc"), "width": 50}
            columns = [desc]
            for key in keys:
                columns.append({"id": key, "label": key, "width": 50 // len(keys)})
            for obj in unassigned_objs.get(clname, []):
                desc = {
                    "text": obj.GetDescription() or get_label("no_description"),
                    "link": {"to": self.get_relative_url(obj.MakeURL("CDB_ShowObject", plain=1))},
                }
                row = {
                    "columns": [desc] + [getattr(obj, key) for key in keys]
                }
                rows.append(row)
            rows = sorted(rows, key=lambda r: r["columns"][0]["text"])
            for index, row in enumerate(rows):
                row["id"] = "%s" % index

        return {
            "results": {
                "columns": columns,
                "rows": rows,
            }
        }

    def get_module_content(self):
        from cdb.comparch.modules import Module
        module_id = self.extra_parameters.get("module_id")
        if not module_id:
            return {"error": "Missing parameter 'module_id'!"}
        state_id = self.extra_parameters.get("state_id", "")
        state = self.getState(state_id)

        if not hasattr(state, "item_types"):
            module = Module.ByKeys(module_id)
            self.setup_module_data(state, module)
            state_id = state.state_id

        item_types = []
        if hasattr(state, "item_types"):
            for item_type in state.item_types:
                desc = state.item_types_content[item_type]["desc"]
                item_types.append({
                    "item_type": item_type,
                    "desc": desc,
                    "count": len(state.item_types_content[item_type]["items"]),
                    "link": COMPARCH_API_FULLPATH,
                    "params": {
                        "mode": COMPARCH_MODULE_CONTENT_DETAIL,
                        "module_id": module_id,
                        "item_type": item_type,
                        "state_id": state_id,
                    },
                })
        item_types = sorted(item_types, key=lambda i: i["desc"].lower())

        return {
            "results": item_types,
        }

    def get_module_content_detail(self):
        from cdb.comparch.modules import Module
        module_id = self.extra_parameters.get("module_id")
        if not module_id:
            return {"error": "Missing parameter 'module_id'!"}
        item_type = self.extra_parameters.get("item_type")
        if not item_type:
            return {"error": "Missing parameter 'item_type'!"}
        state_id = self.extra_parameters.get("state_id", "")
        state = self.getState(state_id)

        if not hasattr(state, "item_types"):
            module = Module.ByKeys(module_id)
            self.setup_module_data(state, module)
            state_id = state.state_id

        columns = []
        rows = []
        if hasattr(state, "item_types") and item_type in state.item_types:
            keys = state.item_types_content[item_type]["items_keys"]
            desc = {"id": "__desc", "label": get_label("desc"), "width": 50}
            columns = [desc]
            for key in keys:
                columns.append({"id": key, "label": key, "width": 50 // len(keys)})
            for obj in state.item_types_content[item_type].get("items", []):
                desc = {
                    "text": obj.GetDescription() or get_label("no_description"),
                    "link": {"to": self.get_relative_url(obj.getURL())},
                }
                row = {
                    "columns": [desc] + [obj.getKeys()[k] for k in keys]
                }
                rows.append(row)
            rows = sorted(rows, key=lambda r: r["columns"][0]["text"].lower())
            for index, row in enumerate(rows):
                row["id"] = "%s" % index

        return {
            "results": {
                "columns": columns,
                "rows": rows,
            }
        }

    # Helper methods

    def get_relative_url(self, url):
        from urllib.parse import urlparse  # TODO unparse
        _url = urlparse(url)
        return "%s?%s" % (_url.path, _url.query)

    def addState(self):
        return self.state_manager.addState()

    def getState(self, state_id):
        state = self.state_manager.getState(state_id)
        if state:
            return self.state_manager.getState(state_id)
        return self.addState()

    def setup_module_data(self, state, module):
        from cdb.comparch import tools
        from cdb.comparch.content import ModuleContent
        from cdb.objects import DataDictionary
        contents = ((module.app_conf_exp_dir, "Dev"),
                    (module.app_conf_master_exp_dir, "Master"),
                    (module.std_conf_exp_dir, "Distribution"))
        for confdir, content_from in contents:
            if os.path.isdir(confdir):
                mc = ModuleContent(module.module_id, confdir)
                state.item_types = sorted(mc.getItemTypes())
                state.content_from = content_from
                state.item_types_content = {}
                if state.item_types:
                    for item_type in state.item_types:
                        sw = DataDictionary().getRootClassRecord(item_type)
                        desc = tools.GetDescription("switch_tabelle",
                                                    {"classname": sw.classname})
                        items = mc.getItems(item_type).values()
                        items_keys = set((key for it in items
                                          for key in it.getKeys()))
                        state.item_types_content[item_type] = {'name': item_type,
                                                               'desc': desc,
                                                               'items_keys': sorted(iter(items_keys)),
                                                               'items': items}
                    break


@ComparchApi.path(model=ComparchApiModel, path="")
def _path(extra_parameters):
    return ComparchApiModel(extra_parameters)


@ComparchApi.json(model=ComparchApiModel)
def _get_json(model, request):
    return model.get_results()


class ApplicationState():
    """
    Container for application states. Instances are
    only created and managed by the ApplicationStateManager.
    """

    def __init__(self):
        self.state_id = cdbuuid.create_uuid()


class ApplicationStateManager():
    """
    Simple application state manager, which
    uses a LRU list with a maximum limit of states to be
    hold in memory.
    If the limit exceeds by adding a new state, the
    most unused state will be removed.
    """

    def __init__(self, max_states):
        self.max_states = max_states
        self.states = {}
        self.lru = []

    def addState(self):
        state = ApplicationState()
        self.states[state.state_id] = state
        self.lru.append(state.state_id)
        to_delete = self.lru[:-self.max_states]
        for del_id in to_delete:
            if del_id in self.states:
                del self.states[del_id]
        del self.lru[:len(to_delete)]
        return state

    def getState(self, state_id):
        try:
            del self.lru[self.lru.index(state_id)]
        except ValueError:
            pass
        state = self.states.get(state_id, None)
        if state:
            self.lru.append(state_id)
        else:
            state = self.addState()
        return state

    def clearStates(self):
        self.lru = []
        self.states = {}
