# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module smlgenerator
^^^^^^^^^^^^^^^^^^^

Main module with central entry point for all cads
to generate parametric models from SC data
"""

import pkg_resources
import logging

from cs.cadbase.sml.ucvariantsbase import ucSupported, NoUcSupport

LOGGER = logging.getLogger(__name__)

__docformat__ = "restructuredtext en"
__revision__ = "$Id: smlgenerator.py 230899 2021-10-26 08:57:35Z nle $"

# Exported objects
__all__ = []


__cad_sml_plugins = dict()

__cad_uc_plugins = dict()


PLUGIN_ENTRY_POINT_GROUP = "cs.cadsml.plugins"
PLUGIN_ENTRY_POINT_UC = "cs.caduc.plugins"


def _loaded_sml_plugins():
    global __cad_sml_plugins
    if not __cad_sml_plugins:
        __cad_sml_plugins = _import_plugins(PLUGIN_ENTRY_POINT_GROUP)
    return __cad_sml_plugins


def _loaded_uc_plugins():
    global __cad_uc_plugins
    if not __cad_uc_plugins:
        __cad_uc_plugins = _import_plugins(PLUGIN_ENTRY_POINT_UC)
    return __cad_uc_plugins


def _import_plugins(group):
    _plgs = {}
    for ep in pkg_resources.iter_entry_points(group=group):
        try:
            _plgs[ep.name] = ep.load()
        except Exception as e:
            LOGGER.debug("Exception during import of sml/uc/plugin: name: "
                         "%s: module_name: %s, ex: %s",
                         ep.name,
                         ep.module_name,
                         e)
    return _plgs


def update_for_cad(item, cad_system, view="3DVIEW"):
    """
    Updates the generic or derived file with generic group information

    :param item: cs.vp.Item
    :param cad_system: string. Name of CAD system from erzeug_system or first part of erzeug_system

    :return: mq-job for cad_system or None if no plugin was found
    """
    splitted_system = cad_system.split(":")[0]
    plg = _loaded_sml_plugins().get(splitted_system.lower())
    if plg is not None:
        return plg(item, cad_system, view)


def update_for_all(item, viewmap=None):
    """
    Updates the generic or derived file with generic group information
    for all registered CAD systems

    :param item: cs.vp.Item
    :param viewmap: None or dict cad_system to viewname
                    Default is to use 3DVIEW unless a special
                    viewname is given per CAD System (First part
                    of erzeug_system name in lower case).

    :return: list of mq-job for every affected cad-system
             or None if no plugin was found
    """
    jobs = []
    for cad, plg in list(_loaded_sml_plugins().items()):
        view = None
        if viewmap is not None:
            view = viewmap.get(cad)
        if view is not None:
            job = plg(item, view=view)
        else:
            job = plg(item)
        jobs.append(job)
    return jobs


def uc_update_for_cad(item,
                      cad_system,
                      view="3DVIEW",
                      preset_callback=None,
                      complete_table=False):
    """
    Updates the generic or derived file with classification data

    :param item: cs.vp.Item

    :param cad_system: string. Name of CAD system from erzeug_system or first part of erzeug_system

    :param preset_callback: None or callable with parameters (generic_document, item).
        Returns a dict with preset attributes for preset of new generated documents.
        This is last update on all preset parameters.
        The order for the preset list is:

        - docattributes from .variantconfig file
        - data from CADDOK_BASE/etc/systemdefaults.json (dict with name/values pairs)
        - result from preset_callback

        Preset for new documents is only relevant for systems
        using a single document per variant item.
        It is ignored for familytable operation.

    :param complete_table: Bool. For familytable CADs update the complete table with
        current values or only the given item (False).

    :return: mq-job for cad_system or None if no plugin was found

    :raises: NoUcSupport if universal classification is not installed
        or cs.workspaces does not support uc
    """
    if not ucSupported():
        raise NoUcSupport()
    splitted_system = cad_system.split(":")[0]
    plg = _loaded_uc_plugins().get(splitted_system.lower())
    if plg is not None:
        return plg(item,
                   cad_system,
                   view,
                   preset_callback=preset_callback,
                   complete_table=complete_table)


def uc_update_for_all(item,
                      viewmap=None,
                      preset_callback=None,
                      complete_table=False):
    """
    Updates the generic or derived file with with classification data
    for all registered CAD systems

    :param item: cs.vp.Item
    :param viewmap: None or dict cad_system to viewname
                    Default is to use 3DVIEW unless a special
                    viewname is given per CAD system (First part
                    of erzeug_system name in lower case).
    :param preset_callback: None or callable with parameters
        (generic_document, item). Returns a dict with preset attributes
        for preset of new generated documents.
        This is last update on all preset parameters.
        The order for the preset list is:

        - docattributes from .variantconfig file
        - data from CADDOK_BASE/etc/systemdefaults.json (dict with name/values pairs)
        - result from preset_callback

        Preset for new documents is only relevant for systems
        using a single document per variant item.
        It is ignored for familytable operation

    :param complete_table: Bool. For familytable CADs update the complete
        table with current values oder only the given item (False)

    :return: list of mq-job for every affected cad-system
        or None if no plugin was found

    :raises: NoUcSupport if universal classification is not installed
        or cs.workspaces does not support uc
    """
    if not ucSupported():
        raise NoUcSupport()
    jobs = []
    for cad, plg in list(_loaded_uc_plugins().items()):
        view = None
        if viewmap is not None:
            view = viewmap.get(cad)
        if view is not None:
            job = plg(item, view=view, preset_callback=None)
        else:
            job = plg(item)
        jobs.append(job)
    return jobs


def test():
    from cs.vp.items import Item
    # i = Item.ByKeys("000027", "")
    # j = uc_update_for_cad(i, "ProE")
    i = Item.ByKeys("000037", "")
    j = uc_update_for_cad(i, "CatiaV5")
    print(("%s" % j))
    # update_for_all(i, {"catiav5": "3DVIEW", "proe": "3DVIEW_PROE"})
