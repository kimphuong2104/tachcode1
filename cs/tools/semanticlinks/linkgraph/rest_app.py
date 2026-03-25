#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
import subprocess
import json
import webob

from cdb import util
from cdb import auth
from cdb import sqlapi
from cs.platform.web.rest import CollectionApp
from cs.platform.web.uisupport import get_webui_link
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal
from cs.platform.web.rest.generic.main import App as GenericApp
from cdb.plattools import killableprocess
from cdb.objects import ByID
from cs.tools.semanticlinks import LinkGraphConfig
from cs.tools.semanticlinks.linkgraph import renderer
from cs.tools.semanticlinks.linkgraph import get_graphviz_dot_path
from cs.tools.semanticlinks import SemanticLink


def filter_to_string(filter):
    h = filter.split(";")
    return "','".join(h).replace("%%20", " ")


def filter_to_list(filter):
    return filter.split(";")


def raiseOnError(result):
    if isinstance(result, dict):
        error = result.get("error", None)
        if error:
            raise webob.exc.HTTPInternalServerError(error)
    return result


class LinkGraphConfigApp(GenericApp):
    def __init__(self):
        super(LinkGraphConfigApp, self).__init__("linkgraphconfig")


@CollectionApp.mount(app=LinkGraphConfigApp, path="linkgraphconfig")
def _mount_app():
    return LinkGraphConfigApp()


@GenericApp.defer_links(model=LinkGraphConfig)
def _defer_linkgraphconfig(app, _linngraphconfig):
    return app.child(LinkGraphConfigApp())


class LinkGraphSVG(object):
    def __init__(self, root, radius, svg):
        self.root = root
        self.radius = radius
        self.svg = svg


@LinkGraphConfigApp.path(path='{keys}/svg/{root_object_id}/{radius}/{filter}', model=LinkGraphSVG)
def _get_svg(keys, root_object_id, radius, filter, app):
    config = app.get_object(keys)
    svg, dot = "", ""
    r = int(radius)
    if r < 0:
        r = 200
    root = ByID(root_object_id)
    if root:
        filtermap = {}
        if filter:
            filters = filter.split("@")
            linktypes = filters[0]
            if linktypes:
                filtermap["links"] = filter_to_list(linktypes)
            classes = filters[1]
            if classes:
                filtermap["classes"] = filter_to_list(classes)
            obsolete = filters[2]
            filtermap["obsolete"] = obsolete

        dot = renderer.render_dot(config, root, r, filtermap)
        dot_path = get_graphviz_dot_path()
        cmds = [dot_path] + config.callargs.split(' ')
        proc = killableprocess.Popen(cmds,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     )
        (stdout, stderr) = proc.communicate(dot.encode('utf-8'))  # @UnusedVariable
        if proc.returncode == 0:
            svg = renderer.render_svg(stdout, '')
        return LinkGraphSVG(root, r, svg)
    return LinkGraphSVG(root, r, svg)


@LinkGraphConfigApp.json(model=LinkGraphSVG)
def _get_svg_json(model, request):
    return {
        "root_object_id": model.root.cdb_object_id,
        "root_desc": model.root.GetDescription(),
        "radius": model.radius,
        "svg": model.svg.decode()
    }


class LinkGraphSettings(JsonAPI):
    pass


@Internal.mount(app=LinkGraphSettings, path="/cs-tools-semanticlinks-linkgraph")
def _mount_app():
    return LinkGraphSettings()


class LinkGraphTests(JsonAPI):
    pass


@Internal.mount(app=LinkGraphTests, path="/cs-tools-semanticlinks-tree")
def _mount_app():
    return LinkGraphTests()


class SettingsModel(object):
    def __init__(self, key):
        self.settings = util.PersonalSettings()
        self.user = auth.persno
        self.key = key

    def getInitialSettings(self):
        usr_settings = self.get_settings()
        usr_settings.update({
            "user": self.user,
            "key": self.key})
        return {"settings": usr_settings}

    def get_settings(self):
        default = {}
        settings = self.settings.getValueOrDefault("cs.tools.semanticlinks.linkgraph",
                                                   self.key,
                                                   "")
        result = json.loads(settings)
        return result

    def set_settings(self, value):
        old = self.get_settings()
        if old:
            settings = old.copy()
            settings.update(value)
        else:
            settings = value
        if settings != old:
            self.settings.setValue("cs.tools.semanticlinks.linkgraph",
                                   self.key,
                                   json.dumps(settings))


