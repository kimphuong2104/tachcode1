#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from dataclasses import dataclass, field
from typing import Any, Callable

from cdb import ue
from cdb.platform import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cdbwrapc import get_label
from cs.variants.api.occurrence_walk_generator import OccurrenceWalkGenerator

CAD_PLUGINS: list["CADPlugin"] = []
OpenCADCallback = (
    Callable[
        [str, OccurrenceWalkGenerator, Any],
        None,
    ]
    | None
)


@dataclass
class CADPlugin:
    erzeug_system: str
    callback: OpenCADCallback
    label: str | None = None
    kwargs: Any = field(default_factory=dict)

    @property
    def title(self):
        """return the human-readable title"""
        if self.label:
            return get_label(self.label)
        else:
            return self.erzeug_system


def register_open_in_cad_plugin(
    erzeug_system: str,
    callback: OpenCADCallback,
    label: str | None = None,
    **kwargs: Any
):
    """
    Register a plugin to be used inside the "Show in CAD" operation

    callback called during the 'now' hook from operation 'open in cad'
    the callback receives the following values:

        - erzeug_system: string like 'CatiaV5:Prod'
        - walk_generator: an instance of cs.variants.api.occurrence_walk_generator.OccurrenceWalkGenerator
        - ctx: the operation context (now)
        - 'label' is used in the dropdown to display a nice name.
           An id for a label in the system is expected as a label (e.g.:  cdbvp_show_bom_item)
           If label is None then the 'erzeug_system' is used

    kwargs can be given for additional params (not used yet)

    :param erzeug_system: erzeug system like "CatiaV5:Prod"
                            used to autodetect the correct CAD system for the selected maxbom
    :param callback:
    :param label: the label to be displayed for humans

    :return:
    """
    CAD_PLUGINS.append(CADPlugin(erzeug_system, callback, label, kwargs))


def get_plugin(erzeug_system: str) -> CADPlugin | None:
    """
    find the first registered plugin with the given `erzeug_system`.
    return None if no plugin found
    :param erzeug_system:
    :return:
    """
    found = [plugin for plugin in CAD_PLUGINS if plugin.erzeug_system == erzeug_system]
    if found:
        return found[0]

    return None


def find_plugins_for_maxbom(maxbom):
    """
    try to find all plugins for the given `maxbom`

    if no plugin found an empty list is returned

    :param maxbom: the maxbom
    :return: a list with the plugins
    """
    list_of_plugins = []

    if maxbom is None:
        return list_of_plugins

    list_of_erzeug_system = maxbom.Documents.erzeug_system

    if not list_of_erzeug_system:
        raise ue.Exception(
            "cs_variants_cad_plugin_no_plugin_for_maxbom",
            maxbom.teilenummer,
            maxbom.t_index,
        )

    for each_erzeug_system in set(list_of_erzeug_system):
        plugin = get_plugin(each_erzeug_system)
        if plugin is not None:
            list_of_plugins.append(plugin)

    return list_of_plugins


class CADPluginCatalog(CDBCatalog):
    """used as dropdown to select the correct plugin"""

    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        self.setResultData(CADPluginCatalogData(self))

    def allowMultiSelection(self):
        return self.kDisableMultiSelection

    def handleResultDataSelection(self, selected_rows):
        title = ""
        erzeug_system = ""
        if selected_rows:
            plugin = CAD_PLUGINS[selected_rows[0]]
            title = plugin.title
            erzeug_system = plugin.erzeug_system

        self.setValue("plugin_selection", title)
        self.setValue("plugin_selected_erzeug_system", erzeug_system)


class CADPluginCatalogData(CDBCatalogContent):
    def __init__(self, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)

    def getNumberOfRows(self):
        return len(CAD_PLUGINS)

    def getRowData(self, row):
        return [CAD_PLUGINS[row].title]
