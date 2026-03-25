# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json
import logging

from cdb.lru_cache import lru_cache
from cdb.platform import gui
from cs.platform.web.rest.support import rest_key

LAYOUT_POSITIONS = {
    "primaryText": "1",
    "secondaryText": "2",
    "beforeText": "b",
    "afterText": "a",
}


@lru_cache(clear_after_ue=True)
def cached_rest_key(object_handle):
    return rest_key(object_handle)


def _get_ui_link(request, object_handle):
    return f"/info/{object_handle.getClassDef().getRESTName()}/{cached_rest_key(object_handle)}"


def _generateListItems(
    displayConfId, dictAttrFunc, dictObjHandles, sortedKeys, request
):
    """
    :param displayConfId: ID of the display config defining how list items
        are to be displayed
    :type displayConfId: basestring

    :param dictAttrFunc: Functions which retrieve the object handle
        attributes used as properties for the components specified by the
        display config. Indexed by layout position.
    :type dictAttrFunc: dict

    :param dictObjHandles: Object Handles
    :type dictObjHandles: dict

    :param sortedKeys: UUIDs in order of appearance
    :type sortedKeys: list

    :param request: HTTP request for generating links
    :type request: Request

    :returns: list_of_items, isError
    :rtypes: tuple (list, bool)

    Generates a list of dictionaries each containing all the attributes
    necessary to display the corresponding list entry, as well as the ID
    of the display config.

    .. rubric :: Example of "list_of_items"

    .. code-block :: python

        [
            {
                "attrs": {
                    "layout position": "attribute value",
                    "sortValue": "value of attribute to sort by",
                    "system:ui_link": "link to object page"
                },
                "display_config": "displayConfId"
            },
        ]

    If any error occurs, the return value's second element will be ``True``
    and the first one may be empty or incomplete.
    """
    list_of_items = []

    for object_id in sortedKeys:
        matched_object_handle = dictObjHandles[object_id]
        dict_of_attributes = {}

        for key, values in dictAttrFunc.items():
            attrFunc = values["function"]
            # Catch all errors, since the functions here can be
            # user-defined and therefore may produce a variety of errors
            try:
                attr = attrFunc(matched_object_handle)
            except Exception as e:
                logging.exception(
                    gui.Message.GetMessage(
                        "cdbpcs_list_err_python_func",
                        values["function_name"],
                        values["display_type"],
                        values["classname"],
                        values["layout_position"],
                        e.args[0],
                    )
                )
                return [], True

            # The functions called here have to ensure, that a
            # valid JSON-serializable value is returned
            # in case of an error that value can be None or empty
            try:
                json.dumps(attr)
            except TypeError:
                logging.exception(
                    gui.Message.GetMessage(
                        "cdbpcs_list_err_python_func_return_not_json_serializable",
                        str(type(attr)),
                    )
                )
                return [], True

            dict_of_attributes[key] = attr

        # as another additional attribute append the UI_Link to the
        # objectpage of the object
        if displayConfId == "Postings":
            # Workaround for Postings due to the fact that activities topics are handled different
            object_link = (
                "/activitystream/posting/" + matched_object_handle.cdb_object_id
            )
        else:
            object_link = _get_ui_link(request, matched_object_handle)

        dict_of_attributes["system:ui_link"] = object_link
        clsname = matched_object_handle.getClassDef().getClassname()
        restname = matched_object_handle.getClassDef().getRESTName()
        restkey = cached_rest_key(matched_object_handle)
        item = {
            "attrs": dict_of_attributes,
            "display_config": displayConfId,
            "contextObject": {
                "system:classname": clsname,
                "system:navigation_id": restkey,
                "@type": f"/api/v1/class/{clsname}",
                "@id": f"{request.application_url}/api/v1/collection/{restname}/{restkey}",
            },
        }
        list_of_items.append(item)

    return list_of_items, False


def _generateDisplayConfig(listOfConfigEntries, classname):
    """
    :param listOfConfigEntries: Entries specifying how to display an item
    :type lisOfConfigEntries: list of
        ``cs.pcs.projects.common.lists.list.ListItemConfigEntries``

    :param classname: classname of items to display
    :type classname: string

    :returns: display_config, dict_of_attribute_functions, isError
    :rtype: tuple (dict, dict, bool)

    The return value consists of three tuple elements:

    The first one is a display config dictionary containing the components
    to be rendered and function parameters to determine their properties
    for each layout position.

    .. rubric :: Example display config dictionary

    .. code-block :: python

        {
            "1": [
                {
                    "comp": component,
                    "props": properties,
                },
            ],
            "2": [],
            "b": [],
            "a": [],
        }

    The second one is a dictionary matching the keys to the
    property-generating functions.

    The third element states whether an error occurred somewhere. If it
    did, the method returns early and other return values may be empty or
    incomplete.
    """
    display_config = {
        layout_pos_short: [] for layout_pos_short in LAYOUT_POSITIONS.values()
    }
    dict_of_attribute_functions = {}
    # count is used to generate attribute keys, that are unique among all
    # attributes stored in the item's attribute dict
    count = 0
    for config_entry in listOfConfigEntries:
        display_type = config_entry.DisplayType.name
        component = config_entry.getDisplayTypeComponent()
        layout_position = config_entry.layout_position
        layout_pos_short = LAYOUT_POSITIONS[layout_position]
        properties = {}
        try:
            property_functions = config_entry.getDisplayTypeProperties()
        except Exception as e:
            # an error occurred during calling the python function, which
            # returns the functions generating the properties

            logging.exception(
                gui.Message.GetMessage(
                    "cdbpcs_list_err_python_help_func",
                    config_entry.DisplayType.fqpyname,
                    e.args[0],
                )
            )

            return {}, {}, True

        for property_name in property_functions:
            property_function = property_functions[property_name]
            # generate an unique key among all entries in the item's
            # attribute dict
            new_key = f"{layout_pos_short}:{display_type}_{count}"
            properties.update({property_name: new_key})
            dict_of_attribute_functions.update(
                {
                    new_key: {
                        "function": property_function,
                        "function_name": config_entry.DisplayType.fqpyname,
                        "layout_position": layout_position,
                        "display_type": display_type,
                        "classname": classname,
                    }
                }
            )
            count += 1

        display_config[layout_pos_short].append(
            {
                "comp": component,
                "props": properties,
            }
        )

    return display_config, dict_of_attribute_functions, False
