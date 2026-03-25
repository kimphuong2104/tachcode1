#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
from webob.exc import HTTPNotFound

from cdb.objects import Object
from cdb.platform.mom import entities
from cs.platform.web.rest import support
from cs.platform.web.rest.relship.main import make_relship_target
from cs.platform.web.rest.generic.main import get_relship_app
from cs.platform.web.uisupport import App


class RelatedObjectTile(Object):
    __maps_to__ = "csweb_related_object_tile"
    __classname__ = "csweb_related_object_tile"

    def get_label(self):
        """
        Returns the label of the tile according to the sessions language.
        This is usually the value of the multilanguage field `label`.
        If the configuration is empty the function tries to get the
        label from the relationship configuration.
        """
        result = self.label
        if not result:
            cldef = entities.CDBClassDef(self.classname)
            rsdef = cldef.getRelationshipByRolename(self.relship_id)
            if rsdef and rsdef.is_valid():
                result = rsdef.get_label()
        return result

    def resolve_relship(self, request, obj, rest_name, rest_id):
        relship_target = make_relship_target(obj, self.relship_id)
        return {
            'name': self.relship_id,
            'label': self.get_label(),
            'relship': request.view(
                relship_target,
                name='complete-target',
                app=get_relship_app(request, rest_name, rest_id)
            )
        }


class RelatedObjects(object):
    def __init__(self, class_name, rest_id):
        self.rest_name = support.rest_name_for_class_name(class_name)
        self.rest_id = rest_id
        self.obj = support.get_object_from_rest_name(self.rest_name, rest_id)
        if not self.obj:
            raise HTTPNotFound()

    def to_json(self, request):
        required_relships = request.json.get('relships')
        query_params = {
            'classname': self.obj.GetClassname(),
            'order_by': 'position',
        }
        if required_relships:
            query_params['relship_id'] = required_relships

        configs = RelatedObjectTile.KeywordQuery(**query_params)
        return [config.resolve_relship(request, self.obj, self.rest_name, self.rest_id)
                for config in configs]


@App.path(path="related_objects/{rest_name}/{rest_id}", model=RelatedObjects)
def _path_related_objects(rest_name, rest_id):
    return RelatedObjects(rest_name, rest_id)


@App.json(model=RelatedObjects, request_method='POST')
def _view_related_objects(self, request):
    return self.to_json(request)
