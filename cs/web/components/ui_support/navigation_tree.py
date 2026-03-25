# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module navigation_tree

This is the documentation for the navigation_tree module.
"""
from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


import logging

from cdbwrapc import NavigationStructure

import six

from cdb import constants
from cdb import kernel
from cdb import util
from cdb.platform.mom import entities
from cs.web.components.ui_support.utils import ui_name_for_class, get_classname_from_app_link


class NavigationClassContent(object):
    """
    A class that returns navigation content for a given class -
    at this time an entry for the class view app.
    """
    def __init__(self, class_id, extra_parameters):
        self.class_id = class_id
        self.extra_parameters = extra_parameters

    def get_content_ui_name(self):
        """
        Returns the UI name of the class.
        """
        if self.class_id:
            cdef = entities.CDBClassDef(self.class_id)
            return ui_name_for_class(cdef)
        return None

    def _get_filtered_query_op_args(self):
        """
        Return the list of predfined args for the query op.
        Filters some attributes, because at this time there are
        annoying tooltips if an attribute is not part of the
        query mask.
        The function removes the source of mapped attributes if there is
        a correspondig mapping. If a multilang attribute is set in different
        languages the function keeps the users language and remove the others.
        Empty query attributes are also ignored.
        """
        cdef = entities.CDBClassDef(self.class_id)
        d = {arg.name: arg
             for arg in cdef.getPredefinedOpArgs(constants.kOperationSearch, True)
             if arg.value}
        if d and not self.extra_parameters.get("as_configured", 0):
            # No need for a predefined classname if there are no base classes
            # or we have our own configuration
            if not cdef.isSubClass() or cdef.getConfiguredUIName():
                d.pop(cdef.getAttrIdentifier("cdb_classname"), None)
                # Also remove mappings of cdb_classname
                for ma in kernel.MappedAttributes(cdef.getClassname()):
                    if ma.getReferer() == "cdb_classname":
                        d.pop(cdef.getAttrIdentifier(ma.getName()), None)

            # Handle multilang attibutes assuming that all values are
            # semantically identical. We do not want the user to have
            # multiple languages in the side bar
            for ma in cdef.getMultiLangAttributeDefs():
                remove = False
                for attr in ma.getLanguageAttributeDefs():
                    if remove:
                        d.pop(attr.getIdentifier(), None)
                    else:
                        remove = attr.getIdentifier() in d

            # Handle Sources of mapped fields
            for ma in kernel.MappedAttributes(cdef.getClassname()):
                aid = cdef.getAttrIdentifier(ma.getName())
                predef_mapped = d.get(aid, None)
                if predef_mapped:
                    # Look if the source is also there
                    sid = cdef.getAttrIdentifier(ma.getReferer())
                    predef_source = d.get(sid, None)
                    # If the the mapped attribute contains the mapping of the
                    # source there is no need for the user to see the source
                    if predef_source and \
                       ma.getValue(predef_source.value) == predef_mapped.value:
                        d.pop(sid)

        return list(six.itervalues(d))

    def get_content_ui_link(self):
        """
        Returns a link to the classes page. This might include query
        parameter if the class is a decomposition class.
        """
        ui_name = self.get_content_ui_name()
        if ui_name:
            base_link = "/info/%s" % ui_name
            # The class might have obligatory search args.
            query_args = self._get_filtered_query_op_args()
            params = {"search_on_navigate": True}
            pos = 0
            for arg in query_args:
                params["search_attributes[%d]" % pos] = arg.name
                params["search_values[%d]" % pos] = arg.value
                pos += 1
            if pos:
                return "%s?%s" % (base_link,
                                  six.moves.urllib.parse.urlencode(params))
            else:
                return base_link
        return None

    def get_classname(self):
        if self.class_id:
            cdef = entities.CDBClassDef(self.class_id)
            return cdef.getClassname()

    def has_content(self):
        return bool(self.get_content_ui_name())

    def supports_fav_content(self, _request):
        # If there are any predefined args we cannot support favourites
        # as long as there are not searchable
        return self.has_content() and not self._get_filtered_query_op_args()

    def get_entries(self, _request):
        return {}


class NavigationTreeContent(object):
    """
    Generates the content for a navigation id. This can be a submenu
    and some class specific things if the entry corresponds with a class.
    """
    def __init__(self, navigation_id, extra_parameters):
        self.navigation_id = navigation_id
        self.extra_parameters = extra_parameters

    def get_node_id(self):
        return six.moves.urllib.parse.unquote(self.navigation_id)

    def _generate_submenu_conf(self, submenu, position, request):
        return {
            "position": position,
            "module_type": "submenu",
            "module_data": {
                "headline": None,
                "conf_link": request.link(submenu)
            }
        }

    def _generate_classcontent_conf(self, class_content, position):
        return {
            "position": position,
            "module_type": "homepage",
            "module_data": [
                {
                    "position": position,
                    "type": "search",
                    "title": util.get_label("button_search"),
                    "tooltip": util.get_label("button_search"),
                    "imageSrc": "/resources/icons/byname/csweb_search/0",
                    "link": class_content.get_content_ui_link(),
                    "is_default_homepage": True
                }
            ]
        }

    def _generate_favcontent_conf(self, class_content, position):
        return {
            "position": position,
            "module_type": "favorites",
            "module_data": {
                "classname": class_content.get_classname()
            }
        }

    def get_entries(self, request):
        result = []
        # if the node is a class, provide access to the class app
        try:
            node = NavigationStructure().get_node(self.get_node_id())
        except KeyError:
            logging.getLogger(__name__).warning("Failed to find structure node %s",
                                                self.get_node_id())
            return {}
        clid = node.get("class_id", "")
        class_content = NavigationClassContent(clid, self.extra_parameters)
        if class_content.has_content():
            result.append(self._generate_classcontent_conf(class_content, 0))

        # Add Favourites
        if class_content.supports_fav_content(request):
            result.append(self._generate_favcontent_conf(class_content, 10))

        # Look fo submenus
        submenu = NavigationTreeSubmenuContent(self.navigation_id, self.extra_parameters)
        if submenu.has_entries(request):
            result.append(self._generate_submenu_conf(submenu, 20, request))
        return result


class NavigationTreeSubmenuContent(object):
    def __init__(self, navigation_id, extra_parameters):
        self.navigation_id = navigation_id
        self.extra_parameters = extra_parameters

    def _generate_submenu_entry(self, node, request):
        icons = node["icons"]
        fallback = "/resources/icons/byname/csweb_broken"
        result = {"title": node["label"],
                  "imageSrc": icons[0]["url"] if icons else fallback,
                  "tooltip": node["label"]}
        if node.get("no_of_subitems", 0) > 0:
            nid = six.moves.urllib.parse.quote(node["id"])
            ntc = NavigationTreeContent(nid, self.extra_parameters)
            # Do not show empty submenus
            if ntc.get_entries(request):
                result.update({"is_direct_link": False,
                               "app_link": None,
                               "conf_link": request.link(ntc)})
                return result
        else:
            clid = node.get("class_id", "")
            ncc = NavigationClassContent(clid, self.extra_parameters)
            ui_link = ncc.get_content_ui_link()
            if ui_link:
                result.update({"is_direct_link": False,
                               "app_link": ui_link,
                               "conf_link": None,
                               "className": get_classname_from_app_link(ui_link)})
                return result
        return {}

    def get_node_id(self):
        return six.moves.urllib.parse.unquote(self.navigation_id)

    def has_entries(self, request):
        nodes = NavigationStructure().get_nodes(self.get_node_id())
        for node in nodes:
            nid = six.moves.urllib.parse.quote(node["id"])
            ntc = NavigationTreeContent(nid, self.extra_parameters)
            if ntc.get_entries(request):
                return True
        return False

    def get_entries(self, request):
        nodes = NavigationStructure().get_nodes(self.get_node_id())
        result = []
        for node in nodes:
            node_config = self._generate_submenu_entry(node, request)
            if node_config:
                result.append(node_config)
        return result
