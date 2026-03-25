#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

from typing import Sequence

import datetime
import io
import json
import logging
import os
import shutil
import sys
from collections import namedtuple
import six
from importlib import resources

from cdb import bootstrap
from cdb.comparch import pkgtools

_LOGGER = logging.getLogger(__name__)


def resource_dir():
    return resources.files('cs.web') / 'resources'


class MakeException(Exception):
    pass


def rmrf(path):
    """
    a crossplatform recursive directory remove, which is able to handle
    pathnames longer than 256 chars (windows limit)
    """
    if os.path.exists(path):
        _LOGGER.debug('> rm -rf %s', path)
        if sys.platform == "win32":
            path = u"\\\\?\\%s" % os.path.abspath(path)
        shutil.rmtree(path)


def puts(msg, put_timestamp):
    ts = "[%s] " % datetime.datetime.now().time().strftime("%H:%M:%S") if put_timestamp else ""
    sys.stdout.write("%s%s\n" % (ts, msg))
    sys.stdout.flush()


def jsonread(jsonfile):
    """Read the content of a jsonfile"""
    with io.open(jsonfile, "rb") as fhandle:
        return json.load(fhandle)


def find_webui_packages():
    """
    Returns a list of all Elements package names, where the package contains one
    or more Web UI applications. The list is sorted according to the package
    dependency order.
    """
    distributions, errors = bootstrap.find_cdb_distributions()
    if errors:
        errors.insert(0, "The package installation is inconsistent!")
        raise bootstrap.InstallationInconsistent("\n* ".join(errors))
    return [
        d.project_name
        for d in bootstrap.sorted_distributions(list(six.itervalues(distributions)))
        if get_javascript_bundles(d.project_name)
    ]


def find_webdev_packages():
    """
    Returns only packages with a webui, that contain a file called `setup.py`.
    This excludes packages installed as eggs.
    """
    pkgs = find_webui_packages()
    return [p for p in pkgs if os.path.isfile(pkgtools.path_join(p, 'setup.py'))]


WebAppInfo = namedtuple('WebAppInfo',
                        ['pkg_name', 'pkg_path', 'app_path', 'component_name_space'])


def find_webui_apps(pkg_name=None):
    """
    Find all Web UI applications from all installed Elements packages. Returns a
    list of WebAppInfos.
    """
    result = []
    if pkg_name is None:
        for pkg_name in find_webui_packages():
            if pkg_name is not None:
                result.extend(find_webui_apps(pkg_name))
    else:
        pkg_path = pkgtools.path_join(pkg_name)
        for app_path in get_javascript_bundles(pkg_name):
            with io.open(os.path.join(pkg_path, app_path, 'namespace.json')) as nsfile:
                component_ns = json.load(nsfile)
            result.append(WebAppInfo(pkg_name=pkg_name,
                                     pkg_path=pkg_path,
                                     app_path=app_path,
                                     component_name_space=component_ns))
    return result


def get_javascript_bundles(packagename: str) -> Sequence[os.PathLike[str]]:
    """
    Get the relative paths to the javascript bundles
    packaged together with the given package name.

    :param packagename: The name of the package to get the javascript bundles for
    :return: The list of relative paths to the javascript bundles
    """
    from importlib.metadata import distribution

    apps = distribution(packagename).read_text("apps.json")
    if not apps:
        return []
    return json.loads(apps)