class TestModel(object):
    def __init__(self, key, radius):
        self.cdb_object_id = key
        self.user = auth.persno
        self.radius = radius

    def subjectInput_objectOutput(self, cdb_object_id, radius):
        H = 0
        radius2 = int(radius)
        result = []
        s = 1
        if s <= radius2:
            dataOutput1 = self.getSubjects(cdb_object_id, s)
            for row2 in range(0, len(dataOutput1)):
                if H == 0:
                    object_byID = cdb_object_id
                    level = 0
                    real_obj = ByID(object_byID)
                    obj_icon = real_obj.GetObjectIcon()
                    obj_description = real_obj.GetDescription()
                    obj_link = get_webui_link(None, real_obj)
                    x = {}
                    x['object_object_id'] = object_byID
                    x['obj_description'] = obj_description
                    x['obj_icon'] = obj_icon
                    x['obj_link'] = obj_link
                    x['radius'] = level
                    result.append(x)
                    H = 1
                x = self.getValues(dataOutput1, row2)
                result.append(x)
                cdb_object_id = x['object_object_id']
                s = 2
                while s <= radius2:
                    dataOutput2 = self.getSubjects(cdb_object_id, s)
                    for row2 in range(0, len(dataOutput2)):
                        x = self.getValues(dataOutput2, row2)
                        result.append(x)
                        cdb_object_id = x['object_object_id']
                    s += 1

        return result

    def getSubjects(self, cdb_object, level):
        sqlSelect = "SELECT Distinct subject_object_id, object_object_id, %s as radius" % (level)
        sqlFrom = " FROM cdb_semantic_link  "
        addCondition = " WHERE subject_object_id = '%s' " % (cdb_object)
        dataOutput2 = sqlapi.RecordSet2(sql=sqlSelect + sqlFrom + addCondition)
        return dataOutput2

    def getValues(self, dataOutput, row):
        dict_output = dict([map(str.strip, i.split('=')) for i in
                            str(dataOutput[row]).split(',')])  # Get data from DB obj_obj_id, subj_obj_id
        object_byID = dict_output['object_object_id']
        level = dict_output['radius']
        real_obj = ByID(object_byID)
        obj_icon = real_obj.GetObjectIcon()
        obj_description = real_obj.GetDescription()
        obj_link = get_webui_link(None, real_obj)
        x = {}
        x['object_object_id'] = object_byID
        x['obj_description'] = obj_description
        x['obj_icon'] = obj_icon
        x['obj_link'] = obj_link
        x['radius'] = level
        return x

    def firstIterate(self, cdb_object_id):
        object_byID = cdb_object_id
        level = 0
        real_obj = ByID(object_byID)
        obj_icon = real_obj.GetObjectIcon()
        obj_description = real_obj.GetDescription()
        x = {}
        x['object_object_id'] = object_byID
        x['obj_description'] = obj_description
        x['obj_icon'] = obj_icon
        x['radius'] = level
        return x


@LinkGraphSettings.path(path="settings/{key}", model=SettingsModel)
def _get_settings_model(key):
    return SettingsModel(key)


@LinkGraphSettings.json(model=SettingsModel)
def get_initial_settings(model, request):
    return raiseOnError(model.getInitialSettings())


@LinkGraphSettings.json(model=SettingsModel, request_method="POST")
def set_settings(model, request):
    model.set_settings(request.json)
    return {"settings": model.get_settings()}


@LinkGraphTests.path(path="{cdb_object_id}/{radius}", model=TestModel)
def _get_settings_model(cdb_object_id, radius):
    return TestModel(cdb_object_id, radius)


@LinkGraphTests.json(model=TestModel)
def set_settings(model, request):
    return model.subjectInput_objectOutput(model.cdb_object_id, model.radius)


class DeleteLink(JsonAPI):
    pass


@Internal.mount(app=DeleteLink, path="/cs-tools-semanticlinks-link-delete")
def _mount_app():
    return DeleteLink()


class DeleteModel(object):
    def __init__(self, cdb_object_id):
        self.cdb_object_id = cdb_object_id

    def deleteLink(self):
        link = SemanticLink.ByKeys(self.cdb_object_id)
        if link:
            link.Delete()


@DeleteLink.path(path="{cdb_object_id}", model=DeleteModel)
def _get_delete_model(cdb_object_id):
    return DeleteModel(cdb_object_id)


@DeleteLink.json(model=DeleteModel)
def delete_model_link(model, request):
    return model.deleteLink()
