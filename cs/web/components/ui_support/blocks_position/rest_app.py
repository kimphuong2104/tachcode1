#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from __future__ import absolute_import

import six

from cdb.util import PersonalSettings
from cs.platform.web import PlatformApp


def _get_default_settings(app_id, update_PersonalSettings):
    from cs.web.components.ui_support.attribute_groups import CsWebAttrBlock
    blocks = CsWebAttrBlock.KeywordQuery(application_id=app_id)
    nr_cols = max([block.position_column for block in blocks])
    grouped_blocks = [[] for _ in six.moves.range(nr_cols)]
    for block in blocks:
        grouped_blocks[block.position_column - 1].append(block)
    grouped_blocks = [sorted(block_group, key=lambda x:x.position_row) for block_group in grouped_blocks]
    blocksposition_str = ';'.join([','.join([block.block_id for block in block_group])
                                   for block_group in grouped_blocks])
    if update_PersonalSettings:
        PersonalSettings().setValue(app_id, "blocksposition", blocksposition_str)
    return blocksposition_str


def _get_blocksposition_str(app_id, update_PersonalSettings):
    blocksposition_str = PersonalSettings().getValueOrDefault(app_id, "blocksposition", '')
    if not len(blocksposition_str):
        blocksposition_str = _get_default_settings(app_id, update_PersonalSettings)
    return blocksposition_str


def _get_block_names_from_str(app_id, blocksposition_str):
    return six.moves.reduce(lambda x, y: x + y,
                  [col.split(',') for col in _get_blocksposition_str(app_id, False).split(';') if col],
                  [])

# ---------- Application ----------


class BlocksPositionApp(PlatformApp):

    def __init__(self, app_id):
        super(BlocksPositionApp, self).__init__()
        self.app_id = app_id


# ---------- Models ----------


class BlocksPositionModel(object):
    def __init__(self, app_id):
        self.app_id = app_id

    @property
    def BlocksPosition(self):
        return _get_block_names_from_str(self.app_id, _get_blocksposition_str(self.app_id, False))


class BlockModel(object):

    def __init__(self, app_id, block_name):
        self.block_name = block_name
        self.app_id = app_id

    @property
    def position_column(self):
        blocksposition_str = _get_blocksposition_str(self.app_id, False)
        col_contains_block = [self.block_name in col for col in blocksposition_str.split(';')]
        return col_contains_block.index(True) + 1 if True in col_contains_block else None

    @property
    def position_row(self):
        blocksposition_str = _get_blocksposition_str(self.app_id, False)
        columns_blocks = blocksposition_str.split(';')[self.position_column - 1].split(',')
        return columns_blocks.index(self.block_name) + 1 if self.block_name in columns_blocks else None

    def set_position(self, col, row):
        blocks_lst = [s.split(',') if s else [] for s in _get_blocksposition_str(self.app_id, False).split(';')]
        # delete old
        _ = [col_lst.remove(self.block_name) if self.block_name in col_lst else col_lst for col_lst in blocks_lst]
        # insert at new position
        bpl = blocks_lst[col - 1]
        bpl.insert(row - 1, self.block_name)
        blocks_lst[col - 1] = bpl
        PersonalSettings().setValue(
                                    self.app_id,
                                    "blocksposition",
                                    ';'.join([','.join(col_lst) for col_lst in blocks_lst]))


# ---------- Paths ----------
@BlocksPositionApp.path(path="", model=BlocksPositionModel)
def _get_blocks_position(app):
    return BlocksPositionModel(app_id=app.app_id)


@BlocksPositionApp.path(path='{block_name}', model=BlockModel)
def _get_block(block_name, app):
    return BlockModel(app.app_id, block_name)


# ---------- Views ----------


@BlocksPositionApp.json(model=BlocksPositionModel)
def _get_settings_default(model, request):
    return [request.view(BlockModel(model.app_id, blk_name))
            for blk_name in model.BlocksPosition]


@BlocksPositionApp.json(model=BlockModel)
def _get_block_default(model, _request):
    return {'blockName': model.block_name,
            'position_column': model.position_column,
            'position_row': model.position_row
    }


@BlocksPositionApp.json(model=BlockModel, request_method='POST')
def _post_block(model, request):
    if "position_column" in list(request.json) and "position_row" in list(request.json):
        model.set_position(request.json["position_column"], request.json["position_row"])
    return request.view(model)
