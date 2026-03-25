# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com
#
# Version:  $Id$

from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIModel, ConfigurableUIApp, SinglePageModel
from cs.classification import api
from cs.classification.rest.utils import ensure_json_serialiability
from cs.platform.web import JsonAPI, root

import os

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


class ObjectClassificationModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, absorb):
        super(ObjectClassificationModel, self).__init__()
        self.absorb = absorb
        self.set_page_frame('cs.classification.web.empty-frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'editapp.json'))
        return config_file_path

    def load_application_configuration(self):
        super(ObjectClassificationModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent", {"configuration": self.config_filename()}
        )

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]


class ObjectClassificationApp(ConfigurableUIApp):

    def __init__(self):
        super(ObjectClassificationApp, self).__init__()


@byname_app.BynameApp.mount(app=ObjectClassificationApp, path="object_classification")
def _mount_app():
    return ObjectClassificationApp()


@ObjectClassificationApp.path(path="", model=ObjectClassificationModel, absorb=True)
def _get_model(absorb):
    return ObjectClassificationModel(absorb)


@ObjectClassificationApp.view(model=ObjectClassificationModel, name="base_path", internal=True)
def get_base_path(model, request):
    return request.path


class CopyClassificationModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, absorb, src_object_id):
        super(CopyClassificationModel, self).__init__()
        self.absorb = absorb
        self.src_object_id = src_object_id
        self.set_page_frame('cs.classification.web.empty-frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'copyapp.json'))
        return config_file_path

    def load_application_configuration(self):
        super(CopyClassificationModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]


class CopyClassificationApp(ConfigurableUIApp):

    def __init__(self):
        super(CopyClassificationApp, self).__init__()


@byname_app.BynameApp.mount(app=CopyClassificationApp, path="copy_classification")
def _mount_copy_app():
    return CopyClassificationApp()


@CopyClassificationApp.path(path="{src_object_id}", model=CopyClassificationModel, absorb=True)
def _get_copy_model(src_object_id, absorb):
    return CopyClassificationModel(absorb, src_object_id)


@CopyClassificationApp.view(model=CopyClassificationModel, name="base_path", internal=True)
def get_create_base_path(model, request):
    return request.path


class CreateClassificationModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, absorb, classname):
        super(CreateClassificationModel, self).__init__()
        self.absorb = absorb
        self.classname = classname
        self.set_page_frame('cs.classification.web.empty-frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'createapp.json'))
        return config_file_path

    def load_application_configuration(self):
        super(CreateClassificationModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]


class CreateClassificationApp(ConfigurableUIApp):

    def __init__(self):
        super(CreateClassificationApp, self).__init__()


@byname_app.BynameApp.mount(app=CreateClassificationApp, path="create_classification")
def _mount_create_app():
    return CreateClassificationApp()


@CreateClassificationApp.path(path="{classname}", model=CreateClassificationModel, absorb=True)
def _get_create_model(classname, absorb):
    return CreateClassificationModel(absorb, classname)


@CreateClassificationApp.view(model=CreateClassificationModel, name="base_path", internal=True)
def get_create_base_path(model, request):
    return request.path

class UpdateClassificationModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, absorb, classname):
        super(UpdateClassificationModel, self).__init__()
        self.absorb = absorb
        self.classname = classname
        self.set_page_frame('cs.classification.web.empty-frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'updateapp.json'))
        return config_file_path

    def load_application_configuration(self):
        super(UpdateClassificationModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]


class UpdateClassificationApp(ConfigurableUIApp):

    def __init__(self):
        super(UpdateClassificationApp, self).__init__()


@byname_app.BynameApp.mount(app=UpdateClassificationApp, path="update_classification")
def _mount_update_app():
    return UpdateClassificationApp()


@UpdateClassificationApp.path(path="{classname}", model=CreateClassificationModel, absorb=True)
def _get_update_model(classname, absorb):
    return UpdateClassificationModel(absorb, classname)


@UpdateClassificationApp.view(model=CreateClassificationModel, name="base_path", internal=True)
def get_update_base_path(model, request):
    return request.path


class SearchClassificationModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, absorb, classname):
        super(SearchClassificationModel, self).__init__()
        self.absorb = absorb
        self.classname = classname
        self.set_page_frame('cs.classification.web.empty-frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'searchapp.json'))
        return config_file_path

    def load_application_configuration(self):
        super(SearchClassificationModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]


class SearchClassificationApp(ConfigurableUIApp):

    def __init__(self):
        super(SearchClassificationApp, self).__init__()


@byname_app.BynameApp.mount(app=SearchClassificationApp, path="search_classification")
def _mount_search_app():
    return SearchClassificationApp()


@SearchClassificationApp.path(path="{classname}", model=SearchClassificationModel, absorb=True)
def _get_search_model(classname, absorb):
    return SearchClassificationModel(absorb, classname)


@SearchClassificationApp.view(model=SearchClassificationModel, name="base_path", internal=True)
def get_search_base_path(model, request):
    return request.path

class ClassificationDiffInternalApp(JsonAPI):
    def __init__(self):
        pass

    def update_app_setup(self, app_setup, model, request):
        pass


@root.Internal.mount(
    app=ClassificationDiffInternalApp, path="cs_classification_diff"
)
def _mount_internal_app():
    return ClassificationDiffInternalApp()


class ClassificationDiffModel(object):  # just to make morepath happy
    def __init__(self, first_object_oid, second_object_oid):
        try:
            self.object_oid_1 = first_object_oid
            self.object_oid_2 = second_object_oid

        except Exception:  # pylint: disable=W0703
            pass


@ClassificationDiffInternalApp.path(
    path="diff/{first_object_key}/{second_object_key}",
    model=ClassificationDiffModel,
)
def get_objects_model(app, first_object_key, second_object_key):
    return ClassificationDiffModel(first_object_key, second_object_key)


@ClassificationDiffInternalApp.json(model=ClassificationDiffModel)
def get_classification_diff_data(model, request):
    object_1_oid = model.object_oid_1 if model.object_oid_1 else None
    object_2_oid = model.object_oid_2 if model.object_oid_2 else None

    compare_data = api.compare_classification(
        object_1_oid, object_2_oid, with_metadata=True, narrowed=False, check_rights=True
    )

    return dict(
        left_title="Linkes Objekt",
        right_title="Rechtes Objekt",
        classification_diff=ensure_json_serialiability(compare_data),
    )

