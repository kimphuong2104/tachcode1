#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module navigation_modules

This is the documentation for the navigation_modules module.
It provides several classes to build up the dictionaries
required for the secondary navigation level as well as for its
navigation modules.
"""

from __future__ import absolute_import
import cdbwrapc

from cdb.objects.iconcache import IconCache
from cs.web.components.ui_support.utils import resolve_ui_name, get_classname_from_app_link

__all__ = ["NavigationModules",
           "NavigationHomepageModule",
           "NavigationFavoritesModule",
           "NavigationAppViewModule",
           "NavigationSubMenuModule"]


class NavigationModules(object):
    """
    Class to provide a list of modules defined
    for the secondary navigation level.
    """
    def __init__(self):
        self.module_list = []

    def addModule(self, pos, nav_module):
        """
        Adds a navigation module (of class type ``NavigationHomepageModule``,
        ``NavigationFavoritesModule``, ``NavigationAppViewModule`` or
        ``NavigationSubMenuModule``) to the list of modules for the secondary
        navigation level. The parameter ``pos`` describes the position to
        be used. ``nav_module`` is an instance of a navigation module class.
        """
        self.module_list.append((pos, nav_module))

    def frontEndModuleList(self):
        """
        Returns a dictionary that contains the list and configuration
        of all used navigation modules as well as their positions. The
        result of this call can be used by the front end to setup the
        required navigation modules in the front end code.
        """
        return [{
            "position": p,
            "module_type": m.moduleType(),
            "module_data": m.moduleDescription()
        } for (p, m) in self.module_list]


class NavigationHomepageModule(object):
    """
    Class to setup and provide data for the homepage module.
    """
    def __init__(self, rest_or_ui_name):
        """
        Initializes the homepage module and generates the
        first entry to the search application for a class
        referenced by its REST or UI name.
        """
        self.module_description = [{
            "position": 0,
            "type": "search",
            "title": cdbwrapc.get_label("web.base.do_extended_search"),
            "tooltip": cdbwrapc.get_label("web.base.do_extended_search"),
            "imageSrc": IconCache.getIcon("csweb_search"),
            "link": "/info/%s" % rest_or_ui_name,
            "is_default_homepage": True
        }]

    def moduleType(self):
        """
        Returns the type of this navigation module ("homepage")
        """
        return "homepage"

    def moduleDescription(self):
        """
        Returns the module configuration used by a
        ``NavigationModules`` instance.
        """
        return self.module_description

    def addAdditionalHomepageEntry(self, label_id, tooltip_id, link, icon_id):
        """
        Add additional links (beside the search application) to the homepage
        module. ``label_id``, ``tooltip_id`` and ``icon_id`` are configured
        items in the database. The parameter ``link`` will be used as provided.
        """
        self.module_description.append({
            "position": self.module_description[-1]["position"] + 10,
            "type": "link",
            "title": cdbwrapc.get_label(label_id),
            "tooltip": cdbwrapc.get_label(tooltip_id),
            "imageSrc": IconCache.getIcon(icon_id),
            "link": link,
            "is_default_homepage": False
        })


class NavigationFavoritesModule(object):
    """
    Class to setup and provide data for the favorites module.
    The favorites module can be used to get a list of all object and search
    favorites for a given REST or UI name.
    """
    def __init__(self, rest_or_ui_name):
        """
        Initializes the favorites module for a class referenced by its REST or
        UI name.
        """
        (classname, _, _) = resolve_ui_name(rest_or_ui_name)
        self.module_description = {
            "classname": classname
        }

    def moduleType(self):
        """
        Returns the type of this navigation module ("favorites")
        """
        return "favorites"

    def moduleDescription(self):
        """
        Returns the module configuration used by a
        ``NavigationModules`` instance.
        """
        return self.module_description


class NavigationAppViewModule(object):
    """
    Class to setup and provide data for the appview module.
    """
    def __init__(self, headline_id, conf_link):
        """
        Initializes the appview module.
        The ``headline_id`` is a configured item in the database.
        It will be used by the front end to label the appview
        module for the user.
        The parameter ``conf_link`` should contain a link the front
        end could call to get the result of this class's moduleContent
        method.
        """
        self.module_content = []
        self.module_description = {
            "headline": cdbwrapc.get_label(headline_id),
            "conf_link": conf_link
        }

    def moduleType(self):
        """
        Returns the type of this navigation module ("appview")
        """
        return "appview"

    def moduleDescription(self):
        """
        Returns the module configuration used by a
        ``NavigationModules`` instance.
        """
        return self.module_description

    def appendAppEntry(self, title, link, icon_id):
        """
        Adds a new entry to the appview module. The ``icon_id``
        is a configured item in the database. The parameters
        ``title`` and ``link`` are raw values and will be used as
        they are.
        """
        length = len(self.module_content)
        pos = self.module_content[-1]["position"] + 10 if length else 0
        self.module_content.append({
            "position": pos,
            "link": link,
            "imageSrc": IconCache.getIcon(icon_id),
            "title": title
        })

    def moduleContent(self):
        """
        Returns the appview's content. This should be provided
        to the front end, if the given ``conf_url`` for this
        instance gets called.
        """
        return self.module_content


class NavigationSubMenuModule(object):
    """
    Class to setup and provide data for the submenu module.
    """
    def __init__(self, headline_id, conf_link):
        """
        Initializes the submenu module.
        The ``headline_id`` is a configured item in the database.
        It will be used by the front end to label the submenu
        module for the user.
        The parameter ``conf_link`` should contain a link the front
        end could call to get the result of this class's moduleContent
        method.
        """
        self.module_content = []
        self.module_description = {
            "headline": cdbwrapc.get_label(headline_id),
            "conf_link": conf_link
        }

    def moduleType(self):
        """
        Returns the type of this navigation module ("submenu")
        """
        return "submenu"

    def moduleDescription(self):
        """
        Returns the module configuration used by a
        ``NavigationModules`` instance.
        """
        return self.module_description

    def appendAppEntry(self, title, tooltip, icon_id, app_link=None, conf_link=None):
        """
        Adds a new submenu entry to the module. If ``app_link`` is provided,
        the submenu entry points to its target and does not show another
        submenu arrow in the front end. If not provided, ``conf_link`` should
        be provided. Calling the given ``conf_link`` should then return a ``NavigationModules``
        structure, which describes the next navigation level's module configuration.
        The ``icon_id`` is a configured item in the database. The parameters
        ``title``, ``tooltip`` and ``link`` are raw values and will be used as
        they are.
        """
        self.module_content.append({
            "is_direct_link": app_link is not None,
            "title": title,
            "tooltip": tooltip,
            "imageSrc": IconCache.getIcon(icon_id),
            "conf_link": conf_link,
            "app_link": app_link,
            "className": get_classname_from_app_link(app_link)
        })

    def moduleContent(self):
        """
        Returns the submenu's content. This should be provided
        to the front end, if the given ``conf_url`` for this
        instance gets called.
        """
        return self.module_content
