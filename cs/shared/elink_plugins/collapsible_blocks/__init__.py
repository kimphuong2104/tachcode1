#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
CDB eLink plug-in "collapsible blocks".
====================================

Use this plug-in to display informations as blocks or even
collapsible/expandable blocks.

Usage:

    1. import the javascript and css resources in page template:

        <link href="${options.plugins}collapsible_blocks/collapsible_blocks.css"
              rel="stylesheet" type="text/css" />
        <script src="${options.plugins}collapsible_blocks/collapsible_blocks.js"
                type="text/javascript"></script>

    2. use the macros to display blocks in page template:

        Normal blocks
        -------------
        There are 2 kinds of blocks: normal blocks, which are always expanded and collapsible blocks.
        To use the normal blocks the `block_container` macro should be called like this:

            <tal:layout metal:use-macro="global_plugins['collapsible_blocks'].macros['block_container']">
              <metal:filltitle fill-slot="block_title">
                <h2>Example</h2>
              </metal:filltitle>
              <metal:blockcontent fill-slot="block_content">
                  <div>Content</div>
              </metal:blockcontent>
            </tal:layout>

        The plug-in provides a block-like frame for the representation. The 2
        slots `block_title` and `block_content` must be filled respectively
        for the application.

        Collapsible blocks
        ------------------
        To use the collapsible blocks the `collapsible_block_container` macro should be called like this:

            <tal:layout metal:use-macro="global_plugins['collapsible_blocks'].macros['collapsible_block_container']"
                        define="block_id string:example_block;
                                block_expanded True">
              <metal:filltitle fill-slot="block_title">
                <h2>Example</h2>
              </metal:filltitle>
              <metal:blockcontent fill-slot="block_content">
                  <div>Content</div>
              </metal:blockcontent>
            </tal:layout>

        In addition to the 2 must-be-filled slots there are 2 variables
        `block_id` and `block_expanded` required. `block_id` must be unique
        to identify the block by the collapse button. `block_expanded` can
        be set to True or False to set the initial state of the block to
        expanded or not.

        Dropdown menu
        -------------
        A dropdown menu at the title line can be added to both kinds of blocks
        by filling the `dropdown_menu` slot:

            <tal:layout metal:use-macro="global_plugins['collapsible_blocks'].macros['block_container']">
              ...
              <metal:menu fill-slot="dropdown_menu">
                <li><a href="#" target="_blank">Menu 1</a></li>
                <li class="divider"></li>
                <li><a href="#" target="_blank">Menu 2</a></li>
              </metal:menu>
              ...
            </tal:layout>

    3. active the plug-in in javascript, e.g.:

        // === Activates Collapsible Blocks plug-in ===
        var collapsibleBlocks = new cdbElinkCollapsibleBlocks();
        // Saves the current settings for appl. 'cdb.elink.exampleApp'
        collapsibleBlocks.blockSettingID = 'cdb.elink.exampleApp';
        //Tells cdb.elink to run that plug-in.
        cdb.elink.addApplication('cdb.elink.collapsibleblocks', collapsibleBlocks);

       The `blockSettingID` property of the plug-in instance should be set if
       the current block settings(order, expanded/collapsed state, see below)
       should be restored. It should represent the current application
       unambiguously. The settings would be saved as user settings in CDB, that
       means personalized. Technically the `blockSettingID` would be treated as
       `setting_id` in the user setting relation in database.

    4. save/read the block settings:

        Block order
        -----------
        The blocks must be ordered to enable the setting saving function. It
        is recommended to use numerical order. The order must be assigned to
        blocks through variable `block_order` and should be unique.

        In powerscript:
            class MyTemplate(elink.Template):
                def render(self, context):
                    ...
                    return {
                            ...
                            "blocks": [(1, obj1), (2, obj2)],
                            ...
                            }

        In page template:
            <tal:blocks repeat="blocksetting blocks">
                <tal:layout
                    metal:use-macro="global_plugins['collapsible_blocks'].macros['block_container']"
                    define="block_order blocksetting[0]">
                  ...
                  <metal:filltitle fill-slot="block_title">
                    <h2>${blocksetting[1].GetDescription()}</h2>
                  </metal:filltitle>
                  ...
                </tal:layout>
            </tal:blocks>

        Reordering
        ----------
        The blocks can also be reordered via Drag&Drop on the horizontal ruler
        at the title line. To activate this feature, the parent container of
        the blocks must have a attribute `data-elink-block-sortable` being set,
        which defines the possible drag direction, thus `x` for
        horizontal, `y` for vertical and empty string for both directions:

            <div id="blocks_parent" data-elink-block-sortable="y">
            <tal:blocks repeat="blocksetting blocks">
                <tal:layout
                    metal:use-macro="global_plugins['collapsible_blocks'].macros['block_container']"
                    define="block_order blocksetting[0]">
                  ...
                  <metal:filltitle fill-slot="block_title">
                    <h2>${blocksetting[1].GetDescription()}</h2>
                  </metal:filltitle>
                  ...
                </tal:layout>
            </tal:blocks>
            </div>

        In this example the blocks can be reordered vertically.

        Saving settings
        ---------------
        If the `blockSettingID` property of the javascript plug-in instance is
        set, see step#3, the order of the blocks, and the expanded state of
        collapsible blocks would be automatically stored in CDB. If the settings
        should not be saved, just set the `blockSettingID` to empty string.

        Restoring settings
        ------------------
        The saved settings can also be restored. They need to be read from CDB
        in the powerscript and passed to template or javascript.

        In powerscirpt:
            class MyTemplate(elink.Template):
                def render(self, context):
                    ...
                    blockmapping = {1: obj1,
                                    2: obj2}
                    app_id = "cdb.elink.exampleApp"  # It is the same as blockSettingID
                                                     # in javascript
                    from cs.shared.elink_plugins.collapsible_blocks import get_blocks_order
                    order = get_blocks_order(app_id)
                    from cs.shared.elink_plugins.collapsible_blocks import get_blocks_expand
                    expanded = get_blocks_expand(app_id)
                    # expanded not defined/saved: expand no block
                    if expanded is None:
                        expanded = []
                    return {
                            ...
                            "blockmapping": blockmapping,
                            "order": order,
                            "expanded": expanded
                            ...
                            }

        In page template:
            <tal:blocks repeat="block_order order">
                <tal:layout
                    metal:use-macro="global_plugins['collapsible_blocks'].macros['block_container']"
                    define="block_order block_order;
                            block_expanded block_order in expanded">
                  ...
                  <metal:filltitle fill-slot="block_title">
                    <h2>${blockmapping[block_order].GetDescription()}</h2>
                  </metal:filltitle>
                  ...
                </tal:layout>
            </tal:blocks>

    This plug-in provides only basic visual styling for the components. The
    individual styling of the blocks can be defined by the application itself.
