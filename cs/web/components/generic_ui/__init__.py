#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Implementation of generic "object detail" and "class" applications for REST
visible classes.
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import os
import sys
from collections import defaultdict

from cdb import rte
from cdb import sig
from cs.platform.web import static
from cs.platform.web.root import Root, get_root
from cs.web.components.configurable_ui import (ConfigurableUIApp,
                                               filter_by_roles)
from cs.web.components.ui_support.related_objects import RelatedObjectTile


class NoViewError(RuntimeError):
    pass


class GenericUIApp(ConfigurableUIApp):
    """ Morepath app to render a generic (configured) UI for an "object detail"
        or "class" page. The application is mounted under `/info`, and provides
        paths of the form `/info/{rest_name}[/{object_key}]`.
    """

    def __init__(self):
        super(GenericUIApp, self).__init__()


@Root.mount(app=GenericUIApp, path="info")
def _mount_app():
    return GenericUIApp()


def get_ui_app(request):
    return get_root(request).child('info')


def _select_view_intern(configurations, classdef, names, viewname):
    # whatever we select, only entries that are actually accessible by the
    # user have to be considered
    configs = filter_by_roles(configurations)
    if viewname is None:
        # filter candidates down to relevant names
        configs = [c for c in configs if c["classname"] in names]
        # find highest priority
        max_prio = max(c.get("priority", -sys.maxsize) for c in configs) if configs else 0
        # filter down to views with that prio
        configs = [c for c in configs if c.get("priority", -sys.maxsize) == max_prio]
        if len(configs) == 1:
            return configs[0]
        elif len(configs) > 1:
            # more than one remains, search upwards in class hierarchy
            for name in names:
                found = [c for c in configs if c["classname"] == name]
                if len(found) > 0:
                    return found[0]
        raise NoViewError("No view found for class '%s' without viewname"
                          % classdef.getClassname())
    else:
        for name in names:
            # walk up the class hierarchy, searching for the first match
            found = [c for c in configs if (c["viewname"] == viewname and
                                            c["classname"] == name)]
            if len(found) > 0:
                return found[0]
        raise NoViewError("No view found for class '%s' / viewname '%s'"
                          % (classdef.getClassname(), viewname))


def select_view(configurations, classdef, viewname=None):
    """ Determine the view configuration to use from the list supplied  in
        `configurations`.

        If `viewname` is not None, use a configuration with that name if one
        exists and is visible to one of the user's roles. The class hierarchy
        is searched starting from the given `classdef` up to the root class,
        if no configuration was found '*' is tried as fallback.

        If `viewname` is None, the algorithm works as follows:

        * Determine, from the complete class hierarchy starting at `classdef`,
          all viewnames that are visible to one of the user's roles.
        * If more than one view is found, select the view(s) with the highest
          `priority` value.
        * If more than one view is found, select one that is defined nearest
          to the given `classdef` in the class hierarchy (with fallback as
          above).
        * Finally, select one at random from the remaining candidates
    """
    # classnames to try in the correct order, with fallback worked in
    clsnames = ([classdef.getClassname()] +
                [name for name in classdef.getBaseClassNames()] +
                ["*"])
    return _select_view_intern(configurations, classdef, clsnames, viewname)
