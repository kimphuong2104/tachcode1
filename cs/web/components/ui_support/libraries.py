#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import

from . import App
from cs.web.components.library_config import Libraries, get_dependencies, _get_script_urls


class LibraryModel(object):
    def __init__(self, library_name):
        self.library_name = library_name

    def get_libraries(self, request):
        library = Libraries.ByKeys(self.library_name)
        libraries = get_dependencies(library) if library is not None else []
        libraries = [{
            "library_name": lib.library_name,
            "script_urls": _get_script_urls(lib.library_name, lib.library_version)
        } for lib in libraries]
        return {
            "libraries": libraries
        }


@App.path(path="/libraries/{library_name}", model=LibraryModel)
def _get_libraries(library_name):
    return LibraryModel(library_name)


@App.json(model=LibraryModel)
def _view_libraries(self, request):
    return self.get_libraries(request)
