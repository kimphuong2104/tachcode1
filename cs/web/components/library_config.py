#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import os
from cdb import CADDOK
from cdb.objects import Object, Reference_N, Forward, Reference_1
from cs.platform.web import static

__revision__ = "$Id$"

fLibraries = Forward(__name__ + ".Libraries")
fLibraryDependencies = Forward(__name__ + ".LibraryDependencies")


class Libraries(Object):
    __maps_to__ = "csweb_libraries"
    __classname__ = "csweb_libraries"

    Dependencies = Reference_N(fLibraryDependencies,
                               fLibraryDependencies.library_name == fLibraries.library_name)


class LibraryDependencies(Object):
    __maps_to__ = "csweb_library_dependencies"
    __classname__ = "csweb_library_dependencies"

    Library = Reference_1(Libraries,
                          Libraries.library_name == fLibraryDependencies.library_name_dependency)


def get_dependencies(lib):
    def _get_dependencies(_lib, prev_libs):
        libs = [_lib]
        for dependency in _lib.Dependencies:
            library = dependency.Library
            if library not in prev_libs:
                dependencies = _get_dependencies(library, prev_libs + [_lib])
                libs = dependencies + libs
        return libs

    result = []
    for _lib in _get_dependencies(lib, []):
        if _lib not in result:
            result.append(_lib)
    return result



def url(f, prefix="", dev_env=False, manifest=None):
    if f.dev_fname and dev_env:
        fname = f.dev_fname
    else:
        fname = f.fname
    ext = os.path.splitext(fname)[1].lower()
    hashed_name = fname if manifest is None else manifest.get_hashed(fname)
    if ext in [u".js"]:
        result = "" + prefix + "/" + hashed_name + ""
    elif ext in [u".css", u".map", u".eot", u".svg", u".ttf", u".woff", u".woff2"]:
        result = ""
    else:
        raise ValueError("Undefined file extension: %s" % (fname))
    return result


# this is a workaround for E053764
def _get_script_urls(library_name, library_version):
    """
    Returns the script urls for the given library name and version.
    """
    try:
        library = static.Registry().get(library_name, library_version)
        debug = bool(CADDOK.get('ELINK_DEBUG'))
        if debug:
            library._manifest.reload()
        prefix = library.url()
        files = (f[0] for f in library.files.values()
                 if f[1] is None or f[1] == debug)
        urls = (url(f, prefix, debug, manifest=library._manifest) for f in files)
        result = []
        for u in urls:
            if u:
                result.append(u)
    except KeyError:
        raise ValueError("Library %s with version %s is not defined" % (library_name,
                                                                        library_version))
    return result
