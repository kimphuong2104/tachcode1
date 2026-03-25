#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Common setups to be used to embed another page.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig
from cs.web.components.configurable_ui import (ConfigurableUIApp,
                                               ConfigurableUIModel,
                                               SinglePageModel)


class EmbeddedPageApp(ConfigurableUIApp):
    """
    The base application of the page frame for embedding another page into it.
    It should be specialized and mounted. For example::

        class MyEmbeddedApp(EmbeddedPageApp):
            pass


        @Root.mount(app=MyEmbeddedApp, path="my_embeded_app")
        def _mount_app():
            return MyEmbeddedApp()


        class MyEmbeddedModel(EmbeddedPageModel):
            def __init__(self, cdb_object_id):
                super(MyEmbeddedModel, self).__init__()
                self._cdb_object_id = cdb_object_id

            def _get_object(self):
                return SomeObjectClass.ByKeys(self._cdb_object_id)

            def get_embedded_page_url(self):
                obj = self.get_object()
                return "/the_real_url_of_embedded_page_showing_object/%s" % (
                    obj.cdb_object_id)


        @MyEmbeddedApp.path(path="{cdb_object_id}", model=MyEmbeddedModel)
        def _get_model(cdb_object_id):
            model = MyEmbeddedModel(cdb_object_id)
            if model.get_object() is None:
                return None
            return model

    """
    def __init__(self):
        super(EmbeddedPageApp, self).__init__()


class EmbeddedPageModel(SinglePageModel):
    page_name = "cs-web-components-embedded_page"

    def get_embedded_page_url(self):
        return ""


@EmbeddedPageApp.path(path="", model=EmbeddedPageModel)
def _get_model():
    """
    The specialized app must always define the paths. If not,
    this default `None` value will cause a 404 error to
    avoid unexpected render errors or a confusing blank page in front end.
    """
    return None


@sig.connect(EmbeddedPageModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    app_setup.merge_in(["cs-web-components-base-embedded_page"],
                       {"link": model.get_embedded_page_url()})
