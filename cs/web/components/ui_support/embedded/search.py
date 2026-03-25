#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
"""

from __future__ import absolute_import
__revision__ = "$Id: search.py 198884 2019-07-22 10:29:58Z tst $"

import os
from cdb import sig, util
from cs.web.components.configurable_ui import ConfigurableUIModel
from cs.web.components.ui_support.search_favourites import SearchFavouriteCollection
from cs.web.components.ui_support.embedded.main import EmbeddedOperationApp


class EmbeddedSearchModel(ConfigurableUIModel):
    """ Morepath model class for a "embedded search" page.
    """

    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, classname):
        super(EmbeddedSearchModel, self).__init__()
        self.classname = classname
        self.set_page_frame('csweb_embedded_empty_page_frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'searchapp.json'))
        return config_file_path

    def load_application_configuration(self):
        super(EmbeddedSearchModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )



@EmbeddedOperationApp.path(path="search/{classname}", model=EmbeddedSearchModel)
def _get_model(classname, extra_parameters):
    return EmbeddedSearchModel(classname)



@EmbeddedOperationApp.view(model=EmbeddedSearchModel, name="document_title", internal=True)
def _document_title(model, _request):
    return util.get_label("csweb_embedded_search")


@sig.connect(EmbeddedSearchModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    class_ops = {}
    class_ops['CDB_Search'] = []
    class_ops['CDB_Search'].append({'classname': model.classname, 'opname': 'CDB_Search'})

    app_setup.merge_in(["class_view"], {
        "classOpInfos": class_ops,
        "searchFavourites": SearchFavouriteCollection(model.classname).make_link(request)})
    app_setup.merge_in(["embedded_search"], {
        "classname": model.classname
    })