"""


from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import elink, util

__all__ = ["set_blocks_order", "set_blocks_expand",
           "get_blocks_order", "get_blocks_expand"]


def _log_setting_err(e):
    from cdb import misc
    misc.cdblogv(misc.kLogErr, 7, "Error by person setting: %s" % e)


def set_blocks_order(app_id, order):
    result = 0
    try:
        util.PersonalSettings().setValue(
            "elink.plugins.collapsible_blocks.order", app_id, order)
        result = 1
    except RuntimeError as e:
        _log_setting_err(e)
    return {"updated": result}


def set_blocks_expand(app_id, expanded):
    result = 0
    try:
        util.PersonalSettings().setValue(
            "elink.plugins.collapsible_blocks.expand", app_id, expanded)
        result = 1
    except RuntimeError as e:
        _log_setting_err(e)
    return {"updated": result}


def get_blocks_order(app_id):
    _order = util.PersonalSettings().getValueOrDefault(
                "elink.plugins.collapsible_blocks.order", app_id, "")
    return [] if not _order else _order.split(",")


def get_blocks_expand(app_id, dflt=""):
    _expanded = util.PersonalSettings().getValueOrDefault(
                    "elink.plugins.collapsible_blocks.expand", app_id, dflt)
    return [] if not _expanded else _expanded.split(",")


@elink.using_template_engine("chameleon")
class CollapsibleBlocks(elink.Application):
    """Application which responses to the collapsible blocks plug-in."""

    def setup(self):
        self.addJSON(set_blocks_order)
        self.addJSON(set_blocks_expand)


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = CollapsibleBlocks("Collapsible Blocks Plug-in")
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)
