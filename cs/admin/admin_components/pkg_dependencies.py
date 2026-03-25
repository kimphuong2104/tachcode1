# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Backend functions for the app that generates a graphviz file to display
the package dependencies.
"""

import morepath

from cs.platform.web import PlatformApp
from cdb.comparch.packages import Package

from cs.platform.web.root import Internal


class PackageDependenciesApp(PlatformApp):
    pass


@Internal.mount(app=PackageDependenciesApp,
                path="/cs-admin/pkg_dependencies")
def mount_pkg_dependencies_app():
    return PackageDependenciesApp()


class PackageDependenciesModel(object):
    def __init__(self, package_name):
        self.package_name = package_name


@PackageDependenciesApp.path(model=PackageDependenciesModel, path="")
def _path(package_name=None):
    return PackageDependenciesModel(package_name)


_NEED_SL18_ERR_SVG = """
<svg width="500" height="50" xmlns="http://www.w3.org/2000/svg">
 <g>
  <title>Error retrieving Dependencies</title>
  <text font-style="normal" font-weight="normal" xml:space="preserve"
        text-anchor="start" font-family="sans-serif" font-size="14"
        id="svg_1" y="31" x="10" stroke-width="0" stroke="#000"
        fill="#FF0000">
You need at least CE 15.5, SL 19 to display package dependencies</text>
 </g>
</svg>
"""


@PackageDependenciesApp.view(model=PackageDependenciesModel)
def _retrieve_file(model, request):
    content = None
    if model.package_name:
        pkg = Package.ByKeys(model.package_name)
        if pkg:
            try:
                content = pkg.get_package_dependencies_as_svg()
            except AttributeError:
                content = _NEED_SL18_ERR_SVG
        else:
            content = Package.get_all_package_dependencies_as_svg()
    response = morepath.Response(content_type="image/svg+xml",
                                 body=content)
    response.cache_control.private = True
    response.cache_control.no_cache = True
    response.cache_control.max_age = 0
    return response
